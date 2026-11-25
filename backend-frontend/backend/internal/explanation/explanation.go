// Package explanation defines the approved reason codes (WBS §6) and validates
// that every served reason carries the machine-readable evidence required by
// the reason-code rules frozen in the model manifest.
package explanation

import (
	"fmt"
	"sort"
)

// ReasonCode is one of the approved WBS §6 codes.
type ReasonCode string

// Approved reason codes.
const (
	CodeSimilarToRecent     ReasonCode = "similar_to_recent"
	CodePopularInTraining   ReasonCode = "popular_in_training"
	CodeLikedBySimilarUsers ReasonCode = "liked_by_similar_users"
	CodeExtensionModelMatch ReasonCode = "extension_model_match"
	CodeColdStart           ReasonCode = "cold_start"
)

// Reason is a single explanation with its evidence.
type Reason struct {
	Code     ReasonCode     `json:"code"`
	Text     string         `json:"text"`
	Evidence map[string]any `json:"evidence"`
}

// Rule mirrors one entry of model/reason_codes.json as exported in the manifest.
type Rule struct {
	Code             ReasonCode `json:"code"`
	Enabled          bool       `json:"enabled"`
	Description      string     `json:"description"`
	RequiredEvidence []string   `json:"required_evidence"`
}

// Rules indexes reason-code rules by code.
type Rules map[ReasonCode]Rule

// NewRules indexes rules and rejects codes outside the approved vocabulary.
func NewRules(list []Rule) (Rules, error) {
	approved := map[ReasonCode]bool{
		CodeSimilarToRecent: true, CodePopularInTraining: true, CodeLikedBySimilarUsers: true,
		CodeExtensionModelMatch: true, CodeColdStart: true,
	}
	rules := make(Rules, len(list))
	for _, rule := range list {
		if !approved[rule.Code] {
			return nil, fmt.Errorf("reason code %q is not in the approved WBS vocabulary", rule.Code)
		}
		rules[rule.Code] = rule
	}
	if _, ok := rules[CodeColdStart]; !ok {
		return nil, fmt.Errorf("manifest has no %q rule", CodeColdStart)
	}
	return rules, nil
}

// Validate checks that a reason is known and has every required evidence key.
// When requireEnabled is true the code must also be enabled for the selected
// model (disabled codes may appear only in experimental comparison lists).
func (r Rules) Validate(reason Reason, requireEnabled bool) error {
	rule, ok := r[reason.Code]
	if !ok {
		return fmt.Errorf("unknown reason code %q", reason.Code)
	}
	if requireEnabled && !rule.Enabled {
		return fmt.Errorf("reason code %q is disabled for the selected model", reason.Code)
	}
	if reason.Text == "" {
		return fmt.Errorf("reason %q has no text", reason.Code)
	}
	var missing []string
	for _, key := range rule.RequiredEvidence {
		if _, ok := reason.Evidence[key]; !ok {
			missing = append(missing, key)
		}
	}
	if len(missing) > 0 {
		sort.Strings(missing)
		return fmt.Errorf("reason %q is missing evidence %v", reason.Code, missing)
	}
	return nil
}

// UserStatus describes why a fallback was or was not used.
type UserStatus string

// User statuses reported by the API.
const (
	UserKnown     UserStatus = "known"
	UserNoHistory UserStatus = "no_positive_history"
	UserUnknown   UserStatus = "unknown"
)

// ColdStart builds the cold-start reason from the frozen popularity artifact.
// Evidence keys follow model/reason_codes.json.
func ColdStart(fallbackModelID string, positiveTrainingEvents int, status UserStatus, forced bool) Reason {
	text := "Popular in positive training interactions; shown because "
	switch {
	case forced:
		text += "the cold-start view was requested."
	case status == UserUnknown:
		text += "this user ID is not in the training data."
	default:
		text += "this user has no positive training history."
	}
	return Reason{
		Code: CodeColdStart,
		Text: text,
		Evidence: map[string]any{
			"fallback_model_id":             fallbackModelID,
			"positive_training_event_count": positiveTrainingEvents,
			"user_status":                   string(status),
			"forced":                        forced,
		},
	}
}
