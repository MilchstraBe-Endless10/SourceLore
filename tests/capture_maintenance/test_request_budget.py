#!/usr/bin/env python3
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "collector"))
sys.path.insert(0, str(ROOT / "tests" / "capture_maintenance"))
import request_budget as RB
from gold.capture_gold import GOLD


class TestRegistry(unittest.TestCase):
    def test_cases(self):
        self.assertGreaterEqual(len(GOLD), 25 - 2)
        ids = [g[0] for g in GOLD]
        self.assertEqual(len(ids), len(set(ids)))


class TestClassification(unittest.TestCase):
    def test_R09_primary(self):
        self.assertEqual(RB.classify_rate_limit(
            status=403, headers={"X-RateLimit-Remaining": "0",
                                 "X-RateLimit-Limit": "60",
                                 "X-RateLimit-Used": "60"}), RB.PRIMARY)

    def test_R10_secondary(self):
        self.assertEqual(RB.classify_rate_limit(
            status=403, headers={"Retry-After": "120",
                                 "X-RateLimit-Remaining": "44"}),
            RB.SECONDARY)

    def test_R12_no_guess(self):
        self.assertEqual(RB.classify_rate_limit(status=403, headers={}),
                         RB.UNKNOWN_KIND)

    def test_R11_reset_from_header(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        obs = b.observe(headers={"X-RateLimit-Reset": "1793942591",
                                 "X-RateLimit-Remaining": "10"}, status=200)
        self.assertEqual(b.reset_at, 1793942591)
        self.assertEqual(obs["reset_at"], 1793942591)

    def test_R13_header_wins(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        b.observe(headers={"X-RateLimit-Remaining": "45"}, status=200)
        b.consume(headers={"X-RateLimit-Remaining": "12"}, status=200)
        self.assertEqual(b.effective_remaining(), 12,
                         "必须采用最近响应头，而非 60-自己计数")


class TestBudget(unittest.TestCase):
    def test_R06_can_spend(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        b.observe(headers={"X-RateLimit-Remaining": "45"}, status=200)
        self.assertEqual(b.can_spend(1), (True, RB.BUDGET_OK))

    def test_R07_insufficient_without_header(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        self.assertEqual(b.can_spend(1)[1], RB.BUDGET_INSUFFICIENT,
                         "没有权威响应头时宁可不发")

    def test_R08_reserve_enforced(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e", reserve_requests=5)
        b.observe(headers={"X-RateLimit-Remaining": "4"}, status=200)
        self.assertFalse(b.can_spend(1)[0])
        b2 = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                    execution_id="e", reserve_requests=5)
        b2.observe(headers={"X-RateLimit-Remaining": "6"}, status=200)
        self.assertTrue(b2.can_spend(1)[0])

    def test_local_limit(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e", request_limit=1)
        b.observe(headers={"X-RateLimit-Remaining": "45"}, status=200)
        b.consumed_requests = 1
        self.assertEqual(b.can_spend(1)[1], RB.BUDGET_EXHAUSTED)

    def test_rate_limited_blocks(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        b.observe(headers={"X-RateLimit-Remaining": "0",
                           "X-RateLimit-Limit": "60",
                           "X-RateLimit-Used": "60"}, status=403)
        self.assertFalse(b.can_spend(1)[0])

    def test_estimated_not_official(self):
        d = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e").to_dict()
        self.assertFalse(d["authoritative_remaining_is_from_headers"])

    def test_planned_count(self):
        b = RB.GitHubRequestBudget(repository_id="r", commit_sha="c",
                                   execution_id="e")
        b.add_plan_item(endpoint="/a", intended_object="x", purpose="p")
        b.add_plan_item(endpoint="/b", intended_object="y", purpose="p",
                        required=False)
        self.assertEqual(b.planned_requests, 1, "可选项不计入必做预算")


if __name__ == "__main__":
    unittest.main(verbosity=2)
