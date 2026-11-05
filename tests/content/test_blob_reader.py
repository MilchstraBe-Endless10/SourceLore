#!/usr/bin/env python3
"""Blob 读取：真实不可用、预算、编码、二进制。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content"))
import sfx
import blob_reader as BR
import content_models as CM
from content_budget import Budget


class TestNotCaptured(unittest.TestCase):
    def test_real_snapshot_has_no_bytes(self):
        """★ P1C/P5A 只存 blob_refs，没有字节 —— 必须明确 NOT_CAPTURED。"""
        snap = {"blob_refs": [{"blob_sha": "980a0d5f19a64b4b30a87d4206aade58726b60e3",
                               "path": "README", "size": 13}]}
        status, text, meta = BR.read_from_snapshot(snap, "README")
        self.assertEqual(status, CM.C_NOT_CAPTURED)
        self.assertIsNone(text)
        self.assertIn("不得凭路径猜测内容", meta["message"])

    def test_missing_path_blob(self):
        snap = {"blob_refs": []}
        status, _, meta = BR.read_from_snapshot(snap, "README")
        self.assertEqual(status, CM.C_NOT_CAPTURED)
        self.assertIn("无该路径", meta["message"])


class TestEncoding(unittest.TestCase):
    def test_bom_stripped(self):
        data = b"\xef\xbb\xbf# T\n"
        st, text, meta = BR.read_text(data=data)
        self.assertEqual(st, CM.C_AVAILABLE)
        self.assertFalse(text.startswith("\ufeff"))
        self.assertTrue(meta["had_bom"])

    def test_crlf(self):
        st, text, meta = BR.read_text(data=b"a\r\nb\r\n")
        self.assertEqual(st, CM.C_AVAILABLE)
        self.assertEqual(meta["line_ending"], "CRLF")

    def test_empty_file(self):
        st, text, meta = BR.read_text(data=b"")
        self.assertEqual(st, CM.C_AVAILABLE)
        self.assertEqual(text, "")
        self.assertEqual(meta["line_count"], 0)

    def test_invalid_utf8(self):
        st, text, meta = BR.read_text(data=b"\xff\xfe# bad")
        self.assertEqual(st, CM.C_BAD_ENCODING)
        self.assertIsNone(text)

    def test_multibyte_unicode(self):
        st, text, meta = BR.read_text(data="# 标题 🎯\n".encode("utf-8"))
        self.assertEqual(st, CM.C_AVAILABLE)
        self.assertIn("🎯", text)

    def test_binary(self):
        st, text, _ = BR.read_text(data=b"\x00\x01\x02binary")
        self.assertEqual(st, CM.C_BINARY)
        self.assertIsNone(text)

    def test_too_large(self):
        big = b"x" * (300 * 1024)
        st, _, meta = BR.read_text(data=big)
        self.assertEqual(st, CM.C_TOO_LARGE)
        self.assertEqual(meta["limit"], 256 * 1024)

    def test_digest_stable(self):
        a = BR.content_digest(b"hello")
        b = BR.content_digest(b"hello")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
