"""Build the Go serving bundle from Syed's frozen, audited artifacts.

Every value written here is copied or deterministically derived from the frozen
offline artifacts; nothing is invented for display:

* ``catalog.json``           official KuaiRec metadata for the 8,418 eligible items
                             (caption/category/topic tags + first daily-feature row).
* ``recommendations.json.gz`` the selected hybrid's frozen controlled-test top-20 list
                             per user, with normalized component scores and reason
                             evidence produced by Syed's ``build_reasons`` rule using
                             the same train+validation history used for test ranking.
* ``comparisons.json``       validation-time top-20 lists for all four manifest models
                             for a deterministic, stratified set of demo users, each
                             item carrying model-specific evidence.
* ``popularity.json``        frozen training-only popularity order (cold-start fallback).
* ``user_profiles.json``     per-user history counts, so the API can distinguish known,
                             no-positive-history and unknown users.
* ``model_manifest.json``    model registry, selected weights, reason-code rules and
                             SHA-256 checksums of every source and bundle file.
* ``metrics_summary.json``   validation comparison + single controlled-test result.

Run from anywhere::

    python backend-frontend/scripts/generate_serving_bundle.py --repo-root <project root>
"""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from scipy import sparse

DEMO_USER_COUNT = 100
RECENT_POSITIVES = 5
SELECTED_MODEL = "hybrid-validation-selected-v1"
MODEL_IDS = {
    "popularity": "popularity-positive-event-count-v1",
    "item_cf": "item-cf-cosine-v1",
    "lightgcn": "lightgcn-validation-selected-v1",
    "hybrid": SELECTED_MODEL,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def metric_row(row: dict) -> dict:
    m = row["metrics"]
    coverage = row.get("catalog_coverage@20", row.get("catalog_coverage_at_20", row.get("catalog_coverage_at_max_k")))
    if coverage is None:
        raise KeyError("catalog coverage missing from metrics artifact")
    return {
        "recall_at_10": m["recall@10"], "recall_at_20": m["recall@20"],
        "ndcg_at_10": m["ndcg@10"], "ndcg_at_20": m["ndcg@20"],
        "hit_rate_at_10": m["hit_rate@10"], "hit_rate_at_20": m["hit_rate@20"],
        "precision_at_10": m["precision@10"], "precision_at_20": m["precision@20"],
        "catalog_coverage": coverage,
    }


def convert_reason(reason: dict) -> dict:
    """Syed's evidence uses ``display_text``; the API contract (WBS §6) uses ``text``."""
    evidence = dict(reason["evidence"])
    for key in ("source_video_id",):
        if key in evidence:
            evidence[key] = str(evidence[key])
    return {"code": reason["code"], "text": reason["display_text"], "evidence": evidence}


def build_catalog(data_dir: Path, raw_dir: Path, pop_counts: dict[str, int]) -> list[dict]:
    caption = pd.read_csv(raw_dir / "kuairec_caption_category.csv", dtype=str, keep_default_na=False,
                          engine="python", on_bad_lines="skip")
    caption = caption.drop_duplicates("video_id").set_index("video_id")
    daily = pd.read_csv(raw_dir / "item_daily_features.csv",
                        usecols=["video_id", "date", "author_id", "video_type", "upload_dt", "video_duration", "video_tag_name"],
                        dtype={"video_id": str, "author_id": str})
    daily = daily.sort_values(["video_id", "date"]).drop_duplicates("video_id").set_index("video_id")

    def clean(value: object) -> str:
        text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()
        return "" if text in {"UNKNOWN", "nan", "-124"} else text

    catalog = []
    ids = pd.read_csv(data_dir / "candidate_catalog.csv", dtype=str)["video_id"].tolist()
    for item in ids:
        meta = caption.loc[item] if item in caption.index else None
        feat = daily.loc[item] if item in daily.index else None
        title = clean(meta["caption"]) or clean(meta["manual_cover_text"]) if meta is not None else ""
        categories = [clean(meta[f"{lvl}_level_category_name"]) for lvl in ("first", "second", "third")] if meta is not None else []
        categories = [c for c in categories if c]
        tags: list[str] = []
        if meta is not None and clean(meta["topic_tag"]):
            try:
                tags = [str(t) for t in ast.literal_eval(meta["topic_tag"]) if str(t).strip()]
            except (ValueError, SyntaxError):
                tags = []
        duration_ms = None
        if feat is not None and not pd.isna(feat["video_duration"]):
            duration_ms = float(feat["video_duration"])
        catalog.append({
            "item_id": item,
            "title": title[:160],
            "has_caption": bool(title),
            "category": categories[0] if categories else "",
            "categories": categories,
            "tags": tags[:10],
            "author_id": clean(feat["author_id"]) if feat is not None else "",
            "upload_date": clean(feat["upload_dt"]) if feat is not None else "",
            "video_type": clean(feat["video_type"]) if feat is not None else "",
            "duration_seconds": round(duration_ms / 1000, 1) if duration_ms else None,
            "positive_training_events": pop_counts.get(item, 0),
        })
    return catalog


def read_history(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, usecols=["user_id", "video_id", "timestamp", "watch_ratio", "is_relevant"],
                       dtype={"user_id": "int32", "video_id": "int32", "is_relevant": "int8"})


def build_profiles(history: pd.DataFrame, detailed_users: set[int]) -> dict[str, dict]:
    seen_counts = history.groupby("user_id")["video_id"].nunique()
    positive = history[history["is_relevant"] == 1]
    positive_counts = positive.groupby("user_id")["video_id"].nunique()
    profiles: dict[str, dict] = {}
    for user, seen in seen_counts.items():
        profiles[str(user)] = {
            "seen_items": int(seen),
            "positive_history_items": int(positive_counts.get(user, 0)),
        }
    detail = history[history["user_id"].isin(detailed_users)]
    for user, rows in detail.groupby("user_id"):
        pos = rows[rows["is_relevant"] == 1].sort_values(["timestamp", "video_id"], ascending=[False, True])
        pos = pos.drop_duplicates("video_id").head(RECENT_POSITIVES)
        profiles[str(user)]["recent_positive"] = [
            {"item_id": str(r.video_id), "timestamp": float(r.timestamp), "watch_ratio": round(float(r.watch_ratio), 4)}
            for r in pos.itertuples()
        ]
        profiles[str(user)]["seen_item_ids"] = sorted({str(v) for v in rows["video_id"].tolist()}, key=int)
    return profiles


def preference_maps(read_training, path: Path, item_to_index: dict[int, int]) -> tuple[list[int], sparse.csr_matrix]:
    users, _seen, preferences = read_training(path, item_to_index)
    return users, preferences


def user_preferences(users: list[int], preferences: sparse.csr_matrix) -> dict[int, dict[int, float]]:
    out = {}
    for index, user in enumerate(users):
        start, end = preferences.indptr[index:index + 2]
        out[user] = {int(i): float(v) for i, v in zip(preferences.indices[start:end], preferences.data[start:end])}
    return out


def main() -> int:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", type=Path, default=default_root,
                        help="project root containing model/ and data/ (default: %(default)s)")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "backend" / "serving_data")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    art, data, raw, out = root / "model" / "artifacts", root / "data" / "processed", root / "data" / "raw" / "KuaiRec", args.output_dir.resolve()
    if not (art / "test_time_manifest.json").exists():
        parser.error(f"{art} does not contain Syed's frozen artifacts; pass --repo-root")
    sys.path.insert(0, str(root))
    from model.src.freeze_day9 import build_reasons  # noqa: E402  (Syed's evidence rule)
    from model.src.item_cf import _read_training  # noqa: E402

    load = lambda name: json.loads((art / name).read_text(encoding="utf-8"))  # noqa: E731
    freeze = load("test_time_manifest.json")
    for name, expected in freeze["frozen_artifacts_sha256"].items():
        if sha256(art / name) != expected:
            raise ValueError(f"Frozen artifact changed since Day 9 freeze: {name}")
    model_manifest, hybrid_config = load("model_manifest.json"), load("hybrid_config.json")
    weights = hybrid_config["selected_weights"]
    reason_config = json.loads((root / "model" / "reason_codes.json").read_text(encoding="utf-8"))
    test_metrics = load("controlled_test_metrics.json")

    pop_model = load("popularity_model.json")
    pop_order = [str(x["video_id"]) for x in pop_model["items"]]
    pop_counts = {str(x["video_id"]): int(x["score"]) for x in pop_model["items"]}

    mapping = load("item_cf_mapping.json")
    catalog_ids: list[int] = mapping["items"]
    item_to_index = {item: i for i, item in enumerate(catalog_ids)}
    similarity = sparse.load_npz(art / "item_cf_model.npz").tocsc()

    out.mkdir(parents=True, exist_ok=True)
    print("catalog ...", flush=True)
    catalog = build_catalog(data, raw, pop_counts)
    (out / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("test-time history ...", flush=True)
    test_users, test_prefs_matrix = preference_maps(_read_training, data / "user_history_test.csv", item_to_index)
    test_prefs = user_preferences(test_users, test_prefs_matrix)

    # Stratified, deterministic demo users: evenly spaced over positive-history size,
    # plus every user without positive pre-test history (the WBS "no-history" state).
    ordered = sorted(test_users, key=lambda u: (len(test_prefs[u]), u))
    no_history = [u for u in ordered if not test_prefs[u]]
    with_history = [u for u in ordered if test_prefs[u]]
    step = len(with_history) / (DEMO_USER_COUNT - len(no_history))
    demo_users = sorted(set(no_history) | {with_history[int(i * step)] for i in range(DEMO_USER_COUNT - len(no_history))})

    print("profiles ...", flush=True)
    history = read_history(data / "user_history_test.csv")
    profiles = build_profiles(history, set(demo_users))
    del history
    for user in demo_users:
        profiles[str(user)]["demo"] = True
    (out / "user_profiles.json").write_text(json.dumps(profiles, separators=(",", ":")), encoding="utf-8")

    print("test-time recommendations + evidence ...", flush=True)
    predictions = pd.read_csv(art / "controlled_test_predictions.csv")
    recommendations: dict[str, list[dict]] = {}
    unsupported = 0
    for row in predictions.itertuples(index=False):
        user, video = int(row.user_id), int(row.video_id)
        reasons = build_reasons(test_prefs[user], item_to_index[video], similarity, catalog_ids, pop_counts[str(video)], weights)
        unsupported += not reasons
        components = {
            "item_cf": {"normalized_score": float(row.item_cf_score), "weight": weights["item_cf"]},
            "lightgcn": {"normalized_score": float(row.lightgcn_score), "weight": weights["lightgcn"]},
            "popularity": {"normalized_score": float(row.popularity_score), "weight": weights["popularity"]},
        }
        for part in components.values():
            part["contribution"] = round(part["normalized_score"] * part["weight"], 9)
        recommendations.setdefault(str(user), []).append({
            "item_id": str(video), "rank": int(row.rank), "score": float(row.hybrid_score),
            "source": SELECTED_MODEL, "components": components,
            "reasons": [convert_reason(r) for r in reasons],
        })
    if unsupported:
        raise ValueError(f"{unsupported} test-time recommendations have no supported reason")
    with gzip.open(out / "recommendations.json.gz", "wt", encoding="utf-8", compresslevel=9) as target:
        json.dump(recommendations, target, separators=(",", ":"))
    stale = out / "recommendations.json"
    if stale.exists():
        stale.unlink()

    print("comparisons ...", flush=True)
    train_users, train_prefs_matrix = preference_maps(_read_training, data / "train.csv", item_to_index)
    train_prefs = user_preferences(train_users, train_prefs_matrix)
    demo_set = set(demo_users)
    hybrid_evidence: dict[tuple[int, int], list[dict]] = {}
    with (art / "explanation_evidence.jsonl").open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            if record["user_id"] in demo_set:
                hybrid_evidence[(record["user_id"], record["video_id"])] = record["reasons"]
    files = {"popularity": "popularity_validation_predictions.csv", "item_cf": "item_cf_validation_predictions.csv",
             "lightgcn": "lightgcn_validation_predictions.csv", "hybrid": "hybrid_validation_predictions.csv"}
    comparisons: dict[str, dict[str, list[dict]]] = {}
    dropped_zero_signal = 0
    for key, filename in files.items():
        frame = pd.read_csv(art / filename)
        frame = frame[frame["user_id"].isin(demo_set)]
        by_user: dict[str, list[dict]] = {}
        for row in frame.itertuples(index=False):
            user, video = int(row.user_id), int(row.video_id)
            score = float(row.hybrid_score if key == "hybrid" else row.score)
            if key == "popularity":
                reasons = [{"code": "popular_in_training", "text": "Popular in positive training interactions.",
                            "evidence": {"positive_training_event_count": pop_counts[str(video)], "popularity_weight": 1.0}}]
            elif key == "item_cf":
                raw_reasons = build_reasons(train_prefs.get(user, {}), item_to_index[video], similarity, catalog_ids,
                                            pop_counts[str(video)], {"item_cf": 1.0, "popularity": 0.0, "lightgcn": 0.0})
                reasons = [convert_reason(r) for r in raw_reasons]
                if not reasons:
                    # Users without positive training history get all-zero Item-CF scores
                    # (id-ordered filler). No supported evidence exists, so do not serve them.
                    if score != 0.0:
                        raise ValueError(f"Item-CF item {video} for user {user} has a score but no evidence")
                    dropped_zero_signal += 1
                    continue
            elif key == "lightgcn":
                reasons = [{"code": "extension_model_match",
                            "text": "Ranked by the LightGCN embedding dot-product score (rejected experiment; zero weight in the selected hybrid).",
                            # ``lightgcn_weight`` is the weight in the selected hybrid, as required by reason_codes.json.
                            "evidence": {"lightgcn_score": score, "lightgcn_weight": weights["lightgcn"]}}]
            else:
                reasons = [convert_reason(r) for r in hybrid_evidence[(user, video)]]
            item = {"item_id": str(video), "rank": int(row.rank), "score": score, "source": MODEL_IDS[key], "reasons": reasons}
            if key == "hybrid":
                item["components"] = {
                    name: {"normalized_score": float(getattr(row, f"{name}_score")), "weight": weights[name],
                           "contribution": round(float(getattr(row, f"{name}_score")) * weights[name], 9)}
                    for name in ("item_cf", "lightgcn", "popularity")
                }
            by_user.setdefault(str(user), []).append(item)
        comparisons[MODEL_IDS[key]] = by_user
    (out / "comparisons.json").write_text(json.dumps(comparisons, separators=(",", ":")), encoding="utf-8")

    (out / "popularity.json").write_text(json.dumps(
        [{"item_id": i, "positive_training_event_count": pop_counts[i]} for i in pop_order], separators=(",", ":")), encoding="utf-8")

    pop_m, item_m, light_m, hyb_m = load("popularity_validation_metrics.json"), load("item_cf_validation_metrics.json"), load("lightgcn_validation_metrics.json"), load("hybrid_validation_metrics.json")
    models = [
        {"id": MODEL_IDS["popularity"], "name": "Popularity baseline", "type": "baseline",
         "description": "Count of training events with watch_ratio > 2.0; also the cold-start fallback.",
         "is_fallback": True, "status": "baseline", "metrics": metric_row(pop_m)},
        {"id": MODEL_IDS["item_cf"], "name": "Item-CF", "type": "collaborative",
         "description": "Validation-tuned cosine item-item collaborative filtering.",
         "is_fallback": False, "status": "baseline", "metrics": metric_row(item_m)},
        {"id": MODEL_IDS["lightgcn"], "name": "LightGCN (rejected experiment)", "type": "experimental",
         "description": "Evaluated on validation; underperformed both baselines and received zero hybrid weight.",
         "is_fallback": False, "status": "rejected", "metrics": metric_row(light_m["validation"])},
        {"id": SELECTED_MODEL, "name": "Selected hybrid", "type": "hybrid",
         "description": f"Frozen {weights['item_cf']} Item-CF + {weights['lightgcn']} LightGCN + {weights['popularity']} popularity (validation-selected).",
         "is_fallback": False, "status": "selected",
         "weights": {"alpha_cf": weights["item_cf"], "beta_extension": weights["lightgcn"], "gamma_popularity": weights["popularity"]},
         "metrics": metric_row(hyb_m["full_validation"])},
    ]
    serving_files = ["catalog.json", "recommendations.json.gz", "comparisons.json", "popularity.json",
                     "user_profiles.json", "item_similarity.json"]
    manifest = {
        "manifest_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_model_manifest_generated_at": model_manifest["generated_at_utc"],
        "dataset_release": {
            "name": model_manifest["dataset"]["release"],
            "paper": "KuaiRec: A Fully-observed Dataset and Insights for Evaluating Recommender Systems",
            "official_url": "https://zenodo.org/records/18164998",
            "source_repo": "https://github.com/chongminggao/KuaiRec",
            "protocol": model_manifest["protocol"]["split"],
            "target_definition": model_manifest["dataset"]["target"]["definition"],
            "eligible_users": len(test_users),
            "eligible_items": len(catalog_ids),
        },
        "current_model": SELECTED_MODEL,
        "fallback_model": MODEL_IDS["popularity"],
        "selected_weights": weights,
        "models": models,
        "serving": {
            "recommendations": {"model_id": SELECTED_MODEL, "split": "test",
                                "history": "train + validation (user_history_test.csv)",
                                "candidates": freeze["test_protocol"]["candidates"], "list_length": 20},
            "comparisons": {"split": "validation", "history": "train only",
                            "candidates": "full eligible catalog minus training-seen items",
                            "users": len(demo_users), "list_length": 20,
                            "item_cf_zero_signal_rows_dropped": dropped_zero_signal},
        },
        "reason_code_rules": [
            {"code": code, "enabled": rule["enabled"], "description": rule["rule"], "required_evidence": rule["required_evidence"]}
            for code, rule in reason_config["reason_codes"].items()
        ],
        "source_artifacts_sha256": {
            "test_time_manifest.json": sha256(art / "test_time_manifest.json"),
            "controlled_test_predictions.csv": sha256(art / "controlled_test_predictions.csv"),
            "controlled_test_metrics.json": sha256(art / "controlled_test_metrics.json"),
            "reason_codes.json": sha256(root / "model" / "reason_codes.json"),
            **freeze["frozen_artifacts_sha256"],
        },
        "bundle_sha256": {name: sha256(out / name) for name in serving_files if (out / name).exists()},
    }
    (out / "model_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    evaluation = test_metrics["evaluation"]
    summary = {
        "evaluation_protocol": {
            "dataset": model_manifest["dataset"]["release"],
            "training_split": "chronological 70%", "validation_split": "chronological 15%", "test_split": "chronological 15%",
            "target_threshold": "watch_ratio > 2.0",
            "candidate_pool": "full eligible catalog minus seen items",
            "evaluation_users_count": evaluation["users_total"], "catalog_size": len(catalog_ids),
            "metric_denominator_policy": test_metrics["metric_denominator_policy"],
            "seed": test_metrics["seed"],
        },
        "validation_metrics": models,
        "overall_metrics": models,
        "controlled_test": {
            "model_id": test_metrics["model_id"], **metric_row(evaluation),
            "users_metric_eligible": evaluation["users_metric_eligible"],
            "users_without_eligible_relevant_item": evaluation["users_without_eligible_relevant_item"],
            "all_user_evaluation_coverage": evaluation["all_user_evaluation_coverage"],
            "behavior_checks": test_metrics["behavior_checks"],
            "runtime_seconds": test_metrics["runtime_seconds"],
            "runtime_environment": test_metrics["runtime_environment"],
        },
    }
    (out / "metrics_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"catalog": len(catalog), "users": len(recommendations), "demo_users": len(demo_users),
                      "no_history_users": len(no_history), "recommendation_rows": int(len(predictions))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
