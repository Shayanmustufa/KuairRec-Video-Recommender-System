from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from model.src.audit import audit_interactions
from model.src.split import build_splits

FIELDS = (
    "user_id",
    "video_id",
    "play_duration",
    "video_duration",
    "time",
    "date",
    "timestamp",
    "watch_ratio",
)


def write_interactions(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def event(user: int, video: int, second: int, ratio: float = 1.0) -> dict[str, object]:
    return {
        "user_id": user,
        "video_id": video,
        "play_duration": 1000,
        "video_duration": 1000,
        "time": f"2020-01-01 00:00:{second:02d}.000",
        "date": 20200101,
        "timestamp": 1577836800 + second,
        "watch_ratio": ratio,
    }


class AuditTests(unittest.TestCase):
    def test_audit_counts_duplicate_keys_and_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "big_matrix.csv"
            rows = [
                event(1, 10, 0),
                event(1, 10, 0),
                event(1, 10, 0, 0.9),
                event(1, 11, 1, 2.5),
            ]
            rows.append({**event(2, 12, 2), "watch_ratio": ""})
            rows.append({**event(2, 12, 3), "timestamp": ""})
            write_interactions(path, rows)

            report = audit_interactions(path)

            self.assertEqual(report["raw_interactions"], 6)
            self.assertEqual(report["valid_interactions"], 5)
            self.assertEqual(report["invalid_interactions"], 1)
            self.assertEqual(report["timestamp_incomplete_interactions"], 1)
            self.assertEqual(report["unique_interactions"], 3)
            self.assertEqual(report["duplicate_user_video_timestamp_rows"], 2)
            self.assertEqual(report["conflicting_duplicate_event_keys"], 1)
            self.assertEqual(report["unique_users"], 2)
            self.assertEqual(report["unique_videos"], 3)
            self.assertEqual(report["missing_values_by_column"], {
                "timestamp": 1,
                "watch_ratio": 1,
            })


class SplitTests(unittest.TestCase):
    def test_splits_are_chronological_deduplicated_and_leakage_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_dir = root / "KuaiRec"
            output_dir = root / "processed"
            data_dir.mkdir()
            rows: list[dict[str, object]] = []
            for user_id in range(1, 7):
                for second in range(10):
                    video_id = (
                        13
                        if second == 9 and user_id == 1
                        else 12
                        if second >= 8 and user_id == 1
                        else 12
                        if second == 6 and user_id > 1
                        else 12
                        if second >= 8
                        else 10 + second % 2
                    )
                    watch_ratio = 2.5 if user_id == 1 and second == 8 else 1.0
                    rows.append(event(user_id, video_id, user_id * 20 + second, watch_ratio))
            rows.append(rows[0].copy())
            rows.append({**rows[0], "watch_ratio": 0.9})
            write_interactions(data_dir / "big_matrix.csv", rows)
            write_interactions(data_dir / "small_matrix.csv", [])

            manifest = build_splits(data_dir, output_dir, min_interactions=2)

            self.assertEqual(manifest["input"]["duplicate_rows_removed"], 2)
            self.assertEqual(manifest["input"]["conflicting_duplicate_event_keys"], 1)
            self.assertFalse(manifest["small_matrix_used"])
            self.assertEqual(manifest["filtered"]["users_after_filtering"], 6)
            self.assertEqual(manifest["filtered"]["items_after_filtering"], 3)
            self.assertEqual(manifest["filtered"]["events_by_split"], {
                "train": 42,
                "validation": 6,
                "test": 11,
            })
            self.assertEqual(manifest["filtered"]["relevant_events_by_split"]["test"], 1)
            self.assertEqual(
                manifest["filtered"]["events_excluded_by_core_filter"],
                1,
            )
            self.assertEqual(
                manifest["filtered"]["candidate_protocol"]["positive_coverage"][
                    "eligible_relevant_user_item_instances"
                ]["test"],
                1,
            )
            splits = {
                name: read_rows(output_dir / f"{name}.csv")
                for name in ("train", "validation", "test")
            }
            for user_id in ("1", "2", "3", "4", "5", "6"):
                times = {
                    name: [
                        float(row["timestamp"])
                        for row in rows
                        if row["user_id"] == user_id
                    ]
                    for name, rows in splits.items()
                }
                self.assertLess(max(times["train"]), min(times["validation"]))
                self.assertLess(max(times["validation"]), min(times["test"]))
            train_keys = {key(row) for row in splits["train"]}
            validation_keys = {key(row) for row in splits["validation"]}
            test_keys = {key(row) for row in splits["test"]}
            self.assertFalse(train_keys & validation_keys)
            self.assertFalse(train_keys & test_keys)
            self.assertFalse(validation_keys & test_keys)
            self.assertTrue(all(row["is_relevant"] == "0" for row in splits["train"]))
            self.assertEqual(
                [row["is_relevant"] for row in splits["test"]].count("1"),
                1,
            )
            self.assertEqual(
                [row["video_id"] for row in read_rows(output_dir / "candidate_catalog.csv")],
                ["10", "11", "12"],
            )
            self.assertNotIn(
                "13",
                [row["video_id"] for row in read_rows(output_dir / "test.csv")],
            )
            self.assertEqual(
                [row["video_id"] for row in read_rows(output_dir / "user_history_train.csv")],
                [row["video_id"] for row in splits["train"]],
            )
            self.assertEqual(
                len(read_rows(output_dir / "user_history_test.csv")),
                len(splits["train"]) + len(splits["validation"]),
            )
            saved_manifest = json.loads((output_dir / "split_manifest.json").read_text())
            self.assertEqual(saved_manifest["sha256"]["test.csv"], manifest["sha256"]["test.csv"])

    def test_iterative_core_excludes_users_and_items_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_dir = root / "data"
            data_dir.mkdir()
            rows = [event(1, video, second) for second, video in enumerate((1, 2, 3, 4, 5))]
            rows.extend(event(2, video, 10 + second) for second, video in enumerate((1, 2, 3, 4)))
            write_interactions(data_dir / "big_matrix.csv", rows)
            write_interactions(data_dir / "small_matrix.csv", [])

            manifest = build_splits(data_dir, root / "processed", min_interactions=5)

            self.assertEqual(manifest["filtered"]["users_after_filtering"], 0)
            self.assertEqual(manifest["filtered"]["items_after_filtering"], 0)

    def test_core_uses_distinct_neighbors_not_repeated_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_dir = root / "data"
            data_dir.mkdir()
            rows = [event(1, 10, second) for second in range(10)]
            rows.extend(event(2, 10, 20 + second) for second in range(10))
            write_interactions(data_dir / "big_matrix.csv", rows)
            write_interactions(data_dir / "small_matrix.csv", [])

            manifest = build_splits(data_dir, root / "processed", min_interactions=2)

            self.assertEqual(manifest["filtered"]["users_after_filtering"], 0)
            self.assertEqual(manifest["filtered"]["items_after_filtering"], 0)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def key(row: dict[str, str]) -> tuple[str, str, str]:
    return row["user_id"], row["video_id"], row["timestamp"]


if __name__ == "__main__":
    unittest.main()
