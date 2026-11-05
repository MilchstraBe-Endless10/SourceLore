#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码结构观察模型。

★ AST 的 col_offset / end_col_offset 是 **UTF-8 字节偏移**（相对行首），
不是 Unicode 字符索引 —— 换算到整文件绝对字节偏移必须按行累加真实字节长度。
"""

import hashlib
import json

SCHEMA = "source-structure-observation/1"
PARSER_VERSION = "python-ast/1"

# 语言
LANG_PYTHON = "python"
LANG_JS = "javascript"
LANG_TS = "typescript"

# 解析状态
EXTRACTED = "EXTRACTED"
PARSE_FAILED = "PARSE_FAILED"
PARSER_UNAVAILABLE = "PARSER_UNAVAILABLE"
UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"
BINARY_CONTENT = "BINARY_CONTENT"

# 符号类型
SYM_MODULE = "module"
SYM_CLASS = "class"
SYM_FUNCTION = "function"
SYM_ASYNC_FUNCTION = "async_function"
SYM_METHOD = "method"
SYM_ASYNC_METHOD = "async_method"
SYM_NESTED_FUNCTION = "nested_function"

DECLARATION_SYMBOL_KINDS = frozenset({
    SYM_CLASS, SYM_FUNCTION, SYM_ASYNC_FUNCTION,
    SYM_METHOD, SYM_ASYNC_METHOD, SYM_NESTED_FUNCTION})

# 本地模块解析状态
RESOLVED = "LOCAL_MODULE_RESOLVED"
EXTERNAL = "EXTERNAL_OR_UNRESOLVED"
AMBIGUOUS = "AMBIGUOUS_CANDIDATES"
INSUFFICIENT_TREE = "INSUFFICIENT_TREE_COVERAGE"
UNSUPPORTED_FORM = "UNSUPPORTED_IMPORT_FORM"


def canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def make_observation_id(*, repository_id, commit_sha, file_path,
                        git_blob_oid, content_sha256, parser_id,
                        parser_version=PARSER_VERSION):
    """观察身份：稳定、确定性、可复算（不含时间）。"""
    payload = (f"{repository_id}|{commit_sha}|{file_path}|{git_blob_oid}|"
               f"{content_sha256}|{parser_id}|{parser_version}")
    return "SL-SOBS-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def make_symbol_id(*, observation_id, qualified_name, kind, start_byte,
                   occurrence):
    """★ 同一文件同名定义必须按"出现序号"区分，不得覆盖。"""
    payload = f"{observation_id}|{kind}|{qualified_name}|{start_byte}|{occurrence}"
    return "SL-SYM-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def make_import_id(*, observation_id, module_name, imported_name, alias,
                   relative_level, scope, start_byte, occurrence):
    payload = (f"{observation_id}|{module_name}|{imported_name}|{alias}|"
               f"{relative_level}|{scope}|{start_byte}|{occurrence}")
    return "SL-IMP-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def build_observation(*, repository_id, commit_sha, file_path, git_blob_oid,
                      content_asset_id, content_sha256, parser_id,
                      language=LANG_PYTHON, source_completeness="COMPLETE",
                      symbols=None, imports=None, evidence_ranges=None,
                      provenance_level="SYNTHETIC_FIXTURE",
                      extraction_status=EXTRACTED, failure_reason=None):
    return {
        "observation_schema": SCHEMA,
        "observation_id": make_observation_id(
            repository_id=repository_id, commit_sha=commit_sha,
            file_path=file_path, git_blob_oid=git_blob_oid,
            content_sha256=content_sha256, parser_id=parser_id,
            parser_version=PARSER_VERSION),
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "file_path": file_path,
        "git_blob_oid": git_blob_oid,
        "content_asset_id": content_asset_id,
        "content_sha256": content_sha256,
        "parser_id": parser_id,
        "parser_version": PARSER_VERSION,
        "language": language,
        "source_completeness": source_completeness,
        "observed_symbols": symbols or [],
        "observed_imports": imports or [],
        "evidence_ranges": evidence_ranges or [],
        "provenance_level": provenance_level,
        "extraction_status": extraction_status,
        "failure_reason": failure_reason,
    }
