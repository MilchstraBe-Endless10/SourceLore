#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1B 四个缺陷的回归测试（题面 §12 要求补录）。

每个失败都对应一个真实 bug，测试必须**在修复前失败、修复后通过**。
本文件同时作为证据：这些不是猜测的缺陷，是有明确复现路径的。
"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "storage"))
sys.path.insert(0, str(ROOT / "src" / "runtime"))

from asset_models import AssetDraft
from knowledge_store import KnowledgeStore, _asset_id_for
import index_store as IX
from checkpoint_store import CheckpointStore
import asset_checkpoint_coordinator as CO


class TestDefect1_AssetIdMissingRepository(unittest.TestCase):
    """缺陷 1：asset_id 初版不含 repository_id → 跨仓库同名撞主键、知识被静默合并。"""

    def test_asset_id_differs_by_repository(self):
        a = _asset_id_for("repo-a", "LI-SAME", 1, "hash1")
        b = _asset_id_for("repo-b", "LI-SAME", 1, "hash1")
        self.assertNotEqual(a, b, "不同仓库必须得到不同 asset_id（修复前相等）")

    def test_two_repos_same_identity_two_assets(self):
        tmp = Path(tempfile.mkdtemp(prefix="reg1_"))
        try:
            with KnowledgeStore(str(tmp / "kb.db")) as ks:
                r1 = ks.append_asset_and_advance(AssetDraft(
                    asset_type="subject_record", logical_identity="LI-SAME",
                    repository_id="repo-a", payload={"n": "same"}), expected_version=None)
                r2 = ks.append_asset_and_advance(AssetDraft(
                    asset_type="subject_record", logical_identity="LI-SAME",
                    repository_id="repo-b", payload={"n": "same"}), expected_version=None)
                self.assertTrue(r1["ok"], r1)
                self.assertTrue(r2["ok"],
                                "第二个仓库的记录不得因主键冲突而失败（修复前的症状）")
                n = ks.conn.execute(
                    "SELECT count(*) AS n FROM assets WHERE logical_identity='LI-SAME'"
                ).fetchone()["n"]
                self.assertEqual(n, 2, "两条必须独立存在")
                pa = ks.current_pointer("LI-SAME", "repo-a")
                pb = ks.current_pointer("LI-SAME", "repo-b")
                self.assertEqual(pa["current_asset_id"], r1["asset_id"])
                self.assertEqual(pb["current_asset_id"], r2["asset_id"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_current_pointer_requires_repository(self):
        """接口签名强制要求 repository_id —— 不给就无法调用。"""
        import inspect
        sig = inspect.signature(KnowledgeStore.current_pointer)
        self.assertIn("repository_id", sig.parameters,
                      "current_pointer 必须要求 repository_id（修复前只有 logical_identity）")


class TestDefect2_ReconcileIntentWithoutReceipt(unittest.TestCase):
    """缺陷 2：result_digest=None 被当成"一致" → 漏窗被判 NOTHING_TO_DO。"""

    def test_intent_only_is_reconciled_not_nothing(self):
        tmp = Path(tempfile.mkdtemp(prefix="reg2_"))
        try:
            kb, cp = str(tmp / "kb.db"), str(tmp / "cp.db")
            with CheckpointStore(cp) as cps, KnowledgeStore(kb) as ks:
                # checkpoint 只有意图，没有回执
                cps.create_checkpoint(task_id="T", run_id="R", stage="asset_pending")
                r = ks.append_asset_and_advance(AssetDraft(
                    asset_type="capability_record", logical_identity="LI-1",
                    repository_id="repo-a", payload={"v": 1}),
                    expected_version=None, operation_id="OP-R2")
                self.assertTrue(r["ok"])
                rec = CO.reconcile(ks, cps, task_id="T", run_id="R",
                                   operation_id="OP-R2")
                self.assertEqual(rec["state"], CO.RECONCILED,
                                 "有意图无回执必须 RECONCILED（修复前误判 NOTHING_TO_DO）")
                self.assertEqual(rec["reason"],
                                 "ASSET_COMMITTED_RESULT_NOT_RECORDED")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestDefect3_DigestMismatch(unittest.TestCase):
    """缺陷 3：摘要口径不一致 → 补写 checkpoint 后下次对账误报 DIGEST_MISMATCH。"""

    def test_write_then_reconcile_is_consistent(self):
        tmp = Path(tempfile.mkdtemp(prefix="reg3_"))
        try:
            kb, cp = str(tmp / "kb.db"), str(tmp / "cp.db")
            with CheckpointStore(cp) as cps, KnowledgeStore(kb) as ks:
                cps.create_checkpoint(task_id="T", run_id="R", stage="asset_pending")
                r = ks.append_asset_and_advance(AssetDraft(
                    asset_type="capability_record", logical_identity="LI-1",
                    repository_id="repo-a", payload={"v": 1}),
                    expected_version=None, operation_id="OP-R3")
                rec = CO.reconcile(ks, cps, task_id="T", run_id="R", operation_id="OP-R3")
                w = CO.write_after_asset_commit(
                    cps, task_id="T", run_id="R", op_record=rec["committed"])
                self.assertTrue(w.get("ok"), f"补写必须成功: {w}")
                rec2 = CO.reconcile(ks, cps, task_id="T", run_id="R",
                                    operation_id="OP-R3")
                self.assertEqual(rec2["state"], CO.NOTHING_TO_DO,
                                 "补写后必须一致（修复前会 DIGEST_MISMATCH）")
                self.assertNotEqual(rec2["reason"], "DIGEST_MISMATCH")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestDefect4_FtsSyntax(unittest.TestCase):
    """缺陷 4：FTS5 MATCH 中 '-' 被当列限定符 → no such column: 1。"""

    def test_hyphenated_query_does_not_crash(self):
        tmp = Path(tempfile.mkdtemp(prefix="reg4_"))
        try:
            with KnowledgeStore(str(tmp / "kb.db")) as ks:
                ks.append_asset_and_advance(AssetDraft(
                    asset_type="capability_record", logical_identity="LI-1",
                    repository_id="repo-a", payload={"n": 1}), expected_version=None)
                r = IX.query(ks, text="LI-1")
                self.assertTrue(r["ok"], f"带连字符查询不得报错: {r}")
                self.assertGreaterEqual(r["count"], 1,
                                        "必须能查到（修复前因 FTS 语法报错）")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestP1BScopeGuard(unittest.TestCase):
    """f1d 的批次作用域登记必须包含 storage。"""

    def test_f1d_allowed_prefixes_include_storage(self):
        src = (ROOT / "tools" / "fusion" / "f1d_verify.py").read_text(encoding="utf-8")
        self.assertIn('"src/storage/"', src,
                      "f1d c24 的已授权目录必须登记 storage")
        self.assertIn('"tests/storage/"', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
