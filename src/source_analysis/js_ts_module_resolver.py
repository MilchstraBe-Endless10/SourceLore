#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JS/TS 有界模块解析。

★ 与 Python 规则截然不同：ESM/CJS 有别、扩展名可省略、index 约定、路径别名。
★ 本版只支持**明确的相对路径**；别名/第三方/裸模块一律不猜。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import source_models as SM

# 七态
RELATIVE_FOUND = "RELATIVE_PATH_CANDIDATE_FOUND"
DYNAMIC = "DYNAMIC_SPECIFIER"
UNSUPPORTED_POLICY = "UNSUPPORTED_RESOLUTION_POLICY"

RESOLVE_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def _safe_norm(p):
    """★ 只剥前导 "./"，不碰前导 "/" 与 "../"（D-37 阻断）。"""
    s = (p or "").replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s

def resolve_js_import(*, import_record, source_path, tree_paths,
                     source_completeness="COMPLETE"):
    """返回 {status, candidates, reason}。"""
    if source_completeness != "COMPLETE":
        return _r(SM.INSUFFICIENT_TREE, [], "SOURCE_INCOMPLETE")

    spec = import_record.get("module_specifier")
    status = import_record.get("specifier_status")

    if status == "DYNAMIC_MODULE_SPECIFIER" or spec is None:
        return _r(DYNAMIC, [], "NON_LITERAL_SPECIFIER")

    if not tree_paths:
        return _r(SM.INSUFFICIENT_TREE, [], "EMPTY_TREE")

    # 裸模块 / 别名 / 子路径导入 → 不支持（不假装能解析）
    if not spec.startswith("./") and not spec.startswith("../"):
        reason = ("ALIAS_OR_BARE_MODULE" if spec.startswith("@")
                  else "BARE_MODULE_SPECIFIER" if not spec.startswith("#")
                  else "HASH_ALIAS")
        return _r(UNSUPPORTED_POLICY, [], reason)

    # 相对路径：构造候选
    base = _join(source_path, spec)
    if base is None:
        return _r(UNSUPPORTED_POLICY, [], "PATH_TRAVERSAL")

    cands = _candidates(base, tree_paths)
    if not cands:
        return _r(SM.EXTERNAL, [], "NO_LOCAL_CANDIDATE")

    if len(cands) > 1:
        return _r(SM.AMBIGUOUS, cands, "MULTIPLE_CANDIDATES")

    return _r(SM.RESOLVED, cands, "UNIQUE_RELATIVE_MATCH")


def _r(status, cands, reason):
    return {"status": status, "candidates": cands, "reason": reason}


def _join(source_path, spec):
    """把相对说明符解析成候选路径前缀（不含扩展名）。"""
    parts = [p for p in source_path.split("/") if p]
    if not parts:
        return None
    base = parts[:-1]                       # 去掉文件名
    for seg in spec.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not base:
                return None
            base.pop()
        else:
            base.append(seg)
    return "/".join(base)


def _candidates(base, tree_paths):
    """生成候选：精确文件 / index 约定 / 带扩展名。"""
    paths = {_safe_norm(p) for p in tree_paths}
    out = []

    def add(path, kind):
        out.append({"path": path, "candidate_kind": kind})

    # 1) 说明符本身带扩展名
    if any(base.endswith(e) for e in RESOLVE_EXTS):
        if base in paths:
            add(base, "exact_with_extension")
        return out

    # 2) 精确文件 + 常见扩展
    for e in RESOLVE_EXTS:
        cand = base + e
        if cand in paths:
            add(cand, "extension_inferred")

    # 3) 目录 index 约定
    for e in RESOLVE_EXTS:
        cand = f"{base}/index{e}"
        if cand in paths:
            add(cand, "directory_index")

    return out


def supports_relative_only(spec):
    """说明符是否属本版可控范围。"""
    return bool(spec) and (spec.startswith("./") or spec.startswith("../"))
