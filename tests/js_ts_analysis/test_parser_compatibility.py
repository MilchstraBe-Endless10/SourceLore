#!/usr/bin/env python3
"""第一层：tree-sitter 运行时与 grammar 兼容。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"js_ts_analysis"))
import sfx
import treesitter_runtime as RT


class TestRuntime(unittest.TestCase):
    def test_all_four_grammars_available(self):
        avail = RT.available_languages()
        for lang in ("javascript", "jsx", "typescript", "tsx"):
            self.assertTrue(avail[lang]["available"],
                            f"{lang}: {avail[lang].get('error')}")

    def test_abi_versions(self):
        avail = RT.available_languages()
        self.assertIsNotNone(avail["javascript"]["abi_version"])
        self.assertIsNotNone(avail["typescript"]["abi_version"])

    def test_ext_mapping(self):
        self.assertEqual(RT.language_for_path("a.js"), "javascript")
        self.assertEqual(RT.language_for_path("a.jsx"), "jsx")
        self.assertEqual(RT.language_for_path("a.ts"), "typescript")
        self.assertEqual(RT.language_for_path("a.tsx"), "tsx")
        self.assertIsNone(RT.language_for_path("a.py"))
        self.assertIsNone(RT.language_for_path("a.md"))

    def test_parse_complete(self):
        t, s, d = RT.parse_bytes(b"function f(){}\n", "javascript")
        self.assertEqual(s, RT.PARSE_COMPLETE)
        self.assertEqual(d["node_count"], d["node_count"])
        self.assertGreater(d["node_count"], 0)

    def test_parse_with_errors(self):
        t, s, d = RT.parse_bytes(b"function ( {", "javascript")
        self.assertEqual(s, RT.PARSE_WITH_ERRORS)
        self.assertTrue(d["has_error"])

    def test_deterministic(self):
        raw = b"class A { m(){} }\n"
        t1, _, _ = RT.parse_bytes(raw, "typescript")
        t2, _, _ = RT.parse_bytes(raw, "typescript")
        self.assertEqual(t1.root_node.end_byte, t2.root_node.end_byte)
        self.assertEqual(t1.root_node.child_count, t2.root_node.child_count)

    def test_node_range_absolute_bytes(self):
        raw = b"function f(){}\n"
        starts, _ = __import__("source_evidence").line_starts_bytes(raw)
        t, _, _ = RT.parse_bytes(raw, "javascript")
        fn = t.root_node.children[0]
        r = RT.node_range(fn, starts, raw)
        self.assertIsNotNone(r)
        sb, eb, sl, el = r
        self.assertEqual(sb, 0)
        self.assertEqual(raw[sb:eb], b"function f(){}")

    def test_no_auto_download(self):
        """★ 运行时代码不得包含下载 grammar 的调用。"""
        src = (ROOT/"src"/"source_analysis"/"treesitter_runtime.py").read_text(
            encoding="utf-8")
        for bad in ("urlopen", "requests.", "pip ", "subprocess"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
