#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JS/TS 静态导入/导出规则。

★ 严格区分：ESM import 声明 / require 调用观察 / 动态说明符 / 导出类型。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import treesitter_runtime as RT

# 导入类型
IMP_DEFAULT = "default_import"
IMP_NAMED = "named_import"
IMP_NAMESPACE = "namespace_import"
IMP_SIDE_EFFECT = "side_effect_import"
IMP_REQUIRE_LITERAL = "require_literal_call"     # ★ 调用观察，非 ESM 声明
IMP_DYNAMIC = "dynamic_import"                   # import() 表达式

# 导出类型
EXP_NAMED = "named_export"
EXP_DEFAULT = "default_export"
EXP_DECLARATION = "export_declaration"
EXP_LIST = "export_list"
EXP_REEXPORT = "re_export"
EXP_ALL = "export_all"

# 说明符状态
SPEC_LITERAL = "LITERAL_MODULE_SPECIFIER"
SPEC_DYNAMIC = "DYNAMIC_MODULE_SPECIFIER"

IMPORT_STMT = "import_statement"
EXPORT_STMT = "export_statement"
CALL_EXPR = "call_expression"
STRING = "string"
TEMPLATE = "template_string"


def _text(node, raw):
    return raw[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _string_value(node, raw):
    """取字符串字面量内容（去引号）。非字面量返回 None。"""
    if node is None:
        return None
    if node.type != STRING:
        return None
    t = _text(node, raw).strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"":
        return t[1:-1]
    return t


def _field(node, name):
    try:
        return node.child_by_field_name(name)
    except Exception:
        return None


def collect_imports(root, raw, *, starts, language):
    """收集静态导入与 require/dynamic 观察。返回 (imports, diagnostics)。"""
    imports = []
    diags = {"dynamic_specifiers": 0}

    for node in RT.walk(root):
        if node.type == IMPORT_STMT:
            imports.extend(_parse_import(node, raw, starts))
        elif node.type == CALL_EXPR:
            imp = _parse_call_import(node, raw, starts)
            if imp:
                imports.append(imp)
                if imp["specifier_status"] == SPEC_DYNAMIC:
                    diags["dynamic_specifiers"] += 1
    return imports, diags


def _parse_import(node, raw, starts):
    """ES import 声明。"""
    out = []
    source = _field(node, "source")
    spec = _string_value(source, raw)
    rng = RT.node_range(node, starts, raw)
    if not rng:
        return out
    sb, eb, sl, el = rng

    # type-only：`import type { X } from "y"`
    txt = _text(node, raw)
    is_type_only = txt.lstrip().startswith("import type")

    has_clause = False
    for ch in node.children:
        if ch.type == "import_clause":
            has_clause = True
            for c2 in ch.children:
                if c2.type == "identifier":
                    # default import
                    out.append(_rec(IMP_DEFAULT, spec, _text(c2, raw), None,
                                    sb, eb, sl, el, is_type_only,
                                    SPEC_LITERAL))
                elif c2.type == "namespace_import":
                    nm = next((x for x in c2.children
                               if x.type == "identifier"), None)
                    out.append(_rec(IMP_NAMESPACE, spec,
                                    _text(nm, raw) if nm else None, None,
                                    sb, eb, sl, el, is_type_only,
                                    SPEC_LITERAL))
                elif c2.type == "named_imports":
                    for spec_node in c2.children:
                        if spec_node.type != "import_specifier":
                            continue
                        nm_node = _field(spec_node, "name")
                        al_node = _field(spec_node, "alias")
                        out.append(_rec(
                            IMP_NAMED, spec,
                            _text(nm_node, raw) if nm_node else None,
                            _text(al_node, raw) if al_node else None,
                            sb, eb, sl, el, is_type_only, SPEC_LITERAL))
    if not has_clause:
        # side-effect import：import "x"
        out.append(_rec(IMP_SIDE_EFFECT, spec, None, None,
                        sb, eb, sl, el, is_type_only, SPEC_LITERAL))
    return out


def _rec(kind, spec, name, alias, sb, eb, sl, el, type_only, spec_status,
         in_function=False, dynamic_call=False):
    return {
        "import_kind": kind,
        "module_specifier": spec,
        "imported_name": name,
        "alias": alias,
        "is_type_only": bool(type_only),
        "specifier_status": spec_status,
        "start_byte": sb, "end_byte": eb,
        "start_line": sl, "end_line": el,
        "in_function_scope": bool(in_function),
        "dynamic_call": bool(dynamic_call),
    }


def _parse_call_import(node, raw, starts):
    """require("x") / import("x") 调用观察。★ 非 ESM 声明。"""
    fn = _field(node, "function")
    if fn is None:
        return None
    args = _field(node, "arguments")
    callee = _text(fn, raw)

    if callee not in ("require", "import"):
        return None

    arg0 = None
    if args is not None:
        named = [c for c in args.children if c.is_named]
        if named:
            arg0 = named[0]

    spec = _string_value(arg0, raw)
    rng = RT.node_range(node, starts, raw)
    if not rng:
        return None
    sb, eb, sl, el = rng

    kind = IMP_REQUIRE_LITERAL if callee == "require" else IMP_DYNAMIC
    status = SPEC_LITERAL if spec else SPEC_DYNAMIC
    return _rec(kind, spec, None, None, sb, eb, sl, el, False, status,
                in_function=_in_function(node),
                dynamic_call=(spec is None))


def _in_function(node):
    p = node.parent
    d = 0
    while p is not None and d < 40:
        if p.type in ("function_declaration", "generator_function_declaration",
                      "method_definition", "arrow_function",
                      "function_expression", "function"):
            return True
        p = p.parent
        d += 1
    return False


def collect_exports(root, raw, *, starts, language):
    """收集导出声明。"""
    exports = []
    for node in RT.walk(root):
        if node.type != EXPORT_STMT:
            continue
        rng = RT.node_range(node, starts, raw)
        if not rng:
            continue
        sb, eb, sl, el = rng
        txt = _text(node, raw)
        head = txt[:40].split("{")[0] if "{" in txt else txt[:40]
        source = _field(node, "source")
        spec = _string_value(source, raw)
        is_type_only = head.lstrip().startswith("export type")

        decl = _field(node, "declaration")
        # 导出声明（export function f() / export class C / export interface I）
        if decl is not None:
            exports.append({
                "export_kind": EXP_DECLARATION,
                "exported_name": _decl_name(decl, raw),
                "source_reference": spec,
                "is_type_only": is_type_only or decl.type in (
                    "interface_declaration", "type_alias_declaration"),
                "declaration_node_type": decl.type,
                "start_byte": sb, "end_byte": eb,
                "start_line": sl, "end_line": el})

        if "default" in head:
            nm = _decl_name(decl, raw) if decl is not None else None
            exports.append({
                "export_kind": EXP_DEFAULT,
                "exported_name": nm,
                "anonymous": nm is None,
                "source_reference": spec,
                "is_type_only": is_type_only,
                "start_byte": sb, "end_byte": eb,
                "start_line": sl, "end_line": el})

        if "export" in txt and "*" in txt:
            exports.append({
                "export_kind": EXP_ALL,
                "exported_name": None,
                "source_reference": spec,
                "as_namespace": " as " in txt,
                "is_type_only": is_type_only,
                "start_byte": sb, "end_byte": eb,
                "start_line": sl, "end_line": el})

        # export { a, b } / export { a } from "./x"
        if "{" in txt:
            for ch in node.children:
                if ch.type == "export_clause":
                    for sp in ch.children:
                        if sp.type != "export_specifier":
                            continue
                        nm = _field(sp, "name")
                        al = _field(sp, "alias")
                        exports.append({
                            "export_kind": (EXP_REEXPORT if spec
                                            else EXP_LIST),
                            "exported_name": _text(al, raw) if al else (
                                _text(nm, raw) if nm else None),
                            "source_reference": spec,
                            "is_type_only": is_type_only,
                            "start_byte": sb, "end_byte": eb,
                            "start_line": sl, "end_line": el})
        if not decl and "{" not in txt and "*" not in txt and "default" not in head:
            exports.append({
                "export_kind": EXP_DECLARATION, "exported_name": None,
                "source_reference": spec, "is_type_only": is_type_only,
                "start_byte": sb, "end_byte": eb,
                "start_line": sl, "end_line": el})
    return exports


def _decl_name(decl, raw):
    for ch in decl.children:
        if ch.type in ("identifier", "type_identifier"):
            return _text(ch, raw)
    return None
