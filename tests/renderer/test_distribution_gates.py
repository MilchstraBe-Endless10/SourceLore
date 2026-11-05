#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-34 / T-35：预览与分发门禁独立。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/renderer", "src/renderer", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import card_renderer as CRD, pre_publish_check as PPC


class TestGates(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg_"))
        self.ks = rfx.fresh(self.tmp)
        self.cards, self.src, self.res = rfx.make_cards(self.ks)
        self.c = self.cards[-1]

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bundle(self):
        return {"html": CRD.render_card_html(self.c),
                "json": json.loads(CRD.render_json(self.c))}

    def _view_like(self):
        return {
            "authorization_is_test_only": self.c["authorization"]["test_only"],
            "provenance_level": self.c["provenance"]["level"],
            "no_usable_evidence": self.c["evidence"]["no_usable_evidence"],
            "conflict_indicators": {},
            "limitations": self.c["limitations"],
        }

    def test_t34_preview_and_distribution_independent(self):
        r = PPC.pre_publish_check(self._bundle(), self._view_like(),
                                  self.c["distribution"])
        self.assertTrue(r["preview_allowed"], "本地预览允许")
        self.assertFalse(r["distribution_allowed"], "对外分发必须拒绝")
        self.assertTrue(r["publish_blocked"])
        self.assertIn("预览许可不等于分发许可", r["statement"])
        self.assertNotEqual(r["preview_allowed"], r["distribution_allowed"],
                            "两类门禁必须独立")

    def test_t35_blockers_open_block_distribution(self):
        r = PPC.pre_publish_check(self._bundle(), self._view_like(),
                                  self.c["distribution"])
        codes = [f["code"] for f in r["findings"]]
        self.assertIn(PPC.C_GATE_OPEN, codes, "分发门禁必须被发现")
        self.assertIn(PPC.C_TEST_ONLY, codes, "TEST_ONLY 必须被发现")
        self.assertGreater(r["blocker_count"], 0)

    def test_synthetic_blocks_distribution(self):
        r = PPC.pre_publish_check(self._bundle(), self._view_like(),
                                  self.c["distribution"])
        self.assertIn(PPC.C_SYNTHETIC,
                      [f["code"] for f in r["findings"]])

    def test_hidden_limitations_detected(self):
        """产物隐藏限制信息时必须被发现。"""
        bundle = {"html": "<html><body>无限制</body></html>",
                  "json": json.loads(CRD.render_json(self.c))}
        r = PPC.pre_publish_check(bundle, self._view_like(),
                                  self.c["distribution"])
        self.assertIn(PPC.C_MISSING_LIMITS,
                      [f["code"] for f in r["findings"]],
                      "未展示的限制必须被检出")

    def test_external_resource_detected(self):
        bundle = {"html": "<html><script src='https://evil.com'></script></html>",
                  "json": {}}
        r = PPC.pre_publish_check(bundle, self._view_like(),
                                  self.c["distribution"])
        self.assertIn(PPC.C_EXTERNAL_RESOURCE,
                      [f["code"] for f in r["findings"]])

    def test_false_current_claim_detected(self):
        bundle = {"html": "<p>已验证当前 master 的权威结论</p>", "json": {}}
        r = PPC.pre_publish_check(bundle, self._view_like(),
                                  self.c["distribution"])
        self.assertIn(PPC.C_CLAIMS_CURRENT,
                      [f["code"] for f in r["findings"]])

    def test_third_party_expression_detected(self):
        protected = "Unsupported claims MUST NOT be presented as facts"
        bundle = {"html": f"<p>{protected}</p>", "json": {}}
        r = PPC.pre_publish_check(bundle, self._view_like(),
                                  self.c["distribution"])
        self.assertIn(PPC.C_THIRD_PARTY,
                      [f["code"] for f in r["findings"]])

    def test_distribution_never_true_even_all_supported(self):
        """★ 即使裁决是 supported、审核是 approved，也不得推导出可分发。

        这是 §12 的核心：知识验证结果与分发许可**独立**。
        """
        c = dict(self.c)
        c = json.loads(json.dumps(c))
        c["verification"] = dict(c["verification"])
        c["verification"]["status"] = "supported"
        c["verification"]["label"] = "支持"
        c["verification"]["meaning"] = "在指定范围内，现有经过验证的证据支持该命题。"
        c["review"] = dict(c["review"])
        c["review"]["status"] = "approved"
        c["review"]["label"] = "已人工批准"

        html = CRD.render_card_html(c)
        self.assertIn("supported", html)
        r = PPC.pre_publish_check(
            {"html": html, "json": json.loads(CRD.render_json(c))},
            {"authorization_is_test_only": True,
             "provenance_level": "SYNTHETIC_FIXTURE",
             "no_usable_evidence": False,
             "conflict_indicators": {},
             "limitations": c["limitations"]},
            c["distribution"])
        self.assertFalse(r["distribution_allowed"],
                         "supported/approved 不得推导出可分发")
        self.assertTrue(r["publish_blocked"])
        self.assertGreater(r["blocker_count"], 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
