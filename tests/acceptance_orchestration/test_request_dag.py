#!/usr/bin/env python3
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "collector"))
sys.path.insert(0, str(ROOT / "tests" / "acceptance_orchestration"))
import acceptance_request_planner as A
from gold.orchestration_gold import GOLD


class TestRegistry(unittest.TestCase):
    def test_cases(self):
        self.assertGreaterEqual(len(GOLD), 20)
        ids = [g[0] for g in GOLD]
        self.assertEqual(len(ids), len(set(ids)))


class TestDag(unittest.TestCase):
    def _plan(self, **kw):
        base = dict(repository_id="24313173", commit_sha="c" * 40,
                    target_paths=("README.md", "package.json", "index.js"),
                    license_path="LICENSE")
        base.update(kw)
        return A.build_repo_acceptance_plan(**base)

    def test_A01_operations_covered(self):
        p = self._plan()
        ops = p.by_operation()
        self.assertIn("GET repo metadata", ops)
        self.assertIn("GET tree", ops)
        self.assertIn("GET blob", ops)

    def test_A02_no_commit_ref_when_sha_known(self):
        p = self._plan()
        self.assertNotIn("GET ref", p.by_operation())

    def test_A03_tree_reused(self):
        p = self._plan(have_tree=True, known_tree_sha="t" * 40)
        n = [x for x in p.nodes if x["operation"] == "GET tree"][0]
        self.assertEqual(n["execution_status"], A.NODE_LOCAL_REUSE)

    def test_A04_blob_reused(self):
        p = self._plan(have_blobs=("README.md",))
        n = [x for x in p.nodes
             if x["operation"] == "GET blob"
             and x["source_object_identity"] == "README.md"][0]
        self.assertEqual(n["execution_status"], A.NODE_LOCAL_REUSE)

    def test_A05_A06_dedup_key_includes_identity(self):
        p1 = self._plan()
        n = [x for x in p1.nodes if x["operation"] == "GET blob"][0]
        k1 = p1.dedup_key(n)
        p2 = A.build_repo_acceptance_plan(
            repository_id="24313173", commit_sha="d" * 40,
            target_paths=("README.md",), license_path=None)
        n2 = [x for x in p2.nodes if x["operation"] == "GET blob"][0]
        self.assertNotEqual(k1, p2.dedup_key(n2),
                            "不同 Commit 不得合并")
        p3 = A.build_repo_acceptance_plan(
            repository_id="999", commit_sha="c" * 40,
            target_paths=("README.md",), license_path=None)
        n3 = [x for x in p3.nodes if x["operation"] == "GET blob"][0]
        self.assertNotEqual(p1.dedup_key(n), p3.dedup_key(n3),
                            "不同仓库不得合并")

    def test_A07_min_max_split(self):
        c = self._plan().counts()
        self.assertIn("minimum_required_requests", c)
        self.assertIn("maximum_planned_requests", c)
        self.assertGreater(c["maximum_planned_requests"],
                           c["minimum_required_requests"])

    def test_A08_conditional_not_certain(self):
        c = self._plan().counts()
        self.assertGreater(c["conditional_requests"], 0,
                           "依赖 tree 的 blob 必须是 conditional")


class TestReuseNotCounted(unittest.TestCase):
    """D-56：复用节点不得算作请求。"""

    def test_all_reused_zero_requests(self):
        p = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40, known_tree_sha="t" * 40,
            target_paths=("README.md", "package.json", "index.js"),
            license_path=None, have_tree=True,
            have_blobs=("README.md", "package.json", "index.js"),
            have_metadata=True)
        c = p.counts()
        self.assertEqual(c["minimum_required_requests"], 0)
        self.assertEqual(c["maximum_planned_requests"], 0)
        self.assertEqual(c["local_reuse_nodes"], 5)
        # 口径一致：by_operation 也不得把复用节点算成请求
        self.assertEqual(p.by_operation().get("GET blob"), 0)
        # 复用桶以 0 值保留 key，断言值而非 key 存在与否
        self.assertEqual(p.by_operation().get("GET tree"), 0)
        self.assertEqual(p.by_operation().get("GET repo metadata"), 0)
        # commit 是 optional（已知 SHA 时不必请求），不计入 min/max
        self.assertEqual(c["optional_requests"], 1)
        self.assertEqual(p.by_operation().get("GET commit"), 1)

    def test_license_not_double_counted(self):
        """D-55：LICENSE 在 target_paths 里时不得再追加一次。"""
        p = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("LICENSE", "readme.md", "package.json", "index.js"),
            license_path="LICENSE")
        self.assertEqual(p.by_operation()["GET blob"], 4)


class TestPreflight(unittest.TestCase):
    def _plan(self):
        return A.build_repo_acceptance_plan(
            repository_id="24313173", commit_sha="c" * 40,
            target_paths=("README.md", "package.json", "index.js"),
            license_path="LICENSE")

    def test_A09_blocked_when_insufficient(self):
        r = A.preflight(plan=self._plan(), observed_remaining=3)
        self.assertFalse(r["can_begin"])
        self.assertIn("INSUFFICIENT_REMAINING", r["block_reason"])

    def test_A10_reserve(self):
        p = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("a",), license_path=None, reserve_requests=10)
        # need=3（metadata+tree+blob），reserve=10 → 需 13
        need = A.preflight(plan=p, observed_remaining=13)
        self.assertEqual(need["planned_primary_requests"], 3)
        self.assertTrue(need["can_begin"])
        r = A.preflight(plan=p, observed_remaining=12)
        self.assertFalse(r["can_begin"], "余量不足必须阻断")
        self.assertIn("INSUFFICIENT_REMAINING", r["block_reason"])

    def test_A11_no_header_blocks(self):
        r = A.preflight(plan=self._plan(), observed_remaining=None)
        self.assertFalse(r["can_begin"])
        self.assertIn("NO_AUTHORITATIVE_REMAINING", r["block_reason"])
        self.assertIn("rate_limit", r["next_action"])

    def test_A13_A14_rate_limit_stops(self):
        for kind in ("PRIMARY", "SECONDARY"):
            r = A.preflight(plan=self._plan(), observed_remaining=60,
                            rate_limit_status=kind)
            self.assertFalse(r["can_begin"], kind)

    def test_local_max(self):
        p = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("a", "b", "c", "d"), license_path=None,
            local_max_requests=3)
        r = A.preflight(plan=p, observed_remaining=60)
        self.assertFalse(r["can_begin"])
        self.assertIn("LOCAL_MAX_EXCEEDED", r["block_reason"])

    def test_A18_preflight_not_capture(self):
        r = A.preflight(plan=self._plan(), observed_remaining=60)
        self.assertTrue(r["can_begin"])
        self.assertIn("不等于配额已预留", r["note"])


class TestStages(unittest.TestCase):
    def test_A17_order(self):
        self.assertEqual(A.STAGE_ORDER[0], A.PREFLIGHT)
        self.assertEqual(A.STAGE_ORDER[-1], A.OFFLINE_REUSE_VERIFIED)
        self.assertEqual(len(A.STAGE_ORDER), 10)

    def test_blocked_state(self):
        r = A.preflight(plan=A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("a",), license_path=None), observed_remaining=0)
        s = A.plan_state(preflight_result=r)
        self.assertEqual(s["state"], A.PREFLIGHT_BUDGET_BLOCKED)

    def test_complete_state(self):
        r = A.preflight(plan=A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("a",), license_path=None), observed_remaining=60)
        s = A.plan_state(preflight_result=r,
                         stage_states={A.OFFLINE_REUSE_VERIFIED: A.NODE_DONE})
        self.assertEqual(s["state"], A.E2E_COMPLETE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
