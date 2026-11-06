#!/usr/bin/env python3
"""真缺口盘点 + 计划只读 + 资产复用（真实 SQLite）。"""
import sys, tempfile, shutil, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface",
          "renderer"):
    sys.path.insert(0, str(ROOT / "src" / p))
sys.path.insert(0, str(ROOT / "tests" / "capture_maintenance"))
import capture_request_plan as PLAN
import request_budget as RB
from knowledge_store import KnowledgeStore


def seed_snapshot(store, tree_paths, repo="r1", commit="c" * 40):
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot
    entries = [{"path": p, "sha": ("ab" * 20)[:40], "size": 100,
                "type": "blob", "mode": "100644"} for p in tree_paths]
    snap = build_snapshot(repository_id=repo, requested_repository="x/y",
                          resolved_repository="x/y", requested_ref="main",
                          commit_sha=commit, root_tree_sha="t" * 40,
                          tree_query_ref="t" * 40,
                          completeness_status="COMPLETE",
                          tree_entries=entries, collected_at="",
                          evidence_refs=["e"])
    return ingest_snapshot(store, snap)["asset_id"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p6c_"))
        self.ks = KnowledgeStore(str(self.tmp / "kb.db"))

    def tearDown(self):
        try:
            self.ks.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestInventory(Base):
    def _inv(self, paths=("README.md", "index.js")):
        seed_snapshot(self.ks, paths)
        return PLAN.build_gap_inventory(
            store=self.ks, repository_id="r1", commit_sha="c" * 40,
            content_scope=list(paths))

    def test_R03_missing_blob_planned(self):
        inv = self._inv()
        self.assertTrue(inv["ok"])
        recs = {o["file_path"]: o for o in inv["objects"]}
        self.assertEqual(recs["index.js"]["state"], PLAN.CONTENT_NOT_CAPTURED)
        self.assertEqual(recs["index.js"]["planned_requests"], 1)
        self.assertEqual(inv["planned_requests_total"], 2)

    def test_R04_multi_accumulates(self):
        inv = self._inv(("README.md", "index.js", "package.json"))
        self.assertEqual(inv["planned_requests_total"], 3)

    def test_states_not_collapsed(self):
        inv = self._inv()
        recs = {o["file_path"]: o for o in inv["objects"]}
        # 不能合并成一个 CACHE_HIT：缺内容就必须是 CONTENT_NOT_CAPTURED
        self.assertNotIn("CACHE_HIT", {o["state"] for o in inv["objects"]})

    def test_three_completeness_reported(self):
        inv = self._inv()
        c = inv["completeness"]
        self.assertEqual(c["tree_enumeration"], "COMPLETE")
        self.assertEqual(c["selected_content_capture"], "PARTIAL")
        self.assertEqual(c["knowledge_processing"], "PARTIAL")


class TestPlan(Base):
    def _plan(self):
        seed_snapshot(self.ks, ("README.md", "index.js"))
        inv = PLAN.build_gap_inventory(
            store=self.ks, repository_id="r1", commit_sha="c" * 40,
            content_scope=["README.md", "index.js"])
        budget = RB.GitHubRequestBudget(repository_id="r1",
                                        commit_sha="c" * 40,
                                        execution_id="plan")
        return PLAN.build_request_plan(inventory=inv, budget=budget)

    def test_R05_read_only(self):
        p = self._plan()
        self.assertTrue(p["read_only"])
        self.assertEqual(p["actual_requests"], 0)

    def test_planned_equals_inventory(self):
        p = self._plan()
        self.assertEqual(p["estimated_requests"], 2)

    def test_no_network_field(self):
        p = self._plan()
        self.assertNotIn("network_requests", {k for k, v in p.items()
                                              if v and k == "network"})


class TestReuse(Base):
    def test_R02_reuse_no_fetch(self):
        """已有完整资产 → 采集阶段必须复用，不发请求。"""
        import content_ingest_coordinator as CIC
        seed_snapshot(self.ks, ("README.md",))
        CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="r1",
            commit_sha="c" * 40, source_snapshot_id="snap",
            file_path="README.md", git_blob_oid="ab" * 20,
            git_object_format="sha1", raw=b"# T\n",
            source_declared_size=4,
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")
        meta = CIC.find_content_asset(self.ks, repository_id="r1",
                                      commit_sha="c" * 40,
                                      file_path="README.md")
        self.assertIsNotNone(meta, "资产应可查回")
        inv = PLAN.build_gap_inventory(store=self.ks, repository_id="r1",
                                       commit_sha="c" * 40,
                                       content_scope=["README.md"])
        rec = inv["objects"][0]
        self.assertEqual(rec["state"], PLAN.CONTENT_CAPTURED_BUT_NOT_PARSED)
        self.assertEqual(rec["planned_requests"], 0, "已捕获不应再请求")


if __name__ == "__main__":
    unittest.main(verbosity=2)
