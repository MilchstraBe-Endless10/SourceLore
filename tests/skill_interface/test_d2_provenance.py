#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-D2 D2-D 来源标记专项测试（离线，零网络，零真实库写入）。

捕获缺陷：修复前 content_capture.capture 把真实远程采集字节硬编码成
SYNTHETIC_FIXTURE（P2-D1 PROVENANCE_DEFECT）。负例确保不把合成夹具冒充真实。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "skill_interface"))
sys.path.insert(0, str(ROOT / "src" / "collector"))
sys.path.insert(0, str(ROOT / "src"))

import content_capture as CC  # noqa: E402


class TestProvenanceContract(unittest.TestCase):
    def test_source_has_no_hardcoded_fixture_at_ingest(self):
        src = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(encoding="utf-8")
        # 生产采集入口不得再把 provenance 硬编码成 SYNTHETIC_FIXTURE
        self.assertNotIn('provenance_level="SYNTHETIC_FIXTURE",\n            )', src)
        self.assertNotIn('report["provenance"] = "SYNTHETIC_FIXTURE"', src)
        self.assertIn("provenance_level=blob_prov", src)
        self.assertIn('report["provenance"] =', src)

    def test_default_is_unverified_until_authorized(self):
        # ★ D3-00 根因修复：不再无条件硬编码 AUTHORIZED_REMOTE_SOURCE。
        #   默认未验证；只有真正通过授权门禁 + 字节校验才升级（见 capture）。
        self.assertEqual(CC.resolve_provenance(None), "UNVERIFIED_REMOTE_SOURCE")
        self.assertEqual(CC.resolve_provenance(""), "UNVERIFIED_REMOTE_SOURCE")

    def test_authorized_constant_still_exists_for_verified_writes(self):
        self.assertEqual(CC.PROVENANCE_AUTHORIZED_REMOTE, "AUTHORIZED_REMOTE_SOURCE")
        self.assertEqual(CC.PROVENANCE_UNVERIFIED_REMOTE, "UNVERIFIED_REMOTE_SOURCE")
        self.assertEqual(CC.PROVENANCE_SYNTHETIC, "SYNTHETIC_FIXTURE")

    def test_explicit_fixture_preserved_as_negative_case(self):
        # 负例：只有显式声明 synthetic 才是合成夹具，不把真实字节降级
        self.assertEqual(CC.resolve_provenance("SYNTHETIC_FIXTURE"),
                         "SYNTHETIC_FIXTURE")

    def test_declared_switches_still_intact(self):
        # 不破坏既有预算语义（B3 回归）
        src = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(encoding="utf-8")
        self.assertIn("byte_budget = {\"used_bytes\": 0, \"paths\": 0}", src)
        self.assertIn("budget.can_spend(1)", src)
        self.assertIn("budget.consume(", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
