#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TS 项目相关裁决。★ 只用 EC 封闭 reason_code。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("evidence_claims", "facts", "storage", "source_analysis"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

RULE_VERSION = "ts-project-verifier/1"

# ★ 状态 → 合法 EC reason_code（数量与枚举全部在封闭集内）
_STATUS_REASON = {
    "PROJECT_CONFIG_NOT_CAPTURED": "FACT_NOT_FOUND",
    "PROJECT_CONFIG_INVALID": "FACT_INTEGRITY_FAILED",
    "PROJECT_CONFIG_INHERITANCE_UNRESOLVED": "SCOPE_NOT_COVERING",
    "PROJECT_CONFIG_AMBIGUOUS": "CONFLICTING_EVIDENCE",
    "PROJECT_REFERENCE_TARGET_NOT_CAPTURED": "FACT_NOT_FOUND",
    "PROJECT_REFERENCE_TARGET_MISSING": "FACT_NOT_FOUND",
    "PROJECT_REFERENCE_OUTSIDE_REPOSITORY": "PATH_MISMATCH",
    "PROJECT_REFERENCE_CYCLE": "CONFLICTING_EVIDENCE",
    "PROJECT_REFERENCE_DEPTH_EXCEEDED": "SCOPE_NOT_COVERING",
    "INPUT_NOT_PROVEN": "FACT_NOT_FOUND",
    "INPUT_MATCHED_MULTIPLE_PROJECTS": "CONFLICTING_EVIDENCE",
    "INPUT_EXCLUDED_FROM_INCLUDE": "PARTIAL_EVIDENCE_INSUFFICIENT",
    "INPUT_POSSIBLE_VIA_IMPORT": "PARTIAL_EVIDENCE_INSUFFICIENT",
    "CONFIG_INCOMPLETE": "PARTIAL_EVIDENCE_INSUFFICIENT",
    "UNSUPPORTED_SELECTION_RULE": "UNSUPPORTED_CLAIM_TYPE",
    "PROJECT_CONTEXT_AMBIGUOUS": "CONFLICTING_EVIDENCE",
    "PROJECT_CONTEXT_NONE": "FACT_NOT_FOUND",
}

CONTRACTS = {
    "tsconfig_project_declared": {
        "supported": "该配置在指定 Commit 中确实存在且被解析为 TS 项目配置",
        "refuted": "配置完整解析且确认不是有效 TS 项目配置",
        "insufficient": "配置未采集/解析失败/继承未解 → abstain",
        "forbidden": "配置存在 ≠ 项目构建成功 ≠ 类型检查通过",
    },
    "tsconfig_project_reference_declared": {
        "supported": "项目 A 的配置声明引用了 B 的配置，且目标配置已验证存在",
        "refuted": "仅在有界完整范围内可确定否定",
        "insufficient": "目标未采集/缺失/越界/循环 → abstain",
        "forbidden": "声明引用 ≠ B 已构建 ≠ A 已使用 B 的产物",
    },
    "tsconfig_file_membership_candidate": {
        "supported": "文件在受支持的选择规则下被该项目选中（files 或 include）",
        "refuted": "仅在规则明确且集合完整时可确定否定",
        "insufficient": "规则不支持/配置不完整/Tree 不足/多项目 → abstain",
        "forbidden": "输入选择 ≠ 类型检查通过；exclude ≠ 永不进入 Program",
    },
}


def ec_reason(state):
    return _STATUS_REASON.get(state, "EVIDENCE_FIELD_MISSING")


def legal_states():
    return sorted(_STATUS_REASON)


def build_project_claim(*, repository_id, commit_sha, config_path):
    import ec_models as M
    params = {"config_path": config_path}
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=M.CLAIM_TS_PROJECT,
                          normalized_parameters=params)
    return M.Claim(claim_id=cid, claim_type=M.CLAIM_TS_PROJECT,
                   repository_id=str(repository_id),
                   commit_sha=str(commit_sha),
                   normalized_path=config_path, expected_exists=True,
                   claim_scope="single_project_config",
                   claim_origin="ts_project_discovery"), params


def build_reference_claim(*, repository_id, commit_sha, from_config_path,
                          declared_path, expected_to_config_path=None):
    import ec_models as M
    params = {"from_config_path": from_config_path,
              "declared_path": declared_path,
              "expected_to_config_path": expected_to_config_path}
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=M.CLAIM_TS_PROJECT_REFERENCE,
                          normalized_parameters=params)
    return M.Claim(claim_id=cid,
                   claim_type=M.CLAIM_TS_PROJECT_REFERENCE,
                   repository_id=str(repository_id),
                   commit_sha=str(commit_sha),
                   normalized_path=from_config_path, expected_exists=True,
                   claim_scope="single_reference",
                   claim_origin="ts_project_reference"), params


def build_membership_claim(*, repository_id, commit_sha, config_path,
                           source_file_path, expected_state=None):
    import ec_models as M
    params = {"config_path": config_path,
              "source_file_path": source_file_path,
              "expected_state": expected_state}
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=M.CLAIM_TS_MEMBERSHIP,
                          normalized_parameters=params)
    return M.Claim(claim_id=cid, claim_type=M.CLAIM_TS_MEMBERSHIP,
                   repository_id=str(repository_id),
                   commit_sha=str(commit_sha),
                   normalized_path=source_file_path, expected_exists=True,
                   claim_scope="single_file_membership",
                   claim_origin="ts_file_selection"), params


_SELECTED_STATES = ("INPUT_EXPLICITLY_LISTED", "INPUT_MATCHED_INCLUDE")


def verify_ts_claim(*, claim, facts, status, subject_binding,
                    evidence_complete=True):
    """统一裁决。★ 任何不确定 → insufficient。"""
    import ec_models as M

    if claim.claim_type not in CONTRACTS:
        return {"status": M.INSUFFICIENT,
                "reason_code": "UNSUPPORTED_CLAIM_TYPE",
                "detail": f"不支持的命题类型 {claim.claim_type}",
                "supported_fact_ids": []}

    if not evidence_complete:
        return {"status": M.INSUFFICIENT,
                "reason_code": "EVIDENCE_FIELD_MISSING",
                "detail": "关键证据缺失", "supported_fact_ids": []}

    matched = [f for f in (facts or []) if _matches(claim, f, subject_binding)]

    if claim.claim_type == M.CLAIM_TS_MEMBERSHIP:
        if status not in _SELECTED_STATES:
            return {"status": M.INSUFFICIENT,
                    "reason_code": ec_reason(status),
                    "detail": f"选择状态 {status} 不出确定结论",
                    "supported_fact_ids": []}
        if not matched:
            return {"status": M.INSUFFICIENT,
                    "reason_code": "NO_MATCHING_FACT",
                    "detail": "无匹配的归属事实",
                    "supported_fact_ids": []}
        return {"status": M.SUPPORTED, "reason_code": "FACT_FOUND",
                "detail": "文件在受支持规则下被该项目选中",
                "supported_fact_ids": [f["fact_id"] for f in matched]}

    if status not in ("PROJECT_CONFIG_VERIFIED",
                      "PROJECT_REFERENCE_TARGET_VERIFIED"):
        return {"status": M.INSUFFICIENT, "reason_code": ec_reason(status),
                "detail": f"状态 {status} 不出确定结论",
                "supported_fact_ids": []}

    if not matched:
        return {"status": M.INSUFFICIENT, "reason_code": "NO_MATCHING_FACT",
                "detail": "无匹配事实", "supported_fact_ids": []}

    return {"status": M.SUPPORTED, "reason_code": "FACT_FOUND",
            "detail": "配置关系成立",
            "supported_fact_ids": [f["fact_id"] for f in matched]}


def _matches(claim, fact, binding):
    want_rule = {
        "tsconfig_project_declared": "TSCONFIG_PROJECT_DECLARED",
        "tsconfig_project_reference_declared":
            "TSCONFIG_PROJECT_REFERENCE_DECLARED",
        "tsconfig_file_membership_candidate":
            "TSCONFIG_FILE_SELECTION_OBSERVED",
    }.get(claim.claim_type)
    if fact.get("rule_id") != want_rule:
        return False
    # ★ 兼容两种形态：
    #   A 层原始 payload → np["subject"]
    #   查询层扁平结果 → 字段直接挂在记录顶层
    np = fact.get("normalized_parameters") or fact
    subject = np.get("subject") or fact.get("subject") or {}
    if not subject:
        # 扁平形态：把记录本身当作 subject
        subject = fact
    if str(fact.get("commit_sha")) != str(claim.commit_sha):
        return False
    if str(fact.get("repository_id")) != str(claim.repository_id):
        return False
    # ★ claim 侧的期望字段名与 fact 侧的实际字段名不同，必须显式映射
    ALIAS = {
        "expected_state": "state",
        "expected_to_config_path": "to_config_path",
    }
    for k, v in (binding or {}).items():
        if v is None:
            continue
        key = ALIAS.get(k, k)
        if subject.get(key) != v:
            return False
    return True
