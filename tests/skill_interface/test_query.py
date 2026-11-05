#!/usr/bin/env python3
"""C. 知识检索：真实 SQLite + 真实 View/Research，不重采集。"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx

for p in ("research","views","lifecycle","storage","collector","facts",
          "evidence_claims","runtime","skill_interface"):
    if str(ROOT/"src"/p) not in sys.path:
        sys.path.insert(0, str(ROOT/"src"/p))
if str(ROOT/"tests"/"views") not in sys.path:
    sys.path.insert(0, str(ROOT/"tests"/"views"))

import vfx
import knowledge as K
import query as Q
from result import SkillError


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="si_"))
        self.ks = vfx.fresh(self.tmp)
        vfx.run_full(self.ks)
        self.root = str(self.tmp)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestKnowledge(Base):
    def test_repositories(self):
        store = K.open_store(self.root)
        try:
            out = K.list_repositories(store)
        finally:
            store.close()
        self.assertEqual(out["count"], 1)
        r = out["repositories"][0]
        self.assertEqual(r["repository_id"], vfx.REPO)
        self.assertGreaterEqual(r["snapshot_count"], 1)
        self.assertIn("knowledge_state", r)

    def test_repositories_not_confused(self):
        store = K.open_store(self.root)
        try:
            out = K.list_repositories(store)
        finally:
            store.close()
        repos = {r["repository_id"] for r in out["repositories"]}
        self.assertEqual(repos, {vfx.REPO}, "不得混入其他仓库")

    def test_inspect(self):
        store = K.open_store(self.root)
        try:
            out = K.inspect_repository(store, vfx.REPO)
        finally:
            store.close()
        self.assertIn(vfx.A, out["commits"])
        self.assertGreaterEqual(len(out["facts"]), 1)
        self.assertGreaterEqual(len(out["limitations"]), 1)

    def test_inspect_missing(self):
        store = K.open_store(self.root)
        try:
            with self.assertRaises(SkillError):
                K.inspect_repository(store, "999999")
        finally:
            store.close()

    def test_history_no_ancestry(self):
        store = K.open_store(self.root)
        try:
            out = K.history(store, vfx.REPO)
        finally:
            store.close()
        self.assertIn("不推断", out["note"])
        self.assertGreaterEqual(len(out["versions"]), 1)


class TestQuery(Base):
    def test_path_query(self):
        out = Q.run_query(repository_id=vfx.REPO, commit_sha=vfx.A,
                          qtype="path", path="README", data_root=self.root)
        self.assertIn("coverage_state", out)
        self.assertEqual(out["coverage_state"],
                         "ANSWERABLE_FROM_EXISTING_EVIDENCE")
        self.assertGreaterEqual(len(out["findings"]), 1)
        f = out["findings"][0]
        self.assertEqual(f["verdict_status"], "supported")
        self.assertTrue(f["evidence_refs"])
        self.assertFalse(out["is_knowledge_authority"])

    def test_insufficient_abstains(self):
        out = Q.run_query(repository_id=vfx.REPO, commit_sha=vfx.A,
                          qtype="path", path="no-such-file-xyz.md",
                          data_root=self.root)
        self.assertEqual(out["coverage_state"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(out["answerable"])
        self.assertEqual(len(out["findings"]), 0)
        blob = json.dumps(out, ensure_ascii=False)
        self.assertNotIn("该命题错误", blob)

    def test_commit_isolation(self):
        out = Q.run_query(repository_id=vfx.REPO, commit_sha="c"*40,
                          qtype="claims", data_root=self.root)
        for f in out["findings"]:
            self.assertNotEqual(f["commit_sha"], "c"*40)

    def test_missing_path_param(self):
        with self.assertRaises(SkillError):
            Q.run_query(repository_id=vfx.REPO, commit_sha=vfx.A,
                        qtype="path", data_root=self.root)

    def test_bad_query_type(self):
        with self.assertRaises(SkillError):
            Q.run_query(repository_id=vfx.REPO, commit_sha=vfx.A,
                        qtype="nonsense", data_root=self.root)

    def test_does_not_refetch_github(self):
        src = (ROOT/"src"/"skill_interface"/"query.py").read_text(encoding="utf-8")
        self.assertNotIn("GitHubClient", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
