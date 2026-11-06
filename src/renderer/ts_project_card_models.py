#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TS 项目 / 引用 / 归属 卡片模型。"""

import hashlib, json

CARD_SCHEMA = "ts-project-card/1"
TS_PROJECT_CARD = "TYPESCRIPT_PROJECT_CARD"
PROJECT_REFERENCE_CARD = "PROJECT_REFERENCE_CARD"
PROJECT_FILE_MEMBERSHIP_CARD = "PROJECT_FILE_MEMBERSHIP_CARD"
TS_PROJECT_ERROR_CARD = "TYPESCRIPT_PROJECT_ERROR"

DISCLAIMERS = [
    "Project Reference 是静态配置关系，不代表项目已成功构建。",
    "配置存在 ≠ 类型检查通过 ≠ 构建产物存在。",
    "exclude 只影响 include 扫描，不等于文件永不进入 TypeScript Program。",
    "files/include 匹配 ≠ 编译成功。",
]


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _cid(model):
    return "SL-TSCARD-" + hashlib.sha256(
        (CARD_SCHEMA + "|" + _canon(model)).encode("utf-8")).hexdigest()[:40]


def build_project_card(q, project=None):
    projects = q.get("projects") or []
    if not projects:
        return _error(q, reason=q.get("state") or "NO_PROJECTS",
                      detail=q.get("note") or "无 TypeScript 项目")
    p = project or projects[0]
    if p.get("discovery_status") != "PROJECT_CONFIG_VERIFIED":
        return _error(q, reason=p.get("discovery_status"),
                      detail="配置未验证，无法生成项目卡片", project=p)

    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": TS_PROJECT_CARD,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "project_id": p.get("project_id"),
        "config_path": p.get("config_path"),
        "config_blob_oid": p.get("config_blob_oid"),
        "discovery_status": p.get("discovery_status"),
        "config_completeness": p.get("config_completeness"),
        "is_solution_style": p.get("is_solution_style"),
        "declared_files": p.get("declared_files") or [],
        "declared_include": p.get("declared_include") or [],
        "declared_exclude": p.get("declared_exclude") or [],
        "declared_composite": p.get("declared_composite"),
        "declared_root_dir": p.get("declared_root_dir"),
        "declared_out_dir": p.get("declared_out_dir"),
        "evidence_refs": p.get("evidence_refs") or [],
        "provenance_level": p.get("provenance_level"),
        "limitations": DISCLAIMERS + (p.get("limitations") or []),
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = _cid(model)
    return model


def build_reference_card(q, reference=None):
    refs = q.get("references") or []
    if not refs:
        return _error(q, reason="NO_REFERENCES", detail="无项目引用事实")
    r = reference or refs[0]
    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": PROJECT_REFERENCE_CARD,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "from_project_id": r.get("from_project_id"),
        "from_config_path": r.get("from_config_path"),
        "declared_path": r.get("declared_path"),
        "to_config_path": r.get("to_config_path"),
        "to_project_id": r.get("to_project_id"),
        "status": r.get("status"),
        "evidence_refs": r.get("evidence_refs") or [],
        "limitations": DISCLAIMERS + (r.get("limitations") or []),
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = _cid(model)
    return model


def build_membership_card(q, membership=None, file_path=None):
    ms = q.get("memberships") or []
    if file_path:
        ms = [m for m in ms if m["source_file_path"] == file_path]
    if not ms:
        return _error(q, reason="MEMBERSHIP_NOT_PROVEN",
                      detail="该文件没有可确认的项目归属")
    # ★ 多候选必须全列，不能只取一个
    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": PROJECT_FILE_MEMBERSHIP_CARD,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "file_path": ms[0]["source_file_path"],
        "ambiguous": len(ms) > 1,
        "candidates": [{
            "project_id": m.get("project_id"),
            "config_path": m.get("config_path"),
            "state": m.get("state"),
            "matched_rule": m.get("matched_rule"),
            "matched_field": m.get("matched_field"),
            "excluded_by": m.get("excluded_by"),
            "selection_mode": m.get("selection_mode"),
            "fact_id": m.get("fact_id"),
        } for m in ms],
        "evidence_refs": sorted({e for m in ms
                                 for e in (m.get("evidence_refs") or [])}),
        "limitations": DISCLAIMERS,
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = _cid(model)
    return model


def _error(q, *, reason, detail, project=None):
    model = {
        "card_schema_version": CARD_SCHEMA,
        "card_type": TS_PROJECT_ERROR_CARD,
        "reason": reason, "detail": detail,
        "repository_id": q.get("repository_id"),
        "commit_sha": q.get("commit_sha"),
        "config_path": (project or {}).get("config_path"),
        "limitations": DISCLAIMERS,
        "distribution_restrictions": {"distribution_allowed": False,
                                      "copy_permitted": False},
        "network_requests": 0,
    }
    model["card_id"] = _cid(model)
    return model
