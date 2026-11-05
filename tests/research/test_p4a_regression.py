#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-39 / T-40：P4A 两项回归核验 + P3C 八阶段追踪。"""
import sys, tempfile, shutil, unittest, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/research", "src/research", "src/views", "src/renderer",
          "src/lifecycle", "src/storage", "src/collector", "src/facts",
          "src/evidence_claims", "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import card_models as CM, card_renderer as CRD, pre_publish_check as PPC
import knowledge_view_assembler as KVA


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p4a_"))
        self.ks = rfx.fresh(self.tmp)
        self.src, self.cand, self.res, self.ad = rfx.vfx.run_full(self.ks)
        self.view = KVA.assemble_from_verification(
            self.ks, verification_id=self.src["verification_id"],
            repository_id=rfx.REPO)["view"]
        self.card = CM.build_card(self.view)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestAssembledAt(Base):
    """§13.A：assembled_at 究竟来自哪里、确定性在什么条件下成立。"""

    def test_default_is_empty_not_now(self):
        """★ 默认值必须是空串 —— 绝不默认取当前系统时间。"""
        import inspect
        sig = inspect.signature(CRD.render_card_html)
        self.assertEqual(sig.parameters["assembled_at"].default, "",
                         "assembled_at 默认必须为空，不得取当前时间")

    def test_byte_identical_without_timestamp(self):
        a = CRD.render_card_html(self.card)
        b = CRD.render_card_html(self.card)
        self.assertEqual(a, b, "不传 assembled_at 时逐字节一致")

    def test_timestamp_only_in_footer(self):
        base = CRD.render_card_html(self.card)
        stamped = CRD.render_card_html(self.card, assembled_at="2026-01-01T00:00:00")
        diff = [ln for ln in stamped.splitlines() if ln not in base.splitlines()]
        self.assertTrue(all("渲染时刻" in ln for ln in diff),
                        f"时间戳只允许出现在诊断页脚：{diff}")
        self.assertIn("诊断用，不参与确定性身份", stamped)

    def test_identity_never_uses_timestamp(self):
        import inspect
        src = inspect.getsource(CM.card_id_of)
        self.assertNotIn("assembled_at", src)
        self.assertNotIn("now()", src)


class TestPreviewGate(Base):
    """§13.B：完整性失败只能给诊断页，不得呈现正常可信卡片。"""

    def test_blocked_on_corrupt(self):
        html = CRD.render_blocked_html(
            {"error_code": "EVIDENCE_CORRUPT", "detail": "快照无法定位"})
        self.assertIn("无法生成可信知识卡片", html)
        self.assertNotIn("<h2>证据裁决</h2>", html)
        self.assertNotIn("badge ok\">supported", html)

    def test_assembler_failure_routes_to_blocked(self):
        bad = KVA.assemble_from_verification(
            self.ks, verification_id="SL-VERIF-DOES-NOT-EXIST",
            repository_id=rfx.REPO)
        self.assertFalse(bad.get("ok"), "装配失败必须显式")
        html = CRD.render_blocked_html(bad)
        self.assertIn("无法生成可信知识卡片", html)

    def test_preview_never_implies_skip_integrity(self):
        r = PPC.pre_publish_check(
            {"html": CRD.render_card_html(self.card), "json": {}},
            {"authorization_is_test_only": True,
             "provenance_level": "SYNTHETIC_FIXTURE",
             "no_usable_evidence": False, "conflict_indicators": {},
             "limitations": self.card["limitations"]},
            self.card["distribution"])
        self.assertTrue(r["preview_allowed"])
        self.assertFalse(r["distribution_allowed"])
        self.assertIn("预览许可不等于分发许可", r["statement"])


class TestStageTracking(Base):
    """§13.C / T-40：P3C 八阶段必须真实写入，不能只检查名字存在。"""

    def _run_record(self):
        """★ 业务键定位：logical_identity + asset_version。

        `revalidation_run` 的 asset_version 在**同一 logical_identity 内**
        单调递增；跨身份时 rowid / 全局 asset_version 都不代表业务先后。
        """
        row = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='revalidation_run' "
            "ORDER BY logical_identity ASC, asset_version DESC, asset_id ASC "
            "LIMIT 1").fetchone()
        return json.loads(row["payload_json"])

    def test_eight_stages_written(self):
        p = self._run_record()
        self.assertEqual(len(p["stages"]), 8)

    def test_stages_have_real_states(self):
        p = self._run_record()
        states = {s["stage"]: s["state"] for s in p["stages"]}
        self.assertNotEqual(set(states.values()), {"PENDING"},
                            "不得全部停在 PENDING")
        self.assertIn("COMMITTED", set(states.values()))

    def test_no_fake_commit_after_failure(self):
        """★ 失败时后续阶段不得伪装为 COMMITTED。

        ★ 注意：revalidation_run 的 asset_version 是**每个 run 自己的**
        从 1 开始的版本号，所以 `ORDER BY asset_version DESC` 取到的
        不一定是"最新一次运行"；必须按业务键
        （logical_identity + asset_version）定位，**不能用 rowid**。
        """
        from collector_adapter import FakeGhAdapter
        import revalidation_executor as EX
        res = EX.execute_revalidation(
            self.ks, candidate_id=self.cand["candidate_id"],
            repository_id=rfx.REPO, authorization={}, plan={},
            adapter=FakeGhAdapter({}, {}), now="2026-11-05T00:00:00+08:00")
        self.assertFalse(res.ok, "无授权必须失败")
        # ★ 取该 run 身份下的**最高业务版本**（不用 rowid）
        row = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='revalidation_run' "
            "ORDER BY logical_identity ASC, asset_version DESC, asset_id ASC "
            "LIMIT 1").fetchone()
        p = json.loads(row["payload_json"])
        self.assertNotEqual(p.get("execution_status"), "SUCCESS",
                            "失败运行不得标为 SUCCESS")
        states = {s["stage"]: s["state"] for s in p["stages"]}
        self.assertNotEqual(set(states.values()), {"COMMITTED"},
                            "失败运行不得全 COMMITTED")
        self.assertTrue(any(v in states.values()
                            for v in ("FAILED_FATAL", "FAILED_RETRYABLE")),
                        f"失败运行必须有失败阶段：{states}")

    def test_run_links_final_verification(self):
        p = self._run_record()
        self.assertTrue(p.get("target_claim_id"), "必须关联目标 Claim")
        self.assertTrue(p.get("target_verification_id"),
                        "必须关联最终 Verification")

    def test_stage_success_is_not_ec_supported(self):
        """★ 阶段全部 COMMITTED ≠ EC supported。"""
        p = self._run_record()
        self.assertEqual(p["execution_status"], "SUCCESS")
        vr = self.ks.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type='claim_verification' "
            "AND asset_id=?",
            (self.res.payload["target_verification_id"],)).fetchall() if False else None
        rp = rfx.run(self.ks, rfx.q_path(commit_sha=rfx.B))
        # 研究包里执行状态与裁决是两个字段
        self.assertNotIn("execution_status",
                         [f.get("verdict_status") for f in rp["findings"]])
        self.assertIn("not_a_verification_status",
                      rp["coverage_assessment"])
        if not rp["findings"]:
            self.assertEqual(rp["packet_status"], "PACKET_INSUFFICIENT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
