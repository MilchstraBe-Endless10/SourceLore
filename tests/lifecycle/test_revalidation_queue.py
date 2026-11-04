#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3B 主测试：T-1..T-18、T-20、T-23..T-30。"""
import sys, tempfile, shutil, unittest, json, hashlib, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/facts", "src/collector",
          "src/runtime", "src/evidence_claims", "tests/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import importlib.util as _ilu
_s = _ilu.spec_from_file_location(
    "lc_fx_b", str(Path(__file__).resolve().parent / "fixtures.py"))
FX = _ilu.module_from_spec(_s); _s.loader.exec_module(FX)

import lc_models as L
import revalidation_models as R
import revalidation_queue as RQ
import revalidation_dispatch_gate as DG
import lifecycle_store as LS
import freshness_evaluator as FE


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3b_"))
        self.ks = FX.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def stack(self, **kw):
        return FX.make_full_stack(self.ks, **kw)

    def propose(self, st, **kw):
        return RQ.propose_candidate(self.ks, assessment_id=st["assessment_id"], **kw)


class TestGate(Base):
    """T-1..T-10：门禁与拒绝原因。"""

    def test_t1_real_assessment_lookup(self):
        st = self.stack()
        g = RQ.evaluate_eligibility.__module__  # 仅确保模块可导入
        from revalidation_planner import evaluate_eligibility
        gate = evaluate_eligibility(self.ks, assessment_id=st["assessment_id"])
        self.assertTrue(gate.ok, f"{gate.reason} {gate.detail}")
        self.assertEqual(gate.ctx["claim_id"], st["claim_id"])

    def test_t2_non_possibly_stale_rejected(self):
        st = self.stack(target=FX.COMMIT_A)          # 目标=基线 → VERSION_ALIGNED
        self.assertEqual(st["assessment"].freshness_state, L.VERSION_ALIGNED)
        r = self.propose(st)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], R.RJ_NOT_POSSIBLY_STALE)

    def test_t3_pinned_commit_rejected(self):
        """PINNED_COMMIT 语义：不建 watch → 无评估 → 无候选。"""
        st = FX.make_pinned_stack(self.ks)
        with self.assertRaises(ValueError):
            L.LifecycleWatch(
                watch_id=L.make_watch_id(
                    repository_id=FX.REPO, requested_ref="master",
                    ref_kind=L.REF_KIND_BRANCH, retrieval_scope=FX.SCOPE,
                    baseline_commit_sha=FX.COMMIT_A,
                    claim_id=st["claim"].claim_id,
                    applicability_scope=L.PINNED_COMMIT),
                repository_id=FX.REPO, requested_ref="master",
                ref_kind=L.REF_KIND_BRANCH, retrieval_scope=FX.SCOPE,
                baseline_commit_sha=FX.COMMIT_A,
                claim_id=st["claim"].claim_id,
                applicability_scope=L.PINNED_COMMIT)
        # 没有评估资产 → 任何 assessment_id 都查不到
        r = RQ.propose_candidate(self.ks,
                                 assessment_id="SL-FRESH-" + "0" * 32)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], R.RJ_ASSESSMENT_NOT_FOUND)

    def _patch_assessment(self, **overrides):
        """伪造评估 payload 的字段（不写库，绕开 A 层完整性校验）。

        ★ 直接改库内 payload 会触发内容哈希校验（ASSESSMENT_INTEGRITY_FAILED）——
          那本身是正确行为，但测不到"字段不一致"这一层门禁。
          所以这里用受控的返回替换，专注测门禁逻辑。
        """
        import revalidation_planner as RP
        st = self.stack()
        real = RP._resolve_assessment(self.ks, st["assessment_id"])
        self.assertTrue(real.get("ok"))
        fake = copy.deepcopy(real)
        # _resolve_assessment 返回 {"ok":True,"asset":{...}}，字段在 asset.payload
        fake["asset"]["payload"].update(overrides)
        orig = RP._resolve_assessment
        RP._resolve_assessment = lambda store, aid: fake
        self.addCleanup(lambda: setattr(RP, "_resolve_assessment", orig))
        return st, fake["asset"]["payload"]["assessment_id"]

    def test_t4_wrong_watch_rejected(self):
        st, aid = self._patch_assessment(watch_id="SL-WATCH-" + "0" * 32)
        r = RQ.propose_candidate(self.ks, assessment_id=aid)
        self.assertFalse(r["ok"])
        self.assertIn(r["reason_code"], (R.RJ_WATCH_NOT_FOUND,
                                         R.RJ_WATCH_MISMATCH))

    def test_t5_wrong_repository_rejected(self):
        st, aid = self._patch_assessment(repository_id="999999")
        r = RQ.propose_candidate(self.ks, assessment_id=aid)
        self.assertFalse(r["ok"])
        self.assertIn(r["reason_code"], (R.RJ_REPO_MISMATCH,
                                         R.RJ_WATCH_NOT_FOUND))

    def test_t6_baseline_mismatch_rejected(self):
        st, aid = self._patch_assessment(baseline_commit_sha="c" * 40)
        r = RQ.propose_candidate(self.ks, assessment_id=aid)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], R.RJ_BASELINE_MISMATCH)

    def test_t7_corrupt_source_rejected(self):
        r = RQ.propose_candidate(self.ks, assessment_id="SL-A-DEADBEEF")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], R.RJ_ASSESSMENT_NOT_FOUND)

    def test_t8_unresolved_conflict_not_queued(self):
        """T-8：冲突未决不得正常入队（且必须真的构造出冲突状态）。"""
        st = self.stack(conflict=L.CONFLICT_DETECTED)
        self.assertEqual(st["assessment"].freshness_state, L.POSSIBLY_STALE)
        self.assertEqual(st["assessment"].source_evidence_conflict,
                         L.CONFLICT_DETECTED)
        r = self.propose(st)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], R.RJ_UNRESOLVED_CONFLICT)

    def test_t8b_conflict_unknown_not_treated_as_none(self):
        """缺失/未核验 ≠ 无冲突。"""
        st = self.stack(conflict=L.CONFLICT_UNKNOWN)
        self.assertEqual(st["assessment"].source_evidence_conflict,
                         L.CONFLICT_UNKNOWN)
        r = self.propose(st)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], R.RJ_CONFLICT_UNKNOWN,
                         "CONFLICT_UNKNOWN 不得当作无冲突放行")

    def test_t9_synthetic_not_dispatchable(self):
        st = self.stack(provenance_real=False)
        r = self.propose(st)
        # 可以入队（保留可追溯），但必须是 BLOCKED 且不可调度
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["candidate_status"], R.BLOCKED)
        self.assertEqual(r["state_reason"], R.RJ_SYNTHETIC_NOT_DISPATCHABLE)
        plan = DG.prepare_revalidation_plan(
            self.ks, candidate_id=r["candidate_id"],
            repository_id=FX.REPO)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["gate"], DG.P_GATE_NOT_PROPOSED)

    def test_t10_historical_not_treated_as_live(self):
        """历史真实观测 ≠ 实时最新状态；不得进入真实调度。"""
        st = self.stack(provenance_real=False)
        r = self.propose(st)
        self.assertEqual(r["source_level"], R.SRC_SYNTHETIC)
        self.assertNotIn(r["source_level"], R.DISPATCHABLE_SOURCES)
        self.assertEqual(sorted(R.DISPATCHABLE_SOURCES), [R.SRC_REAL])


class TestIdentity(Base):
    """T-11..T-14。"""

    def test_t11_candidate_id_deterministic(self):
        cid1 = R.make_candidate_id(
            watch_id="SL-WATCH-" + "a" * 32,
            source_claim_id="SL-CLAIM-" + "b" * 40,
            target_commit_sha="c" * 40, repository_id="1")
        cid2 = R.make_candidate_id(
            watch_id="SL-WATCH-" + "a" * 32,
            source_claim_id="SL-CLAIM-" + "b" * 40,
            target_commit_sha="c" * 40, repository_id="1")
        self.assertEqual(cid1, cid2)
        self.assertTrue(R.SAFE_CANDIDATE_ID.match(cid1))

    def test_t12_different_watch_no_collision(self):
        a = R.make_candidate_id(watch_id="SL-WATCH-"+"a"*32,
                                source_claim_id="SL-CLAIM-"+"b"*40,
                                target_commit_sha="c"*40, repository_id="1")
        b = R.make_candidate_id(watch_id="SL-WATCH-"+"d"*32,
                                source_claim_id="SL-CLAIM-"+"b"*40,
                                target_commit_sha="c"*40, repository_id="1")
        self.assertNotEqual(a, b)

    def test_t13_different_target_no_collision(self):
        a = R.make_candidate_id(watch_id="SL-WATCH-"+"a"*32,
                                source_claim_id="SL-CLAIM-"+"b"*40,
                                target_commit_sha="c"*40, repository_id="1")
        b = R.make_candidate_id(watch_id="SL-WATCH-"+"a"*32,
                                source_claim_id="SL-CLAIM-"+"b"*40,
                                target_commit_sha="d"*40, repository_id="1")
        self.assertNotEqual(a, b)

    def test_t13b_different_repository_no_collision(self):
        a = R.make_candidate_id(watch_id="SL-WATCH-"+"a"*32,
                                source_claim_id="SL-CLAIM-"+"b"*40,
                                target_commit_sha="c"*40, repository_id="1")
        b = R.make_candidate_id(watch_id="SL-WATCH-"+"a"*32,
                                source_claim_id="SL-CLAIM-"+"b"*40,
                                target_commit_sha="c"*40, repository_id="2")
        self.assertNotEqual(a, b, "不同仓库不得碰撞")

    def test_t14_repeat_propose_idempotent(self):
        st = self.stack()
        r1 = self.propose(st)
        self.assertTrue(r1["ok"], r1)
        r2 = self.propose(st)          # 真的再调一次
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(r2["state"], RQ.IDEMPOTENT)
        self.assertEqual(r1["candidate_id"], r2["candidate_id"])
        n = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='revalidation_candidate'"
        ).fetchone()["n"]
        self.assertEqual(n, 1, "重复入队不得产生两条候选资产")


class TestABCHistory(Base):
    """T-15..T-18：A→B→C、取代、Ref 回退。"""

    def _propose_at(self, commit):
        st = self.stack(target=commit)
        return self.propose(st)

    def test_t15_abc_keeps_b_history(self):
        rb = self._propose_at("b" * 40)
        rc = self._propose_at("c" * 40)
        self.assertTrue(rb["ok"] and rc["ok"])
        self.assertNotEqual(rb["candidate_id"], rc["candidate_id"])
        # B 的历史必须在
        vb = RQ.read_candidate_versions(
            self.ks, candidate_id=rb["candidate_id"], repository_id=FX.REPO)
        self.assertTrue(vb["ok"], "被取代的候选必须仍可读")
        self.assertGreaterEqual(len(vb["versions"]), 1)
        hist = RQ.read_queue(self.ks, watch_id=rb.get("queue_id") and
                             FX.make_full_stack.__name__ or "", ) if False else None
        q = RQ.read_queue(self.ks, watch_id=self._watch_id(), repository_id=FX.REPO)
        self.assertIn(rb["candidate_id"], q["history_candidate_ids"])
        self.assertIn(rc["candidate_id"], q["history_candidate_ids"])
        self.assertEqual(q["active_candidate_id"], rc["candidate_id"])

    def _watch_id(self):
        row = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='lifecycle_watch'"
        ).fetchone()
        return json.loads(row["payload_json"])["watch_id"]

    def test_t16_superseded_keeps_reason(self):
        rb = self._propose_at("b" * 40)
        rc = self._propose_at("c" * 40)
        self.assertEqual(rc["state"], RQ.SUPERSEDED_EXISTING)
        self.assertEqual(rc["superseded_candidate_id"], rb["candidate_id"])
        # 标 B 为 SUPERSEDED，原因保留，历史可读
        m = RQ.mark_superseded(self.ks, candidate_id=rb["candidate_id"],
                               repository_id=FX.REPO,
                               superseded_by=rc["candidate_id"])
        self.assertTrue(m["ok"], m)
        got = RQ.read_candidate(self.ks, candidate_id=rb["candidate_id"],
                                repository_id=FX.REPO)
        self.assertEqual(got["payload"]["status"], R.SUPERSEDED)
        self.assertIn("取代", got["payload"]["state_reason"])
        # 旧版本仍可读
        vv = RQ.read_candidate_versions(self.ks, candidate_id=rb["candidate_id"],
                                        repository_id=FX.REPO)
        self.assertEqual(len(vv["versions"]), 2, "旧版本不得被覆盖")

    def test_t17_authorization_not_transferred(self):
        """旧目标的授权不能自动转移给新目标。"""
        rb = self._propose_at("b" * 40)
        rc = self._propose_at("c" * 40)
        # ★ 本轮不实现 AUTHORIZED，但必须保证：新候选不带任何授权痕迹
        cb = RQ.read_candidate(self.ks, candidate_id=rb["candidate_id"],
                               repository_id=FX.REPO)["payload"]
        cc = RQ.read_candidate(self.ks, candidate_id=rc["candidate_id"],
                               repository_id=FX.REPO)["payload"]
        for c in (cb, cc):
            self.assertNotIn("authorized", json.dumps(c, ensure_ascii=False).lower())
            self.assertIn(c["status"], (R.PROPOSED, R.BLOCKED))
        self.assertNotIn("AUTHORIZED", R.CANDIDATE_STATES,
                         "本轮不实现 AUTHORIZED 状态")
        self.assertNotEqual(cb["target_commit_sha"], cc["target_commit_sha"])
        self.assertNotEqual(cb["candidate_id"], cc["candidate_id"],
                            "新目标必须形成新候选，不继承旧授权")

    def test_t18_ref_rollback_keeps_history(self):
        rb = self._propose_at("b" * 40)
        rc = self._propose_at("c" * 40)
        # Ref 回到 A：生成 A 的评估（VERSION_ALIGNED），不应删历史
        st_a = self.stack(target=FX.COMMIT_A)
        self.assertEqual(st_a["assessment"].freshness_state, L.VERSION_ALIGNED)
        r = self.propose(st_a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], R.RJ_NOT_POSSIBLY_STALE)
        q = RQ.read_queue(self.ks, watch_id=self._watch_id(),
                          repository_id=FX.REPO)
        self.assertIn(rb["candidate_id"], q["history_candidate_ids"],
                      "Ref 回退不得删除历史候选")
        self.assertIn(rc["candidate_id"], q["history_candidate_ids"])


class TestImmutability(Base):
    """T-23..T-25：原始 Claim/Verification 不可变。"""

    def _fingerprint(self, asset_type):
        rows = self.ks.conn.execute(
            "SELECT asset_id FROM assets WHERE asset_type=? ORDER BY asset_id",
            (asset_type,)).fetchall()
        out = []
        for r in rows:
            g = self.ks.get_asset(r["asset_id"], verify=True)
            self.assertTrue(g["ok"])
            out.append(hashlib.sha256(
                json.dumps(g["asset"]["payload"], sort_keys=True,
                           ensure_ascii=False).encode()).hexdigest())
        return out

    def test_t23_claim_hash_unchanged(self):
        st = self.stack()
        before = self._fingerprint("claim_candidate")
        self.assertGreater(len(before), 0)
        self.propose(st)
        after = self._fingerprint("claim_candidate")
        self.assertEqual(before, after, "候选生成不得修改原始 Claim")

    def test_t24_verification_hash_unchanged(self):
        st = self.stack()
        before = self._fingerprint("claim_verification")
        self.assertGreater(len(before), 0)
        self.propose(st)
        after = self._fingerprint("claim_verification")
        self.assertEqual(before, after, "候选生成不得修改原始 Verification")

    def test_t25_no_new_verification_id(self):
        st = self.stack()
        n_before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.propose(st)
        n_after = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(n_before, n_after, "不得生成新 verification")
        # 也不生成事实资产
        f_before = st["fact_id"]
        rows = self.ks.conn.execute(
            "SELECT logical_identity FROM assets WHERE asset_type='extracted_fact'"
        ).fetchall()
        self.assertEqual([r["logical_identity"] for r in rows], [f_before])


class TestDispatchGate(Base):
    """T-26..T-29 + Dry-Run 副作用。"""

    def test_t26_t27_t28_dry_run_no_side_effects(self):
        st = self.stack()
        r = self.propose(st)
        self.assertTrue(r["ok"], r)
        plan = DG.prepare_revalidation_plan(
            self.ks, candidate_id=r["candidate_id"], repository_id=FX.REPO)
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(plan["gate"], R.GATE_PLAN_READY)
        se = plan["plan"]["side_effects"]
        # T-26/27/28：不得调用 Collector / Facts / EC
        self.assertFalse(se["called_collector"])
        self.assertFalse(se["called_github"])
        self.assertFalse(se["extracted_facts"])
        self.assertFalse(se["adjudicated_claims"])
        self.assertFalse(se["modified_verification"])
        self.assertFalse(se["modify_review_status"]) if False else None
        self.assertFalse(se["modified_review_status"])

    def test_t26b_plan_does_not_grow_assets(self):
        st = self.stack()
        r = self.propose(st)
        n_before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets").fetchone()["n"]
        DG.prepare_revalidation_plan(self.ks, candidate_id=r["candidate_id"],
                                     repository_id=FX.REPO)
        n_after = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets").fetchone()["n"]
        self.assertEqual(n_before, n_after, "Dry-Run 不得写入任何资产")

    def test_t29_no_authorized_without_human_evidence(self):
        st = self.stack()
        r = self.propose(st)
        plan = DG.prepare_revalidation_plan(
            self.ks, candidate_id=r["candidate_id"], repository_id=FX.REPO)
        ev = plan["plan"]["events_distinguished"]
        self.assertTrue(ev["PLAN_READY"])
        self.assertFalse(ev["EXECUTION_AUTHORIZED"],
                         "无人工审批证据不得标记 AUTHORIZED")
        self.assertFalse(ev["EXECUTION_COMPLETED"])
        DG.assert_no_authorization(plan["plan"])

    def test_plan_requires_proposed_and_active(self):
        st = self.stack(provenance_real=False)     # → BLOCKED
        r = self.propose(st)
        plan = DG.prepare_revalidation_plan(
            self.ks, candidate_id=r["candidate_id"], repository_id=FX.REPO)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["gate"], DG.P_GATE_NOT_PROPOSED)


class TestStatusHistory(Base):
    """T-30：状态历史可读回。"""

    def test_t30_history_readable(self):
        st = self.stack()
        r = self.propose(st)
        vv = RQ.read_candidate_versions(self.ks, candidate_id=r["candidate_id"],
                                        repository_id=FX.REPO)
        self.assertTrue(vv["ok"])
        self.assertGreaterEqual(len(vv["versions"]), 1)
        q = RQ.read_queue(self.ks, watch_id=st["watch_id"],
                          repository_id=FX.REPO)
        self.assertTrue(q["ok"])
        self.assertTrue(q["exists"])
        self.assertEqual(q["active_candidate_id"], r["candidate_id"])


class TestStaleSupersedeRegression(Base):
    """T-20 辅助：CAS 冲突。"""

    def test_t20_wrong_expected_version_conflict(self):
        st = self.stack()
        r = self.propose(st)
        self.assertTrue(r["ok"])
        # 用错误 expected_version 推队列
        q = RQ.read_queue(self.ks, watch_id=st["watch_id"],
                          repository_id=FX.REPO)
        from revalidation_models import WatchQueueState
        bad = WatchQueueState(
            queue_id=q["queue_id"], watch_id=st["watch_id"],
            repository_id=FX.REPO, active_candidate_id=r["candidate_id"],
            active_target_commit_sha="f" * 40,
            history_candidate_ids=q["history_candidate_ids"])
        res = RQ._write_queue(self.ks, watch=st["watch"],
                              queue=bad, expected_version=99)
        self.assertFalse(res["ok"], f"错误 CAS 不得成功: {res}")
        self.assertEqual(res["state"], RQ.CONFLICT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
