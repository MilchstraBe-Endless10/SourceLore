#!/usr/bin/env python3
"""证据范围：字节/行号双向一致、不越界、不跨文件。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content"))
import sfx
import evidence_ranges as ER

DOC = "# A\n\n## B\n内容\n"


class TestRanges(unittest.TestCase):
    def test_line_of_offset(self):
        self.assertEqual(ER.line_of_offset(DOC, 0), 1)
        self.assertEqual(ER.line_of_offset(DOC, 1), 1)
        # ★ 偏移 2 是 "# A\n" 之后的空行位置 —— 仍属第 1 行（换行符在偏移 3）
        self.assertEqual(ER.line_of_offset(DOC, 2), 1)
        # "# A\n" 长度 4：偏移 4 才进入第 2 行
        self.assertEqual(ER.line_of_offset(DOC, 4), 2)
        self.assertEqual(ER.line_of_offset(DOC, len("# A\n\n")), 3)

    def test_multibyte_line_mapping(self):
        """★ 多字节字符不能让行号偏移错位。"""
        t = "# 中文标题\n\n## 第二\n"
        r = ER.build_range(text=t, start_byte=len("# 中文标题\n\n"),
                           end_byte=len("# 中文标题\n\n## 第二"),
                           kind=ER.E_HEADING, file_path="README.md")
        self.assertEqual(r["start_line"], 3)
        ok, why = ER.verify_range(rng=r, text=t)
        self.assertTrue(ok, why)

    def test_crlf_line_mapping(self):
        t = "# A\r\n\r\n## B\r\n"
        start = len("# A\r\n\r\n")
        r = ER.build_range(text=t, start_byte=start,
                           end_byte=start + len("## B"), kind=ER.E_HEADING)
        self.assertEqual(r["start_line"], 3)

    def test_reject_out_of_bounds(self):
        with self.assertRaises(ER.RangeError) as cm:
            ER.build_range(text="abc", start_byte=0, end_byte=99, kind=ER.E_FIELD)
        self.assertEqual(cm.exception.code, "RANGE_BEYOND_CONTENT")

    def test_reject_empty(self):
        with self.assertRaises(ER.RangeError):
            ER.build_range(text="abc", start_byte=1, end_byte=1, kind=ER.E_FIELD)

    def test_reject_bad_kind(self):
        with self.assertRaises(ER.RangeError):
            ER.build_range(text="abc", start_byte=0, end_byte=2, kind="nonsense")

    def test_verify_detects_tampering(self):
        """★ 篡改行号必须被发现。"""
        r = ER.build_range(text=DOC, start_byte=0, end_byte=3, kind=ER.E_HEADING,
                           file_path="README.md", git_blob_oid="oid1")
        r["start_line"] = 99
        ok, why = ER.verify_range(rng=r, text=DOC,
                                  file_path="README.md", git_blob_oid="oid1")
        self.assertFalse(ok)
        self.assertIn("LINE_MISMATCH", why)

    def test_verify_detects_wrong_blob(self):
        r = ER.build_range(text=DOC, start_byte=0, end_byte=3, kind=ER.E_HEADING,
                           file_path="README.md", git_blob_oid="oid1")
        ok, why = ER.verify_range(rng=r, text=DOC, git_blob_oid="oid2")
        self.assertFalse(ok)
        self.assertIn("BLOB_MISMATCH", why)

    def test_verify_detects_wrong_path(self):
        r = ER.build_range(text=DOC, start_byte=0, end_byte=3, kind=ER.E_HEADING,
                           file_path="README.md", git_blob_oid="o")
        ok, why = ER.verify_range(rng=r, text=DOC, file_path="OTHER.md")
        self.assertFalse(ok)
        self.assertIn("PATH_MISMATCH", why)

    def test_complete_ref_has_all_fields(self):
        r = ER.build_range(text=DOC, start_byte=0, end_byte=3, kind=ER.E_HEADING,
                           file_path="README.md", git_blob_oid="o")
        ref = ER.to_evidence_ref(rng=r, repository_id="1", commit_sha="a"*40,
                                 content_asset_id="A1", content_digest="d1",
                                 parser_version="1")
        self.assertTrue(ER.ref_complete(ref))

    def test_incomplete_ref_rejected(self):
        ref = {"repository_id": "1", "commit_sha": "", "file_path": "x",
               "git_blob_oid": None, "content_asset_id": None,
               "content_digest": None, "start_line": 1, "end_line": 2,
               "start_byte": 0, "end_byte": 5, "evidence_kind": "x",
               "parser_version": None}
        self.assertFalse(ER.ref_complete(ref))


if __name__ == "__main__":
    unittest.main(verbosity=2)
