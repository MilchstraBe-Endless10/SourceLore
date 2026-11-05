#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态模块关系裁决。

★ 复用既有 EC 三态与**封闭 reason_code 码表**（D-17 教训）。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("evidence_claims", "facts", "storage", "source_analysis"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

RULE_VERSION = "module-relation-verifier/1"

# 状态 → 合法 EC reason_code（★ 只用封闭集里的码）
_STATE_REASON = {
    "CONFIG_NOT_CAPTURED": "FACT_NOT_FOUND",
    "CONFIG_CONTENT_NOT_CAPTURED": "FACT_NOT_FOUND",
    "CONFIG_INHERITANCE_UNRESOLVED": "SCOPE_NOT_COVERING",
    "CONFIG_INHERITANCE_CYCLE": "CONFLICTING_EVIDENCE",
    "CONFIG_INHERITANCE_TOO_DEEP": "SCOPE_NOT_COVERING",
    "CONFIG_PARSE_FAILED": "FACT_INTEGRITY_FAILED",
    "CONFIG_INTEGRITY_FAILED": "FACT_INTEGRITY_FAILED",
    "CONFIG_COMMIT_MISMATCH": "COMMIT_MISMATCH",
    "CONFIG_AMBIGUOUS_SCOPE": "CONFLICTING_EVIDENCE",
    "RESOLUTION_CONTEXT_INCOMPLETE": "PARTIAL_EVIDENCE_INSUFFICIENT",
    "UNSUPPORTED_RESOLUTION_POLICY": "UNSUPPORTED_CLAIM_TYPE",
    "INSUFFICIENT_TREE_COVERAGE": "SCOPE_NOT_COVERING",
    "AMBIGUOUS_CANDIDATES": "CONFLICTING_EVIDENCE",
    "TARGET_BLOB_MISSING": "FACT_NOT_FOUND",
    "PATH_ESCAPES_REPOSITORY": "PATH_MISMATCH",
    "EXTERNAL_OR_UNRESOLVED": "FACT_NOT_FOUND",
    "DYNAMIC_SPECIFIER": "UNSUPPORTED_CLAIM_TYPE",
    "BUDGET_EXCEEDED": "SCOPE_NOT_COVERING",
}

CONTRACTS = {
    "static_module_relation_resolved": {
        "supported": "Import 声明 + 配置映射 + 目标 Tree 三组证据齐备且精确匹配",
        "refuted": "仅在受支持的有界范围内可确定否定；一般不产 refuted",
        "insufficient": "配置缺失/继承未解/模式未知/候选歧义/Tree 不完整 → abstain",
        "forbidden": "静态映射 ≠ 运行时加载成功；paths 不改写输出导入路径",
    },
    "module_config_paths_declared": {
        "supported": "该配置在指定 Commit 中确实声明该 paths 规则",
        "refuted": "配置完整解析且确无该规则",
        "insufficient": "配置未采集/解析失败/继承未解",
        "forbidden": "声明 ≠ 生效（可能被覆盖或被工具忽略）",
    },
}


def ec_reason(state):
    """★ 映射到 EC 封闭码；不可映射 → EVIDENCE_FIELD_MISSING。"""
    return _STATE_REASON.get(state, "EVIDENCE_FIELD_MISSING")


def build_relation_claim(*, repository_id, commit_sha, importing_file_path,
                         module_specifier, import_kind, is_type_only,
                         expected_target_path=None,
                         expected_matched_rule=None):
    import ec_models as M
    params = {
        "importing_file_path": importing_file_path,
        "module_specifier": module_specifier,
        "import_kind": import_kind,
        "is_type_only": bool(is_type_only),
        "expected_target_path": expected_target_path,
        "expected_matched_rule": expected_matched_rule,
    }
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=M.CLAIM_MODULE_RELATION,
                          normalized_parameters=params)
    claim = M.Claim(
        claim_id=cid, claim_type=M.CLAIM_MODULE_RELATION,
        repository_id=str(repository_id), commit_sha=str(commit_sha),
        normalized_path=importing_file_path, expected_exists=True,
        claim_scope="single_module_reference",
        claim_origin="config_aware_resolution")
    return claim, params


def verify_relation_claim(*, claim, facts, resolution_state,
                          evidence_complete, subject_binding):
    """三层裁决。★ 任何不确定 → insufficient，绝不 refuted。"""
    import ec_models as M

    if claim.claim_type not in CONTRACTS:
        return {"status": M.INSUFFICIENT,
                "reason_code": "UNSUPPORTED_CLAIM_TYPE",
                "detail": f"不支持的命题类型 {claim.claim_type}",
                "supported_fact_ids": []}

    if resolution_state != "LOCAL_MODULE_RESOLVED":
        return {"status": M.INSUFFICIENT,
                "reason_code": ec_reason(resolution_state),
                "detail": f"解析状态 {resolution_state}，不出确定结论",
                "supported_fact_ids": []}

    if not evidence_complete:
        return {"status": M.INSUFFICIENT,
                "reason_code": "EVIDENCE_FIELD_MISSING",
                "detail": "Import / Config / Target 三组证据不全",
                "supported_fact_ids": []}

    matched = [f for f in (facts or []) if _matches(claim, f, subject_binding)]
    if not matched:
        return {"status": M.INSUFFICIENT,
                "reason_code": "NO_MATCHING_FACT",
                "detail": "无匹配的静态关系事实",
                "supported_fact_ids": []}

    return {"status": M.SUPPORTED, "reason_code": "FACT_FOUND",
            "detail": "静态模块关系在配置与 Tree 证据下成立",
            "supported_fact_ids": [f["fact_id"] for f in matched]}


def _matches(claim, fact, binding):
    if fact.get("rule_id") != "STATIC_MODULE_RELATION":
        return False
    # ★ 兼容两种形态：A 层原始 payload（normalized_parameters.subject）
    #   与查询层扁平结果（顶层 subject / 直接挂在记录上）
    np = fact.get("normalized_parameters") or fact
    subject = np.get("subject") or fact.get("subject") or {}
    if not subject and fact.get("resolved_target_path") is not None:
        subject = fact
    if np.get("importing_file_path") != claim.normalized_path:
        return False
    if str(fact.get("commit_sha")) != str(claim.commit_sha):
        return False
    if str(fact.get("repository_id")) != str(claim.repository_id):
        return False
    for k in ("module_specifier", "import_kind", "is_type_only",
              "expected_target_path", "expected_matched_rule"):
        want = binding.get(k)
        if want is None:
            continue
        got = subject.get(k)
        if k == "expected_target_path":
            got = subject.get("resolved_target_path")
        elif k == "expected_matched_rule":
            got = subject.get("matched_config_rule")
        if got != want:
            return False
    return True


def evidence_complete(*, resolution):
    """三组证据齐备检查（★ 不只看非空）。"""
    if not resolution.get("import_fact_id"):
        return False, "IMPORT_EVIDENCE_MISSING"
    if not resolution.get("config_observation_ids"):
        return False, "CONFIG_EVIDENCE_MISSING"
    if not resolution.get("resolved_target_path"):
        return False, "TARGET_PATH_MISSING"
    if not resolution.get("importing_blob_oid"):
        return False, "IMPORT_BLOB_MISSING"
    if not resolution.get("config_blob_oids"):
        return False, "CONFIG_BLOB_MISSING"
    if not (resolution.get("evidence_refs") or []):
        return False, "EVIDENCE_REFS_EMPTY"
    return True, None
