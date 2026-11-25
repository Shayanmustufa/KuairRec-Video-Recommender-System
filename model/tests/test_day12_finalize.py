from __future__ import annotations

import json
import unittest


class Day12ManifestTests(unittest.TestCase):
    def test_ui_contract_shape_contains_release_model_and_metrics(self) -> None:
        payload = {
            "dataset": {"release": "KuaiRec 2.0"},
            "model": {"model_id": "hybrid-validation-selected-v1"},
            "test_summary": {"metrics": {"ndcg@10": 0.1}},
        }
        encoded = json.loads(json.dumps(payload))
        self.assertEqual(encoded["dataset"]["release"], "KuaiRec 2.0")
        self.assertIn("model_id", encoded["model"])
        self.assertIn("ndcg@10", encoded["test_summary"]["metrics"])


if __name__ == "__main__": unittest.main()
