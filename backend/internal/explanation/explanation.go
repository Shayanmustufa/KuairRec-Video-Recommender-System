package explanation

import "fmt"

type ReasonCode string

const (
	CodeSimilarToRecent       ReasonCode = "similar_to_recent"
	CodePopularInTraining     ReasonCode = "popular_in_training"
	CodeLikedBySimilarUsers   ReasonCode = "liked_by_similar_users"
	CodeExtensionModelMatch   ReasonCode = "extension_model_match"
	CodeColdStart             ReasonCode = "cold_start"
)

type Reason struct {
	Code     ReasonCode             `json:"code"`
	Text     string                 `json:"text"`
	Evidence map[string]interface{} `json:"evidence,omitempty"`
}

type Generator struct{}

func NewGenerator() *Generator {
	return &Generator{}
}

func (g *Generator) SimilarToRecent(sourceItemID string, similarity float64) Reason {
	return Reason{
		Code: CodeSimilarToRecent,
		Text: fmt.Sprintf("Similar to video %s from your recent history", sourceItemID),
		Evidence: map[string]interface{}{
			"item_id":    sourceItemID,
			"similarity": similarity,
		},
	}
}

func (g *Generator) PopularInTraining(popularityScore float64, totalViews int) Reason {
	return Reason{
		Code: CodePopularInTraining,
		Text: fmt.Sprintf("Popular among all viewers with %d completions", totalViews),
		Evidence: map[string]interface{}{
			"popularity_score": popularityScore,
			"total_views":      totalViews,
		},
	}
}

func (g *Generator) LikedBySimilarUsers(cfScore float64, overlapDegree float64) Reason {
	return Reason{
		Code: CodeLikedBySimilarUsers,
		Text: "Liked by users with interaction patterns similar to yours",
		Evidence: map[string]interface{}{
			"cf_score":       cfScore,
			"overlap_degree": overlapDegree,
		},
	}
}

func (g *Generator) ExtensionModelMatch(graphScore float64, layerHop int) Reason {
	return Reason{
		Code: CodeExtensionModelMatch,
		Text: "High bipartite graph community alignment in LightGCN embeddings",
		Evidence: map[string]interface{}{
			"graph_score": graphScore,
			"layer_hop":   layerHop,
		},
	}
}

func (g *Generator) ColdStart() Reason {
	return Reason{
		Code: CodeColdStart,
		Text: "Curated top-performing video for new viewers (cold-start baseline)",
		Evidence: map[string]interface{}{
			"reason": "insufficient_user_history",
		},
	}
}
