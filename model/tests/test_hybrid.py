from __future__ import annotations

import unittest
import numpy as np
from scipy import sparse

from model.src.hybrid import _normalize_unseen, _top_k, weight_grid


class HybridTests(unittest.TestCase):
    def test_weight_grid_is_complete_nonnegative_and_sums_to_one(self) -> None:
        grid = weight_grid(10)
        self.assertEqual(len(grid), 66)
        self.assertTrue(all(all(weight >= 0 for weight in row) for row in grid))
        self.assertTrue(all(abs(sum(row) - 1) < 1e-12 for row in grid))
        self.assertIn((1.0, 0.0, 0.0), grid)
        self.assertIn((0.0, 1.0, 0.0), grid)
        self.assertIn((0.0, 0.0, 1.0), grid)

    def test_normalization_excludes_seen_items_and_bounds_candidates(self) -> None:
        scores = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        seen = sparse.csr_matrix(([1.0], ([0], [2])), shape=(1, 3))
        normalized = _normalize_unseen(scores, seen)
        self.assertEqual(normalized[0, 0], 0.0)
        self.assertEqual(normalized[0, 1], 1.0)
        self.assertEqual(normalized[0, 2], 0.0)

    def test_top_k_breaks_boundary_ties_by_video_id(self) -> None:
        scores = np.array([0.5, 0.9, 0.5, 0.8], dtype=np.float32)
        catalog = np.array([30, 40, 10, 20])
        self.assertEqual(_top_k(scores, catalog, 3).tolist(), [1, 3, 2])


if __name__ == "__main__": unittest.main()
