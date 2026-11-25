from __future__ import annotations

import unittest

from model.src.day14_report import render_grouped_bars


class Day14ReportTests(unittest.TestCase):
    def test_chart_is_accessible_and_escapes_labels(self) -> None:
        chart = render_grouped_bars("A < B", [("Group", [("Metric", 0.25)])])
        self.assertIn('role="img"', chart)
        self.assertIn("A &lt; B", chart)
        self.assertIn("0.250000", chart)


if __name__ == "__main__": unittest.main()
