#!/usr/bin/env python3
"""JS/TS 符号语义。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"js_ts_analysis"))
import sfx
import js_ts_parser as JP
import js_ts_symbol_rules as SR


def parse(src, path="a.ts"):
    raw = src.encode() if isinstance(src, str) else src
    return JP.parse_source(raw, repository_id="990001", commit_sha="a"*40,
                           file_path=path, git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")


def kinds(o):
    return {s["qualified_name"]: s["symbol_kind"] for s in o["observed_symbols"]}


class TestJSSymbols(unittest.TestCase):
    def test_function_declaration(self):
        o = parse("function run() {}\n", "a.js")
        self.assertEqual(kinds(o), {"run": SR.JS_FUNCTION})

    def test_async_function(self):
        o = parse("async function af() {}\n", "a.js")
        self.assertEqual(kinds(o), {"af": SR.JS_ASYNC_FUNCTION})

    def test_generator(self):
        o = parse("function* gen() { yield 1; }\n", "a.js")
        self.assertEqual(kinds(o), {"gen": SR.JS_GENERATOR_FUNCTION})

    def test_class(self):
        o = parse("class Worker {}\n", "a.js")
        self.assertEqual(kinds(o), {"Worker": SR.JS_CLASS})

    def test_method(self):
        o = parse("class W { execute() {} }\n", "a.js")
        self.assertEqual(kinds(o), {"W": SR.JS_CLASS,
                                    "W.execute": SR.JS_METHOD})

    def test_arrow_not_function_declaration(self):
        """★ 阻断级：arrow 绑定不能标成 function declaration。"""
        o = parse("const start = () => {};\n", "a.js")
        self.assertEqual(kinds(o), {"start": SR.JS_ARROW_FUNCTION})
        self.assertNotEqual(kinds(o)["start"], SR.JS_FUNCTION)

    def test_function_expression(self):
        o = parse("const fe = function() {};\n", "a.js")
        self.assertEqual(kinds(o), {"fe": SR.JS_FUNCTION_EXPRESSION})

    def test_variable(self):
        o = parse("const x = 1;\n", "a.js")
        self.assertEqual(kinds(o), {"x": SR.JS_VARIABLE})

    def test_object_method(self):
        o = parse("const o = { m() {} };\n", "a.js")
        k = kinds(o)
        self.assertIn("o.m", k)
        self.assertEqual(k["o.m"], SR.JS_OBJECT_METHOD)

    def test_duplicate_kept(self):
        o = parse("function dup(){}\nfunction dup(){}\n", "a.js")
        ids = {s["symbol_id"] for s in o["observed_symbols"]
               if s["symbol_name"] == "dup"}
        # 同名两次 → 两个符号（qualified 相同但位置不同）
        same = [s for s in o["observed_symbols"] if s["symbol_name"] == "dup"]
        self.assertEqual(len(same), 2)
        self.assertNotEqual(same[0]["start_byte"], same[1]["start_byte"])

    def test_no_duplicate_qual(self):
        """★ 限定名不得出现 `x.x` 形式的无意义重复（单名本身合法）。"""
        cases = ["const start = () => {};\n", "const o = { m() {} };\n",
                 "class W { m() {} }\n"]
        for src in cases:
            o = parse(src, "a.js")
            for s in o["observed_symbols"]:
                parts = s["qualified_name"].split(".")
                if len(parts) > 1:
                    self.assertNotEqual(parts[0], parts[-1],
                                        f"重复限定名 {s['qualified_name']}")
                # 不允许任一段连续两次出现
                for a, b in zip(parts, parts[1:]):
                    self.assertNotEqual(a, b,
                                        f"连续重复 {s['qualified_name']}")

    def test_chinese_identifier(self):
        o = parse("function 运行() {}\n", "a.js")
        self.assertEqual(o["observed_symbols"][0]["symbol_name"], "运行")

    def test_multiline(self):
        o = parse("function f(\n  a,\n  b\n) {\n}\n", "a.js")
        s = o["observed_symbols"][0]
        self.assertEqual((s["start_line"], s["end_line"]), (1, 5))

    def test_crlf(self):
        o = parse(b"function f(){}\r\nclass C{}\r\n", "a.js")
        self.assertEqual(o["parse_status"], "PARSE_COMPLETE")
        self.assertEqual(len(o["observed_symbols"]), 2)

    def test_bom(self):
        o = parse(b"\xef\xbb\xbffunction f(){}\n", "a.js")
        self.assertEqual(o["parse_status"], "PARSE_COMPLETE")
        self.assertEqual(len(o["observed_symbols"]), 1)


class TestTSSymbols(unittest.TestCase):
    def test_interface(self):
        o = parse("interface User { id: number }\n")
        self.assertEqual(kinds(o), {"User": SR.TS_INTERFACE})

    def test_type_alias(self):
        o = parse("type Id = string;\n")
        self.assertEqual(kinds(o), {"Id": SR.TS_TYPE_ALIAS})

    def test_enum(self):
        o = parse("enum Color { Red }\n")
        self.assertEqual(kinds(o), {"Color": SR.TS_ENUM})

    def test_interface_not_class(self):
        """★ 阻断级：interface 不得标成 class。"""
        o = parse("interface I { x: number }\nclass C {}\n")
        k = kinds(o)
        self.assertEqual(k["I"], SR.TS_INTERFACE)
        self.assertEqual(k["C"], SR.JS_CLASS)

    def test_typed_function(self):
        o = parse("function f(x: number): string { return ''; }\n")
        self.assertEqual(kinds(o), {"f": SR.JS_FUNCTION})


class TestJSXTSX(unittest.TestCase):
    def test_jsx_parse(self):
        o = parse('function App() { return <div className="x">hi</div>; }\n',
                  "a.jsx")
        self.assertEqual(o["parse_status"], "PARSE_COMPLETE")
        self.assertEqual(o["language"], "jsx")

    def test_tsx_parse(self):
        o = parse("interface P { n: number }\n"
                  "function C(p: P) { return <div>{p.n}</div>; }\n", "a.tsx")
        self.assertEqual(o["parse_status"], "PARSE_COMPLETE")
        self.assertEqual(o["language"], "tsx")
        k = kinds(o)
        self.assertIn("C", k)

    def test_tsx_needs_tsx_grammar(self):
        """★ 用 TS grammar 解析 JSX 会报错——证明必须用 TSX grammar。"""
        import treesitter_runtime as RT
        raw = b"const x = <div/>;\n"
        t_ts, s_ts, _ = RT.parse_bytes(raw, "typescript")
        t_tsx, s_tsx, _ = RT.parse_bytes(raw, "tsx")
        self.assertNotEqual(s_ts, "PARSE_COMPLETE",
                            "TS grammar 不应无错解析 JSX")
        self.assertEqual(s_tsx, "PARSE_COMPLETE")


class TestErrorRecovery(unittest.TestCase):
    def test_error_no_facts(self):
        """★ 阻断级：语法错误不产生权威符号。"""
        o = parse("function ( {", "a.js")
        self.assertEqual(o["parse_status"], "PARSE_WITH_ERRORS")
        self.assertEqual(o["observed_symbols"], [])
        self.assertEqual(o["observed_imports"], [])

    def test_incomplete_source(self):
        o = parse("class A { m( {", "a.ts")
        self.assertNotEqual(o["parse_status"], "PARSE_COMPLETE")
        self.assertEqual(o["observed_symbols"], [])

    def test_unsupported_ext(self):
        o = parse("x", "a.xyz")
        self.assertEqual(o["parse_status"], "PARSE_UNSUPPORTED_SYNTAX")


if __name__ == "__main__":
    unittest.main(verbosity=2)
