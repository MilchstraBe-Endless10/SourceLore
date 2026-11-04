#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evidence-Claims 测试（T-1..T-30 主体）。

全部离线；证据来自真实写入 Storage 的 snapshot/fact。
"""
import sys, tempfile, shutil, unittest, copy, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"tests"/"evidence_claims"), str(ROOT/"src"/"evidence_claims"),
          str(ROOT/"src"/"storage"), str(ROOT/"src"/"facts"),
          str(ROOT/"src"/"collector"), str(ROOT/"src"/"runtime")):
    if p not in sys.path: sys.path.insert(0, p)

import fixtures as FX
import ec_models as M
import verifier as V
import verification_store as VS
from evaluation import score, assert_no_blocking


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ec_"))
        self.ks = FX.fresh(self.tmp)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestIdentity(Base):
    """T-1 / T-2 / T-13 / T-14。"""

    def test_t1_claim_identity_stable(self):
        a = M.build_path_claim(repository_id="1", commit_sha="a"*40,
                               target_path="README", expected_exists=True)
        b = M.build_path_claim(repository_id="1", commit_sha="a"*40,
                               target_path="README/", expected_exists=True)
        self.assertEqual(a.claim_id, b.claim_id, "规范化后同一命题 = 同一身份")

    def test_t1_claim_identity_ignores_evidence(self):
        """换证据不换 claim_id。"""
        c = M.build_path_claim(repository_id="1", commit_sha="a"*40,
                               target_path="README", expected_exists=True)
        by_id = M.make_claim_id(repository_id="1", commit_sha="a"*40,
                                claim_type=M.CLAIM_PATH_EXISTS,
                                normalized_parameters={"normalized_path": "README",
                                                       "expected_exists": True})
        self.assertEqual(c.claim_id, by_id)

    def test_t2_claim_and_verification_ids_differ(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertTrue(M.SAFE_CLAIM_ID.match(c.claim_id))
        self.assertTrue(M.SAFE_VERIF_ID.match(v.verification_id))
        self.assertNotEqual(c.claim_id, v.verification_id,
                            "Claim 与 Verification 身份必须分开")

    def test_t13_fact_order_does_not_change_result(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f1 = FX.make_fact(self.ks, snap["asset_id"], "README")
        f2 = FX.make_fact(self.ks, snap["asset_id"], "NOTHERE")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v1 = V.verify_path_claim(self.ks, c, [f1["fact_id"], f2["fact_id"]])
        v2 = V.verify_path_claim(self.ks, c, [f2["fact_id"], f1["fact_id"]])
        self.assertEqual(v1.status, v2.status)
        self.assertEqual(v1.verification_id, v2.verification_id,
                         "输入顺序不得影响评估身份")

    def test_t14_duplicate_fact_not_double_counted(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        once = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        twice = V.verify_path_claim(self.ks, c, [f["fact_id"], f["fact_id"]])
        self.assertEqual(once.status, twice.status)
        self.assertEqual(once.verification_id, twice.verification_id,
                         "重复事实不得重复计证据")
        self.assertEqual(len(twice.fact_ids), 1)


class TestThreeStates(Base):
    """T-3 / T-4 / T-5 / T-6 / T-7 / T-8 / T-9。"""

    def test_t3_present_supports_existence(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, completeness="COMPLETE")
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.SUPPORTED)
        self.assertIsNone(v.reason_code)
        self.assertTrue(v.supporting_fact_ids)

    def test_t3_absent_supports_non_existence_when_complete(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, completeness="COMPLETE")
        f = FX.make_fact(self.ks, snap["asset_id"], "package.json")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="package.json", expected_exists=False)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.SUPPORTED)

    def test_t4_present_refutes_non_existence(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, completeness="COMPLETE")
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=False)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.REFUTED)
        self.assertTrue(v.counter_fact_ids)

    def test_t4_complete_absent_refutes_existence(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, completeness="COMPLETE")
        f = FX.make_fact(self.ks, snap["asset_id"], "package.json")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="package.json", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.REFUTED)

    def test_t5_no_facts_is_insufficient(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [])
        self.assertEqual(v.status, M.INSUFFICIENT)
        self.assertEqual(v.reason_code, M.R_NO_FACTS,
                         "无证据不得默认 supported 或 refuted")

    def test_t6_partial_absent_cannot_refute(self):
        """PARTIAL 下未命中：不能证明不存在，也不能反驳存在。"""
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, completeness="PARTIAL")
        # PARTIAL 未命中 → Facts 侧产 UNKNOWN，不会入库；这里直接构造场景：
        # 用 COMPLETE 的 absent fact 但把快照标 PARTIAL 不可行，故改为：
        # 用真实 PARTIAL 快照，取一个 UNKNOWN fact 尝试裁决
        f_unknown = FX.make_fact(self.ks, snap["asset_id"], "package.json")
        self.assertEqual(f_unknown["obs"].observation, "UNKNOWN")
        self.assertEqual(f_unknown["state"], "REJECTED",
                         "UNKNOWN fact 不入库 —— 因此它不能成为证据")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="package.json", expected_exists=False)
        v = V.verify_path_claim(self.ks, c, [f_unknown["fact_id"]])
        self.assertEqual(v.status, M.INSUFFICIENT)
        self.assertEqual(v.reason_code, M.R_FACT_NOT_FOUND,
                         "UNKNOWN 未入库 → 找不到 → insufficient，绝不 refute/support")

    def test_t6_partial_present_supports_with_local_limit(self):
        """PARTIAL + 明确观察到存在 → 可支持，但必须带局部限制。"""
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, completeness="PARTIAL")
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        self.assertEqual(f["obs"].observation, "OBSERVED_PRESENT")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.SUPPORTED)
        self.assertTrue(v.local_coverage_only,
                        "PARTIAL 下的支持必须保留局部覆盖限制")

    def test_t7_local_evidence_scope_not_expanded(self):
        """局部证据不得支持更大范围命题（本批只实现路径级，验证限制被记录）。"""
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, completeness="PARTIAL")
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=False,
                               claim_scope="repo_wide_completeness")
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.REFUTED,
                         "存在证据反驳'不存在'命题（范围字段仅记录，不改裁决）")
        self.assertEqual(v.status != M.SUPPORTED, True,
                         "绝不能支持更大范围结论")

    def test_t8_different_commit_not_cross_refuted(self):
        """A 存在、B 不存在 → 两条独立命题，各自裁决，不互相证伪。"""
        snapA = FX.make_snapshot(self.ks, commit=FX.COMMIT_A, entries=[FX.README])
        snapB = FX.make_snapshot(self.ks, commit=FX.COMMIT_B,
                                 entries=[FX.DOCS])
        fA = FX.make_fact(self.ks, snapA["asset_id"], "README")
        fB = FX.make_fact(self.ks, snapB["asset_id"], "README")
        cA = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                target_path="README", expected_exists=True)
        cB = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_B,
                                target_path="README", expected_exists=False)
        vA = V.verify_path_claim(self.ks, cA, [fA["fact_id"]])
        vB = V.verify_path_claim(self.ks, cB, [fB["fact_id"]])
        self.assertEqual(vA.status, M.SUPPORTED)
        self.assertEqual(vB.status, M.SUPPORTED, "不同 Commit 可以各自成立")
        # 交叉传入 → 不匹配，不能互证
        vA_wrong = V.verify_path_claim(self.ks, cA, [fB["fact_id"]])
        self.assertEqual(vA_wrong.status, M.INSUFFICIENT,
                         "错误 Commit 的证据不得被接受")
        self.assertEqual(vA_wrong.reason_code, M.R_COMMIT_MISMATCH)

    def test_t9_repository_isolation(self):
        snapA = FX.make_snapshot(self.ks, repo="111", commit=FX.COMMIT_A)
        fA = FX.make_fact(self.ks, snapA["asset_id"], "README")
        c = M.build_path_claim(repository_id="222", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [fA["fact_id"]])
        self.assertEqual(v.status, M.INSUFFICIENT)
        self.assertEqual(v.reason_code, M.R_REPO_MISMATCH)


class TestEvidenceIntegrity(Base):
    """T-10 / T-11 / T-12。"""

    def test_t10_missing_reference_insufficient(self):
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, ["SL-FACT-" + "0"*40])
        self.assertEqual(v.status, M.INSUFFICIENT)
        self.assertEqual(v.reason_code, M.R_FACT_NOT_FOUND)

    def test_t11_corrupted_content_cannot_support(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        # 篡改事实 payload 的 content_hash（模拟损坏）
        row = self.ks.conn.execute(
            "SELECT asset_id, payload_json FROM assets WHERE logical_identity=?",
            (f["fact_id"],)).fetchone()
        p = json.loads(row["payload_json"]); p["content_hash"] = "f"*64
        self.ks.conn.execute("DROP TRIGGER IF EXISTS assets_no_update")
        self.ks.conn.execute("UPDATE assets SET payload_json=? WHERE asset_id=?",
                             (json.dumps(p, ensure_ascii=False), row["asset_id"]))
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertNotEqual(v.status, M.SUPPORTED, "损坏证据绝不能产生 supported")
        self.assertEqual(v.status, M.INSUFFICIENT)
        self.assertIn(v.reason_code, (M.R_FACT_INTEGRITY, M.R_STORAGE_ERROR))

    def test_t12_conflict_not_forced(self):
        """同仓库同 Commit 同路径出现互相矛盾的已核验事实 → 冲突诊断。"""
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f1 = FX.make_fact(self.ks, snap["asset_id"], "README")   # PRESENT
        # ★ 同 Commit 同路径的"真实矛盾"在当前身份契约下无法由两个正常快照产生
        # （identity 只由 repo/commit/scope/collector_version 决定，内容不同会撞 CONFLICT）。
        # 这种矛盾只可能来自**来源数据损坏**，题面第 7 节正是这么说的。
        # 因此这里用受控注入构造第二条同 Commit 的 ABSENT 事实（模拟损坏），
        # 目的就是验证裁决器遇到矛盾时**不会强行裁决**。
        f2 = FX.inject_synthetic_absent_fact(self.ks, snap["asset_id"],
                                            path="README", commit=FX.COMMIT_A)
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [f1["fact_id"], f2["fact_id"]])
        self.assertEqual(v.status, M.INSUFFICIENT,
                         "冲突不得强行裁决（不得多数票、不得取最新）")
        self.assertEqual(v.reason_code, M.R_CONFLICT)
        self.assertTrue(v.conflict_detected)
        self.assertEqual(len(v.conflict_fact_ids), 2)


class TestReviewSeparation(Base):
    """T-21 / T-22。"""

    def test_t21_ai_cannot_approve(self):
        with self.assertRaises(ValueError):
            M.Claim(claim_id="SL-CLAIM-"+"0"*40, claim_type=M.CLAIM_PATH_EXISTS,
                    repository_id="1", commit_sha="a"*40, normalized_path="README",
                    expected_exists=True, claim_scope="x", claim_origin="ai",
                    review_status=M.APPROVED, human_authored=False)

    def test_t22_human_authored_required_for_approved(self):
        c = M.Claim(claim_id="SL-CLAIM-"+"0"*40, claim_type=M.CLAIM_PATH_EXISTS,
                    repository_id="1", commit_sha="a"*40, normalized_path="README",
                    expected_exists=True, claim_scope="x", claim_origin="human",
                    review_status=M.APPROVED, human_authored=True)
        self.assertEqual(c.review_status, M.APPROVED)

    def test_verification_does_not_set_approved(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                               target_path="README", expected_exists=True)
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.SUPPORTED)
        self.assertEqual(c.review_status, M.PENDING_REVIEW,
                         "评估成功不等于获得批准")
        self.assertFalse(c.human_authored)


class TestPersistence(Base):
    """T-15..T-20。"""

    def _claim(self):
        return M.build_path_claim(repository_id="1296269", commit_sha=FX.COMMIT_A,
                                  target_path="README", expected_exists=True)

    def test_t17_duplicate_verification_idempotent(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = self._claim()
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        VS.ingest_claim(self.ks, c)
        a = VS.ingest_verification(self.ks, v, repository_id="1296269")
        b = VS.ingest_verification(self.ks, v, repository_id="1296269")
        self.assertEqual(b["state"], VS.IDEMPOTENT)
        self.assertEqual(a["asset_id"], b["asset_id"])
        n = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(n, 1)

    def test_t16_old_verification_readable(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = self._claim()
        v1 = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        VS.ingest_verification(self.ks, v1, repository_id="1296269")
        r = VS.read_verification(self.ks, v1.verification_id, "1296269")
        self.assertTrue(r["ok"])
        self.assertEqual(r["versions"][0]["payload"]["status"], M.SUPPORTED)

    def test_t15_rule_version_change_creates_new_version(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = self._claim()
        v1 = V.verify_path_claim(self.ks, c, [f["fact_id"]], rule_version="v1")
        v2 = V.verify_path_claim(self.ks, c, [f["fact_id"]], rule_version="v2")
        self.assertNotEqual(v1.verification_id, v2.verification_id,
                            "规则版本变 → 新评估版本，不覆盖历史")
        VS.ingest_verification(self.ks, v1, repository_id="1296269")
        VS.ingest_verification(self.ks, v2, repository_id="1296269")
        n = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(n, 2, "两个版本都必须保留")

    def test_t18_cas_conflict_explicit(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = self._claim()
        VS.ingest_claim(self.ks, c)
        # 用错误的 expected_version 推进（当前版本是 1）
        c2 = copy.deepcopy(c)
        c2.review_status = M.REJECTED_REVIEW
        r_bad = VS.ingest_claim(self.ks, c2, expected_version=99)
        self.assertFalse(r_bad.get("ok"),
                         f"错误 CAS 不得静默成功: {r_bad}")
        self.assertEqual(r_bad.get("state"), VS.REJECTED, r_bad)
        # 正确版本可以推进
        r_ok = VS.ingest_claim(self.ks, c2, expected_version=1)
        self.assertTrue(r_ok.get("ok"), r_ok)
        self.assertEqual(r_ok["state"], VS.VERSION_ADDED)

    def test_t19_no_half_commit(self):
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        c = self._claim()
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        orig = self.ks.append_asset_and_advance
        def boom(*a, **kw):
            try: self.ks.conn.execute("ROLLBACK")
            except Exception: pass
            return {"ok": False, "error": "PERMISSION_DENIED", "detail": "injected"}
        self.ks.append_asset_and_advance = boom
        try:
            r = VS.ingest_verification(self.ks, v, repository_id="1296269")
            self.assertFalse(r.get("ok"))
        finally:
            self.ks.append_asset_and_advance = orig
        n = self.ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='claim_verification'"
        ).fetchone()["n"]
        self.assertEqual(n, 0, "失败不得留下半提交验证记录")


class TestUnsupportedType(Base):
    def test_unsupported_claim_type(self):
        c = M.build_path_claim(repository_id="1", commit_sha="a"*40,
                               target_path="README", expected_exists=True)
        object.__setattr__(c, "claim_type", "project_is_mature")
        snap = FX.make_snapshot(self.ks, commit=FX.COMMIT_A)
        f = FX.make_fact(self.ks, snap["asset_id"], "README")
        v = V.verify_path_claim(self.ks, c, [f["fact_id"]])
        self.assertEqual(v.status, M.INSUFFICIENT)
        self.assertEqual(v.reason_code, M.R_UNSUPPORTED_TYPE,
                         "不支持类型必须显式拒绝，不得套用路径规则")


if __name__ == "__main__":
    unittest.main(verbosity=2)
