#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-20..T-23 / T-30..T-33：只读性与禁止自动动作。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/research", "src/research", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import view_integrity as VI

RESEARCH_SRC = [p for p in (ROOT/"src"/"research").glob("*.py")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ro_r_"))
        self.ks = rfx.fresh(self.tmp)
        rfx.vfx.run_full(self.ks)
        self.before = {
            "assets": VI.fingerprint_assets(self.ks),
            "pointers": VI.fingerprint_pointers(self.ks),
            "index": VI.fingerprint_index(self.ks),
            "oplog": VI.fingerprint_operation_log(self.ks),
        }

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_all(self):
        rfx.run(self.ks, rfx.q_path())
        rfx.run(self.ks, rfx.q_claims())
        rfx.run(self.ks, rfx.q_version())


class TestReadOnly(Base):
    def test_t31_a_b_c_unchanged(self):
        self.assertGreater(len(self.before["assets"]), 0, "防空集合假通过")
        self._run_all()
        self.assertEqual(self.before["assets"], VI.fingerprint_assets(self.ks))
        self.assertEqual(self.before["pointers"], VI.fingerprint_pointers(self.ks))
        self.assertEqual(self.before["index"], VI.fingerprint_index(self.ks))

    def test_t32_checkpoint_and_oplog_unchanged(self):
        self.assertGreater(len(self.before["oplog"]), 0, "必须有 operation_log")
        self._run_all()
        self.assertEqual(self.before["oplog"],
                         VI.fingerprint_operation_log(self.ks))
        n0 = self.ks.conn.execute(
            "SELECT count(*) n FROM assets WHERE asset_type='revalidation_run'"
        ).fetchone()["n"]
        self._run_all()
        n1 = self.ks.conn.execute(
            "SELECT count(*) n FROM assets WHERE asset_type='revalidation_run'"
        ).fetchone()["n"]
        self.assertEqual(n0, n1, "Checkpoint 不得被 Research 改动")

    def test_t33_claim_verification_fingerprint(self):
        def fp():
            rows = self.ks.conn.execute(
                "SELECT asset_id,content_hash FROM assets WHERE asset_type IN "
                "('claim_candidate','claim_verification') "
                "ORDER BY asset_id").fetchall()
            return [(r["asset_id"], r["content_hash"]) for r in rows]
        b = fp()
        self.assertGreater(len(b), 0)
        self._run_all()
        self.assertEqual(b, fp(), "原始 Claim/Verification 指纹必须不变")

    def test_negative_control(self):
        """负向对照：指纹确实能检测写入。"""
        from asset_models import AssetDraft
        d = AssetDraft(asset_type="freshness_assessment",
                       logical_identity="SL-ASSESS-PROBE-" + "3" * 16,
                       repository_id=rfx.REPO,
                       payload={"probe": True, "assessment_id": "p"},
                       asset_version=1, operation_id="OP-PROBE-RO")
        self.assertTrue(self.ks.append_asset_and_advance(
            d, expected_version=None).get("ok"))
        self.assertNotEqual(self.before["assets"],
                            VI.fingerprint_assets(self.ks))


class TestNoAutoActions(Base):
    def test_t20_no_github(self):
        for f in RESEARCH_SRC:
            t = f.read_text(encoding="utf-8")
            for bad in ("import requests", "urllib.request", "http.client",
                        "socket", "GitHubClient", "gh_api"):
                self.assertNotIn(bad, t, f"{f.name} 不得引入 {bad}")

    def test_t21_no_fact_extraction(self):
        for f in RESEARCH_SRC:
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("extract_file_path_observation", t, f.name)
            self.assertNotIn("ingest_fact", t, f.name)

    def test_t22_no_ec_verification(self):
        for f in RESEARCH_SRC:
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("verify_path_claim", t, f.name)
            self.assertNotIn("import verifier", t, f.name)

    def test_t23_no_lifecycle_reeval(self):
        for f in RESEARCH_SRC:
            t = f.read_text(encoding="utf-8")
            for bad in ("assess(", "execute_revalidation", "revalidation_executor",
                        "propose_candidate"):
                self.assertNotIn(bad, t, f"{f.name} 不得调用 {bad}")

    def test_no_llm(self):
        import re
        pat = re.compile(
            r"\b(import|from)\s+(openai|anthropic|google\.generativeai|cohere)\b"
            r"|\bapi\.(openai|anthropic)\.com\b", re.I)
        for f in RESEARCH_SRC:
            self.assertIsNone(pat.search(f.read_text(encoding="utf-8")), f.name)

    def test_t30_no_second_database(self):
        for f in RESEARCH_SRC:
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("CREATE TABLE", t, f.name)
            self.assertNotIn("sqlite3.connect", t, f.name)

    def test_no_write_api(self):
        for f in RESEARCH_SRC:
            t = f.read_text(encoding="utf-8")
            for bad in ("append_asset_and_advance", "ingest_", "set_stage",
                        "finish_run", "create_run"):
                self.assertNotIn(bad, t, f"{f.name} 不得调用 {bad}")

    def test_sql_is_constant(self):
        """★ SQL 必须是常量模板，不接受外部拼接。"""
        rt = (ROOT/"src/research/retriever.py").read_text(encoding="utf-8")
        self.assertNotIn('execute(f"', rt)
        self.assertNotIn("execute(sql +", rt)
        self.assertNotIn("% (", rt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
