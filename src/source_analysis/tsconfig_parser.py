#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tsconfig / jsconfig 解析：JSONC → 结构化配置。

★ 只解析，不执行；配置原文只作数据。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import tsconfig_jsonc as JC

MAX_RULES = 256
MAX_PATHS_LEN = 512


def parse_tsconfig(raw, *, config_path):
    """返回 dict：{ok, data|None, error_code, error_detail}。"""
    try:
        data = JC.parse_jsonc_bytes(raw, path=config_path)
    except JC.JsoncError as e:
        return {"ok": False, "data": None, "error_code": e.code,
                "error_detail": e.detail}
    return {"ok": True, "data": data, "error_code": None,
            "error_detail": None}


def extract_config_surface(data, *, config_dir):
    """抽取模块解析相关字段。

    ★ config_dir 是相对仓库根的目录（'' 表示根）。
    """
    comp = data.get("compilerOptions") if isinstance(data, dict) else None
    comp = comp if isinstance(comp, dict) else {}

    base_url = comp.get("baseUrl")
    if base_url is not None and not isinstance(base_url, str):
        base_url = None

    raw_paths = comp.get("paths") if isinstance(comp.get("paths"), dict) else {}
    rules = []
    for key in raw_paths:
        targets = raw_paths[key]
        if not isinstance(key, str):
            continue
        if not isinstance(targets, list):
            continue
        clean = [t for t in targets if isinstance(t, str)]
        if not clean:
            continue
        rules.append({"pattern": key, "targets": clean})
        if len(rules) >= MAX_RULES:
            break

    extends = data.get("extends")
    if isinstance(extends, str):
        ext_list = [extends]
    elif isinstance(extends, list):
        ext_list = [x for x in extends if isinstance(x, str)]
    else:
        ext_list = []

    refs = data.get("references")
    ref_list = []
    if isinstance(refs, list):
        for r in refs:
            if isinstance(r, dict) and isinstance(r.get("path"), str):
                ref_list.append({"path": r["path"]})
            elif isinstance(r, str):
                ref_list.append({"path": r})

    return {
        "base_url": base_url,
        "paths": rules,
        "extends": ext_list,
        "references": ref_list,
        "module": comp.get("module"),
        "module_resolution": comp.get("moduleResolution"),
        "custom_conditions": comp.get("customConditions"),
        "paths_declared": isinstance(comp.get("paths"), dict),
        "config_dir": config_dir,
    }


def resolve_base_dir(*, config_dir, base_url):
    """★ baseUrl 缺失时不得默认用项目根。

    按 TypeScript 规则：有 baseUrl → baseUrl 相对**配置目录**；
    无 baseUrl → 映射基准就是**配置目录**本身。
    """
    if base_url and isinstance(base_url, str):
        return _norm_posix(config_dir, base_url)
    return config_dir or ""


def _norm_posix(config_dir, rel):
    """把相对路径按配置目录归一化，拒绝越界。"""
    parts = [p for p in (config_dir or "").split("/") if p]
    for seg in rel.replace("\\", "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return None          # 越界
            parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def normalize_target(target, *, base_dir):
    """把 paths 目标装成仓库相对路径（去 ./，处理 ..）。"""
    if not isinstance(target, str):
        return None
    t = target.replace("\\", "/")
    if t.startswith("/"):
        return None                   # 绝对路径一律拒绝
    return _norm_posix(base_dir, t)


TS_EXT_STRIP = (".js", ".jsx", ".mjs", ".cjs", ".d.ts", ".ts", ".tsx",
                ".mts", ".cts")


def strip_ts_extension(path):
    """去掉 TypeScript 允许的扩展名（供匹配用户写法）。"""
    low = path.lower()
    if low.endswith(".d.ts"):
        return path[:-5]
    for e in (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"):
        if low.endswith(e):
            return path[:-len(e)]
    return path
