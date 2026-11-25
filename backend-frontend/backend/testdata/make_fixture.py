"""Write the small synthetic serving bundle used by Go unit tests.

Synthetic, test-only data: IDs and numbers do not come from KuaiRec. Run from
this directory: ``python make_fixture.py``.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HYBRID, POP, CF, LGCN = ("hybrid-validation-selected-v1", "popularity-positive-event-count-v1",
                         "item-cf-cosine-v1", "lightgcn-validation-selected-v1")


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def cf(source, sim, weight=0.9):
    return {"code": "liked_by_similar_users", "text": "Recommended from collaborative patterns linked to your positive history.",
            "evidence": {"source_video_id": source, "similarity": sim, "preference_strength": 1.5,
                         "contribution": round(sim * 1.5, 6), "item_cf_weight": weight}}


def pop(count, weight=0.1):
    return {"code": "popular_in_training", "text": "Popular in positive training interactions.",
            "evidence": {"positive_training_event_count": count, "popularity_weight": weight}}


counts = {"1": 50, "2": 40, "3": 30, "4": 20, "5": 10, "6": 5, "7": 2, "8": 1}
write("catalog.json", [
    {"item_id": i, "title": f"Synthetic video {i}" if i != "8" else "", "has_caption": i != "8",
     "category": "Test", "categories": ["Test"], "tags": [], "author_id": "a1", "upload_date": "2020-01-01",
     "video_type": "NORMAL", "duration_seconds": 10.0, "positive_training_events": c}
    for i, c in counts.items()])
write("popularity.json", [{"item_id": i, "positive_training_event_count": c} for i, c in counts.items()])


def hybrid_item(item, rank, score):
    return {"item_id": item, "rank": rank, "score": score, "source": HYBRID,
            "components": {"item_cf": {"normalized_score": 1.0, "weight": 0.9, "contribution": 0.9},
                           "lightgcn": {"normalized_score": 0.5, "weight": 0.0, "contribution": 0.0},
                           "popularity": {"normalized_score": 0.2, "weight": 0.1, "contribution": 0.02}},
            "reasons": [cf("5", 0.4), pop(counts[item])]}


write("recommendations.json", {
    "1": [hybrid_item("3", 1, 0.92), hybrid_item("1", 2, 0.81), hybrid_item("4", 3, 0.70), hybrid_item("2", 4, 0.50)],
    "2": [{"item_id": "1", "rank": 1, "score": 0.1, "source": HYBRID, "reasons": [pop(50)]}],
    "3": [hybrid_item("2", 1, 0.66)],
})
write("comparisons.json", {
    POP: {"1": [{"item_id": i, "rank": r, "score": counts[i], "source": POP,
                 "reasons": [{"code": "popular_in_training", "text": "Popular in positive training interactions.",
                              "evidence": {"positive_training_event_count": counts[i], "popularity_weight": 1.0}}]}
                for r, i in enumerate(["1", "2", "3"], 1)], "2": []},
    CF: {"1": [{"item_id": "4", "rank": 1, "score": 1.4, "source": CF, "reasons": [cf("5", 0.5, 1.0)]}], "2": []},
    LGCN: {"1": [{"item_id": "6", "rank": 1, "score": 0.03, "source": LGCN,
                  "reasons": [{"code": "extension_model_match", "text": "Ranked by the LightGCN embedding dot-product score.",
                               "evidence": {"lightgcn_score": 0.03, "lightgcn_weight": 0.0}}]}], "2": []},
    HYBRID: {"1": [hybrid_item("3", 1, 0.9)], "2": [{"item_id": "1", "rank": 1, "score": 0.1, "source": HYBRID, "reasons": [pop(50)]}]},
})
write("user_profiles.json", {
    "1": {"seen_items": 2, "positive_history_items": 1, "demo": True, "seen_item_ids": ["5", "7"],
          "recent_positive": [{"item_id": "5", "timestamp": 1593878903.4, "watch_ratio": 2.5}]},
    "2": {"seen_items": 1, "positive_history_items": 0, "demo": True, "seen_item_ids": ["1"], "recent_positive": []},
    "3": {"seen_items": 4, "positive_history_items": 3},
})
write("item_similarity.json", {"1": {"2": 0.2, "3": 0.9, "4": 0.5}, "3": {"1": 0.9}})
weights = {"popularity": 0.1, "item_cf": 0.9, "lightgcn": 0.0}
rules = [
    {"code": "liked_by_similar_users", "enabled": True, "description": "CF",
     "required_evidence": ["source_video_id", "similarity", "preference_strength", "contribution", "item_cf_weight"]},
    {"code": "popular_in_training", "enabled": True, "description": "pop",
     "required_evidence": ["positive_training_event_count", "popularity_weight"]},
    {"code": "extension_model_match", "enabled": False, "description": "lgcn", "required_evidence": ["lightgcn_score", "lightgcn_weight"]},
    {"code": "similar_to_recent", "enabled": False, "description": "recent", "required_evidence": ["source_video_id", "source_timestamp", "similarity"]},
    {"code": "cold_start", "enabled": True, "description": "fallback", "required_evidence": ["fallback_model_id", "positive_training_event_count"]},
]
metric = {"recall_at_10": 0.01, "recall_at_20": 0.02, "ndcg_at_10": 0.01, "ndcg_at_20": 0.02, "hit_rate_at_10": 0.1,
          "hit_rate_at_20": 0.2, "precision_at_10": 0.01, "precision_at_20": 0.01, "catalog_coverage": 0.5}
models = [
    {"id": POP, "name": "Popularity baseline", "type": "baseline", "description": "test", "is_fallback": True, "status": "baseline", "metrics": metric},
    {"id": CF, "name": "Item-CF", "type": "collaborative", "description": "test", "is_fallback": False, "status": "baseline", "metrics": metric},
    {"id": LGCN, "name": "LightGCN (rejected experiment)", "type": "experimental", "description": "test", "is_fallback": False, "status": "rejected", "metrics": metric},
    {"id": HYBRID, "name": "Selected hybrid", "type": "hybrid", "description": "test", "is_fallback": False, "status": "selected",
     "weights": {"alpha_cf": 0.9, "beta_extension": 0.0, "gamma_popularity": 0.1}, "metrics": metric},
]
write("model_manifest.json", {
    "manifest_version": "2.0", "generated_at": "2026-01-01T00:00:00+00:00",
    "dataset_release": {"name": "synthetic test fixture"}, "current_model": HYBRID, "fallback_model": POP,
    "selected_weights": weights, "models": models,
    "serving": {"recommendations": {"split": "test"}, "comparisons": {"split": "validation"}},
    "reason_code_rules": rules,
})
write("metrics_summary.json", {"evaluation_protocol": {"dataset": "synthetic"}, "validation_metrics": models,
                               "overall_metrics": models, "controlled_test": {"model_id": HYBRID, **metric}})
print("fixture written")
