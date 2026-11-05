#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tree-sitter 运行时封装。

★ 依赖隔离：只从项目 venv 或已安装环境取；**绝不自动下载 grammar**。
★ 若不可用 → PARSER_UNAVAILABLE + 明确原因，绝不降级为正则猜测。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

CORE_VERSION = "0.26.0"
JS_GRAMMAR_VERSION = "0.25.0"
TS_GRAMMAR_VERSION = "0.23.2"

PARSER_UNAVAILABLE = "PARSER_UNAVAILABLE"
PARSE_COMPLETE = "PARSE_COMPLETE"
PARSE_WITH_ERRORS = "PARSE_WITH_ERRORS"
PARSE_UNSUPPORTED_SYNTAX = "PARSE_UNSUPPORTED_SYNTAX"
SOURCE_INCOMPLETE = "SOURCE_INCOMPLETE"
CONTENT_INTEGRITY_FAILED = "CONTENT_INTEGRITY_FAILED"

# 语言 → (grammar 包, 构造函数, grammar 版本)
_LANG_SPEC = {
    "javascript": ("tree_sitter_javascript", "language", JS_GRAMMAR_VERSION),
    "jsx": ("tree_sitter_javascript", "language", JS_GRAMMAR_VERSION),
    "typescript": ("tree_sitter_typescript", "language_typescript",
                   TS_GRAMMAR_VERSION),
    "tsx": ("tree_sitter_typescript", "language_tsx", TS_GRAMMAR_VERSION),
}

_EXT_TO_LANG = {".js": "javascript", ".jsx": "jsx",
                ".ts": "typescript", ".tsx": "tsx",
                ".mjs": "javascript", ".cjs": "javascript",
                ".mts": "typescript", ".cts": "typescript"}

# 遍历预算（防恶意/超大语法树）
MAX_NODES = 20000
MAX_DEPTH = 200


class RuntimeUnavailable(RuntimeError):
    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def language_for_path(path: str):
    """按扩展名判定语言。★ 不根据内容猜测。"""
    ext = Path(path).suffix.lower()
    return _EXT_TO_LANG.get(ext)


def _ensure_site_packages():
    """把**项目内 venv** 的 site-packages 加入 sys.path（若存在）。

    ★ 只认项目根下的 .venv / venv，不依赖 /tmp，保证重启后仍有效。
    ★ 不自动下载 grammar，不修改系统 Python。
    """
    for name in (".venv", "venv"):
        venv = _ROOT / name / "lib"
        if not venv.is_dir():
            continue
        for sp in venv.glob("python*/site-packages"):
            if str(sp) not in sys.path:
                sys.path.insert(0, str(sp))


def available_languages():
    """返回实际可加载的语言清单（含失败原因）。★ 不缓存外部状态到磁盘。"""
    _ensure_site_packages()
    out = {}
    try:
        import tree_sitter  # noqa: F401
    except Exception as e:
        for lang in _LANG_SPEC:
            out[lang] = {"available": False,
                         "error": f"TREE_SITTER_CORE_MISSING: {type(e).__name__}"}
        return out

    from tree_sitter import Language, Parser
    for lang, (pkg, fn, ver) in _LANG_SPEC.items():
        try:
            mod = __import__(pkg)
            lang_obj = Language(getattr(mod, fn)())
            Parser(lang_obj)          # 确认可构建
            out[lang] = {"available": True, "grammar_package": pkg,
                         "grammar_function": fn, "grammar_version": ver,
                         "abi_version": getattr(lang_obj, "abi_version", None)}
        except Exception as e:
            out[lang] = {"available": False,
                         "error": f"GRAMMAR_LOAD_FAILED: {type(e).__name__}: {e}"}
    return out


def _under(path_value, path) -> bool:
    try:
        return str(path_value).startswith(str(path)) or str(path) in str(path_value)
    except Exception:
        return False


def get_parser(language):
    """返回 Parser。不可用则抛 RuntimeUnavailable。"""
    _ensure_site_packages()
    spec = _LANG_SPEC.get(language)
    if not spec:
        raise RuntimeUnavailable(PARSE_UNSUPPORTED_SYNTAX,
                                 f"未支持的语言 {language}")
    pkg, fn, ver = spec
    try:
        from tree_sitter import Language, Parser
        mod = __import__(pkg)
        return Parser(Language(getattr(mod, fn)()))
    except Exception as e:
        raise RuntimeUnavailable(PARSER_UNAVAILABLE,
                                 f"{pkg}.{fn}() 加载失败: {type(e).__name__}: {e}")


def parse_bytes(raw: bytes, language):
    """解析字节。返回 (tree, status, diagnostics)。

    ★ 必须显式检查 has_error / is_error / is_missing，不能因返回 tree 就当有效。
    """
    parser = get_parser(language)
    tree = parser.parse(raw)
    root = tree.root_node
    diags = {"has_error": bool(root.has_error),
             "error_nodes": 0, "missing_nodes": 0,
             "node_count": 0, "max_depth": 0}
    _scan(root, diags, depth=0)
    status = PARSE_WITH_ERRORS if diags["has_error"] else PARSE_COMPLETE
    return tree, status, diags


def _scan(node, diags, *, depth):
    stack = [(node, depth)]
    while stack:
        n, d = stack.pop()
        diags["node_count"] += 1
        if diags["node_count"] > MAX_NODES:
            diags["budget_exceeded"] = "MAX_NODES"
            return
        if d > MAX_DEPTH:
            diags["budget_exceeded"] = "MAX_DEPTH"
            return
        diags["max_depth"] = max(diags["max_depth"], d)
        if n.is_error:
            diags["error_nodes"] += 1
        if n.is_missing:
            diags["missing_nodes"] += 1
        for ch in n.children:
            stack.append((ch, d + 1))


def walk(node):
    """迭代式先序遍历（不递归，防爆栈）。"""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        for ch in reversed(n.children):
            stack.append(ch)


def node_range(node, starts, raw):
    """tree-sitter 的 start_byte/end_byte 已是**绝对字节偏移**。

    ★ 直接校验边界即可，不需要像 Python AST 那样换算 col_offset。
    但行号必须由字节偏移反查（tree-sitter 不给行号）。
    """
    from bisect import bisect_right
    sb, eb = node.start_byte, node.end_byte
    if sb < 0 or eb > len(raw) or eb < sb:
        return None
    sl = bisect_right(starts, sb)
    el = bisect_right(starts, eb)
    return sb, eb, max(1, sl), max(1, el)
