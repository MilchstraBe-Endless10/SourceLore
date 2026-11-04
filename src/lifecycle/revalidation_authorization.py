#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行授权门禁。

**默认拒绝。** 只有满足全部条件才放行。

五类"批准"严格分开，任何一种都不能代替另一种：
  DEV_BATCH_APPROVAL        开发批次批准（本批就是这种）
  TEST_ONLY                 测试夹具生成的隔离授权
  HUMAN_OPERATOR            真实人类操作授权（需可核验来源）
  PLATFORM_APPROVAL         BotHarness 平台审批（Y6-P3，仍 UNVERIFIED）
  EXECUTION_AUTHORIZATION   具体执行所获得的授权（本模块校验的对象）

★ 硬规则：不得凭 JSON 字段 `approved=true` 判定授权可信。
★ 硬规则：Agent 不能自行产生可信的人工批准证据。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lc_models as L

# ── 四类批准 ────────────────────────────────────────────────
KIND_DEV_BATCH = "DEV_BATCH_APPROVAL"
KIND_TEST_ONLY = "TEST_ONLY"
KIND_HUMAN_OPERATOR = "HUMAN_OPERATOR"
KIND_PLATFORM = "PLATFORM_APPROVAL"
AUTH_KINDS = frozenset({KIND_DEV_BATCH, KIND_TEST_ONLY,
                        KIND_HUMAN_OPERATOR, KIND_PLATFORM})

# ★ 只有这两类"来源"被认为**可核验**
VERIFIABLE_SOURCES = frozenset({KIND_HUMAN_OPERATOR, KIND_PLATFORM})
# ★ TEST_ONLY 永不进入正式调度
PRODUCTION_SAFE_KINDS = frozenset({KIND_HUMAN_OPERATOR, KIND_PLATFORM})

# ── 拒绝原因 ──────────────────────────────────────────────
A_NO_AUTHORIZATION = "NO_AUTHORIZATION"
A_EXPIRED = "AUTHORIZATION_EXPIRED"
A_NOT_YET_VALID = "AUTHORIZATION_NOT_YET_VALID"
A_CANDIDATE_MISMATCH = "CANDIDATE_ID_MISMATCH"
A_COMMIT_MISMATCH = "TARGET_COMMIT_MISMATCH"
A_REPO_MISMATCH = "REPOSITORY_MISMATCH"
A_REF_MISMATCH = "REQUESTED_REF_MISMATCH"
A_OPERATION_MISMATCH = "AUTHORIZED_OPERATIONS_MISMATCH"
A_SCOPE_MISMATCH = "AUTHORIZED_SCOPE_MISMATCH"
A_REVOKED = "AUTHORIZATION_REVOKED"
A_UNKNOWN_SOURCE = "UNKNOWN_AUTHORIZATION_SOURCE"
A_TEST_ONLY_IN_PRODUCTION = "TEST_ONLY_IN_PRODUCTION"
A_MISSING_PROOF = "MISSING_VERIFIABLE_PROOF"
A_PLAN_MISMATCH = "PLAN_DIGEST_MISMATCH"
A_SELF_APPROVED = "AGENT_SELF_APPROVED"
A_MALFORMED = "MALFORMED_AUTHORIZATION"

DENY_REASONS = frozenset({
    A_NO_AUTHORIZATION, A_EXPIRED, A_NOT_YET_VALID, A_CANDIDATE_MISMATCH,
    A_COMMIT_MISMATCH, A_REPO_MISMATCH, A_REF_MISMATCH, A_OPERATION_MISMATCH,
    A_SCOPE_MISMATCH, A_REVOKED, A_UNKNOWN_SOURCE, A_TEST_ONLY_IN_PRODUCTION,
    A_MISSING_PROOF, A_PLAN_MISMATCH, A_SELF_APPROVED, A_MALFORMED})

# 允许执行的操作（固定集合，不接受任意扩充）
ALLOWED_OPERATIONS = frozenset({
    "collector_fixed_commit_fetch",
    "facts_extract",
    "target_claim_create",
    "evidence_claims_verify",
})

REQUIRED_FIELDS = (
    "authorization_id", "authorization_kind", "authorization_subject",
    "authorization_source", "candidate_id", "repository_id",
    "requested_ref", "target_commit_sha", "authorized_operations",
    "authorized_scope", "plan_digest", "issued_at", "expires_at",
    "revocation_status",
)


def make_test_authorization(*, candidate_id: str, repository_id: str,
                            requested_ref: str, target_commit_sha: str,
                            plan_digest: str, authorized_scope: str,
                            issued_at: str, expires_at: str,
                            subject: str = "test-fixture",
                            operations=None) -> dict:
    """★ 测试夹具专用。生成 TEST_ONLY 授权。

    ★ 明确标记 TEST_ONLY：无 proof 字段、kind=TEST_ONLY，
      因此**永远不能进入正式调度**（PRODUCTION_SAFE_KINDS 不含它）。
    """
    return {
        "authorization_id": "SL-TESTAUTH-" + L.sha256_of({
            "candidate_id": candidate_id, "commit": target_commit_sha,
            "plan_digest": plan_digest, "issued": issued_at})[:24],
        "authorization_kind": KIND_TEST_ONLY,
        "authorization_subject": subject,
        "authorization_source": "TEST_FIXTURE",
        "candidate_id": candidate_id,
        "repository_id": str(repository_id),
        "requested_ref": requested_ref,
        "target_commit_sha": target_commit_sha,
        "authorized_operations": sorted(operations or ALLOWED_OPERATIONS),
        "authorized_scope": authorized_scope,
        "plan_digest": plan_digest,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "revocation_status": "active",
        # ★ 刻意不含 approved / proof —— 测试授权不可被当作真实批准
        "test_only": True,
    }


def validate_execution_authorization(*, candidate, plan, authorization,
                                     now, require_production=False) -> dict:
    """校验执行授权。返回 {"ok": bool, "reason": str, "detail": str}。

    ★ 默认拒绝：任何缺失/不明都拒绝。
    """
    if not authorization or not isinstance(authorization, dict):
        return _deny(A_NO_AUTHORIZATION, "未提供授权")

    missing = [f for f in REQUIRED_FIELDS if f not in authorization]
    if missing:
        return _deny(A_MALFORMED, f"缺字段 {missing}")

    # ★ 不得只凭 approved=true 判定
    if authorization.get("approved") is True and \
            not authorization.get("authorization_source"):
        return _deny(A_SELF_APPROVED,
                     "仅凭 approved=true 不足以证明授权")

    kind = authorization["authorization_kind"]
    if kind not in AUTH_KINDS:
        return _deny(A_UNKNOWN_SOURCE, f"未知授权类别 {kind!r}")

    source = authorization["authorization_source"]
    if source in ("AGENT", "SELF", "MODEL", "LLM"):
        return _deny(A_SELF_APPROVED, f"Agent 不能自行批准（source={source}）")

    # ★ TEST_ONLY 永不进入正式调度
    if kind == KIND_TEST_ONLY or authorization.get("test_only"):
        if require_production:
            return _deny(A_TEST_ONLY_IN_PRODUCTION,
                         "TEST_ONLY 授权不得进入正式调度")
        # 测试模式：仍需通过其余结构校验

    if require_production and kind not in PRODUCTION_SAFE_KINDS:
        return _deny(A_TEST_ONLY_IN_PRODUCTION,
                     f"正式调度只接受 {sorted(PRODUCTION_SAFE_KINDS)}")

    # 可核验来源（正式模式必需）
    proof = authorization.get("authorization_proof")
    if require_production:
        if kind not in VERIFIABLE_SOURCES:
            return _deny(A_UNKNOWN_SOURCE,
                         f"来源不可核验: {kind}")
        if not proof:
            return _deny(A_MISSING_PROOF, "缺少可核验的授权证明")

    # 撤销
    if authorization.get("revocation_status") not in ("active", None):
        return _deny(A_REVOKED,
                     f"授权状态={authorization.get('revocation_status')}")

    # 时间窗
    try:
        if expires_at_expired(authorization["expires_at"], now):
            return _deny(A_EXPIRED, f"已过期: {authorization['expires_at']}")
        if not_at_yet(authorization["issued_at"], now):
            return _deny(A_NOT_YET_VALID,
                         f"尚未生效: {authorization['issued_at']}")
    except ValueError as e:
        return _deny(A_MALFORMED, f"时间字段非法: {e}")

    # 目标绑定
    if authorization["candidate_id"] != candidate["candidate_id"]:
        return _deny(A_CANDIDATE_MISMATCH,
                     f"{authorization['candidate_id']} != {candidate['candidate_id']}")
    if authorization["target_commit_sha"] != candidate["target_commit_sha"]:
        return _deny(A_COMMIT_MISMATCH,
                     f"{authorization['target_commit_sha']} != {candidate['target_commit_sha']}")
    if str(authorization["repository_id"]) != str(candidate["repository_id"]):
        return _deny(A_REPO_MISMATCH)
    if authorization["requested_ref"] != candidate["requested_ref"]:
        return _deny(A_REF_MISMATCH)

    # ★ 计划必须绑定：**重新计算**实际计划的 digest，与授权里的比对。
    #   （初版只比较 plan["plan_digest"] 字段 —— 若攻击者同时改计划内容和该字段
    #     就绕过了。必须重算。）
    actual_digest = plan_digest_of(plan)
    if authorization["plan_digest"] != actual_digest:
        return _deny(A_PLAN_MISMATCH,
                     f"授权绑定 {authorization['plan_digest']} ≠ 实际 {actual_digest}")

    # 操作范围
    ops = set(authorization["authorized_operations"])
    if not ops:
        return _deny(A_OPERATION_MISMATCH, "授权操作集为空")
    unknown_ops = ops - ALLOWED_OPERATIONS
    if unknown_ops:
        return _deny(A_OPERATION_MISMATCH,
                     f"含未允许操作 {sorted(unknown_ops)}")
    needed = set(plan.get("required_operations") or ALLOWED_OPERATIONS)
    if not needed.issubset(ops):
        return _deny(A_OPERATION_MISMATCH,
                     f"缺少必要操作 {sorted(needed - ops)}")

    # 采集范围
    if authorization["authorized_scope"] != plan.get("intended_collector_scope"):
        return _deny(A_SCOPE_MISMATCH,
                     f"{authorization['authorized_scope']} != "
                     f"{plan.get('intended_collector_scope')}")

    return {"ok": True, "reason": None,
            "detail": f"授权 {authorization['authorization_id']} 校验通过",
            "authorization_kind": kind,
            "test_only": bool(authorization.get("test_only"))}


def _deny(reason: str, detail: str = "") -> dict:
    return {"ok": False, "reason": reason, "detail": detail}


def expires_at_expired(expires_at: str, now: str) -> bool:
    return _parse(expires_at) <= _parse(now)


def not_at_yet(issued_at: str, now: str) -> bool:
    return _parse(issued_at) > _parse(now)


def _parse(ts: str):
    from datetime import datetime
    if not isinstance(ts, str):
        raise ValueError(ts)
    s = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(ts)


def plan_digest_of(plan: dict) -> str:
    """计划的确定性摘要。授权绑定它，防止计划被篡改。"""
    import json
    core = {k: plan.get(k) for k in
            ("candidate_id", "target_commit_sha", "repository_id",
             "requested_ref", "intended_collector_scope",
             "intended_fact_rules", "intended_ec_rule_version",
             "target_claim_parameters")}
    raw = json.dumps(core, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    import hashlib
    return "PLAN-" + hashlib.sha256(raw.encode()).hexdigest()[:32]
