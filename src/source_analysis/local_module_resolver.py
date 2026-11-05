#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""有界本地模块解析。

★ 只在**当前 Commit 已登记的 Tree** 内找候选。
  绝不访问其他 Commit、绝不看本机已安装包。
  文件路径匹配只证明静态候选关系，不证明运行时导入成功。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import source_models as SM


def _norm_dir(path):
    return [p for p in path.split("/") if p not in ("", ".")]


def _resolve_relative(source_path, level, module_name):
    """相对导入 → 绝对候选路径部分。level=1 表示当前目录。"""
    parts = _norm_dir(source_path)
    base_dir = parts[:-1]          # 去掉文件名
    up = max(0, level - 1)
    if up > len(base_dir):
        return None
    if up:
        base_dir = base_dir[:len(base_dir) - up]
    if module_name:
        base_dir = base_dir + _norm_dir(module_name)
    return base_dir


def resolve_import(*, import_record, source_path, tree_paths,
                   source_completeness="COMPLETE"):
    """返回 {status, candidates, reason}。

    tree_paths：当前 Commit 已登记的全部路径集合（set）。
    """
    if source_completeness != "COMPLETE":
        return {"status": SM.INSUFFICIENT_TREE, "candidates": [],
                "reason": "SOURCE_INCOMPLETE"}

    if not tree_paths:
        return {"status": SM.INSUFFICIENT_TREE, "candidates": [],
                "reason": "EMPTY_TREE"}

    syntax = import_record.get("import_syntax")
    module_name = import_record.get("module_name") or ""
    imported = import_record.get("imported_name")
    level = import_record.get("relative_level") or 0

    if imported == "*":
        # star import 形式可行，但目标不确定 → 不解析为本地
        pass

    if syntax == "from_import" and level > 0:
        base = _resolve_relative(source_path, level, module_name)
        if base is None:
            return {"status": SM.UNSUPPORTED_FORM, "candidates": [],
                    "reason": "RELATIVE_LEVEL_TOO_DEEP"}
        cands = _candidates_for(base, imported, tree_paths)
    elif syntax in ("import", "from_import"):
        if not module_name or module_name.startswith("."):
            return {"status": SM.UNSUPPORTED_FORM, "candidates": [],
                    "reason": "DYNAMIC_OR_EMPTY_MODULE"}
        if level == 0:
            base = _norm_dir(module_name)
            cands = _candidates_for(base, imported, tree_paths)
        else:
            base = _resolve_relative(source_path, level, module_name)
            if base is None:
                return {"status": SM.UNSUPPORTED_FORM, "candidates": [],
                        "reason": "RELATIVE_LEVEL_TOO_DEEP"}
            cands = _candidates_for(base, imported, tree_paths)
    else:
        return {"status": SM.UNSUPPORTED_FORM, "candidates": [],
                "reason": f"UNKNOWN_SYNTAX:{syntax}"}

    if not cands:
        return {"status": SM.EXTERNAL, "candidates": [],
                "reason": "NO_LOCAL_CANDIDATE"}

    # 目录 + __init__.py 组合 vs 单模块 → 若两者同时成立则为歧义
    kinds = {c["candidate_kind"] for c in cands}
    if len(cands) > 1 and "module" in kinds and "package_init" in kinds:
        return {"status": SM.AMBIGUOUS, "candidates": cands,
                "reason": "MODULE_AND_PACKAGE_BOTH_EXIST"}
    if len(cands) > 1 and len({c["path"] for c in cands}) > 1:
        return {"status": SM.AMBIGUOUS, "candidates": cands,
                "reason": "MULTIPLE_CANDIDATES"}

    return {"status": SM.RESOLVED, "candidates": cands[:1],
            "reason": "UNIQUE_LOCAL_MATCH"}


def _candidates_for(base_parts, imported, tree_paths):
    """★ 精确构造候选路径，不做前缀扫描。

    `import pkg`         → pkg.py 或 pkg/__init__.py
    `from pkg import core` → pkg/core.py 或 pkg/core/__init__.py
    """
    paths = {p.lstrip("./") for p in tree_paths}

    # ★ from X import Y：Y 若是子模块，Python 语义上优先取子模块（不是歧义）
    if imported and imported != "*":
        sub = _probe(list(base_parts) + [imported], paths)
        if sub:
            return sub
        return _probe(list(base_parts), paths)

    return _probe(list(base_parts), paths)


def _probe(base, paths):
    out = []
    mod = "/".join(base) + ".py"
    if mod in paths:
        out.append({"path": mod, "candidate_kind": "module"})
    pkg_init = "/".join(base) + "/__init__.py"
    if pkg_init in paths:
        out.append({"path": pkg_init, "candidate_kind": "package_init"})
    return out
