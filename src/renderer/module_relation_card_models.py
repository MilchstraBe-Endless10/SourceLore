#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态模块关系卡片模型。"""

import hashlib, json

CARD_SCHEMA = "module-relation-card/1"
MODULE_RELATION_CARD = "SOURCE_MODULE_RELATION_CARD"
MODULE_RELATION_ERROR_CARD = "SOURCE_MODULE_RELATION_ERROR"

DISCLAIMERS = [
    "静态模块映射不等于运行时模块加载成功。",
    "tsconfig.paths 不自动改写输出代码的导入路径。",
    "未验证构建是否成功，也未验证该模块在运行时可用。",
    "未验证相关函数是否被调用。",
]


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def build_relation_card(q, relation=None):
    if not isinstance(q, dict):
        raise ValueError("查询结果必须是 dict")
    rels = q.get("relations") or []
    if not rels:
        return _error(q, reason=q.get("state") or "NO_RELATIONS",
                      detail=q.get("note") or "无静态模块关系事实")

    rel = relation or rels[0]
    state = rel.get("resolution_state")
    if state != "LOCAL_MODULE_RESOLVED":
        return _error(q, reason=state,
                      detail=rel.get("unresolved_reason") or "解析未完成",
                      relation=rel)

    # ★ 三组证据齐备检查
    problems = []
    if not rel.get("import_fact_id"):
        problems.append("缺 Import Fact")
    if not rel.get("config_observation_ids"):
        problems.append("缺配置观察身份")
    if not rel.get("config_blob_oids"):
        problems.append("缺配置 Blob")
    if not rel.get("resolved_target_path"):
        problems.append("缺目标路径")
    if not rel.get("evidence_refs"):
        problems.append("证据引用为空")
    if problems:
        return _error(q, reason="EVIDENCE_CHAIN_INCOMPLETE",
                      detail="；".join(problems), relation=rel)

    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": MODULE_RELATION_CARD,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "import": {
            "file_path": rel.get("importing_file_path"),
            "blob_oid": rel.get("importing_blob_oid"),
            "content_asset_id": rel.get("importing_content_asset_id"),
            "module_specifier": rel.get("module_specifier"),
            "import_kind": rel.get("import_kind"),
            "is_type_only": rel.get("is_type_only"),
            "import_fact_id": rel.get("import_fact_id"),
        },
        "config": {
            "observation_ids": rel.get("config_observation_ids"),
            "blob_oids": rel.get("config_blob_oids"),
            "matched_field": rel.get("matched_config_field"),
            "matched_rule": rel.get("matched_config_rule"),
            "config_path": rel.get("matched_config_path"),
            "resolution_policy": rel.get("resolution_policy"),
        },
        "target": {
            "candidate_paths": rel.get("candidate_paths"),
            "resolved_target_path": rel.get("resolved_target_path"),
            "unique": len(rel.get("candidate_paths") or []) == 1,
            "resolution_state": state,
        },
        "condition_candidates": rel.get("condition_candidates") or [],
        "evidence_refs": rel.get("evidence_refs") or [],
        "limitations": DISCLAIMERS + (rel.get("limitations") or []),
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = _cid(model)
    return model


def _cid(model):
    return "SL-MCARD-" + hashlib.sha256(
        (CARD_SCHEMA + "|" + _canon(model)).encode("utf-8")).hexdigest()[:40]


def _error(q, *, reason, detail, relation=None):
    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": MODULE_RELATION_ERROR_CARD,
        "reason": reason, "detail": detail,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "importing_file_path": q.get("importing_file_path"),
        "module_specifier": q.get("module_specifier"),
        "resolution_state": (relation or {}).get("resolution_state"),
        "limitations": DISCLAIMERS,
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = _cid(model)
    return model
