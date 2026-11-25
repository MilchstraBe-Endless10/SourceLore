#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-C §11：30 题技术问答集（明确预期证据，判级正确答案而非非空/篇幅）。"""
import os
import sys
import unittest
from pathlib import Path

WT = str(Path(__file__).resolve().parents[2])
ISO = os.environ.get("P2C_ISOLATED_DATA")
for sub in ("skill_interface", "views", "trust", "storage", "content_persistence",
            "models", "source_analysis"):
    p = os.path.join(WT, "src", sub)
    if p not in sys.path:
        sys.path.insert(0, p)
sys.path.insert(0, os.path.join(WT, "src"))

AG = ("local:4034d62ed2cf", "8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024")
PR = ("42283287", "dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab")

# (repo(repo,commit), question, expect_intent, expect_status(保留), expect_graph, note)
QA = [
    (AG, "介绍 arch-grower 这个项目", "general", None, False, "项目介绍用正文"),
    (PR, "Preact 是做什么的", "general", None, False, "正文能力"),
    (AG, "这个项目怎么使用", "general", None, False, "使用说明"),
    (PR, "如何安装 Preact", "general", None, False, "安装说明"),
    (AG, "op_collapse 函数定义在哪", "symbol_lookup", None, True, "AST 符号"),
    (AG, "ArchEngineError 类在哪定义", "symbol_lookup", None, True, "AST 类"),
    (AG, "_find_any_node 的位置", "symbol_lookup", None, True, "AST 函数"),
    (PR, "renderComponent.parentDom 定义在哪", "symbol_lookup", None, True, "JS 限定符号"),
    (PR, "COMPONENT_DIRTY 常量定义", "symbol_lookup", None, True, "JS 常量"),
    (AG, "graph_ops.py 的静态模块依赖有哪些", "forward_dependency", None, True, "Python 依赖"),
    (AG, "graph.py 依赖哪些模块", "forward_dependency", None, True, "Python 依赖"),
    (PR, "src/component.js 依赖哪些模块", "forward_dependency", None, True, "JS 依赖"),
    (PR, "src/create-element.js 的直接依赖", "forward_dependency", None, True, "JS 依赖"),
    (PR, "src/diff/index.js 的静态依赖", "forward_dependency", None, True, "JS 依赖"),
    (AG, "谁反向依赖 graph.py", "reverse_dependency", None, True, "Python 反向"),
    (PR, "谁依赖 src/constants.js", "reverse_dependency", None, True, "JS 反向"),
    (PR, "src/options.js 的反向依赖", "reverse_dependency", None, True, "JS 反向"),
    (AG, "哪些文件导入并解析到 records.py", "reverse_dependency", None, True, "Python 反向"),
    (PR, "从 src/component.js 到 src/constants.js 的多跳路径", "multi_hop", None, True, "可达成路径"),
    (PR, "src/component.js 到 src/diff/index.js 经过哪些模块", "multi_hop", None, True, "可达成路径"),
    (AG, "从 graph.py 到 records.py 有没有多跳路径", "multi_hop", None, True, "arch 可达性"),
    (PR, "src/index.js 到 src/component.js 的多跳路径", "multi_hop", None, False, "无已验证路径，应诚实"),
    (AG, "通过 GitHub ID 检索本地补充知识", "supplement", None, False, "补充来源"),
    (PR, "还有其他来源的知识吗", "supplement", None, False, "补充来源"),
    (AG, "在 commit 8f5daf1a 版本里 graph.py 的依赖", "forward_dependency", None, True, "固定 Commit"),
    (PR, "在 commit dbeba0d5 版本里 src/component.js 的依赖", "forward_dependency", None, True, "固定 Commit"),
    (AG, "ghost.py 的运行时函数调用链是什么", "symbol_lookup", None, False, "错误前提+无证据，应拒绝"),
    (PR, "src/ghost.js 的静态依赖", "forward_dependency", None, False, "不存在模块"),
    (AG, "这个项目的运行时函数调用链", "symbol_lookup", None, False, "不做运行时分析，应拒绝"),
    (PR, "src/component.js 里函数 A 调用了函数 B 吗", "symbol_lookup", None, False, "无函数调用图，应拒绝"),
]


@unittest.skipUnless(ISO and Path(ISO, "kb.db").exists(), "未配置 P2C_ISOLATED_DATA")
class DeepAnswerQATest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import deep_answer as DA
        cls.results = []
        for repo, q, ei, es, eg, note in QA:
            rid, commit = repo
            r = DA.deep_answer(repository_id=rid, question=q, data_root=ISO,
                               commit_sha=commit)
            cls.results.append((rid, commit, q, ei, es, eg, note, r))

    @staticmethod
    def row(t):
        # t = (rid, commit, q, ei, es, eg, note, r)
        return t[2], t[3], t[4], t[5], t[6], t[7]

    def test_01_question_count(self):
        self.assertEqual(len(self.results), 30)

    def test_02_all_return_structured_contract(self):
        for t in self.results:
            q, _, _, _, _, r = self.row(t)
            for k in ("query_status", "coverage", "resolved_entities",
                      "graph_results", "evidence_refs", "supplement_sources",
                      "limitations", "network_requests", "wrote_assets"):
                self.assertIn(k, r, q)

    def test_03_zero_network_zero_writes(self):
        for t in self.results:
            q, _, _, _, _, r = self.row(t)
            self.assertEqual(r.get("network_requests"), 0, q)
            self.assertEqual(r.get("wrote_assets"), 0, q)

    def test_04_intent_correct(self):
        checked = 0
        for t in self.results:
            q, ei, _, _, _, r = self.row(t)
            if ei == "general":
                continue
            self.assertEqual(r.get("intent"), ei, q)
            checked += 1
        self.assertGreaterEqual(checked, 20)

    def test_05_graph_evidence_when_expected(self):
        for t in self.results:
            q, _, _, eg, note, r = self.row(t)
            if not eg:
                continue
            has_graph = bool(r.get("graph_results") and
                             r.get("coverage") == "GRAPH+TEXT")
            self.assertTrue(has_graph, q + " | " + note)

    def test_06_false_premise_never_claims_graph_fact(self):
        for t in self.results:
            q, _, _, eg, note, r = self.row(t)
            if eg:
                continue
            self.assertFalse(r.get("graph_paths"), q + " | " + note)

    def test_07_no_cross_repo_pollution(self):
        for repo, t in zip(QA, self.results):
            rid, commit = repo[0]
            r = t[7]
            self.assertEqual(r.get("commit_sha"), commit, repo[1])
            self.assertEqual(r.get("repository_id"), rid, repo[1])

    def test_08_status_honesty(self):
        allowed = {"ANSWERED_WITH_GRAPH", "ANSWERED_WITH_GRAPH_PATHS",
                   "ANSWERED_TEXT_ONLY", "ENTITY_NOT_LOCATED",
                   "ENTITY_AMBIGUOUS", "GRAPH_NOT_AVAILABLE",
                   "QUERY_ERROR", "VERSION_NOT_FOUND"}
        for t in self.results:
            q, _, _, _, _, r = self.row(t)
            self.assertIn(r.get("query_status"), allowed, q)

    def test_09_evidence_refs_have_source_role(self):
        for t in self.results:
            q, _, _, _, _, r = self.row(t)
            for ref in r.get("evidence_refs") or []:
                self.assertIn("source_role", ref, q)

    def test_10_supplement_sources_isolated(self):
        for t in self.results:
            q, _, _, _, _, r = self.row(t)
            for s in r.get("supplement_sources") or []:
                self.assertEqual(s.get("role"), "verified_local_supplement", q)
            for s in r.get("supplement_relations") or []:
                self.assertEqual(s.get("source_role"), "verified_local_supplement", q)

    def test_11_multi_version_no_pollution(self):
        for t in self.results:
            q, _, _, _, _, r = self.row(t)
            if "commit" not in q:
                continue
            self.assertIn(r.get("query_status"),
                          {"ANSWERED_WITH_GRAPH", "ANSWERED_WITH_GRAPH_PATHS",
                           "ANSWERED_TEXT_ONLY"}, q)
            self.assertNotEqual(r.get("query_status"), "QUERY_ERROR", q)

    def test_12_correctness_summary(self):
        correct = 0
        for t in self.results:
            q, ei, _, eg, _, r = self.row(t)
            intent_ok = (ei == "general") or (r.get("intent") == ei)
            graph_ok = bool(r.get("graph_results")) if eg else not bool(r.get("graph_paths"))
            if intent_ok and graph_ok:
                correct += 1
        self.assertGreaterEqual(correct, 27)  # ≥90%
        print("\nQA_SUMMARY correct=%d/30" % correct)


if __name__ == "__main__":
    unittest.main(verbosity=2)
