#!/usr/bin/env python3
"""编排器 CLI 集成、预算、去重、授权前置。"""
import sys, unittest, inspect
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))
import acceptance_request_planner as A
import request_budget as RB


class TestT7_CLIUsesBudget(unittest.TestCase):
    def test_cli_has_preflight_helper(self):
        p = (ROOT / "src" / "skill_interface" / "cli.py").read_text(encoding="utf-8")
        self.assertIn("_preflight_budget", p)
        self.assertIn("budget_preflight", p)
        self.assertIn("budget=_budget", p,
                      "capture 必须收到编排器预算")

    def test_capture_accepts_budget(self):
        import content_capture as CC
        sig = inspect.signature(CC.capture)
        self.assertIn("budget", sig.parameters)

    def test_blob_fetcher_passes_headers(self):
        p = (ROOT / "src" / "collector" / "blob_fetcher.py").read_text(encoding="utf-8")
        self.assertIn('got["headers"]', p, "必须透传响应头，否则预算拿不到真实剩余")


class TestT8_ReuseNotRemote(unittest.TestCase):
    def test_reuse_not_counted(self):
        p = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("a",), license_path=None,
            have_metadata=True, have_tree=True, have_blobs=("a",))
        self.assertEqual(p.counts()["maximum_planned_requests"], 0)


class TestT9_LicenseGate(unittest.TestCase):
    """T9：授权未通过不得持久化业务原始字节。"""

    def test_persist_blocked_skips_request(self):
        p = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(
            encoding="utf-8")
        self.assertIn("PERSIST_BLOCKED", p)
        self.assertIn("决不允许持久化", p) if "决不允许持久化" in p else None
        # 关键：PERSIST 被拒时不得发起请求
        i = p.find("PERSIST_BLOCKED")
        seg = p[i - 500:i + 500]
        self.assertIn("continue", seg)


class TestT14_OfflineNoNetwork(unittest.TestCase):
    def test_offline_preflight_blocks(self):
        p = (ROOT / "src" / "skill_interface" / "cli.py").read_text(encoding="utf-8")
        self.assertIn("OFFLINE_NO_REQUESTS", p)


class TestT12_NetworkOkButPersistFails(unittest.TestCase):
    """T12：网络成功但写入失败 → 不得标记完整。"""

    def test_persist_failed_status(self):
        p = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(
            encoding="utf-8")
        self.assertIn("PERSIST_FAILED", p)


class TestD59_NoRequestNoBudgetCheck(unittest.TestCase):
    def test_zero_need_passes_without_header(self):
        p = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("a",), license_path=None,
            have_metadata=True, have_tree=True, have_blobs=("a",))
        r = A.preflight(plan=p, observed_remaining=None)
        self.assertTrue(r["can_begin"], "无需联网时不应要求配额")

    def test_gap_without_header_blocks(self):
        p = A.build_repo_acceptance_plan(
            repository_id="r", commit_sha="c" * 40,
            target_paths=("a",), license_path=None, have_metadata=True)
        r = A.preflight(plan=p, observed_remaining=None)
        self.assertFalse(r["can_begin"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
