"""Stream and audit the official KuaiRec release without loading it into RAM."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from model.src.common import (
    DatasetError,
    INTERACTION_COLUMNS,
    interaction_path,
    open_interactions,
    repository_root,
)

ZENODO_RECORD = "https://zenodo.org/records/18164998"
REPOSITORY = "https://github.com/chongminggao/KuaiRec"
RESERVOIR_SIZE = 100_000
SEED = 2026


def audit_interactions(path: Path) -> dict[str, object]:
    """Collect exact counts and deterministic sampled engagement statistics."""
    temporary_directory = tempfile.TemporaryDirectory(prefix="kuairec-audit-")
    connection = sqlite3.connect(Path(temporary_directory.name) / "event_keys.sqlite")
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA cache_size=-262144")
    connection.execute(
        "CREATE TABLE event_keys (user_id INTEGER, video_id INTEGER, "
        "timestamp_key TEXT, signature TEXT, conflicting_duplicate INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (user_id, video_id, timestamp_key)) WITHOUT ROWID"
    )
    users: set[int] = set()
    videos: set[int] = set()
    missing = Counter()
    reservoir: list[float] = []
    sample_records: list[dict[str, int | float | None]] = []
    rng = random.Random(SEED)
    timestamp_min: float | None = None
    timestamp_max: float | None = None
    raw_rows = 0
    valid_rows = 0
    invalid_rows = 0
    timestamp_incomplete_rows = 0
    timestamp_parse_errors = 0
    relevant_rows = 0
    batch: list[tuple[int, int, str, str]] = []
    source, reader = open_interactions(path)
    try:
        for raw_row in reader:
            raw_rows += 1
            row = {name: raw_row.get(name) for name in INTERACTION_COLUMNS}
            for name, value in row.items():
                if value is None or not value.strip():
                    missing[name] += 1
            try:
                user_id = int(row["user_id"] or "")
                video_id = int(row["video_id"] or "")
                ratio = float(row["watch_ratio"] or "")
            except (TypeError, ValueError):
                invalid_rows += 1
                continue
            if user_id < 0 or video_id < 0 or not math.isfinite(ratio):
                invalid_rows += 1
                continue
            timestamp_value = row["timestamp"]
            timestamp: float | None = None
            if timestamp_value is None or not timestamp_value.strip():
                timestamp_incomplete_rows += 1
                timestamp_key = "NO_TIMESTAMP"
            else:
                try:
                    parsed_timestamp = float(timestamp_value)
                    if not math.isfinite(parsed_timestamp):
                        raise ValueError("timestamp must be finite")
                    timestamp = parsed_timestamp
                    timestamp_key = format(timestamp, ".15g")
                except ValueError:
                    timestamp_incomplete_rows += 1
                    timestamp_parse_errors += 1
                    timestamp_key = f"INVALID:{timestamp_value}"
            users.add(user_id)
            videos.add(video_id)
            if timestamp is not None:
                timestamp_min = timestamp if timestamp_min is None else min(timestamp_min, timestamp)
                timestamp_max = timestamp if timestamp_max is None else max(timestamp_max, timestamp)
            valid_rows += 1
            relevant_rows += int(ratio > 2.0)
            if len(sample_records) < 10:
                sample_records.append({
                    "user_id": user_id,
                    "video_id": video_id,
                    "timestamp": timestamp,
                    "watch_ratio": ratio,
                })
            signature = "|".join(
                (
                    format(ratio, ".15g")
                    if name == "watch_ratio"
                    else str(row.get(name, "") or "")
                )
                for name in ("play_duration", "video_duration", "watch_ratio")
            )
            batch.append((user_id, video_id, timestamp_key, signature))
            if len(batch) >= 20_000:
                _insert_event_keys(connection, batch)
                batch.clear()
            if len(reservoir) < RESERVOIR_SIZE:
                reservoir.append(ratio)
            else:
                position = rng.randrange(valid_rows)
                if position < RESERVOIR_SIZE:
                    reservoir[position] = ratio
        if batch:
            _insert_event_keys(connection, batch)
            batch.clear()
        connection.commit()
    finally:
        source.close()

    unique_count = connection.execute("SELECT COUNT(*) FROM event_keys").fetchone()[0]
    conflicting_keys = connection.execute(
        "SELECT COUNT(*) FROM event_keys WHERE conflicting_duplicate=1"
    ).fetchone()[0]
    connection.close()
    temporary_directory.cleanup()

    reservoir.sort()
    return {
        "file": path.name,
        "columns": reader.fieldnames,
        "raw_interactions": raw_rows,
        "valid_interactions": valid_rows,
        "invalid_interactions": invalid_rows,
        "timestamp_incomplete_interactions": timestamp_incomplete_rows,
        "timestamp_parse_errors": timestamp_parse_errors,
        "unique_interactions": unique_count,
        "duplicate_user_video_timestamp_rows": valid_rows - unique_count,
        "conflicting_duplicate_event_keys": conflicting_keys,
        "unique_users": len(users),
        "unique_videos": len(videos),
        "timestamp_min_unix": timestamp_min,
        "timestamp_max_unix": timestamp_max,
        "timestamp_min_utc": _utc(timestamp_min),
        "timestamp_max_utc": _utc(timestamp_max),
        "positive_events_watch_ratio_gt_2": relevant_rows,
        "missing_values_by_column": dict(sorted(missing.items())),
        "sample_records_first_10_valid_rows": sample_records,
        "watch_ratio": _sample_distribution(reservoir),
    }


def _insert_event_keys(
    connection: sqlite3.Connection,
    batch: list[tuple[int, int, str, str]],
) -> None:
    connection.executemany(
        "INSERT INTO event_keys (user_id, video_id, timestamp_key, signature) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, video_id, timestamp_key) DO UPDATE SET "
        "conflicting_duplicate=MAX(event_keys.conflicting_duplicate, "
        "event_keys.signature != excluded.signature)",
        batch,
    )


def audit_metadata(data_dir: Path) -> dict[str, object]:
    """Summarize official item category and social-network CSVs when present."""
    metadata: dict[str, object] = {}
    item_categories = _find_file(data_dir, "item_categories.csv")
    if item_categories:
        category_counts: Counter[str] = Counter()
        item_count = 0
        malformed = 0
        with item_categories.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or not {"video_id", "feat"} <= set(reader.fieldnames):
                raise DatasetError(f"{item_categories} must contain video_id and feat")
            for row in reader:
                item_count += 1
                try:
                    features = json.loads(row["feat"]) if row["feat"].startswith("[") else []
                    category_counts.update(str(feature) for feature in features)
                except (json.JSONDecodeError, TypeError):
                    malformed += 1
        metadata["item_categories"] = {
            "metadata_rows": item_count,
            "distinct_category_ids": len(category_counts),
            "category_tag_counts": dict(sorted(category_counts.items())),
            "malformed_feature_rows": malformed,
        }

    social_network = _find_file(data_dir, "social_network.csv")
    if social_network:
        rows = 0
        links = 0
        users: set[int] = set()
        malformed = 0
        with social_network.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or not {"user_id", "friend_list"} <= set(reader.fieldnames):
                raise DatasetError(f"{social_network} must contain user_id and friend_list")
            for row in reader:
                rows += 1
                try:
                    user_id = int(row["user_id"])
                    friends = json.loads(row["friend_list"])
                    if not isinstance(friends, list):
                        raise ValueError("friend_list is not a list")
                    users.add(user_id)
                    links += len(friends)
                except (TypeError, ValueError, json.JSONDecodeError):
                    malformed += 1
        metadata["social_network"] = {
            "rows": rows,
            "users": len(users),
            "directed_friend_entries": links,
            "malformed_rows": malformed,
        }
    return metadata


def create_report(data_dir: Path) -> dict[str, object]:
    big_matrix = interaction_path(data_dir, "big_matrix.csv")
    small_matrix = interaction_path(data_dir, "small_matrix.csv")
    big_stats = audit_interactions(big_matrix)
    small_stats = audit_interactions(small_matrix)
    official_reference = {
        "big_matrix": {
            "users": 7176,
            "videos": 10728,
            "interactions": 12530806,
        },
        "small_matrix": {
            "users": 1411,
            "videos": 3327,
            "interactions": 4676570,
        },
    }
    return {
        "dataset": {
            "name": "KuaiRec Dataset with Raw Features",
            "version": "KuaiRec 2.0; Zenodo record 18164998",
            "record_doi": "10.5281/zenodo.18164998",
            "license_note": (
                "The GitHub repository LICENSE is CC BY-SA 4.0; the Zenodo "
                "record metadata says CC BY 4.0. Treat as CC BY-SA 4.0 pending "
                "clarification."
            ),
            "interaction_source": "big_matrix.csv only",
            "small_matrix_policy": (
                "Audited separately; not concatenated with big_matrix.csv or "
                "used as an independent ratings test."
            ),
            "official_reference_statistics": {
                "big_matrix": {**official_reference["big_matrix"], "density_percent": 16.3},
                "small_matrix": {**official_reference["small_matrix"], "density_percent": 99.6},
                "note": "Published figures are reference values; compare with the audited release.",
            },
            "target": "watch_ratio > 2.0 (official README example; fixed before evaluation)",
            "eligibility": "Iterative user-item 5-core over deduplicated big_matrix.csv",
            "duplicate_policy": (
                "A repeated (user_id, video_id, timestamp) is a duplicate; "
                "retain the first source row and report conflicting payloads."
            ),
            "split_policy": (
                "Per-user chronological 70/15/15 train/validation/test; users "
                "below the eligibility threshold are excluded from warm-user "
                "splits and counted for cold-start reporting."
            ),
        },
        "sources": [
            {"title": "Official KuaiRec website", "url": "https://kuairec.com/"},
            {"title": "Official KuaiRec repository and schema", "url": REPOSITORY},
            {"title": "Zenodo dataset record", "url": ZENODO_RECORD},
            {
                "title": "KuaiRec dataset paper",
                "citation": (
                    "Gao et al., KuaiRec: A Fully-Observed Dataset and Insights "
                    "for Evaluating Recommender Systems, CIKM 2022, "
                    "https://doi.org/10.1145/3511808.3557220"
                ),
            },
        ],
        "interactions": {
            "big_matrix": big_stats,
            "small_matrix": small_stats,
        },
        "published_statistics_comparison": {
            name: {
                "matches_reference": {
                    "users": stats["unique_users"] == official_reference[name]["users"],
                    "videos": stats["unique_videos"] == official_reference[name]["videos"],
                    "interactions": stats["valid_interactions"] == official_reference[name]["interactions"],
                },
                "observed_density_percent": round(
                    100 * stats["valid_interactions"]
                    / (stats["unique_users"] * stats["unique_videos"]),
                    2,
                )
                if stats["unique_users"] and stats["unique_videos"]
                else None,
            }
            for name, stats in (("big_matrix", big_stats), ("small_matrix", small_stats))
        },
        "metadata": audit_metadata(data_dir),
    }


def render_data_card(
    report: dict[str, object],
    split_manifest: dict[str, object] | None = None,
) -> str:
    dataset = report["dataset"]
    interactions = report["interactions"]
    metadata = report["metadata"]
    assert isinstance(dataset, dict)
    assert isinstance(interactions, dict)
    assert isinstance(metadata, dict)
    big = interactions["big_matrix"]
    small = interactions["small_matrix"]
    assert isinstance(big, dict)
    assert isinstance(small, dict)
    comparisons = report["published_statistics_comparison"]
    assert isinstance(comparisons, dict)
    big_comparison = comparisons["big_matrix"]
    small_comparison = comparisons["small_matrix"]
    assert isinstance(big_comparison, dict)
    assert isinstance(small_comparison, dict)
    if split_manifest is None:
        split_manifest_path = repository_root() / "data" / "processed" / "split_manifest.json"
        if split_manifest_path.is_file():
            split_manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    filtered = split_manifest.get("filtered") if split_manifest else None
    if isinstance(filtered, dict):
        events_by_split = filtered["events_by_split"]
        relevant_by_split = filtered.get("relevant_events_by_split", {})
        overlap_users = filtered["user_overlap_counts"]
        overlap_items = filtered["item_overlap_counts"]
        candidate_protocol = filtered["candidate_protocol"]
        positive_coverage = candidate_protocol["positive_coverage"]
        split_summary = (
            f"{filtered['events_after_filtering']:,} eligible events "
            f"({events_by_split.get('train', 0):,} train, "
            f"{events_by_split.get('validation', 0):,} validation, "
            f"{events_by_split.get('test', 0):,} test).\n  "
            f"Relevant events: {relevant_by_split.get('train', 0):,} train, "
            f"{relevant_by_split.get('validation', 0):,} validation, "
            f"{relevant_by_split.get('test', 0):,} test.\n  "
            f"Eligible users/items: {filtered['users_after_filtering']:,}/"
            f"{filtered['items_after_filtering']:,}; training-only distinct-edge core excluded "
            f"{filtered['users_excluded_from_warm_splits']:,} users, "
            f"{filtered['items_before_filtering'] - filtered['items_after_filtering']:,} "
            f"items, and {filtered['events_excluded_by_core_filter']:,} events."
        )
        overlap_summary = (
            f"Train/test overlap is {overlap_users['train_test']:,} users and "
            f"{overlap_items['train_test']:,} items.\n  "
            f"Test has {positive_coverage['eligible_relevant_user_item_instances']['test']:,} "
            f"eligible relevant user-item instances in full-catalog candidates; "
            f"{positive_coverage['users_without_relevant_candidate']['test']:,} "
            "users have no remaining relevant candidate. Primary ranking metrics exclude "
            "those users, and all-user evaluation coverage is reported separately."
        )
    else:
        split_summary = "Pending completion of the chronological split."
        overlap_summary = "Pending completion of the chronological split."
    category_stats = metadata.get("item_categories")
    if isinstance(category_stats, dict):
        category_summary = (
            f"{category_stats['metadata_rows']:,} item rows, "
            f"{category_stats['distinct_category_ids']:,} distinct tag IDs, "
            f"{category_stats['malformed_feature_rows']:,} malformed rows"
        )
    else:
        category_summary = "No item_categories.csv found in this release."
    social_stats = metadata.get("social_network")
    if isinstance(social_stats, dict):
        social_summary = (
            f"{social_stats['users']:,} users and "
            f"{social_stats['directed_friend_entries']:,} directed friend entries; "
            f"{social_stats['malformed_rows']:,} malformed rows"
        )
    else:
        social_summary = "No social_network.csv found in this release."
    big_density = big_comparison["observed_density_percent"]
    small_density = small_comparison["observed_density_percent"]
    big_reference_status = (
        "match" if all(big_comparison["matches_reference"].values()) else "do not match"
    )
    small_reference_status = (
        "match" if all(small_comparison["matches_reference"].values()) else "do not match"
    )
    return f"""# KuaiRec Data Card

## Dataset identity and provenance

- **Dataset:** {dataset['name']}
- **Release:** {dataset['version']}
- **Zenodo DOI:** [10.5281/zenodo.18164998](https://doi.org/10.5281/zenodo.18164998)
- **Official sources:** [KuaiRec website](https://kuairec.com/),
  [official repository]({REPOSITORY}), and the
  [CIKM 2022 data paper](https://doi.org/10.1145/3511808.3557220).
- **Downloaded archive:** `data/raw/KuaiRec.zip`; Zenodo published size
  431,964,858 bytes, MD5 `261550d472c48eff4990fb13c0e5bcf7`.
- **Archive SHA-256:** generated locally after download and recorded in
  `data/processed/release_manifest.json`.
- **License discrepancy:** the official GitHub
  [LICENSE file]({REPOSITORY}/blob/main/LICENSE) identifies CC BY-SA 4.0,
  while Zenodo record metadata identifies CC BY 4.0. This project follows the
  more restrictive CC BY-SA 4.0 terms until the maintainers clarify the
  discrepancy. Do not redistribute the dataset archive from this project.

## Data files and roles

- `big_matrix.csv` is the sole source of interaction events for the model.
- `small_matrix.csv` is audited separately and is not concatenated with the Big
  Matrix or treated as an independent ratings test.
- The official site notes that Small Matrix missing entries reflect blocked
  user-video recommendations. Its 181,992 rows missing time/date/timestamp are
  retained as matrix cells but are not temporal events for this project.
- `item_categories.csv`, when present, is audited as item tag metadata.
- `social_network.csv`, when present, is counted for audit only; social links
  are not treated as evidence of shared taste.

## Schema and semantics

The official Big/Small Matrix schema includes `user_id`, `video_id`,
`play_duration`, `video_duration`, human-readable `time`, integer `date`, Unix
`timestamp`, and `watch_ratio`. The official documentation defines
`watch_ratio = play_duration / video_duration`, says no explicit like signal is
provided, and gives `watch_ratio > 2.0` as an example of deriving a positive
binary signal.

## Frozen protocol for this implementation

- **Relevant event:** `watch_ratio > 2.0`. This is a fixed derived target based
  on the official README example, not a native like label.
- **Duplicate key:** `(user_id, video_id, timestamp)`. Retain the first row in
  source order and report duplicate rows with conflicting payloads.
- **Eligibility:** iteratively retain the user-item 5-core using distinct
  training user-item edges only, so repeated events do not inflate graph degree
  and validation/test data do not determine the warm-user set
  or eligible catalog.
- **Split:** sort each eligible user's Big Matrix events by timestamp, then
  `video_id` for deterministic ties; assign the first 70% to training, next 15%
  to validation, and final 15% to test using floor boundaries. Boundaries are
  determined on deduplicated history before catalog filtering; filtering can
  change the final row ratios and does not move future events into training.
- **Leakage control:** validation/test events are excluded from the training
  history. Small Matrix rows are never merged into training.
- **Candidates:** for validation, use the full training-eligible catalog minus
  training history; for test, remove items seen in training or validation.
  Generate candidate pairs lazily; report users with no
  held-out relevant item remaining after seen-item removal separately.
- **Popularity baseline:** count positive (`watch_ratio > 2.0`) training events;
  use this as the cold-start fallback.
- **Advanced model:** LightGCN is the single planned extension; social edges are
  audit-only, not taste signals.

## Audit results

The audit report at `data/processed/data_audit.json` contains exact interaction,
user, item, missing-value, duplicate, timestamp, and social-link counts. Watch
ratio percentiles are estimated from a deterministic sample of up to
{RESERVOIR_SIZE:,} valid interactions (seed {SEED}); the exact sample size and
percentiles are recorded in the JSON report.

- **Big Matrix:** {big['valid_interactions']:,} rows, {big['unique_users']:,}
  users, {big['unique_videos']:,} videos. There are
  {big['duplicate_user_video_timestamp_rows']:,} duplicate event keys
  ({big['conflicting_duplicate_event_keys']:,} with conflicting payloads);
  {big['positive_events_watch_ratio_gt_2']:,} raw rows exceed the target
  threshold. Timestamp range: {big['timestamp_min_utc']} to
  {big['timestamp_max_utc']}.
- **Small Matrix:** {small['raw_interactions']:,} matrix rows,
  {small['unique_users']:,} users, {small['unique_videos']:,} videos, and
  {small['timestamp_incomplete_interactions']:,} rows without timestamps.
  These remain in published matrix counts but are excluded from temporal
  modeling.
- **Item categories:** {category_summary}.
- **Social links:** {social_summary}. Social links are audit-only.
- **Official published reference:** observed counts {big_reference_status} the
  Big Matrix reference (12,530,806 rows / 7,176 users / 10,728 videos) at
  {big_density:.2f}% density. Small Matrix counts {small_reference_status} its
  reference (4,676,570 rows / 1,411 users / 3,327 videos) at {small_density:.2f}%
  density.
- **Filtered split counts:** {split_summary}
- **Leakage/overlap and candidate coverage:** {overlap_summary}

## Limitations

The target threshold is a derived proxy for positive engagement, not a ground
truth like. Big and Small Matrices have different collection/evaluation roles.
No friendship-based taste claim is made. The split is temporal per user; users
who do not satisfy the warm-user eligibility core are excluded from the warm
split and must be treated as cold-start in later evaluation.
"""


def _sample_distribution(values: list[float]) -> dict[str, object]:
    if not values:
        return {"sample_size": 0}
    return {
        "sample_size": len(values),
        "sampling_method": "reservoir sampling",
        "sampling_seed": SEED,
        "min": values[0],
        "max": values[-1],
        "mean": sum(values) / len(values),
        "percentiles": {
            str(percentile): _quantile(values, percentile / 100)
            for percentile in (0, 25, 50, 75, 90, 95, 99, 100)
        },
    }


def _quantile(sorted_values: list[float], quantile: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _utc(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _find_file(data_dir: Path, filename: str) -> Path | None:
    for candidate in (data_dir / filename, data_dir / "data" / filename):
        if candidate.is_file():
            return candidate
    return None


def main() -> None:
    root = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "raw" / "KuaiRec")
    parser.add_argument("--report", type=Path, default=root / "data" / "processed" / "data_audit.json")
    parser.add_argument("--data-card", type=Path, default=root / "docs" / "DATA_CARD.md")
    args = parser.parse_args()
    report = create_report(args.data_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.data_card.parent.mkdir(parents=True, exist_ok=True)
    args.data_card.write_text(render_data_card(report), encoding="utf-8")
    print(f"Audit report: {args.report}")
    print(f"Data card: {args.data_card}")
    print(json.dumps(report["interactions"], indent=2))


if __name__ == "__main__":
    main()
