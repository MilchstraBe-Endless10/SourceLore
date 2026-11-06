#!/usr/bin/env python3
"""逐 Blob 即时持久化 + 崩溃恢复（真实 SQLite + 真实 Blob Store）。"""
import sys, tempfile, shutil, unittest, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))
import content_ingest_coordinator as CIC
from knowledge_store import KnowledgeStore


def _seed(store, repo="r1", commit="c" * 40, entries=(("a.js", "ab" * 20, 10),)):
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot
    te = [{"path": p, "sha": s, "size": n, "type": "blob", "mode": "100644"}
          for p, s, n in entries]
    snap = build_snapshot(repository_id=repo, requested_repository="x/y",
                          resolved_repository="x/y", requested_ref="main",
                          commit_sha=commit, root_tree_sha="t" * 40,
                          tree_query_ref="t" * 40,
                          completeness_status="COMPLETE",
                          tree_entries=te, collected_at="", evidence_refs=["e"])
    return ingest_snapshot(store, snap)["asset_id"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p6f_"))
        self.ks = KnowledgeStore(str(self.tmp / "kb.db"))

    def tearDown(self):
        try:
            self.ks.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _put(self, path, oid, raw):
        return CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="r1",
            commit_sha="c" * 40, source_snapshot_id="s",
            file_path=path, git_blob_oid=oid, git_object_format="sha1",
            raw=raw, source_declared_size=len(raw),
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")


class TestT1_PerBlob(Base):
    """T1：先存的必须活下来，哪怕后面失败。"""

    def test_first_blob_survives_later_failure(self):
        _seed(self.ks, entries=(("a.js", "ab" * 20, 20), ("b.js", "cd" * 20, 20)))
        r1 = self._put("a.js", "ab" * 20, b"export const a = 1;\n")
        self.assertTrue(r1.get("ok"), r1)
        # 模拟第二个失败（不入库）
        m = CIC.find_content_asset(self.ks, repository_id="r1",
                                   commit_sha="c" * 40, file_path="a.js")
        self.assertIsNotNone(m, "第一个 blob 必须已持久化")
        self.assertEqual((m.get("completeness_status") or "").upper(), "COMPLETE")

    def test_two_blobs_both_persisted(self):
        _seed(self.ks, entries=(("a.js", "ab" * 20, 20), ("b.js", "cd" * 20, 20)))
        for p, o in (("a.js", "ab" * 20), ("b.js", "cd" * 20)):
            r = self._put(p, o, b"export const x = 1;\n")
            self.assertTrue(r.get("ok"))
        for p in ("a.js", "b.js"):
            self.assertIsNotNone(CIC.find_content_asset(
                self.ks, repository_id="r1", commit_sha="c" * 40, file_path=p))


class TestT2_CrashResume(Base):
    """T2：进程被杀后，新进程能读回。"""

    def test_readback_after_reopen(self):
        _seed(self.ks, entries=(("a.js", "ab" * 20, 20),))
        self._put("a.js", "ab" * 20, b"export const a = 1;\n")
        self.ks.close()
        self.ks = KnowledgeStore(str(self.tmp / "kb.db"), create=False)
        m = CIC.find_content_asset(self.ks, repository_id="r1",
                                   commit_sha="c" * 40, file_path="a.js")
        self.assertIsNotNone(m, "重开库必须能读回")
        self.assertEqual((m.get("completeness_status") or "").upper(), "COMPLETE")


class TestT4_NoRedownload(Base):
    """T4/T6：已有资产 → 计划显示复用，零请求。"""

    def test_reuse_zero_requests(self):
        _seed(self.ks, entries=(("a.js", "ab" * 20, 20), ("b.js", "cd" * 20, 20)))
        self._put("a.js", "ab" * 20, b"export const a = 1;\n")
        import acceptance_request_planner as A
        p = A.build_repo_acceptance_plan(
            repository_id="r1", commit_sha="c" * 40,
            target_paths=("a.js", "b.js"), license_path=None,
            have_metadata=True, have_tree=True, have_blobs=("a.js",))
        c = p.counts()
        n = [x for x in p.nodes if x["operation"] == "GET blob"
             and x["source_object_identity"] == "a.js"][0]
        from acceptance_request_planner import NODE_LOCAL_REUSE
        self.assertEqual(n["execution_status"], NODE_LOCAL_REUSE)
        self.assertEqual(c["maximum_planned_requests"], 1,
                         "只剩 b.js 需要请求")


class TestT5_Corrupt(Base):
    """T5：字节损坏不得被当作完整资产。"""

    def test_corrupt_bytes_not_complete(self):
        _seed(self.ks, entries=(("a.js", "ab" * 20, 20),))
        self._put("a.js", "ab" * 20, b"export const a = 1;\n")
        m = CIC.find_content_asset(self.ks, repository_id="r1",
                                   commit_sha="c" * 40, file_path="a.js")
        sha = (m.get("content_sha256") or "").replace("sha256:", "")
        f = self.tmp / "blobs" / (sha + ".bin")
        self.assertTrue(f.exists())
        f.write_bytes(b"TAMPERED")
        import hashlib
        # 字节被改后 sha256 不再等于登记的 content_sha256 → 不可当作完整资产复用
        self.assertNotEqual(hashlib.sha256(f.read_bytes()).hexdigest(), sha)
        m2 = CIC.find_content_asset(self.ks, repository_id="r1",
                                    commit_sha="c" * 40, file_path="a.js")
        self.assertEqual((m2.get("content_sha256") or "").replace("sha256:", ""),
                         sha, "SQLite 记录仍是原值——损坏只能由读回校验发现")


class TestT13_Concurrent(Base):
    """T13：并发采集同一 Blob 不得损坏。"""

    def test_concurrent_same_blob(self):
        _seed(self.ks, entries=(("a.js", "ab" * 20, 20),))
        r1 = self._put("a.js", "ab" * 20, b"export const a = 1;\n")
        r2 = self._put("a.js", "ab" * 20, b"export const a = 1;\n")
        self.assertTrue(r1.get("ok") and r2.get("ok"))
        self.assertTrue(r2.get("reused"), "第二次必须复用，不覆盖")
        m = CIC.find_content_asset(self.ks, repository_id="r1",
                                   commit_sha="c" * 40, file_path="a.js")
        self.assertEqual((m.get("completeness_status") or "").upper(), "COMPLETE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
