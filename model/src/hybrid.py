"""Tune and export the validation-selected three-component hybrid ranker."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import time
from pathlib import Path

import numpy as np
from scipy import sparse

from model.src.common import repository_root, sha256_file
from model.src.item_cf import _read_training
from model.src.lightgcn_tune import _validation

SEED = 2026
TUNING_USERS = 1024
WEIGHT_UNITS = 10
COMPONENTS = ("popularity", "item_cf", "lightgcn")


def weight_grid(units: int = WEIGHT_UNITS) -> list[tuple[float, float, float]]:
    if units < 1:
        raise ValueError("units must be positive")
    return [
        (popularity / units, item_cf / units, lightgcn / units)
        for popularity in range(units + 1)
        for item_cf in range(units - popularity + 1)
        for lightgcn in (units - popularity - item_cf,)
    ]


def tune_hybrid(
    data_dir: Path,
    artifact_dir: Path,
    tuning_users: int = TUNING_USERS,
) -> dict[str, object]:
    started = time.perf_counter()
    _verify_component_artifacts(artifact_dir)
    catalog = _catalog(data_dir / "candidate_catalog.csv")
    item_to_index = {item: index for index, item in enumerate(catalog)}
    users, seen, preferences = _read_training(data_dir / "train.csv", item_to_index)
    relevant = _validation(data_dir / "validation.csv", users, catalog)
    relevant = [
        items - set(seen.indices[seen.indptr[user]:seen.indptr[user + 1]])
        for user, items in enumerate(relevant)
    ]
    eligible = np.array([index for index, items in enumerate(relevant) if items], dtype=np.int32)
    generator = np.random.default_rng(SEED)
    tuning_indices = np.sort(generator.choice(
        eligible, size=min(tuning_users, len(eligible)), replace=False
    ))

    component_data = _load_components(artifact_dir, users, catalog)
    tuning_scores = _component_scores(
        tuning_indices, seen, preferences, component_data
    )
    grid_results: list[dict[str, object]] = []
    selected_weights: tuple[float, float, float] | None = None
    best_key: tuple[float, float, float, float] | None = None
    for weights in weight_grid():
        combined = sum(weight * score for weight, score in zip(weights, tuning_scores))
        _mask_seen(combined, seen[tuning_indices])
        metrics = _evaluate_score_matrix(
            combined,
            seen[tuning_indices],
            [relevant[index] for index in tuning_indices],
            [users[index] for index in tuning_indices],
            catalog,
            predictions_path=None,
            component_scores=None,
        )
        row = {
            "weights": dict(zip(COMPONENTS, weights)),
            **metrics,
        }
        grid_results.append(row)
        values = metrics["metrics"]
        key = (
            float(values["ndcg@10"]),
            float(values["recall@10"]),
            -float(weights[2]),
            -sum(weight > 0 for weight in weights),
        )
        if best_key is None or key > best_key:
            best_key = key
            selected_weights = weights
    assert selected_weights is not None

    predictions_path = artifact_dir / "hybrid_validation_predictions.csv"
    full_metrics = _evaluate_full(
        selected_weights,
        users,
        catalog,
        seen,
        preferences,
        relevant,
        component_data,
        predictions_path,
    )
    frozen_metrics = {
        "popularity": json.loads(
            (artifact_dir / "popularity_validation_metrics.json").read_text(encoding="utf-8")
        )["metrics"],
        "item_cf": json.loads(
            (artifact_dir / "item_cf_validation_metrics.json").read_text(encoding="utf-8")
        )["metrics"],
        "lightgcn": json.loads(
            (artifact_dir / "lightgcn_validation_metrics.json").read_text(encoding="utf-8")
        )["validation"]["metrics"],
    }
    full_comparisons = {
        component: {
            metric: float(full_metrics["metrics"][metric]) - float(values[metric])
            for metric in full_metrics["metrics"]
        }
        for component, values in frozen_metrics.items()
    }
    best_pairs = {}
    for omitted_index, omitted in enumerate(COMPONENTS):
        candidates = [row for row in grid_results if row["weights"][omitted] == 0]
        best_pairs[f"without_{omitted}"] = max(
            candidates,
            key=lambda row: (
                row["metrics"]["ndcg@10"], row["metrics"]["recall@10"]
            ),
        )
    singles = {
        component: next(
            row for row in grid_results
            if row["weights"][component] == 1.0
        )
        for component in COMPONENTS
    }
    config_path = artifact_dir / "hybrid_config.json"
    config_path.write_text(json.dumps({
        "schema_version": "1.0",
        "model_id": "hybrid-validation-selected-v1",
        "components": list(COMPONENTS),
        "normalization": "per-user unseen-candidate min-max to [0,1]",
        "selected_weights": dict(zip(COMPONENTS, selected_weights)),
        "weight_grid_step": 0.1,
        "score": "weighted sum of normalized component scores",
        "tie_break": "score descending, video_id ascending",
    }, indent=2) + "\n", encoding="utf-8")
    metrics = {
        "schema_version": "1.0",
        "model_id": "hybrid-validation-selected-v1",
        "selection_metric": "NDCG@10, then Recall@10; lower LightGCN weight and fewer active components break ties",
        "tuning_users": len(tuning_indices),
        "weight_grid_step": 0.1,
        "weight_combinations": len(grid_results),
        "normalization": "per-user unseen-candidate min-max to [0,1]",
        "selected_weights": dict(zip(COMPONENTS, selected_weights)),
        "tuning_grid": grid_results,
        "ablations": {
            "single_components": singles,
            "best_pairwise": best_pairs,
        },
        "full_validation": full_metrics,
        "full_validation_deltas": full_comparisons,
        "test_data_used": False,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "runtime_environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "platform": platform.platform(),
        },
    }
    metrics_path = artifact_dir / "hybrid_validation_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "model_id": metrics["model_id"],
        "validation_data_used_for_selection": True,
        "test_data_used": False,
        "component_manifests_sha256": {
            name: sha256_file(artifact_dir / filename)
            for name, filename in {
                "popularity": "popularity_manifest.json",
                "item_cf": "item_cf_manifest.json",
                "lightgcn": "lightgcn_manifest.json",
            }.items()
        },
        "artifacts_sha256": {
            path.name: sha256_file(path)
            for path in (config_path, metrics_path, predictions_path)
        },
    }
    (artifact_dir / "hybrid_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"metrics": metrics, "manifest": manifest}


def _verify_component_artifacts(artifact_dir: Path) -> None:
    manifests = (
        "popularity_manifest.json", "item_cf_manifest.json", "lightgcn_manifest.json"
    )
    for filename in manifests:
        manifest = json.loads((artifact_dir / filename).read_text(encoding="utf-8"))
        if manifest.get("test_data_used"):
            raise ValueError(f"Component used test data: {filename}")
        for artifact, expected in manifest["artifacts_sha256"].items():
            if sha256_file(artifact_dir / artifact) != expected:
                raise ValueError(f"Component checksum mismatch: {artifact}")


def _catalog(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return [int(row["video_id"]) for row in csv.DictReader(source)]


def _load_components(
    artifact_dir: Path, users: list[int], catalog: list[int]
) -> dict[str, object]:
    popularity = json.loads(
        (artifact_dir / "popularity_model.json").read_text(encoding="utf-8")
    )
    popularity_by_item = {int(row["video_id"]): float(row["score"]) for row in popularity["items"]}
    item_cf_mapping = json.loads(
        (artifact_dir / "item_cf_mapping.json").read_text(encoding="utf-8")
    )
    lightgcn_mapping = json.loads(
        (artifact_dir / "lightgcn_mapping.json").read_text(encoding="utf-8")
    )
    if item_cf_mapping["users"] != users or lightgcn_mapping["users"] != users:
        raise ValueError("Component user mappings do not match")
    if item_cf_mapping["items"] != catalog or lightgcn_mapping["items"] != catalog:
        raise ValueError("Component item mappings do not match")
    embeddings = np.load(artifact_dir / "lightgcn_embeddings.npz")
    return {
        "popularity": np.log1p(np.array([popularity_by_item[item] for item in catalog], dtype=np.float32)),
        "item_cf_similarity": sparse.load_npz(artifact_dir / "item_cf_model.npz"),
        "lightgcn_users": embeddings["user_embeddings"],
        "lightgcn_items": embeddings["item_embeddings"],
    }


def _component_scores(
    user_indices: np.ndarray,
    seen: sparse.csr_matrix,
    preferences: sparse.csr_matrix,
    data: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    similarity = data["item_cf_similarity"]
    preference_batch = preferences[user_indices]
    binary = preference_batch.copy(); binary.data[:] = 1
    numerator = (preference_batch @ similarity).toarray()
    denominator = (binary @ abs(similarity)).toarray()
    item_cf = np.divide(
        numerator, denominator, out=np.zeros_like(numerator), where=denominator != 0
    )
    popularity = np.broadcast_to(data["popularity"], item_cf.shape).copy()
    lightgcn = data["lightgcn_users"][user_indices] @ data["lightgcn_items"].T
    seen_batch = seen[user_indices]
    return tuple(
        _normalize_unseen(score.astype(np.float32, copy=False), seen_batch)
        for score in (popularity, item_cf, lightgcn)
    )


def _normalize_unseen(scores: np.ndarray, seen: sparse.csr_matrix) -> np.ndarray:
    result = scores.copy()
    for user in range(len(result)):
        start, end = seen.indptr[user:user + 2]
        seen_items = seen.indices[start:end]
        result[user, seen_items] = np.nan
        minimum = np.nanmin(result[user]); maximum = np.nanmax(result[user])
        if maximum > minimum:
            result[user] = (result[user] - minimum) / (maximum - minimum)
        else:
            result[user] = 0
        result[user, seen_items] = 0.0
    return result


def _mask_seen(scores: np.ndarray, seen: sparse.csr_matrix) -> None:
    for user in range(len(scores)):
        start, end = seen.indptr[user:user + 2]
        scores[user, seen.indices[start:end]] = -np.inf


def _evaluate_full(
    weights: tuple[float, float, float],
    users: list[int],
    catalog: list[int],
    seen: sparse.csr_matrix,
    preferences: sparse.csr_matrix,
    relevant: list[set[int]],
    data: dict[str, object],
    predictions_path: Path,
) -> dict[str, object]:
    sums = {f"{name}@{k}": 0.0 for name in ("recall", "ndcg", "precision", "hit_rate") for k in (10, 20)}
    eligible = without = 0; recommended: set[int] = set()
    with predictions_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("user_id", "rank", "video_id", "hybrid_score", "popularity_score", "item_cf_score", "lightgcn_score", "is_relevant"))
        for start in range(0, len(users), 256):
            indices = np.arange(start, min(start + 256, len(users)))
            components = _component_scores(indices, seen, preferences, data)
            combined = sum(weight * score for weight, score in zip(weights, components))
            _mask_seen(combined, seen[indices])
            batch = _evaluate_score_matrix(
                combined, seen[indices], [relevant[i] for i in indices],
                [users[i] for i in indices], catalog, writer, components,
            )
            eligible += batch["users_metric_eligible"]
            without += batch["users_without_eligible_relevant_item"]
            recommended.update(batch.pop("recommended_item_indices"))
            for name, value in batch.pop("metric_sums").items(): sums[name] += value
    return {
        "users_total": len(users), "users_metric_eligible": eligible,
        "users_without_eligible_relevant_item": without,
        "all_user_evaluation_coverage": eligible / len(users),
        "metrics": {name: value / eligible for name, value in sums.items()},
        "catalog_coverage@20": len(recommended) / len(catalog),
        "distinct_recommended_items@20": len(recommended),
        "scores_finite": True,
    }


def _evaluate_score_matrix(
    scores: np.ndarray,
    seen: sparse.csr_matrix,
    relevant: list[set[int]],
    users: list[int],
    catalog: list[int],
    predictions_path: Path | csv.writer | None,
    component_scores: tuple[np.ndarray, np.ndarray, np.ndarray] | None,
) -> dict[str, object]:
    sums = {f"{name}@{k}": 0.0 for name in ("recall", "ndcg", "precision", "hit_rate") for k in (10, 20)}
    eligible = without = 0; recommended: set[int] = set(); catalog_array = np.asarray(catalog)
    writer = predictions_path if hasattr(predictions_path, "writerow") else None
    for user in range(len(users)):
        if np.isnan(scores[user]).any() or np.isposinf(scores[user]).any():
            raise FloatingPointError("Non-finite hybrid candidate score")
        order = _top_k(scores[user], catalog_array, 20)
        recommended.update(order.tolist())
        if writer:
            for rank, item in enumerate(order, 1):
                writer.writerow((users[user], rank, catalog[item], format(float(scores[user, item]), ".9g"), *(format(float(component[user, item]), ".9g") for component in component_scores), int(item in relevant[user])))
        if not relevant[user]: without += 1; continue
        eligible += 1
        for k in (10, 20):
            hits = [int(item in relevant[user]) for item in order[:k]]; count = sum(hits)
            sums[f"recall@{k}"] += count / len(relevant[user]); sums[f"precision@{k}"] += count / k
            sums[f"hit_rate@{k}"] += float(count > 0)
            dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
            ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(relevant[user]))))
            sums[f"ndcg@{k}"] += dcg / ideal
    result = {
        "users_total": len(users), "users_metric_eligible": eligible,
        "users_without_eligible_relevant_item": without,
        "all_user_evaluation_coverage": eligible / len(users),
        "metrics": {name: value / eligible if eligible else 0 for name, value in sums.items()},
        "catalog_coverage@20": len(recommended) / len(catalog),
        "distinct_recommended_items@20": len(recommended), "scores_finite": True,
    }
    if writer:
        result["metric_sums"] = sums; result["recommended_item_indices"] = recommended
    return result


def _top_k(scores: np.ndarray, catalog: np.ndarray, k: int) -> np.ndarray:
    threshold = np.partition(scores, len(scores) - k)[len(scores) - k]
    above = np.flatnonzero(scores > threshold)
    above = above[np.lexsort((catalog[above], -scores[above]))]
    tied = np.flatnonzero(scores == threshold)
    tied = tied[np.argsort(catalog[tied], kind="stable")]
    return np.concatenate((above, tied[: k - len(above)]))


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--artifact-dir", type=Path, default=root / "model" / "artifacts")
    args = parser.parse_args(); result = tune_hybrid(args.data_dir, args.artifact_dir)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__": main()
