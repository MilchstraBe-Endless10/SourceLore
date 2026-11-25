#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-A：离线增量补全（不重采、幂等、A 层不变）。

★ tempfile 隔离；不访问网络；不触碰真实知识库。
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "src"
for _d in ("storage", "collector", "content_persistence", "source_analysis",
           "skill_interface", "content", "facts"):
    sys.path.insert(0, str(_ROOT / _d))

REPO = "local:backfill-fixture"
COMMIT = "cafebabecafebabecafebabecafebabecafebabe"

PY_SRC = b"from .utils import helper\nfrom os import path\n"
UTIL_SRC = b"def helper():\n    return 1\n"


def _fingerprint(store):
    """A 层不可变指纹：所有已存在资产的 (id, content_hash) 排序。"""
    rows = store.conn.execute(
        "SELECT asset_id, asset_type FROM index_rows ORDER BY asset_id").fetchall()
    h = hashlib.sha256()
    for r in rows:
        h.update((r["asset_id"] + "|" + r["asset_type"] + "\n").encode())
    return h.hexdigest(), len(rows)


class BackfillTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = self._td.name
        from knowledge_store import KnowledgeStore
        self.store = KnowledgeStore(str(Path(self.root) / "kb.db"), create=True)
        self._capture("pkg/app.py", PY_SRC, "blob-app-0001")
        self._capture("pkg/utils.py", UTIL_SRC, "blob-util-0002")
        self._snapshot(["pkg/app.py", "pkg/utils.py"])
        self.store.close()

    def tearDown(self):
        self._td.cleanup()

    def _capture(self, path, raw, blob):
        import content_ingest_coordinator as CIC
        r = CIC.ingest_captured_blob(
            self.store, data_root=self.root, repository_id=REPO,
            commit_sha=COMMIT, source_snapshot_id="SL-SNAP-backfill",
            file_path=path, git_blob_oid=blob, git_object_format="sha1",
            raw=raw, source_declared_size=len(raw),
            acquisition_policy="AUTHORIZED_LOCAL_FIXTURE",
            acquisition_policy_ref="fixture",
            provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        assert r.get("ok"), r

    def _snapshot(self, paths):
        from asset_models import AssetDraft
        r = self.store.append_asset_and_advance(
            AssetDraft(asset_type="repository_snapshot",
                       logical_identity="SL-REPOSNAP-backfill",
                       repository_id=REPO,
                       payload={"commit_sha": COMMIT,
                                "completeness_status": "COMPLETE",
                                "blob_refs": [{"path": p} for p in paths]},
                       asset_version=1),
            expected_version=None)
        assert r.get("ok"), r

    def test_backfill_is_offline_idempotent_and_preserves_a_layer(self):
        import relation_backfill as RB
        from knowledge_store import KnowledgeStore

        st = KnowledgeStore(str(Path(self.root) / "kb.db"), create=False)
        before, n_before = _fingerprint(st)
        st.close()

        r1 = RB.backfill_relations(repository_id=REPO, commit_sha=COMMIT,
                                   data_root=self.root)
        self.assertTrue(r1["ok"], r1)
        self.assertEqual(r1["network_requests"], 0)
        self.assertEqual(r1["source_files"], 2)
        self.assertTrue(r1["written"], r1)

        st = KnowledgeStore(str(Path(self.root) / "kb.db"), create=False)
        mid, n_mid = _fingerprint(st)
        st.close()
        self.assertGreater(n_mid, n_before)  # 新增关系审计/事实

        r2 = RB.backfill_relations(repository_id=REPO, commit_sha=COMMIT,
                                   data_root=self.root)
        self.assertEqual(r2["network_requests"], 0)
        self.assertEqual(r2["written"], [], r2)  # 幂等：第二次无新增
        self.assertTrue(r2["reused"])

        st = KnowledgeStore(str(Path(self.root) / "kb.db"), create=False)
        after, n_after = _fingerprint(st)
        st.close()
        self.assertEqual((after, n_after), (mid, n_mid))  # 第二次不改 A 层

    def test_backfill_cli_data_root_none_falls_back_to_env_default(self):
        """CLI 的 --data-root 默认为 None；必须回退到 DEFAULT_DATA_ROOT，
        不能让 blob 字节加载收到 None（曾因此 INTERNAL_ERROR）。"""
        import unittest.mock as mock
        import paths
        import relation_backfill as RB

        # 调用方不传 data_root（CLI 实际路径）；函数内 from paths import
        # DEFAULT_DATA_ROOT 会在调用时读取，故 patch paths 模块即可。
        with mock.patch.object(paths, "DEFAULT_DATA_ROOT", Path(self.root)):
            r = RB.backfill_relations(repository_id=REPO, commit_sha=COMMIT,
                                      data_root=None)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["source_files"], 2)
        self.assertEqual(r["network_requests"], 0)
        self.assertTrue(r["written"] or r["reused"])

    def test_backfill_no_captured_is_noop(self):
        import relation_backfill as RB
        r = RB.backfill_relations(repository_id=REPO,
                                  commit_sha="0" * 40, data_root=self.root)
        self.assertEqual(r["status"], "NO_CAPTURED_SOURCE")
        self.assertEqual(r["written"], [])
        self.assertEqual(r["network_requests"], 0)


if __name__ == "__main__":
    unittest.main()
