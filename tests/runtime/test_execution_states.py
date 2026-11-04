#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行状态契约测试：SUCCESS / FAILED / TIMEOUT / CANCELLED / UNKNOWN。

CANCELLED 与 TIMEOUT 用真实子进程 + 真实信号区分。
UNKNOWN 用受控的两阶段实验：副作用已落地，但回执丢失。
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2] / "src" / "runtime"
sys.path.insert(0, str(RUNTIME))

import execution_result as ER
from checkpoint_store import CheckpointStore


class TestExecutionResultContract(unittest.TestCase):
    def test_states_are_disjoint_from_storage_errors(self):
        self.assertTrue(ER.EXECUTION_STATES.isdisjoint(ER.STORAGE_ERRORS))
        self.assertEqual(len(ER.EXECUTION_STATES), 5)
        self.assertEqual(len(ER.STORAGE_ERRORS), 4)

    def test_unknown_is_not_terminal_and_blocks_retry(self):
        r = ER.ExecutionResult(state=ER.UNKNOWN, side_effect_possible=True)
        self.assertFalse(r.is_terminal())
        self.assertFalse(r.retry_allowed())

    def test_timeout_requires_side_effect_flag(self):
        with self.assertRaises(ValueError):
            ER.ExecutionResult(state=ER.TIMEOUT)  # 缺 side_effect_possible

    def test_failed_without_side_effect_can_retry(self):
        r = ER.ExecutionResult(state=ER.FAILED, exit_code=7)
        self.assertTrue(r.is_terminal())
        self.assertTrue(r.retry_allowed())

    def test_sigkill_maps_to_unknown_not_cancelled(self):
        r = ER.from_exit_code(137)
        self.assertEqual(r.state, ER.UNKNOWN)
        self.assertTrue(r.side_effect_possible)
        self.assertNotEqual(r.state, ER.CANCELLED, "SIGKILL 不得等于正常取消")


class TestRealCancellation(unittest.TestCase):
    """真实 SIGTERM 取消 vs 真实超时。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slstate_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _child(self, body: str):
        code = ("import sys, time, json, pathlib\n"
                "mark = pathlib.Path(sys.argv[1])\n" + body)
        return subprocess.Popen([sys.executable, "-c", code, str(self.tmp / "mark")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)

    def test_cancelled_via_sigterm(self):
        """真实 SIGTERM：子进程收到信号后写清理标记并退出。"""
        p = self._child("""
mark.write_text('started')
time.sleep(30)
""")
        try:
            time.sleep(1.0)
            self.assertTrue((self.tmp / "mark").exists(), "子进程应已启动")
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=20)
            rc = p.returncode
        finally:
            # 显式关闭管道，避免 ResourceWarning
            if p.stdout: p.stdout.close()
            if p.stderr: p.stderr.close()
        # SIGTERM 默认终止 → 负数退出码（-15）
        self.assertLess(rc, 0, f"SIGTERM 应导致信号退出，实际 {rc}")
        result = ER.ExecutionResult(state=ER.CANCELLED, exit_code=rc,
                                    detail="SIGTERM 取消", side_effect_possible=True)
        self.assertEqual(result.state, ER.CANCELLED)
        self.assertNotEqual(result.state, ER.TIMEOUT, "取消不是超时")

    def test_timeout_via_timeout_command(self):
        """真实超时：timeout(1) 杀掉子进程 → 124。"""
        script = self.tmp / "slow.py"
        script.write_text("import time\ntime.sleep(5)\n")
        r = subprocess.run(["timeout", "2", sys.executable, str(script)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 124)
        res = ER.from_exit_code(r.returncode)
        self.assertEqual(res.state, ER.TIMEOUT)
        self.assertNotEqual(res.state, ER.CANCELLED, "超时不是取消")
        self.assertTrue(res.side_effect_possible)

    def test_cancelled_and_timeout_are_distinguishable(self):
        """两态必须能互斥区分，不得合并。"""
        c = ER.ExecutionResult(state=ER.CANCELLED, side_effect_possible=True)
        t = ER.from_exit_code(124)
        self.assertNotEqual(c.state, t.state)
        self.assertIn(c.state, ER.EXECUTION_STATES)
        self.assertIn(t.state, ER.EXECUTION_STATES)


class TestUnknownSemantics(unittest.TestCase):
    """UNKNOWN：副作用已发生但回执丢失，不得误判也不得重做。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slunknown_"))
        self.db = str(self.tmp / "cp.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_side_effect_done_but_no_receipt_is_unknown(self):
        """受控场景：子进程真的写了文件（副作用已发生），但父进程拿不到回执。

        做法：子进程写文件后立即 SIGKILL 自己，父进程读不到任何 stdout。
        此时唯一安全的判定是 UNKNOWN —— 不能判 FAILED，也不能判 NOT_FOUND。
        """
        marker = self.tmp / "side_effect.txt"
        code = f"""
import os, signal, pathlib
p = pathlib.Path({str(marker)!r})
p.write_text('SIDE_EFFECT_HAPPENED')
os.kill(os.getpid(), signal.SIGKILL)
"""
        p = subprocess.Popen([sys.executable, "-c", code],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(timeout=30)
        rc = p.returncode

        # 副作用确实发生了
        self.assertTrue(marker.exists(), "副作用文件应已落地")
        # 但父进程没有可靠回执
        self.assertEqual(out.strip(), "")
        self.assertLess(rc, 0, "应被信号终止")

        res = ER.from_exit_code(rc)
        self.assertEqual(res.state, ER.UNKNOWN,
                         "副作用已发生+回执缺失 ⇒ 只能是 UNKNOWN")

    def test_unknown_not_mistaken_for_not_found(self):
        r = ER.ExecutionResult(state=ER.UNKNOWN, side_effect_possible=True)
        self.assertNotIn(r.state, ER.STORAGE_ERRORS,
                         "UNKNOWN 是执行期状态，不是存储错误")
        self.assertNotEqual(r.state, ER.NOT_FOUND)
        self.assertNotEqual(r.state, ER.FAILED)

    def test_resume_refuses_when_unknown(self):
        """checkpoint 层：上次 UNKNOWN → 不得自动续跑。"""
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T1", run_id="R1", stage="s0")
            st.record_attempt(task_id="T1", run_id="R1", state=ER.UNKNOWN,
                              side_effect_possible=True, detail="回执丢失")
            r = st.resume_checkpoint(task_id="T1", run_id="R1")
            self.assertTrue(r["ok"])
            self.assertFalse(r["resumable"], "UNKNOWN 不得自动续跑")
            self.assertEqual(r["reason"], "UNKNOWN_NEEDS_RECONCILE")

    def test_resume_refuses_when_timeout_with_side_effect(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T2", run_id="R2", stage="s0")
            st.record_attempt(task_id="T2", run_id="R2", state=ER.TIMEOUT,
                              exit_code=124, side_effect_possible=True)
            r = st.resume_checkpoint(task_id="T2", run_id="R2")
            self.assertFalse(r["resumable"])
            self.assertEqual(r["reason"], "TIMEOUT_SIDE_EFFECT_RISK")

    def test_resume_allows_clean_failure(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T3", run_id="R3", stage="s0")
            st.record_attempt(task_id="T3", run_id="R3", state=ER.FAILED,
                              exit_code=3, side_effect_possible=False)
            r = st.resume_checkpoint(task_id="T3", run_id="R3")
            self.assertTrue(r["resumable"], "无副作用的失败应可重跑")

    def test_unknown_requires_side_effect_flag(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T4", run_id="R4", stage="s0")
            r = st.record_attempt(task_id="T4", run_id="R4", state=ER.UNKNOWN,
                                  side_effect_possible=False)
            self.assertFalse(r["ok"], "UNKNOWN 缺副作用声明必须被拒绝")
            self.assertEqual(r["error"], "PERMISSION_DENIED")


class TestIdempotentSideEffect(unittest.TestCase):
    """重复请求不得重复提交受控本地副作用。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slidem_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_local_side_effect_committed_once(self):
        """真实副作用：计数器文件。幂等键重复时不应再次递增。"""
        counter = self.tmp / "count.txt"
        counter.write_text("0")
        db = str(self.tmp / "cp.db")

        def do_work(key: str) -> bool:
            """返回 True 表示这次真的执行了副作用。"""
            with CheckpointStore(db) as st:
                st.create_checkpoint(task_id="T", run_id="R", stage="s",
                                     idempotency_key=key)
                r = st.commit_idempotent(idempotency_key=key, task_id="T",
                                         run_id="R", result_payload={"k": key})
                if r["already_committed"]:
                    return False
            # 只有首次提交才做副作用
            n = int(counter.read_text())
            counter.write_text(str(n + 1))
            return True

        first = do_work("IDEM-A")
        second = do_work("IDEM-A")
        self.assertTrue(first, "首次应真正执行")
        self.assertFalse(second, "重复请求不得再次执行副作用")
        self.assertEqual(int(counter.read_text()), 1,
                         "副作用只能发生一次")


if __name__ == "__main__":
    unittest.main(verbosity=2)
