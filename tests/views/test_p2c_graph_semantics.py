#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-C §2 前置门禁 GRAPH_SEMANTIC_CLASSIFICATION_INTEGRITY 专项证据。

覆盖：按真实 rule_id 精确分类、Python/JS specifier 规范化、导入不冒充符号、
符号去重、多候选解析不盲选 verified[0]、AST 符号进入正文；并对真实库两
固定 Commit 断言 IMPORTS/DECLARES/RESOLVES_TO 口径。
"""
import sys, os, json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/views", "src/storage", "src/trust", "src/skill_interface",
          "src/content_persistence", "src/models", "src/source_analysis",
          "src"):
    sp = str(ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import source_fact_contract as SFC  # noqa: E402
import repo_graph_derivation as RG  # noqa: E402

REPO = "repo-p2c"
C = "cccccccccccccccccccccccccccccccccccccccc"


class ContractTests(unittest.TestCase):
    def test_classify_exact_rule_ids(self):
        self.assertEqual(SFC.classify("SOURCE_SYMBOL_DECLARED"), "symbol")
        self.assertEqual(SFC.classify("SOURCE_IMPORT_DECLARED"), "import")
        self.assertEqual(SFC.classify("SOURCE_EXPORT_DECLARED"), "export")
        self.assertEqual(SFC.classify("SOURCE_LOCAL_MODULE_RESOLVED"), "relation")

    def test_classify_unknown_not_fabricated(self):
        self.assertIsNone(SFC.classify("SOURCE_SOMETHING_ELSE"))
        self.assertIsNone(SFC.classify(""))

    def test_python_from_import_specifier(self):
        subj = {"module_name": "arch_engine", "imported_name": "GraphIR",
                "relative_level": 0, "language": "python"}
        out = SFC.normalize_subject("SOURCE_IMPORT_DECLARED", subj)
        self.assertEqual(out["kind"], "import")
        self.assertEqual(out["module_specifier"], "arch_engine")
        self.assertEqual(out["source_reference"], "arch_engine")
        self.assertEqual(out["imported_name"], "GraphIR")  # 证据保留

    def test_python_relative_import_specifier(self):
        subj = {"module_name": "graph_ops", "relative_level": 2,
                "language": "python"}
        out = SFC.normalize_subject("SOURCE_IMPORT_DECLARED", subj)
        self.assertEqual(out["module_specifier"], "..graph_ops")

    def test_python_bare_import_without_name(self):
        # 普通 import 无 imported_name 也应得到 specifier（旧实现直接丢弃）
        out = SFC.normalize_subject(
            "SOURCE_IMPORT_DECLARED",
            {"module_name": "argparse", "relative_level": 0, "language": "python"})
        self.assertEqual(out["source_reference"], "argparse")

    def test_js_import_specifier_passthrough(self):
        out = SFC.normalize_subject(
            "SOURCE_IMPORT_DECLARED",
            {"module_specifier": "./graph_ops", "language": "javascript"})
        self.assertEqual(out["source_reference"], "./graph_ops")

    def test_import_not_symbol(self):
        # 有 name、无 ref 的导入不得被当作符号声明
        out = SFC.normalize_subject(
            "SOURCE_IMPORT_DECLARED", {"imported_name": "GraphIR"})
        self.assertEqual(out["kind"], "import")
        self.assertNotIn("symbol_kind", out)


def code_sym(path, name, scope="", fact=None):
    return {
        "fact_id": fact or f"sf-{name}", "commit_sha": C, "repository_id": REPO,
        "file_path": path, "kind": "symbol", "rule_id": "SOURCE_SYMBOL_DECLARED",
        "subject": {"qualified_name": name, "name": name, "scope": scope,
                    "symbol_kind": "function", "start_line": 1,
                    "module_specifier": None},
    }


def code_imp(path, ref, fact=None, **extra):
    subj = {"source_reference": ref, "module_specifier": ref,
            "kind": "import"}
    subj.update(extra)
    return {
        "fact_id": fact or f"imp-{path}-{ref}", "commit_sha": C,
        "repository_id": REPO, "file_path": path, "kind": "import",
        "rule_id": "SOURCE_IMPORT_DECLARED", "subject": subj,
    }


def rel(path, ref, target, fact="rel-1", res="res-1", **extra):
    r = {"importing_file_path": path, "module_specifier": ref,
         "resolution_state": "LOCAL_MODULE_RESOLVED", "status": "RESOLVED",
         "resolved_target_path": target, "fact_id": fact,
         "resolution_id": res, "repository_id": REPO, "commit_sha": C,
         "evidence_refs": ["ev-1"], "resolver_version": "pv1"}
    r.update(extra)
    return r


def tree(*paths):
    return [{"path": p, "type": "blob", "size": 10, "sha": "t" * 40}
            for p in paths]


def derive(**kw):
    args = dict(repository_id=REPO, commit_sha=C,
                tree_entries=tree("a.py", "b.py", "c.py"),
                claim_rows=[], code_rows=[], relations=[])
    args.update(kw)
    return RG.derive_repo_graph(**args)


def edge_types(g):
    out = {}
    for e in g["edges"]:
        out[e["edge_type"]] = out.get(e["edge_type"], 0) + 1
    return out


class GraphClassificationTests(unittest.TestCase):
    def test_imports_not_declares(self):
        g = derive(code_rows=[code_sym("a.py", "f"),
                              code_imp("a.py", "b")],
                   tree_entries=tree("a.py", "b.py"))
        et = edge_types(g)
        self.assertEqual(et.get("DECLARES"), 1)
        self.assertEqual(et.get("IMPORTS"), 1)
        sym = [n for n in g["nodes"] if n["node_type"] == "symbol"]
        self.assertEqual(len(sym), 1)

    def test_duplicate_symbol_not_duplicated(self):
        dup = code_sym("a.py", "f")
        dup2 = code_sym("a.py", "f", fact="sf-f-2")  # 同观察重复
        g = derive(code_rows=[dup, dup2])
        self.assertEqual(edge_types(g).get("DECLARES"), 1)

    def test_python_from_import_no_symbol_inflation(self):
        # Python from-import 有 imported_name、无 source_reference，旧实现误判符号
        imp = code_imp("a.py", "b", fact="imp-1")
        imp["subject"] = {"imported_name": "GraphIR", "module_name": "arch_engine",
                          "relative_level": 0, "language": "python",
                          "module_specifier": None, "source_reference": "arch_engine",
                          "kind": "import"}
        g = derive(code_rows=[imp], tree_entries=tree("a.py", "arch_engine.py"))
        self.assertEqual(edge_types(g).get("DECLARES", 0), 0)
        self.assertEqual(edge_types(g).get("IMPORTS"), 1)

    def test_multi_candidate_not_blind_first(self):
        g = derive(
            code_rows=[code_imp("a.py", "./b")],
            tree_entries=tree("a.py", "b.py", "c.py"),
            relations=[rel("a.py", "./b", "b.py", fact="r1", res="s1",
                           candidate_paths=["b.py", "c.py"]),
                       rel("a.py", "./b", "c.py", fact="r2", res="s2",
                           candidate_paths=["b.py", "c.py"])])
        et = edge_types(g)
        self.assertEqual(et.get("RESOLVES_TO"), 1)  # 只落一条主边
        ref = [n for n in g["nodes"] if n["node_type"] == "module_ref"][0]
        self.assertTrue(ref["ambiguous_resolution"])
        self.assertEqual(sorted(ref["candidate_target_paths"]), ["b.py", "c.py"])
        self.assertEqual(len(ref["relation_fact_ids"]), 2)  # 证据不丢


class RealDataGateTests(unittest.TestCase):
    """真实库固定 Commit 数字；数据根缺失则 skip，不伪造。"""
    def _graph(self, rid, commit):
        iso = os.environ.get("P2C_ISOLATED_DATA")
        if not iso or not Path(iso, "kb.db").exists():
            self.skipTest("真实隔离库未配置(P2C_ISOLATED_DATA)")
        import repo_derive_runner as DR
        from knowledge_store import KnowledgeStore
        from paths import db_path
        store = KnowledgeStore(str(db_path(iso)), create=False)
        DR.derive_one(repository_id=rid, data_root=iso, store=store,
                      commit_sha=commit)
        gp = Path(iso, "派生视图", rid, commit, "code-graph.json")
        return json.loads(gp.read_text())

    def test_arch_grower_counts(self):
        g = self._graph("local:4034d62ed2cf",
                        "8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024")
        et = edge_types(g)
        # ★ 真实分页后：旧 47/153 是 max_results=200 静默截断的假象
        self.assertEqual(et.get("IMPORTS"), 335)
        self.assertEqual(et.get("DECLARES"), 218)
        self.assertEqual(et.get("RE_EXPORTS", 0), 0)

    def test_preact_counts(self):
        g = self._graph("42283287",
                        "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab")
        et = edge_types(g)
        self.assertEqual(et.get("DECLARES"), 80)
        self.assertEqual(et.get("IMPORTS"), 43)
        self.assertEqual(et.get("RE_EXPORTS"), 13)
        self.assertEqual(et.get("RESOLVES_TO"), 10)

    def test_pagination_no_silent_truncation(self):
        iso = os.environ.get("P2C_ISOLATED_DATA")
        if not iso or not Path(iso, "kb.db").exists():
            self.skipTest("真实隔离库未配置(P2C_ISOLATED_DATA)")
        import source_knowledge as SK
        all_facts = []
        offset = 0
        for _ in range(10):
            r = SK.query_code(repository_id="local:4034d62ed2cf",
                              commit_sha="8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024",
                              data_root=iso, max_results=100, offset=offset)
            pg = r.get("pagination") or {}
            all_facts.extend(f["fact_id"] for f in r.get("facts") or [])
            if not pg.get("has_more"):
                break
            offset += len(r.get("facts") or [])
        self.assertEqual(len(all_facts), 553)          # 超过旧 200 上限
        self.assertEqual(len(all_facts), len(set(all_facts)))  # 分页不重不漏


if __name__ == "__main__":
    unittest.main(verbosity=2)
