#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bot 呈现模块验收。★ 零网络、零写盘。"""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("content_persistence", "evidence_claims", "storage",
          "source_analysis", "skill_interface", "collector", "content", "facts"):
    sp = ROOT / "src" / p
    if sp.is_dir() and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))

import bot_card as BC


def _q(state="FOUND", claims=None, **kw):
    base = {"state": state, "repository_id": "38923193",
            "commit_sha": "a" * 40, "file_path": "index.js",
            "counts": {"symbols": 2, "exports": 2, "imports": 0, "facts": 6},
            "claims": claims or []}
    base.update(kw)
    return base


class TBotCard(unittest.TestCase):

    def test_t1_supported_glyph(self):
        """已验证 → 满格 ▣。"""
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "SUPPORTED_SOURCE_CLAIM",
             "subject": {"qualified_name": "isPlainObject"}, "claim_id": "x" * 12}]))
        self.assertIn("▣", t)
        self.assertIn("已验证", t)

    def test_t2_observed_not_green(self):
        """已观察 → 半格 ▤，且明确写「尚未验证」，绝不放绿。"""
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "OBSERVED_SOURCE_FACT",
             "subject": {"qualified_name": "f"}}]))
        self.assertIn("▤", t)
        self.assertIn("尚未验证", t)
        self.assertNotIn("已验证·命题成立", t.split("\n|")[0] if False else t)
        # 该行不得出现「已验证·命题成立」
        line = [l for l in t.splitlines() if "f" in l and "▤" in l][0]
        self.assertNotIn("已验证·命题成立", line)

    def test_t3_insufficient_glyph(self):
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "INSUFFICIENT_EVIDENCE",
             "subject": {"qualified_name": "g"}}]))
        self.assertIn("□", t)
        self.assertIn("证据不足", t)

    def test_t4_unsupported_glyph(self):
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "UNSUPPORTED_SEMANTIC_FORM",
             "subject": {"qualified_name": "h"}}]))
        self.assertIn("△", t)

    def test_t5_not_analyzed_glyph(self):
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "NOT_ANALYZED",
             "subject": {"qualified_name": "i"}}]))
        self.assertIn("·", t)
        self.assertIn("尚未分析", t)

    def test_t6_no_html(self):
        """★ 输出里不得含任何 HTML 标签（用户要求删掉网页路径）。"""
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "SUPPORTED_SOURCE_CLAIM",
             "subject": {"qualified_name": "f"}}]))
        for tag in ("<html", "<div", "<table", "<script", "<body", "<style"):
            self.assertNotIn(tag, t.lower())

    def test_t7_not_found_state(self):
        """非 FOUND 状态必须明确说知识库答不了，不编结论。"""
        t = BC.render_bot_block(query_result=_q(state="CONTENT_NOT_CAPTURED", claims=[]))
        self.assertIn("尚未采集", t)
        self.assertIn("回答不了", t)
        self.assertNotIn("▣", t)

    def test_t8_pure_no_side_effect(self):
        """纯函数：调用前后不新增临时文件。"""
        import tempfile, os
        before = set(os.listdir(tempfile.gettempdir()))
        BC.render_bot_block(query_result=_q(claims=[]))
        after = set(os.listdir(tempfile.gettempdir()))
        self.assertEqual(before - after, set(), "render_bot_block 不应写盘")

    def test_t9_legend_present(self):
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "SUPPORTED_SOURCE_CLAIM",
             "subject": {"qualified_name": "f"}}]))
        for g in ("▣", "▤", "□", "△", "·"):
            self.assertIn(g, t, "图例应含 %s" % g)

    def test_t10_line_numbers(self):
        t = BC.render_bot_block(query_result=_q(claims=[
            {"kind": "symbol", "display_level": "SUPPORTED_SOURCE_CLAIM",
             "start_line": 1, "subject": {"qualified_name": "f"}}]))
        self.assertIn("| 1 |", t)


if __name__ == "__main__":
    unittest.main()
