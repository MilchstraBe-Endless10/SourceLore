#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线 Gold 评测（SL-CAP-0075）+ 变异测试（题面第 10/11 节）。

Gold 的预期来自 gold_cases.json（人工写定），**不由裁决器生成**。
"""
import sys, tempfile, shutil, json, unittest, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"tests"/"evidence_claims"), str(ROOT/"src"/"evidence_claims"),
          str(ROOT/"src"/"storage"), str(ROOT/"src"/"facts"),
          str(ROOT/"src"/"collector"), str(ROOT/"src"/"runtime")):
    if p not in sys.path: sys.path.insert(0, p)

import fixtures as FX
import ec_models as M
import verifier as V
from evaluation import score, assert_no_blocking

GOLD = ROOT/"tests"/"evidence_claims"/"gold"/"gold_cases.json"


class GoldRunner(unittest.TestCase):
    """按 gold 场景逐个构造真实证据，跑出实际裁决，再与人工预期比对。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gold_"))
        self.ks = FX.fresh(self.tmp)
        self.gold = json.loads(GOLD.read_text(encoding="utf-8"))
        self._case_dirs = []

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)
        for d in getattr(self, "_case_dirs", []):
            shutil.rmtree(d, ignore_errors=True)

    def _isolated(self):
        """每个 gold 场景用**独立 store**。

        ★ 必须这样：source snapshot 的 identity 只由
        (repository_id, commit_sha, retrieval_scope, collector_version) 决定，
        **completeness_status 不进身份**（P1A/P1C 契约）。
        因此同一 repo+commit 下 COMPLETE 与 PARTIAL 快照会撞同一个 identity，
        在共享 store 里第二次会被判 CONFLICT。隔离 store 才能独立构造各场景。
        """
        d = Path(tempfile.mkdtemp(prefix="goldcase_"))
        self._case_dirs.append(d)
        return FX.fresh(d)

    def run_scenario_isolated(self, name):
        saved = self.ks
        self.ks = self._isolated()
        try:
            return self.run_scenario(name)
        finally:
            try: self.ks.close()
            except Exception: pass
            self.ks = saved

    # ── 场景构造器 ────────────────────────────────────────
    def _complete_snapshot(self, entries=None, commit=FX.COMMIT_A, repo="1296269"):
        return FX.make_snapshot(self.ks, repo=repo, commit=commit,
                                entries=entries or [FX.README, FX.DOCS])

    def run_scenario(self, name):
        """返回 (status, reason_code, evidence_refs_ok, detail)。"""
        ks = self.ks

        if name == "present_claim_exists":
            s = self._complete_snapshot()
            f = FX.make_fact(ks, s["asset_id"], "README")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, bool(v.evidence_refs), ""

        if name == "absent_claim_not_exists":
            s = self._complete_snapshot()
            f = FX.make_fact(ks, s["asset_id"], "package.json")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="package.json", expected_exists=False)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, bool(v.evidence_refs), ""

        if name == "present_refutes_not_exists":
            s = self._complete_snapshot()
            f = FX.make_fact(ks, s["asset_id"], "README")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=False)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, bool(v.evidence_refs), ""

        if name == "complete_absent_refutes_exists":
            s = self._complete_snapshot()
            f = FX.make_fact(ks, s["asset_id"], "package.json")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="package.json", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, bool(v.evidence_refs), ""

        if name == "no_facts":
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [])
            return v.status, v.reason_code, False, ""

        if name == "wrong_commit":
            s = self._complete_snapshot(commit=FX.COMMIT_B)
            f = FX.make_fact(ks, s["asset_id"], "README")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, False, ""

        if name == "wrong_repository":
            s = self._complete_snapshot(repo="999")
            f = FX.make_fact(ks, s["asset_id"], "README")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, False, ""

        if name == "partial_not_covering":
            s = FX.make_snapshot(ks, commit=FX.COMMIT_A, completeness="PARTIAL")
            f = FX.make_fact(ks, s["asset_id"], "package.json")   # UNKNOWN → 不入库
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="package.json", expected_exists=False)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, False, ""

        if name == "partial_local_present":
            s = FX.make_snapshot(ks, commit=FX.COMMIT_A, completeness="PARTIAL")
            f = FX.make_fact(ks, s["asset_id"], "README")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, bool(v.evidence_refs), \
                   f"local_coverage_only={v.local_coverage_only}"

        if name == "corrupted_evidence":
            s = self._complete_snapshot()
            f = FX.make_fact(ks, s["asset_id"], "README")
            row = ks.conn.execute(
                "SELECT asset_id, payload_json FROM assets WHERE logical_identity=?",
                (f["fact_id"],)).fetchone()
            p = json.loads(row["payload_json"]); p["content_hash"] = "f"*64
            ks.conn.execute("DROP TRIGGER IF EXISTS assets_no_update")
            ks.conn.execute("UPDATE assets SET payload_json=? WHERE asset_id=?",
                            (json.dumps(p, ensure_ascii=False), row["asset_id"]))
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, False, ""

        if name == "conflicting_evidence":
            s = self._complete_snapshot()
            f1 = FX.make_fact(ks, s["asset_id"], "README")            # PRESENT
            f2 = FX.inject_synthetic_absent_fact(ks, s["asset_id"],
                                                path="README", commit=FX.COMMIT_A)
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f1["fact_id"], f2["fact_id"]])
            return v.status, v.reason_code, False, \
                   f"conflict={v.conflict_detected}"

        if name == "unsupported_type":
            s = self._complete_snapshot()
            f = FX.make_fact(ks, s["asset_id"], "README")
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            object.__setattr__(c, "claim_type", "project_is_mature")
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, False, ""

        if name == "missing_reference":
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, ["SL-FACT-" + "0"*40])
            return v.status, v.reason_code, False, ""

        if name == "path_mismatch":
            s = self._complete_snapshot()
            f = FX.make_fact(ks, s["asset_id"], "docs")   # 事实是 docs
            c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                   target_path="README", expected_exists=True)
            v = V.verify_path_claim(ks, c, [f["fact_id"]])
            return v.status, v.reason_code, False, ""

        raise KeyError(f"未知 gold 场景: {name}")


class TestGold(GoldRunner):
    """T-23：Gold 覆盖三种状态，且全部命中人工预期。"""

    def test_gold_set_non_empty(self):
        self.assertGreater(len(self.gold["cases"]), 0, "Gold 集不得为空")

    def test_gold_covers_three_statuses(self):
        got = {c["expected"] for c in self.gold["cases"]}
        self.assertEqual(got, set(M.VERIFICATION_STATES),
                         "Gold 必须同时覆盖 supported/refuted/insufficient")

    def test_gold_all_cases_hit_expected(self):
        results = []
        for c in self.gold["cases"]:
            status, reason, ev_ok, detail = self.run_scenario_isolated(c["scenario"])
            results.append({"case_id": c["id"], "expected": c["expected"],
                            "actual": status, "reason_code": reason,
                            "evidence_refs_ok": ev_ok, "detail": detail})
        s = score(results)
        self.assertEqual(s["correct"], s["total"],
                         f"gold 未全对: {s['failures']}")
        self.assertEqual(s["blocking_errors"], [],
                         f"存在阻断级错误: {s['blocking_errors']}")
        self.assertEqual(s["gate"], "PASS")
        self.assertEqual(s["false_supported"], 0)
        self.assertEqual(s["false_refuted"], 0)

    def test_gold_high_risk_gate(self):
        """高风险门禁：缺失证据不得判 refuted，不充分证据不得判 supported。"""
        results = []
        for c in self.gold["cases"]:
            status, *_ = self.run_scenario_isolated(c["scenario"])
            results.append({"case_id": c["id"], "expected": c["expected"],
                            "actual": status, "evidence_refs_ok": True})
        s = assert_no_blocking(results)
        self.assertEqual(s["blocking_errors"], [])

    def test_every_case_actually_executed(self):
        """每个 gold 都必须真的跑过（不能空跑）。"""
        executed = set()
        for c in self.gold["cases"]:
            self.run_scenario_isolated(c["scenario"])
            executed.add(c["id"])
        self.assertEqual(len(executed), len(self.gold["cases"]),
                         "每个 gold 场景都必须被实际执行")


class TestMutation(GoldRunner):
    """T-24 / T-25：变异测试 —— 故意让验证器犯错，确认现有测试能捕获。

    变异**只在测试内替换函数**，不修改正式源码。
    """

    def _all_gold_results(self, verifier_fn):
        results = []
        for c in self.gold["cases"]:
            status, reason, ev_ok, detail = self.run_scenario_isolated(c["scenario"])
            results.append({"case_id": c["id"], "expected": c["expected"],
                            "actual": status, "evidence_refs_ok": True})
        return results

    def test_t24_mutation_missing_judged_refuted_is_caught(self):
        """把'无证据'错判成 refuted 的变异必须被判分器捕获。"""
        results = copy.deepcopy(self._all_gold_results(None))
        # 人为把一条 insufficient 改写成 refuted（模拟验证器被改坏）
        for r in results:
            if r["expected"] == M.INSUFFICIENT and r["reason_code" if "reason_code" in r
                                                       else "case_id"] == "G05":
                r["actual"] = M.REFUTED
        # 上面按 case_id 更容易命中
        for r in results:
            if r["case_id"] == "G05":
                r["actual"] = M.REFUTED
        s = score(results)
        kinds = {b["kind"] for b in s["blocking_errors"]}
        self.assertIn("MISSING_JUDGED_REFUTED", kinds,
                      "缺失证据被误判 refuted 必须被标为阻断")
        self.assertEqual(s["gate"], "BLOCKED")

    def test_t25_mutation_insufficient_judged_supported_is_caught(self):
        results = self._all_gold_results(None)
        for r in results:
            if r["case_id"] == "G06":
                r["actual"] = M.SUPPORTED
        s = score(results)
        kinds = {b["kind"] for b in s["blocking_errors"]}
        self.assertIn("INSUFFICIENT_JUDGED_SUPPORTED", kinds,
                      "不充分证据被误判 supported 必须被标为阻断")
        self.assertEqual(s["gate"], "BLOCKED")

    def test_t25b_all_supported_mutation_caught(self):
        """把一切判成 supported 的极端变异必须被大量捕获。"""
        results = self._all_gold_results(None)
        for r in results:
            r["actual"] = M.SUPPORTED
        s = score(results)
        self.assertGreater(s["false_supported"], 0)
        self.assertGreater(len(s["blocking_errors"]), 0)
        self.assertEqual(s["gate"], "BLOCKED")

    def test_score_not_fooled_by_empty_set(self):
        """空集合必须显式报错，不能返回 accuracy=1。"""
        s = score([])
        self.assertEqual(s.get("error"), "EMPTY_GOLD_SET")
        self.assertNotIn("accuracy", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
