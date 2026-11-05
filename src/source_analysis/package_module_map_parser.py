#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""package.json 的 imports / exports 模块映射解析。

★ 只解析声明，不实现完整 Node.js 条件解析。
★ 条件分支无法确定时保留候选，绝不任选一条。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import module_config_models as CM

MAX_MAP_ENTRIES = 256

# Node 条件中常见的键（顺序有意义）
KNOWN_CONDITIONS = ("types", "import", "require", "node", "default")


def parse_package_map(data):
    """抽取 imports / exports / name / type。

    ★ 保留对象键的**语义顺序**（Python dict 保序）。
    """
    out = {
        "name": data.get("name") if isinstance(data.get("name"), str) else None,
        "type": (data.get("type") if data.get("type") in ("module", "commonjs")
                 else None),
        "imports": {},
        "exports": None,
        "exports_type": None,
    }
    imports = data.get("imports")
    if isinstance(imports, dict):
        for k in list(imports)[:MAX_MAP_ENTRIES]:
            if isinstance(k, str) and k.startswith("#"):
                out["imports"][k] = imports[k]

    exports = data.get("exports")
    if isinstance(exports, str):
        out["exports"] = {".": exports}
        out["exports_type"] = "string"
    elif isinstance(exports, dict):
        out["exports"] = exports
        out["exports_type"] = "object"
    elif isinstance(exports, list):
        out["exports"] = {".": exports}
        out["exports_type"] = "array"
    return out


def is_conditional(value):
    """值是否为条件对象（键是条件名而非子路径）。"""
    if not isinstance(value, dict):
        return False
    keys = [k for k in value]
    if not keys:
        return False
    # 子路径形式：键以 . 或 # 开头
    return not any(k.startswith(".") or k.startswith("#") for k in keys)


def expand_condition(value, *, available_conditions, capture=None):
    """在给定条件集合下展开条件对象。

    ★ 条件集合不足时返回多个候选并标记 unresolved，绝不选第一个。

    返回 {"target": str|None, "candidates": [...], "resolved": bool}
    """
    if isinstance(value, str):
        t = value.replace("*", capture) if (capture is not None and "*" in value) else value
        return {"target": t, "candidates": [t], "resolved": True,
                "condition_used": None}
    if isinstance(value, list):
        # 回退数组：按顺序尝试
        strs = [v for v in value if isinstance(v, str)]
        if len(strs) == 1:
            return {"target": strs[0], "candidates": strs, "resolved": True,
                    "condition_used": "array"}
        return {"target": None, "candidates": strs, "resolved": False,
                "condition_used": "array", "reason": "MULTI_TARGET_FALLBACK"}
    if isinstance(value, dict):
        cands = []
        used = None
        # ★ default 是兜底键：无论条件集合如何，都先记为"可兜底"
        default_entry = None
        for k, v in value.items():
            if k == "default":
                inner_d = expand_condition(v, available_conditions=available_conditions,
                                          capture=capture)
                default_entry = {"condition": "default",
                                 "target": inner_d.get("target")}
                cands.append(default_entry)
                continue
            if k in available_conditions:
                inner = expand_condition(v, available_conditions=available_conditions,
                                        capture=capture)
                if inner["resolved"] and inner["target"]:
                    cands.append({"condition": k, "target": inner["target"]})
                    if used is None:
                        used = k
            else:
                # 未满足的条件：记录候选但不选它
                inner = expand_condition(v, available_conditions=available_conditions,
                                        capture=capture)
                cands.append({"condition": k,
                              "target": inner.get("target"),
                              "available": False})
        # ★ default 是兜底条件：仅在没有任何其它可用条件时才生效
        non_default = [c for c in cands
                       if c.get("available") is not False
                       and c.get("target")
                       and c.get("condition") != "default"]
        resolved_ones = non_default if non_default else (
            [default_entry] if default_entry and default_entry.get("target")
            else [])
        if len(resolved_ones) == 1:
            return {"target": resolved_ones[0]["target"],
                    "candidates": cands, "resolved": True,
                    "condition_used": resolved_ones[0]["condition"]}
        if len(resolved_ones) > 1:
            # ★ 多个可用条件 → 无法唯一确定
            return {"target": None, "candidates": cands, "resolved": False,
                    "condition_used": None,
                    "reason": "MULTIPLE_CONDITIONS_AVAILABLE"}
        return {"target": None, "candidates": cands, "resolved": False,
                "condition_used": None, "reason": "NO_MATCHING_CONDITION"}
    return {"target": None, "candidates": [], "resolved": False,
            "condition_used": None, "reason": "UNSUPPORTED_EXPORT_VALUE"}


def match_subpath(exports_map, subpath):
    """在 exports 里查子路径（支持 * 通配与精确）。返回 (key, value)。"""
    if not isinstance(exports_map, dict):
        return None, None
    if subpath in exports_map:
        return subpath, exports_map[subpath]
    best = None
    for k in exports_map:
        if not isinstance(k, str) or "*" not in k:
            continue
        prefix, suffix = k.split("*", 1)
        if len(subpath) < len(prefix) + len(suffix):
            continue
        if not subpath.startswith(prefix):
            continue
        if suffix and not subpath.endswith(suffix):
            continue
        # 最长前缀优先
        if best is None or len(prefix) > len(best[0].split("*", 1)[0]):
            best = (k, exports_map[k])
    return best if best else (None, None)


def match_imports(imports_map, specifier):
    """在 imports 里查说明符（# 开头）。"""
    if not specifier.startswith("#"):
        return None, None
    if not isinstance(imports_map, dict):
        return None, None
    if specifier in imports_map:
        return specifier, imports_map[specifier]
    best = None
    for k in imports_map:
        if not isinstance(k, str) or "*" not in k:
            continue
        prefix, suffix = k.split("*", 1)
        if len(specifier) < len(prefix) + len(suffix):
            continue
        if not specifier.startswith(prefix):
            continue
        if suffix and not specifier.endswith(suffix):
            continue
        if best is None or len(prefix) > len(best[0].split("*", 1)[0]):
            best = (k, imports_map[k])
    return best if best else (None, None)


def is_explicitly_blocked(value):
    """null 等显式阻断目标。"""
    if value is None:
        return True
    if isinstance(value, list):
        return all(v is None for v in value)
    return False
