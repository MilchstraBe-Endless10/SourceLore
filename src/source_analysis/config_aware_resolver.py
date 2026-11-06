#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置感知的 JS/TS 静态模块解析。

★ 三层状态：MODULE_REFERENCE_OBSERVED → CONFIG_MAPPING_CANDIDATE → LOCAL_MODULE_RESOLVED
★ 绝不产出 RUNTIME_* 成功态。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import module_config_models as CM
import package_module_map_parser as PM
import tsconfig_effective_config as EC
import tsconfig_parser as TP

MAX_CANDIDATES = 64
RESOLVE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts",
                ".d.ts")
INDEX_NAMES = ("index.ts", "index.tsx", "index.js", "index.jsx")


def _safe_norm(p):
    """★ 只剥前导 "./"，不碰前导 "/" 与 "../"（D-37 阻断）。"""
    s = (p or "").replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s

def resolve_with_config(*, specifier, importing_file_path, tree_paths,
                        tsconfig_observation=None, package_observation=None,
                        import_kind="named_import", is_type_only=False,
                        source_completeness="COMPLETE",
                        conditions=None, resolve_relative=True):
    """主入口。返回 resolution 字典（含 state/证据/限制）。"""
    base = {
        "module_specifier": specifier,
        "importing_file_path": importing_file_path,
        "import_kind": import_kind,
        "is_type_only": bool(is_type_only),
        "config_observation_ids": [],
        "matched_config_field": None,
        "matched_config_path": None,
        "matched_config_rule": None,
        "candidate_paths": [],
        "resolved_target_path": None,
        "condition_candidates": [],
        "unresolved_reason": None,
        "resolution_policy": "config-aware/1",
    }
    conds = set(conditions or ["import"])
    if import_kind in ("require_literal_call",):
        conds = {"require", "node"}

    # ── 0. 动态说明符 ──
    if not specifier:
        return dict(base, resolution_state=CM.DYNAMIC_SPECIFIER,
                    unresolved_reason="NON_LITERAL_SPECIFIER")

    # ── 1. # 前缀 → package imports ──
    if specifier.startswith("#"):
        return _resolve_hash(base, specifier, tree_paths, package_observation,
                             conds, source_completeness)

    # ── 2. 相对路径 ──
    if specifier.startswith("./") or specifier.startswith("../"):
        if not resolve_relative:
            return dict(base, resolution_state=CM.UNSUPPORTED_RESOLUTION_POLICY,
                        unresolved_reason="RELATIVE_DISABLED")
        return _resolve_relative(base, specifier, importing_file_path,
                                 tree_paths, source_completeness)

    # ── 3. 包自身引用（self-reference）──
    if package_observation and package_observation.get("declared_name"):
        name = package_observation["declared_name"]
        if specifier == name or specifier.startswith(name + "/"):
            return _resolve_self_reference(base, specifier, name,
                                           package_observation, tree_paths,
                                           conds, source_completeness)

    # ── 4. tsconfig paths ──
    if tsconfig_observation is not None:
        tc = tsconfig_observation
        if tc.get("effective_config_status") != CM.EFFECTIVE_CONFIG_RESOLVED:
            return dict(base, resolution_state=CM.CONFIG_NOT_CAPTURED,
                        config_observation_ids=[tc.get("config_observation_id")],
                        unresolved_reason=tc.get("effective_config_status"))
        return _resolve_paths(base, specifier, tsconfig_observation,
                              tree_paths, source_completeness)

    # ── 5. 无配置可用 ──
    return dict(base, resolution_state=CM.CONFIG_NOT_CAPTURED,
                unresolved_reason="NO_CONFIG_OBSERVATION")


def _resolve_relative(base, specifier, importing_file_path, tree_paths,
                      completeness):
    if completeness != "COMPLETE":
        return dict(base, resolution_state=CM.INSUFFICIENT_TREE_COVERAGE,
                    unresolved_reason="SOURCE_INCOMPLETE")
    target = _join(importing_file_path, specifier)
    if target is None:
        return dict(base, resolution_state=CM.PATH_ESCAPES_REPOSITORY,
                    unresolved_reason="PATH_TRAVERSAL")
    cands = _file_candidates(target, tree_paths)
    if not cands:
        return dict(base, resolution_state=CM.EXTERNAL_OR_UNRESOLVED,
                    unresolved_reason="NO_LOCAL_CANDIDATE",
                    matched_config_field="relative")
    if len(cands) > 1:
        return dict(base, resolution_state=CM.AMBIGUOUS_CANDIDATES,
                    matched_config_field="relative",
                    candidate_paths=cands,
                    unresolved_reason="MULTIPLE_CANDIDATES")
    return dict(base, resolution_state=CM.LOCAL_MODULE_RESOLVED,
                matched_config_field="relative",
                candidate_paths=cands, resolved_target_path=cands[0])


def _resolve_paths(base, specifier, tc, tree_paths, completeness):
    if completeness != "COMPLETE":
        return dict(base, resolution_state=CM.INSUFFICIENT_TREE_COVERAGE,
                    config_observation_ids=[tc.get("config_observation_id")],
                    unresolved_reason="SOURCE_INCOMPLETE")

    rules = tc.get("declared_paths") or []
    if not rules:
        return dict(base, resolution_state=CM.CONFIG_NOT_CAPTURED,
                    config_observation_ids=[tc.get("config_observation_id")],
                    unresolved_reason="NO_PATHS_DECLARED")

    base_dir = tc.get("_base_dir")
    if base_dir is None:
        base_dir = TP.resolve_base_dir(config_dir=tc.get("_config_dir") or "",
                                       base_url=tc.get("declared_base_url"))

    hits = EC.select_rules(rules, specifier)
    if not hits:
        return dict(base, resolution_state=CM.CONFIG_MAPPING_CANDIDATE,
                    config_observation_ids=[tc.get("config_observation_id")],
                    matched_config_field="paths",
                    matched_config_rule=None,
                    unresolved_reason="NO_MATCHING_PATH_RULE")

    best = hits[0]
    expanded = EC.expand_targets(best, base_dir=base_dir or "")
    rejected = [e for e in expanded if e.get("rejected")]
    usable = [e["path"] for e in expanded if e.get("path")]

    # ★ 目标含 * 未展开（通配残留在目标里）→ 上下文不完整
    if any("*" in (p or "") for p in usable):
        return dict(base, resolution_state=CM.RESOLUTION_CONTEXT_INCOMPLETE,
                    config_observation_ids=[tc.get("config_observation_id")],
                    matched_config_field="paths",
                    matched_config_rule=best["pattern"],
                    matched_config_path=tc.get("config_path"),
                    unresolved_reason="WILDCARD_UNEXPANDED")

    # ★ 逐个目标尝试（保留顺序），第一个命中即止
    tried = []
    for cand in usable:
        tried.append(cand)
        found = _file_candidates(cand, tree_paths)
        if found:
            if len(found) > 1:
                return dict(base, resolution_state=CM.AMBIGUOUS_CANDIDATES,
                            config_observation_ids=[tc.get("config_observation_id")],
                            matched_config_field="paths",
                            matched_config_rule=best["pattern"],
                            matched_config_path=tc.get("config_path"),
                            candidate_paths=found,
                            unresolved_reason="MULTIPLE_CANDIDATES")
            return dict(
                base, resolution_state=CM.LOCAL_MODULE_RESOLVED,
                config_observation_ids=[tc.get("config_observation_id")],
                matched_config_field="paths",
                matched_config_rule=best["pattern"],
                matched_config_path=tc.get("config_path"),
                candidate_paths=tried,
                resolved_target_path=found[0])

    return dict(base,
                resolution_state=(CM.CONFIG_MAPPING_CANDIDATE
                                  if not rejected
                                  else CM.PATH_ESCAPES_REPOSITORY),
                config_observation_ids=[tc.get("config_observation_id")],
                matched_config_field="paths",
                matched_config_rule=best["pattern"],
                matched_config_path=tc.get("config_path"),
                candidate_paths=tried,
                unresolved_reason=("TARGET_NOT_IN_TREE" if not rejected
                                   else "PATH_ESCAPES_REPOSITORY"))


def _resolve_hash(base, specifier, tree_paths, pkg, conds, completeness):
    if not pkg:
        return dict(base, resolution_state=CM.CONFIG_NOT_CAPTURED,
                    unresolved_reason="NO_PACKAGE_OBSERVATION")
    if pkg.get("effective_config_status") != CM.EFFECTIVE_CONFIG_RESOLVED:
        return dict(base, resolution_state=CM.CONFIG_NOT_CAPTURED,
                    config_observation_ids=[pkg.get("config_observation_id")],
                    unresolved_reason=pkg.get("effective_config_status"))
    imports = pkg.get("declared_imports") or {}
    if not isinstance(imports, dict):
        imports = {}
    key, value = PM.match_imports(imports, specifier)
    if key is None:
        return dict(base, resolution_state=CM.CONFIG_MAPPING_CANDIDATE,
                    config_observation_ids=[pkg.get("config_observation_id")],
                    matched_config_field="imports",
                    unresolved_reason="NO_MATCHING_IMPORTS_ENTRY")
    if PM.is_explicitly_blocked(value):
        return dict(base, resolution_state=CM.UNSUPPORTED_RESOLUTION_POLICY,
                    config_observation_ids=[pkg.get("config_observation_id")],
                    matched_config_field="imports",
                    matched_config_rule=key,
                    unresolved_reason="EXPORT_EXPLICITLY_BLOCKED")

    cap = _subpath_capture(key, specifier)
    exp = PM.expand_condition(value, available_conditions=conds, capture=cap)
    base.update(config_observation_ids=[pkg.get("config_observation_id")],
                matched_config_field="imports", matched_config_rule=key,
                matched_config_path=pkg.get("config_path"),
                condition_candidates=exp.get("candidates") or [])
    if not exp["resolved"]:
        return dict(base, resolution_state=CM.RESOLUTION_CONTEXT_INCOMPLETE,
                    unresolved_reason=exp.get("reason"))

    target = exp["target"]
    if not isinstance(target, str):
        return dict(base, resolution_state=CM.UNSUPPORTED_RESOLUTION_POLICY,
                    unresolved_reason="TARGET_NOT_LOCAL")
    if target.startswith("./") or target.startswith("../"):
        base_dir = TP.resolve_base_dir(config_dir=pkg.get("_config_dir") or "",
                                       base_url=None)
        norm = TP.normalize_target(target, base_dir=base_dir or "")
        if norm is None:
            return dict(base, resolution_state=CM.PATH_ESCAPES_REPOSITORY,
                        unresolved_reason="PATH_TRAVERSAL")
        found = _file_candidates(norm, tree_paths)
        if found:
            return dict(base, resolution_state=CM.LOCAL_MODULE_RESOLVED,
                        candidate_paths=found,
                        resolved_target_path=found[0])
        return dict(base, resolution_state=CM.CONFIG_MAPPING_CANDIDATE,
                    candidate_paths=[norm],
                    unresolved_reason="TARGET_NOT_IN_TREE")
    return dict(base, resolution_state=CM.UNSUPPORTED_RESOLUTION_POLICY,
                unresolved_reason="EXTERNAL_PACKAGE_MAPPING")


def _resolve_self_reference(base, specifier, name, pkg, tree_paths, conds,
                            completeness):
    if pkg.get("effective_config_status") != CM.EFFECTIVE_CONFIG_RESOLVED:
        return dict(base, resolution_state=CM.CONFIG_NOT_CAPTURED,
                    config_observation_ids=[pkg.get("config_observation_id")],
                    unresolved_reason=pkg.get("effective_config_status"))
    exports = pkg.get("declared_exports")
    if not exports:
        return dict(base, resolution_state=CM.CONFIG_NOT_CAPTURED,
                    config_observation_ids=[pkg.get("config_observation_id")],
                    matched_config_field="exports",
                    unresolved_reason="NO_EXPORTS_DECLARED")

    sub = "." if specifier == name else "." + specifier[len(name):]
    if not isinstance(exports, dict):
        exports = {".": exports}
    key, value = PM.match_subpath(exports, sub)
    base.update(config_observation_ids=[pkg.get("config_observation_id")],
                matched_config_field="exports", matched_config_rule=key,
                matched_config_path=pkg.get("config_path"))
    if key is None:
        # ★ exports 声明存在但该子路径未列出 → 封装边界，不得据文件存在而放行
        return dict(base, resolution_state=CM.UNSUPPORTED_RESOLUTION_POLICY,
                    unresolved_reason="SUBPATH_NOT_IN_EXPORTS")
    if PM.is_explicitly_blocked(value):
        return dict(base, resolution_state=CM.UNSUPPORTED_RESOLUTION_POLICY,
                    unresolved_reason="EXPORT_EXPLICITLY_BLOCKED")

    cap = _subpath_capture(key, sub)
    exp = PM.expand_condition(value, available_conditions=conds, capture=cap)
    base["condition_candidates"] = exp.get("candidates") or []
    if not exp["resolved"]:
        return dict(base, resolution_state=CM.RESOLUTION_CONTEXT_INCOMPLETE,
                    unresolved_reason=exp.get("reason"))
    target = exp["target"]
    if not isinstance(target, str) or not (target.startswith("./")
                                           or target.startswith("../")):
        return dict(base, resolution_state=CM.UNSUPPORTED_RESOLUTION_POLICY,
                    unresolved_reason="EXTERNAL_PACKAGE_MAPPING")
    base_dir = TP.resolve_base_dir(config_dir=pkg.get("_config_dir") or "",
                                   base_url=None)
    norm = TP.normalize_target(target, base_dir=base_dir or "")
    if norm is None:
        return dict(base, resolution_state=CM.PATH_ESCAPES_REPOSITORY,
                    unresolved_reason="PATH_TRAVERSAL")
    found = _file_candidates(norm, tree_paths)
    if found:
        return dict(base, resolution_state=CM.LOCAL_MODULE_RESOLVED,
                    candidate_paths=found, resolved_target_path=found[0])
    return dict(base, resolution_state=CM.CONFIG_MAPPING_CANDIDATE,
                candidate_paths=[norm], unresolved_reason="TARGET_NOT_IN_TREE")


def _subpath_capture(key, specifier):
    """从通配键里取出 * 捕获的内容（供目标展开）。"""
    if not isinstance(key, str) or "*" not in key:
        return None
    prefix, suffix = key.split("*", 1)
    if not specifier.startswith(prefix):
        return None
    end = len(specifier) - len(suffix) if suffix else len(specifier)
    if suffix and not specifier.endswith(suffix):
        return None
    return specifier[len(prefix):end]


def _join(source_path, specifier):
    parts = [p for p in source_path.split("/") if p]
    if not parts:
        return None
    base = parts[:-1]
    for seg in specifier.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not base:
                return None
            base.pop()
        else:
            base.append(seg)
    return "/".join(base)


def _file_candidates(path, tree_paths):
    """给定路径（可能无扩展名），在 Tree 中找候选。"""
    paths = {_safe_norm(p) for p in tree_paths}
    out = []
    if any(path.endswith(e) for e in RESOLVE_EXTS) and path in paths:
        return [path]
    for e in RESOLVE_EXTS:
        cand = path + e
        if cand in paths:
            out.append(cand)
    for ix in INDEX_NAMES:
        cand = f"{path}/{ix}"
        if cand in paths:
            out.append(cand)
    return out
