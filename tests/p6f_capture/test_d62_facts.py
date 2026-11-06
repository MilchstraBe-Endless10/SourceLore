#!/usr/bin/env python3
"""D-62：受支持节点必须产生事实；写与复用都算；0 事实不得谎报合法空。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "source_analysis"))
import semantic_coverage as SC


class TestD62(unittest.TestCase):
    def test_observed_nodes_but_zero_facts_is_defect(self):
        """观察到受支持节点却 0 事实 → 阻断级，不是 VALID_EMPTY。"""
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=4,
                        unsupported_forms=[])
        self.assertEqual(r["analysis_coverage"], SC.SOURCE_FACTS_NOT_PERSISTED)
        self.assertNotEqual(r["analysis_coverage"], SC.VALID_EMPTY_RESULT)
        self.assertIn("不是合法空结果", r["explain"])

    def test_true_empty_still_valid(self):
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=[])
        self.assertEqual(r["analysis_coverage"], SC.VALID_EMPTY_RESULT)

    def test_commonjs_still_unsupported(self):
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=["commonjs_module_exports"])
        self.assertEqual(r["analysis_coverage"], SC.UNSUPPORTED_SEMANTIC_FORM)


class TestReusedCounts(unittest.TestCase):
    """written 与 reused 都必须计入既有事实。"""

    def test_source_facts_counts_reused(self):
        p = (ROOT / "src" / "collector" / "github_knowledge_extract.py").read_text(
            encoding="utf-8")
        self.assertIn('n_reused = len(sr.get("reused")', p,
                      "reused 必须计入，否则重复执行报 0")
        self.assertIn("source_facts_written", p)
        self.assertIn("source_facts_reused", p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
