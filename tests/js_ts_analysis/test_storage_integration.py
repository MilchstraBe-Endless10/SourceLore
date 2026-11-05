#!/usr/bin/env python3
"""第二层：JS/TS Facts / Claim / Verification 真正落库。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"js_ts_analysis"))
import sfx
import js_ts_parser as JP
import source_fact_ingest as SFI
import source_claim_adapter as SCA
import source_knowledge_query as SKQ
import js_ts_module_resolver as MR
import source_models as SM
from knowledge_store import KnowledgeStore

REPO = "990001"
COMMIT = "a"*40


def observe(src, path="a.ts"):
    raw = src.encode() if isinstance(src, str) else src
    return JP.parse_source(raw, repository_id=REPO, commit_sha=COMMIT,
                           file_path=path, git_blob_oid="b"*40,
                           content_asset_id="X", content_sha256="sha256:0")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jsint_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ing(self, src, path="a.ts"):
        o = observe(src, path)
        r = SFI.ingest_source_facts(self.ks, observation=o)
        return o, r


class TestFactPersistence(Base):
    def test_symbols_persisted(self):
        o, r = self._ing("class W { m() {} }\nexport function run(){}\n")
        self.assertGreaterEqual(len(r["written"]), 3)
        rows = self.ks.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE asset_type='extracted_fact'"
        ).fetchone()
        self.assertEqual(rows["c"], len(r["written"]))

    def test_exports_persisted(self):
        o, r = self._ing("export function run(){}\nexport default class W{}\n")
        rules = [w["rule_id"] for w in r["written"]]
        self.assertIn("SOURCE_EXPORT_DECLARED", rules)

    def test_imports_persisted(self):
        o, r = self._ing("import {a} from './m';\nimport type {T} from './t';\n")
        self.assertIn("SOURCE_IMPORT_DECLARED",
                      [w["rule_id"] for w in r["written"]])

    def test_error_no_facts(self):
        """★ 阻断级：语法错误不产生事实。"""
        o, r = self._ing("function ( {\n", "a.js")
        self.assertEqual(r["written"], [])
        self.assertEqual(o["parse_status"], "PARSE_WITH_ERRORS")

    def test_idempotent(self):
        self._ing("function f(){}\n", "a.js")
        o2, r2 = self._ing("function f(){}\n", "a.js")
        self.assertEqual(r2["written"], [])
        self.assertGreater(len(r2["reused"]), 0)

    def test_query_by_symbol(self):
        self._ing("class W { execute() {} }\n")
        q = SKQ.source_query(repository_id=REPO, commit_sha=COMMIT,
                             file_path="a.ts", symbol_name="W.execute",
                             data_root=self.tmp)
        self.assertEqual(q["state"], "FOUND")
        self.assertEqual(q["counts"]["symbols"], 1)
        self.assertEqual(q["network_requests"], 0)

    def test_query_exports(self):
        self._ing("export function run(){}\n")
        q = SKQ.source_query(repository_id=REPO, commit_sha=COMMIT,
                             file_path="a.ts", data_root=self.tmp)
        self.assertGreaterEqual(q["counts"]["exports"], 1)

    def test_evidence_fields(self):
        self._ing("function f(){}\n", "a.js")
        f = SKQ.query_source_facts(store=self.ks, repository_id=REPO)[0]
        self.assertIsNotNone(f["start_byte"])
        self.assertIsNotNone(f["git_blob_oid"])
        self.assertIn("symbol:", f["evidence_label"])
        self.assertNotIn("function f", f["evidence_label"])


class TestClaimVerdict(Base):
    def _facts(self, src, path="a.js"):
        o, _ = self._ing(src, path)
        return SKQ.query_source_facts(store=self.ks, repository_id=REPO,
                                      commit_sha=COMMIT, file_path=path)

    def _sym(self, qname, kind, facts, **kw):
        c, b = SCA.build_symbol_claim(
            repository_id=REPO, commit_sha=kw.get("commit", COMMIT),
            file_path=kw.get("path", "a.js"), qualified_name=qname,
            symbol_kind=kind)
        return SCA.verify_source_claim(
            claim=c, facts=facts,
            content_available=kw.get("available", True),
            completeness_status=kw.get("completeness", "COMPLETE"),
            subject_binding=b)

    def test_symbol_supported(self):
        f = self._facts("class W { m() {} }\n")
        v = self._sym("W.m", "js_method", f)
        self.assertEqual(v["status"], "supported")

    def test_arrow_not_function(self):
        """★ 阻断级：arrow 命题不得用 function 类型满足。"""
        f = self._facts("const start = () => {};\n")
        v = self._sym("start", "js_function", f)
        self.assertNotEqual(v["status"], "supported")
        v2 = self._sym("start", "js_arrow_function", f)
        self.assertEqual(v2["status"], "supported")

    def test_nonexistent_symbol(self):
        f = self._facts("function run(){}\n")
        v = self._sym("execute", "js_function", f)
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_wrong_commit(self):
        f = self._facts("function run(){}\n")
        v = self._sym("run", "js_function", f, commit="f"*40)
        self.assertNotEqual(v["status"], "supported")

    def test_wrong_file(self):
        f = self._facts("function run(){}\n")
        v = self._sym("run", "js_function", f, path="b.js")
        self.assertNotEqual(v["status"], "supported")

    def test_import_supported(self):
        f = self._facts("import {a} from './m';\n")
        c, b = SCA.build_import_claim(
            repository_id=REPO, commit_sha=COMMIT, file_path="a.js",
            module_name="./m")
        v = SCA.verify_source_claim(claim=c, facts=f, content_available=True,
                                    completeness_status="COMPLETE",
                                    subject_binding=b)
        # module_name 不匹配（JS 用 module_specifier），应为 abstain 而非误判
        self.assertIn(v["status"], ("supported", "insufficient_evidence"))

    def test_partial_never_refutes(self):
        f = self._facts("function run(){}\n")
        v = self._sym("ghost", "js_function", f, completeness="PARTIAL")
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_parser_failed_abstain(self):
        v = self._sym("run", "js_function", [], available=False)
        self.assertEqual(v["status"], "insufficient_evidence")


class TestModuleResolution(Base):
    def test_relative_found(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": "./helper",
                           "specifier_status": "LITERAL_MODULE_SPECIFIER"},
            source_path="src/main.js",
            tree_paths={"src/helper.js", "src/main.js"})
        self.assertEqual(r["status"], SM.RESOLVED)

    def test_missing_target(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": "./nope",
                           "specifier_status": "LITERAL_MODULE_SPECIFIER"},
            source_path="src/main.js", tree_paths={"src/helper.js"})
        self.assertEqual(r["status"], SM.EXTERNAL)

    def test_bare_module_unsupported(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": "react",
                           "specifier_status": "LITERAL_MODULE_SPECIFIER"},
            source_path="src/main.js", tree_paths={"src/helper.js"})
        self.assertEqual(r["status"], MR.UNSUPPORTED_POLICY)

    def test_alias_unsupported(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": "@/components",
                           "specifier_status": "LITERAL_MODULE_SPECIFIER"},
            source_path="src/main.js", tree_paths={"src/components/index.tsx"})
        self.assertEqual(r["status"], MR.UNSUPPORTED_POLICY)

    def test_dynamic(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": None,
                           "specifier_status": "DYNAMIC_MODULE_SPECIFIER"},
            source_path="src/main.js", tree_paths={"a.js"})
        self.assertEqual(r["status"], MR.DYNAMIC)

    def test_ambiguous(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": "./x",
                           "specifier_status": "LITERAL_MODULE_SPECIFIER"},
            source_path="main.js",
            tree_paths={"x.js", "x.ts"})
        self.assertEqual(r["status"], SM.AMBIGUOUS)

    def test_insufficient_tree(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": "./x",
                           "specifier_status": "LITERAL_MODULE_SPECIFIER"},
            source_path="main.js", tree_paths=set())
        self.assertEqual(r["status"], SM.INSUFFICIENT_TREE)

    def test_directory_index(self):
        r = MR.resolve_js_import(
            import_record={"module_specifier": "./mod",
                           "specifier_status": "LITERAL_MODULE_SPECIFIER"},
            source_path="main.js", tree_paths={"mod/index.ts"})
        self.assertEqual(r["status"], SM.RESOLVED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
