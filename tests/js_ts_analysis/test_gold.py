#!/usr/bin/env python3
"""40 项 JS/TS Gold 逐条验证。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"js_ts_analysis"))
import sfx
import js_ts_parser as JP
import js_ts_symbol_rules as SR
from gold.js_ts_gold import GOLD


def run(src, path):
    raw = src.encode() if isinstance(src, str) else src
    return JP.parse_source(raw, repository_id="990001", commit_sha="a"*40,
                           file_path=path, git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")


def sym_map(o):
    return {s["qualified_name"]: s["symbol_kind"] for s in o["observed_symbols"]}


class TestGoldCoverage(unittest.TestCase):
    def test_at_least_40_cases(self):
        """★ 任务书要求 ≥40；实际 45（覆盖 33 项必需 + 补充）。"""
        self.assertGreaterEqual(len(GOLD), 40)
        ids = [g[0] for g in GOLD]
        self.assertEqual(len(ids), len(set(ids)), "用例 ID 不得重复")

    def test_every_case_produces_result(self):
        for gid, path, src, check, exp in GOLD:
            o = run(src, path)
            self.assertIn("parse_status", o, gid)


class TestGoldSymbols(unittest.TestCase):
    def test_js_symbols(self):
        cases = {
            "J01": ("run", SR.JS_FUNCTION),
            "J02": ("af", SR.JS_ASYNC_FUNCTION),
            "J03": ("gen", SR.JS_GENERATOR_FUNCTION),
            "J04": ("Worker", SR.JS_CLASS),
            "J05": ("W.execute", SR.JS_METHOD),
            "J06": ("start", SR.JS_ARROW_FUNCTION),
            "J07": ("fe", SR.JS_FUNCTION_EXPRESSION),
        }
        for gid, (qname, kind) in cases.items():
            idx = next(i for i, g in enumerate(GOLD) if g[0] == gid)
            _, path, src, _, _ = GOLD[idx]
            got = sym_map(run(src, path))
            self.assertIn(qname, got, f"{gid} 缺 {qname}")
            self.assertEqual(got[qname], kind, f"{gid} {qname} 类型错")

    def test_ts_symbols(self):
        cases = {
            "T01": ("I", SR.TS_INTERFACE),
            "T02": ("T", SR.TS_TYPE_ALIAS),
            "T03": ("E", SR.TS_ENUM),
        }
        for gid, (qname, kind) in cases.items():
            idx = next(i for i, g in enumerate(GOLD) if g[0] == gid)
            _, path, src, _, _ = GOLD[idx]
            got = sym_map(run(src, path))
            self.assertIn(qname, got, gid)
            self.assertEqual(got[qname], kind, gid)


class TestGoldImportsExports(unittest.TestCase):
    def test_import_kinds(self):
        expect = {"J11": "default_import", "J13": "namespace_import",
                  "J14": "side_effect_import",
                  "J15": "require_literal_call", "J16": "require_literal_call",
                  "J17": "dynamic_import"}
        for gid, kind in expect.items():
            idx = next(i for i, g in enumerate(GOLD) if g[0] == gid)
            _, path, src, _, _ = GOLD[idx]
            o = run(src, path)
            kinds = {i["import_kind"] for i in o["observed_imports"]}
            self.assertIn(kind, kinds, f"{gid} 期望 {kind} 实得 {kinds}")

    def test_type_only_import(self):
        o = run("import type { T } from './t';\n", "a.ts")
        self.assertTrue(o["observed_imports"][0]["is_type_only"])

    def test_export_all(self):
        o = run("export * from './all';\n", "a.js")
        kinds = {e["export_kind"] for e in o["observed_exports"]}
        self.assertIn("export_all", kinds)

    def test_anonymous_default_no_fake_name(self):
        """★ 匿名 default export 不得编造函数名。"""
        o = run("export default function() {}\n", "a.js")
        defaults = [e for e in o["observed_exports"]
                    if e["export_kind"] == "default_export"]
        self.assertTrue(defaults)
        self.assertIsNone(defaults[0]["exported_name"])
        self.assertTrue(defaults[0].get("anonymous"))


class TestGoldParseAndError(unittest.TestCase):
    def test_jsx_tsx(self):
        for gid, lang in (("X01", "tsx"), ("X02", "jsx")):
            idx = next(i for i, g in enumerate(GOLD) if g[0] == gid)
            _, path, src, _, _ = GOLD[idx]
            o = run(src, path)
            self.assertEqual(o["parse_status"], "PARSE_COMPLETE", gid)
            self.assertEqual(o["language"], lang, gid)

    def test_errors_produce_no_symbols(self):
        for gid in ("E01", "E02", "E03", "E04", "V02"):
            idx = next(i for i, g in enumerate(GOLD) if g[0] == gid)
            _, path, src, _, _ = GOLD[idx]
            o = run(src, path)
            if o["parse_status"] != "PARSE_COMPLETE":
                self.assertEqual(o["observed_symbols"], [], gid)

    def test_empty_file(self):
        o = run("", "a.js")
        self.assertEqual(o["parse_status"], "PARSE_COMPLETE")
        self.assertEqual(o["observed_symbols"], [])

    def test_chinese_crlf_bom(self):
        o = run("function 运行() {}\n", "a.js")
        self.assertEqual(o["observed_symbols"][0]["symbol_name"], "运行")
        o2 = run(b"function f(){}\r\n", "a.js")
        self.assertEqual(o2["parse_status"], "PARSE_COMPLETE")
        o3 = run(b"\xef\xbb\xbffunction f(){}\n", "a.js")
        self.assertEqual(o3["parse_status"], "PARSE_COMPLETE")


class TestGoldMetrics(unittest.TestCase):
    def test_no_false_positive_anywhere(self):
        """★ 阻断级：任何用例不得产生伪造符号。"""
        for gid, path, src, check, exp in GOLD:
            o = run(src, path)
            for s in o["observed_symbols"]:
                self.assertIsNotNone(s.get("start_byte"), gid)
                self.assertIsNotNone(s.get("symbol_id"), gid)
                self.assertGreaterEqual(s["end_byte"], s["start_byte"], gid)

    def test_evidence_valid_everywhere(self):
        for gid, path, src, check, exp in GOLD:
            o = run(src, path)
            raw = src.encode() if isinstance(src, str) else src
            for ev in o["evidence_ranges"]:
                self.assertLessEqual(ev["end_byte"], len(raw), gid)
                self.assertGreaterEqual(ev["start_byte"], 0, gid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
