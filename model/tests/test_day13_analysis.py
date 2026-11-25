from __future__ import annotations

import unittest

from model.src.day13_analysis import _bootstrap, _user_metrics


class Day13AnalysisTests(unittest.TestCase):
    def test_user_metrics_and_seeded_bootstrap_are_reproducible(self) -> None:
        first = _user_metrics([1] + [0] * 19, 2)
        second = _user_metrics([0, 1] + [0] * 18, 1)
        self.assertEqual(first["recall@10"], 0.5)
        self.assertEqual(first["precision@10"], 0.1)
        self.assertEqual(first["hit_rate@20"], 1.0)
        report_a = _bootstrap([first, second], (1, 2), 10)
        report_b = _bootstrap([first, second], (1, 2), 10)
        self.assertEqual(report_a, report_b)


if __name__ == "__main__": unittest.main()
