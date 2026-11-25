"""Run the frozen Day 6 LightGCN debugging prototype."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from model.src.common import repository_root, sha256_file


@dataclass(frozen=True)
class LightGCNConfig:
    seed: int = 2026
    sample_users: int = 256
    embedding_dim: int = 32
    layers: int = 2
    learning_rate: float = 0.001
    l2_regularization: float = 0.0001
    epochs: int = 10
    top_k: int = 20
    device: str = "cpu"


class LightGCN(nn.Module):
    def __init__(self, users: int, items: int, dimension: int, layers: int) -> None:
        super().__init__()
        self.user_embedding = nn.Embedding(users, dimension)
        self.item_embedding = nn.Embedding(items, dimension)
        self.layers = layers
        nn.init.normal_(self.user_embedding.weight, std=0.1)
        nn.init.normal_(self.item_embedding.weight, std=0.1)

    def propagate(self, adjacency: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        combined = torch.cat((self.user_embedding.weight, self.item_embedding.weight))
        states = [combined]
        for _ in range(self.layers):
            combined = torch.sparse.mm(adjacency, combined)
            states.append(combined)
        result = torch.stack(states).mean(dim=0)
        return result[: self.user_embedding.num_embeddings], result[self.user_embedding.num_embeddings :]


def run_lightgcn_prototype(
    data_dir: Path,
    output_dir: Path,
    config: LightGCNConfig = LightGCNConfig(),
) -> dict[str, object]:
    started = time.perf_counter()
    _seed_everything(config.seed)
    if config.device != "cpu":
        raise ValueError("Day 6 prototype is frozen to CPU for reproducibility")
    split_manifest_path = data_dir / "split_manifest.json"
    split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    for filename in ("train.csv", "validation.csv", "candidate_catalog.csv"):
        if sha256_file(data_dir / filename) != split_manifest["sha256"][filename]:
            raise ValueError(f"Input checksum mismatch: {filename}")

    catalog = _read_catalog(data_dir / "candidate_catalog.csv")
    item_to_index = {item: index for index, item in enumerate(catalog)}
    validation_all = _read_relevant_validation(data_dir / "validation.csv", item_to_index)
    eligible_users = sorted(user for user, items in validation_all.items() if items)
    generator = np.random.default_rng(config.seed)
    sampled_users = sorted(generator.choice(
        eligible_users, size=min(config.sample_users, len(eligible_users)), replace=False
    ).tolist())
    user_to_index = {user: index for index, user in enumerate(sampled_users)}
    seen, positive_edges = _read_positive_training(
        data_dir / "train.csv", user_to_index, item_to_index
    )
    active_users = [user for user in sampled_users if seen[user_to_index[user]]]
    if len(active_users) != len(sampled_users):
        sampled_users = active_users
        user_to_index = {user: index for index, user in enumerate(sampled_users)}
        seen, positive_edges = _read_positive_training(
            data_dir / "train.csv", user_to_index, item_to_index
        )
    validation = [validation_all[user] - seen[index] for index, user in enumerate(sampled_users)]
    adjacency = _normalized_adjacency(len(sampled_users), len(catalog), positive_edges)
    model = LightGCN(
        len(sampled_users), len(catalog), config.embedding_dim, config.layers
    ).to(config.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    users_tensor = torch.tensor([edge[0] for edge in positive_edges], dtype=torch.long)
    positives_tensor = torch.tensor([edge[1] for edge in positive_edges], dtype=torch.long)
    losses: list[float] = []
    for _ in range(config.epochs):
        negatives_tensor = _sample_negatives(seen, len(catalog), users_tensor, generator)
        optimizer.zero_grad()
        propagated_users, propagated_items = model.propagate(adjacency)
        user_vectors = propagated_users[users_tensor]
        positive_vectors = propagated_items[positives_tensor]
        negative_vectors = propagated_items[negatives_tensor]
        positive_scores = (user_vectors * positive_vectors).sum(dim=1)
        negative_scores = (user_vectors * negative_vectors).sum(dim=1)
        ranking_loss = -torch.nn.functional.logsigmoid(positive_scores - negative_scores).mean()
        regularization = (
            model.user_embedding(users_tensor).pow(2).sum()
            + model.item_embedding(positives_tensor).pow(2).sum()
            + model.item_embedding(negatives_tensor).pow(2).sum()
        ) / len(positive_edges)
        loss = ranking_loss + config.l2_regularization * regularization
        if not torch.isfinite(loss):
            raise FloatingPointError("LightGCN produced a non-finite training loss")
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))

    model.eval()
    with torch.no_grad():
        user_embeddings, item_embeddings = model.propagate(adjacency)
    if not torch.isfinite(user_embeddings).all() or not torch.isfinite(item_embeddings).all():
        raise FloatingPointError("LightGCN produced non-finite embeddings")
    predictions_path = output_dir / "lightgcn_debug_validation_predictions.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation = _evaluate(
        sampled_users,
        seen,
        validation,
        user_embeddings,
        item_embeddings,
        catalog,
        predictions_path,
        config.top_k,
    )
    checkpoint_path = output_dir / "lightgcn_debug_checkpoint.pt"
    torch.save({
        "schema_version": "1.0",
        "model_id": "lightgcn-debug-v1",
        "config": asdict(config),
        "sampled_users": sampled_users,
        "catalog": catalog,
        "state_dict": model.state_dict(),
    }, checkpoint_path)
    metrics = {
        "schema_version": "1.0",
        "model_id": "lightgcn-debug-v1",
        "purpose": "Day 6 debugging prototype; not a selected production model",
        "config": asdict(config),
        "sample": {
            "users": len(sampled_users),
            "catalog_items": len(catalog),
            "positive_training_edges": len(positive_edges),
            "selection": "seeded sample from validation-eligible users",
        },
        "training": {
            "loss_by_epoch": losses,
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "loss_finite": all(math.isfinite(value) for value in losses),
            "embeddings_finite": True,
        },
        "debug_validation": evaluation,
        "test_data_used": False,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "runtime_environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": config.device,
            "platform": platform.platform(),
        },
    }
    metrics_path = output_dir / "lightgcn_debug_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "model_id": "lightgcn-debug-v1",
        "test_data_used": False,
        "split_manifest_sha256": sha256_file(split_manifest_path),
        "artifacts_sha256": {
            path.name: sha256_file(path)
            for path in (checkpoint_path, metrics_path, predictions_path)
        },
    }
    (output_dir / "lightgcn_debug_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"metrics": metrics, "manifest": manifest}


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def _read_catalog(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return [int(row["video_id"]) for row in csv.DictReader(source)]


def _read_relevant_validation(
    path: Path, item_to_index: dict[int, int]
) -> dict[int, set[int]]:
    relevant: dict[int, set[int]] = {}
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            user = int(row["user_id"])
            relevant.setdefault(user, set())
            if row["is_relevant"] == "1":
                relevant[user].add(item_to_index[int(row["video_id"])])
    return relevant


def _read_positive_training(
    path: Path,
    user_to_index: dict[int, int],
    item_to_index: dict[int, int],
) -> tuple[list[set[int]], list[tuple[int, int]]]:
    seen = [set() for _ in user_to_index]
    positives = [set() for _ in user_to_index]
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            user = int(row["user_id"])
            if user not in user_to_index:
                continue
            user_index = user_to_index[user]
            item_index = item_to_index[int(row["video_id"])]
            seen[user_index].add(item_index)
            if row["is_relevant"] == "1":
                positives[user_index].add(item_index)
    edges = [(user, item) for user, items in enumerate(positives) for item in sorted(items)]
    if not edges:
        raise ValueError("Debug sample has no positive training edges")
    return seen, edges


def _normalized_adjacency(
    users: int, items: int, edges: list[tuple[int, int]]
) -> torch.Tensor:
    user_nodes = np.array([edge[0] for edge in edges], dtype=np.int64)
    item_nodes = np.array([users + edge[1] for edge in edges], dtype=np.int64)
    sources = np.concatenate((user_nodes, item_nodes))
    targets = np.concatenate((item_nodes, user_nodes))
    degrees = np.bincount(sources, minlength=users + items).astype(np.float32)
    weights = 1.0 / np.sqrt(degrees[sources] * degrees[targets])
    indices = torch.tensor(np.vstack((sources, targets)), dtype=torch.long)
    return torch.sparse_coo_tensor(
        indices, torch.tensor(weights), (users + items, users + items)
    ).coalesce()


def _sample_negatives(
    seen: list[set[int]],
    item_count: int,
    users: torch.Tensor,
    generator: np.random.Generator,
) -> torch.Tensor:
    negatives = generator.integers(0, item_count, size=len(users), dtype=np.int64)
    for index, user in enumerate(users.tolist()):
        while int(negatives[index]) in seen[user]:
            negatives[index] = generator.integers(0, item_count)
    return torch.tensor(negatives, dtype=torch.long)


def _evaluate(
    users: list[int],
    seen: list[set[int]],
    relevant: list[set[int]],
    user_embeddings: torch.Tensor,
    item_embeddings: torch.Tensor,
    catalog: list[int],
    predictions_path: Path,
    top_k: int,
) -> dict[str, object]:
    sums = {"recall@10": 0.0, "recall@20": 0.0, "ndcg@10": 0.0, "ndcg@20": 0.0}
    eligible = without = 0
    recommended: set[int] = set()
    with predictions_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("user_id", "rank", "video_id", "score", "is_relevant"))
        for user_index, user in enumerate(users):
            scores = torch.mv(item_embeddings, user_embeddings[user_index]).clone()
            scores[list(seen[user_index])] = -torch.inf
            score_values = scores.numpy()
            order = np.lexsort((np.asarray(catalog), -score_values))[:top_k].tolist()
            recommended.update(order)
            eligible_relevant = relevant[user_index]
            for rank, item in enumerate(order, 1):
                writer.writerow((user, rank, catalog[item], format(float(scores[item]), ".9g"), int(item in eligible_relevant)))
            if not eligible_relevant:
                without += 1
                continue
            eligible += 1
            for k in (10, 20):
                hits = [int(item in eligible_relevant) for item in order[:k]]
                sums[f"recall@{k}"] += sum(hits) / len(eligible_relevant)
                dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
                ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(eligible_relevant))))
                sums[f"ndcg@{k}"] += dcg / ideal
    return {
        "users_total": len(users),
        "users_metric_eligible": eligible,
        "users_without_eligible_relevant_item": without,
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
    args = parser.parse_args()
    result = run_lightgcn_prototype(args.data_dir, args.output_dir)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
