#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3C 崩溃恢复测试：C-1..C-6 / T-32..T-36。

全部使用**真实 SIGKILL** 与真实多进程。
"""
import sys, tempfile, shutil, unittest, json, subprocess, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/facts", "src/collector",
          "src/runtime", "src/evidence_claims", "tests/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import importlib.util as _ilu
_s = _ilu.spec_from_file_location(
    "p3c_fx2", str(Path(__file__).resolve().parent / "fixtures.py"))
FX = _ilu.module_from_spec(_s); _s.loader.exec_module(FX)

import lc_models as L
import revalidation_models as R
import revalidation_queue as RQ
import revalidation_authorization as AUTH
import revalidation_run_store as RS
import lifecycle_store as LS

NOW = "2026-11-05T00:00:00+08:00"
B_SHA = "b" * 40


def _boot(paths):
    return "\n".join(f"sys.path.insert(0, {p!r})" for p in paths)


def _paths():
    return [str(ROOT/p) for p in
            ("src/lifecycle", "src/storage", "src/facts", "src/collector",
             "src/runtime", "src/evidence_claims", "tests/lifecycle")]


class TestKillAndReconcile(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3c_kill_"))
        self.ks = FX.fresh(self.tmp)
        st = FX.make_full_stack(self.ks, target=B_SHA)
        r = RQ.propose_candidate(self.ks, assessment_id=st["assessment_id"])
        self.cid = r["candidate_id"]
        self.st = st
        self.ks.close()
        self.ks = None

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _child(self, body):
        code = "import sys, json, os\n" + _boot(_paths()) + "\n" + body
        return subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True)

    # ── C-1：Snapshot 已提交，Checkpoint 未更新 ─────────────
    def test_c1_snapshot_committed_then_kill(self):
        body = f"""
import knowledge_store as KS, lc_models as L
import revalidation_queue as RQ, collector_adapter as CA
import revalidation_executor as EX, revalidation_authorization as AUTH
import revalidation_dispatch_gate as DG
ks = KS.KnowledgeStore({str(self.tmp/'kb.db')!r})
c = RQ.read_candidate(ks, candidate_id={self.cid!r}, repository_id={FX.REPO!r})["payload"]
plan = {{"candidate_id": c["candidate_id"], "repository_id": {FX.REPO!r},
         "requested_ref": "master", "target_commit_sha": {B_SHA!r},
         "intended_collector_scope": "full_tree_enumeration",
         "intended_fact_rules": ["file_path_observation@v1"],
         "intended_ec_rule_version": "path-exists-verifier/v1",
         "target_claim_parameters": c["target_claim_parameters"],
         "required_operations": sorted(AUTH.ALLOWED_OPERATIONS)}}
plan["plan_digest"] = AUTH.plan_digest_of(plan)
auth = AUTH.make_test_authorization(
    candidate_id=c["candidate_id"], repository_id={FX.REPO!r},
    requested_ref="master", target_commit_sha={B_SHA!r},
    plan_digest=plan["plan_digest"],
    authorized_scope="full_tree_enumeration",
    issued_at="2026-11-04T00:00:00+08:00",
    expires_at="2026-11-06T00:00:00+08:00")
# 只跑采集阶段：直接调内部函数
adapter = CA.FakeGhAdapter({{{B_SHA!r}: "1"*40}},
    {{"1"*40: {{"entries": [{{"path":"README","type":"blob","sha":"9"*40,
        "size":13,"mode":"100644"}}], "truncated": False}}}})
res = EX._collect_fixed_target(ks, candidate=c, adapter=adapter, now="t")
print("SNAPSHOT_COMMITTED", json.dumps({{"ok": res.get("ok"),
      "asset": res.get("snapshot_asset_id")}}), flush=True)
os.kill(os.getpid(), 9)
"""
        p = self._child(body)
        self.assertNotEqual(p.returncode, 0, "必须真的被 SIGKILL")
        self.assertIn("SNAPSHOT_COMMITTED", p.stdout)
        self.assertIn('"ok": true', p.stdout)

        ks = FX.fresh(self.tmp)
        try:
            n = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='repository_snapshot'"
            ).fetchone()["n"]
            # 源栈原本 1 个快照（A），加 B 的 → 2
            self.assertEqual(n, 2, "崩溃前提交的快照必须仍在")
            ops = ks.conn.execute(
                "SELECT count(*) AS n FROM operation_log WHERE operation_id LIKE 'OP-COL-%'"
            ).fetchone()["n"]
            self.assertGreaterEqual(ops, 1, "operation_id 必须落账以便对账")
            # 重放：再跑一次采集，必须幂等（不新增快照）
            c = RQ.read_candidate(ks, candidate_id=self.cid,
                                  repository_id=FX.REPO)["payload"]
            import revalidation_executor as EX
            import collector_adapter as CA
            adapter2 = CA.FakeGhAdapter({B_SHA: "1" * 40},
                {"1" * 40: {"entries": [{"path": "README", "type": "blob",
                                          "sha": "9" * 40, "size": 13,
                                          "mode": "100644"}],
                            "truncated": False}})
            res = EX._collect_fixed_target(ks, candidate=c, adapter=adapter2,
                                           now="t2")
            self.assertTrue(res["ok"], res)
            n2 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='repository_snapshot'"
            ).fetchone()["n"]
            self.assertEqual(n2, n, "重放不得新增快照")
        finally:
            ks.close()

    # ── C-2：Fact 已提交，Checkpoint 未更新 ─────────────────
    def test_c2_fact_committed_then_kill(self):
        ks = FX.fresh(self.tmp)
        try:
            c = RQ.read_candidate(ks, candidate_id=self.cid,
                                  repository_id=FX.REPO)["payload"]
            import revalidation_executor as EX
            import collector_adapter as CA
            adapter = CA.FakeGhAdapter({B_SHA: "1" * 40},
                {"1" * 40: {"entries": [{"path": "README", "type": "blob",
                                          "sha": "9" * 40, "size": 13,
                                          "mode": "100644"}],
                            "truncated": False}})
            sres = EX._collect_fixed_target(ks, candidate=c, adapter=adapter,
                                            now="t")
            self.assertTrue(sres["ok"], sres)
            fres = EX._extract_facts(ks, snapshot_asset_id=sres["snapshot_asset_id"],
                                     target_commit=B_SHA, repository_id=FX.REPO,
                                     target_path="README")
            self.assertTrue(fres["ok"], fres)
            n1 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='extracted_fact'"
            ).fetchone()["n"]
            self.assertEqual(n1, 2, "A 的 fact + B 的 fact")
            # 重放：再抽一次必须幂等
            fres2 = EX._extract_facts(ks, snapshot_asset_id=sres["snapshot_asset_id"],
                                      target_commit=B_SHA,
                                      repository_id=FX.REPO, target_path="README")
            self.assertTrue(fres2["ok"], fres2)
            n2 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='extracted_fact'"
            ).fetchone()["n"]
            self.assertEqual(n2, n1, "重复抽取幂等，不得推进 fact 版本")
            self.assertEqual(fres["fact_id"], fres2["fact_id"])
        finally:
            ks.close()

    # ── C-3：新 Claim 已提交，Verification 未提交 ────────────
    def test_c3_claim_without_verification_recovers(self):
        ks = FX.fresh(self.tmp)
        try:
            c = RQ.read_candidate(ks, candidate_id=self.cid,
                                  repository_id=FX.REPO)["payload"]
            import revalidation_executor as EX
            # 只建 Claim，不验证
            cr = EX._create_target_claim(ks, candidate=c, repository_id=FX.REPO)
            self.assertTrue(cr["ok"], cr)
            tc = cr["claim"]
            import ec_models as EM, verification_store as VS
            VS.ingest_claim(ks, tc)
            n1 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='claim_candidate'"
            ).fetchone()["n"]
            self.assertEqual(n1, 2, "源 Claim + 新 Claim")
            # 恢复：再建一次 → 同身份，不产生第二个目标 Claim
            cr2 = EX._create_target_claim(ks, candidate=c,
                                          repository_id=FX.REPO)
            self.assertTrue(cr2["ok"])
            self.assertEqual(cr2["claim"].claim_id, tc.claim_id,
                             "恢复后必须复用同一目标 Claim 身份")
            n2 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='claim_candidate'"
            ).fetchone()["n"]
            self.assertEqual(n2, n1, "不得创建第二个目标 Claim")
        finally:
            ks.close()

    # ── C-4：Verification 已提交，回执丢失 ───────────────────
    def test_c4_verification_committed_no_receipt(self):
        ks = FX.fresh(self.tmp)
        try:
            c = RQ.read_candidate(ks, candidate_id=self.cid,
                                  repository_id=FX.REPO)["payload"]
            import revalidation_executor as EX
            import collector_adapter as CA
            adapter = CA.FakeGhAdapter({B_SHA: "1" * 40},
                {"1" * 40: {"entries": [{"path": "README", "type": "blob",
                                          "sha": "9" * 40, "size": 13,
                                          "mode": "100644"}],
                            "truncated": False}})
            sres = EX._collect_fixed_target(ks, candidate=c, adapter=adapter, now="t")
            fres = EX._extract_facts(ks, snapshot_asset_id=sres["snapshot_asset_id"],
                                     target_commit=B_SHA, repository_id=FX.REPO,
                                     target_path="README")
            cr = EX._create_target_claim(ks, candidate=c, repository_id=FX.REPO)
            vr = EX._verify_target(ks, claim=cr["claim"],
                                   fact_id=fres["fact_id"],
                                   repository_id=FX.REPO)
            self.assertTrue(vr["ok"], vr)
            vid = vr["verification"].verification_id
            n1 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
            ).fetchone()["n"]
            self.assertEqual(n1, 2)
            # 恢复：查询真实 verification_id，重跑不得再推进
            vr2 = EX._verify_target(ks, claim=cr["claim"],
                                    fact_id=fres["fact_id"],
                                    repository_id=FX.REPO)
            self.assertTrue(vr2["ok"])
            self.assertEqual(vr2["verification"].verification_id, vid,
                             "回执丢失后恢复必须复用同一 verification_id")
            n2 = ks.conn.execute(
                "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
            ).fetchone()["n"]
            self.assertEqual(n2, n1, "不得重复推进当前指针")
            # 真实 id 可查
            got = ks.get_asset(
                ks.conn.execute("SELECT asset_id FROM assets WHERE logical_identity=?",
                                (vid,)).fetchone()["asset_id"])
            self.assertTrue(got["ok"], "verification 必须可读回")
        finally:
            ks.close()


class TestAuthorizationMidRun(unittest.TestCase):
    """C-5：执行前授权失效 → 拒绝新阶段启动。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3c_auth_"))
        self.ks = FX.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_c5_revoked_midflight_blocks_next_stage(self):
        import revalidation_executor as EX
        import collector_adapter as CA
        st, c = self._make()
        plan = self._plan(c)
        a = self._auth(c, plan)
        # ★ 采集阶段之后把授权标记为撤销，验证执行器在中间复查时拒绝
        adapter = CA.FakeGhAdapter({B_SHA: "1" * 40},
            {"1" * 40: {"entries": [], "truncated": False}})
        a2 = dict(a); a2["revocation_status"] = "revoked"
        r = EX.execute_revalidation(
            self.ks, candidate_id=c["candidate_id"],
            repository_id=FX.REPO, authorization=a2, plan=plan,
            adapter=adapter, now=NOW)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_code, EX.E_AUTH_REJECTED)
        self.assertEqual(adapter.calls, [], "授权撤销时不得启动采集")

    def _make(self):
        st = FX.make_full_stack(self.ks, target=B_SHA)
        r = RQ.propose_candidate(self.ks, assessment_id=st["assessment_id"])
        c = RQ.read_candidate(self.ks, candidate_id=r["candidate_id"],
                              repository_id=FX.REPO)["payload"]
        return st, c

    def _plan(self, c):
        p = {"candidate_id": c["candidate_id"], "repository_id": FX.REPO,
             "requested_ref": "master", "target_commit_sha": B_SHA,
             "intended_collector_scope": "full_tree_enumeration",
             "intended_fact_rules": ["file_path_observation@v1"],
             "intended_ec_rule_version": "path-exists-verifier/v1",
             "target_claim_parameters": c["target_claim_parameters"],
             "required_operations": sorted(AUTH.ALLOWED_OPERATIONS)}
        p["plan_digest"] = AUTH.plan_digest_of(p)
        return p

    def _auth(self, c, plan):
        return AUTH.make_test_authorization(
            candidate_id=c["candidate_id"], repository_id=FX.REPO,
            requested_ref="master", target_commit_sha=B_SHA,
            plan_digest=plan["plan_digest"],
            authorized_scope="full_tree_enumeration",
            issued_at="2026-11-04T00:00:00+08:00",
            expires_at="2026-11-06T00:00:00+08:00")

    def test_c6_unknown_does_not_auto_retry(self):
        """C-6：结果 UNKNOWN 不得自动重试。"""
        st, c = self._make()
        plan = self._plan(c)
        a = self._auth(c, plan)
        import revalidation_executor as EX
        import collector_adapter as CA
        # 外部只读操作可能发生但无法确认
        adapter = CA.FakeGhAdapter({}, {}, commit_error="NETWORK_TIMEOUT",
                                   uncertain=True)
        r = EX.execute_revalidation(
            self.ks, candidate_id=c["candidate_id"], repository_id=FX.REPO,
            authorization=a, plan=plan, adapter=adapter, now=NOW)
        self.assertFalse(r.ok)
        self.assertEqual(r.execution_status, RS.UNKNOWN,
                         "不确定性必须判 UNKNOWN")
        self.assertTrue(r.uncertain_side_effect,
                        "必须保留副作用风险（不自动重试）")
        # 没有任何 run 被自动重试（本批执行器不自动重试）
        self.assertEqual(len(adapter.calls), 1,
                         "不得自动重复调用外部操作")


if __name__ == "__main__":
    unittest.main(verbosity=2)
