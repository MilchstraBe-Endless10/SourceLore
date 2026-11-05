#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码结构卡片模型。★ 只读投影，不改权威数据。"""

import hashlib, json

CARD_SCHEMA = "source-card/1"

SOURCE_FILE_CARD = "SOURCE_FILE_CARD"
SOURCE_SYMBOL_CARD = "SOURCE_SYMBOL_CARD"
SOURCE_IMPORT_CARD = "SOURCE_IMPORT_CARD"
SOURCE_MODULE_RELATION_CARD = "SOURCE_MODULE_RELATION_CARD"
SOURCE_ERROR_CARD = "SOURCE_EVIDENCE_ERROR"

DISCLAIMERS = {
    SOURCE_FILE_CARD: [
        "静态声明 ≠ 运行时行为",
        "不执行仓库代码，不推断函数调用关系",
        "只覆盖已抽取的源码文件",
    ],
    SOURCE_SYMBOL_CARD: [
        "存在声明 ≠ 函数被执行 ≠ 能完成某项任务",
        "不推断该类被其他模块使用",
    ],
    SOURCE_IMPORT_CARD: [
        "静态导入 ≠ 依赖已安装 ≠ 导入一定成功",
        "条件导入不等于无条件运行时依赖",
    ],
    SOURCE_MODULE_RELATION_CARD: [
        "路径匹配 ≠ 运行时导入成功",
        "不构成依赖图；不做调用图/数据流图",
    ],
    SOURCE_ERROR_CARD: ["证据链不完整；此卡不构成源码知识结论"],
}


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def card_id_of(model):
    return "SL-SCARD-" + hashlib.sha256(
        (CARD_SCHEMA + "|" + _canon(model)).encode("utf-8")).hexdigest()[:40]


def build_source_card(q, *, card_type=None):
    if not isinstance(q, dict):
        raise ValueError("query result 必须是 dict")

    facts = q.get("facts") or []
    caps = q.get("captured") or []

    if not facts:
        return _error(q, reason=q.get("state") or "NO_FACTS",
                      detail="没有可展示的源码结构事实")

    problems = _check_chain(q, facts, caps)
    if problems:
        return _error(q, reason="EVIDENCE_CHAIN_INCOMPLETE",
                      detail="；".join(problems))

    if card_type is None:
        card_type = SOURCE_FILE_CARD

    symbols = [f for f in facts if f["rule_id"] == "SOURCE_SYMBOL_DECLARED"]
    imports = [f for f in facts if f["rule_id"] == "SOURCE_IMPORT_DECLARED"]

    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": card_type,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "file_path": q.get("file_path"),
        "language": (facts[0].get("language") if facts else None),
        "content_availability": q.get("content_availability"),
        "provenance_level": q.get("provenance_level"),
        "captured": [{
            "file_path": c.get("file_path"),
            "commit_sha": c.get("commit_sha"),
            "content_asset_id": c.get("content_asset_id"),
            "git_blob_oid": c.get("git_blob_oid"),
            "byte_length": c.get("raw_byte_length"),
            "verify_status": c.get("verify_status"),
        } for c in caps],
        "symbols": [_row(f, "symbol") for f in symbols],
        "imports": [_row(f, "import") for f in imports],
        "counts": {"symbols": len(symbols), "imports": len(imports),
                   "facts": len(facts)},
        "limitations": (q.get("limitations") or [])
            + DISCLAIMERS.get(card_type, []),
        "distribution_restrictions": q.get("distribution_restrictions")
            or {"distribution_allowed": False, "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = card_id_of(model)
    return model


def _row(f, kind):
    subj = f.get("subject") or {}
    return {
        "fact_id": f.get("fact_id"),
        "rule_id": f.get("rule_id"),
        "rule_version": f.get("rule_version"),
        "subject": subj,
        "git_blob_oid": f.get("git_blob_oid"),
        "content_asset_id": f.get("content_asset_id"),
        "content_sha256": f.get("content_sha256"),
        "parser_version": f.get("parser_version"),
        "start_byte": f.get("start_byte"), "end_byte": f.get("end_byte"),
        "start_line": f.get("start_line"), "end_line": f.get("end_line"),
        "observation_id": f.get("observation_id"),
        "evidence_label": f.get("evidence_label"),
        "kind": kind,
    }


def _check_chain(q, facts, caps):
    problems = []
    if not caps:
        problems.append("无内容资产")
        return problems
    for c in caps:
        if c.get("verify_status") != "CONTENT_AVAILABLE_VERIFIED":
            problems.append(f"字节未验证：{c.get('file_path')}")
    commit = q.get("commit_sha")
    for f in facts:
        if f.get("commit_sha") != commit:
            problems.append("Fact 的 Commit 与查询不一致")
            break
    for f in facts:
        if not f.get("git_blob_oid"):
            problems.append("Fact 缺 Blob 身份")
            break
        if f.get("start_byte") is None:
            problems.append("Fact 缺字节范围")
            break
    return problems


def _error(q, *, reason, detail):
    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": SOURCE_ERROR_CARD,
        "reason": reason, "detail": detail,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "file_path": q.get("file_path"),
        "state": q.get("state"),
        "content_availability": q.get("content_availability"),
        "limitations": DISCLAIMERS[SOURCE_ERROR_CARD],
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = card_id_of(model)
    return model
