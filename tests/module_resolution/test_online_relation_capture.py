#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-A: GitHub online capture path triggers the same shared relation pipeline.

Deterministic fixture: already-captured bytes + a complete snapshot, no network.
This validates the ONLINE_RELATION_CAPTURE_READY gate at the function entry that
the official analyze path calls (github_knowledge_extract.extract_captured).
"""
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "src"
for _d in ("storage", "collector", "content_persistence", "source_analysis",
           "skill_interface", "content", "facts"):
    sys.path.insert(0, str(_ROOT / _d))

REPO = "online:relation-fixture"
COMMIT = "e" * 40
PY_APP = b"from .utils import helper\nfrom os import path\n"
PY_UTIL = b"def helper():\n    return 1\n"
PROV = "AUTHORIZED_REMOTE_SOURCE"


class OnlineRelationCapture(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = self._td.name
        from knowledge_store import KnowledgeStore
        self.store = KnowledgeStore(str(Path(self.root) / "kb.db"), create=True)
        for path, raw, blob in (("pkg/app.py", PY_APP, "blob-app-online"),
                                ("pkg/utils.py", PY_UTIL, "blob-util-online")):
            import content_ingest_coordinator as CIC
            r = CIC.ingest_captured_blob(
                self.store, data_root=self.root, repository_id=REPO,
                commit_sha=COMMIT, source_snapshot_id="SL-SNAP-online",
                file_path=path, git_blob_oid=blob, git_object_format="sha1",
                raw=raw, source_declared_size=len(raw),
                acquisition_policy="AUTHORIZED_REMOTE_SOURCE",
                acquisition_policy_ref="fixture", provenance_level=PROV)
            assert r.get("ok"), r
        from asset_models import AssetDraft
        r = self.store.append_asset_and_advance(
            AssetDraft(asset_type="repository_snapshot",
                       logical_identity="SL-REPOSNAP-online",
                       repository_id=REPO,
                       payload={"commit_sha": COMMIT,
                                "completeness_status": "COMPLETE",
                                "blob_refs": [{"path": "pkg/app.py"},
                                              {"path": "pkg/utils.py"}]},
                       asset_version=1),
            expected_version=None)
        assert r.get("ok"), r
        self.store.close()

    def tearDown(self):
        self._td.cleanup()

    def _extract(self):
        import github_knowledge_extract as GKE
        from knowledge_store import KnowledgeStore
        st = KnowledgeStore(str(Path(self.root) / "kb.db"), create=False)
        try:
            report = {"results": [
                {"file_path": "pkg/app.py",
                 "status": "CAPTURED_VERIFIED"},
                {"file_path": "pkg/utils.py",
                 "status": "CAPTURED_VERIFIED"}]}
            out = GKE.extract_captured(
                store=st, data_root=self.root, repository_id=REPO,
                commit_sha=COMMIT, content_report=report)
            return out, st
        except Exception:
            st.close()
            raise

    def test_online_path_persists_relations_with_source_identity(self):
        import module_relation_query as MQ
        out, st = self._extract()
        try:
            rel = out.get("relation") or {}
            self.assertEqual(rel.get("tree_completeness"), "COMPLETE")
            self.assertGreaterEqual(rel.get("counts", {}).get("written", 0), 1)
            q = MQ.query_relations(data_root=self.root, repository_id=REPO,
                                   commit_sha=COMMIT)
            self.assertEqual(q.get("state"), MQ.STATE_FOUND)
            local = [x for x in q.get("relations", [])
                     if x.get("importing_file_path") == "pkg/app.py"
                     and x.get("resolved_target_path") == "pkg/utils.py"]
            self.assertTrue(local, q.get("relations"))
            # Evidence identity belongs to the importing blob, not the target.
            self.assertEqual(local[0].get("importing_blob_oid"),
                             "blob-app-online")
            self.assertNotIn("blob-util-online",
                             str(local[0].get("evidence_refs")))
        finally:
            st.close()

    def test_online_path_is_idempotent_on_second_run(self):
        out1, st1 = self._extract()
        st1.close()
        # second run reuses already-captured bytes, no new authoritative relations
        report = {"results": [
            {"file_path": "pkg/app.py", "status": "CAPTURED_VERIFIED"},
            {"file_path": "pkg/utils.py", "status": "CAPTURED_VERIFIED"}]}
        import github_knowledge_extract as GKE
        from knowledge_store import KnowledgeStore
        st2 = KnowledgeStore(str(Path(self.root) / "kb.db"), create=False)
        try:
            out2 = GKE.extract_captured(
                store=st2, data_root=self.root, repository_id=REPO,
                commit_sha=COMMIT, content_report=report)
            rel2 = out2.get("relation") or {}
            self.assertGreaterEqual(
                rel2.get("counts", {}).get("reused", 0), 1)
            self.assertEqual(
                rel2.get("counts", {}).get("written", 0), 0)
        finally:
            st2.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
