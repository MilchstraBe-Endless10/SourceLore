#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3C 授权门禁测试（T-1..T-8）。"""
import sys, unittest, copy, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/facts", "src/collector",
          "src/runtime", "src/evidence_claims", "tests/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import revalidation_authorization as AUTH
import lc_models as L

NOW = "2026-11-05T00:00:00+08:00"
CAND = {
    "candidate_id": "SL-REVAL-" + "a" * 32,
    "repository_id": "1296269", "requested_ref": "master",
    "target_commit_sha": "b" * 40,
}
PLAN = {
    "candidate_id": CAND["candidate_id"],
    "target_commit_sha": CAND["target_commit_sha"],
    "repository_id": "1296269", "requested_ref": "master",
    "intended_collector_scope": "full_tree_enumeration",
    "intended_fact_rules": ["file_path_observation@v1"],
    "intended_ec_rule_version": "path-exists-verifier/v1",
    "target_claim_parameters": {"normalized_path": "README",
                                "expected_exists": True},
}


def _plan_with_digest(plan=None):
    p = copy.deepcopy(plan or PLAN)
    p["plan_digest"] = AUTH.plan_digest_of(p)
    return p


def _auth(plan=None, **over):
    p = _plan_with_digest(plan)
    a = AUTH.make_test_authorization(
        candidate_id=CAND["candidate_id"], repository_id="1296269",
        requested_ref="master", target_commit_sha=CAND["target_commit_sha"],
        plan_digest=p["plan_digest"],
        authorized_scope="full_tree_enumeration",
        issued_at="2026-11-04T00:00:00+08:00",
        expires_at="2026-11-06T00:00:00+08:00")
    a.update(over)
    return p, a


class TestAuthorizationDeny(unittest.TestCase):
    """T-1..T-6：各类拒绝。"""

    def _v(self, plan, auth, require_production=False):
        return AUTH.validate_execution_authorization(
            candidate=CAND, plan=plan, authorization=auth, now=NOW,
            require_production=require_production)

    def test_t1_no_authorization(self):
        p, _ = _auth()
        for a in (None, {}, "not-a-dict"):
            r = self._v(p, a)
            self.assertFalse(r["ok"])
            self.assertEqual(r["reason"], AUTH.A_NO_AUTHORIZATION)

    def test_t2_expired(self):
        p, a = _auth()
        a["expires_at"] = "2026-11-04T00:00:00+08:00"
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_EXPIRED)

    def test_t2b_not_yet_valid(self):
        p, a = _auth()
        a["issued_at"] = "2026-12-01T00:00:00+08:00"
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_NOT_YET_VALID)

    def test_t3_wrong_candidate_id(self):
        p, a = _auth()
        a["candidate_id"] = "SL-REVAL-" + "c" * 32
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_CANDIDATE_MISMATCH)

    def test_t4_wrong_commit(self):
        p, a = _auth()
        a["target_commit_sha"] = "c" * 40
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_COMMIT_MISMATCH)

    def test_t5_wrong_repository(self):
        p, a = _auth()
        a["repository_id"] = "999999"
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_REPO_MISMATCH)

    def test_t6_wrong_operation_scope(self):
        p, a = _auth()
        a["authorized_operations"] = ["facts_extract"]   # 缺 collector
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_OPERATION_MISMATCH)

    def test_t6b_unknown_operation(self):
        p, a = _auth()
        a["authorized_operations"] = sorted(AUTH.ALLOWED_OPERATIONS) + ["delete_repo"]
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_OPERATION_MISMATCH)

    def test_t6c_scope_mismatch(self):
        p, a = _auth()
        a["authorized_scope"] = "path_prefix:src/"
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_SCOPE_MISMATCH)

    def test_plan_digest_tampering_rejected(self):
        p, a = _auth()
        p2 = copy.deepcopy(p)
        p2["target_claim_parameters"]["expected_exists"] = False
        r = self._v(p2, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_PLAN_MISMATCH,
                         "计划被篡改必须拒绝")

    def test_revoked_rejected(self):
        p, a = _auth()
        a["revocation_status"] = "revoked"
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_REVOKED)

    def test_missing_fields_rejected(self):
        p, a = _auth()
        del a["authorization_source"]
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_MALFORMED)


class TestAuthorizationTrust(unittest.TestCase):
    """T-7 / T-8：测试授权不能冒充真实审批。"""

    def _v(self, plan, auth, require_production=False):
        return AUTH.validate_execution_authorization(
            candidate=CAND, plan=plan, authorization=auth, now=NOW,
            require_production=require_production)

    def test_t7_test_only_cannot_enter_production(self):
        p, a = _auth()
        self.assertEqual(a["authorization_kind"], AUTH.KIND_TEST_ONLY)
        self.assertTrue(a["test_only"])
        r = self._v(p, a, require_production=True)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_TEST_ONLY_IN_PRODUCTION,
                         "TEST_ONLY 不得进入正式调度")

    def test_t7b_test_only_ok_in_test_mode(self):
        p, a = _auth()
        r = self._v(p, a, require_production=False)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["test_only"])

    def test_t8_approved_true_alone_is_not_trust(self):
        """★ 不得只凭 approved=true 判定授权可信。"""
        p, a = _auth()
        a["approved"] = True
        a["authorization_source"] = ""      # 无来源
        r = self._v(p, a)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_SELF_APPROVED)

    def test_t8b_agent_source_rejected(self):
        p, a = _auth()
        for src in ("AGENT", "SELF", "MODEL", "LLM"):
            a2 = dict(a); a2["authorization_source"] = src
            r = self._v(p, a2)
            self.assertFalse(r["ok"], src)
            self.assertEqual(r["reason"], AUTH.A_SELF_APPROVED)

    def test_t8c_production_requires_verifiable_kind(self):
        p, a = _auth()
        a["authorization_kind"] = AUTH.KIND_DEV_BATCH
        a.pop("test_only", None)
        r = self._v(p, a, require_production=True)
        self.assertFalse(r["ok"])
        self.assertIn(r["reason"], (AUTH.A_UNKNOWN_SOURCE,
                                    AUTH.A_TEST_ONLY_IN_PRODUCTION))

    def test_t8d_production_requires_proof(self):
        p, a = _auth()
        a["authorization_kind"] = AUTH.KIND_HUMAN_OPERATOR
        a.pop("test_only", None)
        r = self._v(p, a, require_production=True)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_MISSING_PROOF,
                         "正式模式必须有可核验证明")

    def test_platform_kind_not_implemented_as_pass(self):
        """PLATFORM_APPROVAL 是类别名，但本会话没有真实平台回执。"""
        self.assertIn(AUTH.KIND_PLATFORM, AUTH.AUTH_KINDS)
        self.assertIn(AUTH.KIND_PLATFORM, AUTH.PRODUCTION_SAFE_KINDS)
        # 但没有 proof 时仍然拒绝
        p, a = _auth()
        a["authorization_kind"] = AUTH.KIND_PLATFORM
        a.pop("test_only", None)
        r = self._v(p, a, require_production=True)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], AUTH.A_MISSING_PROOF)


if __name__ == "__main__":
    unittest.main(verbosity=2)
