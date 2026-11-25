// Package recommender serves frozen, offline-computed recommendation artifacts.
//
// The Go service never trains or re-scores models (WBS §2.3). It loads the
// serving bundle written by scripts/generate_serving_bundle.py, verifies its
// checksums and explanation evidence at startup, and then answers requests by
// filtering and truncating the saved ranked lists.
package recommender

import (
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/explanation"
)

// MaxTopK is the length of every frozen ranked list in the bundle.
const MaxTopK = 20

// Errors returned for invalid requests. Handlers map them to 4xx responses.
var (
	ErrUnknownModel        = errors.New("unknown model id")
	ErrUnknownItems        = errors.New("candidate_ids contains items outside the eligible catalog")
	ErrNoComparisonExport  = errors.New("no exported comparison lists for this user")
	ErrInvalidTopK         = fmt.Errorf("top_k must be between 1 and %d", MaxTopK)
	ErrEmptyUserID         = errors.New("user_id is required")
	ErrModelNotServable    = errors.New("model has no serving lists for this user")
	errBundleChecksumFails = errors.New("serving bundle checksum mismatch")
)

// UnknownItemsError lists rejected candidate IDs.
type UnknownItemsError struct{ IDs []string }

func (e *UnknownItemsError) Error() string { return fmt.Sprintf("%s: %v", ErrUnknownItems, e.IDs) }
func (e *UnknownItemsError) Unwrap() error { return ErrUnknownItems }

// RecommendationRequest is the WBS §7 request body plus two demo controls.
type RecommendationRequest struct {
	UserID       string   `json:"user_id"`
	TopK         int      `json:"top_k"`
	ExcludeSeen  *bool    `json:"exclude_seen"`
	CandidateIDs []string `json:"candidate_ids"`
	// Model selects a manifest model for this request only; empty means the
	// server default. It never changes state shared with other clients.
	Model string `json:"model,omitempty"`
	// ForceColdStart demonstrates the cold-start path for a known user.
	ForceColdStart bool `json:"force_cold_start,omitempty"`
}

// Component is one term of the hybrid score: weight × normalized score.
type Component struct {
	NormalizedScore float64 `json:"normalized_score"`
	Weight          float64 `json:"weight"`
	Contribution    float64 `json:"contribution"`
}

// RecommendedItem is one ranked result (WBS §6).
type RecommendedItem struct {
	ItemID     string               `json:"item_id"`
	Rank       int                  `json:"rank"`
	Score      float64              `json:"score"`
	Source     string               `json:"source"`
	Video      *catalog.VideoItem   `json:"video,omitempty"`
	Components map[string]Component `json:"components,omitempty"`
	Reasons    []explanation.Reason `json:"reasons"`
}

// RecommendationResponse is the WBS §7 response plus provenance fields.
type RecommendationResponse struct {
	UserID          string                 `json:"user_id"`
	Model           string                 `json:"model"`
	TopK            int                    `json:"top_k"`
	Recommendations []RecommendedItem      `json:"recommendations"`
	Fallback        bool                   `json:"fallback"`
	FallbackReason  string                 `json:"fallback_reason,omitempty"`
	UserStatus      explanation.UserStatus `json:"user_status"`
	ArtifactSplit   string                 `json:"artifact_split"`
	ExcludeSeen     bool                   `json:"exclude_seen"`
	GeneratedAt     string                 `json:"generated_at"`
	LatencyMs       float64                `json:"latency_ms"`
}

// ModelMeta describes one registered model.
type ModelMeta struct {
	ID          string             `json:"id"`
	Name        string             `json:"name"`
	Type        string             `json:"type"`
	Description string             `json:"description"`
	IsFallback  bool               `json:"is_fallback"`
	Status      string             `json:"status"`
	Weights     map[string]float64 `json:"weights,omitempty"`
	Metrics     map[string]float64 `json:"metrics"`
}

// ModelManifest is the auditable serving manifest (WBS §2.2, §12).
type ModelManifest struct {
	ManifestVersion      string                    `json:"manifest_version"`
	GeneratedAt          string                    `json:"generated_at"`
	SourceGeneratedAt    string                    `json:"source_model_manifest_generated_at,omitempty"`
	DatasetRelease       map[string]any            `json:"dataset_release"`
	CurrentModel         string                    `json:"current_model"`
	FallbackModel        string                    `json:"fallback_model"`
	SelectedWeights      map[string]float64        `json:"selected_weights"`
	Models               []ModelMeta               `json:"models"`
	Serving              map[string]map[string]any `json:"serving"`
	ReasonCodeRules      []explanation.Rule        `json:"reason_code_rules"`
	SourceArtifactsSHA   map[string]string         `json:"source_artifacts_sha256,omitempty"`
	BundleSHA            map[string]string         `json:"bundle_sha256,omitempty"`
	ActiveDefaultModel   string                    `json:"active_default_model,omitempty"`
	BundleVerifiedAtLoad bool                      `json:"bundle_verified_at_load"`
}

// HistoryEvent is a recent positive interaction kept for demo users.
type HistoryEvent struct {
	ItemID     string  `json:"item_id"`
	Timestamp  float64 `json:"timestamp"`
	WatchRatio float64 `json:"watch_ratio"`
}

// UserProfile summarizes a user's pre-test history.
type UserProfile struct {
	SeenItems            int            `json:"seen_items"`
	PositiveHistoryItems int            `json:"positive_history_items"`
	RecentPositive       []HistoryEvent `json:"recent_positive,omitempty"`
	SeenItemIDs          []string       `json:"seen_item_ids,omitempty"`
	Demo                 bool           `json:"demo,omitempty"`
}

// PopularItem is one entry of the frozen fallback order.
type PopularItem struct {
	ItemID                     string `json:"item_id"`
	PositiveTrainingEventCount int    `json:"positive_training_event_count"`
}

// SimilarItem is an Item-CF neighbor.
type SimilarItem struct {
	ItemID string             `json:"item_id"`
	Score  float64            `json:"score"`
	Video  *catalog.VideoItem `json:"video,omitempty"`
}

// Engine serves the frozen bundle. All loaded data is read-only; only the
// default model ID is mutable and it is guarded by mu.
type Engine struct {
	catalog     *catalog.Repository
	manifest    ModelManifest
	rules       explanation.Rules
	models      map[string]ModelMeta
	selected    map[string][]RecommendedItem
	comparisons map[string]map[string][]RecommendedItem
	popularity  []PopularItem
	profiles    map[string]UserProfile
	seen        map[string]map[string]struct{}
	itemSims    map[string]map[string]float64

	mu           sync.RWMutex
	defaultModel string
}

// NewEngine loads and validates the serving bundle in dataDir.
func NewEngine(dataDir string, repo *catalog.Repository) (*Engine, error) {
	e := &Engine{catalog: repo}
	if err := readJSON(filepath.Join(dataDir, "model_manifest.json"), &e.manifest); err != nil {
		return nil, err
	}
	if err := verifyBundle(dataDir, e.manifest.BundleSHA); err != nil {
		return nil, err
	}
	e.manifest.BundleVerifiedAtLoad = len(e.manifest.BundleSHA) > 0
	rules, err := explanation.NewRules(e.manifest.ReasonCodeRules)
	if err != nil {
		return nil, err
	}
	e.rules = rules
	e.models = make(map[string]ModelMeta, len(e.manifest.Models))
	for _, m := range e.manifest.Models {
		e.models[m.ID] = m
	}
	if err := e.validateManifest(); err != nil {
		return nil, err
	}
	if err := readMaybeGzip(dataDir, "recommendations.json", &e.selected); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(dataDir, "comparisons.json"), &e.comparisons); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(dataDir, "popularity.json"), &e.popularity); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(dataDir, "user_profiles.json"), &e.profiles); err != nil {
		return nil, err
	}
	if err := readJSON(filepath.Join(dataDir, "item_similarity.json"), &e.itemSims); err != nil {
		return nil, err
	}
	if err := e.validateLists(); err != nil {
		return nil, err
	}
	e.seen = make(map[string]map[string]struct{})
	for userID, profile := range e.profiles {
		if len(profile.SeenItemIDs) == 0 {
			continue
		}
		set := make(map[string]struct{}, len(profile.SeenItemIDs))
		for _, id := range profile.SeenItemIDs {
			set[id] = struct{}{}
		}
		e.seen[userID] = set
	}
	e.defaultModel = e.manifest.CurrentModel
	return e, nil
}

func (e *Engine) validateManifest() error {
	m := e.manifest
	if _, ok := e.models[m.CurrentModel]; !ok {
		return fmt.Errorf("manifest current_model %q is not registered", m.CurrentModel)
	}
	if _, ok := e.models[m.FallbackModel]; !ok {
		return fmt.Errorf("manifest fallback_model %q is not registered", m.FallbackModel)
	}
	sum := 0.0
	for name, w := range m.SelectedWeights {
		if w < 0 || w > 1 {
			return fmt.Errorf("selected weight %s=%v outside [0,1]", name, w)
		}
		sum += w
	}
	if math.Abs(sum-1) > 1e-9 {
		return fmt.Errorf("selected weights sum to %v, want 1", sum)
	}
	return nil
}

// validateLists enforces WBS §13 "every explanation has machine-readable
// evidence" and checks every served item exists in the catalog.
func (e *Engine) validateLists() error {
	check := func(model, user string, items []RecommendedItem, requireEnabled bool) error {
		for _, item := range items {
			if !e.catalog.Has(item.ItemID) {
				return fmt.Errorf("%s/%s: item %s is not in the catalog", model, user, item.ItemID)
			}
			if len(item.Reasons) == 0 {
				return fmt.Errorf("%s/%s: item %s has no reason", model, user, item.ItemID)
			}
			for _, reason := range item.Reasons {
				if err := e.rules.Validate(reason, requireEnabled); err != nil {
					return fmt.Errorf("%s/%s/%s: %w", model, user, item.ItemID, err)
				}
			}
		}
		return nil
	}
	for user, items := range e.selected {
		if err := check(e.manifest.CurrentModel, user, items, true); err != nil {
			return err
		}
	}
	for model, byUser := range e.comparisons {
		if _, ok := e.models[model]; !ok {
			return fmt.Errorf("comparison export for unregistered model %q", model)
		}
		for user, items := range byUser {
			if err := check(model, user, items, e.models[model].Status != "rejected"); err != nil {
				return err
			}
		}
	}
	for _, p := range e.popularity {
		if !e.catalog.Has(p.ItemID) {
			return fmt.Errorf("popularity item %s is not in the catalog", p.ItemID)
		}
	}
	return nil
}

// Manifest returns the manifest with the current default model.
func (e *Engine) Manifest() ModelManifest {
	m := e.manifest
	m.ActiveDefaultModel = e.DefaultModel()
	return m
}

// DefaultModel returns the model used when a request names none.
func (e *Engine) DefaultModel() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.defaultModel
}

// SetDefaultModel changes the server-wide default (admin operation).
func (e *Engine) SetDefaultModel(modelID string) error {
	if _, ok := e.models[modelID]; !ok {
		return fmt.Errorf("%w: %s", ErrUnknownModel, modelID)
	}
	e.mu.Lock()
	e.defaultModel = modelID
	e.mu.Unlock()
	return nil
}

// HasModel reports whether modelID is registered in the manifest.
func (e *Engine) HasModel(modelID string) bool { _, ok := e.models[modelID]; return ok }

// UserCount returns the number of known users.
func (e *Engine) UserCount() int { return len(e.profiles) }

// Status classifies a user ID.
func (e *Engine) Status(userID string) (explanation.UserStatus, UserProfile) {
	profile, ok := e.profiles[userID]
	switch {
	case !ok:
		return explanation.UserUnknown, UserProfile{}
	case profile.PositiveHistoryItems == 0:
		return explanation.UserNoHistory, profile
	default:
		return explanation.UserKnown, profile
	}
}

// Recommend answers one request without mutating shared state.
func (e *Engine) Recommend(req RecommendationRequest) (*RecommendationResponse, error) {
	start := time.Now()
	if req.UserID == "" {
		return nil, ErrEmptyUserID
	}
	if req.TopK == 0 {
		req.TopK = 10
	}
	if req.TopK < 1 || req.TopK > MaxTopK {
		return nil, ErrInvalidTopK
	}
	model := req.Model
	if model == "" {
		model = e.DefaultModel()
	}
	if !e.HasModel(model) {
		return nil, fmt.Errorf("%w: %s", ErrUnknownModel, model)
	}
	candidates, err := e.candidateFilter(req.CandidateIDs)
	if err != nil {
		return nil, err
	}
	excludeSeen := req.ExcludeSeen == nil || *req.ExcludeSeen
	status, _ := e.Status(req.UserID)

	resp := &RecommendationResponse{UserID: req.UserID, UserStatus: status, ExcludeSeen: excludeSeen}
	switch {
	case req.ForceColdStart || status != explanation.UserKnown:
		resp.Fallback = true
		resp.Model = e.manifest.FallbackModel
		resp.ArtifactSplit = "train"
		switch {
		case req.ForceColdStart:
			resp.FallbackReason = "cold_start_requested"
		case status == explanation.UserUnknown:
			resp.FallbackReason = "unknown_user"
		default:
			resp.FallbackReason = "no_positive_history"
		}
		resp.Recommendations = e.fallback(req.UserID, status, req.ForceColdStart, excludeSeen, candidates, req.TopK)
	default:
		var stored []RecommendedItem
		if model == e.manifest.CurrentModel {
			stored, resp.ArtifactSplit = e.selected[req.UserID], "test"
		} else {
			stored, resp.ArtifactSplit = e.comparisons[model][req.UserID], "validation"
			if _, exported := e.comparisons[model][req.UserID]; !exported {
				return nil, fmt.Errorf("%w: model %s, user %s (comparison lists are exported for demo users)", ErrModelNotServable, model, req.UserID)
			}
		}
		resp.Model = model
		resp.Recommendations = e.filterStored(req.UserID, stored, excludeSeen, candidates, req.TopK)
	}
	resp.TopK = len(resp.Recommendations)
	resp.GeneratedAt = time.Now().UTC().Format(time.RFC3339)
	resp.LatencyMs = float64(time.Since(start).Microseconds()) / 1000
	return resp, nil
}

func (e *Engine) candidateFilter(ids []string) (map[string]struct{}, error) {
	if len(ids) == 0 {
		return nil, nil
	}
	filter := make(map[string]struct{}, len(ids))
	var unknown []string
	for _, id := range ids {
		if !e.catalog.Has(id) {
			unknown = append(unknown, id)
			continue
		}
		filter[id] = struct{}{}
	}
	if len(unknown) > 0 {
		if len(unknown) > 10 {
			unknown = unknown[:10]
		}
		return nil, &UnknownItemsError{IDs: unknown}
	}
	return filter, nil
}

func (e *Engine) keep(userID, itemID string, excludeSeen bool, candidates map[string]struct{}) bool {
	if candidates != nil {
		if _, ok := candidates[itemID]; !ok {
			return false
		}
	}
	if excludeSeen {
		if _, seen := e.seen[userID][itemID]; seen {
			return false
		}
	}
	return true
}

func (e *Engine) withVideo(item RecommendedItem) RecommendedItem {
	if video, ok := e.catalog.Get(item.ItemID); ok {
		item.Video = &video
	}
	return item
}

func (e *Engine) filterStored(userID string, stored []RecommendedItem, excludeSeen bool, candidates map[string]struct{}, topK int) []RecommendedItem {
	out := make([]RecommendedItem, 0, topK)
	for _, item := range stored {
		if !e.keep(userID, item.ItemID, excludeSeen, candidates) {
			continue
		}
		item = e.withVideo(item)
		item.Rank = len(out) + 1
		out = append(out, item)
		if len(out) == topK {
			break
		}
	}
	return out
}

func (e *Engine) fallback(userID string, status explanation.UserStatus, forced, excludeSeen bool, candidates map[string]struct{}, topK int) []RecommendedItem {
	out := make([]RecommendedItem, 0, topK)
	for _, p := range e.popularity {
		if !e.keep(userID, p.ItemID, excludeSeen, candidates) {
			continue
		}
		item := e.withVideo(RecommendedItem{
			ItemID: p.ItemID,
			Rank:   len(out) + 1,
			Score:  float64(p.PositiveTrainingEventCount),
			Source: e.manifest.FallbackModel,
			Reasons: []explanation.Reason{
				explanation.ColdStart(e.manifest.FallbackModel, p.PositiveTrainingEventCount, status, forced),
			},
		})
		out = append(out, item)
		if len(out) == topK {
			break
		}
	}
	return out
}

// CompareModel is one column of a comparison.
type CompareModel struct {
	Model           string            `json:"model"`
	Recommendations []RecommendedItem `json:"recommendations"`
	EmptyReason     string            `json:"empty_reason,omitempty"`
}

// CompareResult holds all manifest models for the same user and split.
type CompareResult struct {
	UserID        string                  `json:"user_id"`
	UserStatus    explanation.UserStatus  `json:"user_status"`
	TopK          int                     `json:"top_k"`
	ArtifactSplit string                  `json:"artifact_split"`
	Candidates    string                  `json:"candidates"`
	Models        map[string]CompareModel `json:"models"`
}

// Compare returns validation-time lists for every registered model for the
// same user and candidate protocol. It does not touch the default model.
func (e *Engine) Compare(userID string, topK int) (*CompareResult, error) {
	if topK < 1 || topK > MaxTopK {
		return nil, ErrInvalidTopK
	}
	if _, ok := e.comparisons[e.manifest.CurrentModel][userID]; !ok {
		return nil, fmt.Errorf("%w: %s", ErrNoComparisonExport, userID)
	}
	status, _ := e.Status(userID)
	result := &CompareResult{UserID: userID, UserStatus: status, TopK: topK, ArtifactSplit: "validation",
		Candidates: "full eligible catalog minus training-seen items", Models: map[string]CompareModel{}}
	for _, meta := range e.manifest.Models {
		items := e.filterStored(userID, e.comparisons[meta.ID][userID], false, nil, topK)
		column := CompareModel{Model: meta.ID, Recommendations: items}
		if len(items) == 0 {
			column.EmptyReason = "No supported ranking signal for this user (no positive training history)."
		}
		result.Models[meta.ID] = column
	}
	return result, nil
}

// DemoUser is an entry of the user selector.
type DemoUser struct {
	UserID               string                 `json:"user_id"`
	Status               explanation.UserStatus `json:"status"`
	PositiveHistoryItems int                    `json:"positive_history_items"`
	SeenItems            int                    `json:"seen_items"`
}

// DemoUsers returns the users with exported comparison lists, sorted by ID.
func (e *Engine) DemoUsers() []DemoUser {
	users := make([]DemoUser, 0, 100)
	for id, p := range e.profiles {
		if !p.Demo {
			continue
		}
		status, _ := e.Status(id)
		users = append(users, DemoUser{UserID: id, Status: status, PositiveHistoryItems: p.PositiveHistoryItems, SeenItems: p.SeenItems})
	}
	sort.Slice(users, func(i, j int) bool { return lessNumeric(users[i].UserID, users[j].UserID) })
	return users
}

// UserDetail describes a user for the UI history/evidence panel.
type UserDetail struct {
	UserID               string                 `json:"user_id"`
	Status               explanation.UserStatus `json:"status"`
	SeenItems            int                    `json:"seen_items"`
	PositiveHistoryItems int                    `json:"positive_history_items"`
	RecentPositive       []HistoryItem          `json:"recent_positive"`
	HasComparisonExport  bool                   `json:"has_comparison_export"`
}

// HistoryItem is a recent positive event with catalog metadata.
type HistoryItem struct {
	HistoryEvent
	Video *catalog.VideoItem `json:"video,omitempty"`
}

// User returns the profile of a known user.
func (e *Engine) User(userID string) (*UserDetail, bool) {
	status, profile := e.Status(userID)
	if status == explanation.UserUnknown {
		return nil, false
	}
	detail := &UserDetail{UserID: userID, Status: status, SeenItems: profile.SeenItems,
		PositiveHistoryItems: profile.PositiveHistoryItems, RecentPositive: []HistoryItem{}}
	_, detail.HasComparisonExport = e.comparisons[e.manifest.CurrentModel][userID]
	for _, event := range profile.RecentPositive {
		h := HistoryItem{HistoryEvent: event}
		if video, ok := e.catalog.Get(event.ItemID); ok {
			h.Video = &video
		}
		detail.RecentPositive = append(detail.RecentPositive, h)
	}
	return detail, true
}

// SimilarItems returns frozen Item-CF neighbors ordered by similarity.
func (e *Engine) SimilarItems(itemID string, limit int) []SimilarItem {
	neighbors := e.itemSims[itemID]
	items := make([]SimilarItem, 0, len(neighbors))
	for neighborID, score := range neighbors {
		if video, ok := e.catalog.Get(neighborID); ok {
			items = append(items, SimilarItem{ItemID: neighborID, Score: score, Video: &video})
		}
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].Score == items[j].Score {
			return lessNumeric(items[i].ItemID, items[j].ItemID)
		}
		return items[i].Score > items[j].Score
	})
	if len(items) > limit {
		items = items[:limit]
	}
	return items
}

func lessNumeric(a, b string) bool {
	if len(a) != len(b) {
		return len(a) < len(b)
	}
	return a < b
}

func readJSON(path string, target any) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read %s: %w", filepath.Base(path), err)
	}
	if err := json.Unmarshal(raw, target); err != nil {
		return fmt.Errorf("parse %s: %w", filepath.Base(path), err)
	}
	return nil
}

// readMaybeGzip prefers name+".gz" and falls back to the plain file.
func readMaybeGzip(dir, name string, target any) error {
	path := filepath.Join(dir, name+".gz")
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return readJSON(filepath.Join(dir, name), target)
	}
	if err != nil {
		return err
	}
	defer file.Close()
	reader, err := gzip.NewReader(file)
	if err != nil {
		return fmt.Errorf("open %s: %w", filepath.Base(path), err)
	}
	defer reader.Close()
	if err := json.NewDecoder(reader).Decode(target); err != nil {
		return fmt.Errorf("parse %s: %w", filepath.Base(path), err)
	}
	return nil
}

func verifyBundle(dir string, expected map[string]string) error {
	for name, want := range expected {
		file, err := os.Open(filepath.Join(dir, name))
		if err != nil {
			return fmt.Errorf("%w: %s: %v", errBundleChecksumFails, name, err)
		}
		digest := sha256.New()
		_, err = io.Copy(digest, file)
		file.Close()
		if err != nil {
			return err
		}
		if got := hex.EncodeToString(digest.Sum(nil)); got != want {
			return fmt.Errorf("%w: %s has %s, manifest expects %s", errBundleChecksumFails, name, got, want)
		}
	}
	return nil
}
