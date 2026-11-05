#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-1..T-12 / T-32 / T-33：卡片渲染与语义忠实。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/renderer", "src/renderer", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import card_models as CM, card_renderer as CRD
import knowledge_view_assembler as KVA


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rc_"))
        self.ks = rfx.fresh(self.tmp)
    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestRender(Base):
    def test_t1_render_json_from_real_view(self):
        cards, src, res = rfx.make_cards(self.ks)
        self.assertGreaterEqual(len(cards), 1, "必须真产出卡片")
        c = cards[-1]
        text = CRD.render_json(c)
        doc = json.loads(text)
        self.assertEqual(doc["card_id"], c["card_id"])
        self.assertEqual(doc["verification"]["status"],
                         res.verification_status)

    def test_t2_render_html_from_real_view(self):
        cards, src, res = rfx.make_cards(self.ks)
        html = CRD.render_card_html(cards[-1])
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<title>", html)
        self.assertGreater(len(html), 2000)

    def test_t4_supported_rendered_as_is(self):
        cards, src, res = rfx.make_cards(
            self.ks, entries=[{"path": "README", "type": "blob",
                               "sha": "9" * 40, "size": 13, "mode": "100644"}])
        c = [x for x in cards if x["verification"]["status"] == "supported"][0]
        html = CRD.render_card_html(c)
        self.assertIn("supported", html)
        self.assertIn("支持", html)
        self.assertIn("现有经过验证的证据支持该命题", html)

    def test_t5_refuted_rendered_as_is(self):
        cards, src, res = rfx.make_cards(self.ks)
        c = [x for x in cards if x["verification"]["status"] == "refuted"][0]
        html = CRD.render_card_html(c)
        self.assertIn("refuted", html)
        self.assertIn("反驳", html)

    def test_t6_insufficient_not_hidden(self):
        cards, src, res = rfx.make_cards(self.ks, truncated=True)
        c = [x for x in cards
             if x["verification"]["status"] == "insufficient_evidence"][0]
        html = CRD.render_card_html(c)
        self.assertIn("insufficient_evidence", html)
        self.assertIn("证据不足", html)
        self.assertIn("无法作出支持或反驳裁决", html)

    def test_t7_possibly_stale_not_refuted(self):
        """POSSIBLY_STALE 不得被渲染成 refuted。"""
        cards, src, res = rfx.make_cards(self.ks)
        a_card = cards[0]
        self.assertEqual(a_card["freshness"]["state"], "POSSIBLY_STALE")
        html = CRD.render_card_html(a_card)
        self.assertIn("可能已过时", html)
        self.assertIn("这不表示旧结论已经失效或错误", html)
        # 新鲜度措辞不得混进裁决字段
        self.assertNotIn("refuted",
                         json.dumps(a_card["freshness"], ensure_ascii=False))

    def test_t8_unknown_not_current_valid(self):
        cards, src, res = rfx.make_cards(self.ks)
        c = cards[-1]
        self.assertEqual(c["freshness"]["current_applicability"],
                         "CURRENT_APPLICABILITY_UNKNOWN")
        html = CRD.render_card_html(c)
        self.assertIn("当前适用性未知", html)

        # ★ "当前最新" 只允许出现在**否定句**里
        #   （"不代表该仓库的当前最新状态"）——这是正确表述。
        #   禁止的是"肯定地宣称当前状态"。
        negated = ("不代表该仓库的当前最新状态" in html
                   or "不代表" in html)
        self.assertTrue(negated, "范围声明必须显式否定当前最新语义")

        for afirm in ("是最新版本", "即为当前最新", "当前有效结论",
                      "已验证当前", "已确认为当前"):
            self.assertNotIn(afirm, html, f"不得肯定宣称：{afirm}")

        # 结构上：不得出现"当前有效"作为状态值
        self.assertNotIn("当前有效", html)

    def test_t9_pending_review_not_approved(self):
        cards, src, res = rfx.make_cards(
            self.ks, entries=[{"path": "README", "type": "blob",
                               "sha": "9" * 40, "size": 13, "mode": "100644"}])
        c = [x for x in cards if x["verification"]["status"] == "supported"][0]
        self.assertEqual(c["review"]["status"], "pending_review")
        html = CRD.render_card_html(c)
        self.assertIn("待人工审核", html)
        self.assertNotIn("已人工批准", html)

    def test_t10_test_only_explicit(self):
        cards, src, res = rfx.make_cards(self.ks)
        c = cards[-1]
        self.assertTrue(c["authorization"]["test_only"])
        html = CRD.render_card_html(c)
        self.assertIn("TEST_ONLY", html)
        self.assertIn("未通过真实平台授权验收", html)

    def test_t11_synthetic_explicit(self):
        cards, src, res = rfx.make_cards(self.ks)
        c = cards[-1]
        self.assertEqual(c["provenance"]["level"], "SYNTHETIC_FIXTURE")
        html = CRD.render_card_html(c)
        self.assertIn("合成夹具", html)

    def test_t12_mixed_not_washed_to_real(self):
        prov = KVA._provenance_of(
            fresh={"provenance_level": "HISTORICAL_REAL_DATA"},
            run={"execution_source_level": "SYNTHETIC_FIXTURE"},
            chain={"snapshots": []})
        self.assertEqual(prov["provenance_level"], "SYNTHETIC_FIXTURE")
        self.assertTrue(prov["mixed_provenance"])

    def test_wording_check_rejects_amplification(self):
        cards, src, res = rfx.make_cards(self.ks)
        c = dict(cards[-1])
        c["limitations"] = list(c["limitations"]) + ["该软件完全正确"]
        self.assertTrue(CM.check_wording(c))
        with self.assertRaises(ValueError):
            CRD.render_card_html(c)


class TestDeterminism(Base):
    def test_t32_repeat_render_byte_identical(self):
        cards, src, res = rfx.make_cards(self.ks)
        c = cards[-1]
        a_html = CRD.render_card_html(c, assembled_at="")
        b_html = CRD.render_card_html(c, assembled_at="")
        self.assertEqual(a_html, b_html, "无时间戳时应逐字节一致")
        a_js = CRD.render_json(c)
        b_js = CRD.render_json(c)
        self.assertEqual(a_js, b_js)

    def test_t32b_timestamp_do_not_pollute(self):
        cards, src, res = rfx.make_cards(self.ks)
        c = cards[-1]
        h1 = CRD.render_card_html(c, assembled_at="2026-01-01T00:00:00")
        h2 = CRD.render_card_html(c, assembled_at="2030-01-01T00:00:00")
        self.assertNotEqual(h1, h2, "时间戳只进诊断页脚")
        self.assertEqual(c["card_id"], CM.card_id_of(
            KVA.assemble_from_verification(
                self.ks, verification_id=res.payload["target_verification_id"],
                repository_id=rfx.REPO)["view"]), "身份不受时间戳影响")

    def test_t33_input_order_not_affect(self):
        """证据引用排序后参与身份 → 顺序变化不改 card_id。"""
        cards, src, res = rfx.make_cards(self.ks)
        c = dict(cards[-1])
        v = KVA.assemble_from_verification(
            self.ks, verification_id=res.payload["target_verification_id"],
            repository_id=rfx.REPO)["view"]
        v2 = dict(v)
        refs = list(v2.get("evidence_refs") or [])
        v2["evidence_refs"] = list(reversed(refs))
        self.assertEqual(CM.card_id_of(v), CM.card_id_of(v2),
                         "引用顺序不得改变卡片身份")

    def test_different_commit_different_card_id(self):
        cards, src, res = rfx.make_cards(self.ks)
        a, b = cards[0], cards[-1]
        self.assertNotEqual(a["card_id"], b["card_id"],
                            "不同 Commit 不得生成相同卡片身份")


if __name__ == "__main__":
    unittest.main(verbosity=2)
