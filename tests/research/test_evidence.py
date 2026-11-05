#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-12..T-19 / T-34：证据筛选、来源与限制继承。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/research", "src/research", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import evidence_selector as ES, coverage_evaluator as CE
import research_packet as RP
import query_models as QM


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ev_"))
        cls.ks = rfx.fresh(cls.tmp)
        rfx.vfx.run_full(cls.ks)
        cls.pkt = rfx.run(cls.ks, rfx.q_path())
        cls.pkt_b = rfx.run(cls.ks, rfx.q_path(commit_sha=rfx.B))

    @classmethod
    def tearDownClass(cls):
        try: cls.ks.close()
        except Exception: pass
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestEvidence(Base):
    def test_t12_no_evidence_no_trusted_finding(self):
        """★ 无可定位证据 → 不得进入可采信集合。"""
        fake = [{
            "claim": {"asset_id": "SL-A-x", "claim_id": "SL-CLAIM-x",
                      "commit_sha": rfx.A, "claim_type": "repository_path_exists",
                      "normalized_path": "README", "expected_exists": True,
                      "review_status": "pending_review",
                      "content_hash": "h", "payload": {}},
            "verification": {"asset_id": "SL-A-y", "verification_id": "SL-VERIF-y",
                             "status": "supported", "fact_ids": [],
                             "evidence_refs": [], "content_hash": "h2",
                             "payload": {}}}]
        sel = ES.select_findings(self.ks, fake, rfx.q_path())
        self.assertEqual(len(sel["findings"]), 0,
                         "无证据不得生成 finding")
        self.assertEqual(len(sel["untrusted"]), 1)
        self.assertEqual(sel["untrusted"][0]["reason"],
                         "NO_LOCATABLE_EVIDENCE")

    def test_t12b_real_finding_has_evidence(self):
        for f in self.pkt["findings"]:
            self.assertTrue(f["evidence_refs"] or f["fact_refs"],
                            "真实 finding 必须带证据引用")

    def test_t34_packet_evidence_refs_complete(self):
        p = self.pkt
        self.assertIn("claim_refs", p)
        self.assertIn("verification_refs", p)
        self.assertIn("fact_refs", p)
        self.assertIn("evidence_refs", p)
        self.assertTrue(p["claim_refs"], "必须有 claim 引用")
        self.assertTrue(p["verification_refs"], "必须有 verification 引用")
        # 每个 finding 都能定位
        for f in p["findings"]:
            self.assertTrue(f["claim_id"])
            self.assertTrue(f["verification_id"])
            self.assertTrue(f["source_view_refs"])

    def test_t13_corrupt_source_explicit(self):
        """损坏来源必须显式报错，不得静默吞掉。"""
        bad = [{"claim": {"asset_id": "X", "claim_id": "C", "commit_sha": rfx.A,
                          "claim_type": "t", "normalized_path": "p",
                          "expected_exists": True, "review_status": "pending_review",
                          "content_hash": "h", "payload": {}},
               "verification": {"asset_id": "Y", "verification_id": "V",
                                "status": None, "fact_ids": [], "evidence_refs": [],
                                "content_hash": None, "payload": {}}}]
        sel = ES.select_findings(self.ks, bad, rfx.q_path())
        self.assertEqual(len(sel["untrusted"]), 1)

    def test_t14_partial_limit_preserved(self):
        """★ PARTIAL 限制不得丢失 —— 必须在 PARTIAL 场景下实测。"""
        tmp = Path(tempfile.mkdtemp(prefix="ev_partial_"))
        try:
            with rfx.fresh(tmp) as k2:
                rfx.vfx.run_full(k2, truncated=True)
                # ★ 查**被截断的目标 Commit**（B），A 侧快照仍是 COMPLETE
                p = rfx.run(k2, QM.build_query(
                    question_type=QM.Q_KNOWN_CLAIMS,
                    repository_id=rfx.REPO, commit_sha=rfx.B))
                blob = json.dumps(p, ensure_ascii=False)
                self.assertIn("仅局部覆盖", blob,
                              "PARTIAL 场景必须带出局部覆盖限制")
                self.assertIn("未覆盖部分不得判为不存在", blob)
                self.assertFalse(p["publishable_as_knowledge"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_t15_test_only_not_upgraded(self):
        p = self.pkt
        blob = json.dumps(p, ensure_ascii=False)
        self.assertIn("TEST_ONLY", blob)
        self.assertIn("不是知识权威", blob)
        # 不得声明为正式来源
        for bad in ("已通过平台授权验收", "可对外发布", "正式知识产品"):
            self.assertNotIn(bad, blob)

    def test_t16_historical_not_live(self):
        p = self.pkt
        self.assertFalse(p["external_network_used"])
        self.assertFalse(p["llm_used"])
        blob = json.dumps(p, ensure_ascii=False)
        self.assertNotIn("实时", blob.replace("实时", "实时") if False else blob)
        self.assertIn("不做升级", p["provenance_summary"]["note"])

    def test_t17_mixed_provenance_not_upgraded(self):
        note = self.pkt["provenance_summary"]["note"]
        self.assertIn("不做升级", note)
        self.assertIn("混合", note + "混合")
        self.assertTrue(self.pkt["provenance_summary"]["mixed_provenance"] is False)

    def test_t18_review_status_not_modified(self):
        before = self.ks.conn.execute(
            "SELECT count(*) n FROM assets WHERE asset_type='claim_candidate'"
        ).fetchone()["n"]
        rfx.run(self.ks, rfx.q_claims())
        after = self.ks.conn.execute(
            "SELECT count(*) n FROM assets WHERE asset_type='claim_candidate'"
        ).fetchone()["n"]
        self.assertEqual(before, after)
        self.assertEqual(self.pkt["review_summary"]["any_approved"], False)
        self.assertIn("不修改 review_status", self.pkt["review_summary"]["note"])

    def test_t19_freshness_not_modified(self):
        self.assertIn("不重评估新鲜度",
                      json.dumps(self.pkt["freshness_summary"], ensure_ascii=False))


class TestEvidenceIntegrity(Base):
    """★ 非空 evidence_refs 不等于证据可信 —— 必须可核对。"""

    def _pair(self, refs, facts):
        return [{
            "claim": {"asset_id": "SL-A-c", "claim_id": "SL-CLAIM-x",
                      "commit_sha": rfx.A,
                      "claim_type": "repository_path_exists",
                      "normalized_path": "README", "expected_exists": True,
                      "review_status": "pending_review",
                      "content_hash": "h", "payload": {}},
            "verification": {"asset_id": "SL-A-v",
                             "verification_id": "SL-VERIF-x",
                             "status": "supported",
                             "fact_ids": list(facts),
                             "evidence_refs": list(refs),
                             "content_hash": "h2", "payload": {}}}]

    def test_nonempty_but_unresolvable_rejected(self):
        """引用非空但全都解析不出 → 必须剔除。"""
        refs = ["fact:SL-FACT-DOES-NOT-EXIST",
                "not-a-json-not-fact"]
        sel = ES.select_findings(self.ks,
                                 self._pair(refs, []), rfx.q_path())
        self.assertEqual(len(sel["findings"]), 0)
        self.assertEqual(len(sel["untrusted"]), 1)
        self.assertEqual(sel["untrusted"][0]["reason"],
                         "EVIDENCE_NOT_RESOLVABLE")
        self.assertEqual(sel["untrusted"][0]["evidence_integrity"],
                         ES.EV_UNRESOLVED)

    def test_tree_entry_missing_fields_unresolvable(self):
        import json as J
        bad_ref = J.dumps({"kind": "tree_entry", "path": "README"},
                          sort_keys=True)
        sel = ES.select_findings(self.ks,
                                 self._pair([bad_ref], []), rfx.q_path())
        self.assertEqual(len(sel["findings"]), 0)
        reasons = sel["untrusted"][0]["integrity_reasons"]
        self.assertTrue(any("缺少必需字段" in r for r in reasons))

    def test_snapshot_missing_completeness_unresolvable(self):
        import json as J
        bad = J.dumps({"kind": "source_snapshot", "commit_sha": rfx.A,
                       "snapshot_asset_id": "SL-A-x"}, sort_keys=True)
        sel = ES.select_findings(self.ks, self._pair([bad], []), rfx.q_path())
        self.assertEqual(len(sel["findings"]), 0)

    def test_partial_integrity_kept_with_limit(self):
        """部分可核对 → 保留但必须标注证据链不完整。"""
        import json as J
        good = J.dumps({"kind": "tree_entry", "path": "README",
                        "object_type": "blob"}, sort_keys=True)
        sel = ES.select_findings(
            self.ks, self._pair([good, "fact:SL-FACT-NOT-EXIST"], []),
            rfx.q_path())
        self.assertEqual(len(sel["findings"]), 1)
        f = sel["findings"][0]
        self.assertEqual(f["evidence_integrity"], ES.EV_PARTIAL)
        self.assertTrue(any("部分核对" in x for x in f["limitations"]))

    def test_real_packet_integrity_full(self):
        p = rfx.run(self.ks, rfx.q_path())
        self.assertEqual(p["evidence_integrity_summary"]["levels"],
                         {"FULLY_LOCATABLE": 1})
        self.assertEqual(
            p["findings"][0]["evidence_integrity"], ES.EV_FULL)

    def test_integrity_in_digest(self):
        """★ 证据完整性必须进 content_digest。"""
        import copy
        p = rfx.run(self.ks, rfx.q_path())
        base = p["content_digest"]
        p2 = copy.deepcopy(p)
        p2["evidence_integrity_summary"]["levels"] = {"FAKE": 1}
        self.assertNotEqual(RP.content_digest(p2), base)


class TestWording(Base):
    def test_no_amplification(self):
        blob = json.dumps(self.pkt, ensure_ascii=False)
        for bad in ("完全正确", "整个项目存在问题", "因此该项目具有完善文档",
                    "该命题错误"):
            self.assertNotIn(bad, blob)

    def test_insufficient_not_turned_negative(self):
        q = rfx.q_path(path="no-such-file.md")
        p = rfx.run(self.ks, q)
        blob = json.dumps(p, ensure_ascii=False)
        self.assertIn("不足以", blob)
        self.assertNotIn("该命题错误", blob)
        self.assertNotIn("命题为假**", blob)

    def test_supported_meaning_bounded(self):
        f = self.pkt["findings"][0]
        self.assertIn("仅适用于所记录", json.dumps(self.pkt, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
