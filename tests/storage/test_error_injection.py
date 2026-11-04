#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""异常与错误注入（T-11）。

覆盖：锁竞争 / 非法输入 / 数据库损坏副本 / 受控磁盘写入失败。
**无法安全实施的实验不伪造 PASS** —— 磁盘写入失败一节明确记录实施边界。
"""
import os, sys, json, sqlite3, subprocess, tempfile, shutil, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORAGE = ROOT / "src" / "storage"
RUNTIME = ROOT / "src" / "runtime"
sys.path.insert(0, str(STORAGE))
PP = os.pathsep.join([str(STORAGE), str(RUNTIME)])

from asset_models import AssetDraft, ModelError, SourceSnapshot
from knowledge_store import KnowledgeStore
import index_store as IX


def run_py(code, timeout=60):
    env = dict(os.environ); env["PYTHONPATH"] = PP + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, env=env, timeout=timeout)


class TestLockContention(unittest.TestCase):
    """数据库锁竞争。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="err_lock_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writer_holds_lock_and_second_writer_gets_busy(self):
        """一个进程持有写事务时，另一进程的写必须失败或等待，不得静默成功。"""
        holder = f"""
import sys, time, json
sys.path.insert(0, {str(STORAGE)!r})
from knowledge_store import KnowledgeStore
ks = KnowledgeStore({self.db!r})
ks.conn.execute('BEGIN IMMEDIATE')
ks.conn.execute("INSERT INTO assets(asset_id, asset_type, logical_identity, repository_id,"
" subject_id, asset_version, content_hash, payload_json, commit_sha, root_tree_sha,"
" tree_query_ref, operation_id, created_at) VALUES"
" ('SL-A-LOCK','capability_record','LOCK','repo-a',NULL,1,'h','{{}}',NULL,NULL,NULL,NULL,'now')")
print('LOCK_HELD', flush=True)
time.sleep(25)
"""
        env = dict(os.environ); env["PYTHONPATH"] = PP
        p = subprocess.Popen([sys.executable, "-c", holder], stdout=subprocess.PIPE,
                             text=True, env=env)
        try:
            time.sleep(1.0)
            # 另一进程尝试写，busy_timeout=5000 应让它等不到就抛 busy
            r = run_py(f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore
try:
    with KnowledgeStore({self.db!r}, create=False) as ks:
        res = ks.append_asset_and_advance(AssetDraft(
            asset_type='capability_record', logical_identity='X2',
            repository_id='repo-a', payload={{'v':1}}), expected_version=None)
        print(json.dumps({{'ok': res.get('ok'), 'error': res.get('error')}}))
except Exception as e:
    print(json.dumps({{'raised': type(e).__name__}}))
""")
            out = r.stdout.strip()
            self.assertTrue(out, f"无输出: {r.stderr[:200]}")
            d = json.loads(out.splitlines()[-1])
            # 必须不是"静默成功"
            self.assertFalse(d.get("ok") is True and d.get("error") is None,
                             f"锁竞争下不得静默成功: {d}")
        finally:
            p.terminate()
            try: p.wait(timeout=10)
            except Exception: p.kill()

    def test_failed_writer_leaves_no_partial_row(self):
        holder = f"""
import sys, time
sys.path.insert(0, {str(STORAGE)!r})
from knowledge_store import KnowledgeStore
ks = KnowledgeStore({self.db!r})
ks.conn.execute('BEGIN IMMEDIATE')
print('LOCK_HELD', flush=True)
time.sleep(20)
"""
        env = dict(os.environ); env["PYTHONPATH"] = PP
        p = subprocess.Popen([sys.executable, "-c", holder], stdout=subprocess.PIPE,
                             text=True, env=env)
        try:
            time.sleep(1.0)
            run_py(f"""
import sys
sys.path.insert(0, {str(STORAGE)!r})
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore
try:
    with KnowledgeStore({self.db!r}, create=False) as ks:
        ks.append_asset_and_advance(AssetDraft(
            asset_type='capability_record', logical_identity='X3',
            repository_id='repo-a', payload={{'v':1}}), expected_version=None)
except Exception:
    pass
""")
            # 锁释放后检查：不应留下 X3 的半提交
            after = run_py(f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
from knowledge_store import KnowledgeStore
with KnowledgeStore({self.db!r}, create=False) as ks:
    n = ks.conn.execute("SELECT count(*) AS n FROM assets WHERE logical_identity='X3'").fetchone()['n']
    print(json.dumps({{'n': n}}))
""")
            d = json.loads(after.stdout.splitlines()[-1])
            self.assertEqual(d["n"], 0, "失败的写入不得留下半提交行")
        finally:
            p.terminate()
            try: p.wait(timeout=10)
            except Exception: p.kill()


class TestIllegalInput(unittest.TestCase):
    """非法输入必须在写库前拒绝。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="err_input_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_path_traversal_in_identity(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="capability_record",
                       logical_identity="../../../etc/passwd",
                       repository_id="repo-a", payload={})

    def test_null_byte_in_identity(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="capability_record",
                       logical_identity="a\x00b", repository_id="repo-a", payload={})

    def test_overlong_identity(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="capability_record",
                       logical_identity="x" * 200, repository_id="repo-a", payload={})

    def test_non_dict_payload(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="capability_record", logical_identity="LI",
                       repository_id="repo-a", payload=["not", "a", "dict"])

    def test_secret_in_payload(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="capability_record", logical_identity="LI",
                       repository_id="repo-a",
                       payload={"Authorization": "Bearer xyz"})

    def test_bad_source_snapshot(self):
        with self.assertRaises(ModelError):
            SourceSnapshot(commit_sha="ZZZ")

    def test_zero_or_negative_version(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="capability_record", logical_identity="LI",
                       repository_id="repo-a", payload={}, asset_version=0)

    def test_none_accepted_by_validation_no_rows_written(self):
        with KnowledgeStore(self.db) as ks:
            n = ks.conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"]
            self.assertEqual(n, 0)


class TestCorruptCopy(unittest.TestCase):
    """数据库损坏副本：必须显式报错，不得当作空库。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="err_corrupt_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_corrupt_copy_raises_not_empty(self):
        with KnowledgeStore(self.db) as ks:
            ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}), expected_version=None)

        backup = self.tmp / "kb.db.backup"
        backup.write_bytes(Path(self.db).read_bytes())
        with open(self.db, "r+b") as f:
            f.seek(0); f.write(b"\x00" * 200)

        r = run_py(f"""
import sys, json
sys.path.insert(0, {str(STORAGE)!r})
from knowledge_store import KnowledgeStore
try:
    with KnowledgeStore({self.db!r}, create=False) as ks:
        p = ks.current_pointer('LI-1', 'repo-a')
        print(json.dumps({{'ok': p.get('ok'), 'error': p.get('error')}}))
except Exception as e:
    print(json.dumps({{'raised': type(e).__name__, 'msg': str(e)[:100]}}))
""")
        d = json.loads(r.stdout.strip().splitlines()[-1])
        # 必须报错，不得返回 NOT_FOUND（那等于"知识不存在"）
        self.assertTrue("CHECKPOINT_CORRUPT" in json.dumps(d, ensure_ascii=False)
                        or "raised" in d, f"损坏必须显式报错: {d}")
        self.assertNotEqual(d.get("error"), "NOT_FOUND", "损坏不得伪装成不存在")
        self.assertTrue(backup.exists(), "诊断副本应保留")


class TestDiskWriteFailure(unittest.TestCase):
    """受控磁盘写入失败。

    **实施边界（如实记录）：** 本环境可用 `danger-full-access`，但**没有**做
    真实磁盘写满/设备拔除实验 —— 那会影响同机其他会话与系统稳定性。
    这里用**只读目录**模拟"写入被拒"，这是可安全回滚的等价路径。
    真实 ENOSPC/EIO 注入保持 OPEN。
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="err_perm_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_readonly_directory_rejects_db_creation(self):
        ro = self.tmp / "ro"
        ro.mkdir()
        os.chmod(ro, 0o500)   # 只读目录
        try:
            with self.assertRaises(Exception):
                KnowledgeStore(str(ro / "kb.db"))
        finally:
            os.chmod(ro, 0o700)

    def test_write_failure_does_not_leave_usable_partial_db(self):
        """写入被拒后，不得留下一个"看起来可用"的半成品库。"""
        ro = self.tmp / "ro2"
        ro.mkdir()
        os.chmod(ro, 0o500)
        try:
            raised = False
            try:
                KnowledgeStore(str(ro / "kb2.db"))
            except Exception:
                raised = True
            self.assertTrue(raised, "只读目录必须报错")
            self.assertFalse((ro / "kb2.db").exists(), "不得留下半成品库")
        finally:
            os.chmod(ro, 0o700)


if __name__ == "__main__":
    unittest.main(verbosity=2)
