#!/usr/bin/env python3
"""第二层：Facts / Claim / Verification 真正落入 Storage。"""
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
from knowledge_store import KnowledgeStore
import blob_fetcher as BF

REPO = "990001"
COMMIT = "a"*40


def obs(raw, path="m.py"):
    return P.parse_source(raw, repository_id=REPO, commit_sha=COMMIT,
                          file_path=path, git_blob_oid=BF.git_blob_oid(raw),
                          content_asset_id="SL-A-x",
                          content_sha256="sha256:" + "0"*64)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="srcint_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestFactPersistence(Base):
    def test_symbols_persisted(self):
        o = obs(b"class C:\n    def m(self):\n        pass\n")
        r = SFI.ingest_source_facts(self.ks, observation=o)
        self.assertGreaterEqual(len(r["written"]), 2)
        rows = self.ks.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE asset_type='extracted_fact'"
        ).fetchone()
        self.assertEqual(rows["c"], len(r["written"]))

    def test_imports_persisted(self):
        o = obs(b"import os\nfrom x import y\n")
        r = SFI.ingest_source_facts(self.ks, observation=o)
        self.assertGreaterEqual(len(r["written"]), 2)

    def test_parse_failed_no_facts(self):
        """★ 解析失败不得产生事实。"""
        o = obs(b"def f(:\n")
        r = SFI.ingest_source_facts(self.ks, observation=o)
        self.assertEqual(r["written"], [])
        self.assertEqual(r.get("status"), SM.PARSE_FAILED)

    def test_idempotent(self):
        o = obs(b"def f():\n    pass\n")
        SFI.ingest_source_facts(self.ks, observation=o)
        r2 = SFI.ingest_source_facts(self.ks, observation=o)
        self.assertEqual(r2["written"], [])
        self.assertGreater(len(r2["reused"]), 0)
        rows = self.ks.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE asset_type='extracted_fact'"
        ).fetchone()
        self.assertEqual(rows["c"], 1)

    def test_query_by_symbol(self):
        o = obs(b"class Worker:\n    def run(self):\n        pass\n")
        SFI.ingest_source_facts(self.ks, observation=o)
        # 不带过滤 → 全部符号
        qall = SKQ.source_query(repository_id=REPO, commit_sha=COMMIT,
                                file_path="m.py", data_root=self.tmp)
        self.assertEqual(qall["state"], "FOUND")
        self.assertEqual(qall["counts"]["symbols"], 2)
        self.assertEqual(qall["network_requests"], 0)

        # ★ 按 qualified_name 过滤 → 只命中该符号
        q = SKQ.source_query(repository_id=REPO, commit_sha=COMMIT,
                             file_path="m.py", symbol_name="Worker.run",
                             data_root=self.tmp)
        self.assertEqual(q["state"], "FOUND")
        self.assertEqual(q["counts"]["symbols"], 1)
        self.assertEqual(q["symbols"][0]["subject"]["qualified_name"],
                         "Worker.run")

    def test_query_nonexistent_symbol(self):
        o = obs(b"def f():\n    pass\n")
        SFI.ingest_source_facts(self.ks, observation=o)
        q = SKQ.source_query(repository_id=REPO, commit_sha=COMMIT,
                             file_path="m.py", symbol_name="ghost",
                             data_root=self.tmp)
        self.assertNotEqual(q["state"], "FOUND")
        self.assertEqual(q["facts"], [])

    def test_evidence_present(self):
        o = obs(b"def f():\n    pass\n")
        SFI.ingest_source_facts(self.ks, observation=o)
        f = SKQ.query_source_facts(store=self.ks, repository_id=REPO)[0]
        self.assertIsNotNone(f["start_byte"])
        self.assertIsNotNone(f["git_blob_oid"])
        # ★ label 是结构化描述（symbol:kind@L起-止），不含原始源码
        self.assertIn("symbol:", f["evidence_label"])
        self.assertNotIn("def f", f["evidence_label"])


class TestClaimVerdict(Base):
    def _v(self, ctype, path, subject, facts, **kw):
        if ctype == "symbol":
            c, b = SCA.build_symbol_claim(
                repository_id=REPO, commit_sha=kw.get("commit", COMMIT),
                file_path=path, qualified_name=subject["qualified_name"],
                symbol_kind=subject["symbol_kind"])
        else:
            c, b = SCA.build_import_claim(
                repository_id=REPO, commit_sha=kw.get("commit", COMMIT),
                file_path=path, module_name=subject["module_name"])
        return SCA.verify_source_claim(
            claim=c, facts=facts,
            content_available=kw.get("available", True),
            completeness_status=kw.get("completeness", "COMPLETE"),
            parser_ok=kw.get("parser_ok", True), subject_binding=b)

    def _facts(self, raw, path="m.py"):
        o = obs(raw, path)
        SFI.ingest_source_facts(self.ks, observation=o)
        return SKQ.query_source_facts(store=self.ks, repository_id=REPO,
                                      commit_sha=COMMIT, file_path=path)

    def test_symbol_supported(self):
        f = self._facts(b"class Worker:\n    def run(self):\n        pass\n")
        v = self._v("symbol", "m.py",
                    {"qualified_name": "Worker.run", "symbol_kind": "method"},
                    f)
        self.assertEqual(v["status"], "supported")

    def test_nonexistent_symbol_abstain(self):
        """★ 阻断级：不存在的符号不得 supported。"""
        f = self._facts(b"class Worker:\n    def run(self):\n        pass\n")
        v = self._v("symbol", "m.py",
                    {"qualified_name": "Worker.execute",
                     "symbol_kind": "method"}, f)
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_wrong_kind_abstain(self):
        f = self._facts(b"class Worker:\n    def run(self):\n        pass\n")
        v = self._v("symbol", "m.py",
                    {"qualified_name": "Worker.run", "symbol_kind": "function"},
                    f)
        self.assertNotEqual(v["status"], "supported")

    def test_wrong_commit_abstain(self):
        f = self._facts(b"def f():\n    pass\n")
        v = self._v("symbol", "m.py",
                    {"qualified_name": "f", "symbol_kind": "function"}, f,
                    commit="f"*40)
        self.assertNotEqual(v["status"], "supported")

    def test_wrong_file_abstain(self):
        f = self._facts(b"def f():\n    pass\n")
        v = self._v("symbol", "other.py",
                    {"qualified_name": "f", "symbol_kind": "function"}, f)
        self.assertNotEqual(v["status"], "supported")

    def test_import_supported(self):
        f = self._facts(b"import requests\n")
        v = self._v("import", "m.py", {"module_name": "requests"}, f)
        self.assertEqual(v["status"], "supported")

    def test_import_absent_abstain(self):
        f = self._facts(b"import os\n")
        v = self._v("import", "m.py", {"module_name": "requests"}, f)
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_partial_never_refutes(self):
        f = self._facts(b"def f():\n    pass\n")
        v = self._v("symbol", "m.py",
                    {"qualified_name": "ghost", "symbol_kind": "function"},
                    f, completeness="PARTIAL")
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_parser_failed_abstain(self):
        v = self._v("symbol", "m.py",
                    {"qualified_name": "f", "symbol_kind": "function"}, [],
                    parser_ok=False)
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_ec_reason_codes_legal(self):
        """★ D-17 回归：映射出的 reason_code 必须在 EC 封闭码表内。"""
        import ec_models as M
        legal = {getattr(M, k) for k in dir(M) if k.startswith("R_")}
        for status in ("refuted", "insufficient_evidence"):
            for r in SCA._EC_REASON.values():
                self.assertIn(r, legal, r)


class TestModuleResolution(Base):
    def test_resolved(self):
        r = LMR.resolve_import(import_record={
            "import_syntax": "import", "module_name": "solo",
            "relative_level": 0}, source_path="main.py",
            tree_paths={"solo.py", "main.py"})
        self.assertEqual(r["status"], SM.RESOLVED)

    def test_external(self):
        r = LMR.resolve_import(import_record={
            "import_syntax": "import", "module_name": "requests",
            "relative_level": 0}, source_path="main.py",
            tree_paths={"solo.py"})
        self.assertEqual(r["status"], SM.EXTERNAL)

    def test_insufficient_tree(self):
        r = LMR.resolve_import(import_record={
            "import_syntax": "import", "module_name": "solo",
            "relative_level": 0}, source_path="main.py",
            tree_paths=set())
        self.assertEqual(r["status"], SM.INSUFFICIENT_TREE)

    def test_ambiguous(self):
        r = LMR.resolve_import(import_record={
            "import_syntax": "import", "module_name": "pkg",
            "relative_level": 0}, source_path="main.py",
            tree_paths={"pkg.py", "pkg/__init__.py"})
        self.assertEqual(r["status"], SM.AMBIGUOUS)

    def test_unsupported_form(self):
        r = LMR.resolve_import(import_record={
            "import_syntax": "from_import", "module_name": "",
            "relative_level": 9}, source_path="m.py",
            tree_paths={"x.py"})
        self.assertEqual(r["status"], SM.UNSUPPORTED_FORM)


if __name__ == "__main__":
    unittest.main(verbosity=2)
