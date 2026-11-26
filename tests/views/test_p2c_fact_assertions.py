#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-C 收尾 §4：事实级问答断言。

不再靠 intent 正确 + graph_results 非空判答案对；逐项核对
符号名 / 路径 / 依赖目标 / 多跳节点序列 / Fact ID / 来源身份 / 歧义与缺失状态。
依赖隔离数据根 P2C_ISOLATED_DATA；缺失即 skip，不伪造。
"""
import os
import sys
import unittest
from pathlib import Path

WT = str(Path(__file__).resolve().parents[2])
for sub in ("skill_interface", "views", "trust", "storage",
            "content_persistence", "models", "source_analysis"):
    p = str(Path(WT) / "src" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
sys.path.insert(0, str(Path(WT) / "src"))
import deep_answer as DA

ISO = os.environ.get("P2C_ISOLATED_DATA", "")
AG = ("local:4034d62ed2cf", "8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024")
PR = ("42283287", "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab")


def ask(repo, q):
    return DA.deep_answer(repository_id=repo[0], question=q,
                          data_root=ISO, commit_sha=repo[1])


@unittest.skipUnless(ISO and Path(ISO, "kb.db").exists(),
                     "隔离数据根未配置(P2C_ISOLATED_DATA)")
class FactAssertionTests(unittest.TestCase):
    def test_intro_has_real_fact_ids_and_primary_source(self):
        r = ask(AG, "介绍 arch-grower 这个项目")
        self.assertEqual(r["query_status"], "ANSWERED_TEXT_ONLY")
        self.assertEqual(r["repository_id"], AG[0])
        self.assertEqual(r["commit_sha"], AG[1])
        refs = r["evidence_refs"]
        self.assertTrue(any(x["ref"].get("kind") == "readme" for x in refs))
        facts = [x["ref"]["fact_id"] for x in refs
                 if x["ref"].get("kind") == "source_fact"]
        self.assertTrue(facts)
        self.assertTrue(all(f.startswith("SL-FACT-") for f in facts))
        self.assertTrue(all(x["source_role"] == "primary" for x in refs))

    def test_symbol_lookup_exact_name_path_and_fact_id(self):
        r = ask(AG, "op_collapse 函数定义在哪")
        self.assertIn(r["query_status"],
                      ("ANSWERED_WITH_GRAPH", "ANSWERED_WITH_GRAPH_PATHS"))
        res = r["graph_results"]
        node = next(v["node"] for v in res.values()
                    if v.get("node", {}).get("symbol_name") == "op_collapse")
        self.assertEqual(node["symbol_name"], "op_collapse")
        self.assertEqual(node["path"], "scripts/arch_engine/graph_ops.py")
        self.assertEqual(node["start_line"], 84)
        self.assertTrue(node["source_fact_id"].startswith("SL-FACT-"))
        self.assertEqual(node["source_ref"]["commit_sha"], AG[1])
        self.assertEqual(node["source_ref"]["repository_id"], AG[0])

    def test_forward_dependency_exact_target_and_evidence(self):
        r = ask(PR, "src/component.js 依赖哪些模块")
        deps = r["graph_results"]["src/component.js"]["dependencies"]
        paths = [d["path"] for d in deps]
        self.assertIn("src/constants.js", paths)
        ev = next(d["evidence"][0] for d in deps
                  if d["path"] == "src/constants.js")
        self.assertEqual(ev["module_specifier"], "./constants")
        self.assertEqual(ev["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertFalse(ev["ambiguous_resolution"])
        self.assertTrue(ev["import_fact_id"].startswith("SL-FACT-"))
        self.assertTrue(ev["relation_fact_id"].startswith("SL-FACT-"))
        self.assertTrue(all(sr["repository_id"] == PR[0]
                            for sr in ev["source_refs"]))
        self.assertTrue(all(sr["commit_sha"] == PR[1]
                            for sr in ev["source_refs"]))

    def test_reverse_dependency_exact_source(self):
        r = ask(PR, "谁依赖 src/constants.js")
        deps = r["graph_results"]["src/constants.js"]["dependents"]
        self.assertIn("src/component.js", [d["path"] for d in deps])

    def test_multi_hop_exact_node_sequence(self):
        r = ask(PR, "从 src/component.js 到 src/constants.js 的多跳路径")
        self.assertEqual(r["query_status"], "ANSWERED_WITH_GRAPH_PATHS")
        hp = r["graph_results"]["multi_hop"]
        self.assertEqual(hp["status"], "PATHS_FOUND")
        self.assertTrue(any(p["nodes"] == ["src/component.js", "src/constants.js"]
                            for p in hp["paths"]))
        # 每条路径首节点是起点、末节点是终点，且逐边首尾相连
        for p in hp["paths"]:
            self.assertEqual(p["nodes"][0], "src/component.js")
            self.assertEqual(p["nodes"][-1], "src/constants.js")
            self.assertEqual(len(p["edges"]), len(p["nodes"]) - 1)
            for a, e in zip(p["nodes"], p["edges"]):
                self.assertEqual(e["from"], a)
                self.assertEqual(e["to"], p["nodes"][p["nodes"].index(a) + 1])

    def test_no_evidence_is_honest(self):
        r = ask(AG, "ghost.py 的运行时函数调用链")
        self.assertEqual(r["query_status"], "ENTITY_NOT_LOCATED")
        self.assertFalse(r["graph_results"])

    def test_ambiguous_multihop_endpoint_does_not_pick_first(self):
        # 裸文件名 index.js 在 Preact 有两个候选；不得无条件取第一个建路径
        r = ask(PR, "index.js 到 component.js 的多跳路径")
        amb = r.get("ambiguous_entities_blocked") or []
        self.assertIn("index.js", amb)
        hp = r["graph_results"].get("multi_hop")
        self.assertEqual(hp.get("status"), "AMBIGUOUS_ENDPOINT")
        self.assertFalse(hp.get("paths"))
        self.assertEqual(r["query_status"], "ENTITY_AMBIGUOUS")

    def test_graph_status_detail_present(self):
        r = ask(PR, "介绍这个项目")
        detail = r["graph_status_detail"]
        self.assertTrue(detail["present"])
        self.assertEqual(detail["commit_sha"], PR[1])
        self.assertEqual(detail["repository_id"], PR[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
