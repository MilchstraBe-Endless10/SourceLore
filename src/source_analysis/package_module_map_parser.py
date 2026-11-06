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


def expand_condition(value, *, available_conditions, capture=None,
                     conditions_deterministic=True):
    """按 Node 规范展开条件对象。

    ★ 规范要点（https://nodejs.org/api/packages.html#conditional-exports）：
      1. 条件对象**按键的原始顺序**匹配，第一个命中者胜出。
      2. `default` 是**始终匹配**的通用条件——不因它在前面就跳过。
      3. 若某个命中键的值解析不出目标，**继续尝试下一个**。
      4. `types` 是 TypeScript 的键，不是 Node 运行时默认条件；
         只有显式放进 available_conditions 才算可用。

    ★ 条件集合本身不确定时（conditions_deterministic=False 且存在未知键），
      返回未解析，绝不任选。
    """
    if isinstance(value, str):
        t = (value.replace("*", capture)
             if (capture is not None and "*" in value) else value)
        return {"target": t, "candidates": [t], "resolved": True,
                "condition_used": None, "skipped": []}

    if isinstance(value, list):
        # 回退数组：按顺序，第一个能解析的胜出
        for item in value:
            if isinstance(item, str):
                t = (item.replace("*", capture)
                     if (capture is not None and "*" in item) else item)
                return {"target": t, "candidates": [item], "resolved": True,
                        "condition_used": "array", "skipped": []}
            if item is None:
                return {"target": None, "candidates": [], "resolved": False,
                        "condition_used": None,
                        "reason": "EXPORT_EXPLICITLY_BLOCKED", "skipped": []}
            if isinstance(item, dict):
                inner = expand_condition(
                    item, available_conditions=available_conditions,
                    capture=capture,
                    conditions_deterministic=conditions_deterministic)
                if inner["resolved"] and inner["target"]:
                    return inner
        return {"target": None, "candidates": [], "resolved": False,
                "condition_used": "array",
                "reason": "NO_RESOLVABLE_ARRAY_ENTRY", "skipped": []}

    if isinstance(value, dict):
        if not value:
            return {"target": None, "candidates": [], "resolved": False,
                    "condition_used": None,
                    "reason": "EMPTY_CONDITION_OBJECT", "skipped": []}

        cands = []
        skipped = []
        saw_unknown = False
        won = None
        won_target = None
        blocker = None

        for k, v in value.items():
            # ── 判定该键在当前条件下是否命中 ──
            if k == "default":
                hit = True
            elif k in (available_conditions or ()):
                hit = True
            else:
                hit = False
                if k not in KNOWN_CONDITIONS:
                    saw_unknown = True

            inner = None
            if hit and v is None:
                # ★ null 是显式阻断，必须先于递归判定
                cands.append({"condition": k, "matched": True,
                              "target": None, "resolved": False})
                return {"target": None, "candidates": cands,
                        "resolved": False, "condition_used": k,
                        "reason": "EXPORT_EXPLICITLY_BLOCKED",
                        "skipped": skipped}
            if hit:
                inner = expand_condition(
                    v, available_conditions=available_conditions,
                    capture=capture,
                    conditions_deterministic=conditions_deterministic)

            cands.append({
                "condition": k, "matched": hit,
                "target": inner.get("target") if inner else None,
                "resolved": bool(inner and inner.get("resolved")),
            })

            if not hit:
                skipped.append({"condition": k,
                                "reason": "CONDITION_NOT_ACTIVE"})
                continue

            # ★ 命中且能解析 → 记录为胜出，但继续遍历其余键
            #   （候选清单必须包含全部键，供诊断与展示）
            if inner and inner["resolved"] and inner["target"] and won is None:
                won = k
                won_target = inner["target"]

            # 命中但值为 null → 显式阻断（仍先记满候选，见循环后处理）
            if inner and inner.get("reason") == "EXPORT_EXPLICITLY_BLOCKED":
                blocker = k
                continue

            # 命中但解析不出 → 记录并继续尝试下一个
            if won is None:
                skipped.append({"condition": k,
                                "reason": (inner or {}).get("reason")
                                or "NO_RESOLVABLE_TARGET"})

        # ★ 显式阻断优先于任何命中
        if blocker is not None:
            return {"target": None, "candidates": cands, "resolved": False,
                    "condition_used": blocker,
                    "reason": "EXPORT_EXPLICITLY_BLOCKED",
                    "skipped": skipped}

        # ★ 有胜出者 → 按其顺序最先者定论
        if won is not None:
            return {"target": won_target, "candidates": cands,
                    "resolved": True, "condition_used": won,
                    "skipped": skipped}

        # ★ 条件集合不确定且存在未知键 → 不能断定没有匹配
        if saw_unknown and not conditions_deterministic:
            return {"target": None, "candidates": cands, "resolved": False,
                    "condition_used": None,
                    "reason": "UNKNOWN_CONDITIONS_PRESENT",
                    "skipped": skipped}

        return {"target": None, "candidates": cands, "resolved": False,
                "condition_used": None, "reason": "NO_MATCHING_CONDITION",
                "skipped": skipped}

    return {"target": None, "candidates": [], "resolved": False,
            "condition_used": None, "reason": "UNSUPPORTED_EXPORT_VALUE",
            "skipped": []}


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
