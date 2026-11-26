#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TD-001 回归：多进程并发首开新 checkpoint 库。

原缺陷：`_init_schema()` 对 meta.schema_version 做 check-then-insert，
多进程同时首开新库时都读到空、各自 INSERT，触发 UNIQUE 冲突。
本测试以多轮多进程竞争稳定捕获该缺陷，并校验并发写后的数据完整性。
"""
import os
import sys
import json
import sqlite3
import subprocess
import tempfile
import shutil
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2] / "src" / "runtime"

# 子进程：等待 go 信号后首开库并建一条唯一 checkpoint。
CODE = """
import sys, os, time, json
sys.path.insert(0, RUNTIME_PLACEHOLDER)
while not os.path.exists(GO_PLACEHOLDER):
    time.sleep(0.0005)
from checkpoint_store import CheckpointStore
try:
    with CheckpointStore(DB_PLACEHOLDER) as st:
        r = st.create_checkpoint(task_id='T' + sys.argv[1], run_id='R', stage='s0')
    print(json.dumps({'rc': 0, 'ok': r.get('ok'), 'err': r.get('error')}))
except Exception as e:
    print(json.dumps({'rc': 1, 'err': type(e).__name__ + ': ' + str(e)}))
"""


def _child_code(db, go):
    return (CODE.replace("RUNTIME_PLACEHOLDER", repr(str(RUNTIME)))
                .replace("GO_PLACEHOLDER", repr(go))
                .replace("DB_PLACEHOLDER", repr(db)))


def _run_wave(n, *, same_identity=False):
    """启动 n 个进程同时首开同一个新库；返回 (子进程错误列表, db 路径, tmp)。"""
    tmp = Path(tempfile.mkdtemp(prefix="td001reg_"))
    db = str(tmp / "cp.db")
    go = str(tmp / "go")
    code = _child_code(db, go)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME)
    tid_args = ["0"] * n if same_identity else [str(i) for i in range(n)]
    procs = [subprocess.Popen([sys.executable, "-c", code, tid],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env) for tid in tid_args]
    Path(go).write_text("go")
    errs = []
    results = []
    for (o, e), p in zip([pr.communicate(timeout=30) for pr in procs], procs):
        line = o.strip().split("\n")[-1] if o.strip() else ""
        try:
            d = json.loads(line)
        except Exception:
            d = {"rc": p.returncode, "raw": line}
        results.append(d)
        if p.returncode != 0 or d.get("rc") != 0:
            errs.append({"rc": p.returncode, "out": line, "stderr": e.strip()[-160:]})
    return errs, results, db, tmp


def _inspect(db):
    con = sqlite3.connect(db)
    try:
        meta = con.execute("SELECT k,v FROM meta ORDER BY k").fetchall()
        n_ck = con.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
        versions = con.execute(
            "SELECT DISTINCT checkpoint_version FROM checkpoints").fetchall()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        return {"meta": meta, "n_ck": n_ck, "versions": versions,
                "integrity": integrity}
    finally:
        con.close()


class TestConcurrentFirstOpen(unittest.TestCase):
    """多轮竞争：每轮所有进程都必须成功首开并建成自己的 checkpoint。"""

    ROUNDS = 8
    N = 16

    def test_concurrent_first_open_no_unique_conflict(self):
        failures = []
        try:
            for r in range(self.ROUNDS):
                errs, results, db, tmp = _run_wave(self.N)
                try:
                    st = _inspect(db)
                    self.assertEqual(len(results), self.N)
                    self.assertFalse(errs, f"第 {r} 轮出现子进程失败: {errs[:3]}")
                    self.assertEqual(st["meta"], [("schema_version", "1")],
                                     f"第 {r} 轮 meta 不一致: {st['meta']}")
                    self.assertEqual(st["n_ck"], self.N,
                                     f"第 {r} 轮 checkpoint 数不等于进程数: {st}")
                    self.assertEqual(st["integrity"], "ok")
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
        finally:
            pass
        self.assertFalse(failures)


class TestConcurrentSameIdentity(unittest.TestCase):
    """多进程写相同 (task_id, run_id)：只一个成功，其余 CONFLICT，无重复/孤立记录。"""

    def test_same_identity_no_duplicate(self):
        errs, results, db, tmp = _run_wave(12, same_identity=True)
        try:
            self.assertFalse(errs, f"子进程异常退出: {errs[:3]}")
            oks = [d for d in results if d.get("rc") == 0 and d.get("ok")]
            conflicts = [d for d in results if d.get("err") == "CONFLICT"]
            self.assertEqual(len(oks), 1, f"必须恰好一个成功: {results}")
            self.assertEqual(len(conflicts), 11, f"其余必须 CONFLICT: {results}")
            st = _inspect(db)
            self.assertEqual(st["n_ck"], 1, f"不得产生重复记录: {st}")
            self.assertEqual(st["versions"], [(1,)], f"版本指针必须一致: {st}")
            self.assertEqual(st["meta"], [("schema_version", "1")])
            self.assertEqual(st["integrity"], "ok")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestKnowledgeStoreConcurrentFirstOpen(unittest.TestCase):
    """TD-001 同源缺陷：KnowledgeStore 首开新库也不得 UNIQUE 冲突。"""

    STORAGE = Path(__file__).resolve().parents[2] / "src" / "storage"
    CODE = """
import sys, os, time, json
sys.path.insert(0, STORAGE_PLACEHOLDER)
while not os.path.exists(GO_PLACEHOLDER):
    time.sleep(0.0005)
from knowledge_store import KnowledgeStore
try:
    st = KnowledgeStore(DB_PLACEHOLDER)
    print(json.dumps({'rc': 0, 'version': st.schema_version()}))
    st.close()
except Exception as e:
    print(json.dumps({'rc': 1, 'err': type(e).__name__ + ': ' + str(e)}))
"""

    ROUNDS = 6
    N = 16

    def test_concurrent_first_open_no_unique_conflict(self):
        for r in range(self.ROUNDS):
            tmp = Path(tempfile.mkdtemp(prefix="td001ks_"))
            db = str(tmp / "kb.db")
            go = str(tmp / "go")
            code = (self.CODE.replace("STORAGE_PLACEHOLDER", repr(str(self.STORAGE)))
                            .replace("GO_PLACEHOLDER", repr(go))
                            .replace("DB_PLACEHOLDER", repr(db)))
            env = dict(os.environ)
            env["PYTHONPATH"] = str(self.STORAGE)
            procs = [subprocess.Popen([sys.executable, "-c", code],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, env=env) for _ in range(self.N)]
            Path(go).write_text("go")
            outs = [p.communicate(timeout=30) for p in procs]
            try:
                results = []
                for (o, e), p in zip(outs, procs):
                    line = o.strip().split("\n")[-1] if o.strip() else ""
                    results.append(json.loads(line) if line else {"rc": p.returncode})
                errs = [d for d in results if d.get("rc") != 0]
                self.assertFalse(errs, f"第 {r} 轮 KnowledgeStore 首开失败: {errs[:3]}")
                self.assertTrue(all(d.get("version") == 1 for d in results))
                con = sqlite3.connect(db)
                try:
                    meta = con.execute("SELECT k,v FROM meta ORDER BY k").fetchall()
                    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
                finally:
                    con.close()
                self.assertEqual(meta, [("schema_version", "1")])
                self.assertEqual(integrity, "ok")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
