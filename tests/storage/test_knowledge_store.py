#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识存储核心契约测试（T-1 / T-2 / T-6 / T-7 / T-8 / T-9）。"""
import sys, tempfile, shutil, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "storage"))

from asset_models import AssetDraft, ModelError, SourceSnapshot
from knowledge_store import KnowledgeStore, POINTER_DANGLING, POINTER_OK
import index_store as IX


class TestImmutability(unittest.TestCase):
    """T-1：A 层不可原地覆盖。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb_imm_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_update_on_assets_is_blocked_by_trigger(self):
        with KnowledgeStore(self.db) as ks:
            r = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"k": "v1"}), expected_version=None)
            self.assertTrue(r["ok"])
            # 直接 UPDATE 必须被触发器拦住
            with self.assertRaises(Exception) as ctx:
                ks.conn.execute("UPDATE assets SET payload_json='{\"k\":\"hacked\"}' "
                                "WHERE asset_id=?", (r["asset_id"],))
            self.assertIn("A_LAYER_IMMUTABLE", str(ctx.exception))

    def test_delete_on_assets_is_blocked(self):
        with KnowledgeStore(self.db) as ks:
            r = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"k": "v1"}), expected_version=None)
            with self.assertRaises(Exception) as ctx:
                ks.conn.execute("DELETE FROM assets WHERE asset_id=?", (r["asset_id"],))
            self.assertIn("A_LAYER_IMMUTABLE", str(ctx.exception))

    def test_same_version_different_content_is_conflict(self):
        with KnowledgeStore(self.db) as ks:
            ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"k": "v1"}, asset_version=1),
                expected_version=None)
            r2 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"k": "DIFFERENT"}, asset_version=1),
                expected_version=1)
            self.assertFalse(r2["ok"])
            self.assertEqual(r2["error"], "CONFLICT")

    def test_same_version_same_content_is_idempotent(self):
        with KnowledgeStore(self.db) as ks:
            ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"k": "v1"}), expected_version=None)
            r2 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"k": "v1"}), expected_version=None)
            self.assertTrue(r2["ok"])
            self.assertTrue(r2.get("idempotent"))


class TestVersionProgression(unittest.TestCase):
    """T-2：正常版本推进，旧版仍可读。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb_ver_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_advance_and_history_preserved(self):
        with KnowledgeStore(self.db) as ks:
            a1 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}, asset_version=1),
                expected_version=None)
            self.assertTrue(a1["ok"])
            self.assertEqual(ks.current_pointer("LI-1", "repo-a")["current_asset_id"], a1["asset_id"])

            a2 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 2}, asset_version=2),
                expected_version=1)
            self.assertTrue(a2["ok"])
            ptr = ks.current_pointer("LI-1", "repo-a")
            self.assertEqual(ptr["current_asset_id"], a2["asset_id"])
            self.assertEqual(ptr["pointer_version"], 2)
            self.assertEqual(ptr["last_known_good"], a1["asset_id"])

            # A1 仍然可读
            g = ks.get_asset(a1["asset_id"])
            self.assertTrue(g["ok"])
            self.assertEqual(g["asset"]["payload"]["v"], 1)

            hist = ks.history("LI-1")
            self.assertEqual([v["asset_version"] for v in hist["versions"]], [1, 2])

    def test_stale_expected_version_conflicts(self):
        with KnowledgeStore(self.db) as ks:
            ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}), expected_version=None)
            ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 2}, asset_version=2),
                expected_version=1)
            r = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 3}, asset_version=3),
                expected_version=1)
            self.assertEqual(r["error"], "CONFLICT")
            self.assertEqual(r["current_version"], 2)

    def test_pointer_version_and_asset_version_are_distinct(self):
        """checkpoint_version 与 asset_version 不可互换 —— 这里验证 asset 侧。"""
        with KnowledgeStore(self.db) as ks:
            a1 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}, asset_version=1),
                expected_version=None)
            ptr = ks.current_pointer("LI-1", "repo-a")
            self.assertEqual(ptr["pointer_version"], 1)
            asset = ks.get_asset(a1["asset_id"])["asset"]
            self.assertEqual(asset["asset_version"], 1)
            # 语义不同：asset_version 由内容演进决定，pointer_version 由 CAS 次数决定
            a2 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 2}, asset_version=5),
                expected_version=1)
            self.assertTrue(a2["ok"])
            self.assertEqual(a2["pointer_version"], 2)   # 指针 +1
            self.assertEqual(ks.get_asset(a2["asset_id"])["asset"]["asset_version"], 5)


class TestPostcondition(unittest.TestCase):
    """T-6：校验失败必须整体拒绝，不得先提交再检查。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb_pc_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_failing_postcondition_rolls_back_everything(self):
        def doomed(cursor, ctx):
            raise RuntimeError("postcondition 拒绝发布")

        with KnowledgeStore(self.db) as ks:
            r = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}),
                expected_version=None, postcondition=doomed)
            self.assertFalse(r["ok"])
            # A 层没有留下资产
            n = ks.conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"]
            self.assertEqual(n, 0)
            # B 层没有指针
            p = ks.current_pointer("LI-1", "repo-a")
            self.assertEqual(p["error"], "NOT_FOUND")
            # C 层没有索引残留
            n2 = ks.conn.execute("SELECT count(*) AS n FROM index_rows").fetchone()["n"]
            self.assertEqual(n2, 0)

    def test_passing_postcondition_commits(self):
        seen = {}

        def ok(cursor, ctx):
            seen.update(ctx)

        with KnowledgeStore(self.db) as ks:
            r = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}),
                expected_version=None, postcondition=ok)
            self.assertTrue(r["ok"])
            self.assertEqual(seen["pointer_version"], 1)

    def test_invalid_payload_rejected_before_write(self):
        with KnowledgeStore(self.db) as ks:
            with self.assertRaises(ModelError):
                AssetDraft(asset_type="capability_record", logical_identity="LI-1",
                           repository_id="repo-a", payload={"api_key": "x"})
            n = ks.conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"]
            self.assertEqual(n, 0)

    def test_illegal_asset_type_rejected(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="not_a_type", logical_identity="LI-1",
                       repository_id="repo-a", payload={})

    def test_path_injection_in_ids_rejected(self):
        with self.assertRaises(ModelError):
            AssetDraft(asset_type="capability_record",
                       logical_identity="../../etc/passwd",
                       repository_id="repo-a", payload={})


class TestDanglingPointer(unittest.TestCase):
    """T-7：损坏指针不得伪装成空结果，且保留 last_known_good。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb_dang_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dangling_pointer_is_explicit(self):
        with KnowledgeStore(self.db) as ks:
            a1 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}), expected_version=None)
            a2 = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 2}, asset_version=2),
                expected_version=1)
            # 手工制造 dangling：把指针指向一个不存在的资产
            ks.conn.execute("UPDATE current_view SET current_asset_id=? "
                            "WHERE logical_identity=?", ("SL-A-DOESNOTEXIST", "LI-1"))
            p = ks.current_pointer("LI-1", "repo-a")
            self.assertFalse(p["ok"])
            self.assertEqual(p["state"], POINTER_DANGLING)
            # 不能伪装成 NOT_FOUND（那是"没有这条知识"的意思）
            self.assertNotEqual(p.get("error"), "NOT_FOUND")
            # 诊断信息保留
            self.assertEqual(p["last_known_good"], a1["asset_id"])
            self.assertEqual(p["pointer_version"], 2)

    def test_missing_pointer_is_not_found(self):
        with KnowledgeStore(self.db) as ks:
            p = ks.current_pointer("NOPE", "repo-a")
            self.assertEqual(p["error"], "NOT_FOUND")

    def test_tampered_asset_detected_on_read(self):
        with KnowledgeStore(self.db) as ks:
            r = ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}), expected_version=None)
            # 绕过触发器直接改底层（模拟磁盘损坏）
            ks.conn.execute("DROP TRIGGER assets_no_update")
            ks.conn.execute("UPDATE assets SET payload_json='{\"v\":999}' WHERE asset_id=?",
                            (r["asset_id"],))
            g = ks.get_asset(r["asset_id"], verify=True)
            self.assertFalse(g["ok"])
            self.assertEqual(g["error"], "CHECKPOINT_CORRUPT")


class TestIndexRebuild(unittest.TestCase):
    """T-8：删索引重建，查询一致，A/B 不变。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb_idx_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rebuild_preserves_a_b(self):
        with KnowledgeStore(self.db) as ks:
            for i in range(3):
                ks.append_asset_and_advance(AssetDraft(
                    asset_type="capability_record", logical_identity=f"LI-{i}",
                    repository_id="repo-a" if i < 2 else "repo-b",
                    payload={"i": i}), expected_version=None)
            before = IX._ab_fingerprint(ks)
            cnt_before = IX.query(ks, repository_id="repo-a")["count"]

            rb = IX.rebuild_index(ks)
            self.assertTrue(rb["ok"])
            self.assertEqual(rb["indexed"], 3)
            self.assertTrue(rb["a_b_unchanged"])

            after = IX._ab_fingerprint(ks)
            self.assertEqual(before, after, "重建不得修改 A/B")
            self.assertEqual(IX.query(ks, repository_id="repo-a")["count"], cnt_before)

    def test_index_missing_is_not_empty_result(self):
        with KnowledgeStore(self.db) as ks:
            ks.conn.execute("DROP TABLE index_rows")
            r = IX.query(ks, repository_id="repo-a")
            self.assertFalse(r["ok"])
            self.assertEqual(r["error"], IX.INDEX_MISSING,
                             "索引缺失必须显式报 INDEX_MISSING，不能给空列表")

    def test_query_results_carry_provenance(self):
        with KnowledgeStore(self.db) as ks:
            ks.append_asset_and_advance(AssetDraft(
                asset_type="capability_record", logical_identity="LI-1",
                repository_id="repo-a", payload={"v": 1}), expected_version=None)
            r = IX.query(ks, repository_id="repo-a")
            self.assertTrue(r["ok"])
            row = r["results"][0]
            for f in ("asset_id", "asset_version", "is_current", "authority"):
                self.assertIn(f, row)


class TestCrossRepoIdentity(unittest.TestCase):
    """T-9：跨仓库身份不自动合并。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb_xrepo_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_binding_requires_evidence(self):
        with KnowledgeStore(self.db) as ks:
            r = ks.bind_repo(subject_id="SUBJ-1", repository_id="repo-a", evidence_ref="")
            self.assertFalse(r["ok"])
            self.assertEqual(r["error"], "PERMISSION_DENIED")

    def test_same_name_in_two_repos_not_merged(self):
        with KnowledgeStore(self.db) as ks:
            ks.append_asset_and_advance(AssetDraft(
                asset_type="subject_record", logical_identity="LI-SAME",
                repository_id="repo-a", payload={"name": "same"}), expected_version=None)
            ks.append_asset_and_advance(AssetDraft(
                asset_type="subject_record", logical_identity="LI-SAME",
                repository_id="repo-b", payload={"name": "same"}), expected_version=None)
            # 两条独立资产
            n = ks.conn.execute("SELECT count(*) AS n FROM assets WHERE logical_identity='LI-SAME'"
                                ).fetchone()["n"]
            self.assertEqual(n, 2, "跨仓库同名不得自动合并成一条")
            # 各自指针独立
            pa = ks.current_pointer("LI-SAME", "repo-a")
            self.assertEqual(pa["repository_id"], "repo-a")

    def test_explicit_binding_recorded_with_evidence(self):
        with KnowledgeStore(self.db) as ks:
            r = ks.bind_repo(subject_id="SUBJ-1", repository_id="repo-a",
                             evidence_ref="ev-001")
            self.assertTrue(r["ok"])
            lst = ks.same_subject_across_repos("SUBJ-1")
            self.assertEqual(len(lst["bindings"]), 1)

    def test_fork_does_not_merge_identity(self):
        """两条不同 repository_id 的记录各自独立；建立关联须显式证据。"""
        with KnowledgeStore(self.db) as ks:
            ks.bind_repo(subject_id="SUBJ-UP", repository_id="repo-upstream",
                         evidence_ref="ev-up")
            ks.bind_repo(subject_id="SUBJ-FORK", repository_id="repo-fork",
                         evidence_ref="ev-fork")
            a = ks.same_subject_across_repos("SUBJ-UP")
            b = ks.same_subject_across_repos("SUBJ-FORK")
            self.assertEqual(len(a["bindings"]), 1)
            self.assertEqual(len(b["bindings"]), 1)
            self.assertNotEqual(a["subject_id"], b["subject_id"])


class TestSourceSnapshot(unittest.TestCase):
    """source_snapshot 三字段不得混用。"""

    def test_three_fields_kept_separate(self):
        snap = SourceSnapshot(commit_sha="a" * 40, root_tree_sha="b" * 40,
                              tree_query_ref="main")
        d = snap.to_dict()
        self.assertEqual(d["commit_sha"], "a" * 40)
        self.assertEqual(d["root_tree_sha"], "b" * 40)
        self.assertEqual(d["tree_query_ref"], "main")

    def test_bad_sha_rejected(self):
        with self.assertRaises(ModelError):
            SourceSnapshot(commit_sha="not-a-sha")

    def test_snapshot_persisted_and_read_back(self):
        tmp = Path(tempfile.mkdtemp(prefix="kb_ss_"))
        try:
            with KnowledgeStore(str(tmp / "kb.db")) as ks:
                r = ks.append_asset_and_advance(AssetDraft(
                    asset_type="repository_snapshot", logical_identity="LI-SNAP",
                    repository_id="repo-a", payload={"x": 1},
                    source_snapshot=SourceSnapshot(commit_sha="c" * 40,
                                                   root_tree_sha="d" * 40,
                                                   tree_query_ref="refs/heads/main")),
                    expected_version=None)
                self.assertTrue(r["ok"])
                a = ks.get_asset(r["asset_id"])["asset"]
                self.assertEqual(a["source_snapshot"]["commit_sha"], "c" * 40)
                self.assertEqual(a["source_snapshot"]["root_tree_sha"], "d" * 40)
                self.assertEqual(a["source_snapshot"]["tree_query_ref"], "refs/heads/main")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRootGuard(unittest.TestCase):
    """路径边界（仅作辅助，主防线是内部生成 ID）。"""

    def test_refuses_knowledge_namespace(self):
        bad = ROOT / "docs" / "fusion" / "should_not.db"
        with self.assertRaises(PermissionError):
            KnowledgeStore(str(bad))
        self.assertFalse(bad.exists())

    def test_asset_id_is_internally_generated(self):
        """用户输入不得决定实际资产 ID。"""
        from knowledge_store import _asset_id_for
        a = _asset_id_for("repo-a", "../../etc/passwd", 1, "x" * 64)
        self.assertTrue(a.startswith("SL-A-"))
        self.assertNotIn("..", a)
        self.assertNotIn("/", a)


if __name__ == "__main__":
    unittest.main(verbosity=2)
