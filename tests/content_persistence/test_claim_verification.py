#!/usr/bin/env python3
"""内容命题裁决：supported / refuted / insufficient + 禁止推断。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_persistence"))
import sfx
import content_claim_adapter as CA

COMMIT = "a"*40
REPO = "990001"


def fact(level, title, commit=COMMIT, repo=REPO, path="README.md"):
    return {"rule_id": "README_HEADING_EXISTS", "fact_id": "SL-FACT-"+"a"*40,
            "repository_id": repo, "commit_sha": commit,
            "normalized_parameters": {"file_path": path,
                                      "subject": {"level": level, "title": title}}}


class TestClaimVerdict(unittest.TestCase):
    def _v(self, subject, facts, available=True, completeness="COMPLETE", parser_ok=True):
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=REPO,
            commit_sha=COMMIT, file_path="README.md", subject=subject)
        return CA.verify_content_claim(claim=c, facts=facts,
                                       content_available=available,
                                       completeness_status=completeness,
                                       parser_ok=parser_ok, subject_binding=b)

    def test_supported_exact_match(self):
        v = self._v({"level": 2, "title": "Installation"}, [fact(2, "Installation")])
        self.assertEqual(v["status"], "supported")

    def test_no_match_is_insufficient_not_refuted(self):
        """★ 阻断级：找不到 ≠ 被反驳。"""
        v = self._v({"level": 2, "title": "Nonexistent"}, [fact(2, "Installation")])
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "NO_MATCHING_FACT")

    def test_level_must_match(self):
        v = self._v({"level": 3, "title": "Installation"}, [fact(2, "Installation")])
        self.assertNotEqual(v["status"], "supported")

    def test_wrong_commit_insufficient(self):
        v = self._v({"level": 2, "title": "Installation"},
                    [fact(2, "Installation", commit="b"*40)])
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_wrong_repo_insufficient(self):
        v = self._v({"level": 2, "title": "Installation"},
                    [fact(2, "Installation", repo="1")])
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_partial_content_never_refutes(self):
        """★ 阻断级：不完整内容不得产生否定。"""
        v = self._v({"level": 2, "title": "Missing"}, [],
                    completeness="PARTIAL")
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "CONTENT_PARTIAL")

    def test_content_unavailable_insufficient(self):
        v = self._v({"level": 2, "title": "X"}, [], available=False)
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "CONTENT_UNAVAILABLE")

    def test_parser_failed_insufficient(self):
        v = self._v({"level": 2, "title": "X"}, [], parser_ok=False)
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "PARSER_FAILED")

    def test_absence_claim_confirmed_in_complete_scope(self):
        """否定型命题 + 完整内容 → 才可 supported。"""
        v = self._v({"level": 2, "title": "Missing"}, [],
                    completeness="COMPLETE")
        # expected_present 默认为 True → 应 insufficient
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_unsupported_type(self):
        c, b = CA.build_content_claim(
            claim_type="manifest_dependency_declared", repository_id=REPO,
            commit_sha=COMMIT, file_path="package.json",
            subject={"dependency": "lodash"})
        v = CA.verify_content_claim(claim=c, facts=[], content_available=True,
                                    completeness_status="COMPLETE",
                                    subject_binding=b)
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_contract_declared_for_each_type(self):
        for t in ("readme_heading_exists", "manifest_dependency_declared",
                  "manifest_field_present"):
            c = CA.claim_contract(t)
            self.assertIn("supported", c, t)
            self.assertIn("refuted", c, t)
            self.assertIn("insufficient", c, t)
            self.assertIn("forbidden", c, t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
