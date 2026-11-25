#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-A / D3：跨来源 relation 检索复用 D3 可信来源解析。

★ 不依赖作者本机路径；全部用 tempfile 建临时知识库。
★ 验证：补充源关系通过 source_knowledge 查询入口附上，且每条保留证据身份。
"""
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "src"
for _d in ("runtime", "storage", "skill_interface", "trust", "collector",
           "facts", "evidence_claims", "lifecycle", "views",
           "content_persistence", "source_analysis"):
    sys.path.insert(0, str(_ROOT / _d))

from test_source_provenance_d3 import (COMMIT, GID, LID, bind, build_fixture)


def _relation_resolution(rid):
    return {
        "repository_id": rid,
        "commit_sha": COMMIT,
        "resolution_id": "SL-RES-D3-" + rid.replace(":", "-"),
        "importing_file_path": "scripts/arch_cli.py",
        "module_specifier": "./utils",
        "import_kind": "relative",
        "is_type_only": False,
        "resolution_state": "LOCAL_MODULE_RESOLVED",
        "resolution_policy": "TSCONFIG_PATHS_FIRST",
        "resolved_target_path": "scripts/utils.py",
        "import_fact_id": "SL-IMP-D3-1",
        "resolver_version": "p2a-test",
    }


class D3SupplementRelationQueryTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.st = build_fixture(self._td.name)
        # 本地补充源落一条权威关系事实
        import module_relation_ingest as MRI
        r = MRI.ingest_resolution(
            self.st, resolution=_relation_resolution(LID),
            evidence_refs=["blob:cccc3333:scripts/arch_cli.py"])
        self.assertTrue(r.get("written"), r)
        bind(self.st)  # 建立 GID -> LID 的 D3 严格验证绑定

    def tearDown(self):
        self.st.close()
        self._td.cleanup()

    def test_supplement_relation_preserves_evidence_identity(self):
        import source_knowledge as SK
        q = SK.query_module_relations(
            repository_id=GID, commit_sha=COMMIT,
            importing_file_path="scripts/arch_cli.py",
            module_specifier="./utils",
            data_root=self._td.name)
        self.assertIn("supplement_relations", q, q)
        self.assertGreater(q["supplement_count"], 0)
        s = q["supplement_relations"][0]
        self.assertEqual(s["source_repository_id"], LID)
        self.assertEqual(s["source_role"], "verified_local_supplement")
        self.assertTrue(s["evidence_ref"])

    def test_supplement_can_be_disabled(self):
        import source_knowledge as SK
        q = SK.query_module_relations(
            repository_id=GID, commit_sha=COMMIT,
            importing_file_path="scripts/arch_cli.py",
            module_specifier="./utils",
            data_root=self._td.name, include_supplements=False)
        self.assertNotIn("supplement_relations", q)

    def test_non_numeric_repo_has_no_supplements(self):
        import source_knowledge as SK
        q = SK.query_module_relations(
            repository_id=LID, commit_sha=COMMIT,
            importing_file_path="scripts/arch_cli.py",
            module_specifier="./utils", data_root=self._td.name)
        self.assertNotIn("supplement_relations", q)


if __name__ == "__main__":
    unittest.main()
