#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨进程恢复实测（R-1 / R-2 / R-3 / R-4 / R-5）。

**全部使用真实子进程与真实信号**，不用 mock。
所有数据落在临时目录，绝不触碰项目数据。
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


def run_py(code: str, *, env_extra=None) -> subprocess.CompletedProcess:
    """在独立进程里执行一段 Python，返回结果。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME) + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, env=env, timeout=60)


class TestCrossProcess(unittest.TestCase):
    """真实两进程实验。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slck_cross_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def db(self) -> str:
        return str(self.tmp / "cp.db")

    # ── R-1：正常保存与跨进程读取 ───────────────────────────
    def test_r1_write_then_read_from_other_process(self):
        """进程 A 写入，进程 B 读取：数据与版本一致。"""
        code_a = f"""
import sys, json
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db()!r}) as st:
    r = st.create_checkpoint(task_id='T1', run_id='R1', stage='collect',
                             input_digest='abc123')
    print(json.dumps({{'pid': __import__('os').getpid(), 'result': r}}))
"""
        a = run_py(code_a)
        self.assertEqual(a.returncode, 0, a.stderr)
        ra = json.loads(a.stdout)
        self.assertTrue(ra["result"]["ok"])

        code_b = f"""
import sys, json, os
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db()!r}, create=False) as st:
    r = st.read_checkpoint(task_id='T1', run_id='R1')
    print(json.dumps({{'pid': os.getpid(), 'result': r}}))
"""
        b = run_py(code_b)
        self.assertEqual(b.returncode, 0, b.stderr)
        rb = json.loads(b.stdout)
        ck = rb["result"]["checkpoint"]
        self.assertEqual(ck["task_id"], "T1")
        self.assertEqual(ck["run_id"], "R1")
        self.assertEqual(ck["stage"], "collect")
        self.assertEqual(ck["checkpoint_version"], 1)
        # 真·跨进程：两个不同 PID
        self.assertNotEqual(ra["pid"], rb["pid"])

    # ── R-3：两进程并发 CAS ────────────────────────────────
    def test_r3_concurrent_cas_one_wins_one_conflict(self):
        """两个独立进程用同一 expected_version 更新，必须一胜一 CONFLICT。"""
        setup = f"""
import sys
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db()!r}) as st:
    st.create_checkpoint(task_id='T1', run_id='R1', stage='s0')
"""
        r = run_py(setup)
        self.assertEqual(r.returncode, 0, r.stderr)

        # 两个进程在同一时刻尝试 CAS（用 barrier 文件同步起始）
        barrier = self.tmp / "go"
        code_cas = f"""
import sys, json, os, time
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
go = {str(barrier)!r}
while not os.path.exists(go):
    time.sleep(0.001)
with CheckpointStore({self.db()!r}, create=False) as st:
    r = st.update_checkpoint_if_version(task_id='T1', run_id='R1',
                                        expected_version=1, stage='s1')
    print(json.dumps({{'pid': os.getpid(), 'result': r}}))
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(RUNTIME)
        p1 = subprocess.Popen([sys.executable, "-c", code_cas],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env)
        p2 = subprocess.Popen([sys.executable, "-c", code_cas],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env)
        time.sleep(0.15)
        barrier.write_text("go")
        o1, e1 = p1.communicate(timeout=30)
        o2, e2 = p2.communicate(timeout=30)

        results = []
        for o, e, p in ((o1, e1, p1), (o2, e2, p2)):
            self.assertEqual(p.returncode, 0, e)
            results.append(json.loads(o)["result"])

        oks = [r for r in results if r["ok"]]
        conflicts = [r for r in results if not r["ok"] and r.get("error") == "CONFLICT"]
        self.assertEqual(len(oks), 1, f"必须恰好一个成功: {results}")
        self.assertEqual(len(conflicts), 1, f"必须恰好一个 CONFLICT: {results}")
        # 版本只递增一次，没有被静默覆盖两次
        self.assertEqual(oks[0]["checkpoint_version"], 2)

        verify = f"""
import sys, json
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db()!r}, create=False) as st:
    r = st.read_checkpoint(task_id='T1', run_id='R1')
    print(json.dumps(r))
"""
        v = run_py(verify)
        ck = json.loads(v.stdout)["checkpoint"]
        self.assertEqual(ck["checkpoint_version"], 2, "最终版本必须是 2（不是 3）")

    # ── R-4：幂等登记 ──────────────────────────────────────
    def test_r4_idempotent_key_not_registered_twice(self):
        code = f"""
import sys, json
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db()!r}) as st:
    st.create_checkpoint(task_id='T1', run_id='R1', stage='s0',
                         idempotency_key='IDEM-1')
    r1 = st.commit_idempotent(idempotency_key='IDEM-1', task_id='T1',
                              run_id='R1', result_payload={{'k': 1}})
    r2 = st.commit_idempotent(idempotency_key='IDEM-1', task_id='T1',
                              run_id='R1', result_payload={{'k': 2}})
    print(json.dumps({{'r1': r1, 'r2': r2}}))
"""
        r = run_py(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertFalse(d["r1"]["already_committed"])
        self.assertTrue(d["r2"]["already_committed"])
        # 第二次的 payload 没有覆盖第一次的摘要
        self.assertEqual(d["r2"]["result_digest"], d["r1"]["result_digest"])

    # ── 落盘隔离：checkpoint 不得在知识命名空间 ─────────────
    def test_db_cannot_live_in_knowledge_namespace(self):
        code = f"""
import sys
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
try:
    CheckpointStore({str(Path.cwd() / 'docs' / 'fusion' / 'x.db')!r})
    print('ALLOWED')
except PermissionError as e:
    print('BLOCKED')
"""
        r = run_py(code)
        self.assertIn("BLOCKED", r.stdout, r.stderr)


class TestCrashRecovery(unittest.TestCase):
    """R-2 / R-5：真实进程中断与损坏。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slck_crash_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def db(self) -> str:
        return str(self.tmp / "cp.db")

    # ── R-2：写入过程中被 SIGKILL ──────────────────────────
    def test_r2_kill_during_write_leaves_no_half_commit(self):
        """在事务中间强制杀死进程，重启后不得看到半提交记录。

        **中断位置：已 INSERT 但尚未 COMMIT 的窗口内。**
        SQLite 的事务保证：未 COMMIT 的写入在崩溃后回滚。
        """
        code = f"""
import sys, os, json, time
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore

with CheckpointStore({self.db()!r}) as st:
    st.create_checkpoint(task_id='BASE', run_id='R0', stage='init')

    # 开一个**未提交**的事务，然后原地等待被杀
    st.conn.execute("BEGIN IMMEDIATE")
    st.conn.execute(
        "INSERT INTO checkpoints (task_id, run_id, stage, status, "
        "checkpoint_version, checkpoint_ref, attempt_count, idempotency_key, "
        "input_digest, result_digest, updated_at) VALUES "
        "('HALF','RH','s1','in_progress',1,NULL,0,NULL,NULL,NULL,'now')")
    print('INSERTED_UNCOMMITTED', flush=True)
    time.sleep(30)
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(RUNTIME)
        p = subprocess.Popen([sys.executable, "-c", code],
                             stdout=subprocess.PIPE, text=True, env=env)
        # 等它进入"已 INSERT 未 COMMIT"的窗口
        time.sleep(1.2)
        p.send_signal(signal.SIGKILL)
        out, _ = p.communicate(timeout=20)
        self.assertIn("INSERTED_UNCOMMITTED", out, "必须先进入未提交窗口再杀")

        # 重启检查
        check = f"""
import sys, json
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db()!r}, create=False) as st:
    half = st.read_checkpoint(task_id='HALF', run_id='RH')
    base = st.read_checkpoint(task_id='BASE', run_id='R0')
    print(json.dumps({{'half': half, 'base_ok': base['ok']}}))
"""
        r = run_py(check)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        # 半提交记录必须不存在
        self.assertFalse(d["half"]["ok"], "未提交的写入不得在崩溃后可见")
        self.assertEqual(d["half"].get("error"), "NOT_FOUND")
        # 已提交的记录仍在
        self.assertTrue(d["base_ok"])

    # ── R-5：损坏不得被当作空库 ───────────────────────────
    def test_r5_corrupt_db_returns_explicit_error(self):
        """伪造一个损坏的数据库，必须显式报错，不得静默重建。"""
        code = f"""
import sys, json
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.db()!r}) as st:
    st.create_checkpoint(task_id='T1', run_id='R1', stage='s0')
print('CREATED')
"""
        r = run_py(code)
        self.assertEqual(r.returncode, 0, r.stderr)

        # 真实破坏：在已提交的库上面覆写垃圾字节（保留原文件作为对照副本）
        dbp = Path(self.db())
        orig = dbp.read_bytes()
        backup = self.tmp / "cp.db.backup"
        backup.write_bytes(orig)
        with open(dbp, "r+b") as f:
            f.seek(0)
            f.write(b"\x00" * 200)

        check = f"""
import sys, json
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
try:
    with CheckpointStore({self.db()!r}, create=False) as st:
        r = st.read_checkpoint(task_id='T1', run_id='R1')
        print(json.dumps({{'ok': r.get('ok'), 'error': r.get('error'), 'recovered': False}}))
except Exception as e:
    print(json.dumps({{'raised': type(e).__name__, 'msg': str(e)[:120]}}))
"""
        c = run_py(check)
        out = c.stdout.strip()
        self.assertTrue(out, c.stderr)
        d = json.loads(out)
        # 必须报错：要么抛出、要么显式 CHECKPOINT_CORRUPT
        self.assertTrue(
            "CHECKPOINT_CORRUPT" in json.dumps(d, ensure_ascii=False)
            or "raised" in d,
            f"损坏必须显式报错，实际: {d}")
        # 不得把损坏当作"记录不存在"（NOT_FOUND 是业务语义，不是损坏语义）
        self.assertNotEqual(d.get("error"), "NOT_FOUND",
                            "损坏不得伪装成 NOT_FOUND")
        # 对照副本仍在，可作为诊断证据
        self.assertTrue(backup.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
