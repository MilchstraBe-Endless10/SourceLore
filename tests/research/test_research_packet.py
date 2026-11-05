#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-26 / T-27 / T-34 / T-25：研究包结构与确定性。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/research", "src/research", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import research_packet as RP, coverage_evaluator as CE, query_models as QM


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="pk_"))
        cls.ks = rfx.fresh(cls.tmp)
        rfx.vfx.run_full(cls.ks)

    @classmethod
    def tearDownClass(cls):
        try: cls.ks.close()
        except Exception: pass
        shutil.rmtree(cls.tmp, ignore_errors=True)


REQUIRED_KEYS = (
    "research_id", "research_schema_version", "query_id", "query",
    "canonical_refs", "selected_view_ids", "claim_refs", "verification_refs",
    "fact_refs", "evidence_refs", "source_snapshot_refs", "findings",
    "excluded_candidates", "coverage_assessment", "unresolved_questions",
    "limitations", "conflicts", "provenance_summary", "review_summary",
    "freshness_summary", "distribution_restrictions",
    "retrieval_rule_version", "packet_status",
)


class TestPacket(Base):
    def test_t34_required_fields(self):
        p = rfx.run(self.ks, rfx.q_path())
        for k in REQUIRED_KEYS:
            self.assertIn(k, p, f"研究包缺少 {k}")

    def test_t34b_every_finding_locatable(self):
        p = rfx.run(self.ks, rfx.q_path())
        for f in p["findings"]:
            for k in ("finding_id", "claim_id", "verification_id",
                      "claim_commit_sha", "evidence_refs", "verdict_status",
                      "limitations"):
                self.assertIn(k, f, f"finding 缺少 {k}")

    def test_t26_repeat_identical(self):
        q = rfx.q_path()
        a = rfx.run(self.ks, q)
        b = rfx.run(self.ks, q)
        self.assertEqual(a["research_id"], b["research_id"])
        self.assertEqual(a["content_digest"], b["content_digest"])
        self.assertEqual(json.dumps(a["findings"], sort_keys=True),
                         json.dumps(b["findings"], sort_keys=True))

    def test_t25_order_independent(self):
        q = rfx.q_path()
        d = dict(q)
        a = rfx.run(self.ks, d)
        rev = json.loads(json.dumps(q))
        rev["canonical_refs"] = list(reversed(rev["canonical_refs"]))
        b = rfx.run(self.ks, rev)
        self.assertEqual(a["research_id"], b["research_id"],
                         "查询字段顺序不得影响 research_id")

    def test_diagnostics_excluded_from_digest(self):
        a = rfx.run(self.ks, rfx.q_path())
        b = rfx.run(self.ks, rfx.q_path(), include_diagnostics=True)
        self.assertEqual(a["content_digest"], b["content_digest"],
                         "诊断元数据不得污染内容摘要")
        self.assertIn("run_diagnostics", b)
        self.assertNotIn("run_diagnostics", a)
        self.assertEqual(RP.content_digest(b), a["content_digest"])

    def test_research_id_changes_with_findings(self):
        a = rfx.run(self.ks, rfx.q_path())
        b = rfx.run(self.ks, rfx.q_path(commit_sha=rfx.B))
        self.assertNotEqual(a["research_id"], b["research_id"])

    def test_not_claim_authority(self):
        p = rfx.run(self.ks, rfx.q_path())
        self.assertFalse(p["is_claim_authority"])
        self.assertFalse(p["publishable_as_knowledge"])
        self.assertFalse(p["llm_used"])
        self.assertFalse(p["external_network_used"])

    def test_packet_states_orthogonal(self):
        """★ packet_status / coverage / verification 三者正交。"""
        p = rfx.run(self.ks, rfx.q_path())
        self.assertIn(p["packet_status"], RP.PACKET_STATES)
        self.assertIn(p["coverage_assessment"]["coverage_state"],
                      CE.COVERAGE_STATES)
        self.assertTrue(p["coverage_assessment"]["not_a_verification_status"])
        self.assertNotEqual(p["packet_status"],
                            p["findings"][0]["verdict_status"],
                            "包状态不得等于 EC 裁决")

    def test_t27_truncation_propagated(self):
        q = rfx.q_claims(max_results=1)
        p = rfx.run(self.ks, q)
        self.assertEqual(p["retrieval"]["limit"], 1)
        if p["retrieval"]["truncated"]:
            self.assertTrue(any("截断" in x for x in p["limitations"]))

    def test_distribution_preserved(self):
        p = rfx.run(self.ks, rfx.q_path())
        d = p["distribution_restrictions"]
        self.assertFalse(d["distribution_allowed"])
        self.assertEqual(d["freeze_state"], "FROZEN_INTERNAL_RESTRICTED")
        ids = {b["id"] for b in d["blockers"]}
        self.assertEqual(ids, {"B-1", "B-2", "B-3"})

    def test_insufficient_packet(self):
        p = rfx.run(self.ks, rfx.q_path(path="no-such.md"))
        self.assertEqual(p["packet_status"], RP.P_PARTIAL if False else
                         RP.P_INSUFFICIENT)
        self.assertEqual(len(p["findings"]), 0)

    def test_version_packet_partial(self):
        p = rfx.run(self.ks, rfx.q_version())
        self.assertEqual(p["packet_status"], RP.P_PARTIAL)
        self.assertGreaterEqual(len(p["claim_refs"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
