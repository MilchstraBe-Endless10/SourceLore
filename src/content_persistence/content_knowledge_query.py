#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容知识只读查询。★ 纯本地，绝不联网、绝不写库。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "evidence_claims", "content", "skill_interface"):
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


# ═══════════════════════════════════════════════════════════════
# F2-P5F：正式查询入口（CLI 唯一调用点）
# ═══════════════════════════════════════════════════════════════

# 九态（语义不得合并）
REPOSITORY_NOT_REGISTERED = "REPOSITORY_NOT_REGISTERED"
COMMIT_NOT_REGISTERED = "COMMIT_NOT_REGISTERED"
CONTENT_INTEGRITY_FAILED = "CONTENT_INTEGRITY_FAILED"
SUPPORTED = "SUPPORTED"
REFUTED = "REFUTED"
RETRIEVAL_ERROR = "RETRIEVAL_ERROR"

MAX_RESULTS_DEFAULT = 100


def _repo_registered(store, repository_id):
    r = store.conn.execute(
        "SELECT count(*) c FROM index_rows WHERE repository_id=?",
        (str(repository_id),)).fetchone()
    return (r["c"] or 0) > 0


def _commit_registered(store, repository_id, commit_sha):
    r = store.conn.execute(
        "SELECT count(*) c FROM index_rows WHERE repository_id=? AND commit_sha=?",
        (str(repository_id), str(commit_sha))).fetchone()
    return (r["c"] or 0) > 0


def _snapshot_for(store, repository_id, commit_sha):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='repository_snapshot' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("commit_sha") == str(commit_sha):
            return r["asset_id"], pl
    return None, None


def content_query(*, repository_id, commit_sha, file_path=None,
                  fact_rule=None, claim_type=None, fact_id=None,
                  verification_id=None, max_results=MAX_RESULTS_DEFAULT,
                  data_root=None):
    """★ 正式查询入口。纯只读：不联网、不写库、不重新抽取、不推进指针。"""
    from knowledge_store import KnowledgeStore
    from paths import db_path, DEFAULT_DATA_ROOT
    import captured_blob_loader as L
    import blob_content_store as BS

    root = data_root or DEFAULT_DATA_ROOT
    p = db_path(root)
    if not p.exists():
        return _shell(repository_id, commit_sha, file_path,
                      REPOSITORY_NOT_REGISTERED, "知识库未建立")

    store = KnowledgeStore(str(p), create=False)
    try:
        if not _repo_registered(store, repository_id):
            return _shell(repository_id, commit_sha, file_path,
                          REPOSITORY_NOT_REGISTERED,
                          "该 repository_id 从未登记")

        snap_id, snap = _snapshot_for(store, repository_id, commit_sha)
        if snap is None and not _commit_registered(store, repository_id, commit_sha):
            return _shell(repository_id, commit_sha, file_path,
                          COMMIT_NOT_REGISTERED,
                          "该 Commit 从未登记")

        # 内容资产
        caps = _captured_for(store, repository_id, commit_sha, file_path)
        content_availability = "NOT_CAPTURED"
        integrity = None
        for c in caps:
            chk = L.load_captured_blob(store=store, data_root=root,
                                       repository_id=repository_id,
                                       commit_sha=c["commit_sha"],
                                       file_path=c["file_path"])
            c["verify_status"] = chk["status"]
            if chk["status"] == BS.AVAILABLE_VERIFIED:
                content_availability = "CAPTURED_VERIFIED"
            elif chk["status"] == BS.INTEGRITY_FAILED:
                integrity = BS.INTEGRITY_FAILED
        if integrity:
            content_availability = "INTEGRITY_FAILED"

        facts = query_content_facts(store=store, repository_id=repository_id,
                                    commit_sha=commit_sha, file_path=file_path,
                                    rule_id=fact_rule, limit=max_results)
        if fact_id:
            facts = [f for f in facts if f["fact_id"] == fact_id]

        if not facts:
            state = (CONTENT_NOT_CAPTURED if content_availability == "NOT_CAPTURED"
                     else FACT_NOT_REGISTERED)
            out = _shell(repository_id, commit_sha, file_path, state,
                         "无内容事实" if state == FACT_NOT_REGISTERED
                         else "未捕获内容字节")
            out["content_availability"] = content_availability
            out["captured"] = caps
            return out

        claims = _claims_for(store, repository_id, commit_sha,
                             file_path=file_path, claim_type=claim_type)
        verifs = _verifications_for(store, claims, facts,
                                    verification_id=verification_id)

        state = SUPPORTED if any(v.get("status") == "supported" for v in verifs) \
            else (REFUTED if any(v.get("status") == "refuted" for v in verifs)
                  else "INSUFFICIENT_EVIDENCE")

        return {
            "state": state,
            "repository_id": str(repository_id),
            "commit_sha": str(commit_sha),
            "file_path": file_path,
            "content_availability": content_availability,
            "facts": facts,
            "claims": claims,
            "verifications": verifs,
            "captured": caps,
            "source_snapshot_id": snap_id,
            "coverage_status": "COVERED_BY_EXTRACTED_CONTENT",
            "provenance_level": (facts[0].get("provenance_level")
                                 if facts else None),
            "review_status": "PENDING_REVIEW",
            "freshness_state": "OBSERVED_AT_COMMIT",
            "limitations": ["只覆盖已抽取的文件内容",
                            "未抽取内容不得推断为不存在"],
            "distribution_restrictions": {"distribution_allowed": False,
                                          "copy_permitted": False,
                                          "note": "B-1/B-2/B-3 OPEN"},
            "network_requests": 0,
        }
    finally:
        store.close()


def _shell(repository_id, commit_sha, file_path, state, note):
    return {"state": state, "note": note,
            "repository_id": str(repository_id), "commit_sha": str(commit_sha),
            "file_path": file_path, "facts": [], "claims": [],
            "verifications": [], "captured": [],
            "content_availability": "UNKNOWN",
            "coverage_status": "NOT_COVERED",
            "provenance_level": None, "review_status": "PENDING_REVIEW",
            "freshness_state": "UNKNOWN",
            "limitations": [note],
            "distribution_restrictions": {"distribution_allowed": False,
                                          "copy_permitted": False},
            "network_requests": 0}


def _captured_for(store, repository_id, commit_sha, file_path=None):
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


def _claims_for(store, repository_id, commit_sha, file_path=None, claim_type=None):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='claim_candidate' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    out = []
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("commit_sha") != str(commit_sha):
            continue
        if file_path and pl.get("normalized_path") != file_path:
            continue
        if claim_type and pl.get("claim_type") != claim_type:
            continue
        out.append(pl)
    return out


def _verifications_for(store, claims, facts, verification_id=None):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='claim_verification'"
    ).fetchall()
    fact_ids = {f["fact_id"] for f in facts}
    out = []
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if verification_id and pl.get("verification_id") != verification_id:
            continue
        claimed = set(pl.get("supporting_fact_ids") or [])
        if fact_ids & claimed or not claimed:
            out.append(pl)
    return out


def content_knowledge_summary(*, repository_id, commit_sha=None, data_root=None):
    """仓库内容知识概览。★ 计数口径分离：文件条目 / 唯一 Blob / 资产 / Fact。"""
    import content_ingest_coordinator as CIC
    from knowledge_store import KnowledgeStore
    from paths import db_path, DEFAULT_DATA_ROOT

    root = data_root or DEFAULT_DATA_ROOT
    p = db_path(root)
    if not p.exists():
        return {"state": REPOSITORY_NOT_REGISTERED,
                "repository_id": str(repository_id),
                "note": "知识库未建立"}
    store = KnowledgeStore(str(p), create=False)
    try:
        if not _repo_registered(store, repository_id):
            return {"state": REPOSITORY_NOT_REGISTERED,
                    "repository_id": str(repository_id)}

        caps = _captured_for(store, repository_id, commit_sha)
        facts = query_content_facts(store=store, repository_id=repository_id,
                                    commit_sha=commit_sha)
        claims = _claims_for(store, repository_id, commit_sha) \
            if commit_sha else _claims_for_all(store, repository_id)
        verifs = _verifications_for(store, claims, facts)

        # ★ 三种计数严格分开
        file_entries = len(caps)                       # 文件条目
        unique_blobs = len({c.get("git_blob_oid") for c in caps})   # 唯一 Blob
        content_assets = len({c.get("content_asset_id") for c in caps})
        parsed_files = len({f["file_path"] for f in facts})          # 已解析文件

        by_status = {}
        for v in verifs:
            by_status[v.get("status")] = by_status.get(v.get("status"), 0) + 1

        rules = {}
        for f in facts:
            rules[f["rule_id"]] = rules.get(f["rule_id"], 0) + 1

        return {
            "state": FOUND if facts else (
                FACT_NOT_REGISTERED if caps else CONTENT_NOT_CAPTURED),
            "repository_id": str(repository_id),
            "commit_sha": commit_sha,
            "counts": {
                "file_entries": file_entries,
                "unique_blobs": unique_blobs,
                "content_assets": content_assets,
                "parsed_files": parsed_files,
                "observations": len({f["observation_id"] for f in facts}),
                "facts": len(facts),
                "claims": len(claims),
                "verifications": len(verifs),
            },
            "by_rules": rules,
            "verification_status": by_status,
            "readme_headings": rules.get("README_HEADING_EXISTS", 0),
            "manifest_dependencies": rules.get("MANIFEST_DEPENDENCY_DECLARED", 0),
            "content_missing": max(0, file_entries - parsed_files),
            "parse_errors": 0,
            "shared_blobs": _shared_blob_report(caps),
            "distribution_restrictions": {"distribution_allowed": False,
                                          "copy_permitted": False,
                                          "note": "B-1/B-2/B-3 OPEN"},
            "network_requests": 0,
        }
    finally:
        store.close()


def _claims_for_all(store, repository_id):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='claim_candidate' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    out = []
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if got.get("ok"):
            out.append((got["asset"] or {}).get("payload") or {})
    return out


def _shared_blob_report(caps):
    """同一 Blob 在多个路径/Commit 复用 → 共享内容 + 独立来源。"""
    seen = {}
    for c in caps:
        oid = c.get("git_blob_oid")
        seen.setdefault(oid, []).append({
            "file_path": c.get("file_path"),
            "commit_sha": c.get("commit_sha"),
            "content_asset_id": c.get("content_asset_id")})
    shared = {k: v for k, v in seen.items() if len(v) > 1}
    return {"shared_blob_count": len(shared),
            "shared": [{"git_blob_oid": k, "bindings": v}
                       for k, v in shared.items()]}
