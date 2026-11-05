#!/usr/bin/env python3
"""源码结构 Gold：30 项人工定义预期。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"source_analysis"))
import sfx
import python_ast_parser as P
import source_fact_ingest as SFI
import source_claim_adapter as SCA
import source_knowledge_query as SKQ
import local_module_resolver as LMR
import source_models as SM
import blob_fetcher as BF
from knowledge_store import KnowledgeStore

REPO = "990001"
COMMIT = "a"*40
COMMIT_B = "b"*40


def raw_of(content):
    return content.encode("utf-8") if isinstance(content, str) else content


class TestSourceGold(unittest.TestCase):
    """30 例逐项独立验证。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="goldsrc_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _obs(self, content, path="m.py", commit=COMMIT):
        raw = raw_of(content)
        return P.parse_source(raw, repository_id=REPO, commit_sha=commit,
                              file_path=path,
                              git_blob_oid=BF.git_blob_oid(raw),
                              content_asset_id="SL-A-x",
                              content_sha256="sha256:"+"0"*64)

    def _ingest(self, o):
        r = SFI.ingest_source_facts(self.ks, observation=o)
        return r

    def _q(self, commit=COMMIT, path="m.py"):
        return SKQ.query_source_facts(store=self.ks, repository_id=REPO,
                                      commit_sha=commit, file_path=path)

    def _v(self, qname, kind, facts, commit=COMMIT, path="m.py",
           completeness="COMPLETE", available=True):
        c, b = SCA.build_symbol_claim(
            repository_id=REPO, commit_sha=commit, file_path=path,
            qualified_name=qname, symbol_kind=kind)
        return SCA.verify_source_claim(
            claim=c, facts=facts, content_available=available,
            completeness_status=completeness, subject_binding=b)

    # ── S01-S10 符号 ──
    def test_S01_plain_function(self):
        o = self._obs("def f():\n    pass\n")
        self.assertEqual(o["observed_symbols"][0]["symbol_kind"], "function")

    def test_S02_async_function(self):
        o = self._obs("async def f():\n    pass\n")
        self.assertEqual(o["observed_symbols"][0]["symbol_kind"],
                         "async_function")

    def test_S03_class(self):
        o = self._obs("class C:\n    pass\n")
        self.assertEqual(o["observed_symbols"][0]["symbol_kind"], "class")

    def test_S04_method(self):
        o = self._obs("class C:\n    def m(self):\n        pass\n")
        self._ingest(o)
        v = self._v("C.m", "method", self._q())
        self.assertEqual(v["status"], "supported")

    def test_S05_nested(self):
        o = self._obs("def outer():\n    def inner():\n        pass\n")
        qn = {s["qualified_name"]: s["symbol_kind"]
              for s in o["observed_symbols"]}
        self.assertEqual(qn["outer.inner"], "nested_function")

    def test_S06_duplicate_kept(self):
        o = self._obs("def dup():\n    pass\n\ndef dup():\n    pass\n")
        ids = {s["symbol_id"] for s in o["observed_symbols"]}
        self.assertEqual(len(ids), 2)

    def test_S07_multiline(self):
        o = self._obs("def f(\n    a,\n    b,\n):\n    pass\n")
        s = o["observed_symbols"][0]
        self.assertEqual((s["source_start_line"], s["source_end_line"]),
                         (1, 5))

    def test_S08_chinese_comment(self):
        o = self._obs("# 中文注释\ndef f():\n    pass\n")
        s = o["observed_symbols"][0]
        raw = raw_of("# 中文注释\ndef f():\n    pass\n")
        frag = raw[s["source_start_byte"]:s["source_end_byte"]].decode("utf-8")
        self.assertTrue(frag.startswith("def f"), frag)

    def test_S09_utf8_identifier(self):
        o = self._obs("def 函数():\n    pass\n")
        self.assertEqual(o["observed_symbols"][0]["symbol_name"], "函数")

    def test_S10_crlf(self):
        o = self._obs(b"def f():\r\n    pass\r\n")
        self.assertEqual(o["extraction_status"], SM.EXTRACTED)
        self.assertEqual(len(o["observed_symbols"]), 1)

    # ── S11-S21 导入 ──
    def test_S11_no_import(self):
        o = self._obs("def f():\n    pass\n")
        self.assertEqual(o["observed_imports"], [])

    def test_S12_decorator(self):
        o = self._obs("@deco\ndef f():\n    pass\n")
        self.assertIn("deco", o["observed_symbols"][0]["decorators"])

    def test_S13_annotations(self):
        o = self._obs("def f(x: int) -> str:\n    return ''\n")
        self.assertTrue(o["observed_symbols"][0]["has_type_annotations"])

    def test_S14_relative_one(self):
        o = self._obs("from . import x\n")
        self.assertEqual(o["observed_imports"][0]["relative_level"], 1)

    def test_S15_relative_two(self):
        o = self._obs("from ..pkg import y\n")
        i = o["observed_imports"][0]
        self.assertEqual(i["relative_level"], 2)
        self.assertEqual(i["module_name"], "pkg")

    def test_S16_alias(self):
        o = self._obs("import numpy as np\n")
        self.assertEqual(o["observed_imports"][0]["alias"], "np")

    def test_S17_external(self):
        o = self._obs("import requests\n")
        self._ingest(o)
        c, b = SCA.build_import_claim(
            repository_id=REPO, commit_sha=COMMIT, file_path="m.py",
            module_name="requests")
        v = SCA.verify_source_claim(claim=c, facts=self._q(),
                                    content_available=True,
                                    completeness_status="COMPLETE",
                                    subject_binding=b)
        self.assertEqual(v["status"], "supported")

    def test_S18_conditional_kept(self):
        o = self._obs("if True:\n    import os\n")
        self.assertEqual(len(o["observed_imports"]), 1)

    def test_S19_type_checking(self):
        o = self._obs("from typing import TYPE_CHECKING\n"
                      "if TYPE_CHECKING:\n    import t\n")
        self.assertIn("t", {i["module_name"] for i in o["observed_imports"]})

    def test_S20_star_import(self):
        o = self._obs("from x import *\n")
        self.assertTrue(o["observed_imports"][0]["star_import"])

    def test_S21_dynamic_import_statement(self):
        o = self._obs("import importlib\nimportlib.import_module('x')\n")
        self.assertEqual(o["observed_imports"][0]["module_name"], "importlib")

    # ── S22-S30 负例 ──
    def test_S22_nonexistent_symbol(self):
        o = self._obs("def f():\n    pass\n")
        self._ingest(o)
        v = self._v("ghost", "function", self._q())
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_S23_same_name_other_file(self):
        o1 = self._obs("def same():\n    pass\n", path="a.py")
        self._ingest(o1)
        v = self._v("same", "function", self._q(path="a.py"),
                    path="b.py")
        self.assertNotEqual(v["status"], "supported")

    def test_S24_same_name_other_commit(self):
        o = self._obs("def v1():\n    pass\n")
        self._ingest(o)
        v = self._v("v1", "function", self._q(), commit=COMMIT_B)
        self.assertNotEqual(v["status"], "supported")

    def test_S25_wrong_blob(self):
        # ★ 用真实 Git OID：不同内容 → 不同 Blob → 不同观察身份
        raw = raw_of("def f():\n    pass\n")
        o = self._obs("def f():\n    pass\n")
        other = P.parse_source(b"def g():\n    pass\n",
                               repository_id=REPO, commit_sha=COMMIT,
                               file_path="m.py",
                               git_blob_oid=BF.git_blob_oid(b"def g():\n    pass\n"),
                               content_asset_id="SL-A-x",
                               content_sha256="sha256:"+"1"*64)
        self.assertNotEqual(o["observation_id"], other["observation_id"])
        self.assertEqual(o["git_blob_oid"], BF.git_blob_oid(raw))

    def test_S26_dangling_evidence(self):
        o = self._obs("def f():\n    pass\n")
        o2 = dict(o, evidence_ranges=[])
        r = SFI.ingest_source_facts(self.ks, observation=o2)
        self.assertEqual(r["written"], [])
        self.assertTrue(r["skipped"])

    def test_S27_partial_content(self):
        o = self._obs("def f():\n    pass\n")
        self._ingest(o)
        v = self._v("ghost", "function", self._q(), completeness="PARTIAL")
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertNotEqual(v["status"], "refuted")

    def test_S28_syntax_error(self):
        o = self._obs("def f(:\n")
        r = self._ingest(o)
        self.assertEqual(r["written"], [])
        self.assertEqual(o["extraction_status"], SM.PARSE_FAILED)

    def test_S29_unsupported_encoding(self):
        o = P.parse_source(b"\xff\xfe bad", repository_id=REPO,
                           commit_sha=COMMIT, file_path="m.py",
                           git_blob_oid="b"*40, content_asset_id="X",
                           content_sha256="sha256:0")
        self.assertEqual(o["extraction_status"], SM.UNSUPPORTED_ENCODING)
        r = self._ingest(o)
        self.assertEqual(r["written"], [])

    def test_S30_module_resolution(self):
        tree = {"pkg/__init__.py", "pkg/core.py", "main.py"}
        r = LMR.resolve_import(import_record={
            "import_syntax": "from_import", "module_name": "pkg",
            "imported_name": "core", "relative_level": 0},
            source_path="main.py", tree_paths=tree)
        self.assertEqual(r["status"], SM.RESOLVED)

    # ── 阻断级指标 ──
    def test_no_refuted_anywhere(self):
        cases = ["def f():\n    pass\n", "def f(:\n",
                 "import os\n", "class C:\n    pass\n"]
        for c in cases:
            o = self._obs(c)
            for f in o["observed_symbols"] + o["observed_imports"]:
                self.assertNotIn("refuted", str(f).lower())

    def test_all_30_defined(self):
        from gold.source_gold import GOLD
        self.assertEqual(len(GOLD), 30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
