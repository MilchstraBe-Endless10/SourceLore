#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python AST 解析：符号声明 + 静态导入。

★ 只解析，绝不导入/执行被分析代码。用 ast.parse，绝不加载被分析模块。
"""

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import source_evidence as SE
import source_models as SM

PARSER_ID = "python-ast"
PARSER_VERSION = SM.PARSER_VERSION

_DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def parse_source(raw: bytes, *, repository_id, commit_sha, file_path,
                 git_blob_oid, content_asset_id, content_sha256,
                 provenance_level="SYNTHETIC_FIXTURE"):
    """解析真实字节。返回 observation（含 symbols/imports/evidence）。"""
    try:
        text, enc, had_bom = SE.decode_source(raw)
    except ValueError as e:
        msg = str(e)
        status = (SM.UNSUPPORTED_ENCODING if "UNSUPPORTED_ENCODING" in msg
                  else SM.BINARY_CONTENT)
        return SM.build_observation(
            repository_id=repository_id, commit_sha=commit_sha,
            file_path=file_path, git_blob_oid=git_blob_oid,
            content_asset_id=content_asset_id, content_sha256=content_sha256,
            parser_id=PARSER_ID, provenance_level=provenance_level,
            extraction_status=status, failure_reason=msg)

    starts, _lines = SE.line_starts_bytes(raw)
    try:
        tree = ast.parse(text, filename=file_path)
    except (SyntaxError, ValueError) as e:
        return SM.build_observation(
            repository_id=repository_id, commit_sha=commit_sha,
            file_path=file_path, git_blob_oid=git_blob_oid,
            content_asset_id=content_asset_id, content_sha256=content_sha256,
            parser_id=PARSER_ID, provenance_level=provenance_level,
            extraction_status=SM.PARSE_FAILED,
            failure_reason=f"{type(e).__name__}: {e}")

    obs_id = SM.make_observation_id(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, git_blob_oid=git_blob_oid,
        content_sha256=content_sha256, parser_id=PARSER_ID)

    symbols, imports, evs = [], [], []
    _walk(tree, scope=(), raw=raw, starts=starts, obs_id=obs_id,
          repository_id=repository_id, commit_sha=commit_sha,
          file_path=file_path, git_blob_oid=git_blob_oid,
          symbols=symbols, imports=imports, evs=evs, occurrence={})

    return SM.build_observation(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, git_blob_oid=git_blob_oid,
        content_asset_id=content_asset_id, content_sha256=content_sha256,
        parser_id=PARSER_ID, provenance_level=provenance_level,
        symbols=symbols, imports=imports, evidence_ranges=evs)


def _bump(occurrence, key):
    occurrence[key] = occurrence.get(key, 0) + 1
    return occurrence[key]


def _walk(node, *, scope, raw, starts, obs_id, repository_id, commit_sha,
          file_path, git_blob_oid, symbols, imports, evs, occurrence,
          scope_ctx=None):
    """递归遍历。scope = 外层 qualified name 元组。"""
    scope_ctx = scope_ctx or {}

    for child in ast.iter_child_nodes(node):
        if isinstance(child, _DEF_NODES):
            _handle_def(child, scope=scope, raw=raw, starts=starts,
                        obs_id=obs_id, repository_id=repository_id,
                        commit_sha=commit_sha, file_path=file_path,
                        git_blob_oid=git_blob_oid, symbols=symbols, evs=evs,
                        occurrence=occurrence, scope_ctx=scope_ctx)
            # 继续深入该定义的函数体，处理嵌套定义与内部导入
            inner_scope = scope + (child.name,)
            # ★ 必须显式记录父节点是否为类，方法/嵌套函数靠它区分
            inner_ctx = _ctx_of(child, scope_ctx,
                                parent_is_class=isinstance(child, ast.ClassDef))
            _walk(child, scope=inner_scope, raw=raw, starts=starts,
                  obs_id=obs_id, repository_id=repository_id,
                  commit_sha=commit_sha, file_path=file_path,
                  git_blob_oid=git_blob_oid, symbols=symbols, imports=imports,
                  evs=evs, occurrence=occurrence, scope_ctx=inner_ctx)
        elif isinstance(child, (ast.Import, ast.ImportFrom)):
            _handle_import(child, scope=scope, raw=raw, starts=starts,
                           obs_id=obs_id, file_path=file_path,
                           git_blob_oid=git_blob_oid, imports=imports,
                           evs=evs, occurrence=occurrence,
                           scope_ctx=scope_ctx)
            _walk(child, scope=scope, raw=raw, starts=starts, obs_id=obs_id,
                  repository_id=repository_id, commit_sha=commit_sha,
                  file_path=file_path, git_blob_oid=git_blob_oid,
                  symbols=symbols, imports=imports, evs=evs,
                  occurrence=occurrence, scope_ctx=scope_ctx)
        else:
            _walk(child, scope=scope, raw=raw, starts=starts, obs_id=obs_id,
                  repository_id=repository_id, commit_sha=commit_sha,
                  file_path=file_path, git_blob_oid=git_blob_oid,
                  symbols=symbols, imports=imports, evs=evs,
                  occurrence=occurrence, scope_ctx=scope_ctx)


def _decorators_of(node):
    """★ 读节点自身的装饰器（不是父节点的）。"""
    out = []
    for d in getattr(node, "decorator_list", []) or []:
        if isinstance(d, ast.Name):
            out.append(d.id)
        elif isinstance(d, ast.Attribute):
            out.append(d.attr)
        elif isinstance(d, ast.Call):
            f = d.func
            out.append(f.id if isinstance(f, ast.Name)
                       else (f.attr if isinstance(f, ast.Attribute) else "call"))
        else:
            out.append(type(d).__name__)
    return out


def _ctx_of(node, outer_ctx, *, parent_is_class=False):
    """判断该定义所处的语法语境（函数内 / 类内 / 条件内 / TYPE_CHECKING）。"""
    ctx = dict(outer_ctx)
    ctx["parent_is_class"] = parent_is_class
    ctx["is_async"] = isinstance(node, ast.AsyncFunctionDef)
    return ctx


def _handle_def(node, *, scope, raw, starts, obs_id, repository_id,
                commit_sha, file_path, git_blob_oid, symbols, evs,
                occurrence, scope_ctx):
    starts_b, _ = starts, None
    parent_is_class = bool(scope_ctx.get("parent_is_class"))
    if isinstance(node, ast.ClassDef):
        kind = SM.SYM_CLASS
    elif isinstance(node, ast.AsyncFunctionDef):
        # ★ 类体内 → 异步方法；其余（含嵌套）→ 异步函数
        kind = SM.SYM_ASYNC_METHOD if parent_is_class else SM.SYM_ASYNC_FUNCTION
    elif parent_is_class:
        kind = SM.SYM_METHOD
    elif scope:
        kind = SM.SYM_NESTED_FUNCTION
    else:
        kind = SM.SYM_FUNCTION

    qualified = ".".join(scope + (node.name,))
    sb, eb = SE.byte_range_of(node, starts, raw)
    sl, el = SE.line_range_of(node)
    occ = _bump(occurrence, (kind, qualified, sb))
    sid = SM.make_symbol_id(observation_id=obs_id,
                            qualified_name=qualified, kind=kind,
                            start_byte=sb, occurrence=occ)

    ev = SE.to_evidence_ref(kind=f"symbol:{kind}", start_byte=sb, end_byte=eb,
                            start_line=sl, end_line=el,
                            git_blob_oid=git_blob_oid, file_path=file_path,
                            raw=raw)
    evs.append(ev)
    symbols.append({
        "symbol_id": sid,
        "symbol_kind": kind,
        "symbol_name": node.name,
        "qualified_name": qualified,
        "containing_scope": ".".join(scope) if scope else None,
        "file_path": file_path,
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "git_blob_oid": git_blob_oid,
        "source_start_line": sl,
        "source_end_line": el,
        "source_start_byte": sb,
        "source_end_byte": eb,
        "parser_version": PARSER_VERSION,
        "evidence_ref": ev["label"],
        "decorators": _decorators_of(node),
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "has_type_annotations": _has_annotations(node),
    })


def _in_class(scope_ctx, node, scope):
    """判断父节点是否为 ClassDef。由 _walk 记录的 actual parent 决定。"""
    return scope_ctx.get("parent_is_class") is True


def _has_annotations(node) -> bool:
    args = getattr(node, "args", None)
    if args is not None:
        for a in list(getattr(args, "args", []) or []) + \
                list(getattr(args, "posonlyargs", []) or []) + \
                list(getattr(args, "kwonlyargs", []) or []):
            if getattr(a, "annotation", None) is not None:
                return True
        if getattr(args, "vararg", None) is not None and \
                args.vararg.annotation is not None:
            return True
        if getattr(args, "kwarg", None) is not None and \
                args.kwarg.annotation is not None:
            return True
    if getattr(node, "returns", None) is not None:
        return True
    for b in getattr(node, "body", []) or []:
        if isinstance(b, ast.AnnAssign):
            return True
    return False


def _handle_import(node, *, scope, raw, starts, obs_id, file_path,
                   git_blob_oid, imports, evs, occurrence, scope_ctx):
    sb, eb = SE.byte_range_of(node, starts, raw)
    sl, el = SE.line_range_of(node)
    scope_name = ".".join(scope) if scope else "module"

    if isinstance(node, ast.Import):
        items = [(a.name, None, a.asname, 0) for a in node.names]
        syntax = "import"
    else:
        syntax = "from_import"
        base = node.module or ""
        items = [(base, a.name, a.asname, node.level or 0)
                 for a in node.names]

    for module_name, imported_name, alias, level in items:
        occ = _bump(occurrence, ("import", scope_name, module_name,
                                 imported_name, sb))
        iid = SM.make_import_id(observation_id=obs_id,
                                module_name=module_name,
                                imported_name=imported_name, alias=alias,
                                relative_level=level, scope=scope_name,
                                start_byte=sb, occurrence=occ)
        ev = SE.to_evidence_ref(kind="import", start_byte=sb, end_byte=eb,
                                start_line=sl, end_line=el,
                                git_blob_oid=git_blob_oid,
                                file_path=file_path, raw=raw)
        evs.append(ev)
        imports.append({
            "import_id": iid,
            "import_syntax": syntax,
            "module_name": module_name,
            "imported_name": imported_name,
            "alias": alias,
            "relative_level": level,
            "source_scope": scope_name,
            "in_function_scope": bool(scope),
            "star_import": imported_name == "*",
            "source_start_line": sl,
            "source_end_line": el,
            "source_start_byte": sb,
            "source_end_byte": eb,
            "parser_version": PARSER_VERSION,
            "evidence_ref": ev["label"],
        })
