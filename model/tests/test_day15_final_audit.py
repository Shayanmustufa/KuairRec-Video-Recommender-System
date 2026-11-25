from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from model.src.common import sha256_file
from model.src.day15_final_audit import _hashes_match, _scan_hygiene


class Day15FinalAuditTests(unittest.TestCase):
    def test_hash_and_hygiene_checks_detect_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); file = root / "safe.py"; file.write_text("value = 1\n", encoding="utf-8")
            expected = {"safe.py": sha256_file(file)}
            self.assertTrue(_hashes_match(root, expected))
            self.assertEqual(_scan_hygiene(root), {"potential_secrets": [], "local_absolute_paths": []})
            unsafe = "pass" + 'word = "not-safe"\n'
            file.write_text(unsafe, encoding="utf-8")
            self.assertFalse(_hashes_match(root, expected))
            self.assertEqual(_scan_hygiene(root)["potential_secrets"], ["safe.py:1"])


if __name__ == "__main__": unittest.main()
