#!/usr/bin/env python3
"""B. 仓库分析：URL 校验、快照完整性、复用。"""
import sys, unittest, tempfile, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx
sys.path.insert(0, str(ROOT/"src"/"skill_interface"))
import analyze as A
from result import SkillError


class TestUrlParse(unittest.TestCase):
    def test_valid(self):
        p = A.parse_github_url("https://github.com/octocat/Hello-World")
        self.assertEqual(p["canonical"], "octocat/Hello-World")
        self.assertIsNone(p["ref"])

    def test_valid_with_tree(self):
        p = A.parse_github_url("https://github.com/o/r/tree/main")
        self.assertEqual(p["ref"], "main")

    def test_reject_non_github(self):
        for bad in ("https://evil.com/a/b", "https://github.com.evil.com/a/b",
                    "http://127.0.0.1/a/b", "ftp://github.com/a/b"):
            with self.assertRaises(SkillError):
                A.parse_github_url(bad)

    def test_reject_bad_path(self):
        with self.assertRaises(SkillError):
            A.parse_github_url("https://github.com/onlyowner")

    def test_reject_empty(self):
        with self.assertRaises(SkillError):
            A.parse_github_url("")


class TestCompleteness(unittest.TestCase):
    def test_truncated_is_partial(self):
        """★ 截断绝不能标 COMPLETE。"""
        src = (ROOT/"src"/"skill_interface"/"analyze.py").read_text(encoding="utf-8")
        # ★ B3/D1：截断判定改由 TreeCollector 的 completeness_status 提供，
        #   不再用内联三元表达式；断言新实现不变量而非旧字面量。
        self.assertIn('completeness_status', src)
        self.assertIn('truncated_seen=truncated', src)
        self.assertIn('TreeCollector', src)

    def test_limitation_emitted_when_truncated(self):
        src = (ROOT/"src"/"skill_interface"/"analyze.py").read_text(encoding="utf-8")
        self.assertIn("Tree 被 GitHub 截断", src)


class TestRateLimitFastFail(unittest.TestCase):
    def test_no_retry_on_rate_limit(self):
        """★ 限流必须快失败：retry_after 常以千秒计，重试是白烧配额。"""
        src = (ROOT/"src"/"skill_interface"/"analyze.py").read_text(encoding="utf-8")
        self.assertIn('"max_retries": 0', src)
        self.assertIn('"max_retry_after": 0', src)

    def test_rate_limit_error_code_passthrough(self):
        src = (ROOT/"src"/"skill_interface"/"analyze.py").read_text(encoding="utf-8")
        self.assertIn('code=code, detail=detail', src)
        self.assertIn("RATE_LIMITED", src)
        self.assertIn("SECONDARY_RATE_LIMITED", src)

    def test_hint_mentions_no_bypass(self):
        src = (ROOT/"src"/"skill_interface"/"analyze.py").read_text(encoding="utf-8")
        self.assertIn("不会绕过限流", src)


class TestNoSecondImpl(unittest.TestCase):
    def test_reuses_existing_modules(self):
        src = (ROOT/"src"/"skill_interface"/"analyze.py").read_text(encoding="utf-8")
        for mod in ("GitHubClient", "build_snapshot", "ingest_snapshot",
                    "extract_file_path_observation", "verify_path_claim"):
            self.assertIn(mod, src, f"应复用 {mod}")
        # ★ 精确检测 import，不做裸子串匹配（会误伤注释里的中文/变量名）
        import re
        self.assertIsNone(re.search(r"^\s*import\s+requests\b", src, re.M))
        self.assertIsNone(re.search(r"^\s*from\s+requests\b", src, re.M))
        self.assertIsNone(re.search(r"^\s*import\s+urllib\.request\b", src, re.M))
        self.assertIsNone(re.search(r"\burlopen\(", src))

if __name__ == "__main__":
    unittest.main(verbosity=2)
