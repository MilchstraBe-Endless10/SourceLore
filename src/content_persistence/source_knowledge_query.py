#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码结构知识只读查询。★ 纯本地，零网络，不写库。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "content_persistence", "skill_interface"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

SOURCE_NOT_ANALYZED = "SOURCE_NOT_ANALYZED"
SOURCE_PARSE_FAILED = "SOURCE_PARSE_FAILED"
SYMBOL_NOT_REGISTERED = "SYMBOL_NOT_REGISTERED"
FOUND = "FOUND"


def query_source_facts(*, store, repository_id, commit_sha=None,
                       file_path=None, symbol_name=None, symbol_kind=None,
                       module_name=None, rule_id=None, limit=200):
    """按 repo/commit/path/符号名/类型/模块 查源码事实。"""
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    out = []
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("fact_type") != "source_structure_observation":
            continue
        np = pl.get("normalized_parameters") or {}
        subj = np.get("subject") or {}
        if commit_sha and pl.get("commit_sha") != str(commit_sha):
            continue
        if file_path and np.get("file_path") != file_path:
            continue
        if rule_id and pl.get("rule_id") != rule_id:
            continue
        if symbol_name and subj.get("symbol_name") != symbol_name \
                and subj.get("qualified_name") != symbol_name:
            continue
        if symbol_kind and subj.get("symbol_kind") != symbol_kind:
            continue
        if module_name and subj.get("module_name") != module_name \
                and subj.get("module_specifier") != module_name:
            continue
        out.append({
            "fact_id": pl.get("fact_id"),
            "asset_id": r["asset_id"],
            "rule_id": pl.get("rule_id"),
            "rule_version": pl.get("rule_version"),
            "repository_id": str(pl.get("repository_id") or repository_id),
            "commit_sha": pl.get("commit_sha"),
            "file_path": np.get("file_path"),
            "language": np.get("language"),
            "subject": dict(subj, **{
                # ★ 统一展示字段：Python 用 module_name，JS/TS 用 module_specifier
                "module_name": subj.get("module_name")
                or subj.get("module_specifier"),
            }),
            "git_blob_oid": np.get("git_blob_oid"),
            "content_asset_id": np.get("content_asset_id"),
            "content_sha256": np.get("content_sha256"),
            "parser_version": np.get("parser_version"),
            "start_byte": (np.get("byte_range") or [None, None])[0],
            "end_byte": (np.get("byte_range") or [None, None])[1],
            "start_line": (np.get("line_range") or [None, None])[0],
            "end_line": (np.get("line_range") or [None, None])[1],
            "observation_id": np.get("observation_id"),
            "evidence_label": np.get("evidence_label"),
            "provenance_level": (pl.get("observed_value") or {}).get(
                "provenance_level"),
            "completeness_status": pl.get("completeness_status"),
        })
        if len(out) >= limit:
            break
    return out


def source_query(*, repository_id, commit_sha=None, file_path=None,
                 symbol_name=None, symbol_kind=None, module_name=None,
                 rule_id=None, data_root=None, max_results=200):
    """正式入口。九态语义区分。"""
    from knowledge_store import KnowledgeStore
    from paths import db_path, DEFAULT_DATA_ROOT
    import blob_content_store as BS
    import captured_blob_loader as L

    root = data_root or DEFAULT_DATA_ROOT
    p = db_path(root)
    if not p.exists():
        return _shell(repository_id, commit_sha, file_path,
                      "REPOSITORY_NOT_REGISTERED", "知识库未建立")

    store = KnowledgeStore(str(p), create=False)
    try:
        rows = store.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE repository_id=?",
            (str(repository_id),)).fetchone()
        if not (rows["c"] or 0):
            return _shell(repository_id, commit_sha, file_path,
                          "REPOSITORY_NOT_REGISTERED", "该仓库从未登记")

        facts = query_source_facts(
            store=store, repository_id=repository_id, commit_sha=commit_sha,
            file_path=file_path, symbol_name=symbol_name,
            symbol_kind=symbol_kind, module_name=module_name, rule_id=rule_id,
            limit=max_results)

        captured = _captured(store, repository_id, commit_sha, file_path)
        avail = "NOT_CAPTURED"
        for c in captured:
            chk = L.load_captured_blob(store=store, data_root=root,
                                       repository_id=repository_id,
                                       commit_sha=c["commit_sha"],
                                       file_path=c["file_path"])
            c["verify_status"] = chk["status"]
            if chk["status"] == BS.AVAILABLE_VERIFIED:
                avail = "CAPTURED_VERIFIED"

        if not facts:
            state = (SOURCE_NOT_ANALYZED if avail == "CAPTURED_VERIFIED"
                     else "CONTENT_NOT_CAPTURED")
            out = _shell(repository_id, commit_sha, file_path, state,
                         "无源码结构事实")
            out["content_availability"] = avail
            out["captured"] = captured
            return out

        symbols = [f for f in facts if f["rule_id"] == "SOURCE_SYMBOL_DECLARED"]
        imports = [f for f in facts if f["rule_id"] == "SOURCE_IMPORT_DECLARED"]
        exports = [f for f in facts if f["rule_id"] == "SOURCE_EXPORT_DECLARED"]
        exports = _dedupe_exports(exports)

        return {
            "state": FOUND,
            "repository_id": str(repository_id),
            "commit_sha": commit_sha,
            "file_path": file_path,
            "content_availability": avail,
            "facts": facts,
            "symbols": symbols,
            "imports": imports,
            "exports": exports,
            "claims": _verdicts_block(store, repository_id, commit_sha,
                                      file_path, symbols, exports),
            "counts": {"facts": len(facts), "symbols": len(symbols),
                       "imports": len(imports), "exports": len(exports)},
            "captured": captured,
            "coverage_status": "COVERED_BY_EXTRACTED_SOURCE",
            "provenance_level": facts[0].get("provenance_level"),
            "limitations": [
                "只覆盖已抽取的源码文件",
                "静态声明 ≠ 运行时行为",
                "未实现调用图与数据流图",
                "文件路径匹配 ≠ 导入成功",
            ],
            "distribution_restrictions": {"distribution_allowed": False,
                                          "copy_permitted": False},
            "network_requests": 0,
        }
    finally:
        store.close()


def _shell(repository_id, commit_sha, file_path, state, note):
    return {"state": state, "note": note,
            "repository_id": str(repository_id), "commit_sha": commit_sha,
            "file_path": file_path, "facts": [], "symbols": [], "imports": [],
            "counts": {"facts": 0, "symbols": 0, "imports": 0},
            "captured": [], "content_availability": "UNKNOWN",
            "coverage_status": "NOT_COVERED", "provenance_level": None,
            "limitations": [note],
            "distribution_restrictions": {"distribution_allowed": False,
                                          "copy_permitted": False},
            "network_requests": 0}


def _captured(store, repository_id, commit_sha, file_path=None):
    import content_ingest_coordinator as CIC
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type=? AND repository_id=?",
        (CIC.ASSET_TYPE, str(repository_id))).fetchall()
    out = []
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if commit_sha and pl.get("commit_sha") != str(commit_sha):
            continue
        if file_path and pl.get("file_path") != file_path:
            continue
        out.append(pl)
    return out


def _load_verdicts(store, repository_id, commit_sha, file_path):
    """读回源码 Claim / Verification（只读，不写）。"""
    import json as _J
    # ★ D-66：按 asset_version 升序遍历，后写的覆盖前面的
    #   → 取到最新版本（v2 才带 normalized_parameters）。
    rows = store.conn.execute(
        "SELECT a.payload_json, i.asset_type, i.asset_version FROM index_rows i "
        "JOIN assets a USING(asset_id) "
        "WHERE i.repository_id=? AND i.commit_sha=? "
        "AND i.asset_type IN ('claim_candidate','claim_verification') "
        "ORDER BY i.asset_version ASC",
        (str(repository_id), str(commit_sha))).fetchall()
    claims, verifs = {}, {}
    for r in rows:
        try:
            d = _J.loads(r["payload_json"])
        except Exception:
            continue
        if r["asset_type"] == "claim_candidate":
            ct = d.get("claim_type") or ""
            if not ct.startswith("source_"):
                continue
            np_ = d.get("normalized_parameters") or {}
            if np_.get("file_path") != file_path:
                continue
            claims[(ct, _J.dumps(np_, sort_keys=True))] = d
        else:
            verifs[d.get("claim_id")] = d
    return claims, verifs


def _verdict_for(claims, verifs, claim_type, want):
    """按规范 subject 精确定位 claim / verification。"""
    for (ct, _), c in claims.items():
        if ct != claim_type:
            continue
        np_ = c.get("normalized_parameters") or {}
        if any(k in np_ and np_.get(k) != v for k, v in (want or {}).items()):
            continue
        v = verifs.get(c.get("claim_id")) or {}
        st = v.get("status")
        return {
            "claim_id": c.get("claim_id"),
            "verification_id": v.get("verification_id"),
            "verdict": st,
            "reason_code": v.get("reason_code"),
            "display_level": ("SUPPORTED_SOURCE_CLAIM" if st == "supported"
                              else "OBSERVED_SOURCE_FACT"),
        }
    return {"claim_id": None, "verification_id": None, "verdict": None,
            "reason_code": None,
            "display_level": "OBSERVED_SOURCE_FACT",
            "note": "尚未进行命题验证"}


def _verdicts_block(store, repository_id, commit_sha, file_path,
                    symbols, exports):
    """给每条事实挂裁决层级。

    ★ 没验证的必须标 OBSERVED_SOURCE_FACT，不得冒充 SUPPORTED_SOURCE_CLAIM。
    """
    claims, verifs = _load_verdicts(store, repository_id, commit_sha, file_path)
    out = []
    for f in symbols:
        sub = f.get("subject") or {}
        out.append({"fact_id": f.get("fact_id"), "kind": "symbol",
                    "start_line": f.get("start_line"),
                    "end_line": f.get("end_line"),
                    "subject": sub,
                    **_verdict_for(claims, verifs, "source_symbol_declared", {
                        "file_path": file_path,
                        "qualified_name": sub.get("qualified_name"),
                        "symbol_kind": sub.get("symbol_kind")})})
    for f in exports:
        sub = f.get("subject") or {}
        out.append({"fact_id": f.get("fact_id"), "kind": "export",
                    "start_line": f.get("start_line"),
                    "end_line": f.get("end_line"),
                    "subject": sub,
                    **_verdict_for(claims, verifs, "source_export_declared", {
                        "file_path": file_path,
                        "exported_name": sub.get("exported_name"),
                        "export_kind": sub.get("export_kind")})})
    return out



def _dedupe_exports(exports):
    """D-65：同一导出事件只保留信息最全的一条（只改视图，不改资产）。"""
    best = {}
    for e in exports:
        sub = e.get("subject") or (e.get("normalized_parameters") or {}).get("subject") or {}
        key = (sub.get("export_kind"), sub.get("exported_name"),
               e.get("start_byte"), e.get("end_byte"))
        prev = best.get(key)
        if prev is None:
            best[key] = e
            continue
        prev_has = bool((prev.get("subject") or {}).get("declaration_node_type"))
        cur_has = bool(sub.get("declaration_node_type"))
        if cur_has and not prev_has:
            best[key] = e
    return list(best.values())