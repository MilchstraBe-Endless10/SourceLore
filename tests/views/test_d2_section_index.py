#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-D2 D2-B/C/D 专项测试：正文片段索引、身份隔离、授权边界、答案召回。

设计原则（Gate 10）：不依赖真实数据根、不联网；用内存 SQLite + 构造片段。
每个测试都能真实捕获本轮缺陷：
  - 修复前没有 section_fts → 索引缺失即报 SECTION_INDEX_MISSING（不伪造）；
  - 修复前 answer 不消费 content-sections → content_blocks=0；
  - 授权字段必须逐条透传，拒绝读取的正文不得被升级。
"""
import sys
import sqlite3
import unittest
from pathlib import Path

WT = str(Path(__file__).resolve().parents[2])
for sub in ("views", "skill_interface", "storage", "trust"):
    p = str(Path(WT) / "src" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
sys.path.insert(0, str(Path(WT) / "src"))

import section_index as SI  # noqa: E402


class FakeStore:
    """最小 sqlite 包装：section_index 只用 .conn。"""
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row


def _sec(sid, path, body, *, rid="r1", commit="c1", cp=False, da=False):
    return {
        "section_id": sid, "file_path": path, "heading": path,
        "body": body, "content_kind": "documentation_section",
        "source_category": "documentation_self_report",
        "content_asset_id": f"asset:{sid}",
        "content_sha256": f"sha256:{sid}",
        "git_blob_oid": f"oid:{sid}",
        "line_start": 10, "line_end": 12, "byte_start": 100, "byte_end": 200,
        "copy_permitted": cp, "distribution_allowed": da,
        "refs": [{"kind": "capture_ref", "content_sha256": f"sha256:{sid}"}],
    }


class TestSectionIndex(unittest.TestCase):
    def setUp(self):
        self.st = FakeStore()

    def tearDown(self):
        self.st.conn.close()

    def test_missing_index_reported_not_faked(self):
        r = SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["webdriver"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "SECTION_INDEX_MISSING")

    def test_rebuild_then_query_by_identity(self):
        r = SI.rebuild_section_index(
            self.st, repository_id="r1", commit_sha="c1",
            sections=[_sec("a", "README.md", "WebDriver crate renderer"),
                      _sec("b", "docs/Cdp.md", "CDP request flow")])
        self.assertTrue(r["ok"])
        self.assertEqual(r["indexed"], 2)
        qr = SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                               terms=["webdriver"])
        self.assertTrue(qr["ok"])
        self.assertEqual(len(qr["matches"]), 1)
        self.assertEqual(qr["matches"][0]["file_path"], "README.md")
        self.assertEqual(qr["matches"][0]["line_start"], 10)

    def test_repo_and_commit_isolation(self):
        # 两个身份各写一段不同正文；跨身份查询不得串用
        SI.rebuild_section_index(self.st, repository_id="r1", commit_sha="c1",
                                 sections=[_sec("a", "a.md", "ALPHA-ONLY")])
        SI.rebuild_section_index(self.st, repository_id="r1", commit_sha="c2",
                                 sections=[_sec("b", "b.md", "BETA-ONLY")])
        SI.rebuild_section_index(self.st, repository_id="r2", commit_sha="c1",
                                 sections=[_sec("c", "c.md", "GAMMA-ONLY")])
        self.assertEqual(
            SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["alpha-only"])["matches"][0]["body"],
            "ALPHA-ONLY")
        self.assertEqual(
            SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["beta-only"])["matches"], [])
        self.assertEqual(
            SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["gamma-only"])["matches"], [])
        st = SI.index_stats(self.st)
        self.assertEqual(len(st["identities"]), 3)

    def test_rebuild_is_idempotent_and_scoped(self):
        SI.rebuild_section_index(self.st, repository_id="r1", commit_sha="c1",
                                 sections=[_sec("a", "a.md", "WebDriver")])
        r = SI.rebuild_section_index(self.st, repository_id="r1", commit_sha="c1",
                                     sections=[_sec("b", "b.md", "CDP")])
        self.assertEqual(r["removed"], 1)
        self.assertEqual(r["present"], 1)
        self.assertEqual(
            SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["webdriver"])["matches"], [])
        self.assertEqual(
            len(SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                                  terms=["cdp"])["matches"]), 1)

    def test_authorization_flags_pass_through(self):
        SI.rebuild_section_index(
            self.st, repository_id="r1", commit_sha="c1",
            sections=[_sec("deny", "deny.md", "SECRET-TERM", cp=False, da=False),
                      _sec("ok", "ok.md", "PUBLIC-TERM", cp=True, da=True)])
        d = SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["secret-term"])["matches"][0]
        self.assertFalse(d["copy_permitted"])
        self.assertFalse(d["distribution_allowed"])
        o = SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["public-term"])["matches"][0]
        self.assertTrue(o["copy_permitted"])
        self.assertTrue(o["distribution_allowed"])

    def test_byte_offset_and_ref_carried(self):
        SI.rebuild_section_index(self.st, repository_id="r1", commit_sha="c1",
                                 sections=[_sec("a", "a.md", "WebDriver")])
        m = SI.query_sections(self.st, repository_id="r1", commit_sha="c1",
                              terms=["webdriver"])["matches"][0]
        self.assertEqual(m["byte_start"], 100)
        self.assertEqual(m["byte_end"], 200)
        self.assertEqual(m["content_sha256"], "sha256:a")
        self.assertEqual(m["git_blob_oid"], "oid:a")
        self.assertTrue(m["refs"])

    def test_zh_concept_maps_to_en_term(self):
        terms = SI.extract_terms("如何安装和从源码构建？")
        self.assertIn("build", terms)
        self.assertIn("install", terms)
        terms2 = SI.extract_terms("渲染机制是怎样工作的？")
        self.assertIn("renderer", terms2)

    def test_generic_english_markdown_section(self):
        # Gate 8：非 Obscura 的独立英文构造样例也能召回
        SI.rebuild_section_index(
            self.st, repository_id="fixture", commit_sha="fix1",
            sections=[_sec("s", "notes.md", "The renderer module handles requests")])
        qr = SI.query_sections(self.st, repository_id="fixture", commit_sha="fix1",
                               terms=["renderer"])
        self.assertEqual(len(qr["matches"]), 1)
        self.assertEqual(qr["matches"][0]["file_path"], "notes.md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
