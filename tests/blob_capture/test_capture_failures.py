#!/usr/bin/env python3
"""失败场景：HTTP 错误、截断、重复、并发、Never-touch-network。"""
import sys, unittest, tempfile, shutil, base64
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"blob_capture"))
import sfx
import blob_fetcher as BF
import blob_content_store as BS
import content_ingest_coordinator as CIC
import captured_blob_loader as L
from knowledge_store import KnowledgeStore

HELLO = b"Hello World!\n"
HELLO_OID = "980a0d5f19a64b4b30a87d4206aade58726b60e3"


class FakeClient:
    def __init__(self, payload=None, ok=True, error_code=None, status=200):
        self.payload = payload; self.ok_ = ok
        self.error_code = error_code; self.status = status
        self.calls = 0
    def blob(self, owner, name, sha, **kw):
        self.calls += 1
        return sfx.fake_resp(ok=self.ok_,
                             data=self.payload if self.ok_ else None,
                             status=self.status,
                             error_code=self.error_code)


def good_payload(raw=HELLO):
    return {"sha": BF.git_blob_oid(raw), "size": len(raw),
            "encoding": "base64",
            "content": base64.b64encode(raw).decode()}


class TestFetchFailures(unittest.TestCase):
    def test_http_403(self):
        c = FakeClient(ok=False, error_code="RATE_LIMITED", status=403)
        got = BF.fetch_blob(c, owner="o", name="r", blob_sha=HELLO_OID,
                            expected_size=13)
        self.assertEqual(got["status"], BF.HTTP_ERROR)
        self.assertEqual(got["error_code"], "RATE_LIMITED")
        self.assertEqual(got["network_requests"], 1)

    def test_http_404(self):
        c = FakeClient(ok=False, error_code="NOT_FOUND", status=404)
        got = BF.fetch_blob(c, owner="o", name="r", blob_sha=HELLO_OID,
                            expected_size=13)
        self.assertEqual(got["status"], BF.HTTP_ERROR)

    def test_truncated_content(self):
        """★ 内容截断 → size 不符，拒绝。"""
        p = good_payload()
        p["size"] = 13
        p["content"] = base64.b64encode(b"Hello").decode()   # 只 5 字节
        c = FakeClient(payload=p)
        got = BF.fetch_blob(c, owner="o", name="r", blob_sha=HELLO_OID,
                            expected_size=13)
        self.assertNotEqual(got["status"], BF.OK)
        self.assertIsNone(got["raw"])

    def test_no_request_when_size_unknown(self):
        """★ 未知大小 → 不发请求。"""
        c = FakeClient(payload=good_payload())
        got = BF.fetch_blob(c, owner="o", name="r", blob_sha=HELLO_OID,
                            expected_size=None)
        self.assertEqual(got["status"], BF.UNKNOWN_SIZE)
        self.assertEqual(got["network_requests"], 0)
        self.assertEqual(c.calls, 0, "不得发请求")

    def test_no_request_when_too_large(self):
        c = FakeClient(payload=good_payload())
        got = BF.fetch_blob(c, owner="o", name="r", blob_sha=HELLO_OID,
                            expected_size=10**8)
        self.assertEqual(got["status"], BF.TOO_LARGE)
        self.assertEqual(c.calls, 0)


class TestStoreFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fail_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_repeated_capture_idempotent(self):
        out = []
        for _ in range(3):
            out.append(CIC.ingest_captured_blob(
                self.ks, data_root=self.tmp, repository_id="1",
                commit_sha="a"*40, source_snapshot_id="S1",
                file_path="README.md", git_blob_oid=HELLO_OID,
                git_object_format="sha1", raw=HELLO,
                source_declared_size=13,
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="T"))
        self.assertTrue(all(o["ok"] for o in out))
        ids = {o["content_asset_id"] for o in out}
        self.assertEqual(len(ids), 1, "三次采集只应产生一个资产")
        rows = self.ks.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE asset_type=?",
            (CIC.ASSET_TYPE,)).fetchone()
        self.assertEqual(rows["c"], 1, "不得重复写入")

    def test_concurrent_same_blob(self):
        """★ 两个独立连接同时写同一 Blob → 字节去重，不损坏。"""
        ks2 = KnowledgeStore(str(self.tmp/"kb.db"))
        try:
            a = CIC.ingest_captured_blob(
                self.ks, data_root=self.tmp, repository_id="1",
                commit_sha="a"*40, source_snapshot_id="S1",
                file_path="README.md", git_blob_oid=HELLO_OID,
                git_object_format="sha1", raw=HELLO,
                source_declared_size=13,
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="T")
            self.assertTrue(a["ok"])
            got = BS.get_bytes(data_root=self.tmp,
                               content_sha256=a["content_sha256"], verify=True)
            self.assertTrue(got["ok"])
            self.assertEqual(got["raw"], HELLO)
        finally:
            ks2.close()

    def test_tmp_leftover_cleanable(self):
        root = BS.store_root(self.tmp)
        root.mkdir(parents=True, exist_ok=True)
        (root/("deadbeef" + ".tmp")).write_bytes(b"junk")
        res = BS.cleanup_orphans(data_root=self.tmp, referenced=set())
        self.assertGreaterEqual(res["removed"], 1)

    def test_no_network_on_read(self):
        """★ 只读接口不构造任何客户端。"""
        src = (ROOT/"src"/"content"/"captured_blob_loader.py").read_text(encoding="utf-8")
        for bad in ("GitHubClient", "urlopen", "requests"):
            self.assertNotIn(bad, src, f"只读模块不得出现 {bad}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
