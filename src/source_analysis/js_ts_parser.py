#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JS/JSX/TS/TSX 统一解析入口。产出与 Python 同构的 Observation。

★ 语法错误时**不生成权威符号/导入事实**（MVP 安全准则）。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("source_analysis",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import source_evidence as SE
import source_models as SM
import treesitter_runtime as RT

PARSER_ID = "tree-sitter-js-ts"

GRAMMAR_VERSION = {
    "javascript": RT.JS_GRAMMAR_VERSION,
    "jsx": RT.JS_GRAMMAR_VERSION,
    "typescript": RT.TS_GRAMMAR_VERSION,
    "tsx": RT.TS_GRAMMAR_VERSION,
}


def parse_source(raw: bytes, *, repository_id, commit_sha, file_path,
                 git_blob_oid, content_asset_id, content_sha256,
                 provenance_level="SYNTHETIC_FIXTURE"):
    """解析 JS/TS 字节，返回 observation。"""
    language = RT.language_for_path(file_path)
    if not language:
        return _obs(repository_id, commit_sha, file_path, git_blob_oid,
                    content_asset_id, content_sha256, provenance_level,
                    language="unknown", status=RT.PARSE_UNSUPPORTED_SYNTAX,
                    reason=f"未支持的扩展名 {Path(file_path).suffix}")

    try:
        text, enc, had_bom = SE.decode_source(raw)
    except ValueError as e:
        msg = str(e)
        st = (SM.UNSUPPORTED_ENCODING if "UNSUPPORTED_ENCODING" in msg
              else SM.BINARY_CONTENT)
        return _obs(repository_id, commit_sha, file_path, git_blob_oid,
                    content_asset_id, content_sha256, provenance_level,
                    language=language, status=st, reason=msg)

    try:
        tree, status, diags = RT.parse_bytes(raw, language)
    except RT.RuntimeUnavailable as e:
        return _obs(repository_id, commit_sha, file_path, git_blob_oid,
                    content_asset_id, content_sha256, provenance_level,
                    language=language, status=e.reason, reason=e.detail)

    if diags.get("budget_exceeded"):
        return _obs(repository_id, commit_sha, file_path, git_blob_oid,
                    content_asset_id, content_sha256, provenance_level,
                    language=language, status=RT.SOURCE_INCOMPLETE,
                    reason=f"遍历预算超限: {diags['budget_exceeded']}")

    starts, _lines = SE.line_starts_bytes(raw)

    import js_ts_symbol_rules as SR
    import js_ts_import_export_rules as IR

    # ★ 语法错误时不产出权威结构
    if status != RT.PARSE_COMPLETE:
        return _obs(repository_id, commit_sha, file_path, git_blob_oid,
                    content_asset_id, content_sha256, provenance_level,
                    language=language, status=status,
                    reason=(f"语法错误: error_nodes={diags['error_nodes']} "
                            f"missing_nodes={diags['missing_nodes']}"),
                    diagnostics=diags)

    symbols, _exports, sdiags = SR.collect_symbols(
        tree.root_node, raw, starts=starts, language=language)
    imports, idiags = IR.collect_imports(
        tree.root_node, raw, starts=starts, language=language)
    exports = IR.collect_exports(
        tree.root_node, raw, starts=starts, language=language)

    obs_id = SM.make_observation_id(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, git_blob_oid=git_blob_oid,
        content_sha256=content_sha256, parser_id=PARSER_ID,
        parser_version=f"{PARSER_ID}/{GRAMMAR_VERSION[language]}")

    evs = []
    out_symbols = []
    _occ = {}
    for s in symbols:
        # ★ 生成确定性 symbol_id：同 qualified+kind 但位置不同 → 不同 ID
        key = (s["symbol_kind"], s["qualified_name"], s["start_byte"])
        _occ[key] = _occ.get(key, 0) + 1
        s["symbol_id"] = SM.make_symbol_id(
            observation_id=obs_id,
            qualified_name=s["qualified_name"], kind=s["symbol_kind"],
            start_byte=s["start_byte"], occurrence=_occ[key])
        ev = SE.to_evidence_ref(kind=f"symbol:{s['symbol_kind']}",
                                start_byte=s["start_byte"],
                                end_byte=s["end_byte"],
                                start_line=s["start_line"],
                                end_line=s["end_line"],
                                git_blob_oid=git_blob_oid,
                                file_path=file_path, raw=raw)
        evs.append(ev)
        out_symbols.append(dict(s, observation_id=obs_id,
                                evidence_ref=ev["label"], parser_id=PARSER_ID,
                                parser_version=GRAMMAR_VERSION[language]))

    out_imports = []
    _iocc = {}
    for i in imports:
        k2 = (i["import_kind"], i.get("module_specifier"),
              i.get("imported_name"), i["start_byte"])
        _iocc[k2] = _iocc.get(k2, 0) + 1
        i["import_id"] = SM.make_import_id(
            observation_id=obs_id, module_name=i.get("module_specifier") or "",
            imported_name=i.get("imported_name"), alias=i.get("alias"),
            relative_level=0, scope=i["import_kind"],
            start_byte=i["start_byte"], occurrence=_iocc[k2])
        ev = SE.to_evidence_ref(kind=f"import:{i['import_kind']}",
                                start_byte=i["start_byte"],
                                end_byte=i["end_byte"],
                                start_line=i["start_line"],
                                end_line=i["end_line"],
                                git_blob_oid=git_blob_oid,
                                file_path=file_path, raw=raw)
        evs.append(ev)
        out_imports.append(dict(i, observation_id=obs_id,
                                evidence_ref=ev["label"],
                                parser_id=PARSER_ID,
                                parser_version=GRAMMAR_VERSION[language]))

    out_exports = []
    for e in exports:
        e["export_id"] = "SL-EXP-" + __import__("hashlib").sha256(
            f"{obs_id}|{e['export_kind']}|{e.get('exported_name')}|"
            f"{e['start_byte']}".encode()).hexdigest()[:40]
        ev = SE.to_evidence_ref(kind=f"export:{e['export_kind']}",
                                start_byte=e["start_byte"],
                                end_byte=e["end_byte"],
                                start_line=e["start_line"],
                                end_line=e["end_line"],
                                git_blob_oid=git_blob_oid,
                                file_path=file_path, raw=raw)
        evs.append(ev)
        out_exports.append(dict(e, observation_id=obs_id,
                                evidence_ref=ev["label"],
                                parser_id=PARSER_ID,
                                parser_version=GRAMMAR_VERSION[language]))

    o = _obs(repository_id, commit_sha, file_path, git_blob_oid,
             content_asset_id, content_sha256, provenance_level,
             language=language, status=status,
             reason=None, diagnostics=diags)
    o.update({"observation_id": obs_id,
              "observed_symbols": out_symbols,
              "observed_imports": out_imports,
              "observed_exports": out_exports,
              "evidence_ranges": evs,
              "grammar_version": GRAMMAR_VERSION[language],
              "parser_id": PARSER_ID,
              "symbol_diags": sdiags, "import_diags": idiags})
    return o


def _obs(repository_id, commit_sha, file_path, git_blob_oid, content_asset_id,
         content_sha256, provenance_level, *, language, status, reason=None,
         diagnostics=None):
    base = SM.build_observation(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, git_blob_oid=git_blob_oid,
        content_asset_id=content_asset_id, content_sha256=content_sha256,
        parser_id=PARSER_ID, language=language,
        provenance_level=provenance_level,
        extraction_status=(SM.EXTRACTED if status == RT.PARSE_COMPLETE
                           else status),
        failure_reason=reason)
    base.update({"parse_status": status, "grammar_version":
                 GRAMMAR_VERSION.get(language),
                 "observed_exports": base.get("observed_exports") or [],
                 "diagnostics": diagnostics or {}})
    return base


def supports(path):
    return RT.language_for_path(path) is not None
