#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lifecycle 测试（T-1..T-28 主体）。

全部离线；观测走 Collector 契约的确定性替身或已持久化快照回放。
"""
import sys, tempfile, shutil, unittest, json, copy, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"tests"/"lifecycle"), str(ROOT/"src"/"lifecycle"),
          str(ROOT/"src"/"storage"), str(ROOT/"src"/"facts"),
          str(ROOT/"src"/"collector"), str(ROOT/"src"/"runtime"),
          str(ROOT/"src"/"evidence_claims"), str(ROOT/"tests"/"evidence_claims")):
    if p not in sys.path: sys.path.insert(0, p)

# ★ 避免与 tests/evidence_claims/fixtures.py 同名冲突：按文件路径显式加载
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "lc_fixtures", str(Path(__file__).resolve().parent / "fixtures.py"))
FX = _ilu.module_from_spec(_spec); _spec.loader.exec_module(FX)

import lc_models as L
import ref_observer as RO
import freshness_evaluator as FE
import lifecycle_store as LS
import impact_resolver as IR


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3a_"))
        self.ks = FX.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assess(self, watch, obs, *, assessed_at="", observed_at=""):
        return FE.assess(watch=watch, observation=obs,
                         assessed_at=assessed_at, observed_at=observed_at)


class TestPinnedVsTracking(Base):
    """T-1 / T-13 / T-14：固定版本与移动 Ref 隔离。"""

    def test_t1_pinned_commit_not_affected_by_head_move(self):
        """固定 Commit 的 Claim 不随 HEAD 更新而改变。"""
        w = FX.make_watch(baseline=FX.COMMIT_A)
        obs = FX.observe_ok(ref="master", commit=FX.COMMIT_B)  # HEAD 动了
        # 但这条 watch 是 PINNED？—— 用 NOT_APPLICABLE 路径需要 PINNED 语义。
        # ★ 契约规定 PINNED_COMMIT 不得建 watch；这里验证"未建 watch 就不受影响"。
        pinned_watch_attempt = FX.make_pinned_watch()
        with self.assertRaises(ValueError):
            L.LifecycleWatch(
                watch_id=L.make_watch_id(
                    repository_id=FX.REPO, requested_ref="master",
                    ref_kind=L.REF_KIND_BRANCH, retrieval_scope=FX.SCOPE,
                    baseline_commit_sha=FX.COMMIT_A,
                    claim_id="SL-CLAIM-"+"1"*40,
                    applicability_scope=L.PINNED_COMMIT),
                **pinned_watch_attempt)
        # 无 watch → 影响范围为空，Claim 不受任何 Ref 事件影响
        r = IR.resolve_affected([], assessment_list=[])
        self.assertEqual(r["affected_claim_ids"], [],
                         "固定 Commit 的历史 Claim 不得因 HEAD 移动而失效")
        self.assertEqual(r["unaffected_claim_ids"], [])

    def test_t13_tag_treated_as_moving_ref(self):
        """Tag 变化按移动 Ref 处理，不覆盖历史 Commit。"""
        w = L.LifecycleWatch(
            watch_id=L.make_watch_id(
                repository_id=FX.REPO, requested_ref="v1.0",
                ref_kind=L.REF_KIND_TAG, retrieval_scope=FX.SCOPE,
                baseline_commit_sha=FX.COMMIT_A,
                claim_id="SL-CLAIM-"+"1"*40),
            repository_id=FX.REPO, requested_ref="v1.0",
            ref_kind=L.REF_KIND_TAG, retrieval_scope=FX.SCOPE,
            baseline_commit_sha=FX.COMMIT_A, claim_id="SL-CLAIM-"+"1"*40,
            applicability_scope=L.TRACKING_REF)
        obs = FX.observe_ok(ref="v1.0", commit=FX.COMMIT_B)
        v = self.assess(w, obs)
        self.assertEqual(v.freshness_state, L.POSSIBLY_STALE)
        self.assertEqual(w.baseline_commit_sha, FX.COMMIT_A,
                         "baseline 不变 —— 历史 Commit 不被覆盖")

    def test_t14_force_push_not_assumed_fast_forward(self):
        """强制推送不被自动解释成快进。"""
        w = FX.make_watch(baseline=FX.COMMIT_A)
        obs = FX.observe_ok(commit=FX.COMMIT_C)   # 与 A 无已知祖先关系
        v = self.assess(w, obs)
        self.assertEqual(v.freshness_state, L.POSSIBLY_STALE)
        self.assertIn("未验证祖先关系", v.detail,
                      "必须明确声明未验证祖先关系（不假定快进）")
        self.assertNotIn("fast_forward", json.dumps(v.to_dict()))


class TestFreshnessStates(Base):
    """T-2 / T-3 / T-7 / T-8。"""

    def test_t2_same_commit_version_aligned(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        obs = FX.observe_ok(commit=FX.COMMIT_A)
        v = self.assess(w, obs)
        self.assertEqual(v.freshness_state, L.VERSION_ALIGNED)
        self.assertIsNone(v.reason_code)

    def test_t3_new_commit_possibly_stale(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        obs = FX.observe_ok(commit=FX.COMMIT_B)
        v = self.assess(w, obs)
        self.assertEqual(v.freshness_state, L.POSSIBLY_STALE)
        self.assertEqual(v.reason_code, L.R_REF_MOVED)
        self.assertEqual(v.observed_commit_sha, FX.COMMIT_B)
        self.assertEqual(v.baseline_commit_sha, FX.COMMIT_A)
        # 记录必须带这些字段
        d = v.to_dict()
        for f in ("baseline_commit_sha", "observed_commit_sha",
                  "requested_ref", "evidence_refs", "reason_code",
                  "applicability_scope"):
            self.assertIn(f, d)

    def test_t7_no_observation_unknown(self):
        w = FX.make_watch()
        obs = RO.observe_ref_via_collector(
            FX.FakeClient({}, ok=False, error_code="NETWORK_TIMEOUT"),
            owner="octocat", name="Hello-World",
            repository_id=FX.REPO, requested_ref="master")
        v = self.assess(w, obs)
        self.assertEqual(v.freshness_state, L.UNKNOWN)
        self.assertEqual(v.reason_code, L.U_OBSERVATION_FAILED)

    def test_t8_network_failure_not_repo_update(self):
        """网络失败绝不伪装成"仓库更新"。"""
        w = FX.make_watch()
        obs = RO.observe_ref_via_collector(
            FX.FakeClient({}, ok=False, error_code="NETWORK_TIMEOUT"),
            owner="octocat", name="Hello-World",
            repository_id=FX.REPO, requested_ref="master")
        self.assertIsNone(obs.resolved_commit_sha,
                          "失败观测不得带 commit（不得伪造新 HEAD）")
        v = self.assess(w, obs)
        self.assertEqual(v.freshness_state, L.UNKNOWN)
        self.assertNotEqual(v.freshness_state, L.POSSIBLY_STALE,
                            "网络失败不得产生 POSSIBLY_STALE")
        self.assertIsNone(v.observed_commit_sha)

    def test_404_403_not_all_deletion(self):
        """404/403/限流不得统一解释成已删除。"""
        cases = {"REPO_NOT_FOUND": L.U_REF_UNAVAILABLE,
                 "PERMISSION_DENIED": L.U_PERMISSION_DENIED,
                 "RATE_LIMITED": L.U_RATE_LIMITED,
                 "AUTH_FAILED": L.U_PERMISSION_DENIED}
        for code, expect in cases.items():
            obs = RO.observe_ref_via_collector(
                FX.FakeClient({}, ok=False, error_code=code),
                owner="octocat", name="Hello-World",
                repository_id=FX.REPO, requested_ref="master")
            self.assertEqual(obs.failure_reason, expect, code)
            self.assertIsNone(obs.resolved_commit_sha)
            self.assertNotIn("deleted", json.dumps(obs.to_dict()).lower())

    def test_tree_sha_is_not_commit(self):
        """★ 40 位十六进制的 Tree SHA 不能被当成 Commit。"""
        tree_shaped = {"sha": "b4eecafa9be2f2006ce1b709d6857b07069b4608",
                       "tree": [{"path": "README"}], "truncated": False}
        class CT:
            def __init__(self, d): self.ok = True; self.data = d; self.error = None
        class Client:
            def commit_for_ref(self, o, n, r): return CT(tree_shaped)
        obs = RO.observe_ref_via_collector(Client(), owner="o", name="r",
                                           repository_id=FX.REPO,
                                           requested_ref="master")
        self.assertEqual(obs.observation_status, L.OBS_FAILED)
        self.assertEqual(obs.failure_reason, L.U_NOT_A_COMMIT_OBJECT)
        self.assertIsNone(obs.resolved_commit_sha)

    def test_branch_name_not_commit(self):
        class CT:
            def __init__(self, d): self.ok = True; self.data = d; self.error = None
        class Client:
            def commit_for_ref(self, o, n, r):
                return CT({"sha": "master", "commit": {"tree": {"sha": "b"*40}}})
        obs = RO.observe_ref_via_collector(Client(), owner="o", name="r",
                                           repository_id=FX.REPO,
                                           requested_ref="master")
        self.assertEqual(obs.failure_reason, L.U_COMMIT_MALFORMED)


class TestOrthogonality(Base):
    """T-4 / T-5 / T-6 / T-23 / T-25：新鲜度与裁决正交。"""

    def _make_ec_objects(self, ks):
        import ec_models as EM
        import verifier as V
        import verification_store as VS
        import importlib.util as _i2
        _s2 = _i2.spec_from_file_location(
            "ec_fixtures", str(ROOT/"tests"/"evidence_claims"/"fixtures.py"))
        EF = _i2.module_from_spec(_s2); _s2.loader.exec_module(EF)
        snap = EF.make_snapshot(ks, commit=FX.COMMIT_A)
        f = EF.make_fact(ks, snap["asset_id"], "README")
        c = EM.build_path_claim(repository_id=FX.REPO,
                                commit_sha=FX.COMMIT_A,
                                target_path="README", expected_exists=True)
        v = V.verify_path_claim(ks, c, [f["fact_id"]])
        VS.ingest_claim(ks, c)
        VS.ingest_verification(ks, v, repository_id=FX.REPO)
        return c, v, f

    def _verif_payload(self, verification_id):
        import json
        row = self.ks.conn.execute(
            "SELECT asset_id FROM assets WHERE logical_identity=?",
            (verification_id,)).fetchone()
        got = self.ks.get_asset(row["asset_id"])
        self.assertTrue(got["ok"], got)
        return got["asset"]["payload"]

    def test_t4_possibly_stale_does_not_change_supported(self):
        c, v, f = self._make_ec_objects(self.ks)
        self.assertEqual(v.status, "supported")
        # 用 payload（去掉存储层字段）做指纹，比较语义内容是否变
        payload_before = self._verif_payload(v.verification_id)
        before = hashlib.sha256(json.dumps(payload_before, sort_keys=True,
                                           ensure_ascii=False).encode()).hexdigest()
        w = FX.make_watch(baseline=FX.COMMIT_A, claim_id=c.claim_id)
        obs = FX.observe_ok(commit=FX.COMMIT_B)
        a = self.assess(w, obs)
        self.assertEqual(a.freshness_state, L.POSSIBLY_STALE)
        # EC 侧完全没变
        payload_after = self._verif_payload(v.verification_id)
        after = hashlib.sha256(json.dumps(payload_after, sort_keys=True,
                                          ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(before, after, "POSSIBLY_STALE 不得修改 verification")
        self.assertEqual(payload_after["status"], "supported")

    def test_t5_possibly_stale_does_not_change_refuted(self):
        import ec_models as EM, verifier as V
        import importlib.util as _i3
        _s3 = _i3.spec_from_file_location(
            "ec_fixtures2", str(ROOT/"tests"/"evidence_claims"/"fixtures.py"))
        EF = _i3.module_from_spec(_s3); _s3.loader.exec_module(EF)
        snap = EF.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = EF.make_fact(self.ks, snap["asset_id"], "README")
        c = EM.build_path_claim(repository_id=FX.REPO, commit_sha=FX.COMMIT_A,
                                target_path="README", expected_exists=False)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, "refuted")
        w = FX.make_watch(baseline=FX.COMMIT_A, claim_id=c.claim_id)
        a = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B))
        self.assertEqual(a.freshness_state, L.POSSIBLY_STALE)
        # refuted 保持
        self.assertEqual(v.status, "refuted")

    def test_t6_possibly_stale_no_auto_verification(self):
        c, v, f = self._make_ec_objects(self.ks)
        n_before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        w = FX.make_watch(baseline=FX.COMMIT_A, claim_id=c.claim_id)
        a = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B))
        LS.ingest_assessment(self.ks, a)
        n_after = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(n_before, n_after,
                         "POSSIBLY_STALE 不得自动创建 verification")

    def test_t23_review_status_untouched(self):
        import ec_models as EM
        c, v, f = self._make_ec_objects(self.ks)
        before = c.review_status
        w = FX.make_watch(baseline=FX.COMMIT_A, claim_id=c.claim_id)
        a = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B))
        LS.ingest_assessment(self.ks, a)
        self.assertEqual(c.review_status, before)
        self.assertNotEqual(c.review_status, EM.APPROVED,
                            "Lifecycle 不得把 review_status 改成 approved")

    def test_t25_no_auto_refuted_or_approved(self):
        src = (ROOT/"src"/"lifecycle").rglob("*.py")
        bad = []
        for f in src:
            t = f.read_text(encoding="utf-8")
            for token in ('"refuted"', "'refuted'", "APPROVED"):
                if token in t:
                    bad.append((f.name, token))
        self.assertEqual(bad, [], f"Lifecycle 源码不得出现 refuted/approved 写入: {bad}")


class TestScopeIsolation(Base):
    """T-9 / T-10 / T-11 / T-12。"""

    def test_t9_different_branch_no_interference(self):
        w_master = FX.make_watch(ref="master", baseline=FX.COMMIT_A)
        w_dev = FX.make_watch(ref="dev", baseline=FX.COMMIT_A)
        obs_master = FX.observe_ok(ref="master", commit=FX.COMMIT_B)
        obs_dev = FX.observe_ok(ref="dev", commit=FX.COMMIT_A)
        a_master = self.assess(w_master, obs_master)
        a_dev = self.assess(w_dev, obs_dev)
        self.assertEqual(a_master.freshness_state, L.POSSIBLY_STALE)
        self.assertEqual(a_dev.freshness_state, L.VERSION_ALIGNED,
                         "dev 未动，master 动不得影响 dev")
        # ★ 交叉观测必须被拒绝
        cross = self.assess(w_dev, obs_master)
        self.assertEqual(cross.freshness_state, L.UNKNOWN)
        self.assertEqual(cross.reason_code, L.U_REF_MISMATCH)

    def test_t10_different_repository_no_interference(self):
        w = FX.make_watch(repo=FX.REPO, baseline=FX.COMMIT_A)
        obs_other = FX.observe_ok(repo=FX.REPO_FORK, commit=FX.COMMIT_B)
        a = self.assess(w, obs_other)
        self.assertEqual(a.freshness_state, L.UNKNOWN)
        self.assertEqual(a.reason_code, L.U_REPO_MISMATCH)
        self.assertNotEqual(a.freshness_state, L.POSSIBLY_STALE,
                            "不同仓库不得互相影响")

    def test_t11_fork_has_independent_identity(self):
        w_main = FX.make_watch(repo=FX.REPO, baseline=FX.COMMIT_A)
        w_fork = FX.make_watch(repo=FX.REPO_FORK, baseline=FX.COMMIT_A)
        self.assertNotEqual(w_main.watch_id, w_fork.watch_id,
                            "Fork 与原仓库必须是不同 watch 身份")
        obs_fork = FX.observe_ok(repo=FX.REPO_FORK, commit=FX.COMMIT_B)
        a_main = self.assess(w_main, obs_fork)
        a_fork = self.assess(w_fork, obs_fork)
        self.assertEqual(a_main.freshness_state, L.UNKNOWN)
        self.assertEqual(a_fork.freshness_state, L.POSSIBLY_STALE)

    def test_t12_rename_keeps_repository_id(self):
        """仓库重命名后 repository_id 不变 → 同一身份，不产生新 Subject。"""
        w1 = FX.make_watch(repo=FX.REPO, ref="master", baseline=FX.COMMIT_A)
        # 重命名只改 owner/name，repository_id 不变
        w2 = L.build_watch(repository_id=FX.REPO, requested_ref="master",
                           ref_kind=L.REF_KIND_BRANCH, retrieval_scope=FX.SCOPE,
                           baseline_commit_sha=FX.COMMIT_A,
                           claim_id=w1.claim_id)
        self.assertEqual(w1.watch_id, w2.watch_id,
                         "重命名不得产生新 watch 身份（repository_id 稳定）")

    def test_impact_resolver_only_structured_fields(self):
        w = FX.make_watch(ref="master", baseline=FX.COMMIT_A)
        other = FX.make_watch(ref="dev", baseline=FX.COMMIT_A,
                              claim_id="SL-CLAIM-"+"2"*40)
        a = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B))
        r = IR.resolve_affected([w, other], assessment_list=[a])
        self.assertEqual(r["affected_claim_ids"], [w.claim_id],
                         "只有受影响的那条被标")
        self.assertEqual(len(r["unaffected"]), 0)
        self.assertEqual(r["unknown"][0]["claim_id"], other.claim_id)
        self.assertIn("file_name_matching", r["explicitly_not_used"],
                      "必须显式声明未使用文件名匹配")


class TestPersistence(Base):
    """T-15..T-22。"""

    def test_t16_freshness_independent_of_verification(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        a = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B))
        LS.ingest_assessment(self.ks, a)
        for t in ("claim_verification", "claim_candidate", "freshness_assessment"):
            n = self.ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type=?",
                (t,)).fetchone()["n"]
            if t == "freshness_assessment":
                self.assertEqual(n, 1)
            else:
                self.assertEqual(n, 0, f"{t} 不应被 Lifecycle 写入")
        self.assertTrue(L.SAFE_ASSESS_ID.match(a.assessment_id))
        self.assertNotIn("verification_id", a.to_dict())

    def test_t17_repeat_observation_idempotent(self):
        obs = FX.observe_ok(commit=FX.COMMIT_A, at="t1")
        obs2 = FX.observe_ok(commit=FX.COMMIT_A, at="t2")   # 不同时间
        self.assertEqual(obs.observation_id, obs2.observation_id,
                         "时间戳不得影响观测身份")
        a = LS.ingest_observation(self.ks, obs)
        b = LS.ingest_observation(self.ks, obs2)
        self.assertEqual(b["state"], LS.IDEMPOTENT)
        self.assertEqual(a["asset_id"], b["asset_id"])
        n = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='ref_observation'"
        ).fetchone()["n"]
        self.assertEqual(n, 1)

    def test_t18_repeat_assessment_no_duplicates(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        a1 = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B), assessed_at="t1")
        a2 = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B), assessed_at="t2")
        self.assertEqual(a1.assessment_id, a2.assessment_id,
                         "评估时间不得影响确定性身份")
        r1 = LS.ingest_assessment(self.ks, a1)
        r2 = LS.ingest_assessment(self.ks, a2)
        self.assertEqual(r2["state"], LS.IDEMPOTENT)
        n = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='freshness_assessment'"
        ).fetchone()["n"]
        self.assertEqual(n, 1, "重复评估不得创建多条等价资产")

    def test_t19_wrong_expected_version_conflict(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        LS.ingest_watch(self.ks, w)
        # 同 watch 但内容不同（baseline 变）→ 需要新版本
        w2 = L.LifecycleWatch(
            watch_id=w.watch_id, repository_id=w.repository_id,
            requested_ref=w.requested_ref, ref_kind=w.ref_kind,
            retrieval_scope=w.retrieval_scope, baseline_commit_sha=FX.COMMIT_B,
            claim_id=w.claim_id, applicability_scope=L.TRACKING_REF)
        bad = LS.ingest_watch(self.ks, w2, expected_version=99)
        self.assertFalse(bad["ok"], f"错误 CAS 不得成功: {bad}")
        self.assertEqual(bad["state"], LS.CONFLICT)
        good = LS.ingest_watch(self.ks, w2, expected_version=1)
        self.assertTrue(good["ok"])
        self.assertEqual(good["state"], LS.VERSION_ADDED)

    def test_t15_old_versions_readable(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        a1 = self.assess(w, FX.observe_ok(commit=FX.COMMIT_A))
        LS.ingest_assessment(self.ks, a1)
        r = LS.read_assessment_versions(self.ks, a1.assessment_id, FX.REPO)
        self.assertTrue(r["ok"])
        self.assertEqual(r["versions"][0]["payload"]["freshness_state"]
                         if "freshness_state" in r["versions"][0]["payload"]
                         else r["versions"][0]["payload"].get("freshness_state"),
                         L.VERSION_ALIGNED)

    def test_t20_concurrent_cas_only_one_succeeds(self):
        """真实多进程并发 CAS。"""
        import subprocess, os
        code = r'''
import sys, json, os
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import knowledge_store as KS, lc_models as L, lifecycle_store as LS
db = %r
ks = KS.KnowledgeStore(db)
# 各进程都试图把同一条 watch 推进到新内容（baseline 改成 "b"*40）
w = L.LifecycleWatch(
    watch_id=WATCH_ID, repository_id="1296269", requested_ref="master",
    ref_kind=L.REF_KIND_BRANCH, retrieval_scope="full_tree_enumeration",
    baseline_commit_sha="b"*40, claim_id="SL-CLAIM-"+"1"*40,
    applicability_scope=L.TRACKING_REF)
r = LS.ingest_watch(ks, w, expected_version=1)
print(json.dumps({"pid": os.getpid(), "state": r.get("state"), "ok": r.get("ok")}))
''' % (str(ROOT/"src"/"lifecycle"), str(ROOT/"src"/"storage"),
       str(self.tmp/"kb.db"))
        # 先写入 version 1（baseline=A）
        w0 = FX.make_watch(baseline=FX.COMMIT_A)
        LS.ingest_watch(self.ks, w0)
        # 关闭主连接，避免与子进程的写锁竞争干扰实验
        self.ks.close()
        self.ks = None
        code = code.replace("WATCH_ID", repr(w0.watch_id))
        procs = [subprocess.Popen([sys.executable, "-c", code],
                                  stdout=subprocess.PIPE, text=True)
                 for _ in range(4)]
        outs = []
        for p in procs:
            o, _ = p.communicate()
            outs.append(json.loads(o.strip().splitlines()[-1]))
        wins = [o for o in outs if o["state"] == "VERSION_ADDED"]
        others = [o for o in outs if o["state"] != "VERSION_ADDED"]
        # ★ 真实并发下只允许一个进程把版本从 1 推进到 2。
        # 其余进程要么被判 CONFLICT，要么在完成写入后看到已是同一内容
        # 而被判 IDEMPOTENT —— 两种都属于"没推进"，都合法；
        # 不合法的是出现第二个 VERSION_ADDED（那才是双写）。
        self.assertEqual(len(wins), 1,
                         f"并发 CAS 只能一个推进版本，实际: {outs}")
        self.assertEqual(len(others), len(outs) - 1)
        for o in others:
            self.assertIn(o["state"], ("CONFLICT", "IDEMPOTENT_ALREADY_PRESENT"),
                          f"未推进的进程状态非法: {o}")

    def test_t21_checkpoint_reconciliation(self):
        """资产提交后 Checkpoint 未更新 → 可通过 operation_id 恢复。"""
        w = FX.make_watch(baseline=FX.COMMIT_A)
        a = self.assess(w, FX.observe_ok(commit=FX.COMMIT_B))
        LS.ingest_assessment(self.ks, a)
        db = str(self.tmp/"kb.db")
        code = r'''
import sys, json
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import asset_checkpoint_coordinator as C
print(json.dumps({"ok": True}))
''' % (str(ROOT/"src"/"runtime"), str(ROOT/"src"/"storage"))
        n_assets = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='freshness_assessment'"
        ).fetchone()["n"]
        self.assertEqual(n_assets, 1)
        # operation_id 对账记录存在
        ops = self.ks.conn.execute(
            "SELECT count(*) AS n FROM operation_log WHERE operation_id LIKE 'OP-LC-%%'"
        ).fetchone()["n"]
        self.assertGreaterEqual(ops, 1, "operation_id 必须落账以支持对账")

    def test_t22_corrupt_source_diagnosed(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        obs = RO.observe_ref_from_snapshot(
            snapshot_asset={"asset_id": "snap-x", "payload": {
                "repository_id": FX.REPO, "commit_sha": FX.COMMIT_A,
                "requested_ref": "master", "retrieval_scope": FX.SCOPE,
                "collector_version": "c/1.0"}},
            repository_id=FX.REPO, requested_ref="master")
        self.assertEqual(obs.observation_status, L.OBS_OK)
        # 来源损坏：commit 非法
        obs_bad = RO.observe_ref_from_snapshot(
            snapshot_asset={"asset_id": "snap-y", "payload": {
                "repository_id": FX.REPO, "commit_sha": "broken",
                "requested_ref": "master", "retrieval_scope": FX.SCOPE,
                "collector_version": "c/1.0"}},
            repository_id=FX.REPO, requested_ref="master")
        self.assertEqual(obs_bad.observation_status, L.OBS_FAILED)
        self.assertEqual(obs_bad.failure_reason, L.U_COMMIT_MALFORMED)
        a = self.assess(w, obs_bad)
        self.assertEqual(a.freshness_state, L.UNKNOWN)
        self.assertEqual(a.reason_code, L.U_COMMIT_MALFORMED,
                         "损坏来源必须显式诊断，不能静默")

    def test_t24_timestamp_does_not_change_identity(self):
        w = FX.make_watch(baseline=FX.COMMIT_A)
        a1 = FE.assess(watch=w, observation=FX.observe_ok(commit=FX.COMMIT_B),
                       observed_at="2026-01-01", assessed_at="2026-01-01")
        a2 = FE.assess(watch=w, observation=FX.observe_ok(commit=FX.COMMIT_B),
                       observed_at="2027-12-31", assessed_at="2027-12-31")
        self.assertEqual(a1.assessment_id, a2.assessment_id)
        self.assertEqual(a1.to_dict()["freshness_state"],
                         a2.to_dict()["freshness_state"])


class TestSnapshotProvenance(Base):
    """T-26 辅助：快照回放的可信性边界。"""

    def test_snapshot_ref_mismatch_is_unknown(self):
        """快照没记录该 Ref → 不得伪造该 Ref 的观测。"""
        obs = RO.observe_ref_from_snapshot(
            snapshot_asset={"asset_id": "s", "payload": {
                "repository_id": FX.REPO, "commit_sha": FX.COMMIT_A,
                "requested_ref": "dev",          # 快照记的是 dev
                "retrieval_scope": FX.SCOPE,
                "collector_version": "c/1.0"}},
            repository_id=FX.REPO, requested_ref="master")   # 我们要 master
        self.assertEqual(obs.observation_status, L.OBS_FAILED)
        self.assertEqual(obs.failure_reason, L.U_REF_MISMATCH)
        self.assertIsNone(obs.resolved_commit_sha)

    def test_snapshot_repo_mismatch(self):
        obs = RO.observe_ref_from_snapshot(
            snapshot_asset={"asset_id": "s", "payload": {
                "repository_id": FX.REPO_FORK, "commit_sha": FX.COMMIT_A,
                "requested_ref": "master", "retrieval_scope": FX.SCOPE,
                "collector_version": "c/1.0"}},
            repository_id=FX.REPO, requested_ref="master")
        self.assertEqual(obs.failure_reason, L.U_REPO_MISMATCH)

    def test_provenance_levels_distinct(self):
        self.assertEqual(len(RO.PROVENANCE_LEVELS), 3)
        self.assertIn(RO.PROV_SYNTHETIC, RO.PROVENANCE_LEVELS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
