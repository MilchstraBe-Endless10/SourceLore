#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-2..T-11 / T-24 / T-27：结构化检索与确定性排序。"""
import sys, tempfile, shutil, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/research", "src/research", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import retriever as RT, coverage_evaluator as CE


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="rt_"))
        cls.ks = rfx.fresh(cls.tmp)
        rfx.vfx.run_full(cls.ks)

    @classmethod
    def tearDownClass(cls):
        try: cls.ks.close()
        except Exception: pass
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestRetrieval(Base):
    def test_t2_structured_query_uses_view(self):
        r = RT.retrieve_claims(self.ks, rfx.q_claims())
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["kept"]), 1)
        self.assertNotEqual(r["status"], RT.EMPTY)

    def test_t3_does_not_rerun_ec(self):
        """★ 检索只读 Claim/Verification 记录，不调用 verifier。"""
        import retriever
        src = Path(retriever.__file__).read_text(encoding="utf-8")
        self.assertNotIn("verify_path_claim", src)
        self.assertNotIn("verifier", src.replace("verifications", ""))

    def test_t4_supported_preserved(self):
        q = rfx.q_path()
        p = rfx.run(self.ks, q)
        self.assertEqual(p["coverage_assessment"]["coverage_state"],
                         CE.A_ANSWERABLE)
        self.assertEqual(p["findings"][0]["verdict_status"], "supported")
        self.assertEqual(p["findings"][0]["finding_type"], "SUPPORTED")

    def test_t5_refuted_preserved(self):
        q = rfx.q_path(commit_sha=rfx.B)
        p = rfx.run(self.ks, q)
        self.assertEqual(p["findings"][0]["verdict_status"], "refuted")
        self.assertEqual(p["findings"][0]["finding_type"], "REFUTED")
        # ★ refuted 仍可回答，但不是"否定一切"
        self.assertIn("仅针对该 Commit", p["coverage_assessment"]["gaps"][0]["detail"])

    def test_t6_insufficient_preserved(self):
        q = rfx.q_claims()
        p = rfx.run(self.ks, q)
        statuses = {f["verdict_status"] for f in p["findings"]}
        self.assertIn(statuses, ({"supported"},
                                 {"supported", "insufficient_evidence"},
                                 {"insufficient_evidence"}))

    def test_t7_no_result_is_not_false(self):
        """★ 查不到 ≠ 命题为假。"""
        q = rfx.q_path(path="totally-nonexistent.md")
        p = rfx.run(self.ks, q)
        self.assertEqual(p["coverage_assessment"]["coverage_state"],
                         CE.A_INSUFFICIENT)
        self.assertEqual(len(p["findings"]), 0)
        gaps = [g["gap"] for g in p["coverage_assessment"]["gaps"]]
        self.assertIn("NO_REGISTERED_CLAIM", gaps)
        detail = p["coverage_assessment"]["gaps"][-1]["detail"] if \
            p["coverage_assessment"]["gaps"] else ""
        self.assertNotIn("为假", detail.replace("**不**意味着命题为假", ""))
        # 不得出现 refuted
        self.assertEqual(p["packet_status"], "PACKET_INSUFFICIENT")

    def test_t8_repository_not_confused(self):
        q = rfx.q_claims(repository_id="999999999")
        r = RT.retrieve_claims(self.ks, q)
        self.assertEqual(len(r["kept"]), 0)
        self.assertEqual(r["status"], RT.EMPTY)

    def test_t9_commit_not_confused(self):
        q = rfx.q_path(commit_sha="c" * 40)
        r = RT.retrieve_claims(self.ks, q)
        kept = r["kept"]
        self.assertEqual(len(kept), 0, "不存在的 Commit 不得返回别的 Commit 的 Claim")
        reasons = {e["reason"] for e in r["excluded"]}
        self.assertIn("COMMIT_NOT_MATCH", reasons)

    def test_t24_stable_ordering(self):
        r1 = RT.retrieve_claims(self.ks, rfx.q_claims())
        r2 = RT.retrieve_claims(self.ks, rfx.q_claims())
        ids1 = [c["claim_id"] for c in r1["kept"]]
        ids2 = [c["claim_id"] for c in r2["kept"]]
        self.assertEqual(ids1, ids2, "排序必须稳定")

    def test_t27_truncation_marked(self):
        q = rfx.q_claims(max_results=1)
        r = RT.retrieve_claims(self.ks, q)
        self.assertEqual(r["cap"], 1)
        if r["truncated"]:
            self.assertIn("截断", r["note"])
            self.assertIn("不等于不存在", r["note"])

    def test_limit_does_not_mean_absent(self):
        r = RT.retrieve_claims(self.ks, rfx.q_claims(max_results=1))
        self.assertEqual(r["examined_boundary"], 1)
        self.assertIsInstance(r["candidate_count"], int)


class TestVersionCompare(Base):
    def test_t10_history_compare(self):
        q = rfx.q_version()
        p = rfx.run(self.ks, q)
        commits = {f["claim_commit_sha"] for f in p["findings"]}
        self.assertEqual(len(commits), 2, "必须保留两个 Commit")
        self.assertEqual(p["coverage_assessment"]["coverage_state"],
                         CE.A_PARTIAL)

    def test_t11_not_reported_as_conflict(self):
        q = rfx.q_version()
        p = rfx.run(self.ks, q)
        kinds = {c["kind"] for c in p["conflicts"]}
        self.assertIn("MULTI_COMMIT_DIFFERENCE", kinds)
        for c in p["conflicts"]:
            note = c["note"]
            self.assertTrue("**不是**" in note or "不得" in note,
                            "必须显式否定'同一事实冲突'")
            self.assertTrue("不推断祖先" in note or "祖先" in note,
                            "必须显式否定祖先推断")

    def test_version_no_ancestry_claim(self):
        p = rfx.run(self.ks, rfx.q_version())
        blob = json.dumps(p, ensure_ascii=False)
        for bad in ("父提交", "ancestor", "descends from", "上一版本是"):
            self.assertNotIn(bad, blob)


class TestRetrievalError(unittest.TestCase):
    def test_retrieval_error_is_distinct(self):
        """★ 检索失败 ≠ 证据不足。"""
        q = rfx.q_claims()
        bad = {"ok": False, "status": RT.RETRIEVAL_ERROR,
               "error": RT.E_INDEX_CORRUPT, "detail": "模拟索引损坏"}
        cov = CE.evaluate(q, bad, [], [])
        self.assertEqual(cov["coverage_state"], CE.A_ERROR)
        self.assertNotEqual(cov["coverage_state"], CE.A_INSUFFICIENT)
        self.assertIn("RETRIEVAL_FAILED",
                      [g["gap"] for g in cov["gaps"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
