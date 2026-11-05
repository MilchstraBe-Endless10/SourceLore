#!/usr/bin/env python3
"""JSONC 解析（必须正确区分字符串与注释）。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"module_resolution"))
import sfx
import tsconfig_jsonc as JC


class TestJsonc(unittest.TestCase):
    def test_line_comment(self):
        d = JC.parse_jsonc('{\n"a": 1 // c\n}')
        self.assertEqual(d["a"], 1)

    def test_block_comment(self):
        d = JC.parse_jsonc('{\n/* c */ "a": 1\n}')
        self.assertEqual(d["a"], 1)

    def test_trailing_comma_object(self):
        self.assertEqual(JC.parse_jsonc('{"a": 1,}'), {"a": 1})

    def test_trailing_comma_array(self):
        self.assertEqual(JC.parse_jsonc('{"a": [1,2,]}'), {"a": [1, 2]})

    def test_url_inside_string(self):
        """★ 阻断级：字符串里的 // 不能被当注释。"""
        d = JC.parse_jsonc('{"u": "https://example.com/x"}')
        self.assertEqual(d["u"], "https://example.com/x")

    def test_slashes_inside_string(self):
        d = JC.parse_jsonc('{"t": "text // not a comment"}')
        self.assertEqual(d["t"], "text // not a comment")

    def test_block_marker_inside_string(self):
        d = JC.parse_jsonc('{"t": "/* keep */"}')
        self.assertEqual(d["t"], "/* keep */")

    def test_escape(self):
        d = JC.parse_jsonc('{"t": "a\\"b"}')
        self.assertEqual(d["t"], 'a"b')

    def test_multiple_comments(self):
        src = '{\n// one\n"a": 1, /* two */\n"b": 2 // three\n}'
        d = JC.parse_jsonc(src)
        self.assertEqual(d, {"a": 1, "b": 2})

    def test_invalid_json(self):
        with self.assertRaises(JC.JsoncError) as cm:
            JC.parse_jsonc('{"a": }')
        self.assertEqual(cm.exception.code, "JSONC_INVALID_JSON")

    def test_unterminated_string(self):
        with self.assertRaises(JC.JsoncError) as cm:
            JC.parse_jsonc('{"a": "x')
        self.assertEqual(cm.exception.code, "JSONC_UNTERMINATED")

    def test_unterminated_block(self):
        with self.assertRaises(JC.JsoncError) as cm:
            JC.parse_jsonc('{ /* x')
        self.assertEqual(cm.exception.code, "JSONC_UNTERMINATED")

    def test_top_level_not_object(self):
        with self.assertRaises(JC.JsoncError) as cm:
            JC.parse_jsonc('[1,2]')
        self.assertEqual(cm.exception.code, "JSONC_NOT_OBJECT")

    def test_too_large(self):
        big = '{"a": "' + "x" * (600 * 1024) + '"}'
        with self.assertRaises(JC.JsoncError) as cm:
            JC.parse_jsonc(big)
        self.assertEqual(cm.exception.code, "JSONC_TOO_LARGE")

    def test_bom(self):
        d = JC.parse_jsonc_bytes(b'\xef\xbb\xbf{"a": 1}')
        self.assertEqual(d["a"], 1)

    def test_crlf(self):
        d = JC.parse_jsonc('{\r\n"a": 1 // c\r\n}')
        self.assertEqual(d["a"], 1)

    def test_no_regex_comment_strip(self):
        """★ 实现必须用状态机，不得用正则删注释。"""
        src = (ROOT/"src"/"source_analysis"/"tsconfig_jsonc.py").read_text(
            encoding="utf-8")
        self.assertNotIn("re.sub", src)
        self.assertNotIn("re.compile", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
