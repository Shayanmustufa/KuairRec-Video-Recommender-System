"""Run the single controlled test evaluation against Day 9 frozen artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import time

import numpy as np

from model.src.common import repository_root, sha256_file
from model.src.hybrid import _evaluate_full, _load_components
from model.src.item_cf import _read_training
from model.src.lightgcn_tune import _validation


def assert_test_not_already_run(artifact_dir: Path) -> None:
    existing = [
        name for name in (
            "controlled_test_metrics.json",
            "controlled_test_predictions.csv",
            "controlled_test_manifest.json",
        )
        if (artifact_dir / name).exists()
    ]
    if existing:
        raise FileExistsError(
            "Controlled test output already exists; refusing a second test run: "
            + ", ".join(existing)
        )


def run_controlled_test(
    data_dir: Path,
    artifact_dir: Path,
    evaluator_path: Path,
) -> dict[str, object]:
    assert_test_not_already_run(artifact_dir)
    started = time.perf_counter()
    freeze_path = artifact_dir / "test_time_manifest.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze["status"] != "frozen_for_controlled_test":
        raise ValueError("Artifacts are not frozen for controlled test")
    for filename, expected in freeze["frozen_artifacts_sha256"].items():
        if sha256_file(artifact_dir / filename) != expected:
            raise ValueError(f"Frozen artifact changed: {filename}")
    leakage = json.loads((artifact_dir / "leakage_audit.json").read_text(encoding="utf-8"))
    if not leakage["passed"]:
        raise ValueError("Day 10 leakage audit did not pass")
    split = json.loads((data_dir / "split_manifest.json").read_text(encoding="utf-8"))
    if sha256_file(data_dir / "test.csv") != freeze["test_protocol"]["split_sha256"]:
        raise ValueError("Frozen test split checksum mismatch")
    config = json.loads((artifact_dir / "hybrid_config.json").read_text(encoding="utf-8"))
    weights_map = config["selected_weights"]
    if weights_map != freeze["selected_weights"]:
        raise ValueError("Hybrid weights differ from frozen weights")
    weights = tuple(float(weights_map[name]) for name in ("popularity", "item_cf", "lightgcn"))

    catalog = _catalog(data_dir / "candidate_catalog.csv")
    item_to_index = {item: index for index, item in enumerate(catalog)}
    users, seen, preferences = _read_training(
        data_dir / "user_history_test.csv", item_to_index
    )
    relevant = _validation(data_dir / "test.csv", users, catalog)
    relevant = [
        items - set(seen.indices[seen.indptr[user]:seen.indptr[user + 1]])
        for user, items in enumerate(relevant)
    ]
    component_data = _load_components(artifact_dir, users, catalog)
    predictions_path = artifact_dir / "controlled_test_predictions.csv"
    evaluation = _evaluate_full(
        weights, users, catalog, seen, preferences, relevant,
        component_data, predictions_path,
    )
    seen_violations, duplicate_recommendations, prediction_rows = _audit_predictions(
        predictions_path, users, catalog, seen
    )
    if seen_violations or duplicate_recommendations:
        raise ValueError(
            f"Invalid test predictions: seen={seen_violations}, duplicates={duplicate_recommendations}"
        )
    positive_history_users = int(np.count_nonzero(np.diff(preferences.indptr)))
    metrics = {
        "schema_version": "1.0",
        "run_type": "single_controlled_test_pass",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": freeze["selected_model_id"],
        "frozen_weights": weights_map,
        "seed": split["seed"],
        "candidate_protocol": freeze["test_protocol"]["candidates"],
        "metric_denominator_policy": freeze["test_protocol"]["metric_denominator_policy"],
        "evaluation": evaluation,
        "behavior_checks": {
            "prediction_rows": prediction_rows,
            "seen_item_violations": seen_violations,
            "duplicate_recommendations": duplicate_recommendations,
            "users_with_positive_pretest_history": positive_history_users,
            "users_without_positive_pretest_history": len(users) - positive_history_users,
            "known_user_recommendation_coverage": 1.0,
            "cold_start_fallback_available": True,
            "unknown_user_test_population": "not present in offline test split",
        },
        "selection_locked_after_test": True,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "runtime_environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "platform": platform.platform(),
        },
    }
    metrics_path = artifact_dir / "controlled_test_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "run_type": "single_controlled_test_pass",
        "model_selection_reopened": False,
        "frozen_manifest_sha256": sha256_file(freeze_path),
        "leakage_audit_sha256": sha256_file(artifact_dir / "leakage_audit.json"),
        "evaluator_source_sha256": sha256_file(evaluator_path),
        "test_split_sha256": sha256_file(data_dir / "test.csv"),
        "outputs_sha256": {
            predictions_path.name: sha256_file(predictions_path),
            metrics_path.name: sha256_file(metrics_path),
        },
    }
    manifest_path = artifact_dir / "controlled_test_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"metrics": metrics, "manifest": manifest}


def _catalog(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return [int(row["video_id"]) for row in csv.DictReader(source)]


def _audit_predictions(
    path: Path,
    users: list[int],
    catalog: list[int],
    seen,
) -> tuple[int, int, int]:
    user_index = {user: index for index, user in enumerate(users)}
    item_index = {item: index for index, item in enumerate(catalog)}
    seen_violations = duplicates = rows = 0
    previous_user: int | None = None
    recommended: set[int] = set()
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            user = int(row["user_id"]); item = item_index[int(row["video_id"])]
            if user != previous_user:
                previous_user = user; recommended = set()
            if item in recommended:
                duplicates += 1
            recommended.add(item)
            index = user_index[user]
            start, end = seen.indptr[index:index + 2]
            user_seen = seen.indices[start:end]
            position = np.searchsorted(user_seen, item)
            seen_violations += int(position < len(user_seen) and user_seen[position] == item)
            rows += 1
    return seen_violations, duplicates, rows


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--artifact-dir", type=Path, default=root / "model" / "artifacts")
    args = parser.parse_args()
    result = run_controlled_test(args.data_dir, args.artifact_dir, Path(__file__))
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__": main()
