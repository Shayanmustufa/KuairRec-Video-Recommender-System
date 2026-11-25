"""Analyze frozen-test failures, concentration, cold start, and metric stability."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import random
from statistics import mean

from model.src.common import repository_root, sha256_file


METRICS = ("recall@10", "recall@20", "ndcg@10", "ndcg@20", "precision@10", "precision@20", "hit_rate@10", "hit_rate@20")


def _group_events(path: Path):
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        current = None; items: set[int] = set(); relevant: set[int] = set(); has_positive = False
        for row in reader:
            user = int(row["user_id"])
            if current is not None and user != current:
                yield current, items, relevant, has_positive
                items = set(); relevant = set(); has_positive = False
            current = user
            item = int(row["video_id"]); items.add(item)
            if int(row["is_relevant"]):
                relevant.add(item); has_positive = True
        if current is not None:
            yield current, items, relevant, has_positive


def _relevance_and_fallback_users(history_path: Path, test_path: Path, catalog: set[int]):
    history = iter(_group_events(history_path)); test = iter(_group_events(test_path))
    history_row = next(history, None); test_row = next(test, None)
    relevant_counts: dict[int, int] = {}; fallback_seen: dict[int, set[int]] = {}
    while history_row is not None or test_row is not None:
        users = [row[0] for row in (history_row, test_row) if row is not None]
        user = min(users); seen: set[int] = set(); relevant: set[int] = set(); has_positive = False
        if history_row is not None and history_row[0] == user:
            _, seen, _, has_positive = history_row; history_row = next(history, None)
        if test_row is not None and test_row[0] == user:
            _, _, relevant, _ = test_row; test_row = next(test, None)
        relevant_counts[user] = len((relevant & catalog) - seen)
        if not has_positive:
            fallback_seen[user] = seen
    return relevant_counts, fallback_seen


def _user_metrics(hits: list[int], relevant_count: int) -> dict[str, float]:
    result: dict[str, float] = {}
    for k in (10, 20):
        selected = hits[:k]; found = sum(selected)
        result[f"recall@{k}"] = found / relevant_count
        result[f"precision@{k}"] = found / k
        result[f"hit_rate@{k}"] = float(found > 0)
        dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(selected))
        ideal = sum(1 / math.log2(rank + 2) for rank in range(min(relevant_count, k)))
        result[f"ndcg@{k}"] = dcg / ideal if ideal else 0.0
    return result


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values); position = (len(ordered) - 1) * fraction
    lower = math.floor(position); upper = math.ceil(position)
    if lower == upper: return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _bootstrap(rows: list[dict[str, float]], seeds: tuple[int, ...], samples: int) -> dict[str, object]:
    by_seed: dict[str, dict[str, dict[str, float]]] = {}
    for seed in seeds:
        generator = random.Random(seed); distributions = {metric: [] for metric in METRICS}
        for _ in range(samples):
            selected = [rows[generator.randrange(len(rows))] for _ in range(len(rows))]
            for metric in METRICS: distributions[metric].append(mean(row[metric] for row in selected))
        by_seed[str(seed)] = {
            metric: {"mean": mean(values), "p2.5": _percentile(values, .025), "p97.5": _percentile(values, .975)}
            for metric, values in distributions.items()
        }
    spread = {
        metric: max(by_seed[str(seed)][metric]["mean"] for seed in seeds) - min(by_seed[str(seed)][metric]["mean"] for seed in seeds)
        for metric in METRICS
    }
    return {"method": "user-level bootstrap of frozen test users", "seeds": list(seeds), "resamples_per_seed": samples, "by_seed": by_seed, "max_seed_mean_spread": spread}


def analyze_day13(data_dir: Path, artifact_dir: Path, bootstrap_samples: int = 200) -> dict[str, object]:
    controlled = json.loads((artifact_dir / "controlled_test_metrics.json").read_text(encoding="utf-8"))
    popularity = json.loads((artifact_dir / "popularity_model.json").read_text(encoding="utf-8"))
    catalog = {int(row["video_id"]) for row in csv.DictReader((data_dir / "candidate_catalog.csv").open(newline="", encoding="utf-8"))}
    relevant_counts, fallback_seen = _relevance_and_fallback_users(data_dir / "user_history_test.csv", data_dir / "test.csv", catalog)
    popularity_order = [int(row["video_id"]) for row in popularity["items"]]
    popularity_rank = {item: rank for rank, item in enumerate(popularity_order, 1)}
    top_decile = math.ceil(len(popularity_order) * .10)
    exposures: Counter[int] = Counter(); user_rows: list[dict[str, float]] = []
    observed: dict[int, list[int]] = {}; duplicate_count = 0; total = top_decile_count = rank_one_top_decile = 0
    with (artifact_dir / "controlled_test_predictions.csv").open(newline="", encoding="utf-8") as source:
        current = None; hits: list[int] = []; items: list[int] = []
        for row in csv.DictReader(source):
            user = int(row["user_id"])
            if current is not None and user != current:
                if relevant_counts[current] > 0: user_rows.append(_user_metrics(hits, relevant_counts[current]))
                observed[current] = items; hits = []; items = []
            current = user; item = int(row["video_id"]); rank = int(row["rank"])
            if item in items: duplicate_count += 1
            items.append(item); hits.append(int(row["is_relevant"])); exposures[item] += 1; total += 1
            if popularity_rank[item] <= top_decile:
                top_decile_count += 1
                if rank == 1: rank_one_top_decile += 1
        if current is not None:
            if relevant_counts[current] > 0: user_rows.append(_user_metrics(hits, relevant_counts[current]))
            observed[current] = items
    fallback_mismatches = []
    for user, seen in fallback_seen.items():
        expected = [item for item in popularity_order if item not in seen][:20]
        if observed.get(user) != expected: fallback_mismatches.append(user)
    eligible = len(user_rows); no_hit_10 = sum(row["hit_rate@10"] == 0 for row in user_rows); no_hit_20 = sum(row["hit_rate@20"] == 0 for row in user_rows)
    exposure_values = sorted(exposures.values(), reverse=True); one_percent_items = max(1, math.ceil(len(catalog) * .01))
    failures = [
        {"failure": "no eligible relevant test candidate", "users": sum(count == 0 for count in relevant_counts.values()), "rate": sum(count == 0 for count in relevant_counts.values()) / len(relevant_counts), "interpretation": "not scorable under the declared denominator policy"},
        {"failure": "no relevant recommendation in top 10", "users": no_hit_10, "rate": no_hit_10 / eligible, "interpretation": "primary-ranking miss among metric-eligible users"},
        {"failure": "no relevant recommendation in top 20", "users": no_hit_20, "rate": no_hit_20 / eligible, "interpretation": "ranking miss persists at secondary cutoff"},
        {"failure": "no positive pre-test history", "users": len(fallback_seen), "rate": len(fallback_seen) / len(relevant_counts), "interpretation": "served by deterministic popularity fallback"},
        {"failure": "duplicate recommendation", "users": duplicate_count, "rate": duplicate_count / total, "interpretation": "recommendation-row defect count; expected zero"},
        {"failure": "seen-item recommendation", "users": controlled["behavior_checks"]["seen_item_violations"], "rate": controlled["behavior_checks"]["seen_item_violations"] / total, "interpretation": "independently guarded during controlled evaluation; expected zero"},
    ]
    report = {
        "schema_version": "1.0", "analysis_type": "post-test_diagnostic_no_model_selection",
        "selection_reopened": False, "controlled_test_rerun": False,
        "failure_table": failures,
        "cold_start": {"users_without_positive_pretest_history": len(fallback_seen), "fallback_matches_frozen_popularity": not fallback_mismatches, "mismatched_user_ids": fallback_mismatches},
        "popularity_dominance": {"top_popularity_decile_rank_threshold": top_decile, "recommendation_share_from_top_popularity_decile": top_decile_count / total, "rank_1_share_from_top_popularity_decile": rank_one_top_decile / len(relevant_counts), "top_1_percent_catalog_exposure_share": sum(exposure_values[:one_percent_items]) / total, "distinct_recommended_items": len(exposures), "catalog_coverage@20": len(exposures) / len(catalog)},
        "stability": _bootstrap(user_rows, (2026, 2027, 2028), bootstrap_samples),
        "limitations": ["bootstrap seeds quantify sampling uncertainty; they are not independent retraining seeds", "popularity exposure concentration can reinforce exposure bias", "users without eligible positives are excluded from ranking-metric means", "demographic, creator, category, temporal-drift, and content-safety fairness remain unmeasured", "offline relevance is a watch-ratio proxy and does not establish satisfaction"],
        "inputs_sha256": {name: sha256_file(path) for name, path in {"controlled_test_predictions.csv": artifact_dir / "controlled_test_predictions.csv", "controlled_test_metrics.json": artifact_dir / "controlled_test_metrics.json", "popularity_model.json": artifact_dir / "popularity_model.json", "test.csv": data_dir / "test.csv", "user_history_test.csv": data_dir / "user_history_test.csv"}.items()},
    }
    (artifact_dir / "day13_failure_analysis.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (artifact_dir / "day13_failure_table.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=("failure", "users", "rate", "interpretation")); writer.writeheader(); writer.writerows(failures)
    return report


def main() -> None:
    root = repository_root(); parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--artifact-dir", type=Path, default=root / "model" / "artifacts")
    parser.add_argument("--bootstrap-samples", type=int, default=200)
    args = parser.parse_args(); report = analyze_day13(args.data_dir, args.artifact_dir, args.bootstrap_samples)
    print(json.dumps({"failures": report["failure_table"], "cold_start": report["cold_start"], "popularity_dominance": report["popularity_dominance"], "max_seed_mean_spread": report["stability"]["max_seed_mean_spread"]}, indent=2))


if __name__ == "__main__": main()
