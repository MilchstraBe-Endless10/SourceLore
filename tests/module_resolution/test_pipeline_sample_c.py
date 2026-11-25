#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-A 样本 C：独立最小仓库，端到端验证共享静态关系处理管线。

覆盖：Python 相对导入 / JS-TS 相对导入 / TS 路径别名 / 配置缺失 /
外部依赖 / 不完整 Tree / 不同 Commit / 证据身份分离 / 幂等 / 零网络。
"""
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
for sub in ("facts", "storage", "source_analysis", "content_persistence"):
    sys.path.insert(0, str(ROOT / "src" / sub))

import module_relation_pipeline as MRP
import module_config_models as CM
import module_relation_query as MQ
from knowledge_store import KnowledgeStore

REPO = "990099"
COMMIT = "c" * 40
COMMIT_OTHER = "d" * 40

TSCONFIG = b'{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}'
PY_APP = (
    b"from . import utils\n"
    b"from .helpers import thing as t\n"
    b"import os\n"
)
TS_APP = (
    b'import { x } from "@/utils";\n'
    b'import y from "./local";\n'
)
TS_NOCFG = b'import z from "@/missing";\n'

TREE = {
    "pkg/app.py", "pkg/utils.py", "pkg/helpers.py",
    "src/app.ts", "src/utils.ts", "src/local.ts", "tsconfig.json",
}


class PipelineSampleC(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p2a_sample_c_"))
        self.store = KnowledgeStore(str(self.tmp / "kb.db"))

    def tearDown(self):
        try:
            self.store.close()
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def _sources(self):
        return [
            {"file_path": "pkg/app.py", "raw": PY_APP,
             "git_blob_oid": "1" * 40, "content_asset_id": "SL-C-py",
             "content_sha256": "sha256:py"},
            {"file_path": "src/app.ts", "raw": TS_APP,
             "git_blob_oid": "2" * 40, "content_asset_id": "SL-C-ts",
             "content_sha256": "sha256:ts"},
        ]

    def _configs(self):
        return [{"config_path": "tsconfig.json", "raw": TSCONFIG,
                 "blob_oid": "3" * 40, "content_asset_id": "SL-C-cfg",
                 "content_digest": "sha256:cfg"}]

    def _run(self, **kw):
        args = dict(
            repository_id=REPO, commit_sha=COMMIT,
            file_sources=self._sources(), tree_paths=TREE,
            config_sources=self._configs(),
            provenance_level="SYNTHETIC_FIXTURE",
            source_snapshot_id="SL-C-snapshot",
        )
        args.update(kw)
        return MRP.process_source_relations(self.store, **args)

    # ----- 关系解析与证据 -----
    def test_python_and_ts_relations_resolved(self):
        r = self._run()
        states = [x["resolution_state"] for x in r["resolutions"]]
        self.assertIn(CM.LOCAL_MODULE_RESOLVED, states)
        self.assertGreaterEqual(r["counts"]["written"], 3)
        for x in r["resolutions"]:
            if x["resolution_state"] == CM.LOCAL_MODULE_RESOLVED:
                self.assertIn("tree:" + x["resolved_target_path"],
                              x["evidence_refs"])
                # 导入方身份不得冒充配置方身份
                self.assertIn("source:SL-C-", x["evidence_refs"][-1])

    def test_external_not_persisted_as_resolved(self):
        r = self._run()
        ext = [x for x in r["resolutions"]
               if x["resolution_state"] == CM.EXTERNAL_OR_UNRESOLVED]
        self.assertTrue(ext)
        self.assertEqual(ext[0]["resolved_target_path"], None)
        self.assertFalse(any("tree:" in x["evidence_refs"] for x in ext))

    def test_config_alias_resolved_with_own_identity(self):
        r = self._run()
        alias = [x for x in r["resolutions"]
                 if x["module_specifier"] == "@/utils"][0]
        self.assertEqual(alias["resolution_state"], CM.LOCAL_MODULE_RESOLVED)
        self.assertTrue(alias["config_observation_ids"])
        self.assertTrue(any(e.startswith("config:") for e in alias["evidence_refs"]))

    def test_target_not_in_tree_never_becomes_resolved(self):
        shallow = TREE - {"src/utils.ts"}
        r = self._run(tree_paths=shallow)
        alias = [x for x in r["resolutions"]
                 if x["module_specifier"] == "@/utils"][0]
        self.assertNotEqual(alias["resolution_state"], CM.LOCAL_MODULE_RESOLVED)
        self.assertEqual(alias["resolved_target_path"], None)
        self.assertFalse(any(e.startswith("tree:") for e in alias["evidence_refs"]))

    def test_incomplete_tree_honest(self):
        r = self._run(tree_paths=set(), source_completeness="INCOMPLETE")
        self.assertGreater(r["outcomes"].get("insufficient_tree", 0), 0)

    def test_missing_config_is_not_fabricated(self):
        r = self._run(file_sources=[
            {"file_path": "src/app.ts", "raw": TS_NOCFG,
             "git_blob_oid": "4" * 40, "content_asset_id": "SL-C-nocfg",
             "content_sha256": "sha256:nocfg"}],
            config_sources=[])
        self.assertGreater(sum(v for k, v in r["outcomes"].items()
                               if k.startswith("config")), 0)

    def test_different_commit_separates_identity(self):
        a = self._run()
        b = self._run(commit_sha=COMMIT_OTHER)
        ids_a = {x["resolution_id"] for x in a["resolutions"]}
        ids_b = {x["resolution_id"] for x in b["resolutions"]}
        self.assertFalse(ids_a & ids_b)

    # ----- 幂等 / 网络 -----
    def test_idempotent_second_run_reuses(self):
        first = self._run()
        second = self._run()
        self.assertEqual(second["counts"]["written"], 0)
        self.assertEqual(second["counts"]["reused"], first["counts"]["written"])
        self.assertEqual(first["network_requests"], 0)
        self.assertEqual(second["network_requests"], 0)

    def test_no_mutation_when_replayed(self):
        self._run()
        before = self.store.conn.execute(
            "SELECT COUNT(*) FROM index_rows WHERE asset_type='extracted_fact'"
        ).fetchone()[0]
        self._run()
        after = self.store.conn.execute(
            "SELECT COUNT(*) FROM index_rows WHERE asset_type='extracted_fact'"
        ).fetchone()[0]
        self.assertEqual(before, after)

    # ----- 查询契约 -----
    def test_query_status_contract_distinguishes_unresolved(self):
        # 让 Query 直接读本测试的临时库（db_path = data_root/kb.db）。
        self._run()
        q = MQ.query_relations(repository_id=REPO, commit_sha=COMMIT,
                               importing_file_path="pkg/app.py",
                               data_root=str(self.tmp))
        self.assertEqual(q["state"], MQ.STATE_FOUND)
        self.assertEqual(q["status"], MQ.STATUS_RESOLVED)
        self.assertIn(MQ.STATUS_RESOLVED, q["status_counts"])
        self.assertIn(MQ.STATUS_EXTERNAL, q["status_counts"])

        # 外部依赖单独查询：无权威事实，但有非权威审计，状态必须是 EXTERNAL。
        q2 = MQ.query_relations(repository_id=REPO, commit_sha=COMMIT,
                                importing_file_path="pkg/app.py",
                                module_specifier="os",
                                data_root=str(self.tmp))
        self.assertEqual(q2["state"], MQ.STATE_NONE)
        self.assertEqual(q2["status"], MQ.STATUS_EXTERNAL)
        self.assertEqual(q2["relations"], [])
        self.assertTrue(q2["attempts"])
        self.assertFalse(q2["attempts"][0]["authoritative"])


if __name__ == "__main__":
    unittest.main()
