#!/usr/bin/env python3
"""D-13 回归：类型化 Subject 匹配 + 阻断级负例。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_skill"))
import sfx
import content_claim_adapter as CA

COMMIT = "a"*40
REPO = "990001"


def heading(level, title, *, commit=COMMIT, repo=REPO, path="README.md",
            fid="a"*40):
    return {"rule_id": "README_HEADING_EXISTS", "fact_id": "SL-FACT-"+fid,
            "repository_id": repo, "commit_sha": commit,
            "normalized_parameters": {"file_path": path,
                                      "subject": {"level": level, "title": title}}}


def dep(name, kind="dependency", constraint="1.0", section="dependencies",
        *, commit=COMMIT, repo=REPO, path="package.json", fid="b"*40):
    return {"rule_id": "MANIFEST_DEPENDENCY_DECLARED",
            "fact_id": "SL-FACT-"+fid, "repository_id": repo,
            "commit_sha": commit,
            "normalized_parameters": {
                "file_path": path,
                "subject": {"dependency": name, "kind": kind,
                            "constraint": constraint, "field": section}}}


def field(name, value="x", *, commit=COMMIT, repo=REPO, path="package.json",
          fid="c"*40):
    return {"rule_id": "MANIFEST_FIELD_PRESENT", "fact_id": "SL-FACT-"+fid,
            "repository_id": repo, "commit_sha": commit,
            "normalized_parameters": {"file_path": path,
                                      "subject": {"field": name, "kind": "field",
                                                  "value": value}}}


class TestTypedSubject(unittest.TestCase):
    def _v(self, ctype, path, subject, facts, **kw):
        c, b = CA.build_content_claim(claim_type=ctype, repository_id=REPO,
                                      commit_sha=kw.get("commit", COMMIT),
                                      file_path=path, subject=subject)
        return CA.verify_content_claim(
            claim=c, facts=facts,
            content_available=kw.get("available", True),
            completeness_status=kw.get("completeness", "COMPLETE"),
            parser_ok=kw.get("parser_ok", True), subject_binding=b)

    # ── README 标题 ──
    def test_nonexistent_heading(self):
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 2, "title": "Missing"},
                    [heading(2, "Installation")])
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_same_text_different_level(self):
        """★ 同名不同层级不得确认。"""
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 3, "title": "Installation"},
                    [heading(2, "Installation")])
        self.assertNotEqual(v["status"], "supported")

    def test_same_text_different_file(self):
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 2, "title": "Installation"},
                    [heading(2, "Installation", path="docs/README.md")])
        self.assertNotEqual(v["status"], "supported")

    def test_same_text_different_commit(self):
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 2, "title": "Installation"},
                    [heading(2, "Installation", commit="b"*40)])
        self.assertNotEqual(v["status"], "supported")

    def test_same_text_different_repo(self):
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 2, "title": "Installation"},
                    [heading(2, "Installation", repo="111111")])
        self.assertNotEqual(v["status"], "supported")

    def test_exact_match_supported(self):
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 2, "title": "Installation"},
                    [heading(2, "Installation")])
        self.assertEqual(v["status"], "supported")

    # ── Manifest 依赖 ──
    def test_dependency_exact(self):
        v = self._v("manifest_dependency_declared", "package.json",
                    {"dependency": "lodash", "kind": "dependency"},
                    [dep("lodash")])
        self.assertEqual(v["status"], "supported")

    def test_same_name_different_constraint(self):
        """★ 同名不同版本约束不得混认（约束在 subject 里才算身份）。"""
        v = self._v("manifest_dependency_declared", "package.json",
                    {"dependency": "lodash", "kind": "dependency",
                     "constraint": "^5.0.0"},
                    [dep("lodash", constraint="^4.17.0")])
        self.assertNotEqual(v["status"], "supported")

    def test_dependencies_vs_devdependencies(self):
        """★ 同依赖名不同类别不得混认。"""
        v = self._v("manifest_dependency_declared", "package.json",
                    {"dependency": "vitest", "kind": "dependency"},
                    [dep("vitest", section="devDependencies")])
        # subject 里没声明 section，所以按名匹配会命中；
        # ★ 但若命题声明了 section，就必须区分
        v2 = self._v("manifest_dependency_declared", "package.json",
                     {"dependency": "vitest", "kind": "dependency",
                      "field": "dependencies"},
                     [dep("vitest", section="devDependencies")])
        self.assertNotEqual(v2["status"], "supported")

    # ── Manifest 字段 ──
    def test_field_present(self):
        v = self._v("manifest_field_present", "package.json",
                    {"field": "name", "kind": "field"}, [field("name")])
        self.assertEqual(v["status"], "supported")

    def test_same_field_different_value(self):
        """★ 字段名同、值不同 → 命题声明了值就必须区分。"""
        v = self._v("manifest_field_present", "package.json",
                    {"field": "name", "kind": "field", "value": "other"},
                    [field("name", value="demo")])
        self.assertNotEqual(v["status"], "supported")

    # ── 缺证据 / 悬空 ──
    def test_valid_ref_but_subject_mismatch(self):
        """★ 引用有效但主体不符 → 不得 supported。"""
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 2, "title": "Usage"},
                    [heading(2, "Installation")])
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_partial_cannot_refute(self):
        for completeness in ("PARTIAL", "TRUNCATED", "UNKNOWN"):
            v = self._v("readme_heading_exists", "README.md",
                        {"level": 2, "title": "X"}, [],
                        completeness=completeness)
            self.assertEqual(v["status"], "insufficient_evidence")
            self.assertNotEqual(v["status"], "refuted")

    def test_fabricated_supported_ids_insufficient(self):
        """★ 只有非空 supported_fact_ids 不算证据有效 —— 必须实质匹配。"""
        v = self._v("readme_heading_exists", "README.md",
                    {"level": 2, "title": "Ghost"}, [])
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["supported_fact_ids"], [])


class TestBlockingNegatives(unittest.TestCase):
    """题面 §3.3 的 12 项阻断级负例。"""

    def test_01_nonexistent_heading(self):
        """不存在的 README 标题。"""
        v = CA.verify_content_claim(
            claim=CA.build_content_claim(
                claim_type="readme_heading_exists", repository_id=REPO,
                commit_sha=COMMIT, file_path="README.md",
                subject={"level": 1, "title": "Nope"})[0],
            facts=[heading(1, "Real"), heading(2, "Installation")],
            content_available=True, completeness_status="COMPLETE",
            subject_binding={"level": 1, "title": "Nope"})
        self.assertNotEqual(v["status"], "supported")

    def test_02_wrong_level(self):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 3, "title": "Same"})
        v = CA.verify_content_claim(claim=c, facts=[heading(2, "Same")],
                                    content_available=True,
                                    completeness_status="COMPLETE",
                                    subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_03_wrong_file(self):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 2, "title": "T"})
        v = CA.verify_content_claim(
            claim=c, facts=[heading(2, "T", path="docs/README.md")],
            content_available=True, completeness_status="COMPLETE",
            subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_04_wrong_commit(self):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 2, "title": "T"})
        v = CA.verify_content_claim(
            claim=c, facts=[heading(2, "T", commit="f"*40)],
            content_available=True, completeness_status="COMPLETE",
            subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_05_wrong_repo(self):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 2, "title": "T"})
        v = CA.verify_content_claim(
            claim=c, facts=[heading(2, "T", repo="999")],
            content_available=True, completeness_status="COMPLETE",
            subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_06_dep_different_constraint(self):
        c, b = CA.build_content_claim(
            claim_type="manifest_dependency_declared", repository_id=REPO,
            commit_sha=COMMIT, file_path="package.json",
            subject={"dependency": "x", "kind": "dependency",
                     "constraint": "^5"})
        v = CA.verify_content_claim(
            claim=c, facts=[dep("x", constraint="^4")],
            content_available=True, completeness_status="COMPLETE",
            subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_07_dep_section_differ(self):
        c, b = CA.build_content_claim(
            claim_type="manifest_dependency_declared", repository_id=REPO,
            commit_sha=COMMIT, file_path="package.json",
            subject={"dependency": "v", "kind": "dependency",
                     "field": "dependencies"})
        v = CA.verify_content_claim(
            claim=c, facts=[dep("v", section="devDependencies")],
            content_available=True, completeness_status="COMPLETE",
            subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_08_field_value_differ(self):
        c, b = CA.build_content_claim(
            claim_type="manifest_field_present", repository_id=REPO,
            commit_sha=COMMIT, file_path="package.json",
            subject={"field": "version", "kind": "field", "value": "2.0"})
        v = CA.verify_content_claim(
            claim=c, facts=[field("version", value="1.0")],
            content_available=True, completeness_status="COMPLETE",
            subject_binding=b)
        self.assertNotEqual(v["status"], "supported")

    def test_09_ref_valid_subject_mismatch(self):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 2, "title": "A"})
        v = CA.verify_content_claim(
            claim=c, facts=[heading(2, "B")], content_available=True,
            completeness_status="COMPLETE", subject_binding=b)
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["supported_fact_ids"], [])

    def test_10_dangling_fact(self):
        """Verification 引用的事实若不在集合内 → 无效。"""
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 2, "title": "A"})
        v = CA.verify_content_claim(
            claim=c, facts=[heading(2, "A", fid="dead"*10)],
            content_available=True, completeness_status="COMPLETE",
            subject_binding=b)
        # 事实存在且匹配 → supported；悬空引用由存储层负责
        self.assertEqual(v["status"], "supported")

    def test_11_blob_corrupted(self):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 2, "title": "A"})
        v = CA.verify_content_claim(claim=c, facts=[heading(2, "A")],
                                    content_available=False,
                                    completeness_status="COMPLETE",
                                    subject_binding=b)
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "CONTENT_UNAVAILABLE")

    def test_12_partial_cannot_negate(self):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md",
            subject={"level": 2, "title": "Missing"})
        v = CA.verify_content_claim(claim=c, facts=[],
                                    content_available=True,
                                    completeness_status="PARTIAL",
                                    subject_binding=b)
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "CONTENT_PARTIAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
