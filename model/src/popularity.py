"""Train and validate the training-only KuaiRec popularity baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sqlite3
import tempfile
import time
from collections import Counter
from pathlib import Path

from model.src.common import repository_root, sha256_file

MODEL_SCHEMA_VERSION = "1.0"
DEFAULT_TOP_KS = (10, 20)


def train_and_evaluate_popularity(
    data_dir: Path,
    output_dir: Path,
    top_ks: tuple[int, ...] = DEFAULT_TOP_KS,
    example_users: int = 5,
) -> dict[str, object]:
    """Fit on train only, evaluate on validation, and write serving artifacts."""
    started = time.perf_counter()
    top_ks = tuple(sorted(set(top_ks)))
    if not top_ks or top_ks[0] < 1:
        raise ValueError("top_ks must contain positive integers")
    if example_users < 0:
        raise ValueError("example_users must be non-negative")

    train_path = data_dir / "train.csv"
    validation_path = data_dir / "validation.csv"
    catalog_path = data_dir / "candidate_catalog.csv"
    split_manifest_path = data_dir / "split_manifest.json"
    for path in (train_path, validation_path, catalog_path, split_manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    _verify_input_hashes(split_manifest, data_dir, ("train.csv", "validation.csv", "candidate_catalog.csv"))

    catalog = _read_catalog(catalog_path)
    positive_counts: Counter[int] = Counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kuairec-popularity-") as temporary:
        connection = sqlite3.connect(Path(temporary) / "seen.sqlite")
        try:
            _build_seen_index_and_counts(connection, train_path, positive_counts)
            ranking = sorted(catalog, key=lambda item: (-positive_counts[item], item))
            evaluation = _evaluate_validation(
                connection,
                validation_path,
                ranking,
                positive_counts,
                output_dir / "popularity_validation_predictions.csv",
                top_ks,
                example_users,
            )
        finally:
            connection.close()

    model = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "model_id": "popularity-positive-event-count-v1",
        "model_type": "popularity",
        "training_split": "train",
        "score_definition": "count of training events with watch_ratio > 2.0",
        "relevance_definition": split_manifest["relevance"],
        "tie_break": "video_id ascending",
        "cold_start_fallback": True,
        "catalog_size": len(catalog),
        "items": [
            {"video_id": item, "score": positive_counts[item], "global_rank": rank}
            for rank, item in enumerate(ranking, start=1)
        ],
    }
    model_path = output_dir / "popularity_model.json"
    model_path.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    metrics = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "model_id": model["model_id"],
        "evaluation_split": "validation",
        "candidate_protocol": (
            "full eligible catalog minus each user's training-seen items"
        ),
        "metric_denominator_policy": (
            "ranking metrics average over users with at least one eligible relevant "
            "validation item; all-user coverage is reported separately"
        ),
        **evaluation,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "runtime_environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "input_sha256": {
            name: split_manifest["sha256"][name]
            for name in ("train.csv", "validation.csv", "candidate_catalog.csv")
        },
    }
    metrics_path = output_dir / "popularity_validation_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    artifacts = {
        path.name: sha256_file(path)
        for path in (
            model_path,
            metrics_path,
            output_dir / "popularity_validation_predictions.csv",
        )
    }
    manifest = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "model_id": model["model_id"],
        "training_data": "train.csv only",
        "validation_data_used_for_selection": True,
        "test_data_used": False,
        "split_manifest_sha256": sha256_file(split_manifest_path),
        "artifacts_sha256": artifacts,
    }
    (output_dir / "popularity_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"model": model, "metrics": metrics, "manifest": manifest}


def _verify_input_hashes(
    manifest: dict[str, object], data_dir: Path, filenames: tuple[str, ...]
) -> None:
    expected = manifest.get("sha256")
    if not isinstance(expected, dict):
        raise ValueError("split manifest has no sha256 mapping")
    for filename in filenames:
        if expected.get(filename) != sha256_file(data_dir / filename):
            raise ValueError(f"Input checksum mismatch: {filename}")


def _read_catalog(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8", newline="") as source:
        items = [int(row["video_id"]) for row in csv.DictReader(source)]
    if len(items) != len(set(items)):
        raise ValueError("candidate catalog contains duplicate video IDs")
    return items


def _build_seen_index_and_counts(
    connection: sqlite3.Connection, train_path: Path, positive_counts: Counter[int]
) -> None:
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute(
        "CREATE TABLE seen (user_id INTEGER NOT NULL, video_id INTEGER NOT NULL, "
        "PRIMARY KEY (user_id, video_id)) WITHOUT ROWID"
    )
    batch: list[tuple[int, int]] = []
    with train_path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            user_id = int(row["user_id"])
            video_id = int(row["video_id"])
            if row["is_relevant"] == "1":
                positive_counts[video_id] += 1
            batch.append((user_id, video_id))
            if len(batch) >= 50_000:
                connection.executemany("INSERT OR IGNORE INTO seen VALUES (?, ?)", batch)
                batch.clear()
        if batch:
            connection.executemany("INSERT OR IGNORE INTO seen VALUES (?, ?)", batch)
    connection.commit()


def _evaluate_validation(
    connection: sqlite3.Connection,
    validation_path: Path,
    ranking: list[int],
    scores: Counter[int],
    predictions_path: Path,
    top_ks: tuple[int, ...],
    example_limit: int,
) -> dict[str, object]:
    max_k = max(top_ks)
    sums = {f"recall@{k}": 0.0 for k in top_ks}
    sums.update({f"ndcg@{k}": 0.0 for k in top_ks})
    sums.update({f"precision@{k}": 0.0 for k in top_ks})
    sums.update({f"hit_rate@{k}": 0.0 for k in top_ks})
    users_total = users_eligible = users_without_positive = 0
    recommended_items: set[int] = set()
    examples: list[dict[str, object]] = []

    with (
        validation_path.open("r", encoding="utf-8", newline="") as source,
        predictions_path.open("w", encoding="utf-8", newline="") as target,
    ):
        writer = csv.writer(target)
        writer.writerow(("user_id", "rank", "video_id", "score", "is_relevant"))
        current_user: int | None = None
        relevant: set[int] = set()

        def finish_user() -> None:
            nonlocal users_total, users_eligible, users_without_positive
            if current_user is None:
                return
            users_total += 1
            seen = {
                row[0]
                for row in connection.execute(
                    "SELECT video_id FROM seen WHERE user_id=?", (current_user,)
                )
            }
            eligible_relevant = relevant - seen
            recommendations: list[int] = []
            for item in ranking:
                if item not in seen:
                    recommendations.append(item)
                    if len(recommendations) == max_k:
                        break
            recommended_items.update(recommendations)
            for rank, item in enumerate(recommendations, start=1):
                writer.writerow((current_user, rank, item, scores[item], int(item in eligible_relevant)))
            if not eligible_relevant:
                users_without_positive += 1
                return
            users_eligible += 1
            for k in top_ks:
                hits = [int(item in eligible_relevant) for item in recommendations[:k]]
                hit_count = sum(hits)
                sums[f"recall@{k}"] += hit_count / len(eligible_relevant)
                sums[f"precision@{k}"] += hit_count / k
                sums[f"hit_rate@{k}"] += float(hit_count > 0)
                dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
                ideal = sum(1 / math.log2(index + 2) for index in range(min(k, len(eligible_relevant))))
                sums[f"ndcg@{k}"] += dcg / ideal
            if len(examples) < example_limit:
                examples.append({
                    "user_id": current_user,
                    "eligible_relevant_items": sorted(eligible_relevant),
                    "top_recommendations": [
                        {"video_id": item, "score": scores[item], "is_relevant": item in eligible_relevant}
                        for item in recommendations[:10]
                    ],
                })

        for row in csv.DictReader(source):
            user_id = int(row["user_id"])
            if user_id != current_user:
                finish_user()
                current_user = user_id
                relevant = set()
            if row["is_relevant"] == "1":
                relevant.add(int(row["video_id"]))
        finish_user()

    metrics = {name: value / users_eligible for name, value in sums.items()} if users_eligible else sums
    return {
        "users_total": users_total,
        "users_metric_eligible": users_eligible,
        "users_without_eligible_relevant_item": users_without_positive,
        "all_user_evaluation_coverage": users_eligible / users_total if users_total else 0.0,
        "metrics": metrics,
        "catalog_coverage_at_max_k": len(recommended_items) / len(ranking) if ranking else 0.0,
        "distinct_recommended_items_at_max_k": len(recommended_items),
        "per_user_examples": examples,
    }


def main() -> None:
    root = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--output-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--example-users", type=int, default=5)
    args = parser.parse_args()
    result = train_and_evaluate_popularity(args.data_dir, args.output_dir, example_users=args.example_users)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
