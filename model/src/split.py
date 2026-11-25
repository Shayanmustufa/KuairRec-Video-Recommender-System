"""Deduplicate, filter, and export leakage-safe chronological KuaiRec splits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

from model.src.common import (
    OUTPUT_COLUMNS,
    DatasetError,
    format_timestamp,
    interaction_path,
    open_interactions,
    parse_interaction,
    repository_root,
    sha256_file,
)

DEFAULT_SEED = 2026
DEFAULT_MIN_INTERACTIONS = 5
DEFAULT_RELEVANCE_THRESHOLD = 2.0
SCHEMA_VERSION = "1.1"


def build_splits(
    data_dir: Path,
    output_dir: Path,
    min_interactions: int = DEFAULT_MIN_INTERACTIONS,
    relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    if min_interactions < 1:
        raise ValueError("min_interactions must be at least 1")
    source_path = interaction_path(data_dir, "big_matrix.csv")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kuairec-split-") as temporary:
        database_path = Path(temporary) / "events.sqlite"
        connection = sqlite3.connect(database_path)
        try:
            stats = _load_events(connection, source_path)
            _create_eligibility_core(connection, min_interactions)
            counts = _write_outputs(
                connection,
                output_dir,
                relevance_threshold,
            )
            manifest: dict[str, object] = {
                "schema_version": SCHEMA_VERSION,
                "source": "big_matrix.csv",
                "small_matrix_used": False,
                "seed": seed,
                "relevance": {
                    "field": "watch_ratio",
                    "operator": ">",
                    "threshold": relevance_threshold,
                    "definition": (
                        f"watch_ratio > {relevance_threshold:g}; derived positive "
                        "proxy, not an official like label"
                    ),
                },
                "deduplication": {
                    "key": ["user_id", "video_id", "timestamp"],
                    "policy": "keep first source row; report conflicting duplicate payloads",
                },
                "eligibility": {
                    "method": "iterative bipartite k-core on distinct training user-item edges only",
                    "minimum_distinct_neighbors_per_user": min_interactions,
                    "minimum_distinct_neighbors_per_item": min_interactions,
                    "future_events_used_for_filtering": False,
                },
                "split": {
                    "method": "per-user chronological",
                    "proportions": {"train": 0.70, "validation": 0.15, "test": 0.15},
                    "boundaries": (
                        "floor(0.70*n), floor(0.85*n) on each user's deduplicated "
                        "chronology before catalog filtering; video_id breaks timestamp ties"
                    ),
                },
                "input": stats,
                "filtered": counts,
            }
            files = (
                "train.csv",
                "validation.csv",
                "test.csv",
                "user_history_train.csv",
                "user_history_test.csv",
                "candidate_catalog.csv",
            )
            manifest["sha256"] = {
                filename: sha256_file(output_dir / filename) for filename in files
            }
            manifest_path = output_dir / "split_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        finally:
            connection.close()
    return manifest


def _load_events(connection: sqlite3.Connection, source_path: Path) -> dict[str, int]:
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("PRAGMA cache_size=-262144")
    connection.execute(
        "CREATE TABLE events ("
        "user_id INTEGER NOT NULL, video_id INTEGER NOT NULL, timestamp REAL NOT NULL, "
        "watch_ratio REAL NOT NULL, play_duration INTEGER NOT NULL, "
        "video_duration INTEGER NOT NULL, payload_signature TEXT NOT NULL, "
        "conflicting_duplicate INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (user_id, video_id, timestamp)) WITHOUT ROWID"
    )
    valid_rows = 0
    invalid_rows = 0
    batch: list[tuple[int, int, float, float, int, int, str]] = []
    source, reader = open_interactions(source_path)
    try:
        for row in reader:
            try:
                event = parse_interaction(row)
            except (DatasetError, ValueError):
                invalid_rows += 1
                continue
            user_id = int(event["user_id"])
            video_id = int(event["video_id"])
            timestamp = float(event["timestamp"])
            watch_ratio = float(event["watch_ratio"])
            play_duration = int(event["play_duration"])
            video_duration = int(event["video_duration"])
            payload_signature = (
                f"{watch_ratio:.15g}|{play_duration}|{video_duration}"
            )
            batch.append(
                (
                    user_id,
                    video_id,
                    timestamp,
                    watch_ratio,
                    play_duration,
                    video_duration,
                    payload_signature,
                )
            )
            if len(batch) >= 20_000:
                _insert_event_batch(connection, batch)
                valid_rows += len(batch)
                batch.clear()
        if batch:
            _insert_event_batch(connection, batch)
            valid_rows += len(batch)
            batch.clear()
    finally:
        source.close()
    connection.commit()
    connection.execute("CREATE INDEX events_video_idx ON events(video_id, user_id)")
    connection.execute("CREATE INDEX events_user_time_idx ON events(user_id, timestamp, video_id)")
    unique_rows = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conflicting_duplicate_keys = connection.execute(
        "SELECT COUNT(*) FROM events WHERE conflicting_duplicate=1"
    ).fetchone()[0]
    return {
        "rows_read_valid": valid_rows,
        "rows_stored_after_deduplication": unique_rows,
        "invalid_rows": invalid_rows,
        "duplicate_rows_removed": valid_rows - unique_rows,
        "conflicting_duplicate_event_keys": conflicting_duplicate_keys,
        "users_before_filtering": connection.execute(
            "SELECT COUNT(DISTINCT user_id) FROM events"
        ).fetchone()[0],
        "items_before_filtering": connection.execute(
            "SELECT COUNT(DISTINCT video_id) FROM events"
        ).fetchone()[0],
    }


def _insert_event_batch(
    connection: sqlite3.Connection,
    batch: list[tuple[int, int, float, float, int, int, str]],
) -> None:
    connection.executemany(
        "INSERT INTO events "
        "(user_id, video_id, timestamp, watch_ratio, play_duration, video_duration, payload_signature) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, video_id, timestamp) DO UPDATE SET "
        "conflicting_duplicate=MAX(events.conflicting_duplicate, "
        "events.payload_signature != excluded.payload_signature)",
        batch,
    )


def _create_eligibility_core(connection: sqlite3.Connection, minimum: int) -> None:
    connection.execute(
        "CREATE TABLE training_events ("
        "user_id INTEGER NOT NULL, video_id INTEGER NOT NULL, timestamp REAL NOT NULL, "
        "PRIMARY KEY (user_id, video_id, timestamp)) WITHOUT ROWID"
    )
    connection.execute(
        "WITH ordered AS ("
        "SELECT user_id, video_id, timestamp, "
        "ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY timestamp, video_id) AS position, "
        "COUNT(*) OVER (PARTITION BY user_id) AS event_count "
        "FROM events) "
        "INSERT INTO training_events "
        "SELECT user_id, video_id, timestamp FROM ordered "
        "WHERE position <= CAST(event_count * 0.70 AS INTEGER)"
    )
    connection.execute(
        "CREATE INDEX training_events_video_idx ON training_events(video_id, user_id)"
    )
    connection.execute(
        "CREATE TABLE active_users (user_id INTEGER PRIMARY KEY) WITHOUT ROWID"
    )
    connection.execute(
        "CREATE TABLE active_items (video_id INTEGER PRIMARY KEY) WITHOUT ROWID"
    )
    connection.execute(
        "INSERT INTO active_users "
        "SELECT user_id FROM training_events GROUP BY user_id HAVING COUNT(DISTINCT video_id) >= ?",
        (minimum,),
    )
    connection.execute(
        "INSERT INTO active_items "
        "SELECT video_id FROM training_events GROUP BY video_id HAVING COUNT(DISTINCT user_id) >= ?",
        (minimum,),
    )
    while True:
        before = (
            connection.execute("SELECT COUNT(*) FROM active_users").fetchone()[0],
            connection.execute("SELECT COUNT(*) FROM active_items").fetchone()[0],
        )
        connection.execute(
            "DELETE FROM active_users WHERE ("
            "SELECT COUNT(DISTINCT e.video_id) FROM training_events e "
            "JOIN active_items i ON i.video_id=e.video_id "
            "WHERE e.user_id=active_users.user_id) < ?",
            (minimum,),
        )
        connection.execute(
            "DELETE FROM active_items WHERE ("
            "SELECT COUNT(DISTINCT e.user_id) FROM training_events e "
            "JOIN active_users u ON u.user_id=e.user_id "
            "WHERE e.video_id=active_items.video_id) < ?",
            (minimum,),
        )
        after = (
            connection.execute("SELECT COUNT(*) FROM active_users").fetchone()[0],
            connection.execute("SELECT COUNT(*) FROM active_items").fetchone()[0],
        )
        if after == before:
            connection.commit()
            return


def _write_outputs(
    connection: sqlite3.Connection,
    output_dir: Path,
    relevance_threshold: float,
) -> dict[str, object]:
    initial_users = connection.execute(
        "SELECT COUNT(DISTINCT user_id) FROM events"
    ).fetchone()[0]
    initial_items = connection.execute(
        "SELECT COUNT(DISTINCT video_id) FROM events"
    ).fetchone()[0]
    final_users = connection.execute("SELECT COUNT(*) FROM active_users").fetchone()[0]
    final_items = connection.execute("SELECT COUNT(*) FROM active_items").fetchone()[0]
    split_counts = Counter()
    relevant_counts = Counter()
    users_by_split = {name: set() for name in ("train", "validation", "test")}
    items_by_split = {name: set() for name in ("train", "validation", "test")}
    event_key_digest = hashlib.sha256()
    candidate_stats = {
        "evaluated_users": {"validation": 0, "test": 0},
        "users_without_relevant_candidate": {"validation": 0, "test": 0},
        "relevant_user_item_instances": {"validation": 0, "test": 0},
        "relevant_instances_excluded_as_seen": {"validation": 0, "test": 0},
        "eligible_relevant_user_item_instances": {"validation": 0, "test": 0},
    }
    candidate_count_sum = 0
    candidate_count_min: int | None = None
    candidate_count_max = 0
    output_names = ("train.csv", "validation.csv", "test.csv")
    with (
        (output_dir / output_names[0]).open("w", encoding="utf-8", newline="") as train_file,
        (output_dir / output_names[1]).open("w", encoding="utf-8", newline="") as validation_file,
        (output_dir / output_names[2]).open("w", encoding="utf-8", newline="") as test_file,
        (output_dir / "user_history_train.csv").open("w", encoding="utf-8", newline="") as history_file,
        (output_dir / "user_history_test.csv").open("w", encoding="utf-8", newline="") as test_history_file,
        (output_dir / "candidate_catalog.csv").open("w", encoding="utf-8", newline="") as catalog_file,
    ):
        writers = {
            "train": csv.writer(train_file),
            "validation": csv.writer(validation_file),
            "test": csv.writer(test_file),
        }
        history_writer = csv.writer(history_file)
        test_history_writer = csv.writer(test_history_file)
        catalog_writer = csv.writer(catalog_file)
        for writer in (*writers.values(), history_writer, test_history_writer):
            writer.writerow(OUTPUT_COLUMNS)
        catalog_writer.writerow(("video_id",))
        catalog_writer.writerows(
            connection.execute("SELECT video_id FROM active_items ORDER BY video_id")
        )

        current_user: int | None = None
        train_end = 0
        validation_end = 0
        training_seen: set[int] = set()
        validation_seen: set[int] = set()
        heldout_relevant_items = {"validation": set(), "test": set()}

        def finish_user() -> None:
            nonlocal candidate_count_sum, candidate_count_min, candidate_count_max
            if current_user is None:
                return
            user_candidate_count = final_items - len(training_seen | validation_seen)
            candidate_count_sum += user_candidate_count
            candidate_count_min = (
                user_candidate_count
                if candidate_count_min is None
                else min(candidate_count_min, user_candidate_count)
            )
            candidate_count_max = max(candidate_count_max, user_candidate_count)
            for evaluation_split in ("validation", "test"):
                relevant_items = heldout_relevant_items[evaluation_split]
                seen_items = training_seen if evaluation_split == "validation" else training_seen | validation_seen
                candidate_items = relevant_items - seen_items
                candidate_stats["evaluated_users"][evaluation_split] += 1
                candidate_stats["relevant_user_item_instances"][evaluation_split] += len(relevant_items)
                candidate_stats["relevant_instances_excluded_as_seen"][evaluation_split] += (
                    len(relevant_items & seen_items)
                )
                candidate_stats["eligible_relevant_user_item_instances"][evaluation_split] += len(candidate_items)
                if not candidate_items:
                    candidate_stats["users_without_relevant_candidate"][evaluation_split] += 1

        for row in connection.execute(
            "WITH ordered AS ("
            "SELECT user_id, video_id, timestamp, watch_ratio, play_duration, video_duration, "
            "ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY timestamp, video_id) AS position, "
            "COUNT(*) OVER (PARTITION BY user_id) AS event_count "
            "FROM events) "
            "SELECT e.user_id, e.video_id, e.timestamp, e.watch_ratio, "
            "e.play_duration, e.video_duration, e.position, e.event_count "
            "FROM ordered e "
            "JOIN active_users u ON u.user_id=e.user_id "
            "JOIN active_items i ON i.video_id=e.video_id "
            "ORDER BY e.user_id, e.position"
        ):
            (
                user_id,
                video_id,
                timestamp,
                watch_ratio,
                play_duration,
                video_duration,
                event_position,
                event_count,
            ) = row
            if user_id != current_user:
                finish_user()
                current_user = user_id
                training_seen = set()
                validation_seen = set()
                heldout_relevant_items = {"validation": set(), "test": set()}
                train_end = int(event_count * 0.70)
                validation_end = int(event_count * 0.85)
                if train_end < 1 or validation_end <= train_end or validation_end >= event_count:
                    raise DatasetError(
                        f"User {user_id} with {event_count} events cannot form three chronological splits"
                    )
            split_name = "train" if event_position <= train_end else (
                "validation" if event_position <= validation_end else "test"
            )
            relevant = int(watch_ratio > relevance_threshold)
            record = (
                user_id,
                video_id,
                format_timestamp(timestamp),
                format_timestamp(watch_ratio),
                relevant,
                play_duration,
                video_duration,
            )
            writers[split_name].writerow(record)
            split_counts[split_name] += 1
            relevant_counts[split_name] += relevant
            users_by_split[split_name].add(user_id)
            items_by_split[split_name].add(video_id)
            if split_name == "train":
                history_writer.writerow(record)
                test_history_writer.writerow(record)
                training_seen.add(video_id)
            elif split_name == "validation":
                test_history_writer.writerow(record)
                validation_seen.add(video_id)
                if relevant:
                    heldout_relevant_items[split_name].add(video_id)
            elif relevant:
                heldout_relevant_items[split_name].add(video_id)
            event_key_digest.update(f"{user_id},{video_id},{timestamp:.15g}\n".encode("ascii"))
        finish_user()

    evaluated_user_total = candidate_stats["evaluated_users"]["test"]
    candidate_stats["candidate_count_per_user"] = {
        "min": candidate_count_min,
        "max": candidate_count_max,
        "per_user_mean": (
            candidate_count_sum / evaluated_user_total
            if evaluated_user_total
            else 0
        ),
    }
    total_events = sum(split_counts.values())
    return {
        "users_before_filtering": initial_users,
        "items_before_filtering": initial_items,
        "users_after_filtering": final_users,
        "items_after_filtering": final_items,
        "events_after_filtering": total_events,
        "events_by_split": dict(split_counts),
        "relevant_events_by_split": dict(relevant_counts),
        "unique_event_key_sha256": event_key_digest.hexdigest(),
        "candidate_catalog_size": final_items,
        "candidate_protocol": {
            "type": "full_catalog",
            "definition": (
                "For validation, exclude training-seen items. For test, exclude "
                "items seen in training or validation. Candidate sets are evaluated "
                "lazily without materializing dense user-item pairs."
            ),
            "negative_sampling": False,
            "ranking_metric_denominator_policy": (
                "Primary ranking metrics exclude users with no eligible relevant candidate; "
                "report their count and all-user evaluation coverage separately."
            ),
            "positive_coverage": candidate_stats,
        },
        "user_overlap_counts": {
            "train_validation": len(users_by_split["train"] & users_by_split["validation"]),
            "train_test": len(users_by_split["train"] & users_by_split["test"]),
            "validation_test": len(users_by_split["validation"] & users_by_split["test"]),
        },
        "item_overlap_counts": {
            "train_validation": len(items_by_split["train"] & items_by_split["validation"]),
            "train_test": len(items_by_split["train"] & items_by_split["test"]),
            "validation_test": len(items_by_split["validation"] & items_by_split["test"]),
        },
        "users_excluded_from_warm_splits": connection.execute(
            "SELECT COUNT(DISTINCT e.user_id) FROM events e "
            "LEFT JOIN active_users u ON u.user_id=e.user_id "
            "WHERE u.user_id IS NULL"
        ).fetchone()[0],
        "events_excluded_by_core_filter": (
            connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] - total_events
        ),
    }


def main() -> None:
    root = repository_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "raw" / "KuaiRec")
    parser.add_argument("--output-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--min-interactions", type=int, default=DEFAULT_MIN_INTERACTIONS)
    parser.add_argument("--watch-ratio-threshold", type=float, default=DEFAULT_RELEVANCE_THRESHOLD)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    manifest = build_splits(
        args.data_dir,
        args.output_dir,
        args.min_interactions,
        args.watch_ratio_threshold,
        args.seed,
    )
    print(f"Split manifest: {args.output_dir / 'split_manifest.json'}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
