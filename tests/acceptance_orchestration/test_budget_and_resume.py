#!/usr/bin/env python3
"""全局预算、去重、恢复（真实 SQLite 与真实 Blob Store）。"""
import sys, tempfile, shutil, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))
import acceptance_request_planner as A
import acceptance_execution_coordinator as EC
import request_budget as RB
import capture_plan_consistency as CPC
from knowledge_store import KnowledgeStore


class TestBudgetModule(unittest.TestCase):
    def test_A12_bootstrap_constant(self):
        self.assertEqual(A.BOOTSTRAP_ENDPOINT, "GET /rate_limit")

    def test_budget_exhausted_raised(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        c = EC.Coordinator(budget=b, dry_run=True)
        with self.assertRaises(EC.BudgetExhausted):
            c.call(path="/x", purpose="test")

    def test_dry_run_no_call(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        b.observe(headers={"X-RateLimit-Remaining": "50"}, status=200)
        c = EC.Coordinator(budget=b, dry_run=True)
        self.assertIsNone(c.call(path="/x", purpose="test"))
        self.assertEqual(len(c.calls), 0)

    def test_duplicate_detection(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        c = EC.Coordinator(budget=b, dry_run=True)
        c.calls = [{"endpoint": "/a", "object_identity": "x"},
                   {"endpoint": "/a", "object_identity": "x"},
                   {"endpoint": "/b", "object_identity": "y"}]
        self.assertEqual(c._duplicates(), 1)


class TestConsistencyIntegration(unittest.TestCase):
    def test_stale_plan_revalidated_then_reuse(self):
        objs_old = [{"file_path": "a.js", "state": "CONTENT_NOT_CAPTURED",
                     "planned_requests": 1}]
        ctx = CPC.build_plan_context(repository_id="r", commit_sha="c",
                                     data_root="/tmp/z", source_snapshot_id="s",
                                     selected_scope=["a.js"])
        plan = CPC.finalize_plan(context=ctx,
                                 inventory={"objects": objs_old,
                                            "planned_requests_total": 1})
        objs_new = [{"file_path": "a.js", "state": "CLAIMS_VERIFIED",
                     "planned_requests": 0}]
        r = CPC.revalidate(plan, {"objects": objs_new}, data_root="/tmp/z",
                           repository_id="r", commit_sha="c")
        self.assertEqual(r["state"], CPC.REVALIDATED)
        self.assertEqual(r["use_inventory"]["objects"][0]["planned_requests"], 0,
                         "存储变化后不得按旧计划再发请求")


class TestReuseWithStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p6e_"))
        self.ks = KnowledgeStore(str(self.tmp / "kb.db"))

    def tearDown(self):
        try:
            self.ks.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_A15_A16_existing_blob_zero_requests(self):
        import content_ingest_coordinator as CIC
        from source_snapshot import build_snapshot
        from ingest_coordinator import ingest_snapshot
        entries = [{"path": "index.js", "sha": "ab" * 20, "size": 10,
                    "type": "blob", "mode": "100644"}]
        snap = build_snapshot(repository_id="r", requested_repository="x/y",
                              resolved_repository="x/y", requested_ref="main",
                              commit_sha="c" * 40, root_tree_sha="t" * 40,
                              tree_query_ref="t" * 40,
                              completeness_status="COMPLETE",
                              tree_entries=entries, collected_at="",
                              evidence_refs=["e"])
        ingest_snapshot(self.ks, snap)
        CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="r",
            commit_sha="c" * 40, source_snapshot_id="s",
            file_path="index.js", git_blob_oid="ab" * 20,
            git_object_format="sha1", raw=b"export default 1;",
            source_declared_size=17,
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")
        meta = CIC.find_content_asset(self.ks, repository_id="r",
                                      commit_sha="c" * 40,
                                      file_path="index.js")
        self.assertIsNotNone(meta)
        # 计划阶段就应识别为已完整
        plan = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("index.js",), license_path=None,
            have_blobs=("index.js",))
        n = [x for x in plan.nodes if x["operation"] == "GET blob"][0]
        self.assertEqual(n["execution_status"], A.NODE_LOCAL_REUSE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
