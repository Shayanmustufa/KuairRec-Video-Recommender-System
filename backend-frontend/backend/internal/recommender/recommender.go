package recommender

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/catalog"
	"github.com/Shayanmustufa/KuaiRec-Video-Recommender-System/backend/internal/explanation"
)

// RecommendationRequest is the input payload specified in Section 7
type RecommendationRequest struct {
	UserID       string   `json:"user_id"`
	TopK         int      `json:"top_k"`
	ExcludeSeen  bool     `json:"exclude_seen"`
	CandidateIDs []string `json:"candidate_ids,omitempty"`
}

// RecommendedItem represents a single ranked item with explainability
type RecommendedItem struct {
	ItemID   string               `json:"item_id"`
	Rank     int                  `json:"rank"`
	Score    float64              `json:"score"`
	Source   string               `json:"source"`
	Video    *catalog.VideoItem   `json:"video,omitempty"`
	Reasons  []explanation.Reason `json:"reasons"`
}

type SimilarItem struct {
	ItemID string             `json:"item_id"`
	Score  float64            `json:"score"`
	Video  *catalog.VideoItem `json:"video,omitempty"`
}

// RecommendationResponse is the output payload specified in Section 7
type RecommendationResponse struct {
	UserID          string            `json:"user_id"`
	Model           string            `json:"model"`
	TopK            int               `json:"top_k"`
	Recommendations []RecommendedItem `json:"recommendations"`
	Fallback        bool              `json:"fallback"`
	GeneratedAt     string            `json:"generated_at"`
	LatencyMs       float64           `json:"latency_ms,omitempty"`
}

// ModelManifest structures
type ModelManifest struct {
	ManifestVersion string         `json:"manifest_version"`
	GeneratedAt     string         `json:"generated_at"`
	DatasetRelease  map[string]any `json:"dataset_release"`
	CurrentModel    string         `json:"current_model"`
	Models          []ModelMeta    `json:"models"`
	ReasonCodeRules []any          `json:"reason_code_rules"`
}

type ModelMeta struct {
	ID          string         `json:"id"`
	Name        string         `json:"name"`
	Type        string         `json:"type"`
	Description string         `json:"description"`
	IsFallback  bool           `json:"is_fallback"`
	Weights     map[string]any `json:"weights,omitempty"`
	Metrics     map[string]any `json:"metrics"`
}

// InteractionRecord represents user history in KuaiRec
type InteractionRecord struct {
	ItemID     string  `json:"item_id"`
	Timestamp  string  `json:"timestamp"`
	WatchRatio float64 `json:"watch_ratio"`
	Liked      bool    `json:"liked"`
}

type Engine struct {
	mu           sync.RWMutex
	catRepo      *catalog.Repository
	explainer    *explanation.Generator
	userHistory  map[string][]InteractionRecord
	itemSims     map[string]map[string]float64
	manifest     ModelManifest
	activeModel  string
	precomputed  map[string][]RecommendedItem
	comparisons  map[string]map[string][]RecommendedItem
	popularity   []string
	hybridWeight struct {
		Alpha float64 // CF weight
		Beta  float64 // Graph weight
		Gamma float64 // Popularity weight
	}
}

func NewEngine(dataDir string, catRepo *catalog.Repository) (*Engine, error) {
	manifestPath := filepath.Join(dataDir, "model_manifest.json")
	mBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read model manifest %s: %w", manifestPath, err)
	}

	var manifest ModelManifest
	if err := json.Unmarshal(mBytes, &manifest); err != nil {
		return nil, fmt.Errorf("failed to parse model manifest: %w", err)
	}
	precomputed := make(map[string][]RecommendedItem)
	if bytes, err := os.ReadFile(filepath.Join(dataDir, "recommendations.json")); err != nil {
		return nil, fmt.Errorf("failed to read audited recommendations: %w", err)
	} else if err := json.Unmarshal(bytes, &precomputed); err != nil {
		return nil, fmt.Errorf("failed to parse audited recommendations: %w", err)
	}
	comparisons := make(map[string]map[string][]RecommendedItem)
	if bytes, err := os.ReadFile(filepath.Join(dataDir, "comparisons.json")); err == nil {
		if err := json.Unmarshal(bytes, &comparisons); err != nil { return nil, fmt.Errorf("failed to parse comparisons: %w", err) }
	}
	var popularity []string
	if bytes, err := os.ReadFile(filepath.Join(dataDir, "popularity.json")); err != nil {
		return nil, fmt.Errorf("failed to read popularity fallback: %w", err)
	} else if err := json.Unmarshal(bytes, &popularity); err != nil { return nil, fmt.Errorf("failed to parse popularity fallback: %w", err) }

	// Read user history
	userHistory := make(map[string][]InteractionRecord)
	histPath := filepath.Join(dataDir, "user_history.json")
	if hBytes, err := os.ReadFile(histPath); err == nil {
		_ = json.Unmarshal(hBytes, &userHistory)
	}

	// Read item similarities
	itemSims := make(map[string]map[string]float64)
	simPath := filepath.Join(dataDir, "item_similarity.json")
	if sBytes, err := os.ReadFile(simPath); err == nil {
		_ = json.Unmarshal(sBytes, &itemSims)
	}

	e := &Engine{
		catRepo:     catRepo,
		explainer:   explanation.NewGenerator(),
		userHistory: userHistory,
		itemSims:    itemSims,
		manifest:    manifest,
		activeModel: manifest.CurrentModel,
		precomputed: precomputed,
		comparisons: comparisons,
		popularity: popularity,
	}

	// Frozen validation-selected weights.
	e.hybridWeight.Alpha = 0.90
	e.hybridWeight.Beta = 0.0
	e.hybridWeight.Gamma = 0.10

	return e, nil
}

func (e *Engine) GetManifest() ModelManifest {
	e.mu.RLock()
	defer e.mu.RUnlock()
	m := e.manifest
	m.CurrentModel = e.activeModel
	return m
}

func (e *Engine) SetActiveModel(modelID string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	valid := false
	for _, m := range e.manifest.Models {
		if m.ID == modelID {
			valid = true
			break
		}
	}
	if !valid {
		return fmt.Errorf("unknown model id: %s", modelID)
	}

	e.activeModel = modelID
	return nil
}

func (e *Engine) GetActiveModel() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.activeModel
}

func (e *Engine) GetUserHistory(userID string) []InteractionRecord {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.userHistory[userID]
}

func (e *Engine) SimilarItems(itemID string, limit int) []SimilarItem {
	e.mu.RLock()
	neighbors := e.itemSims[itemID]
	e.mu.RUnlock()
	items := make([]SimilarItem, 0, len(neighbors))
	for neighborID, score := range neighbors {
		if video, ok := e.catRepo.Get(neighborID); ok {
			copy := video
			items = append(items, SimilarItem{ItemID: neighborID, Score: score, Video: &copy})
		}
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].Score == items[j].Score { return items[i].ItemID < items[j].ItemID }
		return items[i].Score > items[j].Score
	})
	if limit <= 0 { limit = 5 }
	if limit > 20 { limit = 20 }
	if len(items) > limit { items = items[:limit] }
	return items
}

func (e *Engine) ListDemoUsers() []map[string]any {
	e.mu.RLock()
	defer e.mu.RUnlock()

	var users []map[string]any
	// The model comparison export covers a curated subset. Offer those users
	// in the UI so every switch has predictions from the selected model.
	usersWithComparisons := e.comparisons["hybrid-validation-selected-v1"]
	if len(usersWithComparisons) == 0 {
		usersWithComparisons = make(map[string][]RecommendedItem, len(e.precomputed))
		for uID := range e.precomputed {
			usersWithComparisons[uID] = nil
		}
	}
	for uID := range usersWithComparisons {
		history := e.userHistory[uID]
		users = append(users, map[string]any{
			"user_id":          uID,
			"interaction_count": len(history),
			"is_cold_start":    false,
			"history_available": len(history) > 0,
		})
	}
	sort.Slice(users, func(i, j int) bool {
		return users[i]["user_id"].(string) < users[j]["user_id"].(string)
	})
	if len(users) > 100 { users = users[:100] }
	return users
}

// Recommend computes top-K recommendations adhering to Section 5, 6, and 7
func (e *Engine) Recommend(req RecommendationRequest) (*RecommendationResponse, error) {
	e.mu.RLock()
	modelID := e.activeModel
	e.mu.RUnlock()
	return e.recommendForModel(req, modelID)
}

func (e *Engine) recommendForModel(req RecommendationRequest, activeModel string) (*RecommendationResponse, error) {
	start := time.Now()
	if req.UserID == "" {
		return nil, errors.New("user_id is required")
	}

	topK := req.TopK
	if topK <= 0 {
		topK = 10
	}
	if topK > 50 {
		topK = 50
	}

	e.mu.RLock()
	history := e.userHistory[req.UserID]
	itemSims := e.itemSims
	precomputed := e.precomputed[req.UserID]
	comparison := e.comparisons[activeModel][req.UserID]
	e.mu.RUnlock()

	seen := make(map[string]struct{}, len(history))
	if req.ExcludeSeen {
		for _, record := range history { seen[record.ItemID] = struct{}{} }
	}

	// Serve Syed's exact saved predictions. Baseline/experimental switches use
	// validation comparison outputs for the curated demo users only.
	stored := precomputed
	if activeModel != "hybrid-validation-selected-v1" { stored = comparison }
	if len(stored) > 0 {
		candidate := make(map[string]bool)
		for _, id := range req.CandidateIDs { candidate[id] = true }
		out := make([]RecommendedItem, 0, topK)
		for _, item := range stored {
			if _, alreadySeen := seen[item.ItemID]; alreadySeen { continue }
			if len(candidate) > 0 && !candidate[item.ItemID] { continue }
			if video, ok := e.catRepo.Get(item.ItemID); ok { copy := video; item.Video = &copy }
			item.Rank = len(out)+1; out = append(out,item)
			if len(out) == topK { break }
		}
		return &RecommendationResponse{UserID:req.UserID,Model:activeModel,TopK:len(out),Recommendations:out,Fallback:false,GeneratedAt:time.Now().UTC().Format(time.RFC3339),LatencyMs:float64(time.Since(start).Microseconds())/1000},nil
	}

	allVideos := e.catRepo.ListAll()
	if len(allVideos) == 0 {
		return nil, errors.New("catalog is empty")
	}

	// Candidate pool
	candidateFilter := make(map[string]bool)
	if len(req.CandidateIDs) > 0 {
		for _, cid := range req.CandidateIDs {
			candidateFilter[cid] = true
		}
	}

	var candidates []catalog.VideoItem
	for _, v := range allVideos {
		if _, alreadySeen := seen[v.ItemID]; alreadySeen {
			continue
		}
		if len(candidateFilter) > 0 && !candidateFilter[v.ItemID] {
			continue
		}
		candidates = append(candidates, v)
	}


	// Unknown users use the frozen training-only popularity order.
	isColdStart := len(history) == 0

	var ranked []RecommendedItem
	modelToUse := activeModel

	if isColdStart {
		byID := make(map[string]catalog.VideoItem,len(candidates)); for _, v := range candidates { byID[v.ItemID]=v }
		for _, id := range e.popularity { if v,ok:=byID[id]; ok { ranked=append(ranked,RecommendedItem{ItemID:id,Score:float64(v.TotalViews),Source:"popularity-fallback",Reasons:[]explanation.Reason{e.explainer.ColdStart()}}) } }
		modelToUse = "popularity-positive-event-count-v1"
		for i := range ranked {
			ranked[i].Source = "popularity-fallback"
			ranked[i].Reasons = []explanation.Reason{e.explainer.ColdStart()}
		}
	} else {
		switch activeModel {
		case "popularity-positive-event-count-v1":
			ranked = e.scorePopularity(candidates)
		case "item-cf-cosine-v1":
			ranked = e.scoreItemCF(candidates, history, itemSims)
		case "lightgcn-validation-selected-v1":
			ranked = e.scoreLightGCN(candidates, history)
		case "hybrid-validation-selected-v1":
			fallthrough
		default:
			ranked = e.scoreHybrid(candidates, history, itemSims)
			modelToUse = "hybrid-validation-selected-v1"
		}
	}

	// Sort descending by score
	sort.Slice(ranked, func(i, j int) bool {
		return ranked[i].Score > ranked[j].Score
	})

	// Truncate to top-K and assign ranks
	if len(ranked) > topK {
		ranked = ranked[:topK]
	}
	for i := range ranked {
		ranked[i].Rank = i + 1
		// Enrich with video metadata
		if v, ok := e.catRepo.Get(ranked[i].ItemID); ok {
			vCopy := v
			ranked[i].Video = &vCopy
		}
	}

	duration := time.Since(start)

	return &RecommendationResponse{
		UserID:          req.UserID,
		Model:           modelToUse,
		TopK:            len(ranked),
		Recommendations: ranked,
		Fallback:        isColdStart,
		GeneratedAt:     time.Now().UTC().Format(time.RFC3339),
		LatencyMs:       float64(duration.Microseconds()) / 1000.0,
	}, nil
}

// Popularity baseline: score(v) = log10(views) * (watch_ratio_avg)
func (e *Engine) scorePopularity(candidates []catalog.VideoItem) []RecommendedItem {
	var maxScore float64 = 0.0001
	type scored struct {
		item  catalog.VideoItem
		score float64
	}
	raw := make([]scored, len(candidates))

	for i, c := range candidates {
		views := float64(c.TotalViews)
		if views < 1 {
			views = 1
		}
		s := math.Log10(views) * c.WatchRatioAvg
		raw[i] = scored{item: c, score: s}
		if s > maxScore {
			maxScore = s
		}
	}

	res := make([]RecommendedItem, len(candidates))
	for i, r := range raw {
		normScore := math.Round((r.score/maxScore)*1000) / 1000
		res[i] = RecommendedItem{
			ItemID: r.item.ItemID,
			Score:  normScore,
			Source: "popularity",
			Reasons: []explanation.Reason{
				e.explainer.PopularInTraining(normScore, r.item.TotalViews),
			},
		}
	}
	return res
}

// Item-CF: score(u,v) = sum(sim(v,h)*pref(u,h)) / sum(abs(sim(v,h)))
func (e *Engine) scoreItemCF(candidates []catalog.VideoItem, history []InteractionRecord, itemSims map[string]map[string]float64) []RecommendedItem {
	res := make([]RecommendedItem, len(candidates))

	for i, c := range candidates {
		var simSum, weightSum float64
		var bestSourceItem string
		var bestSim float64

		for _, h := range history {
			sim := 0.0
			if sMap, ok := itemSims[c.ItemID]; ok {
				sim = sMap[h.ItemID]
			}
			if sim == 0 {
				if sMap, ok := itemSims[h.ItemID]; ok {
					sim = sMap[c.ItemID]
				}
			}

			if sim > 0 {
				weight := h.WatchRatio
				if weight <= 0 {
					weight = 1.0
				}
				simSum += sim * weight
				weightSum += sim

				if sim > bestSim {
					bestSim = sim
					bestSourceItem = h.ItemID
				}
			}
		}

		score := 0.0
		if weightSum > 0 {
			score = simSum / weightSum
		} else {
			// tiny baseline for unlinked items
			score = 0.05
		}

		score = math.Min(1.0, math.Round(score*1000)/1000)

		var reasons []explanation.Reason
		if bestSim >= 0.40 && bestSourceItem != "" {
			reasons = append(reasons, e.explainer.SimilarToRecent(bestSourceItem, bestSim))
		} else {
			reasons = append(reasons, e.explainer.LikedBySimilarUsers(score, 0.65))
		}

		res[i] = RecommendedItem{
			ItemID:  c.ItemID,
			Score:   score,
			Source:  "item_cf",
			Reasons: reasons,
		}
	}
	return res
}

// LightGCN graph bipartite score simulation
func (e *Engine) scoreLightGCN(candidates []catalog.VideoItem, history []InteractionRecord) []RecommendedItem {
	historyCats := make(map[string]int)
	for _, h := range history {
		if v, ok := e.catRepo.Get(h.ItemID); ok {
			historyCats[v.Category]++
		}
	}

	res := make([]RecommendedItem, len(candidates))
	for i, c := range candidates {
		catAffinity := float64(historyCats[c.Category]) / float64(len(history)+1)
		viewsFactor := math.Min(1.0, float64(c.TotalViews)/400000.0)

		graphScore := 0.60*catAffinity + 0.40*viewsFactor
		graphScore = math.Min(0.98, math.Max(0.10, math.Round(graphScore*1000)/1000))

		res[i] = RecommendedItem{
			ItemID: c.ItemID,
			Score:  graphScore,
			Source: "lightgcn",
			Reasons: []explanation.Reason{
				e.explainer.ExtensionModelMatch(graphScore, 2),
			},
		}
	}
	return res
}

// Hybrid Ranker combining CF, LightGCN, and Popularity
func (e *Engine) scoreHybrid(candidates []catalog.VideoItem, history []InteractionRecord, itemSims map[string]map[string]float64) []RecommendedItem {
	cfScores := e.scoreItemCF(candidates, history, itemSims)
	graphScores := e.scoreLightGCN(candidates, history)
	popScores := e.scorePopularity(candidates)

	cfMap := make(map[string]RecommendedItem)
	for _, item := range cfScores {
		cfMap[item.ItemID] = item
	}

	graphMap := make(map[string]RecommendedItem)
	for _, item := range graphScores {
		graphMap[item.ItemID] = item
	}

	popMap := make(map[string]RecommendedItem)
	for _, item := range popScores {
		popMap[item.ItemID] = item
	}

	alpha := e.hybridWeight.Alpha
	beta := e.hybridWeight.Beta
	gamma := e.hybridWeight.Gamma

	res := make([]RecommendedItem, len(candidates))
	for i, c := range candidates {
		sCF := cfMap[c.ItemID].Score
		sGraph := graphMap[c.ItemID].Score
		sPop := popMap[c.ItemID].Score

		hybridScore := (alpha * sCF) + (beta * sGraph) + (gamma * sPop)
		hybridScore = math.Round(hybridScore*1000) / 1000

		// Composite reasons: prioritize CF similar_to_recent, add secondary graph signal
		var reasons []explanation.Reason
		if len(cfMap[c.ItemID].Reasons) > 0 {
			reasons = append(reasons, cfMap[c.ItemID].Reasons[0])
		}
		if sPop > 0.80 {
			reasons = append(reasons, e.explainer.PopularInTraining(sPop, c.TotalViews))
		} else if sGraph > 0.70 {
			reasons = append(reasons, e.explainer.ExtensionModelMatch(sGraph, 2))
		}

		res[i] = RecommendedItem{
			ItemID:  c.ItemID,
			Score:   hybridScore,
			Source:  "hybrid",
			Reasons: reasons,
		}
	}
	return res
}

// Compare returns recommendations for all 4 models simultaneously for the given user
func (e *Engine) Compare(userID string, topK int) (map[string]*RecommendationResponse, error) {
	if topK <= 0 {
		topK = 5
	}

	models := []string{"popularity-positive-event-count-v1", "item-cf-cosine-v1", "lightgcn-validation-selected-v1", "hybrid-validation-selected-v1"}
	results := make(map[string]*RecommendationResponse)

	for _, m := range models {
		resp, err := e.recommendForModel(RecommendationRequest{
			UserID:      userID,
			TopK:        topK,
			ExcludeSeen: true,
		}, m)
		if err != nil {
			return nil, err
		}
		results[m] = resp
	}

	return results, nil
}
