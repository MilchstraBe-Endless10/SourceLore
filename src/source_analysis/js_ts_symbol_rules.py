#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JS/TS 符号规则：把 tree-sitter 节点映射为结构化符号。

★ 严格区分声明 / 表达式 / 变量绑定 / 类方法 / 对象方法 / 匿名函数。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import treesitter_runtime as RT

# 符号类型
JS_FUNCTION = "js_function"                  # function 声明
JS_ASYNC_FUNCTION = "js_async_function"
JS_GENERATOR_FUNCTION = "js_generator_function"
JS_CLASS = "js_class"
JS_METHOD = "js_method"
JS_OBJECT_METHOD = "js_object_method"
JS_VARIABLE = "js_variable"                  # 普通变量绑定
JS_ARROW_FUNCTION = "js_arrow_function"      # 箭头函数（绑定在变量上）
JS_FUNCTION_EXPRESSION = "js_function_expression"
JS_ANONYMOUS_FUNCTION = "js_anonymous_function"

TS_INTERFACE = "ts_interface"
TS_TYPE_ALIAS = "ts_type_alias"
TS_ENUM = "ts_enum"
TS_NAMESPACE = "ts_namespace"
TS_TYPE_PARAMETER = "ts_type_parameter"

DECLARATION_KINDS = frozenset({
    JS_FUNCTION, JS_ASYNC_FUNCTION, JS_GENERATOR_FUNCTION, JS_CLASS,
    JS_METHOD, JS_OBJECT_METHOD, JS_VARIABLE, JS_ARROW_FUNCTION,
    JS_FUNCTION_EXPRESSION, JS_ANONYMOUS_FUNCTION,
    TS_INTERFACE, TS_TYPE_ALIAS, TS_ENUM, TS_NAMESPACE})

# tree-sitter 节点类型 → 处理方式
FUNC_DECL = "function_declaration"
GEN_FUNC_DECL = "generator_function_declaration"
CLASS_DECL = "class_declaration"
LEXICAL_DECL = "lexical_declaration"
VAR_DECL = "variable_declaration"
METHOD_DEF = "method_definition"
PAIR = "pair"
IFACE_DECL = "interface_declaration"
TYPE_ALIAS = "type_alias_declaration"
ENUM_DECL = "enum_declaration"
MODULE_DECL = "module"           # TS namespace / module
INTERNAL_MODULE = "internal_module"
CLASS_BODY = "class_body"
OBJECT = "object"
ARROW = "arrow_function"
FUNC_EXPR = "function_expression"
FUNC = "function"                # function expression in expression context
FORMAL_PARAMS = "formal_parameters"


def _text(node, raw) -> str:
    return raw[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _ident_child(node, raw):
    """取声明节点的名字（identifier / property_identifier / type_identifier）。"""
    for ch in node.children:
        if ch.type in ("identifier", "property_identifier",
                       "type_identifier", "statement_identifier"):
            return _text(ch, raw)
    return None


def _child_by_field(node, field):
    try:
        return node.child_by_field_name(field)
    except Exception:
        return None


def _has_async(node, raw) -> bool:
    return _text(node, raw).lstrip().startswith("async") or any(
        ch.type == "async" for ch in node.children)


def _has_generator(node, raw) -> bool:
    """`function*` / `function *` 形式。"""
    head = _text(node, raw)[:40]
    return ("*" in head.split("(")[0]) if "(" in head else False


def _is_value_arrow(value_node) -> bool:
    return value_node is not None and value_node.type == ARROW


def _is_value_function_expr(value_node) -> bool:
    return value_node is not None and value_node.type in (FUNC_EXPR, FUNC)


def collect_symbols(root, raw, *, starts, language):
    """返回 (symbols, exports, diagnostics)。"""
    symbols, exports = [], []
    _seen = set()
    diags = {"skipped_budget": 0}

    # 先收集顶层导出意图（供其它模块引用）
    exports = _collect_exports(root, raw)

    count = 0
    for node in RT.walk(root):
        count += 1
        if count > RT.MAX_NODES:
            diags["skipped_budget"] = RT.MAX_NODES
            break
        kind, name, qual, extra = _classify(node, raw, root)
        if not kind:
            continue
        rng = RT.node_range(node, starts, raw)
        if not rng:
            continue
        sb, eb, sl, el = rng
        # ★ 同一节点可能被多次命中（如 lexical_declaration 内层再遍历一次）
        seen_key = (kind, name, sb)
        if seen_key in _seen:
            continue
        _seen.add(seen_key)
        symbols.append({
            "symbol_kind": kind,
            "symbol_name": name,
            "qualified_name": qual,
            "start_byte": sb, "end_byte": eb,
            "start_line": sl, "end_line": el,
            "node_type": node.type,
            "language": language,
            **extra,
        })
    return symbols, exports, diags


def _parent_chain(node):
    """tree-sitter 节点有 parent 指针；构造外层名字链。"""
    chain = []
    p = node.parent
    depth = 0
    while p is not None and depth < 64:
        if p.type in (CLASS_DECL, FUNC_DECL, IFACE_DECL, MODULE_DECL,
                      INTERNAL_MODULE):
            nm = _ident_child(p, b"") or None
            if nm:
                chain.append(nm)
        elif p.type in (LEXICAL_DECL, VAR_DECL):
            v = _first_variable_name(p, b"")
            if v:
                chain.append(v)
        p = p.parent
        depth += 1
    return list(reversed(chain))


def _first_variable_name(decl_node, raw):
    for n in RT.walk(decl_node):
        if n.type == "variable_declarator":
            nm = _ident_child(n, raw)
            if nm:
                return nm
            break
    return None


def _classify(node, raw, root):
    """判断该节点是否构成一个符号声明。返回 (kind, name, qualified, extra)。"""
    t = node.type
    parent = node.parent

    # ── 函数/类/接口/类型/枚举/命名空间声明 ──
    if t in (FUNC_DECL, GEN_FUNC_DECL):
        nm = _ident_child(node, raw)
        if not nm:
            return None, None, None, {}
        # ★ tree-sitter 用独立节点类型区分 generator，不能只看 `*`
        is_gen = t == GEN_FUNC_DECL or _has_generator(node, raw)
        if is_gen:
            k = JS_GENERATOR_FUNCTION
        elif _has_async(node, raw):
            k = JS_ASYNC_FUNCTION
        else:
            k = JS_FUNCTION
        return k, nm, _qual(node, nm, raw, parent), {
            "is_async": _has_async(node, raw),
            "is_generator": is_gen,
        }

    if t == CLASS_DECL:
        nm = _ident_child(node, raw)
        if not nm:
            return None, None, None, {}
        return JS_CLASS, nm, _qual(node, nm, raw, parent), {}

    if t in (IFACE_DECL, TYPE_ALIAS, ENUM_DECL):
        nm = _ident_child(node, raw)
        if not nm:
            return None, None, None, {}
        k = {IFACE_DECL: TS_INTERFACE, TYPE_ALIAS: TS_TYPE_ALIAS,
             ENUM_DECL: TS_ENUM}[t]
        return k, nm, _qual(node, nm, raw, parent), {"type_only": False,
                                                     "declaration_only": True}

    if t in (MODULE_DECL, INTERNAL_MODULE):
        nm = _ident_child(node, raw) or None
        if not nm:
            return None, None, None, {}
        return TS_NAMESPACE, nm, _qual(node, nm, raw, parent), {}

    # ── 方法与对象方法（tree-sitter 都产出 method_definition）──
    if t == METHOD_DEF:
        nm = _ident_child(node, raw)
        if not nm:
            return None, None, None, {}
        if parent is not None and parent.type == CLASS_BODY:
            cls = _nearest_class_name(parent, raw)
            qual = f"{cls}.{nm}" if cls else nm
            return JS_METHOD, nm, qual, {
                "is_async": _has_async(node, raw),
                "is_generator": _has_generator(node, raw),
                "containing_class": cls,
            }
        if parent is not None and parent.type == OBJECT:
            owner = _object_owner(parent, raw)
            qual = f"{owner}.{nm}" if owner else nm
            return JS_OBJECT_METHOD, nm, qual, {
                "object_property": True,
                "containing_object": owner,
            }
        return None, None, None, {}

    # ── 变量声明（区分 arrow / function expression / 普通变量）──
    if t == LEXICAL_DECL or t == VAR_DECL:
        for decl in RT.walk(node):
            if decl.type != "variable_declarator":
                continue
            nm = _ident_child(decl, raw)
            if not nm:
                continue
            value = _child_by_field(decl, "value")
            if _is_value_arrow(value):
                k = JS_ARROW_FUNCTION
                extra = {"binding_kind": "variable", "value_kind": "arrow"}
            elif _is_value_function_expr(value):
                k = JS_FUNCTION_EXPRESSION
                extra = {"binding_kind": "variable",
                         "value_kind": value.type}
            else:
                k = JS_VARIABLE
                extra = {"binding_kind": "variable", "value_kind": None}
            return k, nm, _qual_decl(decl, nm, raw), extra
        return None, None, None, {}

    # ── 对象字面量方法 ──
    if t == PAIR and parent is not None and parent.type == OBJECT:
        key = _child_by_field(node, "key")
        value = _child_by_field(node, "value")
        if key is None or value is None:
            return None, None, None, {}
        if value.type in (FUNC_EXPR, FUNC, ARROW, METHOD_DEF):
            nm = _text(key, raw).strip("'\"")
            return JS_OBJECT_METHOD, nm, _qual(node, nm, raw, parent), {
                "object_property": True, "value_kind": value.type}
        return None, None, None, {}

    return None, None, None, {}


def _object_owner(object_node, raw):
    """对象字面量所属变量名（供限定名）；找不到返回 None。"""
    p = object_node.parent
    if p is not None and p.type == "variable_declarator":
        return _ident_child(p, raw)
    if p is not None and p.type == "pair":
        key = _child_by_field(p, "key")
        return _text(key, raw).strip("'\"") if key is not None else None
    return None


def _nearest_class_name(class_body, raw):
    p = class_body.parent
    if p is not None and p.type == CLASS_DECL:
        return _ident_child(p, raw)
    return None


def _qual(node, name, raw, parent):
    prefix = _scope_prefix(parent, raw)
    return f"{prefix}.{name}" if prefix else name


def _qual_decl(decl, name, raw):
    """变量声明的限定名：从 declarator 的**父节点**的父节点开始算，
    跳过 lexical_declaration 自身（否则会得到 name.name）。"""
    p = decl.parent            # lexical_declaration
    p = p.parent if p is not None else None
    prefix = _scope_prefix(p, raw)
    return f"{prefix}.{name}" if prefix else name


def _scope_prefix(node, raw, depth=0):
    """按语法作用域构造前缀。★ 不靠字符串相似性。"""
    if node is None or depth > 32:
        return ""
    t = node.type
    if t in (CLASS_DECL, FUNC_DECL, IFACE_DECL):
        nm = _ident_child(node, raw)
        if nm:
            return nm
        return ""
    if t in (MODULE_DECL, INTERNAL_MODULE):
        nm = _ident_child(node, raw)
        return nm or ""
    if t in (LEXICAL_DECL, VAR_DECL):
        # ★ 变量声明作为"前缀"没有意义（会得到 name.name）；
        #   继续向外找真正的语法作用域。
        return _scope_prefix(node.parent, raw, depth + 1)
    if t in ("statement_block", "program", "export_statement"):
        return _scope_prefix(node.parent, raw, depth + 1)
    return _scope_prefix(node.parent, raw, depth + 1)


def _collect_exports(root, raw):
    """收集顶层 export 声明（供 Export 规则使用）。"""
    out = []
    for node in RT.walk(root):
        if node.type == "export_statement":
            txt = _text(node, raw)[:60]
            kind = "named"
            if "default" in txt.split("{")[0]:
                kind = "default"
            if node.child_by_field_name("source"):
                kind = "re-export"
            if "export *" in txt:
                kind = "export_all"
            out.append({"node_type": node.type, "kind": kind,
                        "start_byte": node.start_byte,
                        "end_byte": node.end_byte})
    return out
