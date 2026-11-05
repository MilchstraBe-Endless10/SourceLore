#!/usr/bin/env python3
"""Git Blob OID 完整性：算法、响应校验、八项拒绝。"""
import sys, unittest, base64
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"blob_capture"))
import sfx
import blob_fetcher as BF

HELLO = b"Hello World!\n"
HELLO_OID = "980a0d5f19a64b4b30a87d4206aade58726b60e3"


class TestOidAlgorithm(unittest.TestCase):
    def test_known_value(self):
        """★ 已知真值：Hello-World README 13 字节。"""
        self.assertEqual(BF.git_blob_oid(HELLO), HELLO_OID)

    def test_not_plain_sha1(self):
        """★ 普通文件 sha1 ≠ Git blob oid。"""
        import hashlib
        self.assertNotEqual(hashlib.sha1(HELLO).hexdigest(),
                            BF.git_blob_oid(HELLO))

    def test_length_prefix_matters(self):
        a = BF.git_blob_oid(b"ab")
        b = BF.git_blob_oid(b"a")
        self.assertNotEqual(a, b)

    def test_sha256_format(self):
        v = BF.git_blob_oid(b"x", fmt="sha256")
        self.assertEqual(len(v), 64)

    def test_unsupported_format_raises(self):
        with self.assertRaises(ValueError):
            BF.git_blob_oid(b"x", fmt="md5")


class TestResponseVerify(unittest.TestCase):
    def _payload(self, raw, oid=None, size=None, enc="base64"):
        return {"sha": oid or BF.git_blob_oid(raw),
                "size": len(raw) if size is None else size,
                "encoding": enc,
                "content": base64.b64encode(raw).decode()}

    def test_happy_path(self):
        got = BF.decode_and_verify(response_payload=self._payload(HELLO),
                                   expected_oid=HELLO_OID, expected_size=13,
                                   max_bytes=1024)
        self.assertEqual(got["status"], BF.OK)
        self.assertEqual(got["raw"], HELLO)
        self.assertEqual(got["git_blob_oid"], HELLO_OID)
        self.assertTrue(got["content_sha256"].startswith("sha256:"))

    def test_wrong_expected_oid(self):
        got = BF.decode_and_verify(response_payload=self._payload(HELLO),
                                   expected_oid="0"*40, max_bytes=1024)
        self.assertNotEqual(got["status"], BF.OK)
        self.assertIsNone(got["raw"])

    def test_size_mismatch(self):
        p = self._payload(HELLO, size=99)
        got = BF.decode_and_verify(response_payload=p, expected_oid=HELLO_OID,
                                   expected_size=99, max_bytes=1024)
        self.assertNotEqual(got["status"], BF.OK)

    def test_bad_base64(self):
        p = {"sha": HELLO_OID, "size": 13, "encoding": "base64",
             "content": "!!!not-base64!!!"}
        got = BF.decode_and_verify(response_payload=p, expected_oid=HELLO_OID,
                                   max_bytes=1024)
        self.assertEqual(got["status"], BF.BAD_BASE64)
        self.assertIsNone(got["raw"])

    def test_wrong_encoding(self):
        p = {"sha": HELLO_OID, "size": 13, "encoding": "utf-8",
             "content": "Hello"}
        got = BF.decode_and_verify(response_payload=p, expected_oid=HELLO_OID)
        self.assertEqual(got["status"], BF.BAD_BASE64)

    def test_too_large_after_decode(self):
        big = b"x" * 5000
        got = BF.decode_and_verify(response_payload=self._payload(big),
                                   expected_oid=BF.git_blob_oid(big),
                                   max_bytes=1000)
        self.assertEqual(got["status"], BF.TOO_LARGE)
        self.assertIsNone(got["raw"])

    def test_transport_budget_before_decode(self):
        """★ 编码后长度先卡一道，不解码就拒。"""
        big = b"x" * 5000
        p = self._payload(big)
        budget = BF.transport_budget(1000)
        self.assertGreater(len(p["content"]), budget)
        got = BF.decode_and_verify(response_payload=p,
                                   expected_oid=BF.git_blob_oid(big),
                                   max_bytes=1000)
        self.assertEqual(got["status"], BF.TOO_LARGE)

    def test_content_tampered_same_sha_field(self):
        """★ 返回 sha 说对、内容却不同 → 计算 OID 必须抓住。"""
        p = {"sha": HELLO_OID, "size": 13, "encoding": "base64",
             "content": base64.b64encode(b"XXXX World!\n").decode()}
        got = BF.decode_and_verify(response_payload=p, expected_oid=HELLO_OID,
                                   max_bytes=1024)
        self.assertNotEqual(got["status"], BF.OK)

    def test_unsupported_git_format(self):
        got = BF.decode_and_verify(response_payload=self._payload(HELLO),
                                   expected_oid=HELLO_OID, max_bytes=1024,
                                   git_object_format="svn")
        self.assertEqual(got["status"], BF.UNSUPPORTED_FORMAT)


class TestSizeGate(unittest.TestCase):
    def test_known_size_ok(self):
        allow, why = BF.declared_size_gate(13, 256*1024)
        self.assertTrue(allow); self.assertIsNone(why)

    def test_known_size_too_large(self):
        allow, why = BF.declared_size_gate(10**7, 256*1024)
        self.assertFalse(allow); self.assertEqual(why, BF.TOO_LARGE)

    def test_unknown_size_skipped(self):
        """★ 未知大小保守跳过 —— 不发请求。"""
        allow, why = BF.declared_size_gate(None, 256*1024)
        self.assertFalse(allow); self.assertEqual(why, BF.UNKNOWN_SIZE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
