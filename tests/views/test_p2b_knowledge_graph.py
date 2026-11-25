#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-B 项目知识图谱专项功能验收（纯派生函数，无需真实库）。

覆盖任务 §10 中可由 derive_repo_graph 直接判定的条目：
节点无重复 ID、无悬空边、graph_digest 确定性、版本/仓库/作用域/导入方
身份隔离、P2-A 已验证关系消费、未解析不冒充、覆盖诚实、IMPORTS≠CALLS、
来源证据字段。固定 Commit 正文隔离与 answer 缺失状态由真实库脚本验证
（见验收文档），本文件专注图谱结构判据。
"""
import sys, copy, random, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/views", "src/storage", "src/trust"):
    sp = str(ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import repo_graph_derivation as RG  # noqa: E402

REPO_A = "repo-alpha"
REPO_B = "repo-beta"
C1 = "1111111111111111111111111111111111111111"
C2 = "2222222222222222222222222222222222222222"


def tree(*paths):
    out = []
    for p in paths:
        out.append({
            "path": p,
            "type": "blob" if "." in p.rsplit("/", 1)[-1] else "tree",
            "size": 10, "sha": "t" * 40,
        })
    return out


def sym(path, name, *, scope="", kind="function", commit=C1, repo=REPO_A,
        fact=None, parser="python-ast", status="AST_SOURCE"):
    return {
        "fact_id": fact or f"sf-{name}-{scope}-{path}",
        "commit_sha": commit, "repository_id": repo,
        "file_path": path, "kind": kind,
        "provenance_level": status, "parser_id": parser,
        "parser_version": "1.0", "git_blob_oid": "g" * 40,
        "content_asset_id": "ca-1", "extraction_status": status,
        "subject": {
            "qualified_name": name, "name": name, "scope": scope,
            "start_line": 1, "line_range": [1, 5],
        },
    }


def imp(path, ref, *, name="", commit=C1, repo=REPO_A, fact=None):
    return {
        "fact_id": fact or f"imp-{path}-{ref}",
        "commit_sha": commit, "repository_id": repo,
        "file_path": path, "kind": "import",
        "provenance_level": "AST_SOURCE",
        "subject": {"source_reference": ref, "imported_name": name},
    }


def rel(path, ref, target, *, status="RESOLVED",
        state="LOCAL_MODULE_RESOLVED", commit=C1, repo=REPO_A):
    return {
        "importing_file_path": path, "module_specifier": ref,
        "resolution_state": state, "status": status,
        "resolved_target_path": target,
        "fact_id": f"rel-{path}-{ref}", "resolution_id": f"res-{path}-{ref}",
        "repository_id": repo, "commit_sha": commit,
        "evidence_refs": ["ev-1"], "resolver_version": "pv1",
        "matched_config_rule": "paths@jsconfig",
    }


def derive(**kw):
    args = dict(repository_id=REPO_A, commit_sha=C1,
                tree_entries=tree("app.py", "utils.py"),
                claim_rows=[], code_rows=[], relations=[])
    args.update(kw)
    return RG.derive_repo_graph(**args)


def all_ids(g):
    return [n["id"] for n in g["nodes"]]


class GraphIdentityTests(unittest.TestCase):
    def test_no_duplicate_node_ids(self):
        rows = [sym("app.py", "run"), sym("app.py", "run")]  # 重复观察
        g = derive(code_rows=rows)
        ids = all_ids(g)
        self.assertEqual(len(ids), len(set(ids)), "节点 ID 必须唯一")

    def test_no_dangling_edges(self):
        g = derive(code_rows=[sym("app.py", "run"), imp("app.py", "./utils")],
                   relations=[rel("app.py", "./utils", "utils.py")])
        ids = set(all_ids(g))
        dangling = [e["id"] for e in g["edges"]
                    if any(x is not None and x not in ids
                           for x in (e.get("from"), e.get("to")))]
        self.assertEqual(dangling, [], "不得有悬空边")
        self.assertEqual(g["coverage"]["dangling_edges_dropped"], 0)

    def test_commit_isolation_same_path_symbol(self):
        # 一张图绑定一个 commit：跨版本隔离应比较两次派生的节点 ID
        ga = derive(code_rows=[sym("app.py", "run")])                 # C1
        gb = derive(commit_sha=C2, code_rows=[sym("app.py", "run", commit=C2)])
        sa = next(n for n in ga["nodes"] if n["node_type"] == "symbol")
        sb = next(n for n in gb["nodes"] if n["node_type"] == "symbol")
        self.assertNotEqual(sa["id"], sb["id"], "不同 Commit 同名符号不得归并")

    def test_repo_isolation_same_symbol(self):
        ga = derive(code_rows=[sym("app.py", "run")])                 # REPO_A
        gb = derive(repository_id=REPO_B, code_rows=[sym("app.py", "run", repo=REPO_B)])
        sa = next(n for n in ga["nodes"] if n["node_type"] == "symbol")
        sb = next(n for n in gb["nodes"] if n["node_type"] == "symbol")
        self.assertNotEqual(sa["id"], sb["id"], "不同仓库同名符号不得归并")

    def test_scope_distinction_same_file(self):
        rows = [sym("app.py", "helper", scope="ClassA"),
                sym("app.py", "helper", scope="ClassB")]
        g = derive(code_rows=rows)
        syms = [n for n in g["nodes"] if n["node_type"] == "symbol"]
        self.assertEqual(len(syms), 2, "同文件不同作用域符号必须区分")
        self.assertNotEqual(syms[0]["scope"], syms[1]["scope"])

    def test_same_specifier_different_files(self):
        rows = [imp("a/app.js", "./constants"), imp("b/app.js", "./constants")]
        g = derive(code_rows=rows)
        mods = [n for n in g["nodes"] if n["node_type"] == "module_ref"]
        self.assertEqual(len(mods), 2, "同名 specifier 跨导入文件不得归并")
        self.assertNotEqual(mods[0]["importing_file_path"],
                            mods[1]["importing_file_path"])


class RelationGraphTests(unittest.TestCase):
    def test_resolved_relation_creates_edge(self):
        g = derive(code_rows=[imp("app.py", "./utils")],
                   relations=[rel("app.py", "./utils", "utils.py")])
        res = [e for e in g["edges"] if e["edge_type"] == "RESOLVES_TO"]
        self.assertEqual(len(res), 1, "已验证关系必须建 RESOLVES_TO")
        self.assertEqual(res[0]["to"],
                         next(n["id"] for n in g["nodes"]
                              if n.get("path") == "utils.py"))
        mod = next(n for n in g["nodes"] if n["node_type"] == "module_ref")
        self.assertEqual(mod["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertEqual(mod["resolved_target_path"], "utils.py")

    def test_unresolved_relation_no_edge(self):
        g = derive(code_rows=[imp("app.py", "./ghost")],
                   relations=[rel("app.py", "./ghost", "ghost.py",
                                  status="EXTERNAL_OR_UNRESOLVED",
                                  state="EXTERNAL")])
        res = [e for e in g["edges"] if e["edge_type"] == "RESOLVES_TO"]
        self.assertEqual(res, [], "未解析关系不得建已落定目标边")
        mod = next(n for n in g["nodes"] if n["node_type"] == "module_ref")
        self.assertNotIn("resolved_target_path", mod)

    def test_target_outside_tree_no_dangling(self):
        g = derive(code_rows=[imp("app.py", "./outside")],
                   relations=[rel("app.py", "./outside", "deep/out.py")])
        target = next(n for n in g["nodes"] if n.get("path") == "deep/out.py")
        self.assertFalse(target["in_tree"], "树外目标须标注 in_tree=False")
        ids = set(all_ids(g))
        self.assertTrue(all(x is None or x in ids
                            for e in g["edges"]
                            for x in (e.get("from"), e.get("to"))))

    def test_no_calls_edge(self):
        g = derive(code_rows=[sym("app.py", "run"), imp("app.py", "./utils")],
                   relations=[rel("app.py", "./utils", "utils.py")])
        types = {e["edge_type"] for e in g["edges"]}
        self.assertNotIn("CALLS", types, "IMPORTS 不得命名为 CALLS")

    def test_evidence_fields_on_symbol(self):
        g = derive(code_rows=[sym("app.py", "run")])
        node = next(n for n in g["nodes"] if n["node_type"] == "symbol")
        for f in ("source_fact_id", "parser_id", "git_blob_oid",
                  "content_asset_id", "provenance_level", "extraction_status"):
            self.assertIn(f, node, f"符号须携带证据字段 {f}")
        self.assertEqual(node["source_ref"]["commit_sha"], C1)


class DeterminismTests(unittest.TestCase):
    def test_digest_deterministic_same_input(self):
        kw = dict(code_rows=[sym("app.py", "run"), imp("app.py", "./utils")],
                  relations=[rel("app.py", "./utils", "utils.py")])
        self.assertEqual(derive(**kw)["graph_digest"],
                         derive(**kw)["graph_digest"])

    def test_digest_order_invariant(self):
        rows = [sym("app.py", "run"), sym("utils.py", "helper"),
                imp("app.py", "./utils")]
        rels = [rel("app.py", "./utils", "utils.py")]
        base = derive(code_rows=rows, relations=rels)
        shuffled = copy.deepcopy(rows)
        r2 = copy.deepcopy(rels)
        random.Random(0).shuffle(shuffled)
        random.Random(1).shuffle(r2)
        other = derive(code_rows=shuffled, relations=r2)
        self.assertEqual(base["graph_digest"], other["graph_digest"],
                         "输入顺序变化不应造成 graph_digest 漂移")

    def test_coverage_honesty_root_only(self):
        g = derive(tree_entries=tree("app.py"), code_rows=[],
                   tree_coverage=[{"completeness_status": "COMPLETE"}])  # 仅根层
        self.assertIn("ROOT_ONLY", str(g["completeness"]["tree_status"]))
        self.assertTrue(any("树快照" in x or "未采集" in x
                            for x in g["limitations"]),
                        "树不完整须如实标注限制")


if __name__ == "__main__":
    unittest.main(verbosity=2)
