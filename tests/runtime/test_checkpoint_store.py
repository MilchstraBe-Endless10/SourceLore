#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""checkpoint 存储核心契约测试（单进程语义 + 边界）。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2] / "src" / "runtime"
sys.path.insert(0, str(RUNTIME))
from checkpoint_store import CheckpointStore, SCHEMA_VERSION
import execution_result as ER


class TestBasics(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="slck_unit_"))
        self.db = str(self.tmp / "cp.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_schema_version_present_and_valid(self):
        with CheckpointStore(self.db) as st:
            self.assertEqual(st.schema_version(), SCHEMA_VERSION)

    def test_create_and_read(self):
        with CheckpointStore(self.db) as st:
            r = st.create_checkpoint(task_id="T", run_id="R", stage="s0")
            self.assertTrue(r["ok"])
            self.assertEqual(r["checkpoint_version"], 1)
            got = st.read_checkpoint(task_id="T", run_id="R")
            self.assertTrue(got["ok"])
            self.assertEqual(got["checkpoint"]["stage"], "s0")

    def test_duplicate_create_is_conflict(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s0")
            r2 = st.create_checkpoint(task_id="T", run_id="R", stage="s1")
            self.assertFalse(r2["ok"])
            self.assertEqual(r2["error"], "CONFLICT")

    def test_task_id_and_run_id_not_interchangeable(self):
        """task_id/run_id 互换后必须查到不同的（不存在的）记录。"""
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="A", run_id="B", stage="s0")
            r = st.read_checkpoint(task_id="B", run_id="A")
            self.assertFalse(r["ok"])
            self.assertEqual(r["error"], "NOT_FOUND")

    def test_version_monotonic(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s0")
            v = 1
            for i in range(4):
                r = st.update_checkpoint_if_version(task_id="T", run_id="R",
                                                    expected_version=v, stage=f"s{i+1}")
                self.assertTrue(r["ok"])
                self.assertEqual(r["checkpoint_version"], v + 1)
                v = r["checkpoint_version"]

    def test_stale_version_cannot_overwrite(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s0")
            st.update_checkpoint_if_version(task_id="T", run_id="R", expected_version=1, stage="s1")
            r = st.update_checkpoint_if_version(task_id="T", run_id="R", expected_version=1, stage="s2")
            self.assertFalse(r["ok"])
            self.assertEqual(r["error"], "CONFLICT")
            self.assertEqual(r["current_version"], 2)
            # 内容未被子虚乌有的覆盖
            got = st.read_checkpoint(task_id="T", run_id="R")["checkpoint"]
            self.assertEqual(got["stage"], "s1")

    def test_missing_record_is_not_found(self):
        with CheckpointStore(self.db) as st:
            r = st.read_checkpoint(task_id="X", run_id="Y")
            self.assertEqual(r["error"], "NOT_FOUND")

    def test_update_missing_is_not_found(self):
        with CheckpointStore(self.db) as st:
            r = st.update_checkpoint_if_version(task_id="X", run_id="Y", expected_version=1)
            self.assertEqual(r["error"], "NOT_FOUND")

    def test_sensitive_fields_rejected(self):
        with CheckpointStore(self.db) as st:
            with self.assertRaises(PermissionError):
                st.create_checkpoint(task_id="T", run_id="R", stage="s0",
                                     payload={"api_key": "should-not-store"})

    def test_empty_ids_rejected(self):
        with CheckpointStore(self.db) as st:
            r = st.create_checkpoint(task_id="", run_id="R", stage="s0")
            self.assertFalse(r["ok"])
            self.assertEqual(r["error"], "PERMISSION_DENIED")

    def test_record_attempt_increments_version(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s0")
            r = st.record_attempt(task_id="T", run_id="R", state=ER.SUCCESS, exit_code=0)
            self.assertTrue(r["ok"])
            self.assertEqual(r["attempt_no"], 1)
            self.assertEqual(r["checkpoint_version"], 2)

    def test_record_result_success_has_digest(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s0")
            r = st.record_result(task_id="T", run_id="R", state=ER.SUCCESS,
                                 exit_code=0, result_payload={"k": "v"})
            self.assertTrue(r["ok"])
            self.assertIsNotNone(r["result_digest"])
            got = st.read_checkpoint(task_id="T", run_id="R")["checkpoint"]
            self.assertEqual(got["status"], ER.SUCCESS)

    def test_inspect_lists_attempts(self):
        with CheckpointStore(self.db) as st:
            st.create_checkpoint(task_id="T", run_id="R", stage="s0")
            st.record_attempt(task_id="T", run_id="R", state=ER.FAILED, exit_code=5)
            st.record_attempt(task_id="T", run_id="R", state=ER.SUCCESS, exit_code=0)
            r = st.inspect_checkpoint(task_id="T", run_id="R")
            self.assertEqual(len(r["attempts"]), 2)
            self.assertEqual([a["attempt_no"] for a in r["attempts"]], [1, 2])

    def test_resume_from_missing_record_does_not_invent(self):
        with CheckpointStore(self.db) as st:
            r = st.resume_checkpoint(task_id="X", run_id="Y")
            self.assertFalse(r["ok"])
            self.assertFalse(r["resumable"])
            self.assertEqual(r["error"], "NOT_FOUND")

    def test_db_rejects_knowledge_namespace(self):
        bad = Path.cwd() / "docs" / "fusion" / "should_not.db"
        with self.assertRaises(PermissionError):
            CheckpointStore(str(bad))
        self.assertFalse(bad.exists(), "不得创建文件")

    def test_wal_mode_enabled(self):
        with CheckpointStore(self.db) as st:
            mode = st.conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")

    def test_schema_mismatch_rejected(self):
        with CheckpointStore(self.db) as st:
            st.conn.execute("UPDATE meta SET v='99' WHERE k='schema_version'")
        with self.assertRaises(RuntimeError):
            CheckpointStore(self.db)


if __name__ == "__main__":
    unittest.main(verbosity=2)
