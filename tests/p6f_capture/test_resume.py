#!/usr/bin/env python3
"""--resume 恢复盘点：只读、零网络、按 Storage 算缺口。"""
import sys, tempfile, shutil, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))
import capture_resume_report as CRR
import content_ingest_coordinator as CIC
from knowledge_store import KnowledgeStore


class TestResume(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p6f_rs_"))
        self.ks = KnowledgeStore(str(self.tmp / "kb.db"))

    def tearDown(self):
        try:
            self.ks.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, paths):
        from source_snapshot import build_snapshot
        from ingest_coordinator import ingest_snapshot
        te = [{"path": p, "sha": "ab" * 20, "size": 20, "type": "blob",
               "mode": "100644"} for p in paths]
        snap = build_snapshot(repository_id="r1", requested_repository="o/r",
                              resolved_repository="o/r", requested_ref="main",
                              commit_sha="c" * 40, root_tree_sha="t" * 40,
                              tree_query_ref="t" * 40,
                              completeness_status="COMPLETE",
                              tree_entries=te, collected_at="", evidence_refs=["e"])
        return ingest_snapshot(self.ks, snap)["asset_id"]

    def _put(self, path, sid=None):
        sid = sid or self._seed([path])
        return CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="r1",
            commit_sha="c" * 40, source_snapshot_id=sid, file_path=path,
            git_blob_oid="ab" * 20, git_object_format="sha1",
            raw=b"export default 1;\n", source_declared_size=15,
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")

    def test_resume_zero_network(self):
        sid = self._seed(["a.js", "b.js"])
        self._put("a.js", sid=sid)
        self.ks.close()
        r = CRR.inventory(data_root=self.tmp, repository_id="r1",
                          commit="c" * 40, content_paths=["a.js", "b.js"])
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["network_requests"], 0)
        self.assertEqual([x["file_path"] for x in r["persisted_verified"]], ["a.js"])
        self.assertEqual([x["file_path"] for x in r["missing"]], ["b.js"])
        self.assertEqual(r["planned_requests"], 1)

    def test_resume_all_done(self):
        self._seed(["a.js"])
        self._put("a.js")
        self.ks.close()
        r = CRR.inventory(data_root=self.tmp, repository_id="r1",
                          commit="c" * 40, content_paths=["a.js"])
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["planned_requests"], 0)
        self.assertIn("无需采集", r["next_action"])

    def test_resume_read_only(self):
        """盘点不得写入任何资产。"""
        self._seed(["a.js", "b.js"])
        self.ks.close()
        before = None
        import sqlite3
        db = str(self.tmp / "kb.db")
        con = sqlite3.connect(db)
        before = con.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        con.close()
        CRR.inventory(data_root=self.tmp, repository_id="r1",
                      commit="c" * 40, content_paths=["a.js", "b.js"])
        con = sqlite3.connect(db)
        after = con.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        con.close()
        self.assertEqual(before, after, "恢复盘点必须只读")


if __name__ == "__main__":
    unittest.main(verbosity=2)
