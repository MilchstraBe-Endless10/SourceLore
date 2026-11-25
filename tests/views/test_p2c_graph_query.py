#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-C §4-§5 图谱查询引擎专项测试（真实图谱 + 独立夹具）。"""
import os
import sys
import unittest
from pathlib import Path

WT = str(Path(__file__).resolve().parents[2])
for sub in ("views", "skill_interface", "trust", "storage", "content_persistence",
            "models", "source_analysis"):
    p = os.path.join(WT, "src", sub)
    if p not in sys.path:
        sys.path.insert(0, p)
sys.path.insert(0, os.path.join(WT, "src"))

import graph_query as GQ


def _fixture_graph():
    """独立可运行夹具：多候选、环、多跳、不可达、不完整覆盖。"""
    nodes = []
    edges = []

    def file_node(path):
        nid = "node:path:" + path
        nodes.append({"id": nid, "node_type": "file", "path": path,
                      "source_ref": {"kind": "tree_entry", "path": path}})
        return nid

    def module(ref, src):
        mid = "node:module:" + src + ":" + ref
        nodes.append({"id": mid, "node_type": "module_ref",
                      "module_specifier": ref, "importing_file_path": src,
                      "source_ref": {"kind": "source_fact", "path": src}})
        return mid

    for p in ("a.js", "b.js", "c.js", "d.js", "x.js", "orphan.js"):
        file_node(p)
    # a -> b -> c -> d (3 跳)，c -> a 形成环；x 不可达
    def dep(src, ref, dst):
        m = module(ref, src)
        edges.append({"id": "imp:" + src + ":" + ref, "edge_type": "IMPORTS",
                      "from": "node:path:" + src, "to": m,
                      "import_fact_id": "FACT:" + src + ":" + ref,
                      "source_ref": {"kind": "source_fact", "path": src}})
        edges.append({"id": "res:" + src + ":" + ref, "edge_type": "RESOLVES_TO",
                      "from": m, "to": "node:path:" + dst,
                      "resolution_state": "LOCAL_MODULE_RESOLVED",
                      "relation_fact_id": "REL:" + src + ":" + ref,
                      "source_ref": {"kind": "module_relation_fact"}})
    dep("a.js", "./b", "b.js")
    dep("b.js", "./c", "c.js")
    dep("c.js", "./d", "d.js")
    dep("c.js", "./a", "a.js")   # 环
    # 同名符号不同作用域
    for path, scope, qn in (("a.js", "m1", "render"), ("b.js", "m2", "render")):
        sid = "node:symbol:" + path + ":" + scope
        nodes.append({"id": sid, "node_type": "symbol", "symbol_name": "render",
                      "qualified_name": qn, "scope": scope, "path": path,
                      "source_fact_id": "FACT:" + sid,
                      "source_ref": {"kind": "source_fact", "path": path}})
        edges.append({"id": "dec:" + sid, "edge_type": "DECLARES",
                      "from": "node:path:" + path, "to": sid})
    return {"nodes": nodes, "edges": edges,
            "coverage": "PARTIAL",
            "limitations": ["fixture: incomplete tree"]}


class GraphQueryFixtureTest(unittest.TestCase):
    def setUp(self):
        self.g = _fixture_graph()
        self.idx = GQ.build_index(self.g)

    def test_entity_path_resolved(self):
        r = GQ.resolve_entity(self.idx, "a.js")
        self.assertEqual(r["status"], "RESOLVED")

    def test_entity_ambiguous_symbol(self):
        r = GQ.resolve_entity(self.idx, "render")
        self.assertEqual(r["status"], "AMBIGUOUS")
        self.assertEqual(len(r["candidates"]), 2)

    def test_entity_not_found_distinct(self):
        r = GQ.resolve_entity(self.idx, "ghost.js")
        self.assertEqual(r["status"], "NOT_FOUND_IN_GRAPH")
        self.assertIn("不等于", r["note"])

    def test_node_query_declares(self):
        r = GQ.node_query(self.idx, "node:path:a.js")
        self.assertEqual(len(r["declared_symbols"]), 1)
        self.assertEqual(r["declared_symbols"][0]["name"], "render")

    def test_node_query_symbol_owner(self):
        r = GQ.node_query(self.idx, "node:symbol:a.js:m1")
        self.assertEqual(r["source_location"]["path"], "a.js")
        self.assertEqual(len(r["declared_in_files"]), 1)

    def test_forward(self):
        r = GQ.forward_dependencies(self.idx, "a.js")
        self.assertEqual([d["path"] for d in r["dependencies"]], ["b.js"])

    def test_reverse(self):
        r = GQ.reverse_dependencies(self.idx, "d.js")
        self.assertEqual([d["path"] for d in r["dependents"]], ["c.js"])
        self.assertIn("不代表", r["note"])

    def test_multihop(self):
        r = GQ.multi_hop(self.idx, "a.js", "d.js", max_hops=4)
        self.assertEqual(r["status"], "PATHS_FOUND")
        self.assertEqual(r["paths"][0]["hops"], 3)

    def test_multihop_unreachable(self):
        r = GQ.multi_hop(self.idx, "a.js", "x.js", max_hops=4)
        self.assertEqual(r["status"], "NO_PATH_FOUND")
        self.assertIn("不等于", r["note"])

    def test_multihop_cycle_safe(self):
        r = GQ.multi_hop(self.idx, "a.js", "a.js", max_hops=5)
        self.assertEqual(r["status"], "NO_PATH_FOUND")  # 环被截断，不重复访问

    def test_multihop_bounded(self):
        r = GQ.multi_hop(self.idx, "a.js", "d.js", max_hops=2)
        self.assertEqual(r["status"], "NO_PATH_FOUND")
        self.assertTrue(r["meta"]["truncated"] or r["meta"]["visited"] > 0)

    def test_input_immutable(self):
        import copy
        before = copy.deepcopy(self.g)
        GQ.build_index(self.g)
        GQ.multi_hop(self.idx, "a.js", "d.js")
        self.assertEqual(self.g, before)


class GraphQueryRealTest(unittest.TestCase):
    def setUp(self):
        iso = os.environ.get("P2C_ISOLATED_DATA")
        if not iso or not Path(iso, "kb.db").exists():
            self.skipTest("真实隔离库未配置(P2C_ISOLATED_DATA)")
        import json
        gp = Path(iso, "派生视图", "42283287",
                  "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab", "code-graph.json")
        self.g = json.loads(gp.read_text())
        self.idx = GQ.build_index(self.g)

    def test_real_forward_graph_ops(self):
        # Preact 局部图谱：真实存在的静态依赖（若有）
        r = GQ.forward_dependencies(self.idx, "src/component.js")
        self.assertEqual(r["query_path"], "src/component.js")
        for d in r["dependencies"]:
            self.assertTrue(d["evidence"])

    def test_real_node_query(self):
        syms = [n for n in self.g["nodes"] if n.get("node_type") == "symbol"]
        r = GQ.node_query(self.idx, syms[0]["id"])
        self.assertEqual(r["status"], "FOUND")


if __name__ == "__main__":
    unittest.main(verbosity=2)
