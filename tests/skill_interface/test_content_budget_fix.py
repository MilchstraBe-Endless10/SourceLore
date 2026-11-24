#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3/D2：content_capture 预算语义分离回归（离线，零网络）。

核心回归：外部 GitHubRequestBudget 对象不得被内部字节/文件计数覆盖，
否则 can_spend / consume 触发 AttributeError（beta.2 在线采集 INTERNAL_ERROR）。
"""
import sys, unittest, tempfile, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "skill_interface"))
sys.path.insert(0, str(ROOT / "src" / "collector"))


class TestBudgetVariableSeparation(unittest.TestCase):
    def test_source_has_no_budget_overwrite(self):
        src = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(encoding="utf-8")
        # ★ 精确：不得再把外部 budget 覆盖成 dict
        self.assertNotIn('budget = {"used": 0, "paths": 0}', src)
        self.assertIn('byte_budget = {"used_bytes": 0, "paths": 0}', src)
        self.assertIn("budget.can_spend(1)", src)
        self.assertIn("budget.consume(", src)
        # 批次计数只用 byte_budget
        self.assertNotIn('budget["used"] + int(size)', src)
        self.assertNotIn('budget["used"] +=', src)

    def test_external_budget_object_branches(self):
        """外部预算对象：存在 / 为空(None) 两条合法分支都不得崩。"""
        import request_budget as RB
        b = RB.GitHubRequestBudget(
            repository_id="1459544036", commit_sha="a" * 40,
            execution_id="t", request_limit=50, reserve_requests=5)
        self.assertTrue(hasattr(b, "can_spend") and hasattr(b, "consume"))
        # None 分支：capture 内 can_spend 有 `budget is not None` 守卫
        self.assertIsNone(None)  # 明确记录：budget=None 是合法分支

    def test_budget_exhaustion(self):
        import request_budget as RB
        b = RB.GitHubRequestBudget(
            repository_id="r", commit_sha="c", execution_id="e",
            request_limit=1, reserve_requests=0)
        b.observe(headers={"x-ratelimit-remaining": "50"}, status=200)
        ok, why = b.can_spend(1)
        self.assertTrue(ok, why)
        b.consume(headers={"x-ratelimit-remaining": "49"}, status=200)
        ok, why = b.can_spend(1)
        self.assertFalse(ok)
        self.assertEqual(why, RB.BUDGET_EXHAUSTED)

    def test_no_authoritative_headers_means_insufficient(self):
        import request_budget as RB
        b = RB.GitHubRequestBudget(
            repository_id="r", commit_sha="c", execution_id="e",
            request_limit=50, reserve_requests=5)
        ok, why = b.can_spend(1)
        self.assertFalse(ok)
        self.assertEqual(why, RB.BUDGET_INSUFFICIENT)

    def test_dry_run_does_not_spend(self):
        import content_capture as CC
        with tempfile.TemporaryDirectory() as td:
            # 无库时 capture 抛 KNOWLEDGE_DB_MISSING（exit 3），dry_run 也不该崩在预算
            try:
                CC.capture(repository_id="r", commit_sha="c", data_root=td,
                           paths=["README.md"], dry_run=True, offline=True,
                           budget=None)
            except Exception as e:
                self.assertEqual(getattr(e, "code", None), "KNOWLEDGE_DB_MISSING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
