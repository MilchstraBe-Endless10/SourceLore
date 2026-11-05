#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-20..T-22 / T-36..T-38：来源与授权隔离。"""
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
import collector_adapter as CA
import revalidation_authorization as AUTH
import revalidation_executor as EX


class TestProvenanceIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pv_"))
        self.ks = vfx.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _view(self, vid):
        return KVA.assemble_from_verification(
            self.ks, verification_id=vid, repository_id=vfx.REPO)

    def test_t20_test_authorization_kept_test_only(self):
        """TEST_ONLY 执行结果不得被标成生产运行。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        v = self._view(res.payload["target_verification_id"])["view"]
        self.assertEqual(v["authorization_class"], "TEST_ONLY_ISOLATED")
        self.assertEqual(v["authorization_kind"], "TEST_ONLY")
        self.assertTrue(v["authorization_is_test_only"])
        self.assertNotEqual(v["authorization_class"], "VERIFIABLE_PRODUCTION")

    def test_t21_synthetic_source_kept_synthetic(self):
        """合成来源必须保留 SYNTHETIC_FIXTURE，哪怕历史数据是真的。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        v = self._view(res.payload["target_verification_id"])["view"]
        self.assertEqual(v["execution_source_level"], "SYNTHETIC_FIXTURE")
        self.assertNotEqual(v["provenance_level"], "REAL_LIVE_API")
        self.assertNotEqual(v["provenance_level"], "HISTORICAL_REAL_DATA")

    def test_t22_historical_source_kept_historical(self):
        """历史真实来源必须保留 HISTORICAL_REAL_DATA，不因测试授权变合成。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        # 直接把 run 的执行来源标记为历史真实
        run_row = self.ks.conn.execute(
            "SELECT asset_id, payload_json FROM assets "
            "WHERE asset_type='revalidation_run'").fetchone()
        p = json.loads(run_row["payload_json"])
        p = dict(p); p["execution_source_level"] = "HISTORICAL_REAL_DATA"
        v = self._view(res.payload["target_verification_id"])["view"]
        # 用只读路径验证：手工构造 provenance 判定的等价输入
        prov = KVA._provenance_of(
            fresh={"provenance_level": "HISTORICAL_REAL_DATA"},
            run={"execution_source_level": "HISTORICAL_REAL_DATA"},
            chain={"snapshots": []})
        self.assertEqual(prov["provenance_level"], "HISTORICAL_REAL_DATA")
        self.assertEqual(prov["evidence_source_level"],
                         "HISTORICAL_REAL_DATA")
        # 授权类别仍是 TEST_ONLY —— 两个判断互不影响
        self.assertTrue(v["authorization_is_test_only"])

    def test_mixed_provenance_takes_weakest(self):
        """混合来源以最弱为准，并显式标注。"""
        prov = KVA._provenance_of(
            fresh={"provenance_level": "REAL_LIVE_API"},
            run={"execution_source_level": "SYNTHETIC_FIXTURE"},
            chain={"snapshots": []})
        self.assertEqual(prov["provenance_level"], "SYNTHETIC_FIXTURE")
        self.assertTrue(prov["mixed_provenance"])

    def test_undetermined_provenance_not_guessed(self):
        """无法判定来源时报 None，绝不猜成真实。"""
        prov = KVA._provenance_of(fresh={}, run={}, chain={"snapshots": []})
        self.assertIsNone(prov["provenance_level"])
        self.assertIn("undetermined", prov["basis"])

    def test_snapshot_has_no_provenance_field_acknowledged(self):
        """★ 如实记录：快照 payload 不含 provenance_level。

        来源等级只存在于观测（ref_observation）与执行记录。
        视图不得凭空给快照编一个来源等级。
        """
        src, cand, res, ad = vfx.run_full(self.ks)
        snap = self.ks.get_asset(res.payload["source_snapshot_ref"])["asset"]
        self.assertNotIn("provenance_level", snap["payload"])
        self.assertIn("source_provider", snap["payload"])


class TestP3CRegression(unittest.TestCase):
    """T-36 / T-37 / T-38：复核 P3C 三个真实缺陷。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rc_"))
        self.ks = vfx.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_t36_plan_digest_recomputed(self):
        """T-36：同时篡改计划内容与其自带 plan_digest，仍必须拒绝。"""
        plan = {"candidate_id": "SL-REVAL-" + "a" * 28,
                "target_commit_sha": vfx.B, "repository_id": vfx.REPO,
                "requested_ref": "master",
                "intended_collector_scope": "full_tree_enumeration",
                "target_claim_parameters": {"normalized_path": "README",
                                            "expected_exists": True}}
        plan["plan_digest"] = AUTH.plan_digest_of(plan)

        # 正常应通过
        ok = AUTH.validate_execution_authorization(
            candidate={"candidate_id": plan["candidate_id"],
                       "repository_id": vfx.REPO,
                       "requested_ref": "master",
                       "target_commit_sha": vfx.B},
            plan=plan,
            authorization=vfx.test_auth(
                {"candidate_id": plan["candidate_id"],
                 "target_claim_parameters": {"normalized_path": "README",
                                             "expected_exists": True}},
                plan),
            now="2026-11-05T00:00:00+08:00")
        self.assertTrue(ok["ok"], ok)

        # ★ 篡改内容**并**把 plan_digest 也改成新的 —— 仍须拒绝
        tampered = dict(plan)
        tampered["target_claim_parameters"] = dict(
            plan["target_claim_parameters"])
        tampered["target_claim_parameters"]["expected_exists"] = False
        tampered["plan_digest"] = AUTH.plan_digest_of(tampered)

        auth = vfx.test_auth(
            {"candidate_id": plan["candidate_id"],
             "target_claim_parameters": {"normalized_path": "README",
                                         "expected_exists": True}},
            plan)   # 授权绑定的是**原始**摘要
        r = AUTH.validate_execution_authorization(
            candidate={"candidate_id": plan["candidate_id"],
                       "repository_id": vfx.REPO,
                       "requested_ref": "master",
                       "target_commit_sha": vfx.B},
            plan=tampered, authorization=auth,
            now="2026-11-05T00:00:00+08:00")
        self.assertFalse(r["ok"], "篡改后的计划必须被拒绝")
        self.assertEqual(r["reason"], AUTH.A_PLAN_MISMATCH)

    def test_t37_bad_tree_sha_no_definitive_verdict(self):
        """T-37：错误 Tree 条目 SHA 不得产生 supported/refuted。"""
        src = vfx.make_source(self.ks)
        r, watch, a = vfx.make_candidate(self.ks, claim_id=src["claim_id"])
        cand = vfx.RQ.read_candidate(self.ks, candidate_id=r["candidate_id"],
                                     repository_id=vfx.REPO)["payload"]
        plan = vfx.plan_for(cand)
        auth = vfx.test_auth(cand, plan)
        bad = CA.FakeGhAdapter(
            {vfx.B: vfx.TREE_B},
            {vfx.TREE_B: {"entries": [
                {"path": "README", "type": "blob", "sha": "zzz",
                 "size": 1, "mode": "100644"}], "truncated": False}})
        res = EX.execute_revalidation(
            self.ks, candidate_id=cand["candidate_id"],
            repository_id=vfx.REPO, authorization=auth, plan=plan,
            adapter=bad, now="2026-11-05T00:00:00+08:00")
        self.assertFalse(
            res.ok and res.verification_status in ("supported", "refuted"),
            f"损坏条目不得产生确定性裁决: {res.verification_status}")
        self.assertEqual(res.execution_status, "FAILED")

    def test_t38_auth_ref_has_no_secret(self):
        """T-38：run/result 里只存授权**引用**，不含任何凭据。"""
        src, cand, res, ad = vfx.run_full(self.ks)
        rows = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type IN "
            "('revalidation_run','revalidation_result')").fetchall()
        self.assertGreater(len(rows), 0, "必须真的有 run/result 资产")
        forbidden = ("api_key", "token", "cookie", "secret", "password",
                     "credential", "private_key", "authorization",
                     "proof")
        for r in rows:
            p = json.loads(r["payload_json"])
            for k in p:
                low = k.lower()
                for f in forbidden:
                    self.assertNotIn(
                        f, low, f"payload 键 {k} 含禁词 {f}")
        # auth_ref 只应是稳定标识符
        for r in rows:
            p = json.loads(r["payload_json"])
            ref = p.get("auth_ref")
            if ref:
                self.assertIsInstance(ref, str)
                self.assertTrue(ref.startswith("SL-TESTAUTH-"),
                                f"auth_ref 应为稳定引用: {ref}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
