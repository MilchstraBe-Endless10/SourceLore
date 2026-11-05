#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多版本装配：A→B→C 三个 Commit 的独立视图。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/views", "src/views", "src/lifecycle", "src/storage",
          "src/collector", "src/facts", "src/evidence_claims", "src/runtime"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import vfx
import knowledge_view_assembler as KVA
import view_models as VM
import view_integrity as VI
import revalidation_queue as RQ
import revalidation_models as RM


class TestMultiVersion(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mv_"))
        self.ks = vfx.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _view(self, vid):
        return KVA.assemble_from_verification(
            self.ks, verification_id=vid, repository_id=vfx.REPO)

    def test_a_and_b_views_are_distinct(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        va = self._view(src["verification_id"])
        vb = self._view(res.payload["target_verification_id"])
        self.assertTrue(va["ok"], va)
        self.assertTrue(vb["ok"], vb)
        self.assertNotEqual(va["view_id"], vb["view_id"],
                            "不同 Claim/Commit 的视图身份不得碰撞")
        self.assertEqual(va["view"]["claim_commit_sha"], vfx.A)
        self.assertEqual(vb["view"]["claim_commit_sha"], vfx.B)

    def test_b_then_c_creates_third_version(self):
        """B 已裁决后 Ref 移到 C → C 是新候选，B 视图保持绑 B。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        vb = self._view(res.payload["target_verification_id"])["view"]
        self.assertEqual(vb["claim_commit_sha"], vfx.B)

        # 触发 C
        r_c, watch_c, a_c = vfx.make_candidate(
            self.ks, baseline=vfx.B, target=vfx.C, claim_id=src["claim_id"])
        self.assertTrue(r_c.get("ok"), r_c)
        q = RQ.read_queue(self.ks, watch_id=watch_c.watch_id,
                          repository_id=vfx.REPO)
        self.assertEqual(q["active_target_commit_sha"], vfx.C)
        self.assertNotEqual(q["active_candidate_id"], cand["candidate_id"])

        # B 的视图不变
        vb2 = self._view(res.payload["target_verification_id"])["view"]
        self.assertEqual(vb2["view_id"], vb["view_id"], "B 视图必须稳定")
        self.assertEqual(vb2["claim_commit_sha"], vfx.B)
        self.assertEqual(vb2["current_applicability"],
                         VM.E_CURRENT_APPLICABILITY_UNKNOWN)

        # B 结果不被提升为 C 的当前结论
        self.assertNotIn("valid_for_current_ref", vb2)
        self.assertNotEqual(vb2["current_applicability"], "CURRENT_VALID")

    def test_multiple_verifications_same_claim_distinguished(self):
        """同一 Claim 的两条 Verification 版本可分别读取、身份不同。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        # 同一目标 Claim 再验证一次（确定性身份 → 相同 verification_id）
        rows = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(rows, 2, "源 1 + 目标 1")
        ids = set()
        for r in self.ks.conn.execute(
                "SELECT logical_identity FROM assets "
                "WHERE asset_type='claim_verification'").fetchall():
            ids.add(r["logical_identity"])
        self.assertEqual(len(ids), 2, "两条 verification 身份必须不同")

    def test_history_refs_link_a_to_b(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        v = self._view(res.payload["target_verification_id"])["view"]
        h = v["history_refs"]
        self.assertEqual(h["source_claim_id"], src["claim_id"],
                         "必须能追溯到源 Claim")
        self.assertEqual(h["source_verification_id"], src["verification_id"])
        self.assertIsNotNone(h["candidate_id"])
        self.assertEqual(h["relation"], "revalidated_at_newer_commit")

    def test_old_claim_still_bound_to_a(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        row = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE logical_identity=?",
            (src["claim_id"],)).fetchone()
        p = json.loads(row["payload_json"])
        self.assertEqual(p["commit_sha"], vfx.A, "旧 Claim 仍绑 A")
        self.assertEqual(p["review_status"], "pending_review")
        # B 的裁决没有改写 A
        self.assertEqual(src["status"], "supported")

    def test_no_cross_commit_fact_merging(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        # 目标 Claim 的 fact 只能属于 B
        fact_ids = res.payload["fact_refs"]
        for fid in fact_ids:
            row = self.ks.conn.execute(
                "SELECT payload_json FROM assets WHERE logical_identity=?",
                (fid,)).fetchone()
            p = json.loads(row["payload_json"])
            self.assertEqual(p["commit_sha"], vfx.B,
                             "目标 fact 不得来自其它 Commit")

    def test_view_has_no_merged_verdict_field(self):
        """视图结构上不提供"跨版本合并裁决"。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        v = self._view(res.payload["target_verification_id"])["view"]
        for forbidden in ("is_valid", "overall_status", "combined_status",
                          "final_verdict", "effective_status"):
            self.assertNotIn(forbidden, v, f"不得有 {forbidden} 字段")

    def test_history_refs_does_not_claim_current(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        v = self._view(res.payload["target_verification_id"])["view"]
        self.assertNotEqual(v["history_refs"].get("relation"), "current")


if __name__ == "__main__":
    unittest.main(verbosity=2)
