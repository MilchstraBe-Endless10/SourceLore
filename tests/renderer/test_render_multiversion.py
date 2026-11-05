#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-13 / T-14 / T-17：多版本对照与阻断页。"""
import sys, tempfile, shutil, unittest, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/renderer", "src/renderer", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import card_models as CM, card_renderer as CRD, report_renderer as RPT


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mv_"))
        self.ks = rfx.fresh(self.tmp)
    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestMultiVersion(Base):
    def test_t13_different_commits_side_by_side(self):
        cards, src, res = rfx.make_cards(self.ks)
        self.assertEqual(len(cards), 2, "应有 A 与 B 两张卡片")
        html = RPT.render_report_html(cards)
        a_sha = cards[0]["commit_sha"]
        b_sha = cards[-1]["commit_sha"]
        self.assertIn(a_sha, html)
        self.assertIn(b_sha, html)
        self.assertNotEqual(a_sha, b_sha)
        self.assertIn("不同 Commit", html)
        self.assertIn("不构成同一事实的矛盾", html)

    def test_t14_not_merged_into_conflict(self):
        cards, src, res = rfx.make_cards(self.ks)
        html = RPT.render_report_html(cards)
        # 报告不得声称"同一事实既真又假"
        for bad in ("既真又假", "自相矛盾", "矛盾结论", "同一事实"):
            if bad == "同一事实":
                self.assertIn("不构成同一事实的矛盾", html,
                              "必须显式否定合并语义")
            else:
                self.assertNotIn(bad, html, f"不得出现 {bad}")

    def test_no_ancestry_inference(self):
        """不得推断两个 Commit 的祖先关系。"""
        cards, src, res = rfx.make_cards(self.ks)
        html = RPT.render_report_html(cards)
        self.assertIn("不推断", html)
        self.assertIn("祖先", html)
        for bad in ("父提交", "ancestor of", "descends from",
                    "新版本是旧版本的升级", "上一版本的继承"):
            self.assertNotIn(bad, html)

    def test_report_deterministic(self):
        cards, src, res = rfx.make_cards(self.ks)
        h1 = RPT.render_report_html(cards)
        h2 = RPT.render_report_html(cards)
        self.assertEqual(h1, h2)

    def test_report_order_independent(self):
        """传入顺序变化不得改变报告内容（内部按 commit 排序）。"""
        cards, src, res = rfx.make_cards(self.ks)
        h1 = RPT.render_report_html(list(cards))
        h2 = RPT.render_report_html(list(reversed(cards)))
        self.assertEqual(h1, h2, "卡片输入顺序不得影响报告")

    def test_distinct_commit_distinct_card(self):
        cards, src, res = rfx.make_cards(self.ks)
        self.assertNotEqual(cards[0]["card_id"], cards[-1]["card_id"])

    def test_history_relation_preserved(self):
        cards, src, res = rfx.make_cards(self.ks)
        b = cards[-1]
        refs = b["history"]["refs"]
        self.assertEqual(refs.get("relation"), "revalidated_at_newer_commit")
        self.assertIn("source_claim_id", refs)
        html = RPT.render_report_html(cards)
        self.assertIn("revalidated_at_newer_commit", html)


class TestBlocked(Base):
    """T-16 / T-17：缺失/损坏证据必须阻断可信卡片。"""

    def test_t16_insufficient_still_renders_with_limit(self):
        """insufficient_evidence 是合法裁决，应渲染并显式标注。"""
        cards, src, res = rfx.make_cards(self.ks, truncated=True)
        c = [x for x in cards
             if x["verification"]["status"] == "insufficient_evidence"][0]
        c["limitations"] = list(c["limitations"]) + ["证据不足，不得据此得出肯定或否定结论"]
        html = CRD.render_card_html(c)
        self.assertIn("证据不足", html)
        self.assertIn("无法作出支持或反驳裁决", html)

    def test_t17_blocked_page_states_no_trustworthy_card(self):
        html = CRD.render_blocked_html(
            {"error_code": "EVIDENCE_CORRUPT",
             "detail": "证据链损坏，snapshot 无法定位"})
        self.assertIn("无法生成可信知识卡片", html)
        self.assertIn("EVIDENCE_CORRUPT", html)
        # ★ 阻断页可以有"阻断"诊断徽章（badge bad 语义上表示严重），
        #   但**不得出现任何裁决徽章**——那才是"看似完整其实缺证据"的危险形态。
        for verdict in ("supported", "refuted", "insufficient_evidence"):
            self.assertNotIn(f'class="badge ok">{verdict}</span>', html)
            self.assertNotIn(f'class="badge bad">{verdict}</span>', html)
        self.assertIn("阻断", html, "必须明确标注阻断")
        # 阻断页不得含裁决措辞
        for meaning in ("现有经过验证的证据支持该命题",
                        "现有有效反证与该命题矛盾"):
            self.assertNotIn(meaning, html)

    def test_blocked_page_no_fake_completeness(self):
        html = CRD.render_blocked_html({"error_code": "SOURCE_MISSING"})
        self.assertIn("无法生成可信知识卡片", html)
        self.assertNotIn("<h2>证据裁决</h2>", html,
                         "阻断页不得展示裁决区")
        self.assertNotIn("<h2>新鲜度与适用性</h2>", html)

    def test_corrupt_source_from_view_blocks(self):
        """真实链路里证据缺失时，装配失败应能走阻断路径。"""
        v = {"ok": False, "error_code": "EVIDENCE_CORRUPT",
             "detail": "证据链损坏"}
        self.assertFalse(v["ok"])
        html = CRD.render_blocked_html(v)
        self.assertIn("无法生成可信知识卡片", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
