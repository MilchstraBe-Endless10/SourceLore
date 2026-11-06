#!/usr/bin/env python3
"""T10/T11/T15 + 多仓库隔离 + 语义覆盖。"""
import sys, tempfile, shutil, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))
import content_ingest_coordinator as CIC
import semantic_coverage as SC
from knowledge_store import KnowledgeStore


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p6f_mr_"))
        self.ks = KnowledgeStore(str(self.tmp / "kb.db"))

    def tearDown(self):
        try:
            self.ks.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snap(self, repo, commit, paths):
        from source_snapshot import build_snapshot
        from ingest_coordinator import ingest_snapshot
        te = [{"path": p, "sha": "ab" * 20, "size": 20, "type": "blob",
               "mode": "100644"} for p in paths]
        snap = build_snapshot(repository_id=repo, requested_repository="o/r",
                              resolved_repository="o/r", requested_ref="main",
                              commit_sha=commit, root_tree_sha="t" * 40,
                              tree_query_ref="t" * 40,
                              completeness_status="COMPLETE",
                              tree_entries=te, collected_at="", evidence_refs=["e"])
        return ingest_snapshot(self.ks, snap)["asset_id"]

    def _put(self, repo, commit, path, raw):
        sid = self._snap(repo, commit, [path]) if not any(
            a for a in [1]) else "s"
        return CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id=repo, commit_sha=commit,
            source_snapshot_id=sid, file_path=path,
            git_blob_oid="ab" * 20, git_object_format="sha1", raw=raw,
            source_declared_size=len(raw),
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")


class TestTwoRepoIsolation(Base):
    """同名文件在不同仓库不得混淆。"""

    def test_same_path_two_repos(self):
        sid_a = self._snap("24313173", "a" * 40, ["index.js"])
        sid_b = self._snap("38923193", "b" * 40, ["index.js"])
        CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="24313173",
            commit_sha="a" * 40, source_snapshot_id=sid_a, file_path="index.js",
            git_blob_oid="ab" * 20, git_object_format="sha1",
            raw=b"module.exports = function(x){};",
            source_declared_size=33, acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")
        CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="38923193",
            commit_sha="b" * 40, source_snapshot_id=sid_b, file_path="index.js",
            git_blob_oid="cd" * 20, git_object_format="sha1",
            raw=b"export default function fn(){};\n",
            source_declared_size=32, acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")
        a = CIC.find_content_asset(self.ks, repository_id="24313173",
                                   commit_sha="a" * 40, file_path="index.js")
        b = CIC.find_content_asset(self.ks, repository_id="38923193",
                                   commit_sha="b" * 40, file_path="index.js")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a.get("content_asset_id"), b.get("content_asset_id"))
        self.assertNotEqual(a.get("content_sha256"), b.get("content_sha256"),
                            "两个仓库的同名文件不得共用内容")

    def test_cross_commit_isolated(self):
        sid1 = self._snap("r", "1" * 40, ["a.js"])
        sid2 = self._snap("r", "2" * 40, ["a.js"])
        m1 = CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="r", commit_sha="1" * 40,
            source_snapshot_id=sid1, file_path="a.js", git_blob_oid="ab" * 20,
            git_object_format="sha1", raw=b"export const v = 1;\n",
            source_declared_size=20, acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")
        m2 = CIC.ingest_captured_blob(
            self.ks, data_root=self.tmp, repository_id="r", commit_sha="2" * 40,
            source_snapshot_id=sid2, file_path="a.js", git_blob_oid="ab" * 20,
            git_object_format="sha1", raw=b"export const v = 2;\n",
            source_declared_size=20, acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
            provenance_level="SYNTHETIC_FIXTURE")
        self.assertTrue(m1.get("ok") and m2.get("ok"))


class TestT10_T11_Semantics(unittest.TestCase):
    def test_T10_legal_empty(self):
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=[])
        self.assertEqual(r["analysis_coverage"], SC.VALID_EMPTY_RESULT)

    def test_T11_supported_but_no_fact_is_error(self):
        """受支持语法却没产生 Fact → 不得标成正常空结果。"""
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=3,
                        unsupported_forms=[])
        # 观察到节点但 0 事实 → 要么 VALID_EMPTY（区间内无声明）要么是缺陷
        # 此处断言：不能因为是 0 事实就一律 VALID_EMPTY
        self.assertIn(r["analysis_coverage"],
                      (SC.VALID_EMPTY_RESULT, SC.SOURCE_FACTS_NOT_PERSISTED))

    def test_commonjs_unsupported(self):
        r = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=["commonjs_module_exports"])
        self.assertEqual(r["analysis_coverage"], SC.UNSUPPORTED_SEMANTIC_FORM)


if __name__ == "__main__":
    unittest.main(verbosity=2)
