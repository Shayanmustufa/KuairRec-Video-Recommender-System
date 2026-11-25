from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from model.src.common import sha256_file
from model.src.lightgcn_tune import tune_and_train_lightgcn


class LightGCNTuningTests(unittest.TestCase):
    def test_validation_only_selection_and_full_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data, output = root / "data", root / "artifacts"
            data.mkdir(); output.mkdir()
            fields = ("user_id", "video_id", "timestamp", "watch_ratio", "is_relevant", "play_duration", "video_duration")
            train = [
                (10, 1, 1, 3, 1, 1, 1), (10, 2, 2, 3, 1, 1, 1),
                (20, 2, 1, 3, 1, 1, 1), (20, 3, 2, 3, 1, 1, 1),
                (30, 3, 1, 3, 1, 1, 1), (30, 4, 2, 3, 1, 1, 1),
            ]
            validation = [(10, 3, 3, 3, 1, 1, 1), (20, 4, 3, 3, 1, 1, 1), (30, 1, 3, 3, 1, 1, 1)]
            self._write(data / "train.csv", fields, train)
            self._write(data / "validation.csv", fields, validation)
            self._write(data / "candidate_catalog.csv", ("video_id",), [(1,), (2,), (3,), (4,), (5,)])
            hashes = {name: sha256_file(data / name) for name in ("train.csv", "validation.csv", "candidate_catalog.csv")}
            (data / "split_manifest.json").write_text(json.dumps({"sha256": hashes}), encoding="utf-8")
            zero_metrics = {f"{name}@{k}": 0 for name in ("recall", "ndcg", "precision", "hit_rate") for k in (10, 20)}
            (output / "popularity_validation_metrics.json").write_text(json.dumps({"metrics": zero_metrics}), encoding="utf-8")
            (output / "item_cf_validation_metrics.json").write_text(json.dumps({"metrics": zero_metrics}), encoding="utf-8")
            configs = (
                {"learning_rate": 0.001, "layers": 1, "embedding_dim": 4, "epochs": 1},
                {"learning_rate": 0.002, "layers": 1, "embedding_dim": 4, "epochs": 2},
            )

            result = tune_and_train_lightgcn(
                data, output, configurations=configs, tuning_users=3, device="cpu"
            )

            self.assertEqual(len(result["metrics"]["tuning_grid"]), 2)
            self.assertEqual(result["metrics"]["validation"]["users_metric_eligible"], 3)
            self.assertFalse(result["metrics"]["test_data_used"])
            self.assertTrue((output / "lightgcn_embeddings.npz").is_file())
            self.assertEqual(len(result["manifest"]["artifacts_sha256"]), 4)

    @staticmethod
    def _write(path: Path, fields: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target); writer.writerow(fields); writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
