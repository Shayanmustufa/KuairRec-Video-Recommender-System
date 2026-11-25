"""Tune LightGCN on validation and train the selected full-data model."""

from __future__ import annotations

import argparse
from array import array
import csv
import json
import math
import os
import platform
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy import sparse
import torch

from model.src.common import repository_root, sha256_file
from model.src.lightgcn import LightGCN, _normalized_adjacency, _seed_everything

SEED = 2026
TUNING_USERS = 1024
L2_REGULARIZATION = 0.0001
CONFIGURATIONS = (
    {"learning_rate": 0.001, "layers": 2, "embedding_dim": 32, "epochs": 15},
    {"learning_rate": 0.0005, "layers": 2, "embedding_dim": 32, "epochs": 15},
    {"learning_rate": 0.002, "layers": 2, "embedding_dim": 32, "epochs": 15},
    {"learning_rate": 0.001, "layers": 1, "embedding_dim": 32, "epochs": 15},
    {"learning_rate": 0.001, "layers": 3, "embedding_dim": 32, "epochs": 15},
    {"learning_rate": 0.001, "layers": 2, "embedding_dim": 64, "epochs": 15},
    {"learning_rate": 0.001, "layers": 2, "embedding_dim": 32, "epochs": 10},
    {"learning_rate": 0.001, "layers": 2, "embedding_dim": 32, "epochs": 20},
)


def tune_and_train_lightgcn(
    data_dir: Path,
    output_dir: Path,
    configurations: tuple[dict[str, int | float], ...] = CONFIGURATIONS,
    tuning_users: int = TUNING_USERS,
    device: str | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    _seed_everything(SEED)
    split_path = data_dir / "split_manifest.json"
    split_manifest = json.loads(split_path.read_text(encoding="utf-8"))
    for name in ("train.csv", "validation.csv", "candidate_catalog.csv"):
        if sha256_file(data_dir / name) != split_manifest["sha256"][name]:
            raise ValueError(f"Input checksum mismatch: {name}")
    catalog = _catalog(data_dir / "candidate_catalog.csv")
    users, seen, positives = _training_matrices(data_dir / "train.csv", catalog)
    validation = _validation(data_dir / "validation.csv", users, catalog)
    validation = [
        items - set(seen.indices[seen.indptr[user]:seen.indptr[user + 1]])
        for user, items in enumerate(validation)
    ]
    eligible = np.array([i for i, items in enumerate(validation) if items], dtype=np.int32)
    generator = np.random.default_rng(SEED)
    tuning_indices = np.sort(generator.choice(
        eligible, size=min(tuning_users, len(eligible)), replace=False
    ))
    tuning_seen = seen[tuning_indices]
    tuning_positives = positives[tuning_indices]
    tuning_validation = [validation[index] for index in tuning_indices]

    grid: list[dict[str, object]] = []
    best_key: tuple[float, float, int, int, float, int] | None = None
    selected: dict[str, int | float] | None = None
    for config in configurations:
        losses, user_embeddings, item_embeddings = _train(
            tuning_positives, tuning_seen, config, device, SEED
        )
        evaluation = _evaluate_embeddings(
            user_embeddings,
            item_embeddings,
            tuning_seen,
            tuning_validation,
            [users[index] for index in tuning_indices],
            catalog,
            predictions_path=None,
        )
        row = {
            **config,
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "loss_finite": all(math.isfinite(value) for value in losses),
            **evaluation,
        }
        grid.append(row)
        metrics = evaluation["metrics"]
        key = (
            float(metrics["ndcg@10"]),
            float(metrics["recall@10"]),
            -int(config["embedding_dim"]),
            -int(config["layers"]),
            -float(config["learning_rate"]),
            -int(config["epochs"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            selected = dict(config)
        del user_embeddings, item_embeddings
        if device == "cuda":
            torch.cuda.empty_cache()
    assert selected is not None

    losses, user_embeddings, item_embeddings = _train(
        positives, seen, selected, device, SEED
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "lightgcn_validation_predictions.csv"
    full_evaluation = _evaluate_embeddings(
        user_embeddings,
        item_embeddings,
        seen,
        validation,
        users,
        catalog,
        predictions_path,
    )
    embeddings_path = output_dir / "lightgcn_embeddings.npz"
    np.savez_compressed(
        embeddings_path,
        user_embeddings=user_embeddings.numpy(),
        item_embeddings=item_embeddings.numpy(),
    )
    mapping_path = output_dir / "lightgcn_mapping.json"
    mapping_path.write_text(json.dumps({
        "schema_version": "1.0",
        "model_id": "lightgcn-validation-selected-v1",
        "users": users,
        "items": catalog,
        "selected_configuration": selected,
        "seed": SEED,
        "score": "dot product of propagated user and item embeddings",
        "tie_break": "score descending, video_id ascending",
    }, indent=2) + "\n", encoding="utf-8")

    baseline_metrics = {
        "popularity": json.loads(
            (output_dir / "popularity_validation_metrics.json").read_text(encoding="utf-8")
        )["metrics"],
        "item_cf": json.loads(
            (output_dir / "item_cf_validation_metrics.json").read_text(encoding="utf-8")
        )["metrics"],
    }
    comparisons = {
        baseline: {
            metric: float(full_evaluation["metrics"][metric]) - float(values[metric])
            for metric in full_evaluation["metrics"]
        }
        for baseline, values in baseline_metrics.items()
    }
    metrics = {
        "schema_version": "1.0",
        "model_id": "lightgcn-validation-selected-v1",
        "selection_metric": "NDCG@10, then Recall@10; simpler configuration breaks ties",
        "tuning_protocol": (
            "fixed one-factor grid on a seed-2026 sample of validation-eligible users"
        ),
        "tuning_users": len(tuning_indices),
        "tuning_grid": grid,
        "selected_configuration": selected,
        "full_training": {
            "users": len(users),
            "items": len(catalog),
            "positive_edges": int(positives.nnz),
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "loss_by_epoch": losses,
            "finite": all(math.isfinite(value) for value in losses),
        },
        "validation": full_evaluation,
        "comparison_deltas": comparisons,
        "test_data_used": False,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "runtime_environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": device,
            "device_name": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
            "platform": platform.platform(),
        },
    }
    metrics_path = output_dir / "lightgcn_validation_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    artifact_paths = (embeddings_path, mapping_path, predictions_path, metrics_path)
    manifest = {
        "schema_version": "1.0",
        "model_id": metrics["model_id"],
        "validation_data_used_for_selection": True,
        "test_data_used": False,
        "split_manifest_sha256": sha256_file(split_path),
        "artifacts_sha256": {path.name: sha256_file(path) for path in artifact_paths},
    }
    (output_dir / "lightgcn_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"metrics": metrics, "manifest": manifest}


def _catalog(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return [int(row["video_id"]) for row in csv.DictReader(source)]


def _training_matrices(
    path: Path, catalog: list[int]
) -> tuple[list[int], sparse.csr_matrix, sparse.csr_matrix]:
    item_index = {item: index for index, item in enumerate(catalog)}
    users: list[int] = []
    user_index: dict[int, int] = {}
    seen_rows, seen_columns = array("I"), array("I")
    positive_sets: list[set[int]] = []
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            user = int(row["user_id"])
            if user not in user_index:
                user_index[user] = len(users)
                users.append(user)
                positive_sets.append(set())
            u = user_index[user]
            item = item_index[int(row["video_id"])]
            seen_rows.append(u)
            seen_columns.append(item)
            if row["is_relevant"] == "1":
                positive_sets[u].add(item)
    shape = (len(users), len(catalog))
    seen = sparse.coo_matrix((
        np.ones(len(seen_rows), dtype=np.float32),
        (np.frombuffer(seen_rows, dtype=np.uint32), np.frombuffer(seen_columns, dtype=np.uint32)),
    ), shape=shape).tocsr()
    seen.data[:] = 1
    positive_rows, positive_columns = zip(*(
        (user, item) for user, items in enumerate(positive_sets) for item in sorted(items)
    ))
    positives = sparse.csr_matrix((
        np.ones(len(positive_rows), dtype=np.float32),
        (positive_rows, positive_columns),
    ), shape=shape)
    return users, seen, positives


def _validation(path: Path, users: list[int], catalog: list[int]) -> list[set[int]]:
    user_index = {user: index for index, user in enumerate(users)}
    item_index = {item: index for index, item in enumerate(catalog)}
    result = [set() for _ in users]
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["is_relevant"] == "1":
                result[user_index[int(row["user_id"])]].add(item_index[int(row["video_id"])])
    return result


def _train(
    positives: sparse.csr_matrix,
    seen: sparse.csr_matrix,
    config: dict[str, int | float],
    device: str,
    seed: int,
) -> tuple[list[float], torch.Tensor, torch.Tensor]:
    _seed_everything(seed)
    users_count, items_count = positives.shape
    rows, columns = positives.nonzero()
    edges = list(zip(rows.tolist(), columns.tolist()))
    adjacency = _normalized_adjacency(users_count, items_count, edges).to(device)
    model = LightGCN(
        users_count, items_count, int(config["embedding_dim"]), int(config["layers"])
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["learning_rate"]))
    user_tensor = torch.tensor(rows, dtype=torch.long, device=device)
    positive_tensor = torch.tensor(columns, dtype=torch.long, device=device)
    generator = np.random.default_rng(seed)
    losses: list[float] = []
    for _ in range(int(config["epochs"])):
        negatives = generator.integers(0, items_count, size=len(rows), dtype=np.int64)
        for index, user in enumerate(rows):
            start, end = seen.indptr[user:user + 2]
            user_seen = seen.indices[start:end]
            while np.searchsorted(user_seen, negatives[index]) < len(user_seen) and user_seen[np.searchsorted(user_seen, negatives[index])] == negatives[index]:
                negatives[index] = generator.integers(0, items_count)
        negative_tensor = torch.tensor(negatives, dtype=torch.long, device=device)
        optimizer.zero_grad()
        propagated_users, propagated_items = model.propagate(adjacency)
        user_vectors = propagated_users[user_tensor]
        positive_vectors = propagated_items[positive_tensor]
        negative_vectors = propagated_items[negative_tensor]
        loss = -torch.nn.functional.logsigmoid(
            (user_vectors * positive_vectors).sum(1) - (user_vectors * negative_vectors).sum(1)
        ).mean()
        regularization = (
            model.user_embedding(user_tensor).pow(2).sum()
            + model.item_embedding(positive_tensor).pow(2).sum()
            + model.item_embedding(negative_tensor).pow(2).sum()
        ) / len(rows)
        loss = loss + L2_REGULARIZATION * regularization
        if not torch.isfinite(loss):
            raise FloatingPointError("Non-finite LightGCN loss")
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    model.eval()
    with torch.no_grad():
        final_users, final_items = model.propagate(adjacency)
    if not torch.isfinite(final_users).all() or not torch.isfinite(final_items).all():
        raise FloatingPointError("Non-finite LightGCN embeddings")
    return losses, final_users.cpu(), final_items.cpu()


def _evaluate_embeddings(
    user_embeddings: torch.Tensor,
    item_embeddings: torch.Tensor,
    seen: sparse.csr_matrix,
    relevant: list[set[int]],
    users: list[int],
    catalog: list[int],
    predictions_path: Path | None,
) -> dict[str, object]:
    metric_names = ("recall", "ndcg", "precision", "hit_rate")
    sums = {f"{name}@{k}": 0.0 for name in metric_names for k in (10, 20)}
    eligible = without = 0
    recommended: set[int] = set()
    target = predictions_path.open("w", encoding="utf-8", newline="") if predictions_path else None
    writer = csv.writer(target) if target else None
    if writer:
        writer.writerow(("user_id", "rank", "video_id", "score", "is_relevant"))
    catalog_array = np.asarray(catalog)
    try:
        for start_user in range(0, len(users), 256):
            end_user = min(len(users), start_user + 256)
            scores = (user_embeddings[start_user:end_user] @ item_embeddings.T).numpy()
            if not np.isfinite(scores).all():
                raise FloatingPointError("Non-finite LightGCN validation scores")
            for local, user_index in enumerate(range(start_user, end_user)):
                begin, end = seen.indptr[user_index:user_index + 2]
                scores[local, seen.indices[begin:end]] = -np.inf
                order = np.lexsort((catalog_array, -scores[local]))[:20]
                recommended.update(order.tolist())
                eligible_relevant = relevant[user_index]
                if writer:
                    for rank, item in enumerate(order, 1):
                        writer.writerow((users[user_index], rank, catalog[item], format(float(scores[local, item]), ".9g"), int(item in eligible_relevant)))
                if not eligible_relevant:
                    without += 1
                    continue
                eligible += 1
                for k in (10, 20):
                    hits = [int(item in eligible_relevant) for item in order[:k]]
                    count = sum(hits)
                    sums[f"recall@{k}"] += count / len(eligible_relevant)
                    sums[f"precision@{k}"] += count / k
                    sums[f"hit_rate@{k}"] += float(count > 0)
                    dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
                    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(eligible_relevant))))
                    sums[f"ndcg@{k}"] += dcg / ideal
    finally:
        if target:
            target.close()
    return {
        "users_total": len(users),
        "users_metric_eligible": eligible,
        "users_without_eligible_relevant_item": without,
        "all_user_evaluation_coverage": eligible / len(users),
        "metrics": {name: value / eligible if eligible else 0 for name, value in sums.items()},
        "catalog_coverage@20": len(recommended) / len(catalog),
        "distinct_recommended_items@20": len(recommended),
        "scores_finite": True,
    }


def main() -> None:
    root = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--output-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--device", choices=("cpu", "cuda"), default=None)
    args = parser.parse_args()
    result = tune_and_train_lightgcn(args.data_dir, args.output_dir, device=args.device)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
