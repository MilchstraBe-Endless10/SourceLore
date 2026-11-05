#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识卡片数据模型：把 KnowledgeView 投影成**结构化、可渲染**的卡片描述。

★ 只做投影与措辞约束，不重新裁决、不推断祖先关系、不补造缺失。
"""

import sys
import hashlib
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CARD_SCHEMA_VERSION = "knowledge-card/1"
RENDERER_VERSION = "renderer/1"

# ── 裁决措辞（严格忠实，不放大） ──────────────────────────
VERDICT_LABEL = {
    "supported": "支持",
    "refuted": "反驳",
    "insufficient_evidence": "证据不足",
}
VERDICT_MEANING = {
    "supported": "在指定范围内，现有经过验证的证据支持该命题。",
    "refuted": "现有有效反证与该命题矛盾。",
    "insufficient_evidence": "证据不足，无法作出支持或反驳裁决。",
}
# ★ 明确禁止的放大措辞（渲染层不得出现）
FORBIDDEN_PHRASES = (
    "完全正确", "整个项目存在问题", "该软件正确", "肯定不存在",
    "已证明错误", "必然无效", "当前最新", "当前有效", "已发布",
)

FRESHNESS_LABEL = {
    "NOT_APPLICABLE_TO_PINNED": "固定 Commit，不适用时效判断",
    "VERSION_ALIGNED": "观测时版本对齐",
    "POSSIBLY_STALE": "可能已过时",
    "UNKNOWN": "新鲜度未知",
}
FRESHNESS_MEANING = {
    "NOT_APPLICABLE_TO_PINNED":
        "该结论绑定固定 Commit，不随时间推移失效。",
    "VERSION_ALIGNED":
        "在一次可信观测时，所跟踪 Ref 与基线 Commit 一致。"
        "这不保证此后仍然一致。",
    "POSSIBLY_STALE":
        "所跟踪版本已经变化，旧结论对该 Ref 的当前适用性有待核查。"
        "这不表示旧结论已经失效或错误。",
    "UNKNOWN": "没有足够证据判断该结论的当前适用性。",
}

APPLICABILITY_LABEL = {
    "ALIGNED_AT_OBSERVATION_TIME_ONLY": "仅在观测时刻对齐",
    "STALE_AT_OBSERVATION_TIME": "观测时已可能过时",
    "PINNED_COMMIT_IMMUTABLE": "固定 Commit，结论不变",
    "SYNTHETIC_ONLY": "仅合成数据",
    "CURRENT_APPLICABILITY_UNKNOWN": "当前适用性未知",
}

REVIEW_LABEL = {
    "pending_review": "待人工审核",
    "approved": "已人工批准",
    "rejected": "已人工驳回",
}

PROVENANCE_LABEL = {
    "REAL_LIVE_API": "实时 API 观测",
    "HISTORICAL_REAL_DATA": "历史真实数据",
    "SYNTHETIC_FIXTURE": "合成夹具",
}

AUTH_LABEL = {
    "TEST_ONLY_ISOLATED": "隔离测试授权（TEST_ONLY）",
    "VERIFIABLE_PRODUCTION": "可核验的真实授权",
    "DEVELOPMENT_BATCH_ONLY": "仅开发批次授权",
    None: "未知授权类别",
}


def _canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def card_id_of(view: dict, *, renderer_version: str = RENDERER_VERSION) -> str:
    """卡片身份：只由视图内容决定，不含时间戳。"""
    core = {
        "view_id": view.get("view_id"),
        "verification_status": view.get("verification_status"),
        "claim_commit_sha": view.get("claim_commit_sha"),
        "review_status": view.get("review_status"),
        "freshness_state": view.get("freshness_state"),
        "current_applicability": view.get("current_applicability"),
        "provenance_level": view.get("provenance_level"),
        "authorization_class": view.get("authorization_class"),
        "card_schema_version": CARD_SCHEMA_VERSION,
        "renderer_version": renderer_version,
    }
    return "SL-CARD-" + hashlib.sha256(
        _canonical(core).encode()).hexdigest()[:32]


def build_card(view: dict, *, renderer_version: str = RENDERER_VERSION) -> dict:
    """把视图投影成卡片。**只读投影，不改任何裁决。**"""
    if not isinstance(view, dict):
        raise ValueError("view 必须是 dict")

    verdict = view.get("verification_status")
    freshness = view.get("freshness_state")
    applic = view.get("current_applicability")
    review = view.get("review_status")
    prov = view.get("provenance_level")
    auth = view.get("authorization_class")

    claim = view.get("claim_payload") or {}
    path = claim.get("normalized_path")
    exists = claim.get("expected_exists")
    claim_type = view.get("claim_type") or claim.get("claim_type")

    title = _claim_title(claim_type=claim_type, path=path, exists=exists)

    return {
        "card_id": card_id_of(view, renderer_version=renderer_version),
        "card_schema_version": CARD_SCHEMA_VERSION,
        "renderer_version": renderer_version,
        "view_id": view.get("view_id"),
        "query_scope": view.get("query_scope"),

        # A. 标题与范围
        "title": title,
        "repository_id": view.get("repository_id"),
        "commit_sha": view.get("claim_commit_sha"),
        "claim_id": view.get("claim_id"),
        "claim_type": claim_type,
        "claim_scope": {
            "normalized_path": path,
            "expected_exists": exists,
            "claim_scope": claim.get("claim_scope"),
            "claim_schema_version": claim.get("claim_schema_version"),
        },

        # B. 证据裁决（原样）
        "verification": {
            "status": verdict,
            "label": VERDICT_LABEL.get(verdict, "未知裁决"),
            "meaning": VERDICT_MEANING.get(verdict, "无法解释的裁决值。"),
            "verification_id": view.get("verification_id"),
            "rule_version": view.get("verification_rule_version"),
            "evidence_level": view.get("verification_evidence_level"),
        },

        # C. 新鲜度（原样）
        "freshness": {
            "state": freshness,
            "label": FRESHNESS_LABEL.get(freshness, "新鲜度未知"),
            "meaning": FRESHNESS_MEANING.get(freshness,
                            "没有足够证据判断当前适用性。"),
            "applicability_scope": view.get("applicability_scope"),
            "current_applicability": applic,
            "current_applicability_label":
                APPLICABILITY_LABEL.get(applic, "当前适用性未知"),
            "watch_id": view.get("watch_id"),
            "requested_ref": view.get("requested_ref"),
            "observed_commit_sha": view.get("observed_commit_sha"),
            "baseline_commit_sha": view.get("baseline_commit_sha"),
            "last_observed_at": view.get("last_observed_at"),
            "reason_code": view.get("freshness_reason_code"),
            "source_evidence_conflict": view.get("source_evidence_conflict"),
        },

        # D. 人工审核（原样，不因 EC supported 而改变）
        "review": {
            "status": review,
            "label": REVIEW_LABEL.get(review, "审核状态未知"),
            "human_authored": view.get("human_authored"),
        },

        # E. 来源与授权（分别呈现）
        "provenance": {
            "level": prov,
            "label": PROVENANCE_LABEL.get(prov, "来源未知"),
            "basis": list(view.get("provenance_basis") or []),
            "evidence_source_level": view.get("evidence_source_level"),
            "execution_source_level": view.get("execution_source_level"),
            "snapshot_source_level": view.get("snapshot_source_level"),
            "snapshot_source_provider": view.get("snapshot_source_provider"),
            "mixed_provenance": bool(view.get("mixed_provenance")),
        },
        "authorization": {
            "class": auth,
            "label": AUTH_LABEL.get(auth, "未知授权类别"),
            "kind": view.get("authorization_kind"),
            "test_only": bool(view.get("authorization_is_test_only")),
        },

        # F. 证据与历史
        "evidence": {
            "refs": _sorted_unique(view.get("evidence_refs") or []),
            "fact_refs": _sorted_unique(view.get("fact_refs") or []),
            "snapshot_refs": _sorted_unique(
                view.get("source_snapshot_refs") or []),
            "local_coverage_only": bool(view.get("local_coverage_only")),
            "coverage_scope": view.get("coverage_scope"),
            "no_usable_evidence": bool(view.get("no_usable_evidence")),
        },
        "history": {
            "refs": _normalize_history(view.get("history_refs") or {}),
        },
        "execution": {
            "run_ref": view.get("execution_run_ref"),
            "status": view.get("execution_status"),
            "stages": view.get("execution_stages"),
        },

        # G. 限制（一条都不许隐藏）
        "limitations": list(view.get("limitations") or []),
        "conflict_indicators": dict(view.get("conflict_indicators") or {}),
        "distribution": dict(view.get("distribution_restrictions") or {}),
    }


def _sorted_unique(items) -> list:
    out = []
    for x in items:
        s = x if isinstance(x, str) else _canonical(x)
        if s not in out:
            out.append(s)
    return sorted(out)


def _normalize_history(h: dict) -> dict:
    keys = ("source_claim_id", "source_verification_id", "candidate_id",
            "revalidation_of", "relation")
    return {k: h.get(k) for k in keys if h.get(k) is not None}


def _claim_title(*, claim_type, path, exists) -> str:
    """★ 命题描述只陈述"待验证的说法"，不暗示结论。"""
    if claim_type == "repository_path_exists" and path:
        if exists is True:
            return f"仓库路径「{path}」存在"
        if exists is False:
            return f"仓库路径「{path}」不存在"
        return f"仓库路径「{path}」的存否"
    if claim_type:
        return str(claim_type)
    return "未命名命题"


def check_wording(card: dict) -> list:
    """★ 校验渲染措辞没有放大裁决。返回违规短语列表。"""
    blob = json.dumps(card, ensure_ascii=False)
    return [p for p in FORBIDDEN_PHRASES if p in blob]
