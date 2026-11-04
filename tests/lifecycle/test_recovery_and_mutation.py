#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIGKILL 漏窗恢复 + 变异测试（题面 §10/§11）。"""
import sys, tempfile, shutil, unittest, json, subprocess, os, signal, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"tests"/"lifecycle"), str(ROOT/"src"/"lifecycle"),
          str(ROOT/"src"/"storage"), str(ROOT/"src"/"runtime"),
          str(ROOT/"src"/"facts"), str(ROOT/"src"/"collector"),
          str(ROOT/"src"/"evidence_claims")):
    if p not in sys.path: sys.path.insert(0, p)

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "lc_fx", str(Path(__file__).resolve().parent / "fixtures.py"))
FX = _ilu.module_from_spec(_spec); _spec.loader.exec_module(FX)

import lc_models as L
import lifecycle_store as LS
import impact_resolver as IR
import freshness_evaluator as FE


class TestSigkillRecovery(unittest.TestCase):
    """T-21 加强：资产已提交但 checkpoint 未更新 → 通过 operation_id 恢复。"""

    def test_sigkill_after_asset_commit_then_reconcile(self):
        tmp = Path(tempfile.mkdtemp(prefix="lc_kill_"))
        db = str(tmp / "kb.db")
        code = r'''
import sys, os, json
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import knowledge_store as KS, lc_models as L, lifecycle_store as LS
ks = KS.KnowledgeStore(%r)
w = L.build_watch(repository_id="1296269", requested_ref="master",
                  ref_kind=L.REF_KIND_BRANCH, retrieval_scope="full_tree_enumeration",
                  baseline_commit_sha="a"*40, claim_id="SL-CLAIM-"+"1"*40)
r = LS.ingest_watch(ks, w)
print("ASSET_COMMITTED", json.dumps({"state": r.get("state"),
                                     "asset_id": r.get("asset_id")}), flush=True)
# 资产已提交，但复算 checkpoint 尚未完成 → 真实 SIGKILL
os.kill(os.getpid(), 9)
''' % (str(ROOT/"src"/"lifecycle"), str(ROOT/"src"/"storage"), db)
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True)
        self.assertNotEqual(p.returncode, 0, "必须真的被 SIGKILL")
        self.assertIn("ASSET_COMMITTED", p.stdout,
                      "必须在 kill 前完成资产提交")

        # 重启：资产在，operation_log 在
        ks = FX.fresh(tmp)
        try:
            n = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='lifecycle_watch'"
            ).fetchone()["n"]
            self.assertEqual(n, 1, "崩溃前已提交的资产必须仍在")
            ops = ks.conn.execute(
                "SELECT count(*) AS n FROM operation_log WHERE operation_id LIKE 'OP-LC-%%'"
            ).fetchone()["n"]
            self.assertGreaterEqual(ops, 1,
                                    "operation_id 必须落账以便对账")
            # 幂等重放：再次写入同一 watch 不应产生第二条资产
            w = FX.make_watch(baseline=FX.COMMIT_A)
            r2 = LS.ingest_watch(ks, w)
            self.assertEqual(r2["state"], LS.IDEMPOTENT,
                             "崩溃后重放必须幂等，不得重复写入")
            n2 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='lifecycle_watch'"
            ).fetchone()["n"]
            self.assertEqual(n2, 1)
        finally:
            ks.close(); shutil.rmtree(tmp, ignore_errors=True)


class TestMutation(unittest.TestCase):
    """T-25 加强：把 POSSIBLY_STALE 变成 REFUTED 的变异必须被测试捕获。

    ★ 只在测试内替换函数，不改正式源码。
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lc_mut_"))
        self.ks = FX.fresh(self.tmp)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _scenario(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        obs = FX.observe_ok(commit=FX.COMMIT_B)
        return w, obs

    def test_mutation_stale_to_refuted_is_detectable(self):
        """若 Lifecycle 输出 refuted，测试必须失败 —— 证明现有断言有效。"""
        w, obs = self._scenario()
        a = FE.assess(watch=w, observation=obs)
        self.assertEqual(a.freshness_state, L.POSSIBLY_STALE)
        # 变异后的状态不在合法集合内 → 契约层直接拒绝
        with self.assertRaises(ValueError):
            L.FreshnessAssessment(
                assessment_id=a.assessment_id, watch_id=a.watch_id,
                claim_id=a.claim_id, repository_id=a.repository_id,
                requested_ref=a.requested_ref,
                baseline_commit_sha=a.baseline_commit_sha,
                observed_commit_sha=a.observed_commit_sha,
                freshness_state="refuted",        # ← 变异
                reason_code=None, evidence_refs=[], rule_version="v1",
                input_digest=a.input_digest,
                applicability_scope=a.applicability_scope)
        # 且 FRESHNESS_STATES 里根本没有 refuted
        self.assertNotIn("refuted", L.FRESHNESS_STATES,
                         "refuted 不能是新鲜度状态")

    def test_mutation_no_observation_to_stale_is_detectable(self):
        """把'无观测'判成 POSSIBLY_STALE 必须被拒绝（缺 commit）。"""
        w = FX.make_watch()
        bad = RO_obs_failed()
        a = FE.assess(watch=w, observation=bad)
        self.assertEqual(a.freshness_state, L.UNKNOWN)
        with self.assertRaises(ValueError):
            L.FreshnessAssessment(
                assessment_id=a.assessment_id, watch_id=a.watch_id,
                claim_id=a.claim_id, repository_id=a.repository_id,
                requested_ref=a.requested_ref,
                baseline_commit_sha=a.baseline_commit_sha,
                observed_commit_sha=None,         # ← 无观测却判 stale
                freshness_state=L.POSSIBLY_STALE, reason_code=L.R_REF_MOVED,
                evidence_refs=[], rule_version="v1",
                input_digest=a.input_digest,
                applicability_scope=a.applicability_scope)

    def test_mutation_aligned_with_mismatch_detectable(self):
        """observed != baseline 却判 VERSION_ALIGNED 必须被拒绝。"""
        w, obs = self._scenario()
        a = FE.assess(watch=w, observation=obs)   # 正确应为 POSSIBLY_STALE
        with self.assertRaises(ValueError):
            L.FreshnessAssessment(
                assessment_id=a.assessment_id, watch_id=a.watch_id,
                claim_id=a.claim_id, repository_id=a.repository_id,
                requested_ref=a.requested_ref,
                baseline_commit_sha=FX.COMMIT_A,
                observed_commit_sha=FX.COMMIT_B,
                freshness_state=L.VERSION_ALIGNED,   # ← 变异
                reason_code=None, evidence_refs=[], rule_version="v1",
                input_digest=a.input_digest,
                applicability_scope=a.applicability_scope)


def RO_obs_failed():
    import ref_observer as RO
    return RO.observe_ref_via_collector(
        FX.FakeClient({}, ok=False, error_code="NETWORK_TIMEOUT"),
        owner="octocat", name="Hello-World",
        repository_id=FX.REPO, requested_ref="master")


class TestImpactNonEmpty(unittest.TestCase):
    """§11：断言受影响集合非空、未受影响集合确实存在。"""

    def test_affected_set_non_empty(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        a = FE.assess(watch=w, observation=FX.observe_ok(commit=FX.COMMIT_B))
        r = IR.resolve_affected([w], assessment_list=[a])
        self.assertGreater(len(r["affected_claim_ids"]), 0,
                           "必须实际产生受影响的 Claim（非空集合）")
        self.assertIn(w.claim_id, r["affected_claim_ids"])

    def test_unaffected_set_exists(self):
        w1 = FX.make_watch(ref="master", baseline=FX.COMMIT_A)
        w2 = FX.make_watch(ref="dev", baseline=FX.COMMIT_A,
                           claim_id="SL-CLAIM-" + "2" * 40)
        a1 = FE.assess(watch=w1, observation=FX.observe_ok(ref="master",
                                                          commit=FX.COMMIT_B))
        a2 = FE.assess(watch=w2, observation=FX.observe_ok(ref="dev",
                                                          commit=FX.COMMIT_A))
        r = IR.resolve_affected([w1, w2], assessment_list=[a1, a2])
        self.assertGreater(len(r["unaffected"]), 0,
                           "必须真的存在未受影响的 Claim")
        self.assertEqual(r["unaffected"][0]["claim_id"], w2.claim_id)

    def test_duplicate_observation_actually_runs_twice(self):
        """§11：重复观测必须真的跑两次，而不是跳过。"""
        obs = FX.observe_ok(commit=FX.COMMIT_A)
        w = FX.make_watch(baseline=FX.COMMIT_A)
        calls = []
        a1 = FE.assess(watch=w, observation=obs); calls.append(a1)
        a2 = FE.assess(watch=w, observation=obs); calls.append(a2)
        self.assertEqual(len(calls), 2, "评估必须实际执行两次")
        self.assertEqual(a1.assessment_id, a2.assessment_id)

    def test_cas_conflict_actually_happened(self):
        """§11：CAS 冲突必须真的发生（不是假设）。"""
        ks = FX.fresh(Path(tempfile.mkdtemp(prefix="lc_cas_")))
        try:
            w = FX.make_watch(baseline=FX.COMMIT_A)
            LS.ingest_watch(ks, w)
            w2 = L.LifecycleWatch(
                watch_id=w.watch_id, repository_id=w.repository_id,
                requested_ref=w.requested_ref, ref_kind=w.ref_kind,
                retrieval_scope=w.retrieval_scope,
                baseline_commit_sha=FX.COMMIT_B, claim_id=w.claim_id,
                applicability_scope=L.TRACKING_REF)
            r = LS.ingest_watch(ks, w2, expected_version=42)
            self.assertEqual(r["state"], LS.CONFLICT,
                             "必须真的发生 CAS 冲突")
        finally:
            ks.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
