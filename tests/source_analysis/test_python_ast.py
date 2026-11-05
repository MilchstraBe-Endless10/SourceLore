#!/usr/bin/env python3
"""第一层：Python AST 解析 + 字节/行号证据。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"source_analysis"))
import sfx
import python_ast_parser as P
import source_evidence as SE
import source_models as SM
import blob_fetcher as BF


def parse(raw, path="m.py"):
    return P.parse_source(raw, repository_id="990001", commit_sha="a"*40,
                          file_path=path, git_blob_oid=BF.git_blob_oid(raw)
                          if False else "b"*40,
                          content_asset_id="SL-A-x",
                          content_sha256="sha256:"+"0"*64)


class TestEvidence(unittest.TestCase):
    def test_lf_line_starts(self):
        raw = b"a\nbb\nccc\n"
        starts, _ = SE.line_starts_bytes(raw)
        self.assertEqual(starts[:3], [0, 2, 5])

    def test_crlf_line_starts(self):
        raw = b"a\r\nbb\r\n"
        starts, _ = SE.line_starts_bytes(raw)
        self.assertEqual(starts[0], 0)
        self.assertEqual(starts[1], 3)

    def test_chinese_comment_byte_offsets(self):
        """★ 中文注释：AST 列偏移是字节，不是字符索引。"""
        raw = "# 中文注释\ns = 1\n".encode("utf-8")
        starts, _ = SE.line_starts_bytes(raw)
        self.assertEqual(starts[1], len("# 中文注释\n".encode("utf-8")))

    def test_bom_stripped(self):
        raw = b"\xef\xbb\xbfdef f():\n    pass\n"
        text, enc, bom = SE.decode_source(raw)
        self.assertTrue(bom)
        o = P.parse_source(raw, repository_id="1", commit_sha="a"*40,
                           file_path="m.py", git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")
        self.assertEqual(len(o["observed_symbols"]), 1)

    def test_invalid_encoding(self):
        raw = b"\xff\xfe bad"
        o = P.parse_source(raw, repository_id="1", commit_sha="a"*40,
                           file_path="m.py", git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")
        self.assertEqual(o["extraction_status"], SM.UNSUPPORTED_ENCODING)

    def test_binary_nul(self):
        o = P.parse_source(b"\x00\x01", repository_id="1", commit_sha="a"*40,
                           file_path="m.py", git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")
        self.assertEqual(o["extraction_status"], SM.BINARY_CONTENT)

    def test_syntax_error(self):
        o = P.parse_source(b"def f(:\n", repository_id="1", commit_sha="a"*40,
                           file_path="m.py", git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")
        self.assertEqual(o["extraction_status"], SM.PARSE_FAILED)
        self.assertEqual(o["observed_symbols"], [], "解析失败不得产生符号")

    def test_empty_file(self):
        o = P.parse_source(b"", repository_id="1", commit_sha="a"*40,
                           file_path="m.py", git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")
        self.assertEqual(o["extraction_status"], SM.EXTRACTED)
        self.assertEqual(o["observed_symbols"], [])

    def test_verify_range_catches_mismatch(self):
        raw = b"class A:\n    pass\n"
        probs = SE.verify_range(raw, start_byte=0, end_byte=8,
                                start_line=1, end_line=1, expect_text="class A")
        self.assertEqual(probs, [])
        probs2 = SE.verify_range(raw, start_byte=0, end_byte=8,
                                 start_line=1, end_line=1, expect_text="class B")
        self.assertIn("TEXT_NOT_IN_RANGE", probs2)


class TestSymbols(unittest.TestCase):
    def test_plain_function(self):
        o = parse(b"def f():\n    pass\n")
        self.assertEqual(o["observed_symbols"][0]["symbol_kind"], "function")
        self.assertEqual(o["observed_symbols"][0]["qualified_name"], "f")

    def test_async_function(self):
        o = parse(b"async def f():\n    pass\n")
        self.assertEqual(o["observed_symbols"][0]["symbol_kind"],
                         "async_function")

    def test_class(self):
        o = parse(b"class C:\n    pass\n")
        self.assertEqual(o["observed_symbols"][0]["symbol_kind"], "class")

    def test_method(self):
        o = parse(b"class C:\n    def m(self):\n        pass\n")
        kinds = {s["symbol_kind"] for s in o["observed_symbols"]}
        self.assertIn("method", kinds)
        names = {s["qualified_name"] for s in o["observed_symbols"]}
        self.assertEqual(names, {"C", "C.m"})

    def test_async_method(self):
        o = parse(b"class C:\n    async def m(self):\n        pass\n")
        self.assertIn("async_method",
                      {s["symbol_kind"] for s in o["observed_symbols"]})

    def test_nested_function(self):
        o = parse(b"def outer():\n    def inner():\n        pass\n")
        qn = {s["qualified_name"] for s in o["observed_symbols"]}
        self.assertEqual(qn, {"outer", "outer.inner"})
        kinds = {s["qualified_name"]: s["symbol_kind"]
                 for s in o["observed_symbols"]}
        self.assertEqual(kinds["outer.inner"], "nested_function")

    def test_duplicate_names_kept(self):
        """★ 同名定义必须保留各自位置，不得覆盖。"""
        o = parse(b"def dup():\n    pass\n\ndef dup():\n    pass\n")
        syms = [s for s in o["observed_symbols"]
                if s["symbol_name"] == "dup"]
        self.assertEqual(len(syms), 2)
        self.assertNotEqual(syms[0]["symbol_id"], syms[1]["symbol_id"])
        self.assertNotEqual(syms[0]["source_start_byte"],
                            syms[1]["source_start_byte"])

    def test_decorator_recorded(self):
        o = parse(b"class C:\n    @staticmethod\n    def m():\n        pass\n")
        m = [s for s in o["observed_symbols"] if s["symbol_name"] == "m"][0]
        self.assertIn("staticmethod", m["decorators"])

    def test_type_annotations(self):
        o = parse(b"def f(x: int) -> str:\n    return ''\n")
        self.assertTrue(o["observed_symbols"][0]["has_type_annotations"])

    def test_utf8_identifier(self):
        o = parse("def 函数():\n    pass\n".encode("utf-8"))
        self.assertEqual(o["observed_symbols"][0]["symbol_name"], "函数")

    def test_multiline_def(self):
        o = parse(b"def f(\n    a,\n    b,\n):\n    pass\n")
        s = o["observed_symbols"][0]
        self.assertEqual(s["source_start_line"], 1)
        self.assertEqual(s["source_end_line"], 5)

    def test_symbol_id_deterministic(self):
        raw = b"class A:\n    pass\n"
        a = parse(raw)["observed_symbols"][0]["symbol_id"]
        b = parse(raw)["observed_symbols"][0]["symbol_id"]
        self.assertEqual(a, b)

    def test_observation_id_deterministic(self):
        raw = b"def f():\n    pass\n"
        self.assertEqual(parse(raw)["observation_id"],
                         parse(raw)["observation_id"])

    def test_col_offset_is_bytes(self):
        """★ 中文标识符后接语句，字节偏移必须按真实字节算。"""
        raw = "class 类:\n    def 方法(self):\n        pass\n".encode("utf-8")
        o = parse(raw)
        for s in o["observed_symbols"]:
            snippet = raw[s["source_start_byte"]:s["source_end_byte"]]
            self.assertTrue(snippet.decode("utf-8").startswith(
                ("class", "def", "    def")), s["qualified_name"])


class TestImports(unittest.TestCase):
    def test_plain_import(self):
        o = parse(b"import os\n")
        i = o["observed_imports"][0]
        self.assertEqual(i["import_syntax"], "import")
        self.assertEqual(i["module_name"], "os")

    def test_dotted_import(self):
        o = parse(b"import a.b\n")
        self.assertEqual(o["observed_imports"][0]["module_name"], "a.b")

    def test_from_import(self):
        o = parse(b"from x import y\n")
        i = o["observed_imports"][0]
        self.assertEqual(i["import_syntax"], "from_import")
        self.assertEqual(i["module_name"], "x")
        self.assertEqual(i["imported_name"], "y")

    def test_relative_import(self):
        o = parse(b"from . import x\n")
        self.assertEqual(o["observed_imports"][0]["relative_level"], 1)

    def test_relative_two_levels(self):
        o = parse(b"from ..x import y\n")
        i = o["observed_imports"][0]
        self.assertEqual(i["relative_level"], 2)
        self.assertEqual(i["module_name"], "x")

    def test_alias(self):
        o = parse(b"import numpy as np\n")
        self.assertEqual(o["observed_imports"][0]["alias"], "np")

    def test_star_import(self):
        o = parse(b"from x import *\n")
        self.assertTrue(o["observed_imports"][0]["star_import"])

    def test_function_scope_import(self):
        o = parse(b"def f():\n    import os\n")
        i = o["observed_imports"][0]
        self.assertEqual(i["source_scope"], "f")
        self.assertTrue(i["in_function_scope"])

    def test_conditional_import_kept(self):
        """★ 条件导入必须保留，不能提升为无条件依赖。"""
        o = parse(b"if True:\n    import os\n")
        self.assertEqual(len(o["observed_imports"]), 1)

    def test_type_checking_import(self):
        o = parse(b"from typing import TYPE_CHECKING\n"
                  b"if TYPE_CHECKING:\n    import x\n")
        mods = {i["module_name"] for i in o["observed_imports"]}
        self.assertIn("x", mods)

    def test_no_execution(self):
        """★ 解析器绝不能执行/导入被分析代码。"""
        src = (ROOT/"src"/"source_analysis"/"python_ast_parser.py").read_text(
            encoding="utf-8")
        for bad in ("exec(", "eval(", "importlib", "__import__"):
            self.assertNotIn(bad, src, f"解析器不得使用 {bad}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
