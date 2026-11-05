#!/usr/bin/env python3
"""预算：单 blob / 批总量 / 路径数。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content"))
import sfx
from content_budget import Budget, BatchBudget, BudgetError


class TestBudget(unittest.TestCase):
    def test_blob_too_large(self):
        b = BatchBudget(Budget(max_blob_bytes=100))
        with self.assertRaises(BudgetError) as cm:
            b.check_blob(101)
        self.assertEqual(cm.exception.code, "BLOB_TOO_LARGE")

    def test_batch_byte_limit(self):
        b = BatchBudget(Budget(max_blob_bytes=100, max_batch_bytes=200))
        b.check_blob(100); b.check_blob(100)
        with self.assertRaises(BudgetError):
            b.check_blob(50)

    def test_path_limit(self):
        b = BatchBudget(Budget(max_paths=2))
        b.admit_path(); b.admit_path()
        with self.assertRaises(BudgetError):
            b.admit_path()

    def test_defaults_are_sane(self):
        d = Budget()
        self.assertEqual(d.max_blob_bytes, 256 * 1024)
        self.assertEqual(d.max_batch_bytes, 2 * 1024 * 1024)
        self.assertEqual(d.max_paths, 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
