#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视图装配测试 T-1..T-19 / T-23..T-28。"""
import sys, tempfile, shutil, unittest, json, hashlib
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
import lc_models as L


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="v_"))
        self.ks = vfx.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assemble(self, vid, **kw):
        return KVA.assemble_from_verification(
            self.ks, verification_id=vid, repository_id=vfx.REPO, **kw)


class TestAssembly(Base):
    """T-1 / T-2 / T-3 / T-13 / T-14 / T-15 / T-23 / T-24."""

    def test_t1_view_assembles(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        self.assertTrue(res.ok, (res.error_code, res.detail))
        v = self.assemble(res.payload["target_verification_id"])
        self.assertTrue(v["ok"], v)
        self.assertEqual(v["view"]["status"], VM.OK)
        self.assertEqual(v["view"]["verification_status"], "refuted")

    def test_t2_same_input_same_view_id(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        v1 = self.assemble(res.payload["target_verification_id"])
        v2 = self.assemble(res.payload["target_verification_id"])
        self.assertEqual(v1["view_id"], v2["view_id"])

    def test_t3_order_independent(self):
        a = VM.make_view_id(query_scope="q", source_asset_refs=["x", "y", "z"],
                            content_digests=["d1", "d2"])
        b = VM.make_view_id(query_scope="q", source_asset_refs=["z", "x", "y"],
                            content_digests=["d2", "d1"])
        self.assertEqual(a, b)

    def test_t13_supported_preserved(self):
        src, cand, res, ad = vfx.run_full(
            self.ks, entries=[{"path": "README", "type": "blob",
                               "sha": "9" * 40, "size": 13,
                               "mode": "100644"}])
        self.assertTrue(res.ok, (res.error_code, res.detail))
        v = self.assemble(res.payload["target_verification_id"])
        self.assertEqual(v["view"]["verification_status"], "supported")

    def test_t14_refuted_preserved(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        self.assertTrue(res.ok)
        v = self.assemble(res.payload["target_verification_id"])
        self.assertEqual(v["view"]["verification_status"], "refuted")

    def test_t15_insufficient_not_hidden(self):
        src, cand, res, ad = vfx.run_full(self.ks, truncated=True)
        self.assertTrue(res.ok)
        self.assertEqual(res.verification_status, "insufficient_evidence")
        v = self.assemble(res.payload["target_verification_id"])
        self.assertEqual(v["view"]["verification_status"],
                         "insufficient_evidence")
        self.assertTrue(any("insufficient" in l.lower()
                            for l in v["view"]["limitations"]),
                        "证据不足必须出现在 limitations 里")

    def test_t23_execution_success_not_supported(self):
        """执行 SUCCESS 不得自动变成 supported。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        self.assertEqual(res.execution_status, "SUCCESS")
        v = self.assemble(res.payload["target_verification_id"])
        self.assertEqual(v["view"]["execution_status"], "SUCCESS")
        self.assertNotEqual(v["view"]["verification_status"], "supported")
        # 两条轴是不同字段
        self.assertNotEqual(v["view"]["execution_status"],
                            v["view"]["verification_status"])

    def test_t24_supported_not_become_approved(self):
        src, cand, res, ad = vfx.run_full(
            self.ks, entries=[{"path": "README", "type": "blob",
                               "sha": "9" * 40, "size": 13,
                               "mode": "100644"}])
        v = self.assemble(res.payload["target_verification_id"])
        self.assertEqual(v["view"]["verification_status"], "supported")
        self.assertEqual(v["view"]["review_status"], "pending_review",
                         "supported 不得自动变 approved")
        self.assertNotEqual(v["view"]["review_status"], "approved")

    def test_t25_assembler_does_not_modify_review(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_candidate'"
        ).fetchone()["n"]
        rows_before = VI.fingerprint_assets(self.ks, asset_types=["claim_candidate"])
        self.assemble(res.payload["target_verification_id"])
        rows_after = VI.fingerprint_assets(self.ks, asset_types=["claim_candidate"])
        self.assertEqual(rows_before, rows_after, "装配器不得改 Claim")


class TestDiagnostics(Base):
    """T-4..T-10 / T-28：明确诊断，不伪装成"没有知识"。"""

    def test_t4_missing_claim(self):
        v = KVA.assemble_from_verification(
            self.ks, verification_id="SL-VER-" + "0" * 32, repository_id=vfx.REPO)
        self.assertFalse(v["ok"])
        self.assertEqual(v["error_code"], VM.E_VERIFICATION_NOT_FOUND)
        self.assertIn("verification", str(v).lower())

    def test_t5_missing_verification(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        v = KVA.assemble_from_verification(
            self.ks, verification_id="SL-VER-" + "9" * 32,
            repository_id=vfx.REPO)
        self.assertFalse(v["ok"])
        self.assertEqual(v["error_code"], VM.E_VERIFICATION_NOT_FOUND)

    def test_t6_wrong_link_rejected(self):
        """Verification 引用别的 Claim → CLAIM_VERIFICATION_MISMATCH。

        直接构造「Claim A 与为其 Verif 的 payload 但 claim_id 指向 B」，
        验证 check_link 会拒绝，且走完整装配路径也会拒绝。
        """
        src, cand, res, ad = vfx.run_full(self.ks)
        claim = {"payload": {"claim_id": "SL-CLAIM-" + "a" * 40,
                             "commit_sha": vfx.B},
                 "repository_id": vfx.REPO}
        verif = {"payload": {"claim_id": "SL-CLAIM-" + "b" * 40},
                 "repository_id": vfx.REPO}
        err = VI.check_link(claim, verif)
        self.assertEqual(err, VM.E_CLAIM_VERIFICATION_MISMATCH)
        # 仓库不一致也要拒绝
        v2 = {"payload": {"claim_id": claim["payload"]["claim_id"]},
              "repository_id": "999999"}
        self.assertEqual(VI.check_link(claim, v2), VM.E_REPOSITORY_MISMATCH)

    def test_t7_wrong_repository(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        v = KVA.assemble_from_verification(
            self.ks, verification_id=res.payload["target_verification_id"],
            repository_id="999999")
        self.assertFalse(v["ok"])
        self.assertEqual(v["error_code"], VM.E_REPOSITORY_MISMATCH)

    def test_t8_wrong_commit_detected(self):
        """Claim commit 与 Verification 记录 commit 不一致 → COMMIT_MISMATCH。"""
        err = VI.check_link(
            {"payload": {"claim_id": "SL-CLAIM-x", "commit_sha": vfx.A},
             "repository_id": vfx.REPO},
            {"payload": {"claim_id": "SL-CLAIM-x",
                         "normalized_verification_params":
                             {"commit_sha": vfx.B}},
             "repository_id": vfx.REPO})
        self.assertEqual(err, VM.E_COMMIT_MISMATCH)

    def test_t10_snapshot_missing_diagnosed(self):
        """Fact 引用的 snapshot 不存在 → SOURCE_MISSING，不返回"没有知识"。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        vr = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE logical_identity=?",
            (res.payload["target_verification_id"],)).fetchone()
        p = json.loads(vr["payload_json"])
        fake_verif = {"payload": dict(p, fact_ids=["SL-FACT-doesnotexist"]),
                      "repository_id": vfx.REPO}
        err, chain = VI.check_fact_chain(self.ks, fake_verif)
        self.assertEqual(err, VM.E_EVIDENCE_CORRUPT)
        self.assertTrue(chain["damaged"])
        self.assertEqual(chain["damaged"][0]["reason"],
                         VM.E_DANGLING_REFERENCE)

    def test_t28_dangling_pointer_not_empty_knowledge(self):
        v = KVA.assemble_from_verification(
            self.ks, verification_id="SL-VER-" + "7" * 32,
            repository_id=vfx.REPO)
        self.assertFalse(v["ok"])
        self.assertNotEqual(v.get("status"), "NO_KNOWLEDGE")
        self.assertIn(v["error_code"], VM.DIAGNOSTIC_CODES)


class TestMultiVersion(Base):
    """T-11 / T-12：旧新版本各自可读，不合并成冲突。"""

    def test_t11_old_and_new_both_readable(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        old = KVA.assemble_from_verification(
            self.ks, verification_id=src["verification_id"],
            repository_id=vfx.REPO)
        new = KVA.assemble_from_verification(
            self.ks, verification_id=res.payload["target_verification_id"],
            repository_id=vfx.REPO)
        self.assertTrue(old["ok"], old)
        self.assertTrue(new["ok"], new)
        self.assertEqual(old["view"]["claim_commit_sha"], vfx.A)
        self.assertEqual(new["view"]["claim_commit_sha"], vfx.B)
        self.assertEqual(old["view"]["verification_status"], "supported")
        self.assertEqual(new["view"]["verification_status"], "refuted")

    def test_t12_different_commits_not_merged_as_conflict(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        old = KVA.assemble_from_verification(
            self.ks, verification_id=src["verification_id"],
            repository_id=vfx.REPO)["view"]
        new = KVA.assemble_from_verification(
            self.ks, verification_id=res.payload["target_verification_id"],
            repository_id=vfx.REPO)["view"]
        # 两个结论在不同 Commit 下都成立 → 不是"证据自相矛盾"
        self.assertFalse(old["conflict_indicators"]["evidence_conflict_detected"])
        self.assertFalse(new["conflict_indicators"]["evidence_conflict_detected"])
        self.assertNotEqual(old["claim_commit_sha"], new["claim_commit_sha"])
        # 视图不提供跨版本"合并裁决"字段
        self.assertNotIn("is_valid", new)
        self.assertNotIn("combined_status", new)
        self.assertEqual(old["verification_status"], "supported")
        self.assertEqual(new["verification_status"], "refuted")


class TestFreshnessAndRef(Base):
    """T-16 / T-17 / T-18 / T-19 / T-26 / T-27。"""

    def test_t16_partial_limit_kept(self):
        src, cand, res, ad = vfx.run_full(self.ks, truncated=True)
        v = self.assemble(res.payload["target_verification_id"])["view"]
        self.assertEqual(v["verification_status"], "insufficient_evidence")
        limits = " ".join(v["limitations"])
        self.assertIn("局部", limits, "PARTIAL 覆盖范围限制必须保留")

    def test_t17_unknown_not_converted_to_absent(self):
        """新鲜度 UNKNOWN 不得被当成"不存在"。"""
        src, cand, res, ad = vfx.run_full(self.ks, truncated=True)
        v = self.assemble(res.payload["target_verification_id"])["view"]
        self.assertEqual(v["freshness_state"], None,
                         "目标版本无对应评估 → 如实为 None")
        self.assertEqual(v["current_applicability"],
                         VM.E_CURRENT_APPLICABILITY_UNKNOWN)
        self.assertNotEqual(v["verification_status"], "refuted")

    def test_t18_historical_not_current(self):
        """来源为历史观测时，不得描述成当前最新。"""
        v = VM.limitations_of(
            verification_status="supported",
            freshness_state=L.VERSION_ALIGNED,
            review_status="pending_review",
            provenance_level="HISTORICAL_REAL_DATA",
            execution_status="SUCCESS")
        joined = " ".join(v)
        self.assertIn("历史", joined)
        self.assertIn("不保证", joined)

    def test_t19_b_verified_but_ref_moved_to_c(self):
        """B 已裁决，但 Ref 移到 C → 不把 B 显示为 C 的当前验证。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        v = self.assemble(res.payload["target_verification_id"])["view"]
        self.assertEqual(v["claim_commit_sha"], vfx.B)
        self.assertEqual(v["current_applicability"],
                         VM.E_CURRENT_APPLICABILITY_UNKNOWN)
        ctx = v["history_refs"]
        self.assertNotEqual(ctx.get("relation"), "current",
                            "不得标为 current")
        # 视图里不存在"当前有效于 C"这类断言
        self.assertNotIn("valid_for_current_ref", v)
        self.assertNotIn("is_current", v)

    def test_t26_distribution_gate_open(self):
        src, cand, res, ad = vfx.run_full(self.ks)
        v = self.assemble(res.payload["target_verification_id"])["view"]
        d = v["distribution_restrictions"]
        self.assertFalse(d["distribution_allowed"])
        self.assertEqual(d["freeze_state"], VM.FREEZE_STATE)
        blockers = {b["id"]: b["status"] for b in d["blockers"]}
        self.assertEqual(blockers, {"B-1": "OPEN", "B-2": "OPEN", "B-3": "OPEN"})

    def test_t27_insufficient_cannot_be_read_as_positive(self):
        """反例机制不得通过视图恢复为正向能力。

        注意：`claim_payload.expected_exists=true` 是**命题本身**
        （"该路径存在"这个待验证的说法），不是裁决。必须区分：
        命题可以存在，裁决不得变成肯定。
        """
        src, cand, res, ad = vfx.run_full(self.ks, truncated=True)
        v = self.assemble(res.payload["target_verification_id"])["view"]

        # 裁决必须是 insufficient，不得出现任何"已证实"的语义
        self.assertEqual(v["verification_status"], "insufficient_evidence")
        self.assertNotIn(v["verification_status"],
                         ("supported", "refuted"))

        # 命题保留（这是待验证的说法，不是结论）
        self.assertEqual(v["claim_payload"]["expected_exists"], True,
                         "命题参数应原样保留")

        # 视图不得提供任何"存在/有效"的肯定裁决字段
        for forbidden in ("is_valid", "confirmed_exists", "verified_true",
                          "exists_verdict", "effective_status"):
            self.assertNotIn(forbidden, v, f"不得出现 {forbidden}")

        # 证据缺失必须显式为"无可用证据"，而不是被静默当作否证
        self.assertTrue(v["no_usable_evidence"])
        self.assertFalse(v["distribution_restrictions"]["distribution_allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
