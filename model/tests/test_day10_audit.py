from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from model.src.day10_audit import split_bounds


class Day10AuditTests(unittest.TestCase):
    def test_split_bounds_counts_and_rejects_non_monotonic_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "split.csv"
            fields = ("user_id", "video_id", "timestamp")
            with path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.writer(target); writer.writerow(fields)
                writer.writerows(((1, 10, 1.0), (1, 11, 2.0), (2, 10, 1.0)))
            result = split_bounds(path)
            self.assertEqual(result["rows"], 3)
            self.assertEqual(result["users"][1], ((1.0, 10), (2.0, 11)))
            with path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.writer(target); writer.writerow(fields)
                writer.writerows(((1, 11, 2.0), (1, 10, 1.0)))
            with self.assertRaises(ValueError):
                split_bounds(path)


if __name__ == "__main__": unittest.main()
