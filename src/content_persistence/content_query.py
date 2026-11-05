#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容知识只读查询。★ 纯本地，绝不联网、绝不写库。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "evidence_claims", "content"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

# 三态明确区分
CONTENT_NOT_CAPTURED = "CONTENT_NOT_CAPTURED"
FACT_NOT_REGISTERED = "FACT_NOT_REGISTERED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
FOUND = "FOUND"


def query_content_facts(*, store, repository_id, commit_sha=None,
                        file_path=None, rule_id=None, limit=200):
    """按 repo/commit/path/rule 查内容事实。"""
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    out = []
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("fact_type") != "content_observation":
            continue
        np = pl.get("normalized_parameters") or {}
        if commit_sha and pl.get("commit_sha") != str(commit_sha):
            continue
        if file_path and np.get("file_path") != file_path:
            continue
        if rule_id and pl.get("rule_id") != rule_id:
            continue
        out.append({
            "fact_id": pl.get("fact_id"),
            "asset_id": r["asset_id"],
            "rule_id": pl.get("rule_id"),
            "rule_version": pl.get("rule_version"),
            "commit_sha": pl.get("commit_sha"),
            "file_path": np.get("file_path"),
            "subject": np.get("subject"),
            "git_blob_oid": np.get("git_blob_oid"),
            "content_asset_id": np.get("content_asset_id"),
            "content_sha256": np.get("content_sha256"),
            "parser_version": np.get("parser_version"),
            "start_byte": np.get("byte_range", [None, None])[0],
            "end_byte": np.get("byte_range", [None, None])[1],
            "start_line": np.get("line_range", [None, None])[0],
            "end_line": np.get("line_range", [None, None])[1],
            "observation_id": np.get("observation_id"),
            "provenance_level": (pl.get("observed_value") or {}).get("provenance_level"),
            "evidence_refs": pl.get("evidence_refs"),
            "completeness_status": pl.get("completeness_status"),
        })
        if len(out) >= limit:
            break
    return out


def content_summary(*, store, repository_id, commit_sha=None):
    """内容概览：区分「没有内容」与「有内容但无事实」。"""
    import content_ingest_coordinator as CIC
    import captured_blob_loader as L
    from paths import DEFAULT_DATA_ROOT

    caps = []
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type=? AND repository_id=?",
        (CIC.ASSET_TYPE, str(repository_id))).fetchall()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if commit_sha and pl.get("commit_sha") != str(commit_sha):
            continue
        chk = L.load_captured_blob(
            store=store, data_root=DEFAULT_DATA_ROOT,
            repository_id=repository_id, commit_sha=pl.get("commit_sha"),
            file_path=pl.get("file_path"))
        caps.append({"file_path": pl.get("file_path"),
                     "commit_sha": pl.get("commit_sha"),
                     "content_asset_id": pl.get("content_asset_id"),
                     "git_blob_oid": pl.get("git_blob_oid"),
                     "byte_length": pl.get("raw_byte_length"),
                     "verify_status": chk["status"],
                     "provenance_level": pl.get("provenance_level"),
                     "acquisition_policy": pl.get("acquisition_policy"),
                     "distribution_allowed": pl.get("distribution_allowed", False)})

    facts = query_content_facts(store=store, repository_id=repository_id,
                                commit_sha=commit_sha)
    if not caps:
        state = CONTENT_NOT_CAPTURED
        note = "本地未捕获任何内容字节（需显式 analyze --include-content）"
    elif not facts:
        state = FACT_NOT_REGISTERED
        note = "有内容字节但尚无内容事实登记"
    else:
        state = FOUND
        note = "ok"
    return {"state": state, "note": note, "captured": caps,
            "facts_count": len(facts), "facts": facts,
            "distribution_allowed": False, "copy_permitted": False,
            "network_requests": 0}
