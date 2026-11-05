#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P4C：Trusted Statement Bank / STRICT_CITED / DRAFT / 逐句引用校验。"""
import sys, tempfile, shutil, unittest, json, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/research", "src/research", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import statement_bank as SB, citation_validator as CV
import llm_adapter as LA, synthesis_engine as SE


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="syn_"))
        cls.ks = rfx.fresh(cls.tmp)
        rfx.vfx.run_full(cls.ks)
        cls.pkt = rfx.run(cls.ks, rfx.q_claims())
        cls.bank = SB.build_bank(cls.pkt)
        cls.ids = {s["kind"]: [x["statement_id"] for x in cls.bank["statements"]
                               if x["kind"] == s["kind"]]
                   for s in cls.bank["statements"]}

    @classmethod
    def tearDownClass(cls):
        try: cls.ks.close()
        except Exception: pass
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestStatementBank(Base):
    def test_bank_has_statements(self):
        self.assertGreater(self.bank["statement_count"], 0)

    def test_every_statement_bound_to_refs(self):
        """★ 每条陈述都必须绑定引用。"""
        for s in self.bank["statements"]:
            self.assertTrue(s["finding_refs"], f"{s['statement_id']} 无引用")

    def test_fact_statements_trace_to_findings(self):
        fid = {f["finding_id"] for f in self.pkt["findings"]}
        for s in self.bank["statements"]:
            if s["kind"].startswith("FACT_"):
                for r in s["finding_refs"]:
                    self.assertIn(r, fid, "事实陈述必须绑定真实 finding")

    def test_no_statement_without_finding(self):
        """★ 研究包没有 finding 时不得凭空造事实陈述。"""
        empty = copy.deepcopy(self.pkt)
        empty["findings"] = []
        bank = SB.build_bank(empty)
        facts = [s for s in bank["statements"]
                 if s["kind"].startswith("FACT_")]
        self.assertEqual(facts, [], "无 finding 不得生成事实陈述")

    def test_bank_deterministic(self):
        b2 = SB.build_bank(self.pkt)
        self.assertEqual(self.bank["bank_digest"], b2["bank_digest"])

    def test_bank_contains_limitations(self):
        lims = [s for s in self.bank["statements"]
                if s["kind"] == SB.S_LIMITATION]
        self.assertGreater(len(lims), 0, "限制必须进陈述池")


class TestValidator(Base):
    def test_cited_sentence_ok(self):
        sid = self.ids["FACT_SUPPORTED"][0]
        v = CV.validate({"text": "在固定 Commit 上，该路径存在命题的裁决为 supported（支持）。",
                         "statement_refs": [sid]}, self.bank)
        self.assertTrue(v["is_strict_citable"])
        self.assertEqual(v["overall"], CV.C_OK)

    def test_no_citation_not_strict(self):
        v = CV.validate({"text": "该路径存在。", "statement_refs": []}, self.bank)
        self.assertFalse(v["is_strict_citable"])
        self.assertEqual(v["uncited_count"], 1)

    def test_fake_reference_blocking(self):
        v = CV.validate({"text": "该路径存在。",
                         "statement_refs": ["SL-ST-FAKE"]}, self.bank)
        self.assertIn(CV.C_BAD_CITATION, v["blocking_failures"])
        self.assertIn("SL-ST-FAKE", v["unbound_references"])

    def test_amplify_blocking(self):
        sid = self.ids["FACT_SUPPORTED"][0]
        for phrase in ("完全正确", "功能完备", "该软件存在漏洞"):
            v = CV.validate({"text": f"该命题{phrase}。",
                             "statement_refs": [sid]}, self.bank)
            self.assertIn(CV.C_AMPLIFIED, v["blocking_failures"], phrase)

    def test_insufficient_as_negation_blocking(self):
        """★ 把证据不足写成否定 = 阻断。"""
        sid = self.ids.get("FACT_INSUFFICIENT", self.ids["FACT_SUPPORTED"])[0]
        v = CV.validate({"text": "该命题为假。", "statement_refs": [sid]},
                        self.bank)
        self.assertIn(CV.C_NEGATED_INSUFFICIENT, v["blocking_failures"])

    def test_sentence_split(self):
        s = CV.split_sentences("甲。乙！丙？")
        self.assertEqual(len(s), 3)


class TestSynthesis(Base):
    def test_no_client_no_synthesis(self):
        """★ 无 LLM 客户端 → 绝不产出叙述。"""
        r = SE.synthesize(self.pkt)
        self.assertEqual(r["synthesis_state"], SE.S_NONE)
        self.assertEqual(r["text"], "")
        self.assertFalse(r["llm_used"])
        self.assertFalse(r["real_call_verified"])

    def _run(self, preset):
        return SE.synthesize(self.pkt, client=LA.make_stub_client(preset))

    def test_strict_cited_path(self):
        sid = self.ids["FACT_SUPPORTED"][0]
        r = self._run({"text": "在固定 Commit 上，该路径存在命题的裁决为 supported（支持）。",
                       "statement_refs": [sid]})
        self.assertEqual(r["verdict"], LA.SYN_STRICT)
        self.assertFalse(r["review_required"])

    def test_draft_path(self):
        r = self._run({"text": "该路径存在。", "statement_refs": []})
        self.assertEqual(r["verdict"], LA.SYN_DRAFT)
        self.assertTrue(r["review_required"])

    def test_rejected_on_amplify(self):
        sid = self.ids["FACT_SUPPORTED"][0]
        r = self._run({"text": "该软件完全正确。", "statement_refs": [sid]})
        self.assertEqual(r["verdict"], LA.SYN_REJECTED)

    def test_rejected_on_fake_ref(self):
        r = self._run({"text": "该路径存在。", "statement_refs": ["SL-ST-FAKE"]})
        self.assertEqual(r["verdict"], LA.SYN_REJECTED)

    def test_never_publishable(self):
        """★ 任何合成产物都不可发布、不是知识权威。"""
        for preset in ({}, {"text": "x。", "statement_refs": []},
                       {"text": "该软件完全正确。", "statement_refs": []}):
            r = self._run(preset)
            self.assertFalse(r["is_knowledge_authority"])
            self.assertFalse(r["publishable"])

    def test_limitations_and_gate_inherited(self):
        r = self._run({"text": "该路径存在。", "statement_refs": []})
        self.assertIn("limitations", r)
        self.assertFalse(
            r["distribution_restrictions"]["distribution_allowed"])

    def test_synthesis_id_deterministic(self):
        sid = self.ids["FACT_SUPPORTED"][0]
        preset = {"text": "在固定 Commit 上，该路径存在命题的裁决为 supported（支持）。",
                  "statement_refs": [sid]}
        a = self._run(preset)
        b = self._run(preset)
        self.assertEqual(a["synthesis_id"], b["synthesis_id"])

    def test_stub_never_real_verified(self):
        """★ stub 永远不得声称真实调用已验证。"""
        r = self._run({"text": "该路径存在。", "statement_refs": []})
        self.assertEqual(r["adapter_state"], LA.A_STUB)
        self.assertFalse(r["real_call_verified"])
        self.assertIn("不代表任何真实模型能力", r["note"])

    def test_no_network_in_source(self):
        for f in (ROOT/"src"/"research").glob("*.py"):
            # 允许出现 olama: 之类占位，但不得有真实客户端依赖
            t = f.read_text(encoding="utf-8")
            for tok in ("import requests", "import httpx", "urllib.request"):
                self.assertNotIn(tok, t, f"{f.name} 不得引入 {tok}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
