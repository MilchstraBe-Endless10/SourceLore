#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TS 项目知识只读查询。★ 零网络、不写库。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "source_analysis", "content_persistence",
           "skill_interface"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

STATE_PROJECTS_FOUND = "PROJECTS_FOUND"
STATE_NO_PROJECTS = "NO_PROJECTS"
STATE_NOT_REGISTERED = "REPOSITORY_NOT_REGISTERED"


def query_projects(*, repository_id, commit_sha=None, config_path=None,
                   file_path=None, limit=200, data_root=None,
                   include_memberships=True, show_references=False):
    from knowledge_store import KnowledgeStore
    from paths import db_path, DEFAULT_DATA_ROOT

    root = data_root or DEFAULT_DATA_ROOT
    p = db_path(root)
    if not p.exists():
        return _shell(repository_id, commit_sha, STATE_NOT_REGISTERED,
                      "知识库未建立")

    store = KnowledgeStore(str(p), create=False)
    try:
        rows = store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
            "AND repository_id=?", (str(repository_id),)).fetchall()
        if not rows:
            return _shell(repository_id, commit_sha, STATE_NOT_REGISTERED,
                          "该仓库从未登记")

        projects, references, memberships = [], [], []
        for r in rows:
            got = store.get_asset(r["asset_id"], verify=True)
            if not got.get("ok"):
                continue
            pl = (got["asset"] or {}).get("payload") or {}
            ftype = pl.get("fact_type")
            np = pl.get("normalized_parameters") or {}
            subj = np.get("subject") or {}
            if commit_sha and pl.get("commit_sha") != str(commit_sha):
                continue

            if ftype == "ts_project_declaration":
                if config_path and subj.get("config_path") != config_path:
                    continue
                projects.append(_project_row(pl, np, subj))
            elif ftype == "ts_project_reference":
                references.append(_reference_row(pl, np, subj))
            elif ftype == "ts_file_membership":
                if file_path and subj.get("source_file_path") != file_path:
                    continue
                memberships.append(_membership_row(pl, np, subj))

        if not projects:
            return dict(
                _shell(repository_id, commit_sha, STATE_NO_PROJECTS,
                       "无已登记的 TypeScript 项目"),
                references=references, memberships=memberships)

        out = {
            "state": STATE_PROJECTS_FOUND,
            "repository_id": str(repository_id),
            "commit_sha": commit_sha,
            "config_path": config_path,
            "file_path": file_path,
            "projects": projects[:limit],
            "references": references if show_references else [],
            "memberships": memberships[:limit] if include_memberships else [],
            "counts": {"projects": len(projects),
                       "references": len(references),
                       "memberships": len(memberships),
                       "solution_style": sum(
                           1 for x in projects if x["is_solution_style"])},
            "network_requests": 0,
            "limitations": [
                "项目配置关系不代表构建成功",
                "exclude 只影响 include 扫描",
                "files/include 匹配 ≠ 类型检查通过",
                "不支持 tsc --build 与产物映射",
            ],
            "distribution_restrictions": {"distribution_allowed": False,
                                          "copy_permitted": False},
        }
        if show_references:
            out["reference_graph"] = _build_graph(projects, references)
        return out
    finally:
        store.close()


def _project_row(pl, np, subj):
    return {
        "fact_id": pl.get("fact_id"),
        "project_id": np.get("project_observation_id"),
        "config_path": subj.get("config_path"),
        "config_blob_oid": subj.get("config_blob_oid"),
        "discovery_status": subj.get("discovery_status"),
        "is_solution_style": subj.get("is_solution_style"),
        "declared_files": subj.get("declared_files") or [],
        "declared_include": subj.get("declared_include") or [],
        "declared_exclude": subj.get("declared_exclude") or [],
        "declared_composite": subj.get("declared_composite"),
        "declared_root_dir": subj.get("declared_root_dir"),
        "declared_out_dir": subj.get("declared_out_dir"),
        "rule_id": pl.get("rule_id"),
        "rule_version": pl.get("rule_version"),
        "commit_sha": pl.get("commit_sha"),
        "repository_id": pl.get("repository_id"),
        "config_completeness": np.get("config_completeness"),
        "provenance_level": np.get("provenance_level"),
        "evidence_refs": pl.get("evidence_refs") or [],
        "limitations": ["配置存在 ≠ 构建成功"],
    }


def _reference_row(pl, np, subj):
    return {
        "fact_id": pl.get("fact_id"),
        "reference_id": np.get("reference_id"),
        "from_project_id": subj.get("from_project_id"),
        "from_config_path": subj.get("from_config_path"),
        "declared_path": subj.get("declared_path"),
        "to_config_path": subj.get("to_config_path"),
        "to_project_id": subj.get("to_project_id"),
        "status": subj.get("status"),
        "rule_id": pl.get("rule_id"),
        "commit_sha": pl.get("commit_sha"),
        "repository_id": pl.get("repository_id"),
        "evidence_refs": pl.get("evidence_refs") or [],
        "limitations": ["引用 ≠ 目标已构建"],
    }


def _membership_row(pl, np, subj):
    return {
        "fact_id": pl.get("fact_id"),
        "membership_id": np.get("membership_id"),
        "project_id": subj.get("project_id"),
        "config_path": subj.get("config_path"),
        "source_file_path": subj.get("source_file_path"),
        "state": subj.get("state"),
        "matched_rule": subj.get("matched_rule"),
        "matched_field": subj.get("matched_field"),
        "excluded_by": subj.get("excluded_by"),
        "selection_mode": np.get("selection_mode"),
        "rule_id": pl.get("rule_id"),
        "commit_sha": pl.get("commit_sha"),
        "repository_id": pl.get("repository_id"),
        "evidence_refs": pl.get("evidence_refs") or [],
        "limitations": ["输入选择 ≠ 类型检查通过"],
    }


def _build_graph(projects, references):
    nodes = [{"project_id": p["project_id"], "config_path": p["config_path"]}
             for p in projects]
    edges = [{"from": r["from_project_id"], "to": r.get("to_project_id"),
              "to_config_path": r.get("to_config_path"),
              "status": r["status"]} for r in references]
    return {"nodes": nodes, "edges": edges}


def _shell(repository_id, commit_sha, state, note):
    return {"state": state, "note": note,
            "repository_id": str(repository_id), "commit_sha": commit_sha,
            "projects": [], "references": [], "memberships": [],
            "counts": {"projects": 0, "references": 0,
                       "memberships": 0, "solution_style": 0},
            "network_requests": 0, "limitations": [note]}


def resolve_file_membership(*, repository_id, file_path, commit_sha=None,
                            data_root=None):
    """查询某文件的全部项目归属候选（★ 多候选必须全列）。"""
    q = query_projects(repository_id=repository_id, commit_sha=commit_sha,
                       file_path=file_path, data_root=data_root)
    ms = [m for m in q.get("memberships") or []
          if m["source_file_path"] == file_path]
    if not ms:
        return {"state": "MEMBERSHIP_NOT_PROVEN", "file_path": file_path,
                "candidates": [], "network_requests": 0}
    distinct = {(m["project_id"], m["state"]) for m in ms}
    state = ("INPUT_MATCHED_MULTIPLE_PROJECTS" if len(distinct) > 1
             else ms[0]["state"])
    return {"state": state, "file_path": file_path, "candidates": ms,
            "counts": {"candidates": len(ms)},
            "network_requests": 0,
            "limitations": ["输入选择 ≠ 类型检查通过"]}
