#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D3-00 §1.2 来源标记根因修复专项（离线、零网络、零真实库写入）。

捕获缺陷：P2-D2 把硬编码 SYNTHETIC_FIXTURE 换成硬编码
AUTHORIZED_REMOTE_SOURCE，属于"一种默认值替换另一种"。本轮要求：
来源等级必须由实际授权门禁 + 字节校验决定，默认不宣称已授权。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "skill_interface"))
sys.path.insert(0, str(ROOT / "src" / "collector"))
sys.path.insert(0, str(ROOT / "src"))

import content_capture as CC  # noqa: E402


class TestD3ProvenanceGate(unittest.TestCase):
    def test_no_unconditional_authorized_default(self):
        # 默认必须是未验证，不能无条件宣称 AUTHORIZED_REMOTE_SOURCE
        self.assertNotEqual(CC.resolve_provenance(None), "AUTHORIZED_REMOTE_SOURCE")
        self.assertEqual(CC.resolve_provenance(None), "UNVERIFIED_REMOTE_SOURCE")

    def test_upgrade_is_conditional_on_persisted_blobs(self):
        src = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(encoding="utf-8")
        # 升级条件必须依赖实际落盘计数，而不是无条件赋值
        self.assertIn('elif report["persisted_blobs"] > 0', src)
        self.assertIn('report["reused_blobs"] > 0', src)
        self.assertIn('else:\n            report["provenance"] = PROVENANCE_UNVERIFIED_REMOTE', src)
        # 写入 provenance 必须由逐 blob 判定决定
        self.assertIn("blob_prov = (provenance_level if provenance_level", src)
        self.assertIn("provenance_level=blob_prov", src)

    def test_explicit_synthetic_never_upgraded(self):
        # 负例：显式 fixture 即使有成功写入也不得升级为已授权
        self.assertEqual(CC.resolve_provenance("SYNTHETIC_FIXTURE"),
                         "SYNTHETIC_FIXTURE")
        self.assertEqual(CC.resolve_provenance("AUTHORIZED_LOCAL_FIXTURE"),
                         "AUTHORIZED_LOCAL_FIXTURE")

    def test_provenance_basis_recorded(self):
        src = (ROOT / "src" / "skill_interface" / "content_capture.py").read_text(encoding="utf-8")
        self.assertIn('"provenance_basis"', src)
        self.assertIn("derived_from_authorization_and_hash_check", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
