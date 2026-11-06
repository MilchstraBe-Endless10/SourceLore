#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TypeScript project references 有界解析。

★ references 只表示静态配置关系，不代表构建成功。
★ references **不随 extends 继承**——只读当前配置自己的顶层 references。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import ts_project_models as PM
import tsconfig_parser as TP

MAX_PROJECTS = 256
MAX_REFERENCES = 512
MAX_DEPTH = 8

CONFIG_NAMES = ("tsconfig.json", "jsconfig.json")


def resolve_reference_path(*, declared_path, from_config_dir, tree_paths):
    """把 references[].path 解析成仓库相对配置路径。

    两种情况：
      1. 指向目录 → 该目录下 tsconfig.json
      2. 指向具体配置文件 → 该文件
    """
    if not isinstance(declared_path, str) or not declared_path:
        return None, PM.PROJECT_REFERENCE_TARGET_MISSING

    norm = TP.normalize_target(declared_path, base_dir=from_config_dir or "")
    if norm is None:
        return None, PM.PROJECT_REFERENCE_OUTSIDE_REPOSITORY

    paths = {p.lstrip("./") for p in tree_paths}

    # ① 显式配置文件
    if norm.endswith(".json"):
        if norm in paths:
            return norm, PM.PROJECT_REFERENCE_TARGET_VERIFIED
        return norm, PM.PROJECT_REFERENCE_TARGET_MISSING

    # ② 目录 → 目录下 tsconfig.json / jsconfig.json
    for name in CONFIG_NAMES:
        cand = f"{norm}/{name}" if norm else name
        if cand in paths:
            return cand, PM.PROJECT_REFERENCE_TARGET_VERIFIED
    return f"{norm}/tsconfig.json", PM.PROJECT_REFERENCE_TARGET_MISSING


def build_references_for_project(*, project, tree_paths, config_lookup,
                                 captured_configs=None):
    """解析单个项目的 references。

    config_lookup(path) → project observation 或 None（未采集/未解析）。
    captured_configs: 已捕获配置路径集合（用于区分 NOT_CAPTURED / MISSING）。
    """
    from_config_dir = str(Path(project["config_path"]).parent).replace(".", "") \
        if str(Path(project["config_path"]).parent) != "." else ""
    refs = []
    for entry in project.get("declared_references") or []:
        declared = entry.get("path") if isinstance(entry, dict) else entry
        target_path, status = resolve_reference_path(
            declared_path=declared, from_config_dir=from_config_dir,
            tree_paths=tree_paths)

        to_proj = config_lookup(target_path) if target_path else None
        if status == PM.PROJECT_REFERENCE_TARGET_VERIFIED:
            if to_proj is None:
                known = (captured_configs or set())
                if target_path in known:
                    status = PM.PROJECT_REFERENCE_CONFIG_UNPARSEABLE \
                        if hasattr(PM, "PROJECT_REFERENCE_CONFIG_UNPARSEABLE") \
                        else PM.PROJECT_REFERENCE_TARGET_NOT_CAPTURED
                else:
                    status = PM.PROJECT_REFERENCE_TARGET_NOT_CAPTURED

        refs.append(PM.build_reference(
            repository_id=project["repository_id"],
            commit_sha=project["commit_sha"],
            from_project_id=project["project_observation_id"],
            from_config_path=project["config_path"],
            declared_path=declared,
            to_config_path=target_path,
            to_project_id=(to_proj["project_observation_id"]
                           if to_proj else None),
            to_config_blob_oid=(to_proj["config_blob_oid"]
                                if to_proj else None),
            to_config_content_asset_id=(to_proj["config_content_asset_id"]
                                        if to_proj else None),
            status=status,
            evidence_refs=[
                f"config:{project['config_path']}",
                f"references:{declared}",
                (f"config_target:{target_path}" if target_path else ""),
            ]))
    return refs


def detect_cycles(references, *, max_depth=MAX_DEPTH):
    """在 from_project → to_project 边上检测循环。返回 (cycles, max_reached)。"""
    graph = {}
    for r in references:
        a, b = r.get("from_project_id"), r.get("to_project_id")
        if a and b:
            graph.setdefault(a, []).append(b)

    cycles, visited, stack_path = [], set(), []
    deepest = 0

    def dfs(node, depth):
        nonlocal deepest
        deepest = max(deepest, depth)
        if depth > max_depth:
            return
        if node in stack_path:
            idx = stack_path.index(node)
            cyc = stack_path[idx:] + [node]
            if cyc not in cycles:
                cycles.append(cyc)
            return
        if node in visited:
            return
        stack_path.append(node)
        for nxt in graph.get(node, []):
            dfs(nxt, depth + 1)
        stack_path.pop()
        visited.add(node)

    for node in list(graph):
        dfs(node, 1)
    return cycles, deepest


def build_project_graph(*, projects, references):
    """有界项目引用视图。★ 不建新图数据库，只是内存视图。"""
    nodes = [{
        "project_id": p["project_observation_id"],
        "config_path": p["config_path"],
        "config_blob_oid": p["config_blob_oid"],
        "commit_sha": p["commit_sha"],
        "discovery_status": p.get("discovery_status"),
    } for p in projects[:MAX_PROJECTS]]

    edges = [{
        "from_project_id": r["from_project_id"],
        "to_project_id": r.get("to_project_id"),
        "to_config_path": r.get("to_config_path"),
        "status": r["status"],
    } for r in references[:MAX_REFERENCES]]

    cycles, deepest = detect_cycles(references)
    return {
        "nodes": nodes, "edges": edges,
        "cycles": cycles, "max_depth_reached": deepest,
        "truncated": (len(projects) > MAX_PROJECTS
                      or len(references) > MAX_REFERENCES),
        "limitations": ["项目引用是静态配置关系，不代表构建成功"],
    }
