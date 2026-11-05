#!/usr/bin/env python3
"""Content Gold：25 例，统计支持/否定/abstention 命中率。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_persistence"))
import sfx
import fixtures as FX
import pipeline as PL
import content_claim_adapter as CA
from gold_contents import GOLD
from knowledge_store import KnowledgeStore


class TestContentGold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="gold_"))
        cls.ks = KnowledgeStore(str(cls.tmp/"kb.db"))
        cls.per_case = {}
        for gid, path, content, kind, exp in GOLD:
            files = [(path, content)]
            sid, li = PL.make_snapshot(cls.ks, FX.COMMIT_A + gid, files)
            cmap = PL.capture(cls.ks, cls.tmp, sid, FX.COMMIT_A + gid, files)
            res = PL.extract_and_ingest(cls.ks, sid, li, FX.COMMIT_A + gid,
                                        cmap, paths=[path])
            cls.per_case[gid] = {
                "path": path, "content": content, "kind": kind, "expect": exp,
                "facts": res[path]["facts"], "extraction": res[path]["extraction"],
                "commit": FX.COMMIT_A + gid, "snapshot": sid, "li": li}

    @classmethod
    def tearDownClass(cls):
        try: cls.ks.close()
        except Exception: pass
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _verdict(self, gid, subject, available=True, completeness="COMPLETE",
                 facts=None, commit=None):
        pc = self.per_case[gid]
        c, b = CA.build_content_claim(
            claim_type=("readme_heading_exists" if pc["kind"] in ("HEADING","CROSS")
                        else "manifest_dependency_declared" if pc["kind"] == "DEP"
                        else "manifest_field_present"),
            repository_id=FX.REPO,
            commit_sha=commit or pc["commit"], file_path=pc["path"],
            subject=subject)
        return CA.verify_content_claim(
            claim=c, facts=facts if facts is not None else pc["facts"],
            content_available=available,
            completeness_status=completeness, subject_binding=b)

    def test_c01_level1_present(self):
        self.assertEqual(self._verdict("C01", {"level":1,"title":"A"})["status"],
                         "supported")

    def test_c02_level2_present(self):
        self.assertEqual(self._verdict("C02", {"level":2,"title":"B"})["status"],
                         "supported")

    def test_c03_h1_absent_still_h2_ok(self):
        self.assertEqual(self._verdict("C03", {"level":2,"title":"Only H2"})["status"],
                         "supported")
        self.assertEqual(self._verdict("C03", {"level":1,"title":"Only H2"})["status"],
                         "insufficient_evidence")

    def test_c04_h2_absent(self):
        self.assertEqual(self._verdict("C04", {"level":2,"title":"C"})["status"],
                         "insufficient_evidence")

    def test_c05_nonexistent_title_insufficient(self):
        """★ 阻断级：不存在的标题必须 abstain。"""
        self.assertEqual(self._verdict("C05", {"level":1,"title":"Missing"})["status"],
                         "insufficient_evidence")

    def test_c06_wrong_level(self):
        self.assertEqual(self._verdict("C06", {"level":2,"title":"T"})["status"],
                         "insufficient_evidence")

    def test_c07_c08_no_facts(self):
        for gid in ("C07","C08"):
            self.assertEqual(self.per_case[gid]["facts"], [], gid)

    def test_c09_utf8(self):
        self.assertEqual(self._verdict("C09", {"level":1,"title":"中文"})["status"],
                         "supported")

    def test_c10_crlf(self):
        self.assertEqual(self._verdict("C10", {"level":2,"title":"B"})["status"],
                         "supported")

    def test_c11_fence_only_no_heading(self):
        self.assertEqual(self._verdict("C11", {"level":1,"title":"x"})["status"],
                         "insufficient_evidence")

    def test_c12_heading_plus_link(self):
        self.assertEqual(self._verdict("C12", {"level":1,"title":"A"})["status"],
                         "supported")

    def test_c13_dep_declared(self):
        self.assertEqual(self._verdict("C13", {"dependency":"x","kind":"dependency"})["status"],
                         "supported")

    def test_c14_dep_not_declared_does_not_refute_usage(self):
        """★ 声明 y ≠ 未使用 x —— 不得 refuted。"""
        v = self._verdict("C14", {"dependency":"x","kind":"dependency"})
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertNotEqual(v["status"], "refuted")

    def test_c15_empty_deps(self):
        self.assertEqual(self._verdict("C15", {"dependency":"x","kind":"dependency"})["status"],
                         "insufficient_evidence")

    def test_c16_field_present(self):
        self.assertEqual(self._verdict("C16", {"field":"name","kind":"field"})["status"],
                         "supported")

    def test_c17_field_absent(self):
        self.assertEqual(self._verdict("C17", {"field":"name","kind":"field"})["status"],
                         "insufficient_evidence")

    def test_c18_two_deps(self):
        for d in ("a","b"):
            self.assertEqual(self._verdict("C18", {"dependency":d})["status"],
                             "supported")

    def test_c19_invalid_json_abstain(self):
        self.assertEqual(self._verdict("C19", {"dependency":"x","kind":"dependency"})["status"],
                         "insufficient_evidence")

    def test_c20_array_not_object(self):
        self.assertEqual(self._verdict("C20", {"field":"name","kind":"field"})["status"],
                         "insufficient_evidence")

    def test_c21_pyproject_name(self):
        self.assertEqual(self._verdict("C21", {"field":"project.name","kind":"field"})["status"],
                         "supported")

    def test_c22_invalid_toml(self):
        self.assertEqual(self._verdict("C22", {"field":"name","kind":"field"})["status"],
                         "insufficient_evidence")

    def test_c23_idempotent(self):
        pc = self.per_case["C23"]
        sid, li = PL.make_snapshot(self.ks, FX.COMMIT_A + "C23r",
                                   [("README.md", pc["content"])])
        cm = PL.capture(self.ks, self.tmp, sid, FX.COMMIT_A + "C23r",
                        [("README.md", pc["content"])])
        r1 = PL.extract_and_ingest(self.ks, sid, li, FX.COMMIT_A + "C23r", cm)
        r2 = PL.extract_and_ingest(self.ks, sid, li, FX.COMMIT_A + "C23r", cm)
        self.assertEqual(len(r1["README.md"]["ingest"]["written"]),
                         len(r2["README.md"]["ingest"]["reused"]) +
                         len(r2["README.md"]["ingest"]["written"]))

    def test_c24_wrong_commit_not_supported(self):
        """★ 阻断级：错 Commit 证据不得确认命题。"""
        v = self._verdict("C24", {"level":1,"title":"A"}, commit="f"*40)
        self.assertNotEqual(v["status"], "supported")

    def test_c25_wrong_repo_not_supported(self):
        pc = self.per_case["C25"]
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id="111111",
            commit_sha=pc["commit"], file_path=pc["path"],
            subject={"level":1,"title":"A"})
        v = CA.verify_content_claim(claim=c, facts=pc["facts"],
                                    content_available=True,
                                    completeness_status="COMPLETE",
                                    subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_no_refuted_anywhere(self):
        """★ 阻断级：本 Gold 集合不应产生任何 refuted。"""
        for gid, pc in self.per_case.items():
            for f in pc["facts"]:
                self.assertNotEqual(f.get("observation"), "REFUTED", gid)

    def test_all_25_present(self):
        self.assertEqual(len(self.per_case), len(GOLD))


if __name__ == "__main__":
    unittest.main(verbosity=2)
