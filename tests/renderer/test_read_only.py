#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-23..T-31 / T-37：只读性、输出路径约束与执行追踪。"""
import sys, tempfile, shutil, unittest, json, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/renderer", "src/renderer", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import card_models as CM, card_renderer as CRD
import view_integrity as VI


class TestReadOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ro_"))
        self.ks = rfx.fresh(self.tmp)
        self.cards, self.src, self.res = rfx.make_cards(self.ks)
        self.assertTrue(len(self.cards) >= 1)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _render_all(self):
        for c in self.cards:
            CRD.render_json(c)
            CRD.render_card_html(c)

    def test_t25_a_layer_unchanged(self):
        before = VI.fingerprint_assets(self.ks)
        self.assertGreater(len(before), 0, "必须有资产（防空集合假通过）")
        self._render_all()
        self.assertEqual(before, VI.fingerprint_assets(self.ks),
                         "A 层资产指纹必须不变")

    def test_t26_b_pointer_unchanged(self):
        before = VI.fingerprint_pointers(self.ks)
        self._render_all()
        self.assertEqual(before, VI.fingerprint_pointers(self.ks))

    def test_t27_c_index_unchanged(self):
        before = VI.fingerprint_index(self.ks)
        self._render_all()
        self.assertEqual(before, VI.fingerprint_index(self.ks))

    def test_t28_checkpoint_unchanged(self):
        before = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='revalidation_run'"
        ).fetchone()["n"]
        self.assertGreater(before, 0)
        self._render_all()
        after = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='revalidation_run'"
        ).fetchone()["n"]
        self.assertEqual(before, after)

    def test_t29_operation_log_unchanged(self):
        before = VI.fingerprint_operation_log(self.ks)
        self.assertGreater(len(before), 0, "必须有 operation_log")
        self._render_all()
        self.assertEqual(before, VI.fingerprint_operation_log(self.ks))

    def test_t30_no_github_access(self):
        for mod in (CM, CRD):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            for bad in ("import requests", "urllib.request", "http.client",
                        "socket", "GitHubClient"):
                self.assertNotIn(bad, src, f"{mod.__name__} 不得引入 {bad}")

    def test_t31_no_ec_reverification(self):
        for mod in (CM, CRD):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            self.assertNotIn("verify_path_claim", src,
                             "渲染器不得重新裁决")
            self.assertNotIn("verify_", src.replace("verify_integrity", ""),
                             "渲染器不得调用任何 verifier")

    def test_negative_control_write_detected(self):
        """负向对照：指纹确实能抓到写入。"""
        before = VI.fingerprint_assets(self.ks)
        from asset_models import AssetDraft
        d = AssetDraft(asset_type="freshness_assessment",
                       logical_identity="SL-ASSESS-PROBE-" + "2" * 16,
                       repository_id=rfx.REPO,
                       payload={"probe": True, "assessment_id": "p"},
                       asset_version=1, operation_id="OP-PROBE-R")
        self.assertTrue(self.ks.append_asset_and_advance(
            d, expected_version=None).get("ok"))
        self.assertNotEqual(before, VI.fingerprint_assets(self.ks),
                            "指纹必须能检测写入")

    def test_t37_execution_stages_queryable(self):
        """P3C 八阶段记录必须真的可回查且非全 PENDING。"""
        row = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='revalidation_run' "
            "ORDER BY asset_version DESC LIMIT 1").fetchone()
        p = json.loads(row["payload_json"])
        stages = {s["stage"]: s["state"] for s in p["stages"]}
        self.assertEqual(len(stages), 8, "必须有 8 个阶段")
        self.assertNotEqual(set(stages.values()), {"PENDING"},
                             "阶段状态不得全部停在 PENDING")
        self.assertEqual(p["execution_status"], "SUCCESS")
        self.assertIn("target_claim_id", p)
        self.assertTrue(p["target_claim_id"], "target_claim_id 必须持久化")
        self.assertTrue(p.get("target_verification_id"))


class TestOutputPath(unittest.TestCase):
    """T-23 / T-24：受控输出路径不可逃逸、不能覆盖人工文档。"""

    def test_t23_path_cannot_escape_root(self):
        """受控输出目录：任何相对路径都不得逃逸出根。"""
        tmp = Path(tempfile.mkdtemp(prefix="op_"))
        try:
            root = tmp/"out"
            root.mkdir()
            root_res = root.resolve()
            escaped = []
            for bad in ("../escape", "../../escape", "/etc/passwd",
                        "a/../../../b", "sub/nested-ok"):
                target = (root/bad)
                try:
                    resolved = target.resolve()
                except Exception:
                    escaped.append(bad)
                    continue
                inside = (resolved == root_res) or (
                    str(resolved).startswith(str(root_res) + os.sep))
                if not inside:
                    escaped.append(bad)
            # 只有合法的嵌套路径允许
            self.assertNotIn("sub/nested-ok", escaped,
                             "合法子目录不应被误判为逃逸")
            for bad in ("../escape", "../../escape", "/etc/passwd",
                        "a/../../../b"):
                self.assertIn(bad, escaped, f"{bad} 必须被判为逃逸")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_t24_no_overwrite_manual_docs(self):
        """渲染器源文件不得含对人工文档路径的写入。"""
        for mod in (CM, CRD):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            self.assertNotIn("docs/fusion", src)
            self.assertNotIn("progress/", src)
            self.assertNotIn("write_text", src.replace(
                "OUT.write_text", ""), "渲染器自身不得写文件")


if __name__ == "__main__":
    unittest.main(verbosity=2)
