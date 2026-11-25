from __future__ import annotations

import unittest
from scipy import sparse

from model.src.freeze_day9 import build_reasons


class ExplanationTests(unittest.TestCase):
    def test_reasons_use_actual_item_cf_and_popularity_evidence(self) -> None:
        similarity = sparse.csc_matrix((
            [0.2, 0.5], ([0, 1], [2, 2])
        ), shape=(3, 3))
        reasons = build_reasons(
            {0: 1.0, 1: 2.0}, 2, similarity, [10, 20, 30], 7,
            {"popularity": 0.1, "item_cf": 0.9, "lightgcn": 0.0},
        )
        self.assertEqual([reason["code"] for reason in reasons], [
            "liked_by_similar_users", "popular_in_training"
        ])
        self.assertEqual(reasons[0]["evidence"]["source_video_id"], 20)
        self.assertAlmostEqual(reasons[0]["evidence"]["contribution"], 1.0)
        self.assertNotIn("extension_model_match", [reason["code"] for reason in reasons])


if __name__ == "__main__": unittest.main()
