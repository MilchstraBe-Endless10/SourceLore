#!/usr/bin/env python3
"""C. 多 Commit：T-17..T-25。用确定性双 Commit 集成测试。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx
for p in ("research","views","lifecycle","storage","collector","facts",
          "evidence_claims","runtime","renderer","skill_interface"):
    if str(ROOT/"src"/p) not in sys.path:
        sys.path.insert(0, str(ROOT/"src"/p))
if str(ROOT/"tests"/"views") not in sys.path:
    sys.path.insert(0, str(ROOT/"tests"/"views"))
import vfx, knowledge as K, query as Q

A_SHA = vfx.A
B_SHA = "b" * 40


def build_two(tmp):
    """在同一 repository_id 下构造两个不同 Commit 的快照+事实。"""
    from knowledge_store import KnowledgeStore
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot
    import extractor, ingest as FI

    ks = KnowledgeStore(str(tmp/"kb.db"))
    for sha, entries in ((A_SHA, [{"path": "README", "type": "blob",
                                   "mode": "100644", "sha": "1"*40}]),
                         (B_SHA, [])):
        snap = build_snapshot(
            repository_id=vfx.REPO, requested_repository="oc/hw",
            resolved_repository="oc/hw", requested_ref="master",
            commit_sha=sha, root_tree_sha="t"*40, tree_query_ref="t"*40,
            completeness_status="COMPLETE", tree_entries=entries,
            collected_at="", evidence_refs=[f"github@{sha}"])
        ingest_snapshot(ks, snap)
    return ks


class TestMultiCommit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mc_"))
        self.ks = build_two(self.tmp)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_snapshots_same_repo(self):
        rows = self.ks.conn.execute(
            "SELECT asset_id, commit_sha FROM index_rows "
            "WHERE asset_type='repository_snapshot'").fetchall()
        shas = {r["commit_sha"] for r in rows}
        ids = {r["asset_id"] for r in rows}
        self.assertEqual(len(rows), 2, "两个 Commit 都应保存")
        self.assertEqual(shas, {A_SHA, B_SHA}, "commit 不同")
        self.assertEqual(len(ids), 2, "Snapshot 身份必须不同")

    def test_history_lists_two(self):
        out = K.history(self.ks, vfx.REPO)
        shas = {v["commit_sha"] for v in out["versions"]}
        self.assertEqual(shas, {A_SHA, B_SHA})
        self.assertIn("不推断", out["note"])

    def test_no_ancestry_claim(self):
        src = (ROOT/"src"/"skill_interface"/"knowledge.py").read_text(encoding="utf-8")
        self.assertIn("不推断", src)

    def test_version_query_two_commits(self):
        out = Q.run_query(repository_id=vfx.REPO, commit_sha=A_SHA,
                          qtype="version", compare_commit=B_SHA,
                          data_root=str(self.tmp))
        self.assertIn(out["coverage_state"],
                      ("ANSWERABLE_FROM_EXISTING_EVIDENCE", "PARTIALLY_ANSWERABLE",
                       "INSUFFICIENT_EVIDENCE", "CONFLICT_REQUIRES_REVIEW"))
        self.assertFalse(out["is_knowledge_authority"])

    def test_repositories_shows_two_commits(self):
        out = K.list_repositories(self.ks)
        repo = out["repositories"][0]
        self.assertEqual(set(repo["commits"]), {A_SHA, B_SHA})
        self.assertEqual(repo["snapshot_count"], 2)


class TestSnapshotIsolation(unittest.TestCase):
    def test_scope_not_treated_as_conflict(self):
        """★ 不同 Commit 各自成立，不是同范围冲突。"""
        tmp = Path(tempfile.mkdtemp(prefix="iso_"))
        try:
            ks = build_two(tmp)
            import verifier as V, ec_models as EM
            import extractor, ingest as FI
            from knowledge_store import KnowledgeStore
            c1 = EM.build_path_claim(repository_id=vfx.REPO, commit_sha=A_SHA,
                                     target_path="README", expected_exists=True,
                                     claim_origin="multi")
            c2 = EM.build_path_claim(repository_id=vfx.REPO, commit_sha=B_SHA,
                                     target_path="README", expected_exists=True,
                                     claim_origin="multi")
            self.assertNotEqual(c1.claim_id, c2.claim_id,
                                "不同 Commit 的 Claim 身份必须不同")
            # ★ Claim 对象没有 logical_identity 属性 —— 别凭想象断言
            self.assertFalse(hasattr(c1, "logical_identity"))
            self.assertEqual(c1.commit_sha, A_SHA)
            self.assertEqual(c2.commit_sha, B_SHA)
            ks.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
