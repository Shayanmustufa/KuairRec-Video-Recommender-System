"""Generate and validate explanation evidence, then freeze test-time artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from scipy import sparse

from model.src.common import repository_root, sha256_file
from model.src.item_cf import _read_training


def build_reasons(
    user_preferences: dict[int, float],
    candidate: int,
    similarity: sparse.csc_matrix,
    catalog: list[int],
    popularity_count: int,
    weights: dict[str, float],
) -> list[dict[str, object]]:
    reasons: list[dict[str, object]] = []
    start, end = similarity.indptr[candidate:candidate + 2]
    best: tuple[float, int, float, float] | None = None
    for source, value in zip(similarity.indices[start:end], similarity.data[start:end]):
        preference = user_preferences.get(int(source))
        if preference is None or value <= 0:
            continue
        contribution = float(value) * preference
        key = (contribution, -catalog[int(source)])
        if best is None or key > (best[0], -catalog[best[1]]):
            best = (contribution, int(source), float(value), preference)
    if best is not None and weights["item_cf"] > 0:
        contribution, source, similarity_value, preference = best
        reasons.append({
            "code": "liked_by_similar_users",
            "display_text": "Recommended from collaborative patterns linked to your positive history.",
            "evidence": {
                "source_video_id": catalog[source],
                "similarity": similarity_value,
                "preference_strength": preference,
                "contribution": contribution,
                "item_cf_weight": weights["item_cf"],
            },
        })
    if popularity_count > 0 and weights["popularity"] > 0:
        reasons.append({
            "code": "popular_in_training",
            "display_text": "Popular in positive training interactions.",
            "evidence": {
                "positive_training_event_count": popularity_count,
                "popularity_weight": weights["popularity"],
            },
        })
    return reasons


def freeze_day9(data_dir: Path, artifact_dir: Path, reason_config_path: Path) -> dict[str, object]:
    hybrid_config = json.loads((artifact_dir / "hybrid_config.json").read_text(encoding="utf-8"))
    weights = hybrid_config["selected_weights"]
    reason_config = json.loads(reason_config_path.read_text(encoding="utf-8"))
    if weights["lightgcn"] == 0 and reason_config["reason_codes"]["extension_model_match"]["enabled"]:
        raise ValueError("LightGCN explanations cannot be enabled at zero selected weight")
    mapping = json.loads((artifact_dir / "item_cf_mapping.json").read_text(encoding="utf-8"))
    users, catalog = mapping["users"], mapping["items"]
    item_to_index = {item: index for index, item in enumerate(catalog)}
    training_users, _, preferences = _read_training(data_dir / "train.csv", item_to_index)
    if training_users != users:
        raise ValueError("Training and artifact user mappings differ")
    similarity = sparse.load_npz(artifact_dir / "item_cf_model.npz").tocsc()
    popularity = json.loads((artifact_dir / "popularity_model.json").read_text(encoding="utf-8"))
    popularity_counts = {int(row["video_id"]): int(row["score"]) for row in popularity["items"]}
    user_to_index = {user: index for index, user in enumerate(users)}

    evidence_path = artifact_dir / "explanation_evidence.jsonl"
    counts: dict[str, int] = {}
    recommendation_count = unsupported = lightgcn_reasons = 0
    with (
        (artifact_dir / "hybrid_validation_predictions.csv").open("r", encoding="utf-8", newline="") as source,
        evidence_path.open("w", encoding="utf-8") as target,
    ):
        current_user: int | None = None
        preference_map: dict[int, float] = {}
        for row in csv.DictReader(source):
            user = int(row["user_id"])
            if user != current_user:
                current_user = user
                index = user_to_index[user]
                start, end = preferences.indptr[index:index + 2]
                preference_map = {
                    int(item): float(value)
                    for item, value in zip(preferences.indices[start:end], preferences.data[start:end])
                }
            video_id = int(row["video_id"])
            item = item_to_index[video_id]
            reasons = build_reasons(
                preference_map, item, similarity, catalog,
                popularity_counts[video_id], weights,
            )
            recommendation_count += 1
            if not reasons:
                unsupported += 1
            for reason in reasons:
                code = str(reason["code"])
                counts[code] = counts.get(code, 0) + 1
                lightgcn_reasons += code == "extension_model_match"
            target.write(json.dumps({
                "user_id": user,
                "rank": int(row["rank"]),
                "video_id": video_id,
                "model_id": hybrid_config["model_id"],
                "hybrid_score": float(row["hybrid_score"]),
                "reasons": reasons,
            }, separators=(",", ":")) + "\n")
    if unsupported:
        raise ValueError(f"{unsupported} recommendations have no supported reason")
    if lightgcn_reasons:
        raise ValueError("LightGCN reasons emitted despite zero selected weight")

    validation = {
        "schema_version": "1.0",
        "recommendations_checked": recommendation_count,
        "recommendations_without_supported_reason": unsupported,
        "reason_instances_by_code": counts,
        "extension_model_reasons_at_zero_weight": lightgcn_reasons,
        "evidence_coverage": 1.0,
        "passed": True,
    }
    validation_path = artifact_dir / "explanation_validation.json"
    validation_path.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")

    frozen_files = (
        "popularity_model.json", "popularity_manifest.json",
        "item_cf_model.npz", "item_cf_mapping.json", "item_cf_manifest.json",
        "lightgcn_embeddings.npz", "lightgcn_mapping.json", "lightgcn_manifest.json",
        "hybrid_config.json", "hybrid_manifest.json",
        "explanation_evidence.jsonl", "explanation_validation.json",
    )
    split_manifest = json.loads((data_dir / "split_manifest.json").read_text(encoding="utf-8"))
    freeze = {
        "schema_version": "1.0",
        "status": "frozen_for_controlled_test",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_model_id": hybrid_config["model_id"],
        "selected_weights": weights,
        "selection_data": "validation only",
        "test_data_accessed_for_model_selection": False,
        "test_protocol": {
            "split_sha256": split_manifest["sha256"]["test.csv"],
            "candidates": "full eligible catalog minus training and validation seen items",
            "primary_k": 10,
            "secondary_k": 20,
            "metric_denominator_policy": split_manifest["filtered"]["candidate_protocol"]["ranking_metric_denominator_policy"],
        },
        "reason_config_sha256": sha256_file(reason_config_path),
        "data_manifests_sha256": {
            "release_manifest.json": sha256_file(data_dir / "release_manifest.json"),
            "split_manifest.json": sha256_file(data_dir / "split_manifest.json"),
            "data_audit.json": sha256_file(data_dir / "data_audit.json"),
        },
        "frozen_artifacts_sha256": {
            filename: sha256_file(artifact_dir / filename) for filename in frozen_files
        },
    }
    freeze_path = artifact_dir / "test_time_manifest.json"
    freeze_path.write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    return {"validation": validation, "freeze": freeze}


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--artifact-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--reason-config", type=Path, default=root / "model" / "reason_codes.json")
    args = parser.parse_args(); result = freeze_day9(args.data_dir, args.artifact_dir, args.reason_config)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
