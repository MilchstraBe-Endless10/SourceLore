#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码命题：Claim 构造 + 裁决契约。

★ 复用既有 EC 三态与封闭 reason_code 码表（D-17 教训）。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("evidence_claims", "facts", "storage", "source_analysis"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

RULE_VERSION = "source-verifier/1"

# 源码命题类型（与 ec_models 的 CLAIM_* 对应）
CLAIM_SYMBOL = "source_symbol_declared"
CLAIM_IMPORT = "source_import_declared"
CLAIM_LOCAL_MODULE = "source_local_module_resolved"

# 裁决契约（显式，供测试逐条核对）
CONTRACTS = {
    CLAIM_SYMBOL: {
        "supported": "文件在指定 Commit 中声明了该 qualified_name 与 kind 的符号，且字节范围可核验",
        "refuted": "文件 COMPLETE、AST 解析成功，且该 qualified_name+kind 的声明确实不存在",
        "insufficient": "内容未采集/损坏/PARTIAL/解析失败/跨 Commit/跨仓库 → 一律 abstain",
        "forbidden": "存在声明 ≠ 函数被执行 ≠ 类能完成某项任务",
    },
    CLAIM_IMPORT: {
        "supported": "文件包含对指定模块的静态导入声明",
        "refuted": "文件 COMPLETE 且解析成功，确无该导入声明",
        "insufficient": "解析失败或内容不完整",
        "forbidden": "静态导入 ≠ 依赖已安装 ≠ 导入一定成功 ≠ 运行时必执行",
    },
    CLAIM_LOCAL_MODULE: {
        "supported": "在**当前 Commit 已登记 Tree** 中存在唯一候选路径",
        "refuted": "Tree 完整且确认无候选（须显式给出）",
        "insufficient": "Tree 覆盖不足 / 候选歧义 / 不支持的形式",
        "forbidden": "路径匹配 ≠ 运行时导入成功；不构成依赖图",
    },
}

_EC_REASON = {
    "CONTENT_UNAVAILABLE": "FACT_NOT_FOUND",
    "PARSER_FAILED": "FACT_INTEGRITY_FAILED",
    "NO_MATCHING_FACT": "FACT_NOT_FOUND",
    "CONTENT_PARTIAL": "PARTIAL_EVIDENCE_INSUFFICIENT",
    "COMMIT_MISMATCH": "COMMIT_MISMATCH",
    "REPOSITORY_MISMATCH": "REPOSITORY_MISMATCH",
    "PATH_MISMATCH": "PATH_MISMATCH",
    "TREE_INSUFFICIENT": "SCOPE_NOT_COVERING",
    "AMBIGUOUS": "CONFLICTING_EVIDENCE",
    "UNSUPPORTED_TYPE": "UNSUPPORTED_CLAIM_TYPE",
}


def ec_reason(status, reason):
    """★ 映射到 EC 封闭码表；supported 不带 reason。"""
    if status == "supported":
        return None
    return _EC_REASON.get(reason, "EVIDENCE_FIELD_MISSING")


def build_symbol_claim(*, repository_id, commit_sha, file_path,
                       qualified_name, symbol_kind, expected_present=True):
    import ec_models as M
    import source_models as SM
    params = {"file_path": file_path, "qualified_name": qualified_name,
              "symbol_kind": symbol_kind,
              "expected_present": bool(expected_present)}
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=CLAIM_SYMBOL,
                          normalized_parameters=params)
    claim = M.Claim(
        claim_id=cid, claim_type=CLAIM_SYMBOL,
        repository_id=str(repository_id), commit_sha=str(commit_sha),
        normalized_path=file_path, expected_exists=bool(expected_present),
        claim_scope="single_file_source", claim_origin="source_extraction")
    return claim, {"qualified_name": qualified_name,
                   "symbol_kind": symbol_kind}


def build_import_claim(*, repository_id, commit_sha, file_path,
                       module_name, imported_name=None, expected_present=True):
    import ec_models as M
    params = {"file_path": file_path, "module_name": module_name,
              "imported_name": imported_name,
              "expected_present": bool(expected_present)}
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=CLAIM_IMPORT,
                          normalized_parameters=params)
    claim = M.Claim(
        claim_id=cid, claim_type=CLAIM_IMPORT,
        repository_id=str(repository_id), commit_sha=str(commit_sha),
        normalized_path=file_path, expected_exists=bool(expected_present),
        claim_scope="single_file_source", claim_origin="source_extraction")
    return claim, {"module_name": module_name,
                   "imported_name": imported_name}


def verify_source_claim(*, claim, facts, content_available,
                        completeness_status, parser_ok=True,
                        subject_binding=None):
    """裁决。★ 任何不确定都 abstain，绝不 refuted。"""
    import ec_models as M
    import source_models as SM

    if claim.claim_type not in CONTRACTS:
        return {"status": M.INSUFFICIENT, "reason_code": "UNSUPPORTED_TYPE",
                "detail": f"不支持的源码命题 {claim.claim_type}",
                "supported_fact_ids": []}

    if not content_available:
        return {"status": M.INSUFFICIENT, "reason_code": "CONTENT_UNAVAILABLE",
                "detail": "原始源码字节不可用", "supported_fact_ids": []}
    if not parser_ok:
        return {"status": M.INSUFFICIENT, "reason_code": "PARSER_FAILED",
                "detail": "AST 解析失败", "supported_fact_ids": []}
    if (completeness_status or "").upper() != "COMPLETE":
        return {"status": M.INSUFFICIENT, "reason_code": "CONTENT_PARTIAL",
                "detail": f"内容不完整（{completeness_status}）",
                "supported_fact_ids": []}

    binding = subject_binding or {}
    matched = [f for f in (facts or []) if _matches(claim, f, binding)]
    want = claim.expected_exists

    if matched:
        if want:
            return {"status": M.SUPPORTED, "reason_code": "FACT_FOUND",
                    "detail": "源文件中确实存在该声明",
                    "supported_fact_ids": [f["fact_id"] for f in matched]}
        return {"status": M.REFUTED, "reason_code": "CONFLICTING_EVIDENCE",
                "detail": "存在与命题相反的确定性声明",
                "supported_fact_ids": [f["fact_id"] for f in matched]}

    if not want:
        return {"status": M.SUPPORTED, "reason_code": "ABSENCE_CONFIRMED",
                "detail": "文件完整且解析成功，确认无该声明",
                "supported_fact_ids": []}

    return {"status": M.INSUFFICIENT, "reason_code": "NO_MATCHING_FACT",
            "detail": "内容可用但无匹配声明；不代表该声明在项目其他文件不存在",
            "supported_fact_ids": []}


def _matches(claim, fact, binding):
    """★ 逐字段比对：rule + file_path + commit + repo + 类型化 Subject。"""
    want_rule = {"source_symbol_declared": "SOURCE_SYMBOL_DECLARED",
                 "source_import_declared": "SOURCE_IMPORT_DECLARED",
                 }.get(claim.claim_type)
    if fact.get("rule_id") != want_rule:
        return False
    # ★ 兼容两种形态：A 层原始 payload（有 normalized_parameters）
    #   与查询层扁平化结果（file_path/subject 直接挂在顶层）
    np = fact.get("normalized_parameters") or fact
    if np.get("file_path") != claim.normalized_path:
        return False
    if str(fact.get("commit_sha")) != str(claim.commit_sha):
        return False
    if str(fact.get("repository_id")) != str(claim.repository_id):
        return False
    subject = np.get("subject") or fact.get("subject") or {}
    if not binding:
        return False
    for k, v in binding.items():
        if subject.get(k) != v:
            return False
    return True


def claim_contract(claim_type):
    return CONTRACTS.get(claim_type, {})
