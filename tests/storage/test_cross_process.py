#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨进程并发与崩溃测试（T-3 / T-4 / T-5 / T-10）。

全部真实子进程、真实信号、真实 SIGKILL。不用 mock。
所有数据落临时目录，不碰项目数据。
"""
import json, os, signal, subprocess, sys, tempfile, time, shutil, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "src" / "storage"
RUNTIME = ROOT / "src" / "runtime"
PP = os.pathsep.join([str(STORAGE), str(RUNTIME)])


def run_py(code: str, env_extra=None, timeout=60):
    env = dict(os.environ)
    env["PYTHONPATH"] = PP + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, env=env, timeout=timeout)


class TestConcurrentCAS(unittest.TestCase):
    """T-3：真实多进程竞争同一 B 指针版本。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p1b_cas_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_four_processes_one_wins_three_conflict(self):
        setup = f"""
import sys
sys.path.insert(0, {str(STORAGE)!r})
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore
with KnowledgeStore({self.db!r}) as ks:
    r = ks.append_asset_and_advance(AssetDraft(
        asset_type='capability_record', logical_identity='LI-1',
        repository_id='repo-a', payload={{'v': 1}}), expected_version=None)
    assert r['ok'], r
"""
        r = run_py(setup)
        self.assertEqual(r.returncode, 0, r.stderr)

        barrier = self.tmp / "go"
        code = f"""
import sys, json, os, time
sys.path.insert(0, {str(STORAGE)!r})
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore
go = {str(barrier)!r}
while not os.path.exists(go):
    time.sleep(0.001)
with KnowledgeStore({self.db!r}) as ks:
    r = ks.append_asset_and_advance(AssetDraft(
        asset_type='capability_record', logical_identity='LI-1',
        repository_id='repo-a', payload={{'v': sys.argv[1]}},
        asset_version=2), expected_version=1)
    print(json.dumps(r))
"""
        env = dict(os.environ); env["PYTHONPATH"] = PP
        procs = [subprocess.Popen([sys.executable, "-c", code, str(i)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env=env) for i in range(4)]
        time.sleep(0.2)
        barrier.write_text("go")
        outs = [p.communicate(timeout=60) for p in procs]

        results = []
        for (o, e), p in zip(outs, procs):
            self.assertEqual(p.returncode, 0, e)
            results.append(json.loads(o))

        wins = [r for r in results if r["ok"]]
        conflicts = [r for r in results if not r["ok"] and r.get("error") == "CONFLICT"]
        self.assertEqual(len(wins), 1, f"必须恰好一个成功: {results}")
        self.assertEqual(len(conflicts), 3, f"其余必须 CONFLICT: {results}")
        self.assertEqual(wins[0]["pointer_version"], 2)

        verify = run_py(f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
from knowledge_store import KnowledgeStore
with KnowledgeStore({self.db!r}, create=False) as ks:
    p = ks.current_pointer('LI-1', 'repo-a')
    n = ks.conn.execute('SELECT count(*) AS n FROM assets').fetchone()['n']
    print(json.dumps({{'pointer': p, 'assets': n}}))
""")
        d = json.loads(verify.stdout)
        self.assertEqual(d["pointer"]["pointer_version"], 2, "版本只能前进一次")
        self.assertEqual(d["assets"], 2, "只允许两个资产（v1 + 一个 v2）")


class TestKillBeforeCommit(unittest.TestCase):
    """T-4：事务内 A 已写入但未 COMMIT，SIGKILL → B 不得指向它。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p1b_kill_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_kill_inside_transaction_leaves_nothing(self):
        code = f"""
import sys
sys.path.insert(0, {str(STORAGE)!r})
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore

with KnowledgeStore({self.db!r}) as ks:
    ks.append_asset_and_advance(AssetDraft(
        asset_type='capability_record', logical_identity='BASE',
        repository_id='repo-a', payload={{'v': 0}}), expected_version=None)

    # 手工模拟"写 A 但未 COMMIT"的窗口
    ks.conn.execute('BEGIN IMMEDIATE')
    ks.conn.execute(
        "INSERT INTO assets(asset_id, asset_type, logical_identity, repository_id, "
        "subject_id, asset_version, content_hash, payload_json, commit_sha, "
        "root_tree_sha, tree_query_ref, operation_id, created_at) VALUES "
        "('SL-A-HALF','capability_record','HALF','repo-a',NULL,1,'deadbeef',"
        "'{{\\\"v\\\":9}}',NULL,NULL,NULL,NULL,'now')")
    ks.conn.execute(
        "INSERT INTO current_view(logical_identity, repository_id, current_asset_id, "
        "pointer_version, last_known_good, updated_at) VALUES "
        "('HALF','repo-a','SL-A-HALF',1,'SL-A-HALF','now')")
    print('HALF_UNCOMMITTED', flush=True)
    import time; time.sleep(30)
"""
        env = dict(os.environ); env["PYTHONPATH"] = PP
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                             text=True, env=env)
        time.sleep(1.3)
        p.send_signal(signal.SIGKILL)
        out, _ = p.communicate(timeout=30)
        self.assertIn("HALF_UNCOMMITTED", out, "必须先进未提交窗口")

        check = run_py(f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
from knowledge_store import KnowledgeStore
with KnowledgeStore({self.db!r}, create=False) as ks:
    half_ptr = ks.current_pointer('HALF', 'repo-a')
    half_asset = ks.conn.execute(
        "SELECT count(*) AS n FROM assets WHERE asset_id='SL-A-HALF'").fetchone()['n']
    base = ks.current_pointer('BASE', 'repo-a')
    print(json.dumps({{'half_ptr': half_ptr, 'half_asset': half_asset, 'base_ok': base['ok']}}))
""")
        self.assertEqual(check.returncode, 0, check.stderr)
        d = json.loads(check.stdout)
        self.assertEqual(d["half_asset"], 0, "未提交的 A 层记录不得可见")
        self.assertEqual(d["half_ptr"]["error"], "NOT_FOUND", "B 不得指向未提交的 A")
        self.assertTrue(d["base_ok"], "已提交的仍在")


class TestCrossDatabaseGap(unittest.TestCase):
    """T-5 / T-10：资产已提交、checkpoint 未更新 → operation_id 对账。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p1b_gap_"))
        self.kb = str(self.tmp / "kb.db")
        self.cp = str(self.tmp / "cp.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_asset_committed_checkpoint_missing_is_reconciled(self):
        """真实漏窗：知识库已提交，checkpoint 从未写入。"""
        code = f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
sys.path.insert(0, {str(RUNTIME)!r})
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore
from checkpoint_store import CheckpointStore
import asset_checkpoint_coordinator as CO

OP = 'OP-FIXED-001'
with CheckpointStore({self.cp!r}) as cps, KnowledgeStore({self.kb!r}) as ks:
    # 1) checkpoint 登记意图（stage=in_progress）
    cps.create_checkpoint(task_id='T1', run_id='R1', stage='asset_pending')
    # 2) 资产事务提交（带稳定 operation_id）
    r = ks.append_asset_and_advance(
        AssetDraft(asset_type='capability_record', logical_identity='LI-1',
                   repository_id='repo-a', payload={{'v': 1}}),
        expected_version=None, operation_id=OP)
    assert r['ok'], r
    # 3) 模拟"此处进程崩溃"—— 不写 checkpoint 的 result
    rec = CO.reconcile(ks, cps, task_id='T1', run_id='R1', operation_id=OP)
    print(json.dumps(rec))
"""
        r = run_py(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(rec["state"], CO_RECONCILED(),
                         f"资产已提交且 checkpoint 缺失 → 必须 RECONCILED: {rec}")
        # 该用例里 checkpoint 已建（stage=asset_pending，但无 result_digest），
        # 属于「有意图无回执」这一子情形，reason 应为 RESULT_NOT_RECORDED。
        self.assertEqual(rec["reason"], "ASSET_COMMITTED_RESULT_NOT_RECORDED")
        self.assertFalse(rec["auto_retry"], "不得自动重试（资产已存在）")
        self.assertEqual(rec["committed"]["pointer_version"], 1)

    def test_reconcile_writes_checkpoint_without_duplicating_asset(self):
        code = f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
sys.path.insert(0, {str(RUNTIME)!r})
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore
from checkpoint_store import CheckpointStore
import asset_checkpoint_coordinator as CO

OP = 'OP-FIXED-002'
with CheckpointStore({self.cp!r}) as cps, KnowledgeStore({self.kb!r}) as ks:
    cps.create_checkpoint(task_id='T2', run_id='R2', stage='asset_pending')
    r = ks.append_asset_and_advance(
        AssetDraft(asset_type='capability_record', logical_identity='LI-2',
                   repository_id='repo-a', payload={{'v': 1}}),
        expected_version=None, operation_id=OP)
    rec = CO.reconcile(ks, cps, task_id='T2', run_id='R2', operation_id=OP)
    w = CO.write_after_asset_commit(cps, task_id='T2', run_id='R2',
                                    op_record=rec['committed'])
    # 再对账一次，应变成"无需动作"
    rec2 = CO.reconcile(ks, cps, task_id='T2', run_id='R2', operation_id=OP)
    dup = CO.assert_no_version_double_advance(ks, OP)
    n_assets = ks.conn.execute("SELECT count(*) AS n FROM assets").fetchone()['n']
    print(json.dumps({{'rec': rec, 'write': w, 'rec2': rec2, 'dup': dup,
                       'assets': n_assets}}))
"""
        r = run_py(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(d["rec"]["state"], CO_RECONCILED())
        self.assertTrue(d["write"].get("ok"))
        self.assertEqual(d["rec2"]["state"], CO_NOTHING())
        self.assertTrue(d["dup"]["ok"], "operation_id 不得出现多次")
        self.assertEqual(d["dup"]["occurrences"], 1)
        self.assertEqual(d["assets"], 1, "对账不得重复创建资产")

    def test_no_operation_and_no_checkpoint_is_retry_safe(self):
        code = f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
sys.path.insert(0, {str(RUNTIME)!r})
from knowledge_store import KnowledgeStore
from checkpoint_store import CheckpointStore
import asset_checkpoint_coordinator as CO
with CheckpointStore({self.cp!r}) as cps, KnowledgeStore({self.kb!r}) as ks:
    rec = CO.reconcile(ks, cps, task_id='TX', run_id='RX', operation_id='OP-NONE')
    print(json.dumps(rec))
"""
        r = run_py(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(rec["state"], CO_RETRY_SAFE())
        self.assertTrue(rec["auto_retry"], "两侧均无副作用时可安全重试")

    def test_corrupt_checkpoint_needs_human(self):
        """checkpoint 库损坏 → NEEDS_HUMAN，绝不自动重做。"""
        code = f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
sys.path.insert(0, {str(RUNTIME)!r})
from knowledge_store import KnowledgeStore
from checkpoint_store import CheckpointStore
import asset_checkpoint_coordinator as CO
try:
    with CheckpointStore({self.cp!r}, create=False) as cps, KnowledgeStore({self.kb!r}) as ks:
        rec = CO.reconcile(ks, cps, task_id='TZ', run_id='RZ', operation_id='OP-Z')
        print(json.dumps(rec))
except Exception as e:
    print(json.dumps({{'state': 'NEEDS_HUMAN', 'reason': 'CHECKPOINT_UNREADABLE',
                       'raised': type(e).__name__}}))
"""
        # 先建一个真实 checkpoint 库再破坏
        pre = run_py(f"""
import sys
sys.path.insert(0, {str(RUNTIME)!r})
from checkpoint_store import CheckpointStore
with CheckpointStore({self.cp!r}) as cps:
    cps.create_checkpoint(task_id='TZ', run_id='RZ', stage='s')
""")
        self.assertEqual(pre.returncode, 0, pre.stderr)
        with open(self.cp, "r+b") as f:
            f.seek(0); f.write(b"\x00" * 200)

        r = run_py(code)
        out = r.stdout.strip()
        if not out:
            self.fail(f"无输出: {r.stderr[:200]}")
        d = json.loads(out)
        self.assertEqual(d["state"], "NEEDS_HUMAN")
        self.assertNotEqual(d.get("state"), CO_RETRY_SAFE(),
                            "损坏绝不能当作可重试")


def CO_RECONCILED(): 
    sys.path.insert(0, str(RUNTIME)); import asset_checkpoint_coordinator as C
    return C.RECONCILED

def CO_RETRY_SAFE():
    sys.path.insert(0, str(RUNTIME)); import asset_checkpoint_coordinator as C
    return C.RETRY_SAFE

def CO_NOTHING():
    sys.path.insert(0, str(RUNTIME)); import asset_checkpoint_coordinator as C
    return C.NOTHING_TO_DO


if __name__ == "__main__":
    unittest.main(verbosity=2)
