from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from model.src.common import sha256_file
from model.src.lightgcn import LightGCNConfig, run_lightgcn_prototype


class LightGCNTests(unittest.TestCase):
    def test_debug_prototype_is_finite_reproducible_and_test_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "data"
            output = root / "artifacts"
            data.mkdir()
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
            config = LightGCNConfig(sample_users=3, embedding_dim=8, layers=1, epochs=2, top_k=3)

            result = run_lightgcn_prototype(data, output, config)

            metrics = result["metrics"]
            self.assertTrue(metrics["training"]["loss_finite"])
            self.assertTrue(metrics["training"]["embeddings_finite"])
            self.assertTrue(metrics["debug_validation"]["scores_finite"])
            self.assertFalse(metrics["test_data_used"])
            self.assertEqual(metrics["sample"]["users"], 3)
            self.assertTrue((output / "lightgcn_debug_checkpoint.pt").is_file())

    @staticmethod
    def _write(path: Path, fields: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(fields)
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
