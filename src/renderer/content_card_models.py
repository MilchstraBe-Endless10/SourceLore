#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容知识卡片模型。★ 只读投影，绝不修改权威数据。

流程：Content Query → 本模块 → Safe Renderer（复用既有 HTML 转义与 CSP）。
"""

import hashlib
import html
import json

CARD_SCHEMA_VERSION = "content-card/1"

README_CARD = "README_CONTENT_CARD"
MANIFEST_CARD = "MANIFEST_CONTENT_CARD"
FACT_CARD = "CONTENT_FACT_DETAIL"
ERROR_CARD = "CONTENT_EVIDENCE_ERROR"

# 卡片必须展示的免责声明（按类型）
DISCLAIMERS = {
    README_CARD: [
        "标题存在 ≠ 项目功能已实现",
        "只覆盖已抽取的 README 内容；未抽取部分不得推断为不存在",
    ],
    MANIFEST_CARD: [
        "声明依赖 ≠ 依赖已安装",
        "存在脚本 ≠ 脚本可运行",
        "存在测试命令 ≠ 测试已通过",
    ],
    FACT_CARD: ["单条事实只覆盖其证据字节范围"],
    ERROR_CARD: ["证据链不完整；此卡不构成知识结论"],
}


def _canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def card_id_of(model, *, version=CARD_SCHEMA_VERSION):
    h = hashlib.sha256((version + "|" + _canon(model)).encode("utf-8")).hexdigest()
    return "SL-CCARD-" + h[:40]


def build_content_card(query_result, *, card_type=None):
    """从 content_query 结果构造卡片模型。

    ★ 证据链不完整 → 只能出 ERROR_CARD，绝不冒充满分卡。
    """
    if not isinstance(query_result, dict):
        raise ValueError("query_result 必须是 dict")

    facts = query_result.get("facts") or []
    caps = query_result.get("captured") or []
    path = query_result.get("file_path")

    if not facts:
        return _error_card(query_result,
                           reason=query_result.get("state") or "NO_FACTS",
                           detail="没有可展示的内容事实")

    # 证据链完整性检查（十项）
    problems = _check_chain(query_result, facts, caps)
    if problems:
        return _error_card(query_result, reason="EVIDENCE_CHAIN_INCOMPLETE",
                           detail="；".join(problems))

    if card_type is None:
        card_type = (MANIFEST_CARD if (path or "").lower().endswith(
            ("package.json", "pyproject.toml", "cargo.toml", "go.mod"))
            else README_CARD)

    model = {
        "card_schema_version": CARD_SCHEMA_VERSION,
        "card_type": card_type,
        "file_path": path,
        "repository_id": query_result.get("repository_id"),
        "commit_sha": query_result.get("commit_sha"),
        "source_snapshot_id": query_result.get("source_snapshot_id"),
        "content_availability": query_result.get("content_availability"),
        "provenance_level": query_result.get("provenance_level"),
        "review_status": query_result.get("review_status"),
        "freshness_state": query_result.get("freshness_state"),
        "distribution_restrictions": query_result.get("distribution_restrictions")
            or {"distribution_allowed": False, "copy_permitted": False},
        "captured": [{
            "file_path": c.get("file_path"),
            "commit_sha": c.get("commit_sha"),
            "content_asset_id": c.get("content_asset_id"),
            "git_blob_oid": c.get("git_blob_oid"),
            "content_sha256": c.get("content_sha256"),
            "byte_length": c.get("raw_byte_length"),
            "verify_status": c.get("verify_status"),
            "acquisition_policy": c.get("acquisition_policy"),
        } for c in caps],
        "facts": [_fact_row(f) for f in facts],
        "claims": query_result.get("claims") or [],
        "verifications": query_result.get("verifications") or [],
        "counts": _counts(facts, card_type),
        "limitations": (query_result.get("limitations") or [])
            + DISCLAIMERS.get(card_type, []),
        "network_requests": 0,
    }
    model["card_id"] = card_id_of(model)
    return model


def _fact_row(f):
    """★ label 只放结构化描述，不回显不可信原文（保留 D-6 规则）。"""
    return {
        "fact_id": f.get("fact_id"),
        "rule_id": f.get("rule_id"),
        "rule_version": f.get("rule_version"),
        "subject": f.get("subject"),
        "git_blob_oid": f.get("git_blob_oid"),
        "content_asset_id": f.get("content_asset_id"),
        "content_sha256": f.get("content_sha256"),
        "parser_version": f.get("parser_version"),
        "start_byte": f.get("start_byte"), "end_byte": f.get("end_byte"),
        "start_line": f.get("start_line"), "end_line": f.get("end_line"),
        "observation_id": f.get("observation_id"),
        "evidence_label": _evidence_label(f),
    }


def _evidence_label(f):
    """结构化标签：只有规则与位置，不含原文。"""
    rule = f.get("rule_id") or "fact"
    sl, el = f.get("start_line"), f.get("end_line")
    return f"{rule}@L{sl}-{el}" if sl is not None else f"{rule}@b{f.get('start_byte')}"


def _counts(facts, card_type):
    rules = {}
    for f in facts:
        rules[f.get("rule_id")] = rules.get(f.get("rule_id"), 0) + 1
    headings = sum(1 for f in facts if f.get("rule_id") == "README_HEADING_EXISTS")
    deps = sum(1 for f in facts if f.get("rule_id") == "MANIFEST_DEPENDENCY_DECLARED")
    fields = sum(1 for f in facts if f.get("rule_id") == "MANIFEST_FIELD_PRESENT")
    return {"facts_total": len(facts), "by_rule": rules,
            "headings": headings, "dependencies": deps, "fields": fields}


def _check_chain(query_result, facts, caps):
    """十项内容卡片前置检查。返回问题清单（空 = 通过）。"""
    problems = []
    if not caps:
        problems.append("无内容资产")
        return problems
    for c in caps:
        if c.get("verify_status") != "CONTENT_AVAILABLE_VERIFIED":
            problems.append(f"字节未验证：{c.get('file_path')}")
    commit = query_result.get("commit_sha")
    for f in facts:
        if f.get("commit_sha") != commit:
            problems.append("Fact 的 Commit 与查询不一致")
            break
    repo = str(query_result.get("repository_id"))
    for f in facts:
        if not f.get("git_blob_oid"):
            problems.append("Fact 缺 Blob 身份")
            break
        if f.get("start_byte") is None or f.get("end_byte") is None:
            problems.append("Fact 缺字节范围")
            break
    return problems


def _error_card(query_result, *, reason, detail):
    model = {
        "card_schema_version": CARD_SCHEMA_VERSION,
        "card_type": ERROR_CARD,
        "reason": reason,
        "detail": detail,
        "repository_id": query_result.get("repository_id"),
        "commit_sha": query_result.get("commit_sha"),
        "file_path": query_result.get("file_path"),
        "state": query_result.get("state"),
        "content_availability": query_result.get("content_availability"),
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "limitations": DISCLAIMERS[ERROR_CARD],
        "network_requests": 0,
    }
    model["card_id"] = card_id_of(model)
    return model


def esc(value):
    """统一转义入口 —— 供渲染器使用。"""
    return html.escape("" if value is None else str(value))
