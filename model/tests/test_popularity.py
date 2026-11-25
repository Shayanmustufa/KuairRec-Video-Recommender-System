from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from model.src.common import sha256_file
from model.src.popularity import train_and_evaluate_popularity


class PopularityTests(unittest.TestCase):
    def test_training_only_ranking_seen_filter_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            output = root / "artifacts"
            data.mkdir()
            fields = ("user_id", "video_id", "timestamp", "watch_ratio", "is_relevant", "play_duration", "video_duration")
            train = [
                (1, 10, 1, 3, 1, 1, 1), (1, 11, 2, 1, 0, 1, 1),
                (2, 10, 1, 3, 1, 1, 1), (2, 12, 2, 3, 1, 1, 1),
            ]
            validation = [(1, 12, 3, 3, 1, 1, 1), (2, 13, 3, 3, 1, 1, 1)]
            self._write(data / "train.csv", fields, train)
            self._write(data / "validation.csv", fields, validation)
            self._write(data / "candidate_catalog.csv", ("video_id",), [(10,), (11,), (12,), (13,)])
            hashes = {name: sha256_file(data / name) for name in ("train.csv", "validation.csv", "candidate_catalog.csv")}
            (data / "split_manifest.json").write_text(json.dumps({
                "relevance": {"field": "watch_ratio", "operator": ">", "threshold": 2.0},
                "sha256": hashes,
            }), encoding="utf-8")

            result = train_and_evaluate_popularity(data, output, top_ks=(1, 2), example_users=2)

            items = result["model"]["items"]
            self.assertEqual([item["video_id"] for item in items], [10, 12, 11, 13])
            self.assertEqual(result["metrics"]["users_metric_eligible"], 2)
            self.assertEqual(result["metrics"]["metrics"]["recall@1"], 0.5)
            self.assertEqual(result["metrics"]["metrics"]["recall@2"], 1.0)
            with (output / "popularity_validation_predictions.csv").open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))
            self.assertEqual([row["video_id"] for row in rows if row["user_id"] == "1"], ["12", "13"])
            self.assertFalse(result["manifest"]["test_data_used"])

    @staticmethod
    def _write(path: Path, fields: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(fields)
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
