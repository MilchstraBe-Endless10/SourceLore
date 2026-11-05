#!/usr/bin/env python3
"""存储持久化 + 离线读回 + 幂等 + 篡改检测（全合成）。"""
import sys, unittest, tempfile, shutil, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"blob_capture"))
import sfx
import blob_content_store as BS
import content_ingest_coordinator as CIC
import captured_blob_loader as L
from knowledge_store import KnowledgeStore

REPO = "770001"
COMMIT_A = "a"*40
COMMIT_B = "b"*40
README = b"# Demo\n\n## Install\n"
OID_README = "0"*40


def _oid(raw):
    import blob_fetcher as BF
    return BF.git_blob_oid(raw)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="blob_"))
        self.db = self.tmp/"kb.db"
        self.ks = KnowledgeStore(str(self.db))
        self.root = self.tmp

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestStore(Base):
    def test_put_get_roundtrip(self):
        raw = b"exact bytes \x00\x01 with nul"
        put = BS.put_bytes(data_root=self.root, raw=raw)
        self.assertTrue(put["ok"])
        got = BS.get_bytes(data_root=self.root,
                           content_sha256=put["digest"], verify=True)
        self.assertTrue(got["ok"])
        self.assertEqual(got["raw"], raw)

    def test_idempotent_same_content(self):
        raw = b"same"
        a = BS.put_bytes(data_root=self.root, raw=raw)
        b = BS.put_bytes(data_root=self.root, raw=raw)
        self.assertTrue(a["ok"] and b["ok"])
        self.assertFalse(a["reused"])
        self.assertTrue(b["reused"], "第二次应复用")
        self.assertEqual(a["path"], b["path"])

    def test_tamper_detected(self):
        put = BS.put_bytes(data_root=self.root, raw=b"original")
        Path(put["path"]).write_bytes(b"tampered!!")
        got = BS.get_bytes(data_root=self.root,
                           content_sha256=put["digest"], verify=True)
        self.assertFalse(got["ok"])
        self.assertEqual(got["error"], BS.INTEGRITY_FAILED)

    def test_missing_asset(self):
        got = BS.get_bytes(data_root=self.root,
                           content_sha256="sha256:" + "9"*64, verify=True)
        self.assertEqual(got["error"], BS.ASSET_MISSING)

    def test_digest_expectation_enforced(self):
        put = BS.put_bytes(data_root=self.root, raw=b"abc",
                           expected_sha256="sha256:" + "0"*64)
        self.assertFalse(put["ok"])
        self.assertEqual(put["error"], BS.INTEGRITY_FAILED)

    def test_orphan_cleanup_keeps_referenced(self):
        a = BS.put_bytes(data_root=self.root, raw=b"keep")
        b = BS.put_bytes(data_root=self.root, raw=b"drop")
        d = a["digest"].split("sha256:")[1]
        res = BS.cleanup_orphans(data_root=self.root, referenced={d})
        self.assertEqual(res["kept"], 1)
        self.assertEqual(res["removed"], 1)
        self.assertTrue(Path(a["path"]).exists())
        self.assertFalse(Path(b["path"]).exists())


class TestIngestAndReload(Base):
    def _ingest(self, raw, commit=COMMIT_A, path="README.md", policy="ACQUISITION_ALLOWED"):
        return CIC.ingest_captured_blob(
            self.ks, data_root=self.root, repository_id=REPO,
            commit_sha=commit, source_snapshot_id="SL-A-SNAP-1",
            file_path=path, git_blob_oid=_oid(raw), git_object_format="sha1",
            raw=raw, source_declared_size=len(raw),
            acquisition_policy=policy, acquisition_policy_ref="TEST")

    def test_ingest_then_reload(self):
        got = self._ingest(README)
        self.assertTrue(got["ok"])
        back = L.load_captured_blob(store=self.ks, data_root=self.root,
                                    repository_id=REPO, commit_sha=COMMIT_A,
                                    file_path="README.md")
        self.assertEqual(back["status"], BS.AVAILABLE_VERIFIED)
        self.assertEqual(back["raw"], README)
        self.assertEqual(back["byte_length"], len(README))

    def test_ingest_idempotent(self):
        a = self._ingest(README)
        b = self._ingest(README)
        self.assertTrue(a["ok"] and b["ok"])
        self.assertFalse(a["reused"])
        self.assertTrue(b["reused"], "同内容同身份应复用，不重复写")
        self.assertEqual(a["content_asset_id"], b["content_asset_id"])

    def test_not_captured(self):
        back = L.load_captured_blob(store=self.ks, data_root=self.root,
                                    repository_id=REPO, commit_sha=COMMIT_A,
                                    file_path="never.md")
        self.assertEqual(back["status"], BS.NOT_CAPTURED)

    def test_commit_mismatch(self):
        self._ingest(README, commit=COMMIT_A)
        back = L.load_captured_blob(store=self.ks, data_root=self.root,
                                    repository_id=REPO, commit_sha=COMMIT_B,
                                    file_path="README.md")
        self.assertEqual(back["status"], BS.COMMIT_MISMATCH)
        self.assertIsNone(back["raw"])

    def test_acquisition_blocked(self):
        self._ingest(README, policy="AUTHORIZATION_UNKNOWN")
        back = L.load_captured_blob(store=self.ks, data_root=self.root,
                                    repository_id=REPO, commit_sha=COMMIT_A,
                                    file_path="README.md")
        self.assertEqual(back["status"], BS.ACQUISITION_BLOCKED)
        self.assertIsNone(back["raw"])

    def test_bytes_lost_after_asset(self):
        got = self._ingest(README)
        pl = CIC.find_content_asset(self.ks, repository_id=REPO,
                                    commit_sha=COMMIT_A, file_path="README.md")
        path = BS._path_for(BS.store_root(self.root),
                            pl["content_sha256"].split("sha256:")[1])
        path.unlink()
        back = L.load_captured_blob(store=self.ks, data_root=self.root,
                                    repository_id=REPO, commit_sha=COMMIT_A,
                                    file_path="README.md")
        self.assertEqual(back["status"], BS.ASSET_MISSING)

    def test_same_blob_diff_path_distinct_identity(self):
        a = self._ingest(README, path="README.md")
        b = self._ingest(README, path="docs/README.md")
        self.assertNotEqual(a.get("content_asset_id"), b.get("content_asset_id"),
                            "同 Blob 不同路径必须各自来源身份")

    def test_same_blob_diff_commit_distinct(self):
        a = self._ingest(README, commit=COMMIT_A)
        b = self._ingest(README, commit=COMMIT_B)
        self.assertNotEqual(a.get("content_asset_id"), b.get("content_asset_id"))

    def test_a_layer_payload_has_commit(self):
        got = self._ingest(README)
        rows = self.ks.conn.execute(
            "SELECT commit_sha FROM index_rows WHERE asset_type=?",
            (CIC.ASSET_TYPE,)).fetchall()
        self.assertEqual(rows[0]["commit_sha"], COMMIT_A,
                         "索引 commit_sha 必须可用（P5B 回退生效）")

    def test_no_token_in_payload(self):
        got = self._ingest(README)
        import json
        pl = CIC.find_content_asset(self.ks, repository_id=REPO,
                                    commit_sha=COMMIT_A, file_path="README.md")
        blob = json.dumps(pl, ensure_ascii=False).lower()
        for bad in ("ghp_", "github_token", "authorization"):
            self.assertNotIn(bad, blob)

    def test_distribution_still_false(self):
        self._ingest(README)
        pl = CIC.find_content_asset(self.ks, repository_id=REPO,
                                    commit_sha=COMMIT_A, file_path="README.md")
        self.assertFalse(pl["distribution_allowed"])
        self.assertFalse(pl["copy_permitted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
