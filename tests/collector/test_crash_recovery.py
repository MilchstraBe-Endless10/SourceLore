#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-17 / T-18：采集入库的跨库漏窗与真实 SIGKILL 恢复。

真实子进程 + 真实信号。数据落临时目录。
"""
import json, os, signal, subprocess, sys, tempfile, time, shutil, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLL = ROOT / "src" / "collector"
ST = ROOT / "src" / "storage"
RT = ROOT / "src" / "runtime"
PP = os.pathsep.join([str(COLL), str(ST), str(RT), str(ROOT / "tests" / "collector")])

for p in (str(COLL), str(ST), str(RT), str(ROOT / "tests" / "collector")):
    if p not in sys.path:
        sys.path.insert(0, p)

import fake_gh as F
from source_snapshot import build_snapshot, COLLECTOR_VERSION
from tree_collector import COMPLETE
from ingest_coordinator import stable_operation_id, INGESTED
from knowledge_store import KnowledgeStore
import asset_checkpoint_coordinator as CO


def run_py(code, timeout=60):
    env = dict(os.environ); env["PYTHONPATH"] = PP + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, env=env, timeout=timeout)


class TestCollectorGap(unittest.TestCase):
    """T-17：资产已提交、checkpoint 未更新 → operation_id 对账。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p1c_gap_"))
        self.kb = str(self.tmp / "kb.db")
        self.cp = str(self.tmp / "cp.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_collect_then_die(self):
        """真实漏窗：资产入库成功，然后进程被 SIGKILL —— checkpoint 没写。"""
        code = f"""
import sys, os, signal, time, json
sys.path.insert(0, {str(COLL)!r})
sys.path.insert(0, {str(ST)!r})
sys.path.insert(0, {str(RT)!r})
from knowledge_store import KnowledgeStore
from checkpoint_store import CheckpointStore
from source_snapshot import build_snapshot, COLLECTOR_VERSION
from ingest_coordinator import ingest_snapshot, stable_operation_id

OP = 'OP-COL-T17'
with CheckpointStore({self.cp!r}) as cps, KnowledgeStore({self.kb!r}) as ks:
    cps.create_checkpoint(task_id='T1', run_id='R1', stage='collect_pending')
    snap = build_snapshot(
        repository_id='1296269', requested_repository='octocat/Hello-World',
        resolved_repository='octocat/Hello-World', requested_ref='master',
        commit_sha='{'a'*40}', root_tree_sha='{'b'*40}',
        tree_query_ref='{'b'*40}', completeness_status='COMPLETE',
        tree_entries=[{{'path':'README','type':'blob','sha':'{'3'*40}','size':12,'mode_kind':'file'}}],
        collected_at='2026-11-04T20:00:00+0800', evidence_refs=['ev'])
    r = ingest_snapshot(ks, snap, operation_id=OP)
    assert r['ok'], r
    print('ASSET_COMMITTED', flush=True)
    # 此处模拟"checkpoint 尚未更新时进程死亡"
    os.kill(os.getpid(), signal.SIGKILL)
"""
        env = dict(os.environ); env["PYTHONPATH"] = PP
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                             text=True, env=env)
        out, _ = p.communicate(timeout=60)
        return out, p.returncode

    def test_t17_reconcile_after_asset_committed(self):
        out, rc = self._run_collect_then_die()
        self.assertIn("ASSET_COMMITTED", out, "资产必须真的先提交")
        self.assertLess(rc, 0, "进程必须被信号杀死")

        check = run_py(f"""
import sys, json
sys.path.insert(0, {str(ST)!r})
sys.path.insert(0, {str(RT)!r})
from knowledge_store import KnowledgeStore
from checkpoint_store import CheckpointStore
import asset_checkpoint_coordinator as CO
st, err = CO.open_store({self.cp!r}, create=False)
if st is None:
    print(json.dumps({{'cps': None, 'err': err}}))
else:
    with st as cps, KnowledgeStore({self.kb!r}, create=False) as ks:
        rec = CO.reconcile(ks, cps, task_id='T1', run_id='R1',
                           operation_id='OP-COL-T17')
        n_assets = ks.conn.execute('SELECT count(*) AS n FROM assets').fetchone()['n']
        n_ops = ks.conn.execute('SELECT count(*) AS n FROM operation_log').fetchone()['n']
        print(json.dumps({{'rec': rec, 'assets': n_assets, 'ops': n_ops}}))
""")
        self.assertEqual(check.returncode, 0, check.stderr)
        d = json.loads(check.stdout.strip().splitlines()[-1])
        self.assertEqual(d["rec"]["state"], CO.RECONCILED,
                         f"资产已提交、checkpoint 缺失 → 必须 RECONCILED: {d['rec']}")
        self.assertFalse(d["rec"]["auto_retry"], "不得自动重做（资产已存在）")
        self.assertEqual(d["assets"], 1, "资产只应有一条")
        self.assertEqual(d["ops"], 1, "operation 只应有一条")

    def test_t17_reconcile_then_complete_no_duplicate(self):
        self._run_collect_then_die()
        code = f"""
import sys, json
sys.path.insert(0, {str(COLL)!r}); sys.path.insert(0, {str(ST)!r}); sys.path.insert(0, {str(RT)!r})
from knowledge_store import KnowledgeStore
from checkpoint_store import CheckpointStore
import asset_checkpoint_coordinator as CO
from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot

OP = 'OP-COL-T17'
with CheckpointStore({self.cp!r}) as cps, KnowledgeStore({self.kb!r}) as ks:
    rec = CO.reconcile(ks, cps, task_id='T1', run_id='R1', operation_id=OP)
    w = CO.write_after_asset_commit(cps, task_id='T1', run_id='R1',
                                    op_record=rec['committed'])
    rec2 = CO.reconcile(ks, cps, task_id='T1', run_id='R1', operation_id=OP)
    # 再跑一次采集（幂等）
    snap = build_snapshot(
        repository_id='1296269', requested_repository='octocat/Hello-World',
        resolved_repository='octocat/Hello-World', requested_ref='master',
        commit_sha='{'a'*40}', root_tree_sha='{'b'*40}',
        tree_query_ref='{'b'*40}', completeness_status='COMPLETE',
        tree_entries=[{{'path':'README','type':'blob','sha':'{'3'*40}','size':12,'mode_kind':'file'}}],
        collected_at='2026-11-04T21:00:00+0800', evidence_refs=['ev'])
    again = ingest_snapshot(ks, snap, operation_id=OP)
    n_assets = ks.conn.execute('SELECT count(*) AS n FROM assets').fetchone()['n']
    n_ops = ks.conn.execute('SELECT count(*) AS n FROM operation_log').fetchone()['n']
    ptr = ks.current_pointer(snap.logical_identity(), '1296269')
    print(json.dumps({{'rec': rec['state'], 'write': w.get('ok'),
                       'rec2': rec2['state'], 'again': again['state'],
                       'assets': n_assets, 'ops': n_ops,
                       'pointer_version': ptr.get('pointer_version')}}))
"""
        r = run_py(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(d["rec"], CO.RECONCILED)
        self.assertTrue(d["write"])
        self.assertEqual(d["rec2"], CO.NOTHING_TO_DO, "补齐后应无动作")
        self.assertEqual(d["again"], "IDEMPOTENT_ALREADY_PRESENT",
                         "重采不得重复入库")
        self.assertEqual(d["assets"], 1)
        self.assertEqual(d["ops"], 1)
        self.assertEqual(d["pointer_version"], 1, "不得重复推进指针")


class TestKillDuringIngest(unittest.TestCase):
    """入库事务中途被杀 —— 不得留下半提交。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p1c_kill_"))
        self.kb = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_kill_inside_asset_transaction(self):
        code = f"""
import sys, os, signal, time
sys.path.insert(0, {str(ST)!r})
from knowledge_store import KnowledgeStore
with KnowledgeStore({self.kb!r}) as ks:
    ks.append_asset_and_advance.__self__  # 触到 API，确保库已建
    ks.conn.execute('BEGIN IMMEDIATE')
    ks.conn.execute(
        "INSERT INTO assets(asset_id, asset_type, logical_identity, repository_id,"
        " subject_id, asset_version, content_hash, payload_json, commit_sha,"
        " root_tree_sha, tree_query_ref, operation_id, created_at) VALUES"
        " ('SL-A-HALFCOL','repository_snapshot','LI-HALF','1296269',NULL,1,"
        "'deadbeef','{{}}',NULL,NULL,NULL,NULL,'now')")
    print('HALF_INSERTED', flush=True)
    time.sleep(30)
"""
        env = dict(os.environ); env["PYTHONPATH"] = PP
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                             text=True, env=env)
        time.sleep(1.3)
        p.send_signal(signal.SIGKILL)
        out, _ = p.communicate(timeout=30)
        self.assertIn("HALF_INSERTED", out)

        chk = run_py(f"""
import sys, json
sys.path.insert(0, {str(ST)!r})
from knowledge_store import KnowledgeStore
with KnowledgeStore({self.kb!r}, create=False) as ks:
    n = ks.conn.execute("SELECT count(*) AS n FROM assets WHERE asset_id='SL-A-HALFCOL'").fetchone()['n']
    print(json.dumps({{'half': n}}))
""")
        d = json.loads(chk.stdout.strip().splitlines()[-1])
        self.assertEqual(d["half"], 0, "未提交的采集资产不得可见")


if __name__ == "__main__":
    unittest.main(verbosity=2)
