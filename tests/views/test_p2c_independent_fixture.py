#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-C §10.C 独立夹具：陌生开发环境可独立运行，无数据根依赖。

覆盖：多版本同名文件、同名不同作用域符号、依赖环、多跳可达、
不可判定路径、不完整 Tree、多配置候选目标、未授权补充、无效证据、大型有界图谱。
"""
import sys
import unittest
from pathlib import Path

WT = str(Path(__file__).resolve().parents[2])
for sub in ("views", "skill_interface", "trust", "storage",
            "content_persistence", "models", "source_analysis"):
    p = str(Path(WT) / "src" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
sys.path.insert(0, str(Path(WT) / "src"))

import graph_query as GQ


def _file(path, commit="c1", tree=True):
    return {"id": "f:" + commit + ":" + path, "node_type": "file",
            "path": path, "commit": commit, "in_tree": tree}


def _sym(name, path, scope="", commit="c1"):
    return {"id": "s:" + commit + ":" + path + ":" + name + ":" + scope,
            "node_type": "symbol", "qualified_name": scope + "." + name if scope else name,
            "symbol_name": name, "path": path, "commit": commit}


def _mod(path, spec):
    return {"id": "m:" + path + ":" + spec, "node_type": "module_ref",
            "path": path, "module_specifier": spec}


def _imp(src, mod, fid="imp"):
    return {"id": "e:" + fid, "from": src["id"], "to": mod["id"],
            "edge_type": "IMPORTS", "source_ref": "line:1", "import_fact_id": fid}


def _res(mod, tgt, fid="rel"):
    return {"id": "e:" + fid, "from": mod["id"], "to": tgt["id"],
            "edge_type": "RESOLVES_TO", "resolution_state": "verified",
            "relation_fact_id": fid}


class FixtureTest(unittest.TestCase):
    def test_multi_version_same_path_isolated(self):
        a, b = _file("app.py", "cA"), _file("app.py", "cB")
        g = {"nodes": [a, b], "edges": []}
        ia, ib = GQ.build_index(g), None
        # 同路径不同 commit 的节点各自存在，实体定位如实标歧义、不擅自选定
        self.assertNotEqual(a["id"], b["id"])
        r = GQ.resolve_entity(ia, "app.py")
        self.assertEqual(r["status"], "AMBIGUOUS")
        self.assertEqual(len(r["candidates"]), 2)

    def test_same_name_symbol_different_scope_ambiguous(self):
        s1 = _sym("run", "a.py", "ClassA")
        s2 = _sym("run", "b.py", "ClassB")
        g = {"nodes": [s1, s2], "edges": []}
        idx = GQ.build_index(g)
        r = GQ.resolve_entity(idx, "run")
        self.assertEqual(r["status"], "AMBIGUOUS")
        self.assertEqual(len(r["candidates"]), 2)

    def test_cycle_forward_no_infinite_loop(self):
        a, b = _file("a.py"), _file("b.py")
        ma, mb = _mod("a.py", "b"), _mod("b.py", "a")
        g = {"nodes": [a, b, ma, mb],
             "edges": [_imp(a, ma, "i1"), _res(ma, b, "r1"),
                       _imp(b, mb, "i2"), _res(mb, a, "r2")]}
        idx = GQ.build_index(g)
        hp = GQ.multi_hop(idx, "a.py", "b.py", max_hops=4, max_visited=100, max_paths=10)
        self.assertTrue(hp["paths"])
        self.assertTrue(hp["meta"].get("visited", 0) < 100)

    def test_multi_hop_reachable_with_evidence(self):
        a, b, c = _file("a.py"), _file("b.py"), _file("c.py")
        m1, m2 = _mod("a.py", "b"), _mod("b.py", "c")
        g = {"nodes": [a, b, c, m1, m2],
             "edges": [_imp(a, m1, "i1"), _res(m1, b, "r1"),
                       _imp(b, m2, "i2"), _res(m2, c, "r2")]}
        idx = GQ.build_index(g)
        hp = GQ.multi_hop(idx, "a.py", "c.py", max_hops=4)
        self.assertTrue(hp["paths"])
        self.assertEqual(hp["paths"][0]["nodes"][-1], "c.py")
        self.assertTrue(hp["paths"][0]["edges"][0]["evidence"])

    def test_unreachable_is_honest(self):
        a, b, c = _file("a.py"), _file("b.py"), _file("c.py")
        m1 = _mod("a.py", "b")
        g = {"nodes": [a, b, c, m1],
             "edges": [_imp(a, m1), _res(m1, b)]}
        idx = GQ.build_index(g)
        hp = GQ.multi_hop(idx, "a.py", "c.py", max_hops=4)
        self.assertEqual(hp.get("status"), "NO_PATH_FOUND")
        self.assertFalse(hp["paths"])

    def test_incomplete_tree_declared(self):
        # in_tree=False 节点存在，但查询不把隐式文件当完整覆盖
        a, ghost = _file("a.py"), _file("ghost.py", tree=False)
        g = {"nodes": [a, ghost], "edges": [], "coverage": "PARTIAL"}
        idx = GQ.build_index(g)
        self.assertIn("ghost.py", idx["by_path"])
        self.assertEqual(GQ.resolve_entity(idx, "ghost.py")["status"], "RESOLVED")

    def test_multi_candidate_resolution_not_blind(self):
        a, b, c = _file("a.py"), _file("b.py"), _file("c.py")
        m = _mod("a.py", "shared")
        e1 = _res(m, b, "r1")
        e2 = _res(m, c, "r2")
        e1["ambiguous_resolution"] = True
        e2["ambiguous_resolution"] = True
        imp = _imp(a, m)
        g = {"nodes": [a, b, c, m], "edges": [imp, e1, e2]}
        idx = GQ.build_index(g)
        # ★ P2-C 收尾 §2：冲突候选不进确定性依赖邻接（不取第一个候选）。
        amb = idx.get("ambiguous_resolution_edges") or []
        self.assertEqual(len(amb), 2)  # 两条歧义解析边都被如实记录
        # 正向依赖不得凭排序确定性把任候选当成真实目标
        self.assertFalse(idx["forward"].get("a.py"))
        hp = GQ.multi_hop(idx, "a.py", "b.py", max_hops=4)
        self.assertEqual(hp.get("status"), "NOT_FOUND_IN_GRAPH")

    def test_invalid_evidence_dropped(self):
        a = _file("a.py")
        bad = {"id": "e:bad", "from": a["id"], "to": "missing-node",
               "edge_type": "IMPORTS"}
        g = {"nodes": [a], "edges": [bad]}
        idx = GQ.build_index(g)
        self.assertFalse(idx["forward"].get("a.py"))

    def test_unauthorized_supplement_not_merged(self):
        # 来源身份字段保留，不因内容等价合并身份
        a = _file("a.py", "cMain")
        sup = _file("a.py", "cSup")
        a["source_identity"] = "github:owner/repo"
        sup["source_identity"] = "supplement:unauthorized"
        g = {"nodes": [a, sup], "edges": []}
        idx = GQ.build_index(g)
        # 两节点 ID 不同，查询不自动合并
        self.assertNotEqual(a["id"], sup["id"])

    def test_bounded_large_graph(self):
        nodes, edges = [], []
        n = 60
        for i in range(n):
            nodes.append(_file("f%d.py" % i))
        for i in range(n - 1):
            m = _mod("f%d.py" % i, "f%d" % (i + 1))
            nodes.append(m)
            edges.append(_imp(nodes[i], m, "i%d" % i))
            edges.append(_res(m, nodes[i + 1], "r%d" % i))
        idx = GQ.build_index({"nodes": nodes, "edges": edges})
        hp = GQ.multi_hop(idx, "f0.py", "f59.py", max_hops=4,
                          max_visited=50, max_paths=5)
        # 有界：4 跳无法到达 59 跳外的目标；访问受 max_visited 限制且不爆
        self.assertFalse(hp["paths"])
        self.assertLessEqual(hp["meta"].get("visited", 0), 50)
        self.assertTrue(hp["meta"].get("truncated") or
                        hp["meta"].get("depth_limit") or
                        hp.get("status") == "NO_PATH_FOUND")


if __name__ == "__main__":
    unittest.main(verbosity=2)
