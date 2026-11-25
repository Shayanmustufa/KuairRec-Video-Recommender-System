from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from model.src.common import sha256_file
from model.src.item_cf import train_and_evaluate_item_cf


class ItemCFTests(unittest.TestCase):
    def test_item_cf_trains_selects_and_excludes_seen_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            output = root / "artifacts"
            data.mkdir()
            output.mkdir()
            fields = ("user_id", "video_id", "timestamp", "watch_ratio", "is_relevant", "play_duration", "video_duration")
            train = [
                (10, 1, 1, 3, 1, 1, 1), (10, 2, 2, 4, 1, 1, 1),
                (20, 1, 1, 3, 1, 1, 1), (20, 3, 2, 4, 1, 1, 1),
                (30, 2, 1, 3, 1, 1, 1), (30, 3, 2, 4, 1, 1, 1),
            ]
            validation = [(10, 3, 3, 3, 1, 1, 1), (20, 2, 3, 3, 1, 1, 1), (30, 1, 3, 3, 1, 1, 1)]
            self._write(data / "train.csv", fields, train)
            self._write(data / "validation.csv", fields, validation)
            self._write(data / "candidate_catalog.csv", ("video_id",), [(1,), (2,), (3,), (4,)])
            hashes = {name: sha256_file(data / name) for name in ("train.csv", "validation.csv", "candidate_catalog.csv")}
            (data / "split_manifest.json").write_text(json.dumps({"sha256": hashes}), encoding="utf-8")
            (output / "popularity_validation_metrics.json").write_text(json.dumps({
                "metrics": {f"{name}@{k}": 0 for name in ("recall", "ndcg", "precision", "hit_rate") for k in (10, 20)}
            }), encoding="utf-8")

            result = train_and_evaluate_item_cf(
                data, output, neighborhoods=(1, 2), shrinkages=(0.0, 1.0), tuning_user_limit=None
            )

            self.assertFalse(result["manifest"]["test_data_used"])
            self.assertEqual(result["metrics"]["users_metric_eligible"], 3)
            with (output / "item_cf_validation_predictions.csv").open(encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
            user_10 = [int(row["video_id"]) for row in rows if row["user_id"] == "10"]
            self.assertNotIn(1, user_10)
            self.assertNotIn(2, user_10)
            self.assertEqual(user_10[0], 3)

    @staticmethod
    def _write(path: Path, fields: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(fields)
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
