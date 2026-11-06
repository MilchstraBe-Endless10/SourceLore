#!/usr/bin/env python3
"""守护：每个 CLI 开关都必须在函数体里被真正读过一次。

★ D-46（license_known）、D-60（--resume）都是「argparse 有定义、函数体零引用」。
  不报错、不崩溃，只是静默地什么都不做。这条测试专门防它复发。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "src" / "skill_interface" / "cli.py"


class TestDeclaredSwitches(unittest.TestCase):
    def setUp(self):
        self.text = CLI.read_text(encoding="utf-8")
        # 收集所有 add_argument 定义的开关名
        self.flags = set()
        for m in re.finditer(r'add_argument\("(--[a-z0-9-]+)"', self.text):
            self.flags.add(m.group(1))

    def test_all_flags_read(self):
        """每个开关都必须在 getattr(args, ...) 或 args.X 里被读过。"""
        dead = []
        for f in sorted(self.flags):
            key = f.lstrip("-").replace("-", "_")
            if ("getattr(args, \"%s\"" % key) in self.text:
                continue
            if ("args.%s" % key) in self.text:
                continue
            dead.append(f)
        self.assertEqual(dead, [], "以下开关只在 argparse 里定义、函数体零引用：%s" % dead)

    def test_resume_wired(self):
        self.assertIn('args, "resume"', self.text)
        self.assertIn("capture_resume_report", self.text)

    def test_license_known_wired(self):
        self.assertIn('args, "license_known"', self.text)

    def test_plan_wired(self):
        self.assertIn('args, "plan"', self.text)


class TestCaptureParams(unittest.TestCase):
    """content_capture 的每个参数也必须被真正使用。"""

    def test_budget_used(self):
        p = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(
            encoding="utf-8")
        self.assertIn("if budget is not None", p, "budget 必须真被读")
        self.assertIn("budget.can_spend", p)
        self.assertIn("budget.consume", p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
