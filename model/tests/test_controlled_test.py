from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model.src.controlled_test import assert_test_not_already_run


class ControlledTestGuardTests(unittest.TestCase):
    def test_guard_refuses_existing_controlled_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assert_test_not_already_run(root)
            (root / "controlled_test_metrics.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                assert_test_not_already_run(root)


if __name__ == "__main__": unittest.main()
