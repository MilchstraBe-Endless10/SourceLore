#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码解析分派：按扩展名选 Python AST 或 tree-sitter。

★ 单一入口，避免调用方各自猜语言。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

PY_EXTS = (".py",)


def pick_parser(path):
    """返回 'python' / 'js-ts' / None。"""
    ext = Path(path).suffix.lower()
    if ext in PY_EXTS:
        return "python"
    import treesitter_runtime as RT
    if RT.language_for_path(path):
        return "js-ts"
    return None


def parse_source(raw, *, repository_id, commit_sha, file_path,
                 git_blob_oid, content_asset_id, content_sha256,
                 provenance_level="SYNTHETIC_FIXTURE"):
    kind = pick_parser(file_path)
    if kind == "python":
        import python_ast_parser as PP
        return PP.parse_source(
            raw, repository_id=repository_id, commit_sha=commit_sha,
            file_path=file_path, git_blob_oid=git_blob_oid,
            content_asset_id=content_asset_id,
            content_sha256=content_sha256,
            provenance_level=provenance_level)
    if kind == "js-ts":
        import js_ts_parser as JP
        return JP.parse_source(
            raw, repository_id=repository_id, commit_sha=commit_sha,
            file_path=file_path, git_blob_oid=git_blob_oid,
            content_asset_id=content_asset_id,
            content_sha256=content_sha256,
            provenance_level=provenance_level)
    import source_models as SM
    return SM.build_observation(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, git_blob_oid=git_blob_oid,
        content_asset_id=content_asset_id, content_sha256=content_sha256,
        parser_id="none", provenance_level=provenance_level,
        extraction_status=SM.PARSER_UNAVAILABLE,
        failure_reason=f"未支持的扩展名 {file_path}")
