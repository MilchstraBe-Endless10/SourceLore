#!/usr/bin/env python3
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "collector"))
sys.path.insert(0, str(ROOT / "tests" / "product_multirepo"))
import capture_plan_consistency as CPC
from gold.multirepo_gold import GOLD


class TestRegistry(unittest.TestCase):
    def test_cases(self):
        self.assertGreaterEqual(len(GOLD), 20)
        ids = [g[0] for g in GOLD]
        self.assertEqual(len(ids), len(set(ids)))


class TestConsistency(unittest.TestCase):
    def _plan(self, root="/tmp/a", objs=None):
        objs = objs or [{"file_path": "a.js", "state": "CONTENT_NOT_CAPTURED",
                         "planned_requests": 1}]
        ctx = CPC.build_plan_context(repository_id="r", commit_sha="c",
                                     data_root=root, source_snapshot_id="s",
                                     selected_scope=["a.js"])
        return CPC.finalize_plan(context=ctx,
                                 inventory={"objects": objs,
                                            "planned_requests_total": 1})

    def test_M04_context_fields(self):
        ctx = CPC.build_plan_context(repository_id="r", commit_sha="c",
                                     data_root="/tmp/a", source_snapshot_id="s",
                                     selected_scope=["a.js"])
        for k in ("repository_id", "commit_sha", "db_id", "source_snapshot_id",
                  "selected_scope"):
            self.assertIn(k, ctx)
        self.assertTrue(ctx["db_path_masked"].startswith("…/"))

    def test_M01_fresh(self):
        plan = self._plan()
        self.assertEqual(CPC.revalidate(
            plan, {"objects": [{"file_path": "a.js",
                                "state": "CONTENT_NOT_CAPTURED",
                                "planned_requests": 1}]},
            data_root="/tmp/a", repository_id="r", commit_sha="c")["state"],
            CPC.FRESH)

    def test_M02_stale(self):
        plan = self._plan()
        fresh = {"objects": [{"file_path": "a.js", "state": "CLAIMS_VERIFIED",
                              "planned_requests": 0}]}
        r = CPC.revalidate(plan, fresh, data_root="/tmp/a",
                           repository_id="r", commit_sha="c")
        self.assertEqual(r["state"], CPC.REVALIDATED)
        self.assertEqual(r["use_inventory"], fresh,
                         "过期计划必须改用新鲜盘点")

    def test_M03_context_mismatch(self):
        plan = self._plan(root="/tmp/a")
        r = CPC.revalidate(plan, {"objects": []}, data_root="/tmp/b",
                           repository_id="r", commit_sha="c")
        self.assertEqual(r["state"], CPC.ABORTED)
        self.assertIn("data_root", r["mismatches"])

    def test_commit_mismatch(self):
        plan = self._plan()
        r = CPC.revalidate(plan, {"objects": []}, data_root="/tmp/a",
                           repository_id="r", commit_sha="other")
        self.assertEqual(r["state"], CPC.ABORTED)

    def test_digest_changes_with_state(self):
        a = CPC.inventory_digest([{"file_path": "x", "state": "A",
                                   "planned_requests": 1}])
        b = CPC.inventory_digest([{"file_path": "x", "state": "B",
                                   "planned_requests": 0}])
        self.assertNotEqual(a, b)

    def test_plan_id_stable(self):
        self.assertEqual(self._plan()["plan_id"], self._plan()["plan_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
