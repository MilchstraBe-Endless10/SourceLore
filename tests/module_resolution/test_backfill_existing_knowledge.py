#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-A 样本 A / B：已有知识副本上的离线增量补全（自包含、零网络）。

样本 A：arch-grower 形态——Python 包相对导入 + 已有 AST Facts。
样本 B：Preact 形态——JS 相对导入 + jsconfig 路径别名 + 配置/项目事实复用。

★ 不依赖作者本机知识库；用 tempfile 从真实采集接口构造夹具；真实库只读。
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

import content_ingest_coordinator as CIC
import source_dispatch as SD
import source_fact_ingest as SFI
import relation_backfill as RB
from asset_models import AssetDraft
from knowledge_store import KnowledgeStore


def _fingerprint(store):
    rows = store.conn.execute(
        "SELECT asset_id, asset_type, logical_identity FROM index_rows ORDER BY asset_id"
    ).fetchall()
    h = hashlib.sha256()
    for r in rows:
        h.update(f"{r['asset_id']}|{r['asset_type']}|{r['logical_identity']}\n".encode())
    return h.hexdigest(), len(rows)


class BackfillExistingKnowledge(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = self._td.name
        self.store = KnowledgeStore(str(Path(self.root) / "kb.db"), create=True)

    def tearDown(self):
        self.store.close()
        self._td.cleanup()

    def _capture(self, repo, commit, path, raw, blob):
        r = CIC.ingest_captured_blob(
            self.store, data_root=self.root, repository_id=repo,
            commit_sha=commit, source_snapshot_id="SL-SNAP-fixture",
            file_path=path, git_blob_oid=blob, git_object_format="sha1",
            raw=raw, source_declared_size=len(raw),
            acquisition_policy="AUTHORIZED_LOCAL_FIXTURE",
            acquisition_policy_ref="fixture",
            provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        self.assertTrue(r.get("ok"), r)

    def _ast_fact(self, repo, commit, path, raw, blob, caid):
        """模拟已存在的 AST 事实（607 Facts 的合法复用来源）。"""
        obs = SD.parse_source(raw, repository_id=repo, commit_sha=commit,
                              file_path=path, git_blob_oid=blob,
                              content_asset_id=caid, content_sha256="sha256:" + blob,
                              provenance_level="AUTHORIZED_LOCAL_FIXTURE")
        r = SFI.ingest_source_facts(self.store, observation=obs,
                                    source_snapshot_id="SL-SNAP-fixture")
        self.assertGreater(len(r["written"]), 0, r)
        return r["written"]

    def _snapshot(self, repo, commit, paths):
        r = self.store.append_asset_and_advance(
            AssetDraft(asset_type="repository_snapshot",
                       logical_identity="SL-REPOSNAP-" + repo,
                       repository_id=repo,
                       payload={"commit_sha": commit,
                                "completeness_status": "COMPLETE",
                                "blob_refs": [{"path": p} for p in paths]},
                       asset_version=1),
            expected_version=None)
        self.assertTrue(r.get("ok"), r)

    # ---------- 样本 A：Python 包 + 已有 AST Facts ----------
    def test_sample_a_python_relations_and_existing_ast_preserved(self):
        repo, commit = "local:sample-a", "a" * 40
        app = b"from . import utils\nfrom .helpers import thing\nimport os\n"
        self._capture(repo, commit, "pkg/app.py", app, "a1" * 20)
        self._capture(repo, commit, "pkg/utils.py", b"X = 1\n", "a2" * 20)
        self._capture(repo, commit, "pkg/helpers.py", b"thing = 2\n", "a3" * 20)
        ast_written = self._ast_fact(repo, commit, "pkg/app.py", app,
                                      "a1" * 20, "SL-A-py")
        self._snapshot(repo, commit,
                       ["pkg/app.py", "pkg/utils.py", "pkg/helpers.py"])
        self.store.close()
        self.store = KnowledgeStore(str(Path(self.root) / "kb.db"), create=False)

        before, n_before = _fingerprint(self.store)
        r1 = RB.backfill_relations(repository_id=repo, commit_sha=commit,
                                   data_root=self.root)
        self.assertTrue(r1["ok"], r1)
        self.assertEqual(r1["network_requests"], 0)
        self.assertEqual(r1["source_files"], 3)
        self.assertGreater(r1["counts"]["written"], 0)
        self.assertEqual(r1["outcomes"]["error"], 0)

        # 原有 AST Facts 逐条仍存在（合法复用，未被改写）
        for w in ast_written:
            got = self.store.get_asset(w["asset_id"], verify=True)
            self.assertTrue(got.get("ok"), w)

        mid, n_mid = _fingerprint(self.store)
        r2 = RB.backfill_relations(repository_id=repo, commit_sha=commit,
                                   data_root=self.root)
        self.assertEqual(r2["written"], [], r2)
        self.assertEqual({x["fact_id"] for x in r2["reused"]},
                         {x["fact_id"] for x in r1["written"]}, r2)
        self.assertEqual(r2["network_requests"], 0)
        after, n_after = _fingerprint(self.store)
        self.assertEqual((after, n_after), (mid, n_mid))

    # ---------- 样本 B：JS + jsconfig 路径别名 ----------
    def test_sample_b_js_config_and_project_facts_reused(self):
        repo, commit = "42283287", "b" * 40
        js = b'import { h } from "@/utils";\nimport { render } from "./render";\n'
        cfg = b'{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}'
        self._capture(repo, commit, "src/index.js", js, "b1" * 20)
        self._capture(repo, commit, "src/utils.js", b"export const h = 1;\n", "b2" * 20)
        self._capture(repo, commit, "src/render.js", b"export const render = 1;\n", "b3" * 20)
        self._capture(repo, commit, "jsconfig.json", cfg, "b4" * 20)
        self._snapshot(repo, commit,
                       ["src/index.js", "src/utils.js", "src/render.js", "jsconfig.json"])
        self.store.close()
        self.store = KnowledgeStore(str(Path(self.root) / "kb.db"), create=False)

        r1 = RB.backfill_relations(repository_id=repo, commit_sha=commit,
                                   data_root=self.root)
        self.assertTrue(r1["ok"], r1)
        self.assertEqual(r1["network_requests"], 0)
        self.assertEqual(r1["config_files"], 1)
        self.assertGreater(r1["counts"]["config_facts_written"], 0)
        self.assertGreaterEqual(r1["counts"]["project_facts_written"], 0)
        self.assertGreater(r1["counts"]["written"], 0)
        self.assertEqual(r1["outcomes"]["error"], 0)

        mid, n_mid = _fingerprint(self.store)
        r2 = RB.backfill_relations(repository_id=repo, commit_sha=commit,
                                   data_root=self.root)
        self.assertEqual(r2["written"], [], r2)
        self.assertEqual(r2["counts"]["config_facts_reused"],
                         r1["counts"]["config_facts_written"], r2)
        self.assertEqual(r2["network_requests"], 0)
        after, n_after = _fingerprint(self.store)
        self.assertEqual((after, n_after), (mid, n_mid))


if __name__ == "__main__":
    unittest.main()
