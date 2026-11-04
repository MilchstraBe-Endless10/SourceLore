#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并发与恢复协调器测试。全部真实子进程。"""
import os, sys, json, subprocess, tempfile, shutil, time, unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2] / "src" / "runtime"
sys.path.insert(0, str(RUNTIME))
from checkpoint_store import CheckpointStore
import resume_coordinator as RC
import execution_result as ER


def run_py(code: str, env_extra=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME) + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra: env.update(env_extra)
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, env=env, timeout=60)


class TestResumeCoordinator(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slres_"))
        self.db = str(self.tmp / "cp.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_does_not_invent(self):
        with CheckpointStore(self.db) as st:
            p = RC.plan_resume(st, task_id="X", run_id="Y")
            self.assertFalse(p["ok"])
            self.assertFalse(p["auto_resume"])
            self.assertTrue(p["requires_human"])

    def test_clean_state_auto_resumes(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s1")
            st.record_attempt(task_id="T", run_id="R", state=ER.SUCCESS, exit_code=0)
            p = RC.plan_resume(st, task_id="T", run_id="R")
            self.assertTrue(p["ok"])
            self.assertTrue(p["auto_resume"])
            self.assertEqual(p["reason"], RC.RESUME_CLEAN)

    def test_unknown_blocks_auto_resume(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s1")
            st.record_attempt(task_id="T", run_id="R", state=ER.UNKNOWN,
                              side_effect_possible=True)
            p = RC.plan_resume(st, task_id="T", run_id="R")
            self.assertFalse(p["auto_resume"])
            self.assertTrue(p["requires_human"])

    def test_advance_stage_cas(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s1")
            r = RC.advance_stage(st, task_id="T", run_id="R",
                                 expected_version=1, next_stage="s2")
            self.assertTrue(r["ok"])
            bad = RC.advance_stage(st, task_id="T", run_id="R",
                                   expected_version=1, next_stage="s3")
            self.assertEqual(bad["error"], "CONFLICT")

    def test_unknown_result_not_written_as_success(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s1")
            res = ER.ExecutionResult(state=ER.UNKNOWN, side_effect_possible=True)
            RC.finish(st, task_id="T", run_id="R", result=res)
            got = st.read_checkpoint(task_id="T", run_id="R")["checkpoint"]
            self.assertEqual(got["status"], ER.UNKNOWN)
            self.assertNotEqual(got["status"], ER.SUCCESS)
            self.assertNotEqual(got["status"], ER.FAILED)


class TestMultiProcessConcurrency(unittest.TestCase):
    """多进程并发写：不得出现丢失更新或幻影记录。"""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slconc_"))
        self.db = str(self.tmp / "cp.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_many_processes_create_distinct_records(self):
        n = 6
        code = f"""
import sys, json, os
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db!r}) as st:
    r = st.create_checkpoint(task_id='T' + sys.argv[1], run_id='R', stage='s0')
    print(json.dumps(r))
"""
        env = dict(os.environ); env["PYTHONPATH"] = str(RUNTIME)
        procs = [subprocess.Popen([sys.executable, "-c", code, str(i)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env=env) for i in range(n)]
        outs = [p.communicate(timeout=30) for p in procs]
        for (o, e), p in zip(outs, procs):
            self.assertEqual(p.returncode, 0, e)
            self.assertTrue(json.loads(o)["ok"])
        with CheckpointStore(self.db, create=False) as st:
            for i in range(n):
                self.assertTrue(st.read_checkpoint(task_id=f"T{i}", run_id="R")["ok"])

    def test_concurrent_cas_no_lost_update(self):
        """4 进程各试 CAS，只有与当前版本匹配的那个能成功。"""
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s0")
        code = f"""
import sys, json, os, time
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
go = {str(self.tmp / 'go')!r}
while not os.path.exists(go): time.sleep(0.001)
with CheckpointStore({self.db!r}, create=False) as st:
    r = st.update_checkpoint_if_version(task_id='T', run_id='R',
                                        expected_version=1, stage='adv')
    print(json.dumps(r))
"""
        env = dict(os.environ); env["PYTHONPATH"] = str(RUNTIME)
        ps = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, env=env)
              for _ in range(4)]
        time.sleep(0.2)
        (self.tmp / "go").write_text("go")
        outs = [p.communicate(timeout=30) for p in ps]
        results = []
        for (o, e), p in zip(outs, ps):
            self.assertEqual(p.returncode, 0, e)
            results.append(json.loads(o))
        wins = [r for r in results if r["ok"]]
        conflicts = [r for r in results if not r["ok"] and r.get("error") == "CONFLICT"]
        self.assertEqual(len(wins), 1, f"必须只有一个成功: {results}")
        self.assertEqual(len(conflicts), 3)
        with CheckpointStore(self.db, create=False) as st:
            v = st.read_checkpoint(task_id="T", run_id="R")["checkpoint"]["checkpoint_version"]
            self.assertEqual(v, 2, "版本只能前进一次（没有丢失更新）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
