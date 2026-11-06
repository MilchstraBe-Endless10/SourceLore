#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tsconfig files / include / exclude 选择语义。

★ 只实现明确可验证的模式子集；不支持的降级为 UNSUPPORTED_SELECTION_RULE。
★ exclude 只影响 include 扫描，不是绝对排除。
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

MAX_FILES = 20000

# TypeScript 默认包含的扩展名（无 files/include 时）
DEFAULT_INCLUDE_EXT = (".ts", ".tsx", ".d.ts", ".js", ".jsx")
ALLOW_JS_EXT = (".js", ".jsx")


class UnsupportedPattern(ValueError):
    pass


def _norm(path):
    """规范化仓库相对路径。

    ★ 不能直接用 lstrip("./")：它会把绝对路径的前导 `/` 和 `../` 一起吃掉，
      导致越界路径被误当成合法相对路径。
    """
    p = (path or "").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def split_pattern(pattern):
    """把 include 模式拆成 (目录前缀, 匹配形式)。

    支持的子集：
      "src/**/*"       → 前缀 src/，形式 GLOB_ALL
      "src/**/*.ts"    → 前缀 src/，形式 GLOB_EXT(.ts) 且递归
      "src/*"          → 前缀 src/，形式 GLOB_ONE_LEVEL
      "src/types.ts"   → 精确文件
      "*.ts"           → 前缀 ""，形式 GLOB_EXT 单层
    不支持：`**` 不在段内、含 `{a,b}`、含 `!` 取反、多重 `**`。
    """
    if not isinstance(pattern, str) or not pattern:
        raise UnsupportedPattern("EMPTY_PATTERN")
    raw = (pattern or "").replace("\\", "/")
    # ★ 绝对路径判定必须用**原始值**，先归一化就把前导 / 抹掉了
    if raw.startswith("/"):
        raise UnsupportedPattern(f"ABSOLUTE_PATTERN_{raw}")
    p = _norm(raw)
    if "!" in p or "{" in p or "[" in p:
        raise UnsupportedPattern(f"UNSUPPORTED_BRACES_IN_{p}")
    segs = [s for s in p.split("/") if s]
    if len(segs) == 0:
        raise UnsupportedPattern("EMPTY_PATTERN")
    if segs.count("**") > 1:
        raise UnsupportedPattern(f"MULTIPLE_RECURSIVE_{p}")
    if any("**" in s and s != "**" for s in segs):
        raise UnsupportedPattern(f"EMBEDDED_RECURSIVE_{p}")

    if "**" in segs:
        idx = segs.index("**")
        prefix = "/".join(segs[:idx])
        rest = segs[idx + 1:]
        if len(rest) == 0:
            return {"prefix": prefix, "form": "RECURSIVE_ANY",
                    "ext": None, "pattern": p}
        if len(rest) == 1:
            last = rest[0]
            if "*" in last:
                if last.count("*") > 1 or not last.startswith("*"):
                    raise UnsupportedPattern(f"COMPLEX_TAIL_{p}")
                ext = last[1:]                    # "*.ts" → ".ts"
                return {"prefix": prefix, "form": "RECURSIVE_EXT",
                        "ext": ext, "pattern": p}
            return {"prefix": prefix, "form": "RECURSIVE_EXACT",
                    "ext": None, "suffix": last, "pattern": p}
        raise UnsupportedPattern(f"TOO_DEEP_AFTER_RECURSIVE_{p}")

    # 无 **：单层
    if len(segs) == 1:
        s = segs[0]
        if s == "*":
            return {"prefix": "", "form": "ONE_LEVEL_ANY", "ext": None,
                    "pattern": p}
        if s.startswith("*") and s.count("*") == 1:
            return {"prefix": "", "form": "ONE_LEVEL_EXT", "ext": s[1:],
                    "pattern": p}
        return {"prefix": "", "form": "EXACT", "ext": None, "suffix": s,
                "pattern": p}

    prefix = "/".join(segs[:-1])
    last = segs[-1]
    if last == "*":
        return {"prefix": prefix, "form": "ONE_LEVEL_ANY", "ext": None,
                "pattern": p}
    if last.startswith("*") and last.count("*") == 1:
        return {"prefix": prefix, "form": "ONE_LEVEL_EXT", "ext": last[1:],
                "pattern": p}
    return {"prefix": prefix, "form": "EXACT", "ext": None, "suffix": last,
            "pattern": p}


def match_pattern(spec, file_path):
    """判断已解析的 include 规格是否匹配仓库相对路径。返回 bool。"""
    fp = _norm(file_path)
    prefix = spec.get("prefix") or ""
    form = spec.get("form")

    if form in ("EXACT", "RECURSIVE_EXACT"):
        target = f"{prefix}/{spec['suffix']}" if prefix else spec["suffix"]
        return fp == _norm(target)

    if prefix:
        if not (fp == prefix or fp.startswith(prefix + "/")):
            return False
        rel = fp[len(prefix) + 1:] if fp.startswith(prefix + "/") else fp
    else:
        rel = fp
    if not rel:
        return False
    depth = rel.count("/")

    if form == "ONE_LEVEL_ANY":
        return depth == 0
    if form == "ONE_LEVEL_EXT":
        return depth == 0 and rel.endswith(spec["ext"])
    if form == "RECURSIVE_ANY":
        return True
    if form == "RECURSIVE_EXT":
        return rel.endswith(spec["ext"])
    return False


def _file_matches_any(specs, file_path):
    for spec in specs:
        if match_pattern(spec, file_path):
            return spec
    return None


def prepare_rules(*, include, exclude, config_dir):
    """把声明的 include/exclude 解析成内部规格。返回 (inc, exc, problems)。"""
    inc, exc, problems = [], [], []

    for pat in include or []:
        try:
            spec = split_pattern(pat)
            spec["base"] = TP.normalize_target(
                spec["prefix"] or ".", base_dir=config_dir or "")
            if spec["base"] is None:
                problems.append({"pattern": pat,
                                 "reason": "PATH_ESCAPES_REPOSITORY"})
                continue
            if spec["prefix"]:
                spec["prefix"] = spec["base"]
            inc.append(spec)
        except UnsupportedPattern as e:
            problems.append({"pattern": pat, "reason": str(e)})

    for pat in exclude or []:
        try:
            spec = split_pattern(pat)
            spec["base"] = TP.normalize_target(
                spec["prefix"] or ".", base_dir=config_dir or "")
            if spec["base"] is None:
                problems.append({"pattern": pat,
                                 "reason": "PATH_ESCAPES_REPOSITORY"})
                continue
            if spec["prefix"]:
                spec["prefix"] = spec["base"]
            exc.append(spec)
        except UnsupportedPattern as e:
            problems.append({"pattern": pat, "reason": str(e)})

    return inc, exc, problems


def declared_files(*, files, config_dir):
    """声明的 files 列表 → 仓库相对路径（保留声明顺序）。"""
    out, rejected = [], []
    for f in files or []:
        norm = TP.normalize_target(f, base_dir=config_dir or "")
        if norm is None:
            rejected.append({"file": f, "reason": "PATH_ESCAPES_REPOSITORY"})
            continue
        out.append(norm)
    return out, rejected


def default_inclusion_active(*, files_declared, include_declared,
                            exclude_declared, allow_js):
    """TypeScript 默认文件集合规则。

    ★ 关键：`files: []` **不**触发默认扫描（显式空数组表示没有输入文件）；
       只有完全未声明 files 且未声明 include 时，才用默认通配。
       这与「把 files=[] 当成未声明」是两回事。
    """
    if files_declared:
        return {"active": False, "reason": "FILES_DECLARED"}
    if include_declared:
        return {"active": False, "reason": "INCLUDE_DECLARED"}
    exts = list(DEFAULT_INCLUDE_EXT)
    if not allow_js:
        exts = [e for e in exts if e not in ALLOW_JS_EXT]
    return {"active": True, "reason": "DEFAULT_RECURSIVE_INCLUDE",
            "extensions": exts}


def evaluate_file(*, file_path, tree_paths, project, inc_specs, exc_specs,
                  explicit_files, default_rule):
    """判定单个文件在该项目下的输入选择状态。"""
    fp = _norm(file_path)
    in_tree = fp in {_norm(p) for p in tree_paths}

    base = {
        "source_file_path": fp,
        "config_path": project["config_path"],
        "project_id": project["project_observation_id"],
        "in_tree": in_tree,
    }

    # ① files 显式列出（★ 优先于 include，且不受 exclude 影响）
    if explicit_files and fp in explicit_files:
        return dict(base, state=PM.INPUT_EXPLICITLY_LISTED,
                    matched_field="files", matched_rule=fp,
                    selection_mode="explicit_files")

    # ② include 匹配
    matched_inc = _file_matches_any(inc_specs, fp)
    if matched_inc:
        # ③ exclude 只过滤 include 结果
        matched_exc = _file_matches_any(exc_specs, fp)
        if matched_exc:
            return dict(base, state=PM.INPUT_EXCLUDED_FROM_INCLUDE,
                        matched_field="include",
                        matched_rule=matched_inc["pattern"],
                        excluded_by=matched_exc["pattern"],
                        selection_mode="include_excluded")
        return dict(base, state=PM.INPUT_MATCHED_INCLUDE,
                    matched_field="include",
                    matched_rule=matched_inc["pattern"],
                    selection_mode="include")

    # ④ 默认扫描规则（仅当 files 与 include 都未声明）
    if default_rule.get("active"):
        if fp.endswith(tuple(default_rule["extensions"])):
            matched_exc = _file_matches_any(exc_specs, fp)
            if matched_exc:
                return dict(base, state=PM.INPUT_EXCLUDED_FROM_INCLUDE,
                            matched_field="default_include",
                            matched_rule="DEFAULT_RECURSIVE_INCLUDE",
                            excluded_by=matched_exc["pattern"],
                            selection_mode="default_excluded")
            return dict(base, state=PM.INPUT_MATCHED_INCLUDE,
                        matched_field="default_include",
                        matched_rule="DEFAULT_RECURSIVE_INCLUDE",
                        selection_mode="default")

    # ⑤ 都未命中
    if fp.endswith((".ts", ".tsx", ".d.ts")):
        return dict(base, state=PM.INPUT_POSSIBLE_VIA_IMPORT,
                    matched_field=None, matched_rule=None,
                    selection_mode="not_selected_but_importable")
    return dict(base, state=PM.INPUT_NOT_PROVEN,
                matched_field=None, matched_rule=None,
                selection_mode="not_selected")


def evaluate_project_files(*, project, tree_paths, inc_specs, exc_specs,
                          explicit_files, default_rule, target_file=None):
    """对全量或单个文件求归属。返回 list of membership dict。"""
    if target_file:
        candidates = [target_file]
    else:
        candidates = sorted(tree_paths)
        if len(candidates) > MAX_FILES:
            candidates = candidates[:MAX_FILES]

    out = []
    for fp in candidates:
        r = evaluate_file(file_path=fp, tree_paths=tree_paths, project=project,
                          inc_specs=inc_specs, exc_specs=exc_specs,
                          explicit_files=explicit_files, default_rule=default_rule)
        out.append(r)
    return out
