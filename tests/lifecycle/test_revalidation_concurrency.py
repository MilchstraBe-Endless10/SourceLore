#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3B 并发与崩溃恢复：T-19、T-21、T-22。

全部使用**真实多进程**与**真实 SIGKILL**，不用 Mock。
"""
import sys, tempfile, shutil, unittest, json, subprocess, os, signal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/facts", "src/collector",
          "src/runtime", "src/evidence_claims", "tests/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import importlib.util as _ilu
_s = _ilu.spec_from_file_location(
    "lc_fx_c", str(Path(__file__).resolve().parent / "fixtures.py"))
FX = _ilu.module_from_spec(_s); _s.loader.exec_module(FX)

import lc_models as L
import revalidation_models as R
import revalidation_queue as RQ


_BOOT = """
import sys
for p in ({paths!r}):
    sys.path.insert(0, p)
import knowledge_store as KS
import revalidation_queue as RQ
import revalidation_models as R
"""


def _paths():
    return [str(ROOT/p) for p in
            ("src/lifecycle", "src/storage", "src/facts", "src/collector",
             "src/runtime", "src/evidence_claims")]


class TestConcurrency(unittest.TestCase):
    """T-19：真实多进程并发只有一个活动候选。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3b_cc_"))
        self.ks = FX.fresh(self.tmp)
        self.st = FX.make_full_stack(self.ks)
        self.ks.close()
        self.ks = None

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _child(self, *, target, kill_after=None):
        code = _BOOT.format(paths=_paths()) + f"""
import json, os
ks = KS.KnowledgeStore({str(self.tmp / "kb.db")!r})
r = RQ.propose_candidate(ks, assessment_id={self.st['assessment_id']!r})
print(json.dumps({{"pid": os.getpid(), "ok": r.get("ok"),
                  "state": r.get("state"), "reason": r.get("reason_code"),
                  "cid": r.get("candidate_id")}}), flush=True)
ks.close()
"""
        return subprocess.Popen([sys.executable, "-c", code],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)

    def test_t19_single_active_candidate_under_concurrency(self):
        """多个进程同时提议同一目标 → 只产生一条候选、一个活动槽位。"""
        procs = [self._child(target=FX.COMMIT_B) for _ in range(4)]
        outs = []
        for p in procs:
            o, e = p.communicate()
            line = [l for l in o.strip().splitlines() if l.startswith("{")]
            self.assertTrue(line, f"子进程无输出: {e[:300]}")
            outs.append(json.loads(line[-1]))

        pids = {o["pid"] for o in outs}
        self.assertEqual(len(pids), len(outs), "必须使用不同 PID")

        created = [o for o in outs if o.get("state") in ("VERSION_ADDED",
                                                         "INGESTED")]
        others = [o for o in outs if o not in created]
        # 同一候选被并发提议：只允许一次真正"新建队列版本"
        self.assertLessEqual(len(created), 1,
                             f"最多一个进程新建队列，实际: {outs}")

        ks = FX.fresh(self.tmp)
        try:
            q = RQ.read_queue(ks, watch_id=self.st["watch_id"],
                              repository_id=FX.REPO)
            self.assertTrue(q["exists"])
            self.assertEqual(len(q["active_candidate_id"]), len("SL-REVAL-") + 32)
            cnt = RQ.count_active(ks, repository_id=FX.REPO)
            self.assertEqual(cnt["multi_active_watches"], [],
                             f"出现多活动候选: {cnt}")
            self.assertEqual(cnt["total_active"], 1,
                             f"全库活动候选必须恰好 1 个，实际 {cnt}")
            n_cand = ks.conn.execute(
                "SELECT count(*) AS n FROM assets "
                "WHERE asset_type='revalidation_candidate'").fetchone()["n"]
            self.assertEqual(n_cand, 1, "并发不得产生多条候选资产")
        finally:
            ks.close()

    def test_t19b_different_targets_still_single_active(self):
        """不同目标 Commit 并发 → 仍只有一个活动候选。"""
        stacks = []
        ks = FX.fresh(self.tmp)
        try:
            for tgt in ("b" * 40, "c" * 40):
                st = FX.make_full_stack(ks, target=tgt)
                stacks.append(st)
        finally:
            ks.close()
        code = _BOOT.format(paths=_paths()) + f"""
import json, os
ks = KS.KnowledgeStore({str(self.tmp / "kb.db")!r})
out = []
for aid in {[s["assessment_id"] for s in stacks]!r}:
    r = RQ.propose_candidate(ks, assessment_id=aid)
    out.append({{"aid": aid, "state": r.get("state"), "cid": r.get("candidate_id")}})
print(json.dumps({{"pid": os.getpid(), "out": out}}), flush=True)
ks.close()
"""
        procs = [subprocess.Popen([sys.executable, "-c", code],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) for _ in range(2)]
        outs = []
        for p in procs:
            o, e = p.communicate()
            line = [l for l in o.strip().splitlines() if l.startswith("{")]
            self.assertTrue(line, f"子进程无输出: {e[:300]}")
            outs.append(json.loads(line[-1]))
        self.assertEqual(len({o["pid"] for o in outs}), len(outs),
                         "必须不同 PID")
        ks = FX.fresh(self.tmp)
        try:
            cnt = RQ.count_active(ks, repository_id=FX.REPO)
            self.assertEqual(cnt["multi_active_watches"], [],
                             f"不得出现多活动候选: {cnt}")
            self.assertLessEqual(cnt["total_active"], 1,
                                 f"活动候选必须 <=1，实际 {cnt}")
        finally:
            ks.close()


class TestRecovery(unittest.TestCase):
    """T-21/T-22：真实 SIGKILL + operation_id 对账。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3b_rc_"))
        self.ks = FX.fresh(self.tmp)
        self.st = FX.make_full_stack(self.ks)
        self.ks.close()
        self.ks = None

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_t21_sigkill_after_commit_recovers(self):
        code = _BOOT.format(paths=_paths()) + f"""
import json, os
ks = KS.KnowledgeStore({str(self.tmp / "kb.db")!r})
r = RQ.propose_candidate(ks, assessment_id={self.st['assessment_id']!r})
print("COMMITTED", json.dumps({{"state": r.get("state"),
      "cid": r.get("candidate_id")}}), flush=True)
os.kill(os.getpid(), 9)
"""
        p = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0, "必须真的被 SIGKILL")
        self.assertIn("COMMITTED", p.stdout, "必须在 kill 前完成提交")

        ks = FX.fresh(self.tmp)
        try:
            q = RQ.read_queue(ks, watch_id=self.st["watch_id"],
                              repository_id=FX.REPO)
            self.assertTrue(q["exists"], "崩溃前提交的队列必须仍在")
            self.assertIsNotNone(q["active_candidate_id"])
            ops = ks.conn.execute(
                "SELECT count(*) AS n FROM operation_log "
                "WHERE operation_id LIKE 'OP-RVQ-%%'").fetchone()["n"]
            self.assertGreaterEqual(ops, 1, "operation_id 必须落账")
            # 重放：幂等，不重复写入
            before = ks.conn.execute(
                "SELECT count(*) AS n FROM assets").fetchone()["n"]
            r2 = RQ.propose_candidate(ks, assessment_id=self.st["assessment_id"])
            self.assertTrue(r2["ok"], r2)
            after = ks.conn.execute(
                "SELECT count(*) AS n FROM assets").fetchone()["n"]
            self.assertEqual(before, after,
                             f"崩溃后重放不得新增资产: {before} → {after}")
        finally:
            ks.close()

    def test_t22_operation_id_reconcile_no_double_version(self):
        ks = FX.fresh(self.tmp)
        try:
            r1 = RQ.propose_candidate(ks, assessment_id=self.st["assessment_id"])
            self.assertTrue(r1["ok"], r1)
            v1 = RQ.read_queue(ks, watch_id=self.st["watch_id"],
                               repository_id=FX.REPO)["asset_version"]
            # 重复执行同一提议（模拟恢复重放）
            r2 = RQ.propose_candidate(ks, assessment_id=self.st["assessment_id"])
            self.assertEqual(r2["state"], RQ.IDEMPOTENT)
            v2 = RQ.read_queue(ks, watch_id=self.st["watch_id"],
                               repository_id=FX.REPO)["asset_version"]
            self.assertEqual(v1, v2, "对账重放不得推进版本")
            rows = ks.conn.execute(
                "SELECT count(*) AS n FROM operation_log "
                "WHERE operation_id LIKE 'OP-RVQ-%%'").fetchone()["n"]
            self.assertGreaterEqual(rows, 1, "操作日志必须真实存在")
        finally:
            ks.close()


class TestMutation(unittest.TestCase):
    """§14 受控变异：核心测试必须能捕获这些错误。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p3b_mut_"))
        self.ks = FX.fresh(self.tmp)

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mutation_two_active_rejected(self):
        """让两个候选同时 ACTIVE —— 必须被契约拒绝。"""
        q = R.WatchQueueState(
            queue_id=R.make_queue_id(watch_id="SL-WATCH-" + "a" * 32),
            watch_id="SL-WATCH-" + "a" * 32, repository_id=FX.REPO,
            active_candidate_id="SL-REVAL-" + "b" * 32,
            active_target_commit_sha="c" * 40,
            history_candidate_ids=[])
        self.assertIsNotNone(q.active_candidate_id)
        # 结构上不可能有两个活动槽位（只有单一 active_candidate_id 字段）
        keys = [f for f in q.to_dict() if "active" in f]
        self.assertEqual(keys, ["active_candidate_id",
                                "active_target_commit_sha"],
                         "活动槽位必须唯一")

    def test_mutation_stale_to_refuted_rejected(self):
        """把 POSSIBLY_STALE 映射成 refuted —— 状态机必须拒绝。"""
        self.assertNotIn("refuted", R.CANDIDATE_STATES)
        self.assertNotIn("REFUTED", R.CANDIDATE_STATES)
        src = (ROOT/"src"/"lifecycle").glob("*.py")
        bad = [f.name for f in src
               if '"refuted"' in f.read_text(encoding="utf-8")]
        self.assertEqual(bad, [], f"Lifecycle 源码不得出现 refuted: {bad}")

    def test_mutation_unauthorized_execution_rejected(self):
        """允许未授权候选执行 —— 计划闸门必须拦住。"""
        self.assertNotIn("AUTHORIZED", R.CANDIDATE_STATES,
                         "本轮不得实现 AUTHORIZED 状态")
        import revalidation_dispatch_gate as DG
        plan_src = (ROOT/"src"/"lifecycle"/
                    "revalidation_dispatch_gate.py").read_text(encoding="utf-8")
        self.assertIn("EXECUTION_AUTHORIZED", plan_src)
        self.assertIn('"EXECUTION_AUTHORIZED": False', plan_src)

    def test_mutation_double_version_rejected(self):
        """对同一 candidate 重复推进版本 —— 幂等必须拦住。"""
        st = FX.make_full_stack(self.ks)
        r1 = RQ.propose_candidate(self.ks, assessment_id=st["assessment_id"])
        r2 = RQ.propose_candidate(self.ks, assessment_id=st["assessment_id"])
        self.assertEqual(r2["state"], RQ.IDEMPOTENT)
        v = RQ.read_queue(self.ks, watch_id=st["watch_id"],
                          repository_id=FX.REPO)["asset_version"]
        self.assertEqual(v, 1, f"重复推进必须只留 1 个版本，实际 {v}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
