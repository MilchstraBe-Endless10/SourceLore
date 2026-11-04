#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3C 本地受控端到端验收（题面 §13）。"""
import sys, tempfile, shutil, unittest, json, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/facts", "src/collector",
          "src/runtime", "src/evidence_claims", "tests/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import importlib.util as _ilu
_s = _ilu.spec_from_file_location(
    "p3c_fx3", str(Path(__file__).resolve().parent / "fixtures.py"))
FX = _ilu.module_from_spec(_s); _s.loader.exec_module(FX)

import lc_models as L
import revalidation_models as R
import revalidation_queue as RQ
import revalidation_authorization as AUTH
import revalidation_executor as EX
import revalidation_run_store as RS
import collector_adapter as CA

NOW = "2026-11-05T00:00:00+08:00"
B_SHA = "b" * 40
TREE_B = "1" * 40


def _plan(c, *, path=None, exists=None):
    params = c["target_claim_parameters"]
    p = {"candidate_id": c["candidate_id"], "repository_id": FX.REPO,
         "requested_ref": "master", "target_commit_sha": B_SHA,
         "intended_collector_scope": "full_tree_enumeration",
         "intended_fact_rules": ["file_path_observation@v1"],
         "intended_ec_rule_version": "path-exists-verifier/v1",
         "target_claim_parameters": {
             "normalized_path": path or params["normalized_path"],
             "expected_exists": (params["expected_exists"]
                                 if exists is None else exists)},
         "required_operations": sorted(AUTH.ALLOWED_OPERATIONS)}
    p["plan_digest"] = AUTH.plan_digest_of(p)
    return p


def _auth(c, plan, *, expires="2026-11-06T00:00:00+08:00"):
    return AUTH.make_test_authorization(
        candidate_id=c["candidate_id"], repository_id=FX.REPO,
        requested_ref="master", target_commit_sha=B_SHA,
        plan_digest=plan["plan_digest"],
        authorized_scope="full_tree_enumeration",
        issued_at="2026-11-04T00:00:00+08:00", expires_at=expires)


class TestEndToEnd(unittest.TestCase):
    """题面 §13 的四条链路。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3c_e2e_"))
        self.ks = FX.fresh(self.tmp)
        # 源侧：A 上 README 存在、已 supported
        st = FX.make_full_stack(self.ks, target=B_SHA)
        r = RQ.propose_candidate(self.ks, assessment_id=st["assessment_id"])
        self.assertTrue(r.get("ok"), r)
        self.c = RQ.read_candidate(self.ks, candidate_id=r["candidate_id"],
                                   repository_id=FX.REPO)["payload"]
        self.source_claim_id = self.c["source_claim_id"]
        self.source_verification_id = self.c["source_verification_id"]
        self.snap_a = st["snapshot_asset_id"]
        self.fact_a = st["fact_id"]

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fp(self, asset_type):
        rows = self.ks.conn.execute(
            "SELECT asset_id FROM assets WHERE asset_type=? ORDER BY asset_id",
            (asset_type,)).fetchall()
        out = []
        for r in rows:
            g = self.ks.get_asset(r["asset_id"], verify=True)
            out.append(hashlib.sha256(json.dumps(
                g["asset"]["payload"], sort_keys=True,
                ensure_ascii=False).encode()).hexdigest())
        return sorted(out)

    # ── 主链路：B 上路径不存在 → refuted ───────────────────
    def test_chain_b_absent_yields_refuted(self):
        fp_claim_before = self._fp("claim_candidate")
        fp_verif_before = self._fp("claim_verification")

        plan = _plan(self.c)
        auth = _auth(self.c, plan)
        adapter = CA.FakeGhAdapter({B_SHA: TREE_B},
            {TREE_B: {"entries": [
                {"path": "docs", "type": "tree", "sha": "d" * 40,
                 "mode": "040000"}], "truncated": False}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter, now=NOW)

        self.assertTrue(r.ok, (r.error_code, r.detail))
        self.assertEqual(r.execution_status, RS.SUCCESS)
        self.assertEqual(r.verification_status, "refuted")

        # 旧历史：A 的 Claim 与 Verification 未变
        a_claim = self.ks.conn.execute(
            "SELECT asset_id FROM assets WHERE logical_identity=?",
            (self.source_claim_id,)).fetchone()
        g = self.ks.get_asset(a_claim["asset_id"])["asset"]
        self.assertEqual(g["payload"]["commit_sha"], "a" * 40, "旧 Claim 仍绑 A")
        self.assertEqual(g["payload"]["review_status"], "pending_review")

        # 新 Claim 独立身份、绑 B
        new_claim = self.ks.conn.execute(
            "SELECT asset_id FROM assets WHERE logical_identity=?",
            (r.payload["target_claim_id"],)).fetchone()
        self.assertIsNotNone(new_claim, "新 Claim 必须真实存在")
        nc = self.ks.get_asset(new_claim["asset_id"])["asset"]
        self.assertEqual(nc["payload"]["commit_sha"], B_SHA)
        self.assertNotEqual(nc["payload"]["claim_id"], self.source_claim_id)
        self.assertEqual(nc["payload"]["review_status"], "pending_review",
                         "不得自动 approved")

        # 新 Verification 独立、旧的不变
        self.assertNotEqual(r.payload["target_verification_id"],
                            self.source_verification_id)
        # 旧 verification payload 指纹仍在
        for h in fp_verif_before:
            found = any(hh == h for hh in self._fp("claim_verification"))
            self.assertTrue(found, "旧 Verification 必须保留")

    # ── 变体 1：B 上仍存在 → supported ─────────────────────
    def test_chain_b_present_yields_supported(self):
        plan = _plan(self.c)
        auth = _auth(self.c, plan)
        adapter = CA.FakeGhAdapter({B_SHA: TREE_B},
            {TREE_B: {"entries": [
                {"path": "README", "type": "blob", "sha": "9" * 40,
                 "size": 13, "mode": "100644"}], "truncated": False}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter, now=NOW)
        self.assertTrue(r.ok, (r.error_code, r.detail))
        self.assertEqual(r.execution_status, RS.SUCCESS)
        self.assertEqual(r.verification_status, "supported")

    # ── 变体 2：PARTIAL 且未观察到 → insufficient ───────────
    def test_chain_partial_yields_insufficient(self):
        plan = _plan(self.c)
        auth = _auth(self.c, plan)
        adapter = CA.FakeGhAdapter({B_SHA: TREE_B},
            {TREE_B: {"entries": [
                {"path": "docs", "type": "tree", "sha": "d" * 40,
                 "mode": "040000"}], "truncated": True}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter, now=NOW)
        self.assertTrue(r.ok, (r.error_code, r.detail))
        self.assertEqual(r.execution_status, RS.SUCCESS,
                         "证据不足不等于执行失败")
        self.assertEqual(r.verification_status, "insufficient_evidence")

    # ── 变体 3：B 获取失败 → 执行失败，不生成虚假裁决 ─────────
    def test_chain_collect_failure_no_verdict(self):
        plan = _plan(self.c)
        auth = _auth(self.c, plan)
        adapter = CA.FakeGhAdapter({}, {}, commit_error="REPO_NOT_FOUND")
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter, now=NOW)
        self.assertFalse(r.ok)
        self.assertEqual(r.execution_status, RS.FAILED)
        self.assertIsNone(r.verification_status,
                          "执行失败不得产生任何裁决")
        # 没有新增 verification
        n = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(n, 1, "失败时不得写入新 verification")

    # ── 变体 4：B 证据损坏 → 不得产生 supported/refuted ───────
    def test_chain_corrupt_evidence_no_definitive_verdict(self):
        plan = _plan(self.c)
        auth = _auth(self.c, plan)
        # tree 条目 sha 非法 → 抽取时 Git blob 校验会失败/异常
        adapter = CA.FakeGhAdapter({B_SHA: TREE_B},
            {TREE_B: {"entries": [
                {"path": "README", "type": "blob", "sha": "zzz",
                 "size": 13, "mode": "100644"}], "truncated": False}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter, now=NOW)
        # 或者执行失败，或者裁决不是 supported/refuted
        definitive = r.verification_status in ("supported", "refuted")
        self.assertFalse(r.ok and definitive,
                         f"损坏证据不得产生确定性裁决: {r.verification_status}")

    # ── 无授权：不得触发任何外部操作 ─────────────────────────
    def test_no_authorization_no_external_calls(self):
        plan = _plan(self.c)
        adapter = CA.FakeGhAdapter({B_SHA: TREE_B},
            {TREE_B: {"entries": [], "truncated": False}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=None, plan=plan,
            adapter=adapter, now=NOW)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)
        self.assertEqual(adapter.calls, [],
                         "无授权时 Collector 必须零调用")

    # ── 结果结构完整性 ───────────────────────────────────────
    def test_result_payload_complete(self):
        plan = _plan(self.c)
        auth = _auth(self.c, plan)
        adapter = CA.FakeGhAdapter({B_SHA: TREE_B},
            {TREE_B: {"entries": [
                {"path": "README", "type": "blob", "sha": "9" * 40,
                 "size": 13, "mode": "100644"}], "truncated": False}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter, now=NOW)
        self.assertTrue(r.ok)
        need = ("candidate_id", "repository_id", "source_claim_id",
                "source_verification_id", "target_claim_id",
                "target_verification_id", "target_commit_sha",
                "source_snapshot_ref", "fact_refs", "verification_status",
                "freshness_context", "auth_ref", "execution_status",
                "evidence_refs")
        missing = [k for k in need if k not in r.payload]
        self.assertEqual(missing, [], f"结果缺字段 {missing}")
        self.assertEqual(r.payload["target_commit_sha"], B_SHA)
        self.assertFalse(r.payload["freshness_context"]["is_current_ref_target"],
                         "必须标明不是当前 Ref 目标")
        self.assertTrue(r.payload["test_only"],
                        "测试授权必须标记 test_only")

    def test_result_not_marked_approved(self):
        plan = _plan(self.c)
        auth = _auth(self.c, plan)
        adapter = CA.FakeGhAdapter({B_SHA: TREE_B},
            {TREE_B: {"entries": [], "truncated": False}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=self.c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter, now=NOW)
        self.assertTrue(r.ok)
        blob = json.dumps(r.payload, ensure_ascii=False).lower()
        self.assertNotIn("approved", blob,
                         "执行结果不得自动写 approved")
        self.assertNotIn("human_authored\": true", blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
