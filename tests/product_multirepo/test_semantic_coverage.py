#!/usr/bin/env python3
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "source_analysis"))
import semantic_coverage as SC


class TestDetect(unittest.TestCase):
    def test_M06_commonjs(self):
        self.assertIn("commonjs_module_exports",
                      SC.detect_unsupported_forms(
                          "module.exports = function(x){};"))

    def test_esm_clean(self):
        self.assertEqual(SC.detect_unsupported_forms(
            "export default function f(){}\nexport const x = 1;"), [])

    def test_require(self):
        self.assertIn("commonjs_require",
                      SC.detect_unsupported_forms("const a = require('b');"))


class TestClassify(unittest.TestCase):
    def test_M06_unsupported_not_empty(self):
        """★ 解析成功 + 有未支持形态 → 绝不能报 VALID_EMPTY_RESULT。"""
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=["commonjs_module_exports"])
        self.assertEqual(r["analysis_coverage"],
                         SC.UNSUPPORTED_SEMANTIC_FORM)
        self.assertNotEqual(r["analysis_coverage"], SC.VALID_EMPTY_RESULT)

    def test_M07_valid_empty(self):
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=[])
        self.assertEqual(r["analysis_coverage"], SC.VALID_EMPTY_RESULT)

    def test_with_facts(self):
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=2, observed_nodes=2,
                        unsupported_forms=[])
        self.assertEqual(r["analysis_coverage"],
                         SC.SUPPORTED_FACTS_EXTRACTED)

    def test_parse_failed(self):
        r = SC.classify(parse_status="PARSE_FAILED", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=[])
        self.assertEqual(r["analysis_coverage"], SC.PARSE_FAILED)

    def test_content_missing(self):
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=[], content_available=False)
        self.assertEqual(r["analysis_coverage"],
                         SC.SOURCE_CONTENT_NOT_CAPTURED)


class TestReport(unittest.TestCase):
    def _r(self, forms=(), facts=0):
        return SC.coverage_report(
            file_path="a.js", language="javascript", parser_version="v1",
            parse_status="PARSE_COMPLETE", facts_persisted=facts,
            claims_verified=0, observed_nodes=facts, unsupported_forms=forms)

    def test_M08_fields_complete(self):
        r = self._r(["commonjs_module_exports"])
        for k in ("language", "parser_version", "parse_status",
                  "supported_rule_families", "observed_supported_nodes",
                  "recognized_but_unsupported_forms", "facts_persisted",
                  "claims_verified", "analysis_coverage", "limitations"):
            self.assertIn(k, r)

    def test_M09_not_overclaim(self):
        r = self._r(["commonjs_module_exports"])
        joined = " ".join(r["limitations"])
        self.assertIn("不等于完整理解", joined)
        self.assertNotIn("已完整理解 JavaScript", joined)

    def test_unsupported_has_sample(self):
        r = self._r(["commonjs_module_exports"])
        f = r["recognized_but_unsupported_forms"][0]
        self.assertEqual(f["form"], "commonjs_module_exports")
        self.assertIn("module.exports", f["sample"])

    def test_rule_families_are_real(self):
        r = self._r()
        self.assertEqual(len(r["supported_rule_families"]), 3)
        self.assertIn("es_export_statement", r["supported_rule_families"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
