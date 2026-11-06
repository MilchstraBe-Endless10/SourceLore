#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TypeScript 项目发现与上下文解析。

★ 串联：配置解析 → references → 文件选择 → 项目归属。
★ 不执行编译器，不生成产物。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import ts_file_membership as FM
import ts_project_models as PM
import ts_project_references as REF
import tsconfig_effective_config as EC
import tsconfig_parser as TP

CONFIG_NAMES = ("tsconfig.json", "jsconfig.json")
MAX_PROJECTS = 64


def config_dir_of(config_path):
    parent = str(Path(config_path).parent)
    return "" if parent == "." else parent.replace("\\", "/")


def discover_config_paths(*, tree_paths, named_configs=None):
    """从 Tree 中找出所有可能为 TS 项目配置的路径。

    ★ 只认 Tree 里真实存在的路径，不扫描本机文件系统。
    """
    tree = {p.lstrip("./") for p in tree_paths}
    found = set()
    for p in tree:
        name = p.rsplit("/", 1)[-1]
        if name in CONFIG_NAMES:
            found.add(p)
    for p in (named_configs or []):
        if p in tree:
            found.add(p)
    return sorted(found)


def parse_project_config(*, raw, config_path, repository_id, commit_sha,
                         config_blob_oid, config_content_asset_id,
                         config_content_digest, read_config=None,
                         provenance_level="SYNTHETIC_FIXTURE"):
    """解析单个项目配置，产出 ProjectObservation。

    返回 (observation, inc_specs, exc_specs, explicit_files, default_rule)。
    """
    cdir = config_dir_of(config_path)

    pr = TP.parse_tsconfig(raw, config_path=config_path)
    if not pr["ok"]:
        return PM.build_project_observation(
            repository_id=repository_id, commit_sha=commit_sha,
            config_path=config_path, config_blob_oid=config_blob_oid,
            config_content_asset_id=config_content_asset_id,
            config_content_digest=config_content_digest,
            discovery_status=PM.PROJECT_CONFIG_INVALID,
            project_root=cdir, provenance_level=provenance_level,
            failure_reason=f"{pr['error_code']}: {pr['error_detail']}",
        ), [], [], [], {}

    data = pr["data"]
    surf = TP.extract_config_surface(data, config_dir=cdir)

    # ── extends 链 ──
    chain_status = None
    chain = []
    if surf.get("extends"):
        if read_config is None:
            chain_status = PM.PROJECT_CONFIG_INHERITANCE_UNRESOLVED
        else:
            res = EC.resolve_extends_chain(config_path=config_path,
                                           read_config=read_config)
            if not res["ok"]:
                chain_status = PM.PROJECT_CONFIG_INHERITANCE_UNRESOLVED
            else:
                chain = [{"config_path": c["config_path"],
                          "surface": {k: c["surface"].get(k)
                                      for k in ("files", "include", "exclude",
                                                "base_url", "paths",
                                                "module_resolution")},
                          "surface_keys": sorted(c["surface"])}
                         for c in res["chain"]]

    comp = (data.get("compilerOptions")
            if isinstance(data.get("compilerOptions"), dict) else {})

    status = (chain_status if chain_status
              else PM.PROJECT_CONFIG_VERIFIED)

    # ★ TypeScript 语义：
    #   files / include / exclude **随 extends 继承**（子配置有则覆盖）；
    #   references **不**继承（只读本配置顶层）。
    files_declared = "files" in data
    include_declared = "include" in data
    exclude_declared = "exclude" in data

    files = data.get("files") if files_declared else []
    include = data.get("include") if include_declared else []
    exclude = data.get("exclude") if exclude_declared else []

    # 从继承链里找父配置的 files/include/exclude（自最父级向子级叠加）
    inherited_fields = {}
    if chain:
        for entry in reversed(chain[1:]):       # 跳过自身
            surf_i = entry.get("surface") or {}
            for fld in ("files", "include", "exclude"):
                if fld in surf_i:
                    inherited_fields[fld] = surf_i[fld]

    if not files_declared and "files" in inherited_fields:
        files_declared = True
        files = inherited_fields["files"]
    if not include_declared and "include" in inherited_fields:
        include_declared = True
        include = inherited_fields["include"]
    if not exclude_declared and "exclude" in inherited_fields:
        exclude_declared = True
        exclude = inherited_fields["exclude"]

    is_solution = (files_declared and files == []
                   and (surf.get("references") or []))

    obs = PM.build_project_observation(
        repository_id=repository_id, commit_sha=commit_sha,
        config_path=config_path, config_blob_oid=config_blob_oid,
        config_content_asset_id=config_content_asset_id,
        config_content_digest=config_content_digest,
        discovery_status=status, project_root=cdir,
        declared_files=list(files) if isinstance(files, list) else [],
        declared_include=(list(include)
                          if isinstance(include, list) else []),
        declared_exclude=(list(exclude)
                          if isinstance(exclude, list) else []),
        # ★ references 只读**本配置自己的**顶层字段，不继承
        declared_references=surf.get("references") or [],
        declared_composite=comp.get("composite"),
        declared_root_dir=comp.get("rootDir"),
        declared_out_dir=comp.get("outDir"),
        declared_declaration=comp.get("declaration"),
        declared_allow_js=comp.get("allowJs"),
        declared_jsx=comp.get("jsx"),
        config_completeness=("COMPLETE" if chain_status is None
                             else "PARTIAL"),
        inheritance_chain=chain,
        is_solution_style=is_solution,
        evidence_refs=[f"config:{config_path}"],
        provenance_level=provenance_level,
        failure_reason=None)

    inc, exc, probs = FM.prepare_rules(
        include=obs["declared_include"], exclude=obs["declared_exclude"],
        config_dir=cdir)
    expl, rej = FM.declared_files(files=obs["declared_files"],
                                 config_dir=cdir)
    default_rule = FM.default_inclusion_active(
        files_declared=files_declared, include_declared=include_declared,
        exclude_declared=exclude_declared,
        allow_js=bool(comp.get("allowJs")))

    obs["selection_problems"] = probs
    obs["selection_unsupported"] = bool(probs)
    return obs, inc, exc, expl, default_rule


def build_all_projects(*, tree_paths, config_blobs, repository_id,
                       commit_sha, provenance_level="SYNTHETIC_FIXTURE"):
    """批量构建项目观察 + 引用关系。

    config_blobs: {config_path: {"raw": bytes, "blob_oid": str,
                                 "content_asset_id": str, "content_digest": str}}
    """
    # ★ 只把**标准命名**的配置当作项目候选。
    #   被 extends 引用的 base.json 之类是基础配置，不是独立项目。
    paths = discover_config_paths(tree_paths=tree_paths)
    projects = []
    details = {}

    def read_config(p):
        b = config_blobs.get(p)
        if not b:
            return None
        pr = TP.parse_tsconfig(b["raw"], config_path=p)
        if not pr["ok"]:
            return {"ok": False, "error_code": pr["error_code"]}
        return {"ok": True, "data": pr["data"]}

    for p in paths[:MAX_PROJECTS]:
        b = config_blobs.get(p)
        if not b:
            projects.append(PM.build_project_observation(
                repository_id=repository_id, commit_sha=commit_sha,
                config_path=p, config_blob_oid=None,
                config_content_asset_id=None, config_content_digest=None,
                discovery_status=PM.PROJECT_CONFIG_NOT_CAPTURED,
                project_root=config_dir_of(p),
                provenance_level=provenance_level,
                failure_reason="CONFIG_CONTENT_NOT_CAPTURED"))
            continue
        obs, inc, exc, expl, default_rule = parse_project_config(
            raw=b["raw"], config_path=p, repository_id=repository_id,
            commit_sha=commit_sha, config_blob_oid=b["blob_oid"],
            config_content_asset_id=b["content_asset_id"],
            config_content_digest=b["content_digest"],
            read_config=read_config, provenance_level=provenance_level)
        projects.append(obs)
        details[p] = {"include": inc, "exclude": exc,
                      "explicit_files": expl, "default_rule": default_rule}

    by_path = {p["config_path"]: p for p in projects}
    references = []
    for p in projects:
        if p["discovery_status"] == PM.PROJECT_CONFIG_INVALID:
            continue
        references.extend(REF.build_references_for_project(
            project=p, tree_paths=tree_paths,
            config_lookup=lambda cp: by_path.get(cp),
            captured_configs=set(config_blobs)))

    graph = REF.build_project_graph(projects=projects,
                                    references=references)
    return {"projects": projects, "references": references,
            "graph": graph, "details": details}


def resolve_membership(*, file_path, projects, details, tree_paths):
    """单个文件的项目归属判定。

    ★ 不能只用“最近的 tsconfig”，必须收集全部候选项目。
    """
    hits = []
    for p in projects:
        if p["discovery_status"] != PM.PROJECT_CONFIG_VERIFIED:
            continue
        d = details.get(p["config_path"])
        if not d:
            continue
        r = FM.evaluate_file(
            file_path=file_path, tree_paths=tree_paths, project=p,
            inc_specs=d["include"], exc_specs=d["exclude"],
            explicit_files=d["explicit_files"],
            default_rule=d["default_rule"])
        if r["state"] in (PM.INPUT_EXPLICITLY_LISTED,
                          PM.INPUT_MATCHED_INCLUDE,
                          PM.INPUT_EXCLUDED_FROM_INCLUDE):
            hits.append({"project": p, "evaluation": r})

    if not hits:
        return {"state": PM.INPUT_NOT_PROVEN, "candidates": [],
                "reason": "NO_PROJECT_SELECTED_THIS_FILE"}

    if len(hits) > 1:
        return {"state": PM.INPUT_MATCHED_MULTIPLE_PROJECTS,
                "candidates": [
                    {"project_id": h["project"]["project_observation_id"],
                     "config_path": h["project"]["config_path"],
                     "state": h["evaluation"]["state"],
                     "matched_rule": h["evaluation"].get("matched_rule"),
                     "matched_field": h["evaluation"].get("matched_field"),
                     "excluded_by": h["evaluation"].get("excluded_by")}
                    for h in hits],
                "reason": "MULTIPLE_PROJECTS_MATCH"}

    h = hits[0]
    return {"state": h["evaluation"]["state"],
            "candidates": [{
                "project_id": h["project"]["project_observation_id"],
                "config_path": h["project"]["config_path"],
                "state": h["evaluation"]["state"],
                "matched_rule": h["evaluation"].get("matched_rule"),
                "matched_field": h["evaluation"].get("matched_field"),
                "excluded_by": h["evaluation"].get("excluded_by")}],
            "reason": None}


def select_project_context(*, file_path, projects, details, tree_paths):
    """为模块解析选择项目上下文。

    ★ 唯一可验证 → PROJECT_CONTEXT_SELECTED
    ★ 多候选或归属不明 → PROJECT_CONTEXT_AMBIGUOUS / NONE
    """
    m = resolve_membership(file_path=file_path, projects=projects,
                           details=details, tree_paths=tree_paths)
    if m["state"] == PM.INPUT_MATCHED_MULTIPLE_PROJECTS:
        return {"state": PM.PROJECT_CONTEXT_AMBIGUOUS,
                "candidates": m["candidates"], "project": None}
    if m["state"] == PM.INPUT_NOT_PROVEN or not m["candidates"]:
        # 允许退回：若只有一个项目且其 root 覆盖该文件
        roots = [p for p in projects
                 if p["discovery_status"] == PM.PROJECT_CONFIG_VERIFIED]
        if len(roots) == 1:
            return {"state": PM.PROJECT_CONTEXT_SELECTED,
                    "candidates": m["candidates"],
                    "project": roots[0],
                    "reason": "SINGLE_PROJECT_FALLBACK"}
        if len(roots) > 1:
            return {"state": PM.PROJECT_CONTEXT_AMBIGUOUS,
                    "candidates": [], "project": None,
                    "reason": "MULTIPLE_PROJECTS_NO_FILE_SELECTION"}
        return {"state": PM.PROJECT_CONTEXT_NONE,
                "candidates": [], "project": None}
    return {"state": PM.PROJECT_CONTEXT_SELECTED,
            "candidates": m["candidates"],
            "project": next(p for p in projects
                            if p["project_observation_id"]
                            == m["candidates"][0]["project_id"]),
            "reason": None}


def build_memberships(*, project, details, tree_paths, target_files=None):
    """为项目产出 membership 记录。"""
    d = details.get(project["config_path"])
    if not d:
        return []
    evals = FM.evaluate_project_files(
        project=project, tree_paths=tree_paths,
        inc_specs=d["include"], exc_specs=d["exclude"],
        explicit_files=d["explicit_files"], default_rule=d["default_rule"],
        target_file=(target_files[0] if target_files else None))
    # ★ 只有"被规则实际选中/排除"才成为归属事实。
    #   INPUT_POSSIBLE_VIA_IMPORT / INPUT_NOT_PROVEN 只是非归属结论，不入库。
    MEMBER_STATES = (PM.INPUT_EXPLICITLY_LISTED, PM.INPUT_MATCHED_INCLUDE,
                     PM.INPUT_EXCLUDED_FROM_INCLUDE)
    out = []
    for e in evals:
        if target_files and e["source_file_path"] != FM._norm(target_files[0]):
            continue
        if e["state"] not in MEMBER_STATES:
            continue
        out.append(PM.build_membership(
            repository_id=project["repository_id"],
            commit_sha=project["commit_sha"],
            project_id=project["project_observation_id"],
            config_path=project["config_path"],
            source_file_path=e["source_file_path"], state=e["state"],
            matched_rule=e.get("matched_rule"),
            matched_field=e.get("matched_field"),
            excluded_by=e.get("excluded_by"),
            selection_mode=e.get("selection_mode"),
            evidence_refs=[f"config:{project['config_path']}",
                           f"file:{e['source_file_path']}",
                           f"rule:{e.get('matched_rule') or 'none'}"]))
    return out
