#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-29..T-35：只读性实测。"""
import sys, tempfile, shutil, unittest, json, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/views", "src/views", "src/lifecycle", "src/storage",
          "src/collector", "src/facts", "src/evidence_claims", "src/runtime"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import vfx
import knowledge_view_assembler as KVA
import view_integrity as VI


class TestReadOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ro_"))
        self.ks = vfx.fresh(self.tmp)
        self.src, self.cand, self.res, self.ad = vfx.run_full(self.ks)
        self.assertTrue(self.res.ok, (self.res.error_code, self.res.detail))
        self.vid = self.res.payload["target_verification_id"]

    def tearDown(self):
        if getattr(self, "ks", None) is not None:
            try: self.ks.close()
            except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_t29_a_layer_fingerprint_unchanged(self):
        before = VI.fingerprint_assets(self.ks)
        self.assertGreater(len(before), 0, "必须有资产（防空集合假通过）")
        KVA.assemble_from_verification(
            self.ks, verification_id=self.vid, repository_id=vfx.REPO)
        after = VI.fingerprint_assets(self.ks)
        self.assertEqual(before, after, "A 层资产指纹必须完全不变")

    def test_t30_b_pointer_version_unchanged(self):
        before = VI.fingerprint_pointers(self.ks)
        KVA.assemble_from_verification(
            self.ks, verification_id=self.vid, repository_id=vfx.REPO)
        after = VI.fingerprint_pointers(self.ks)
        self.assertEqual(before, after, "B 层指针版本必须不变")

    def test_t31_c_index_unchanged(self):
        before = VI.fingerprint_index(self.ks)
        KVA.assemble_from_verification(
            self.ks, verification_id=self.vid, repository_id=vfx.REPO)
        after = VI.fingerprint_index(self.ks)
        self.assertEqual(before, after, "C 层索引必须不变")

    def test_t32_checkpoint_unchanged(self):
        before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='revalidation_run'"
        ).fetchone()["n"]
        KVA.assemble_from_verification(
            self.ks, verification_id=self.vid, repository_id=vfx.REPO)
        after = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='revalidation_run'"
        ).fetchone()["n"]
        self.assertEqual(before, after, "checkpoint 必须不变")

    def test_t33_operation_log_unchanged(self):
        before = VI.fingerprint_operation_log(self.ks)
        self.assertGreater(len(before), 0, "必须有 operation_log（防空集合假通过）")
        KVA.assemble_from_verification(
            self.ks, verification_id=self.vid, repository_id=vfx.REPO)
        after = VI.fingerprint_operation_log(self.ks)
        self.assertEqual(before, after, "不得新增 operation_log")

    def test_t34_no_collector_call(self):
        """装配时不得调用 Collector。"""
        calls_before = list(self.ad.calls)
        KVA.assemble_from_verification(
            self.ks, verification_id=self.vid, repository_id=vfx.REPO)
        self.assertEqual(self.ad.calls, calls_before,
                         "装配期间 Collector 调用列表不得变化")

    def test_t35_no_network(self):
        """模块不得引入任何网络客户端。"""
        import knowledge_view_assembler as m1
        import view_integrity as m2
        for mod in (m1, m2):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            for bad in ("import requests", "urllib.request",
                        "http.client", "socket", "GitHubClient"):
                self.assertNotIn(bad, src,
                                 f"{mod.__name__} 不得引入 {bad}")

    def test_repeated_assembly_no_new_asset(self):
        n_before = len(VI.fingerprint_assets(self.ks))
        for _ in range(3):
            KVA.assemble_from_verification(
                self.ks, verification_id=self.vid, repository_id=vfx.REPO)
        n_after = len(VI.fingerprint_assets(self.ks))
        self.assertEqual(n_before, n_after, "重复装配不得新增资产")

    def test_negative_control_write_would_be_detected(self):
        """负向对照：确认指纹真的能抓到写入（证明上面的"不变"不是空转）。"""
        before = VI.fingerprint_assets(self.ks)
        from asset_models import AssetDraft
        import lc_models as L
        draft = AssetDraft(
            asset_type="freshness_assessment",
            logical_identity="SL-ASSESS-PROBE-" + "1" * 16,
            repository_id=vfx.REPO,
            payload={"probe": True, "assessment_id": "probe"},
            asset_version=1, operation_id="OP-PROBE-WRITE")
        r = self.ks.append_asset_and_advance(draft, expected_version=None)
        after = VI.fingerprint_assets(self.ks)
        self.assertTrue(r.get("ok"), r)
        self.assertNotEqual(before, after,
                            "指纹必须能检测到写入（否则只读断言是假的）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
