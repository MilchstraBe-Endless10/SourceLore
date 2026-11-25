#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-B 样本 C：固定 Commit 正文/快照隔离回归（真实 SQLite + blob）。

复现场景：同一仓库两个 Commit 含同名文件 app.py 不同正文，最新 snapshot 是 B。
修复后按 commit 读取必须拿到各自版本正文；指定不存在 Commit 严禁回退；
默认读取走 current_view。此文件同时是 §2 修复的可执行证据。
"""
import sys, tempfile, unittest, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/views", "src/storage", "src/skill_interface", "src/trust",
          "src/content"):
    sp = str(ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import knowledge_store as KS            # noqa: E402
from asset_models import AssetDraft     # noqa: E402
import blob_content_store as BCS        # noqa: E402
import versioned_assets as VA           # noqa: E402
import repo_derive_runner as DR         # noqa: E402
import repo_miner as RM                 # noqa: E402

A = "a" * 40
B = "b" * 40
BODY_A = 'def value():\n    return "A-commit"\n'
BODY_B = 'def value():\n    return "B-commit"\n'
REPO = "p2b:fixture"


class FixedCommitIsolationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="p2bsampleC_"))
        cls.root = cls.tmp / "data"
        cls.root.mkdir(parents=True)
        cls.store = KS.KnowledgeStore(str(cls.root / "kb.db"))
        cls._add(A, BODY_A)
        cls._add(B, BODY_B)   # B 后写 → 最新 snapshot = B

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def _add(cls, commit, text):
        digest = BCS.put_bytes(data_root=str(cls.root),
                               raw=text.encode("utf-8"))["digest"]
        snap = AssetDraft(
            asset_type="repository_snapshot",
            logical_identity="SNAP-" + commit[:8], repository_id=REPO,
            payload={
                "commit_sha": commit, "completeness_status": "COMPLETE",
                "tree_entry_count": 1,
                "tree_entries": [{"path": "app.py", "type": "blob",
                                  "sha": commit[:8]}],
                "snapshot_asset_id": "SNAP-" + commit[:8],
            })
        cls.store.append_asset_and_advance(snap, expected_version=None)
        blob = AssetDraft(
            asset_type="captured_blob_content",
            logical_identity="BLOB-" + commit[:8], repository_id=REPO,
            payload={
                "file_path": "app.py", "normalized_path": "app.py",
                "content_sha256": digest, "commit_sha": commit,
                "source_snapshot_id": "SNAP-" + commit[:8],
                "git_blob_oid": commit[:12],
                "provenance_level": "AUTHORIZED_REMOTE_SOURCE",
                "copy_permitted": True, "distribution_allowed": False,
            })
        cls.store.append_asset_and_advance(blob, expected_version=None)

    def test_blob_text_pinned_to_commit_a(self):
        texts, meta = RM._blob_texts(self.store, REPO, str(self.root), A)
        self.assertIn("A-commit", texts.get("app.py", ""))
        self.assertNotIn("B-commit", texts.get("app.py", ""))

    def test_blob_text_pinned_to_commit_b(self):
        texts, meta = RM._blob_texts(self.store, REPO, str(self.root), B)
        self.assertIn("B-commit", texts.get("app.py", ""))
        self.assertNotIn("A-commit", texts.get("app.py", ""))

    def test_snapshot_pinned_to_commit_a(self):
        ex = DR._load_assets_ex(self.store, REPO, A)
        self.assertTrue(ex.get("ok"), ex)
        self.assertEqual(ex["commit_sha"], A)
        self.assertEqual(ex["snapshot"]["commit_sha"], A)
        self.assertEqual(ex["selection"]["selection"], VA.SELECT_PINNED)

    def test_unknown_commit_no_fallback(self):
        ex = DR._load_assets_ex(self.store, REPO, "f" * 40)
        self.assertFalse(ex.get("ok"), "不存在 Commit 不得回退到新版本")
        self.assertEqual(ex.get("reason"), "COMMIT_NOT_FOUND")

    def test_default_selection_is_current_view(self):
        ex = DR._load_assets_ex(self.store, REPO, None)
        self.assertTrue(ex.get("ok"), ex)
        self.assertEqual(ex["selection"]["selection"], VA.SELECT_CURRENT_VIEW)

    def test_captured_blobs_fingerprint_differs(self):
        ta, _ = RM._blob_texts(self.store, REPO, str(self.root), A)
        tb, _ = RM._blob_texts(self.store, REPO, str(self.root), B)
        self.assertNotEqual(ta["app.py"], tb["app.py"],
                            "同名文件不同 Commit 正文必须不同")


if __name__ == "__main__":
    unittest.main(verbosity=2)
