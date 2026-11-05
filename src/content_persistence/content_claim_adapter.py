#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容命题：Claim 构造 + 裁决。★ 复用既有 Claim/Verification 三态，不建第二套状态机。

每种内容命题的裁决契约在此显式声明（支撑 §八 的 supported/refuted/insufficient）。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("evidence_claims", "facts", "storage", "content"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

RULE_VERSION = "content-verifier/1"

# 内容命题的裁决契约（显式，供测试逐条核对）
CONTRACTS = {
    "readme_heading_exists": {
        "supported": "解析器在 COMPLETE 内容中找到同层级同文本标题，且证据范围可核验",
        "refuted": ("只在内容 COMPLETE、解析成功、且该 README 确实无该标题时成立"),
        "insufficient": ("内容不可用/损坏/PARTIAL/解析失败/引用悬空/"
                         "Blob 与 Commit 不一致 → 一律 insufficient"),
        "forbidden": "README 未提到 X ≠ 项目未实现 X",
    },
    "manifest_dependency_declared": {
        "supported": "清单依赖字段中解析到该名字，且内容已验证",
        "refuted": "内容 COMPLETE 且清单有效解析，依赖字段中确无该名字",
        "insufficient": "清单无效/PARTIAL/内容不可用 → insufficient",
        "forbidden": "清单未声明 Y ≠ 项目未使用 Y；声明 ≠ 已安装",
    },
    "manifest_field_present": {
        "supported": "字段真实存在于解析结果",
        "refuted": "内容 COMPLETE 且有效解析，字段不存在",
        "insufficient": "解析失败或内容不完整",
        "forbidden": "字段存在 ≠ 真实部署状态",
    },
}


def build_content_claim(*, claim_type, repository_id, commit_sha, file_path,
                        subject, expected_present=True,
                        snapshot_logical_identity=None,
                        claim_origin="content_extraction"):
    """构造内容命题。★ claim_id 不含事实列表 —— 换证据仍是同一 Claim。"""
    import ec_models as M
    if claim_type not in M.CONTENT_CLAIM_TYPES:
        raise ValueError(f"不支持的内容命题类型：{claim_type}")

    params = {"file_path": file_path,
              "expected_present": bool(expected_present)}
    params.update({k: subject[k] for k in sorted(subject)})
    cid = M.make_claim_id(repository_id=str(repository_id),
                          commit_sha=str(commit_sha),
                          claim_type=claim_type,
                          normalized_parameters=params)
    # normalized_path 在内容命题里表示"目标文件路径"
    _claim = M.Claim(
        claim_id=cid, claim_type=claim_type,
        repository_id=str(repository_id), commit_sha=str(commit_sha),
        normalized_path=file_path, expected_exists=bool(expected_present),
        claim_scope="single_file_content",
        claim_origin=claim_origin,
        snapshot_logical_identity=snapshot_logical_identity)
    # ★ 同时返回主体绑定 —— Claim 模型不存它，验证时必须显式传
    return _claim, dict(subject)


def verify_content_claim(*, claim, facts, content_available,
                         completeness_status, parser_ok=True,
                         subject_binding=None):
    """对内容命题作出裁决。

    ★ 关键：内容不可用/不完整/解析失败 → 一律 insufficient_evidence，
      绝不产出 refuted（无证据不等于否证）。

    返回 {status, reason_code, detail, supported_fact_ids}
    """
    import ec_models as M

    if claim.claim_type not in M.CONTENT_CLAIM_TYPES:
        return {"status": M.INSUFFICIENT,
                "reason_code": M.R_UNSUPPORTED_TYPE,
                "detail": f"不支持的命题类型 {claim.claim_type}",
                "supported_fact_ids": []}

    if not content_available:
        return {"status": M.INSUFFICIENT,
                "reason_code": "CONTENT_UNAVAILABLE",
                "detail": "原始内容不可用（未捕获/损坏）",
                "supported_fact_ids": []}

    if not parser_ok:
        return {"status": M.INSUFFICIENT,
                "reason_code": "PARSER_FAILED",
                "detail": "解析器未能成功解析该内容",
                "supported_fact_ids": []}

    if (completeness_status or "").upper() != "COMPLETE":
        return {"status": M.INSUFFICIENT,
                "reason_code": "CONTENT_PARTIAL",
                "detail": f"内容不完整（{completeness_status}），不能作否定裁决",
                "supported_fact_ids": []}

    # ★ 必须按 subject 精确匹配，不能只按 rule_id ——
    #   否则"查不存在的标题"会命中别的标题，凭空确认一条不存在的命题。
    want_level = claim.expected_exists
    matched = [f for f in (facts or [])
               if _matches(claim, f, subject_binding or {})]
    if matched:
        if want_level:
            return {"status": M.SUPPORTED,
                    "reason_code": "CONTENT_FACT_FOUND",
                    "detail": "内容中确实存在该观察对象",
                    "supported_fact_ids": [f["fact_id"] for f in matched]}
        return {"status": M.REFUTED,
                "reason_code": "CONTENT_FACT_CONTRADICTS",
                "detail": "内容完整且存在与该命题相反的确定性观察",
                "supported_fact_ids": [f["fact_id"] for f in matched]}

    # 没有匹配事实：内容完整且解析成功 → 才允许 refuted（仅否定型命题）
    if not want_level:
        return {"status": M.SUPPORTED,
                "reason_code": "ABSENCE_CONFIRMED_IN_COMPLETE_SCOPE",
                "detail": "内容完整且解析成功，确认不存在该观察对象",
                "supported_fact_ids": []}

    # 肯定型命题但没找到 → insufficient（不是 refuted）
    return {"status": M.INSUFFICIENT,
            "reason_code": "NO_MATCHING_FACT",
            "detail": ("内容可用但未找到匹配事实；"
                       "不代表该内容不存在于项目"),
            "supported_fact_ids": []}


def _matches(claim, fact, subject_binding) -> bool:
    """★ claim 与 fact 的主体必须逐个字段相符。

    subject_binding 由 build_content_claim 返回 —— Claim 模型不存主体参数，
    所以必须显式随 claim 传递，不能靠 rule_id 粗配。
    """
    if fact.get("rule_id") != _rule_of(claim.claim_type):
        return False
    np = fact.get("normalized_parameters") or {}
    if np.get("file_path") != claim.normalized_path:
        return False
    if fact.get("commit_sha") != claim.commit_sha:
        return False
    if str((fact.get("repository_id"))) != str(claim.repository_id):
        return False
    subject = np.get("subject") or {}
    # ★ 子集匹配：claim 声明的每个键都必须与事实相符；
    #   fact 可以带额外元数据（kind/field/constraint），不要求 claim 全声明。
    if not subject_binding:
        return False
    for k, v in subject_binding.items():
        if subject.get(k) != v:
            return False
    return True


_RULE_MAP = {
    "readme_heading_exists": "README_HEADING_EXISTS",
    "manifest_dependency_declared": "MANIFEST_DEPENDENCY_DECLARED",
    "manifest_field_present": "MANIFEST_FIELD_PRESENT",
}


def _rule_of(claim_type):
    return _RULE_MAP.get(claim_type, claim_type)


def claim_contract(claim_type):
    return CONTRACTS.get(claim_type, {})
