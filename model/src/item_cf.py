"""Train and validate an implicit-feedback item-based collaborative filter."""

from __future__ import annotations

import argparse
from array import array
import csv
import json
import math
import platform
import time
from pathlib import Path

import numpy as np
from scipy import sparse

from model.src.common import repository_root, sha256_file

SCHEMA_VERSION = "1.0"
TOP_KS = (10, 20)
NEIGHBORHOODS = (1, 3, 5, 10, 20, 50, 100)
SHRINKAGES = (0.0, 10.0, 50.0, 100.0, 200.0, 500.0, 1000.0)


def train_and_evaluate_item_cf(
    data_dir: Path,
    output_dir: Path,
    neighborhoods: tuple[int, ...] = NEIGHBORHOODS,
    shrinkages: tuple[float, ...] = SHRINKAGES,
    tuning_user_limit: int | None = 1000,
) -> dict[str, object]:
    started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    split_manifest_path = data_dir / "split_manifest.json"
    split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    required = ("train.csv", "validation.csv", "candidate_catalog.csv")
    for name in required:
        expected = split_manifest["sha256"][name]
        if sha256_file(data_dir / name) != expected:
            raise ValueError(f"Input checksum mismatch: {name}")

    catalog = _read_catalog(data_dir / "candidate_catalog.csv")
    item_to_index = {item: index for index, item in enumerate(catalog)}
    users, seen, preferences = _read_training(data_dir / "train.csv", item_to_index)
    validation = _read_validation(data_dir / "validation.csv", users, item_to_index)
    similarity_inputs = _cooccurrence(preferences)

    tune_indices = np.arange(len(users))
    if tuning_user_limit is not None:
        eligible = np.array([i for i, relevant in enumerate(validation) if relevant], dtype=np.int32)
        generator = np.random.default_rng(2026)
        tune_indices = np.sort(generator.choice(
            eligible, size=min(tuning_user_limit, len(eligible)), replace=False
        ))
    grid: list[dict[str, object]] = []
    best_key: tuple[float, float, float, int] | None = None
    best_config: tuple[int, float] | None = None
    for shrinkage in shrinkages:
        maximum = _build_similarity(similarity_inputs, max(neighborhoods), shrinkage)
        for neighborhood in neighborhoods:
            similarity = _prune_similarity(maximum, neighborhood)
            result = _evaluate(
                preferences,
                seen,
                validation,
                similarity,
                catalog,
                users,
                user_indices=tune_indices,
                predictions_path=None,
            )
            row = {
                "neighborhood_size": neighborhood,
                "shrinkage": shrinkage,
                "users_metric_eligible": result["users_metric_eligible"],
                **result["metrics"],
            }
            grid.append(row)
            key = (
                float(result["metrics"]["ndcg@10"]),
                float(result["metrics"]["recall@10"]),
                -shrinkage,
                -neighborhood,
            )
            if best_key is None or key > best_key:
                best_key = key
                best_config = (neighborhood, shrinkage)
    assert best_config is not None

    selected_neighbors, selected_shrinkage = best_config
    selected_similarity = _prune_similarity(
        _build_similarity(similarity_inputs, max(neighborhoods), selected_shrinkage),
        selected_neighbors,
    )
    predictions_path = output_dir / "item_cf_validation_predictions.csv"
    full_result = _evaluate(
        preferences,
        seen,
        validation,
        selected_similarity,
        catalog,
        users,
        user_indices=np.arange(len(users)),
        predictions_path=predictions_path,
    )
    model_path = output_dir / "item_cf_model.npz"
    sparse.save_npz(model_path, selected_similarity)
    mapping_path = output_dir / "item_cf_mapping.json"
    mapping_path.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "model_id": "item-cf-cosine-v1",
        "users": users,
        "items": catalog,
        "preference_weight": "max log1p(watch_ratio) per positive training user-item",
        "similarity": "binary-positive implicit cosine with cooccurrence shrinkage",
        "score": "similarity-weighted mean of positive-history preference strengths",
        "selected_neighborhood_size": selected_neighbors,
        "selected_shrinkage": selected_shrinkage,
        "tie_break": "score descending, video_id ascending",
    }, indent=2) + "\n", encoding="utf-8")

    popularity_metrics = json.loads(
        (output_dir / "popularity_validation_metrics.json").read_text(encoding="utf-8")
    )
    metrics = {
        "schema_version": SCHEMA_VERSION,
        "model_id": "item-cf-cosine-v1",
        "evaluation_split": "validation",
        "test_data_used": False,
        "candidate_protocol": "full eligible catalog minus training-seen items",
        "selection_metric": "NDCG@10, then Recall@10; simpler configuration breaks ties",
        "tuning_user_limit": tuning_user_limit,
        "tuning_grid": grid,
        "selected_configuration": {
            "neighborhood_size": selected_neighbors,
            "shrinkage": selected_shrinkage,
        },
        **full_result,
        "comparison_to_popularity": {
            metric: float(full_result["metrics"][metric]) - float(popularity_metrics["metrics"][metric])
            for metric in full_result["metrics"]
        },
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "runtime_environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "platform": platform.platform(),
        },
    }
    metrics_path = output_dir / "item_cf_validation_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    artifact_paths = (model_path, mapping_path, metrics_path, predictions_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "model_id": "item-cf-cosine-v1",
        "training_data": "train.csv only",
        "validation_data_used_for_selection": True,
        "test_data_used": False,
        "split_manifest_sha256": sha256_file(split_manifest_path),
        "artifacts_sha256": {path.name: sha256_file(path) for path in artifact_paths},
    }
    (output_dir / "item_cf_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"metrics": metrics, "manifest": manifest}


def _read_catalog(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return [int(row["video_id"]) for row in csv.DictReader(source)]


def _read_training(
    path: Path, item_to_index: dict[int, int]
) -> tuple[list[int], sparse.csr_matrix, sparse.csr_matrix]:
    users: list[int] = []
    user_to_index: dict[int, int] = {}
    seen_rows = array("I")
    seen_columns = array("I")
    preference: dict[tuple[int, int], float] = {}
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            user = int(row["user_id"])
            if user not in user_to_index:
                user_to_index[user] = len(users)
                users.append(user)
            pair = (user_to_index[user], item_to_index[int(row["video_id"])])
            seen_rows.append(pair[0])
            seen_columns.append(pair[1])
            if row["is_relevant"] == "1":
                weight = math.log1p(float(row["watch_ratio"]))
                preference[pair] = max(preference.get(pair, 0.0), weight)
    shape = (len(users), len(item_to_index))
    seen = sparse.coo_matrix(
        (
            np.ones(len(seen_rows), dtype=np.float32),
            (np.frombuffer(seen_rows, dtype=np.uint32), np.frombuffer(seen_columns, dtype=np.uint32)),
        ),
        shape=shape,
    ).tocsr()
    seen.data[:] = 1.0
    seen.eliminate_zeros()
    rows, columns, values = zip(*((u, i, w) for (u, i), w in preference.items()))
    preferences = sparse.csr_matrix((values, (rows, columns)), shape=shape, dtype=np.float32)
    return users, seen, preferences


def _read_validation(
    path: Path, users: list[int], item_to_index: dict[int, int]
) -> list[set[int]]:
    user_to_index = {user: index for index, user in enumerate(users)}
    relevant = [set() for _ in users]
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["is_relevant"] == "1":
                relevant[user_to_index[int(row["user_id"])]].add(
                    item_to_index[int(row["video_id"])]
                )
    return relevant


def _cooccurrence(preferences: sparse.csr_matrix) -> tuple[sparse.csr_matrix, np.ndarray]:
    binary = preferences.copy()
    binary.data[:] = 1.0
    degrees = np.asarray(binary.sum(axis=0)).ravel()
    cooccurrence = (binary.T @ binary).tocsr()
    cooccurrence.setdiag(0)
    cooccurrence.eliminate_zeros()
    return cooccurrence, degrees


def _build_similarity(
    inputs: tuple[sparse.csr_matrix, np.ndarray], max_neighbors: int, shrinkage: float
) -> sparse.csr_matrix:
    cooccurrence, degrees = inputs
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for item in range(cooccurrence.shape[0]):
        start, end = cooccurrence.indptr[item:item + 2]
        candidates = cooccurrence.indices[start:end]
        counts = cooccurrence.data[start:end]
        similarities = counts / np.sqrt(degrees[item] * degrees[candidates])
        if shrinkage:
            similarities *= counts / (counts + shrinkage)
        order = np.lexsort((candidates, -similarities))[:max_neighbors]
        rows.extend([item] * len(order))
        columns.extend(candidates[order].tolist())
        values.extend(similarities[order].tolist())
    return sparse.csr_matrix((values, (rows, columns)), shape=cooccurrence.shape, dtype=np.float32)


def _prune_similarity(similarity: sparse.csr_matrix, neighbors: int) -> sparse.csr_matrix:
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for item in range(similarity.shape[0]):
        start, end = similarity.indptr[item:item + 2]
        candidates = similarity.indices[start:end]
        similarities = similarity.data[start:end]
        order = np.lexsort((candidates, -similarities))[:neighbors]
        columns.extend(candidates[order].tolist())
        values.extend(similarities[order].tolist())
        rows.extend([item] * len(order))
    return sparse.csr_matrix((values, (rows, columns)), shape=similarity.shape, dtype=np.float32)


def _evaluate(
    preferences: sparse.csr_matrix,
    seen: sparse.csr_matrix,
    relevant: list[set[int]],
    similarity: sparse.csr_matrix,
    catalog: list[int],
    users: list[int],
    user_indices: np.ndarray,
    predictions_path: Path | None,
) -> dict[str, object]:
    numerators = (preferences[user_indices] @ similarity).tocsr()
    binary = preferences[user_indices].copy()
    binary.data[:] = 1.0
    denominators = (binary @ abs(similarity)).tocsr()
    scores = numerators.multiply(denominators.power(-1))
    scores.data[~np.isfinite(scores.data)] = 0
    sums = {f"{name}@{k}": 0.0 for name in ("recall", "ndcg", "precision", "hit_rate") for k in TOP_KS}
    eligible = without = 0
    recommended: set[int] = set()
    examples: list[dict[str, object]] = []
    target = predictions_path.open("w", encoding="utf-8", newline="") if predictions_path else None
    writer = csv.writer(target) if target else None
    if writer:
        writer.writerow(("user_id", "rank", "video_id", "score", "is_relevant"))
    try:
        for local, user_index in enumerate(user_indices):
            seen_items = set(seen.indices[seen.indptr[user_index]:seen.indptr[user_index + 1]])
            eligible_relevant = relevant[user_index] - seen_items
            start, end = scores.indptr[local:local + 2]
            candidate_indices = scores.indices[start:end]
            candidate_scores = scores.data[start:end]
            order = sorted(
                ((float(score), int(item)) for item, score in zip(candidate_indices, candidate_scores) if item not in seen_items),
                key=lambda pair: (-pair[0], catalog[pair[1]]),
            )
            chosen = order[:20]
            if len(chosen) < 20:
                chosen_items = {item for _, item in chosen}
                for item in range(len(catalog)):
                    if item not in seen_items and item not in chosen_items:
                        chosen.append((0.0, item))
                        if len(chosen) == 20:
                            break
            recommended.update(item for _, item in chosen)
            if writer:
                for rank, (score, item) in enumerate(chosen, 1):
                    writer.writerow((users[int(user_index)], rank, catalog[item], format(score, ".9g"), int(item in eligible_relevant)))
            if not eligible_relevant:
                without += 1
                continue
            eligible += 1
            for k in TOP_KS:
                hits = [int(item in eligible_relevant) for _, item in chosen[:k]]
                count = sum(hits)
                sums[f"recall@{k}"] += count / len(eligible_relevant)
                sums[f"precision@{k}"] += count / k
                sums[f"hit_rate@{k}"] += float(count > 0)
                dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
                ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(eligible_relevant))))
                sums[f"ndcg@{k}"] += dcg / ideal
            if len(examples) < 5:
                examples.append({"user_id": users[int(user_index)], "top_video_ids": [catalog[item] for _, item in chosen[:10]]})
    finally:
        if target:
            target.close()
    return {
        "users_total": len(user_indices),
        "users_metric_eligible": eligible,
        "users_without_eligible_relevant_item": without,
        "all_user_evaluation_coverage": eligible / len(user_indices) if len(user_indices) else 0,
        "metrics": {name: value / eligible if eligible else 0 for name, value in sums.items()},
        "catalog_coverage_at_20": len(recommended) / len(catalog),
        "distinct_recommended_items_at_20": len(recommended),
        "per_user_examples": examples,
    }


def main() -> None:
    root = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--output-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--tuning-user-limit", type=int, default=1000)
    args = parser.parse_args()
    result = train_and_evaluate_item_cf(args.data_dir, args.output_dir, tuning_user_limit=args.tuning_user_limit)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
