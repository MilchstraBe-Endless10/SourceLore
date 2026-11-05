#!/usr/bin/env python3
"""内容卡片：模型、安全、诊断降级。"""
import sys, unittest, re, html
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_skill"))
import sfx
import content_card_models as CM
import content_card_renderer as CR


def good_query():
    return {
        "state": "SUPPORTED", "repository_id": "990001",
        "commit_sha": "a"*40, "file_path": "README.md",
        "source_snapshot_id": "SL-A-SNAP-1",
        "content_availability": "CAPTURED_VERIFIED",
        "provenance_level": "AUTHORIZED_LOCAL_FIXTURE",
        "review_status": "PENDING_REVIEW", "freshness_state": "OBSERVED_AT_COMMIT",
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "captured": [{"file_path": "README.md", "commit_sha": "a"*40,
                      "content_asset_id": "SL-A-x", "git_blob_oid": "b"*40,
                      "content_sha256": "sha256:"+"0"*64,
                      "raw_byte_length": 120,
                      "verify_status": "CONTENT_AVAILABLE_VERIFIED",
                      "acquisition_policy": "ACQUISITION_ALLOWED"}],
        "facts": [{"fact_id": "SL-FACT-"+"a"*40,
                   "rule_id": "README_HEADING_EXISTS",
                   "rule_version": "content-facts/1",
                   "subject": {"level": 2, "title": "Installation"},
                   "git_blob_oid": "b"*40, "content_asset_id": "SL-A-x",
                   "content_sha256": "sha256:"+"0"*64,
                   "parser_version": "1.0.0",
                   "start_byte": 30, "end_byte": 44,
                   "start_line": 5, "end_line": 5,
                   "observation_id": "SL-OBS-"+"c"*40,
                   "commit_sha": "a"*40}],
        "claims": [{"claim_id": "SL-CLAIM-"+"d"*40}],
        "verifications": [{"verification_id": "SL-VERIF-"+"e"*40,
                           "status": "supported",
                           "status_reason": None}],
        "limitations": [], "network_requests": 0,
    }


class TestCardModel(unittest.TestCase):
    def test_readme_card(self):
        m = CM.build_content_card(good_query())
        self.assertEqual(m["card_type"], CM.README_CARD)
        self.assertIn("标题存在 ≠ 项目功能已实现", m["limitations"])

    def test_manifest_card(self):
        q = good_query(); q["file_path"] = "package.json"
        m = CM.build_content_card(q)
        self.assertEqual(m["card_type"], CM.MANIFEST_CARD)
        self.assertIn("声明依赖 ≠ 依赖已安装", m["limitations"])
        self.assertIn("存在测试命令 ≠ 测试已通过", m["limitations"])

    def test_no_facts_gives_error_card(self):
        q = good_query(); q["facts"] = []
        m = CM.build_content_card(q)
        self.assertEqual(m["card_type"], CM.ERROR_CARD)

    def test_incomplete_chain_gives_error_card(self):
        """★ 证据链不完整 → 只能出诊断卡。"""
        q = good_query()
        q["captured"][0]["verify_status"] = "CONTENT_INTEGRITY_FAILED"
        m = CM.build_content_card(q)
        self.assertEqual(m["card_type"], CM.ERROR_CARD)

    def test_fact_missing_blob_gives_error(self):
        q = good_query(); q["facts"][0]["git_blob_oid"] = None
        m = CM.build_content_card(q)
        self.assertEqual(m["card_type"], CM.ERROR_CARD)

    def test_fact_missing_range_gives_error(self):
        q = good_query(); q["facts"][0]["start_byte"] = None
        m = CM.build_content_card(q)
        self.assertEqual(m["card_type"], CM.ERROR_CARD)

    def test_commit_mismatch_gives_error(self):
        q = good_query(); q["facts"][0]["commit_sha"] = "f"*40
        m = CM.build_content_card(q)
        self.assertEqual(m["card_type"], CM.ERROR_CARD)

    def test_card_id_deterministic(self):
        a = CM.build_content_card(good_query())["card_id"]
        b = CM.build_content_card(good_query())["card_id"]
        self.assertEqual(a, b)

    def test_evidence_label_no_raw_text(self):
        """★ D-6 回归：label 不得回显原文。"""
        for f in CM.build_content_card(good_query())["facts"]:
            self.assertNotIn("Installation", f["evidence_label"])
            self.assertIn("README_HEADING_EXISTS", f["evidence_label"])


class TestCardRender(unittest.TestCase):
    def test_runnable_html(self):
        h = CR.render_content_card_html(CM.build_content_card(good_query()))
        self.assertTrue(h.startswith("<!DOCTYPE html>"))
        self.assertIn("Content-Security-Policy", h)

    def test_no_script(self):
        h = CR.render_content_card_html(CM.build_content_card(good_query()))
        self.assertNotIn("<script", h.lower())
        self.assertIsNone(re.search(r"\son[a-z]+\s*=", h, re.I))

    def test_contains_required_sections(self):
        h = CR.render_content_card_html(CM.build_content_card(good_query()))
        for s in ("仓库与文件身份", "内容知识概览", "已登记的结构化事实",
                  "证据定位", "限制与免责", "Git Blob OID", "distribution_allowed"):
            self.assertIn(s, h, s)

    def test_long_sha_wrappable(self):
        h = CR.render_content_card_html(CM.build_content_card(good_query()))
        self.assertIn('.mono', h)

    def test_html_escape(self):
        q = good_query()
        q["facts"][0]["subject"] = {"level": 1, "title": "<script>alert(1)</script>"}
        h = CR.render_content_card_html(CM.build_content_card(q))
        self.assertNotIn("<script>alert", h)
        self.assertIn("&lt;script&gt;", h)

    def test_error_card_render(self):
        q = good_query(); q["facts"] = []
        h = CR.render_content_card_html(CM.build_content_card(q))
        self.assertIn("证据链不完整", h)

    def test_distribution_restrictions_shown(self):
        h = CR.render_content_card_html(CM.build_content_card(good_query()))
        self.assertIn("False", h)

    def test_deterministic_output(self):
        a = CR.render_content_card_html(CM.build_content_card(good_query()))
        b = CR.render_content_card_html(CM.build_content_card(good_query()))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
