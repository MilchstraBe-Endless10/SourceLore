#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tsconfig 有效配置：paths 匹配 + extends 继承。

★ TypeScript 的 paths 匹配规则是「最长字面前缀优先，`*` 通配兜底」，
   不是按配置文件里出现的顺序。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import module_config_models as CM
import tsconfig_parser as TP

MAX_INHERIT_DEPTH = 8
MAX_CANDIDATES = 64


def match_pattern(pattern, specifier):
    """判断 paths 模式是否匹配 specifier。返回捕获的 * 内容或 None。

    ★ `*` 只在模式里出现一次；有 * → 前缀/后缀匹配；无 * → 精确匹配。
    """
    if not isinstance(pattern, str) or not pattern:
        return None
    star = pattern.find("*")
    if star < 0:
        return "" if specifier == pattern else None
    prefix = pattern[:star]
    suffix = pattern[star + 1:]
    if len(specifier) < len(prefix) + len(suffix):
        return None
    if not specifier.startswith(prefix):
        return None
    if suffix and not specifier.endswith(suffix):
        return None
    end = len(specifier) - len(suffix) if suffix else len(specifier)
    return specifier[len(prefix):end]


def pattern_rank(pattern):
    """★ 匹配优先级：精确匹配最高；通配越长（字面前缀越具体）越优先。

    排序键：(有无通配, -前缀长度)
    精确 → (0, 0)；`@lib/*` 前缀 4 → (1, -4)；`@/*` 前缀 2 → (1, -2)；
    `*` 前缀 0 → (1, 0)。升序排序 → 精确最先，`*` 最后。
    """
    if not isinstance(pattern, str):
        return (9, 0)
    star = pattern.find("*")
    if star < 0:
        return (0, 0)
    return (1, -star)


def select_rules(rules, specifier):
    """选出所有匹配的规则，按 TypeScript 优先级排序（第一个最优）。"""
    hits = []
    for r in rules:
        pat = r.get("pattern")
        cap = match_pattern(pat, specifier)
        if cap is None:
            continue
        hits.append({"pattern": pat, "targets": r.get("targets") or [],
                     "capture": cap, "rank": pattern_rank(pat)})
    hits.sort(key=lambda h: h["rank"])
    return hits


def expand_targets(rule, *, base_dir):
    """把规则的 targets 展开成仓库相对路径（保留顺序）。"""
    out = []
    capture = rule.get("capture")
    for t in rule.get("targets") or []:
        if len(out) >= MAX_CANDIDATES:
            break
        if not isinstance(t, str):
            continue
        subst = t.replace("*", capture) if "*" in t else t
        norm = TP.normalize_target(subst, base_dir=base_dir)
        if norm is None:
            out.append({"path": None, "raw": t,
                        "rejected": CM.PATH_ESCAPES_REPOSITORY})
            continue
        out.append({"path": norm, "raw": t, "rejected": None})
    return out


def resolve_extends_chain(*, config_path, read_config, max_depth=MAX_INHERIT_DEPTH):
    """沿 extends 链向上读取。read_config(path) → {ok,data,error_code} 或 None。

    ★ 只支持**同仓库同 Commit 的本地配置**；其它来源返回 UNRESOLVED。
    ★ 检测循环与深度。
    """
    chain = []
    visited = set()
    current = config_path
    depth = 0

    while current:
        if depth > max_depth:
            return {"ok": False, "chain": chain,
                    "error": CM.CONFIG_INHERITANCE_TOO_DEEP}
        if current in visited:
            return {"ok": False, "chain": chain,
                    "error": CM.CONFIG_INHERITANCE_CYCLE}
        visited.add(current)

        got = read_config(current)
        if got is None:
            return {"ok": False, "chain": chain,
                    "error": CM.CONFIG_CONTENT_NOT_CAPTURED}
        if not got.get("ok"):
            return {"ok": False, "chain": chain,
                    "error": got.get("error_code") or CM.CONFIG_PARSE_FAILED}

        surface = TP.extract_config_surface(
            got["data"], config_dir=str(Path(current).parent).replace(".", "")
            if str(Path(current).parent) != "." else "")
        chain.append({"config_path": current, "surface": surface})

        exts = surface.get("extends") or []
        if not exts:
            break
        if len(exts) > 1:
            # 多个 extends 需要合并语义，本轮不完整实现 → 明确降级
            return {"ok": False, "chain": chain,
                    "error": CM.CONFIG_INHERITANCE_UNRESOLVED}
        nxt = exts[0]
        if not _is_local_extends(nxt):
            return {"ok": False, "chain": chain,
                    "error": CM.CONFIG_INHERITANCE_UNRESOLVED}
        resolved = _resolve_extends_path(nxt, config_dir=str(
            Path(current).parent).replace(".", "") if str(Path(current).parent) != "." else "")
        if resolved is None:
            return {"ok": False, "chain": chain,
                    "error": CM.CONFIG_INHERITANCE_UNRESOLVED}
        current = resolved
        depth += 1

    return {"ok": True, "chain": chain, "error": None}


def _is_local_extends(value):
    """本地相对路径才算可解析；裸包名/绝对路径 → 不支持。"""
    if not isinstance(value, str) or not value:
        return False
    if value.startswith("/"):
        return False
    return value.startswith("./") or value.startswith("../") or \
        value.endswith(".json")


def _resolve_extends_path(value, *, config_dir):
    if value.endswith(".json"):
        rel = value
    else:
        rel = value + ".json"
    return TP.normalize_target(rel, base_dir=config_dir)


def merge_chain(chain):
    """合成有效配置：子配置覆盖父配置的基字段。

    ★ paths 子配置有则覆盖（TypeScript 语义：paths 不合并）。
    """
    base_url = None
    paths = []
    module_resolution = None
    custom = None
    for entry in reversed(chain):        # 从最父级往子级叠加
        s = entry["surface"]
        if s.get("base_url"):
            base_url = s["base_url"]
        if s.get("paths"):
            paths = s["paths"]
        if s.get("module_resolution"):
            module_resolution = s["module_resolution"]
        if s.get("custom_conditions"):
            custom = s["custom_conditions"]
    return {"base_url": base_url, "paths": paths,
            "module_resolution": module_resolution,
            "custom_conditions": custom,
            "chain_length": len(chain)}
