#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3C 执行器测试（T-9..T-31 主体）。"""
import sys, tempfile, shutil, unittest, json, copy, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/facts", "src/collector",
          "src/runtime", "src/evidence_claims", "tests/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import importlib.util as _ilu
_s = _ilu.spec_from_file_location(
    "p3c_fx", str(Path(__file__).resolve().parent / "fixtures.py"))
FX = _ilu.module_from_spec(_s); _s.loader.exec_module(FX)

import lc_models as L
import revalidation_models as R
import revalidation_queue as RQ
import revalidation_dispatch_gate as DG
import revalidation_authorization as AUTH
import revalidation_executor as EX
import revalidation_run_store as RS
import collector_adapter as CA
import lifecycle_store as LS
import freshness_evaluator as FE

NOW = "2026-11-05T00:00:00+08:00"
A_SHA = "a" * 40
B_SHA = "b" * 40
C_SHA = "c" * 40
TREE_B = "1" * 40


def _plan(cand_id: str, commit: str, *, path="README", exists=True,
          scope="full_tree_enumeration"):
    p = {
        "gate": "PLAN_READY", "candidate_id": cand_id,
        "repository_id": FX.REPO, "requested_ref": "master",
        "target_commit_sha": commit,
        "intended_collector_scope": scope,
        "intended_fact_rules": ["file_path_observation@v1"],
        "intended_ec_rule_version": "path-exists-verifier/v1",
        "target_claim_parameters": {"normalized_path": path,
                                    "expected_exists": exists},
        "required_operations": sorted(AUTH.ALLOWED_OPERATIONS),
    }
    p["plan_digest"] = AUTH.plan_digest_of(p)
    return p


def _auth(cand_id: str, commit: str, plan: dict, **over):
    a = AUTH.make_test_authorization(
        candidate_id=cand_id, repository_id=FX.REPO, requested_ref="master",
        target_commit_sha=commit, plan_digest=plan["plan_digest"],
        authorized_scope=plan["intended_collector_scope"],
        issued_at="2026-11-04T00:00:00+08:00",
        expires_at="2026-11-06T00:00:00+08:00")
    a.update(over)
    return a


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3c_"))
        self.ks = FX.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def setup_running(self, *, path="README"):
        """建完整栈 + 候选，返回 (stack, candidate, plan, auth)。"""
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA, path=path)
        auth = _auth(c["candidate_id"], B_SHA, plan)
        return st, c, plan, auth

    def _cand_id(self):
        q = RQ.read_queue(self.ks, watch_id=self._watch_id(),
                          repository_id=FX.REPO)
        return q["active_candidate_id"]

    def make_candidate(self, *, target=B_SHA, provenance_real=True):
        """建栈并**真正调用 propose_candidate**，返回 (stack, candidate payload)。"""
        st = FX.make_full_stack(self.ks, target=target,
                                provenance_real=provenance_real)
        r = RQ.propose_candidate(self.ks, assessment_id=st["assessment_id"])
        assert r.get("ok"), r
        cid = r["candidate_id"]
        c = RQ.read_candidate(self.ks, candidate_id=cid,
                              repository_id=FX.REPO)["payload"]
        return st, c

    def _watch_id(self):
        row = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='lifecycle_watch'"
        ).fetchone()
        return json.loads(row["payload_json"])["watch_id"]

    def adapter(self, *, entries=None, truncated=False, **kw):
        return CA.FakeGhAdapter(
            {B_SHA: TREE_B},
            {TREE_B: {"entries": entries if entries is not None else [
                {"path": "docs", "type": "tree", "sha": "d" * 40,
                 "mode": "040000"}],
                "truncated": truncated}},
            **kw)

    def run_exec(self, c, plan, auth, adapter=None, **kw):
        return EX.execute_revalidation(
            self.ks, candidate_id=c["candidate_id"],
            repository_id=FX.REPO, authorization=auth, plan=plan,
            adapter=adapter or self.adapter(), now=NOW, **kw)


class TestPreflightAndAuth(Base):
    """T-1/2/3/4/5/6/9/10。"""

    def _full(self, **over):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        auth = _auth(c["candidate_id"], B_SHA, plan, **over)
        return c, plan, auth

    def test_t1_unauthorized_rejected(self):
        c, plan, _ = self._full()
        r = self.run_exec(c, plan, None)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)
        self.assertEqual(r.stage, "AUTHORIZATION_CHECK")

    def test_t2_expired_rejected(self):
        c, plan, _ = self._full(expires_at="2026-11-04T00:00:00+08:00")
        r = self.run_exec(c, plan, _)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)

    def test_t3_wrong_candidate_rejected(self):
        c, plan, _ = self._full(candidate_id="SL-REVAL-" + "9" * 32)
        r = self.run_exec(c, plan, _)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)

    def test_t4_wrong_commit_rejected(self):
        c, plan, _ = self._full(target_commit_sha=C_SHA)
        r = self.run_exec(c, plan, _)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)

    def test_t5_wrong_repo_rejected(self):
        c, plan, _ = self._full(repository_id="999999")
        r = self.run_exec(c, plan, _)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)

    def test_t6_wrong_scope_rejected(self):
        c, plan, _ = self._full(authorized_scope="path_prefix:src/")
        r = self.run_exec(c, plan, _)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)

    def test_t9_non_proposed_rejected_in_production(self):
        """★ BLOCKED 候选在**正式模式**下必须拒绝（不得调用 Collector）。

        注意：隔离测试模式（TEST_ONLY 授权）**允许** BLOCKED —— 这是 §13
        "测试授权仅适用于隔离测试"的落地。正式模式的拒绝见本用例。
        """
        st, c = self.make_candidate(target=B_SHA, provenance_real=False)
        self.assertEqual(c["status"], R.BLOCKED)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        adapter = self.adapter()
        r = self.run_exec(c, plan, a, adapter=adapter, require_production=True)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_PREFLIGHT_NOT_PROPOSED)
        self.assertEqual(adapter.calls, [], "正式模式下不得调用 Collector")

    def test_t9b_synthetic_source_blocked_in_production(self):
        """非 REAL_LIVE_API 来源在正式模式下一律拒绝。"""
        st, c = self.make_candidate(target=B_SHA, provenance_real=False)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        # 即便把状态伪装成 PROPOSED，正式模式仍拒绝来源
        a_prod = dict(a)
        a_prod["authorization_kind"] = AUTH.KIND_HUMAN_OPERATOR
        a_prod["authorization_proof"] = "not-a-real-proof"
        a_prod.pop("test_only", None)
        adapter = self.adapter()
        r = EX.execute_revalidation(
            self.ks, candidate_id=c["candidate_id"], repository_id=FX.REPO,
            authorization=a_prod, plan=plan, adapter=adapter, now=NOW,
            require_production=True)
        self.assertFalse(r.ok)
        self.assertIn(r.error_code, (EX.E_AUTH_REJECTED,
                                     EX.E_PREFLIGHT_NOT_PROPOSED))
        self.assertEqual(adapter.calls, [])

    def test_t10_superseded_not_started(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        # 标记 SUPERSEDED
        RQ.mark_superseded(self.ks, candidate_id=c["candidate_id"],
                           repository_id=FX.REPO, superseded_by="SL-REVAL-" + "9" * 32)
        adapter = self.adapter()
        r = self.run_exec(c, plan, a, adapter=adapter)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_PREFLIGHT_SUPERSEDED)
        self.assertEqual(adapter.calls, [], "SUPERSEDED 不得调用 Collector")

    def test_not_active_rejected(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        # 把活动槽位改成别的
        q = RQ.read_queue(self.ks, watch_id=c["watch_id"], repository_id=FX.REPO)
        bad = R.WatchQueueState(
            queue_id=q["queue_id"], watch_id=c["watch_id"],
            repository_id=FX.REPO, active_candidate_id="SL-REVAL-" + "8" * 32,
            active_target_commit_sha=C_SHA,
            history_candidate_ids=q["history_candidate_ids"])
        RQ._write_queue(self.ks, watch=None, queue=bad,
                        expected_version=q["asset_version"])
        adapter = self.adapter()
        r = self.run_exec(c, plan, a, adapter=adapter)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_PREFLIGHT_NOT_ACTIVE)
        self.assertEqual(adapter.calls, [])


class TestFixedTarget(Base):
    """T-12：固定目标 B 不被漂移；T-13：返回错 Commit 被拒；T-14：Tree SHA 不冒充。"""

    def test_t12_target_is_commit_b_not_ref(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        adapter = self.adapter()
        r = self.run_exec(c, plan, a, adapter=adapter)
        self.assertTrue(r.ok, (r.error_code, r.detail))
        # ★ 只按 sha 取，不做 Ref 解析
        self.assertEqual(adapter.calls[0], ("fetch_commit", B_SHA))
        self.assertEqual([k for k, _ in adapter.calls],
                         ["fetch_commit", "fetch_tree"],
                         "不得有 Ref 解析调用")
        # 源快照必须是 B
        snap = self.ks.get_asset(r.payload["source_snapshot_ref"])["asset"]
        self.assertEqual(snap["payload"]["commit_sha"], B_SHA)

    def test_t13_wrong_commit_returned_rejected(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        adapter = self.adapter(wrong_commit_for=B_SHA)
        r = self.run_exec(c, plan, a, adapter=adapter)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_COLLECT_COMMIT_MISMATCH)

    def test_t14_tree_sha_not_used_as_commit(self):
        """root_tree_sha 必须来自 commit.tree.sha，且 tree 请求用它。"""
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        adapter = self.adapter()
        r = self.run_exec(c, plan, a, adapter=adapter)
        self.assertTrue(r.ok)
        self.assertEqual(adapter.calls[1], ("fetch_tree", TREE_B))
        snap = self.ks.get_asset(r.payload["source_snapshot_ref"])["asset"]
        self.assertEqual(snap["payload"]["root_tree_sha"], TREE_B)
        self.assertNotEqual(snap["payload"]["commit_sha"], TREE_B)


class TestClaimIdentity(Base):
    """T-15..T-20。"""

    def _ok_run(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        r = self.run_exec(c, plan, a)
        return st, c, plan, a, r

    def test_t17_target_claim_identity_matches_expected(self):
        st, c, plan, a, r = self._ok_run()
        self.assertTrue(r.ok, (r.error_code, r.detail))
        self.assertEqual(r.payload["target_claim_id"],
                         c["expected_target_claim_identity"],
                         "新 Claim 身份必须等于 expected_target_claim_identity")

    def test_t19_new_and_old_claim_ids_differ(self):
        st, c, plan, a, r = self._ok_run()
        self.assertNotEqual(r.payload["target_claim_id"], c["source_claim_id"],
                            "新 Claim 必须有独立身份")

    def test_t18_identity_mismatch_stops(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        # 先记下当前 Claim 数（源 Claim = 1）
        n_before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_candidate'"
        ).fetchone()["n"]
        self.assertEqual(n_before, 1)

        # ★ 篡改 candidate 的 expected 身份，验证执行器拒绝
        bad_c = dict(c)
        bad_c["expected_target_claim_identity"] = "SL-CLAIM-" + "0" * 40
        r2 = EX._create_target_claim(self.ks, candidate=bad_c,
                                     repository_id=FX.REPO)
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["error_code"], EX.E_TARGET_CLAIM_IDENTITY_MISMATCH)

        # ★ 完整执行路径：用篡改后的候选跑 execute（应停在该阶段）
        orig = RQ.read_candidate
        RQ.read_candidate = lambda store, **kw: {"ok": True, "payload": bad_c,
                                                 "asset_version": 1}
        try:
            r3 = EX.execute_revalidation(
                self.ks, candidate_id=c["candidate_id"], repository_id=FX.REPO,
                authorization=a, plan=plan, adapter=self.adapter(), now=NOW)
        finally:
            RQ.read_candidate = orig
        self.assertFalse(r3.ok)
        self.assertEqual(r3.error_code, EX.E_TARGET_CLAIM_IDENTITY_MISMATCH)
        self.assertEqual(r3.stage, "TARGET_CLAIM_CREATE")

        n_after = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_candidate'"
        ).fetchone()["n"]
        self.assertEqual(n_after, n_before,
                         "身份不一致时不得写出新 Claim")

    def test_t15_t16_facts_only_from_b_snapshot(self):
        st, c, plan, a, r = self._ok_run()
        # fact_refs 里是 fact_id（logical_identity），不是 asset_id
        row = self.ks.conn.execute(
            "SELECT asset_id FROM assets WHERE logical_identity=?",
            (r.payload["fact_refs"][0],)).fetchone()
        self.assertIsNotNone(row, "Fact 必须真实存在")
        fact = self.ks.get_asset(row["asset_id"])["asset"]
        self.assertEqual(fact["payload"]["commit_sha"], B_SHA, "Fact 必须属于 B")
        self.assertEqual(
            fact["payload"]["snapshot_asset_id"],
            r.payload["source_snapshot_ref"], "Fact 的来源必须是 B 的快照")
        self.assertNotEqual(fact["payload"]["commit_sha"], A_SHA,
                            "旧 Fact 不得冒充新 Fact")

    def test_t20_verifications_independent(self):
        st, c, plan, a, r = self._ok_run()
        self.assertNotEqual(r.payload["target_verification_id"],
                            c["source_verification_id"],
                            "新旧 Verification 身份独立")
        # 旧 Verification 仍在
        row = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(row, 2, "旧 Verification 必须保留")


class TestVerdicts(Base):
    """T-21..T-26。"""

    def _run_with(self, *, entries, truncated=False):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        r = self.run_exec(c, plan, a,
                          adapter=self.adapter(entries=entries,
                                               truncated=truncated))
        return c, r

    def test_t21_supported_path(self):
        c, r = self._run_with(entries=[
            {"path": "README", "type": "blob", "sha": "9" * 40,
             "size": 13, "mode": "100644"}])
        self.assertTrue(r.ok)
        self.assertEqual(r.execution_status, RS.SUCCESS)
        self.assertEqual(r.verification_status, "supported")

    def test_t22_refuted_path(self):
        c, r = self._run_with(entries=[
            {"path": "docs", "type": "tree", "sha": "d" * 40,
             "mode": "040000"}])
        self.assertTrue(r.ok)
        self.assertEqual(r.execution_status, RS.SUCCESS)
        self.assertEqual(r.verification_status, "refuted")

    def test_t23_insufficient_path(self):
        """PARTIAL 且未观察到路径 → insufficient_evidence（执行仍 SUCCESS）。"""
        c, r = self._run_with(entries=[
            {"path": "docs", "type": "tree", "sha": "d" * 40,
             "mode": "040000"}], truncated=True)
        self.assertTrue(r.ok)
        self.assertEqual(r.execution_status, RS.SUCCESS,
                         "证据不足不等于执行失败")
        self.assertEqual(r.verification_status, "insufficient_evidence")

    def test_t24_partial_no_fake_absent(self):
        c, r = self._run_with(entries=[
            {"path": "docs", "type": "tree", "sha": "d" * 40,
             "mode": "040000"}], truncated=True)
        self.assertEqual(r.verification_status, "insufficient_evidence",
                         "PARTIAL 不得产生虚假 ABSENT")
        self.assertNotEqual(r.verification_status, "refuted")

    def test_t26_execution_and_verdict_separated(self):
        c, r = self._run_with(entries=[], truncated=True)
        self.assertEqual(r.execution_status, RS.SUCCESS)
        self.assertEqual(r.verification_status, "insufficient_evidence")
        # 两个字段真的分开
        payload = r.payload
        self.assertIn("execution_status", payload)
        self.assertIn("verification_status", payload)
        self.assertIsNot(payload["execution_status"],
                         payload["verification_status"])

    def test_t25_conflict_not_forced(self):
        """同范围证据冲突 → 不硬裁（由 EC 负责；此处验证不会变 supported）。"""
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        # 注入一条同 Commit 同路径的 synthetic ABSENT fact（模拟来源损坏）
        snap_id = None
        adapter = self.adapter(entries=[
            {"path": "README", "type": "blob", "sha": "9" * 40,
             "size": 13, "mode": "100644"}])
        r = self.run_exec(c, plan, a, adapter=adapter)
        self.assertTrue(r.ok)
        self.assertEqual(r.verification_status, "supported")
        # 再注入矛盾 fact 后重跑同命题 → 不应再 supported
        import importlib.util as _i
        _sp = _i.spec_from_file_location(
            "ec_fx_inject", str(ROOT/"tests"/"evidence_claims"/"fixtures.py"))
        EFX = _i.module_from_spec(_sp); _sp.loader.exec_module(EFX)
        injected = EFX.inject_synthetic_absent_fact(
            self.ks, r.payload["source_snapshot_ref"],
            path="README", commit=B_SHA)
        # 直接对同一 target claim 再次验证（含两条矛盾证据）
        import ec_models as EM
        import verifier as V
        tc = EM.build_path_claim(
            repository_id=int(FX.REPO), commit_sha=B_SHA,
            target_path="README", expected_exists=True)
        v2 = V.verify_path_claim(self.ks, tc,
                                 [r.payload["fact_refs"][0],
                                  injected["fact_id"]])
        self.assertNotEqual(v2.status, "supported",
                            "冲突不得被强行裁成 supported")
        self.assertEqual(v2.reason_code, "CONFLICTING_EVIDENCE")


class TestRunRecords(Base):
    """T-27/28/29/30/31 + T-37/38。"""

    def _setup(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        return st, c, plan, a

    def test_t27_review_status_not_transferred(self):
        st, c, plan, a = self._setup()
        r = self.run_exec(c, plan, a)
        self.assertTrue(r.ok)
        import ec_models as EM
        rows = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='claim_candidate'"
        ).fetchall()
        for row in rows:
            p = json.loads(row["payload_json"])
            self.assertEqual(p.get("review_status"), "pending_review")
            self.assertFalse(p.get("human_authored"))

    def test_t30_repeat_run_idempotent(self):
        st, c, plan, a = self._setup()
        r1 = self.run_exec(c, plan, a)
        self.assertTrue(r1.ok)
        n_before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        adapter2 = self.adapter()          # 真的再跑一次
        r2 = self.run_exec(c, plan, a, adapter=adapter2)
        self.assertTrue(r2.ok)
        self.assertGreater(len(adapter2.calls), 0, "重复运行必须真的调用")
        n_after = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(n_before, n_after,
                         "重复运行不得产生额外的 verification")
        self.assertEqual(r1.payload["target_verification_id"],
                         r2.payload["target_verification_id"])

    def test_t31_run_id_deterministic(self):
        st, c, plan, a = self._setup()
        rid1 = RS.make_run_id(candidate_id=c["candidate_id"],
                              plan_digest=plan["plan_digest"],
                              authorization_id=a["authorization_id"])
        rid2 = RS.make_run_id(candidate_id=c["candidate_id"],
                              plan_digest=plan["plan_digest"],
                              authorization_id=a["authorization_id"])
        self.assertEqual(rid1, rid2)
        self.assertTrue(rid1.startswith("SL-RUN-"))

    def test_t37_wrong_expected_version_conflict(self):
        """T-37：错误 expected_version 必须返回 CONFLICT。"""
        st, c, plan, a = self._setup()
        cr = RS.create_run(self.ks, candidate=c,
                           plan_digest=plan["plan_digest"],
                           authorization_id=a["authorization_id"],
                           authorization_ref=a["authorization_id"],
                           created_at=NOW)
        self.assertTrue(cr["ok"], cr)
        rid = cr["run_id"]

        def _mut(p):
            p["current_stage"] = "SNAPSHOT_COLLECT"

        # ★ 直接用错误 expected_version 走底层写入
        cur = RS.read_run(self.ks, run_id=rid, repository_id=FX.REPO)
        p = cur["payload"]; _mut(p)
        bad = RS._write(self.ks, asset_type=RS.RUN_ASSET, li=rid,
                        repo_id=FX.REPO, payload=p,
                        op_id="OP-RUN-WRONGVERSION", expected_version=99,
                        drop=("created_at", "updated_at"))
        self.assertFalse(bad["ok"], f"错误 CAS 不得成功: {bad}")
        self.assertEqual(bad["state"], RS.CONFLICT)

        # 正确版本可以推进
        good = RS.update_run(self.ks, run_id=rid, repository_id=FX.REPO,
                             mutate=_mut, updated_at=NOW)
        self.assertTrue(good["ok"], good)
        self.assertEqual(RS.read_run(self.ks, run_id=rid,
                                     repository_id=FX.REPO)["asset_version"], 2)

    def test_t38_failure_does_not_touch_old(self):
        st, c, plan, a = self._setup()
        def fp(asset_type):
            rows = self.ks.conn.execute(
                "SELECT asset_id FROM assets WHERE asset_type=? ORDER BY asset_id",
                (asset_type,)).fetchall()
            out = []
            for r in rows:
                g = self.ks.get_asset(r["asset_id"], verify=True)
                out.append(hashlib.sha256(json.dumps(
                    g["asset"]["payload"], sort_keys=True,
                    ensure_ascii=False).encode()).hexdigest())
            return out
        before_v = fp("claim_verification")
        before_c = fp("claim_candidate")
        # 用会失败的 adapter
        r = self.run_exec(c, plan, a,
                          adapter=CA.FakeGhAdapter({}, {},
                                                   commit_error="NETWORK_TIMEOUT"))
        self.assertFalse(r.ok)
        self.assertEqual(fp("claim_verification"), before_v,
                         "执行失败不得修改旧 Verification")
        self.assertEqual(fp("claim_candidate"), before_c,
                         "执行失败不得修改旧 Claim")

    def test_execution_status_unknown_on_unobservable(self):
        """只读 API 超时 → UNKNOWN，不冒充已失败或已成功。"""
        st, c, plan, a = self._setup()
        r = self.run_exec(c, plan, a,
                          adapter=CA.FakeGhAdapter({}, {},
                                                   commit_error="NETWORK_TIMEOUT",
                                                   uncertain=True))
        self.assertFalse(r.ok)
        self.assertEqual(r.execution_status, RS.UNKNOWN)
        self.assertTrue(r.uncertain_side_effect,
                        "必须保留副作用风险标记（不自动重试）")


class TestTargetDrift(Base):
    """T-28/T-29：执行中 B→C 不自动改目标、授权不转移。"""

    def test_t28_b_result_keeps_target_commit(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        r = self.run_exec(c, plan, a)
        self.assertTrue(r.ok)
        self.assertEqual(r.payload["target_commit_sha"], B_SHA,
                         "结果必须绑定 B")
        self.assertFalse(r.payload["freshness_context"]["is_current_ref_target"],
                         "必须标明已不是当前 Ref 目标")
        # 现在出现 C
        st_c, c_c = self.make_candidate(target=C_SHA)
        # B 的结果不变
        c2 = RQ.read_candidate(self.ks, candidate_id=c["candidate_id"],
                               repository_id=FX.REPO)["payload"]
        self.assertEqual(c2["target_commit_sha"], B_SHA)
        # 新的活动候选是 C
        q = RQ.read_queue(self.ks, watch_id=c["watch_id"],
                          repository_id=FX.REPO)
        self.assertNotEqual(q["active_candidate_id"], c["candidate_id"])

    def test_t29_old_auth_not_valid_for_c(self):
        st, c = self.make_candidate(target=B_SHA)
        plan = _plan(c["candidate_id"], B_SHA)
        a = _auth(c["candidate_id"], B_SHA, plan)
        # 出现 C
        st_c, c_c = self.make_candidate(target=C_SHA)
        c_new = RQ.read_candidate(self.ks,
                                  candidate_id=self._cand_id(),
                                  repository_id=FX.REPO)["payload"]
        self.assertEqual(c_new["target_commit_sha"], C_SHA)
        plan_c = _plan(c_new["candidate_id"], C_SHA)
        # ★ 用 B 的授权去执行 C 的候选 → 必须拒绝
        adapter = CA.FakeGhAdapter({C_SHA: TREE_B},
                                   {TREE_B: {"entries": [], "truncated": False}})
        r = EX.execute_revalidation(
            self.ks, candidate_id=c_new["candidate_id"],
            repository_id=FX.REPO, authorization=a, plan=plan_c,
            adapter=adapter, now=NOW)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)
        self.assertEqual(adapter.calls, [], "旧授权不得触发新目标的采集")


if __name__ == "__main__":
    unittest.main(verbosity=2)
