#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识视图数据模型。

★ 五条状态轴严格独立，绝不合并成一个 `is_valid`：
  A. verification_status   EC 的证据裁决
  B. freshness_state       Lifecycle 的版本适用性
  C. review_status         人工审核（只有人能改）
  D. execution_status      Runtime 的执行结果
  E. provenance_level + authorization_class   来源与授权（分别判断）
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "lifecycle"),
           str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lc_models as L

VIEW_SCHEMA_VERSION = "knowledge-view/1"
PROJECTION_RULE_VERSION = "projection/1"

# ── 视图装配结果 ────────────────────────────────────────────
OK = "OK"
# 明确诊断码（视图不装配时不返回"没有知识"）
E_VIEW_INTEGRITY_FAILED = "VIEW_INTEGRITY_FAILED"
E_DANGLING_REFERENCE = "DANGLING_REFERENCE"
E_SOURCE_MISSING = "SOURCE_MISSING"
E_VERSION_MISMATCH = "VERSION_MISMATCH"
E_CLAIM_NOT_FOUND = "CLAIM_NOT_FOUND"
E_VERIFICATION_NOT_FOUND = "VERIFICATION_NOT_FOUND"
E_CLAIM_VERIFICATION_MISMATCH = "CLAIM_VERIFICATION_MISMATCH"
E_REPOSITORY_MISMATCH = "REPOSITORY_MISMATCH"
E_COMMIT_MISMATCH = "COMMIT_MISMATCH"
E_EVIDENCE_CORRUPT = "EVIDENCE_CORRUPT"
E_CURRENT_APPLICABILITY_UNKNOWN = "CURRENT_APPLICABILITY_UNKNOWN"
E_PARTIAL_COVERAGE_ONLY = "PARTIAL_COVERAGE_ONLY"

DIAGNOSTIC_CODES = frozenset({
    E_VIEW_INTEGRITY_FAILED, E_DANGLING_REFERENCE, E_SOURCE_MISSING,
    E_VERSION_MISMATCH, E_CLAIM_NOT_FOUND, E_VERIFICATION_NOT_FOUND,
    E_CLAIM_VERIFICATION_MISMATCH, E_REPOSITORY_MISMATCH, E_COMMIT_MISMATCH,
    E_EVIDENCE_CORRUPT, E_CURRENT_APPLICABILITY_UNKNOWN,
    E_PARTIAL_COVERAGE_ONLY,
})

# ── 分发门禁：F1-D 仍 FROZEN_INTERNAL_RESTRICTED ───────────
FREEZE_STATE = "FROZEN_INTERNAL_RESTRICTED"
DISTRIBUTION_BLOCKERS = (
    {"id": "B-1", "status": "OPEN",
     "title": "第三方声明措辞（THIRD_PARTY_NOTICES 越界）"},
    {"id": "B-2", "status": "OPEN",
     "title": "UPSTREAM-06 法律审查（28 项 copy_permitted=false）"},
    {"id": "B-3", "status": "OPEN",
     "title": "CC BY 4.0 署名（SL-CAP-0023 含 6 词原句）"},
)

# 知识命题不表示分发许可 —— 无论裁决结果如何
DISTRIBUTION_ALLOWED = False
DISTRIBUTION_SCOPE = "LOCAL_INTERNAL_TEST_ONLY"


def distribution_restrictions() -> dict:
    """★ 分发限制是**独立结论**，不因 Claim supported 而变。"""
    return {
        "distribution_allowed": DISTRIBUTION_ALLOWED,
        "freeze_state": FREEZE_STATE,
        "scope": DISTRIBUTION_SCOPE,
        "blockers": [dict(b) for b in DISTRIBUTION_BLOCKERS],
        "note": ("知识验证结果与来源许可证是两个独立结论；"
                 "supported 不推导出 distribution_allowed=true"),
    }


def limitations_of(*, verification_status, freshness_state,
                   review_status, provenance_level, execution_status,
                   partial_coverage=False, coverage_scope=None) -> list:
    """把"这条知识能用到哪"的边界写成结构化列表。"""
    out = []
    if provenance_level == "HISTORICAL_REAL_DATA":
        out.append("来源为历史真实观测，不是当前 Ref 的实时状态")
    elif provenance_level == "SYNTHETIC_FIXTURE":
        out.append("来源为合成夹具，仅证明状态转换，不代表真实仓库内容")
    elif provenance_level == "REAL_LIVE_API":
        out.append("来源为实时 API 观测，其时效性以观测时间为准")

    if freshness_state == L.VERSION_ALIGNED:
        out.append("VERSION_ALIGNED 仅表示某次可信观测时 Ref 与基线一致，"
                   "不保证此后仍然一致")
    elif freshness_state == L.POSSIBLY_STALE:
        out.append("POSSIBLY_STALE 表示 Ref 已移动，基线结论可能不再适用；"
                   "不等于旧结论被推翻")
    elif freshness_state == L.UNKNOWN:
        out.append("新鲜度未知：没有足够证据判断适用性")

    if verification_status == "insufficient_evidence":
        out.append("证据不足，不得据此得出肯定或否定结论")
    if partial_coverage:
        out.append(f"仅覆盖局部范围（{coverage_scope or 'PARTIAL'}），"
                   "未覆盖部分不得判为不存在")

    if review_status != "approved":
        out.append(f"人工审核状态为 {review_status}，未经人工批准")
    if execution_status is not None and execution_status != "SUCCESS":
        out.append(f"执行状态 {execution_status}，本次运行未成功完成")

    out.append("分发门禁仍为 FROZEN_INTERNAL_RESTRICTED，仅限本地内部消费")
    return out


def make_view_id(*, query_scope: str, source_asset_refs,
                 content_digests, subject_id=None) -> str:
    """★ 确定性身份。

    - 输入顺序无关（排序后参与哈希）
    - 时间戳不参与
    - 不含 assembled_at
    """
    import hashlib, json
    payload = {
        "query_scope": query_scope,
        "subject_id": subject_id,
        "source_asset_refs": sorted(source_asset_refs),
        "content_digests": sorted(content_digests),
        "view_schema_version": VIEW_SCHEMA_VERSION,
        "projection_rule_version": PROJECTION_RULE_VERSION,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return "SL-VIEW-" + hashlib.sha256(raw.encode()).hexdigest()[:32]
