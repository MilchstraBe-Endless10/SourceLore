#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D3 跨来源知识关联：独立、可重复的隔离测试夹具。

★ 不依赖作者本机任何路径；全部用 tempfile 建临时知识库。
★ 覆盖：来源真实性正反例、严格绑定、补充源解析、只读不污染 A 层。
"""
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "src"
for _d in ("runtime", "storage", "skill_interface", "trust", "collector",
           "facts", "evidence_claims", "lifecycle", "views"):
    sys.path.insert(0, str(_ROOT / _d))

COMMIT = "8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024"
ROOT_TREE = "c668da9687b98d340616ce1e4c2ede911d090ec3"
GID = "1459544036"
LID = "local:4034d62ed2cf"


def _add(store, *, asset_type, rid, payload, logical=None):
    from asset_models import AssetDraft
    logical = logical or ("SL-TEST-" + asset_type + "-" + rid)
    op = "OP-D3-" + str(abs(hash(logical)))[:16]
    r = store.append_asset_and_advance(
        AssetDraft(asset_type=asset_type, logical_identity=logical,
                   repository_id=rid, payload=payload, asset_version=1,
                   operation_id=op),
        expected_version=None, operation_id=op)
    assert r.get("ok"), r
    return r["asset_id"]


def build_fixture(tmp, *, with_identity=True, github_blobs=None,
                  local_blobs=None, local_commit=COMMIT):
    from knowledge_store import KnowledgeStore
    db = Path(tmp) / "kb.db"
    st = KnowledgeStore(str(db), create=True)
    if with_identity:
        _add(st, asset_type="subject_record", rid=GID,
             logical="SL-REPONAME-" + GID,
             payload={"record_kind": "repository_display_name",
                      "resolved_repository": "Tobi1chi/arch-grower",
                      "requested_repository": "Tobi1chi/arch-grower",
                      "repository_id": GID})
    gh_blobs = github_blobs if github_blobs is not None else [
        {"path": "README.md", "blob_sha": "aaaa1111"},
        {"path": "pyproject.toml", "blob_sha": "bbbb2222"}]
    lo_blobs = local_blobs if local_blobs is not None else [
        {"path": "README.md", "blob_sha": "aaaa1111"},
        {"path": "pyproject.toml", "blob_sha": "bbbb2222"},
        {"path": "scripts/arch_cli.py", "blob_sha": "cccc3333"}]
    _add(st, asset_type="repository_snapshot", rid=GID,
         payload={"commit_sha": COMMIT, "root_tree_sha": ROOT_TREE,
                  "blob_refs": gh_blobs, "repository_id": GID})
    _add(st, asset_type="repository_snapshot", rid=LID,
         payload={"commit_sha": local_commit, "root_tree_sha": ROOT_TREE,
                  "blob_refs": lo_blobs, "repository_id": LID})
    return st


def bind(st, *, evidence="source_verified=1;CONTENT-ANCHOR-test"):
    subject = "CONTENT-ANCHOR-test"
    st.bind_repo(subject_id=subject, repository_id=GID, evidence_ref=evidence)
    st.bind_repo(subject_id=subject, repository_id=LID, evidence_ref=evidence)
    return subject


class SourceProvenanceD3Test(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.st = build_fixture(self._td.name)

    def tearDown(self):
        self.st.close()
        self._td.cleanup()

    def test_identity_requires_authoritative_record(self):
        import source_provenance as SP
        ok = SP.github_identity_evidence(self.st, GID)
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["resolved_repository"], "Tobi1chi/arch-grower")
        bad = SP.github_identity_evidence(self.st, "999999999")
        self.assertFalse(bad["ok"])

    def test_numeric_local_id_is_rejected(self):
        import source_provenance as SP
        v = SP.verify_source_binding(self.st, github_id=GID,
                                     local_id="999999999", commit_sha=COMMIT)
        self.assertFalse(v["ok"])
        self.assertTrue(any("SNAPSHOT_MISSING" in r for r in v["reasons"]))

    def test_blob_hash_conflict_rejected(self):
        import source_provenance as SP
        # 用冲突 blob 建一个独立库（current_view 自然指向该快照）
        with tempfile.TemporaryDirectory() as td:
            st = build_fixture(td, github_blobs=[
                {"path": "README.md", "blob_sha": "DEADBEEF"},
                {"path": "pyproject.toml", "blob_sha": "bbbb2222"}])
            try:
                v = SP.verify_source_binding(st, github_id=GID, local_id=LID,
                                             commit_sha=COMMIT)
                self.assertFalse(v["ok"])
                self.assertTrue(any("BLOB_HASH_CONFLICT" in r
                                    for r in v["reasons"]))
            finally:
                st.close()

    def test_same_commit_root_tree_alone_insufficient(self):
        import source_provenance as SP
        with tempfile.TemporaryDirectory() as td:
            bare = build_fixture(td, with_identity=False)
            try:
                v = SP.verify_source_binding(bare, github_id=GID, local_id=LID,
                                             commit_sha=COMMIT)
                self.assertFalse(v["ok"])
                self.assertTrue(any("GITHUB_IDENTITY_UNVERIFIED" in r
                                    for r in v["reasons"]))
            finally:
                bare.close()

    def test_valid_binding_and_supplement_resolution(self):
        import source_provenance as SP
        before = self._fingerprint()
        bind(self.st)
        v = SP.verify_source_binding(self.st, github_id=GID, local_id=LID,
                                     commit_sha=COMMIT)
        self.assertTrue(v["ok"], v["reasons"])
        self.assertTrue(v["blob_subset_verified"])
        r = SP.resolve_supplement(self.st, GID, COMMIT)
        self.assertTrue(r["ok"])
        self.assertEqual([s["repository_id"] for s in r["supplements"]], [LID])
        self.assertIn("source_verified=1", r["supplements"][0]["evidence_ref"])
        self.assertEqual(before, self._fingerprint())

    def test_unverified_evidence_not_used(self):
        import source_provenance as SP
        bind(self.st, evidence="unverified;no-marker")
        r = SP.resolve_supplement(self.st, GID, COMMIT)
        self.assertFalse(r["ok"])
        self.assertEqual(r["supplements"], [])

    def _fingerprint(self):
        rows = self.st.conn.execute(
            "SELECT asset_id||'|'||asset_type||'|'||content_hash FROM assets "
            "ORDER BY asset_id").fetchall()
        return [r[0] for r in rows]


if __name__ == "__main__":
    unittest.main(verbosity=2)
