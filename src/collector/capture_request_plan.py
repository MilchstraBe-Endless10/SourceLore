#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集缺口盘点 + 请求计划。★ 只读：不联网、不写资产、不改 A/B 层。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("collector", "storage", "runtime", "content", "content_persistence",
           "source_analysis", "facts", "evidence_claims"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

# ── 对象状态（必须分开，不能合并成 CACHE_HIT） ────────────────
METADATA_AVAILABLE = "METADATA_AVAILABLE"
CONTENT_NOT_CAPTURED = "CONTENT_NOT_CAPTURED"
CONTENT_AVAILABLE_VERIFIED = "CONTENT_CAPTURED_VERIFIED"
CONTENT_CAPTURED_BUT_NOT_PARSED = "CONTENT_CAPTURED_BUT_NOT_PARSED"
FACTS_PERSISTED = "FACTS_PERSISTED"
CLAIMS_VERIFIED = "CLAIMS_VERIFIED"
KNOWLEDGE_QUERYABLE = "KNOWLEDGE_QUERYABLE"
POLICY_BLOCKED = "POLICY_BLOCKED"
BLOB_TOO_LARGE = "BLOB_TOO_LARGE"
OID_UNAVAILABLE = "OID_UNAVAILABLE"
PARSER_UNSUPPORTED = "PARSER_UNSUPPORTED"

# 采集任务状态
CAPTURE_COMPLETE = "CAPTURE_COMPLETE"
CAPTURE_PARTIAL_RATE_LIMITED = "CAPTURE_PARTIAL_RATE_LIMITED"
CAPTURE_PARTIAL_BUDGET = "CAPTURE_PARTIAL_BUDGET"
CAPTURE_PARTIAL_POLICY_BLOCKED = "CAPTURE_PARTIAL_POLICY_BLOCKED"
CAPTURE_PARTIAL_CONTENT_MISSING = "CAPTURE_PARTIAL_CONTENT_MISSING"
CAPTURE_INTEGRITY_FAILED = "CAPTURE_INTEGRITY_FAILED"
CAPTURE_NOT_APPLICABLE = "CAPTURE_NOT_APPLICABLE"

# 可选内容范围：只挑本轮要采的文件
DEFAULT_CONTENT_SCOPE = ("README.md", "package.json", "index.js")


def _is_source(path):
    return path.endswith((".js", ".jsx", ".ts", ".tsx", ".py"))


def build_gap_inventory(*, store, repository_id, commit_sha,
                        content_scope=None):
    """★ 只读盘点。返回每个对象的真实状态。

    判定顺序：树条目 → 内容资产 → 解析事实 → 命题/裁决。
    """
    import content_ingest_coordinator as CIC
    import content_knowledge_query as CKQ
    import source_knowledge_query as SKQ

    scope = tuple(content_scope or DEFAULT_CONTENT_SCOPE)
    snap = _load_snapshot(store, repository_id, commit_sha)
    if snap is None:
        return {"ok": False, "error": "SNAPSHOT_NOT_FOUND",
                "repository_id": str(repository_id),
                "commit_sha": str(commit_sha)}

    entries = snap.get("tree_entries") or []
    by_path = {e["path"]: e for e in entries}
    snap_id = snap.get("_snapshot_asset_id")

    objects = []
    for path in scope:
        entry = by_path.get(path)
        rec = {
            "repository_id": str(repository_id),
            "commit_sha": str(commit_sha),
            "source_snapshot_id": snap_id,
            "file_path": path,
            "git_blob_oid": (entry or {}).get("sha"),
            "expected_size": (entry or {}).get("size"),
            "acquisition_permission": None,
            "captured_content_asset_id": None,
            "content_integrity_status": None,
            "parser_status": None,
            "facts_persisted": 0,
            "claims_persisted": 0,
            "verifications_persisted": 0,
            "state": None,
            "required_next_operation": None,
            "planned_requests": 0,
        }
        if entry is None:
            rec["state"] = METADATA_AVAILABLE
            rec["required_next_operation"] = "ADD_TO_SCOPE_OR_TREE"
            rec["note"] = "该路径不在快照 tree 中"
            objects.append(rec)
            continue
        if not rec["git_blob_oid"]:
            rec["state"] = OID_UNAVAILABLE
            rec["required_next_operation"] = "REFETCH_TREE"
            objects.append(rec)
            continue

        meta = CIC.find_content_asset(store, repository_id=str(repository_id),
                                      commit_sha=str(commit_sha),
                                      file_path=path)
        if meta is None:
            rec["state"] = CONTENT_NOT_CAPTURED
            rec["required_next_operation"] = "FETCH_BLOB"
            rec["planned_requests"] = 1
        else:
            rec["captured_content_asset_id"] = meta.get("content_asset_id")
            rec["content_integrity_status"] = meta.get("completeness_status")
            if content_integrity_status_ok(meta):
                rec["state"] = CONTENT_AVAILABLE_VERIFIED
                rec["required_next_operation"] = None
            else:
                rec["state"] = CAPTURE_INTEGRITY_FAILED
                rec["required_next_operation"] = "VERIFY_OR_RECAPTURE"

        # 解析与事实
        if _is_source(path):
            fs = SKQ.query_source_facts(store=store,
                                        repository_id=str(repository_id))
            mine = [f for f in fs if f.get("file_path") == path]
            rec["facts_persisted"] = len(mine)
            if rec["facts_persisted"] == 0:
                rec["parser_status"] = "NOT_PARSED"
                if rec["state"] == CONTENT_AVAILABLE_VERIFIED:
                    rec["state"] = CONTENT_CAPTURED_BUT_NOT_PARSED
                    rec["required_next_operation"] = "PARSE_LOCAL"
                    rec["planned_requests"] = 0  # ★ 离线可做，0 请求
            else:
                rec["parser_status"] = "PARSED"
                rec["state"] = FACTS_PERSISTED
                rec["required_next_operation"] = None
        else:
            fs = CKQ.query_content_facts(
                store=store, repository_id=str(repository_id),
                commit_sha=str(commit_sha), file_path=path, limit=500)
            rec["facts_persisted"] = len(fs)
            if rec["facts_persisted"]:
                rec["state"] = FACTS_PERSISTED
                rec["required_next_operation"] = None
            elif rec["state"] == CONTENT_AVAILABLE_VERIFIED:
                rec["state"] = CONTENT_CAPTURED_BUT_NOT_PARSED
                rec["required_next_operation"] = "PARSE_LOCAL"
                rec["planned_requests"] = 0

        if rec["state"] == FACTS_PERSISTED:
            claims = _count_claims(store, repository_id, commit_sha, path)
            rec["claims_persisted"] = claims["claims"]
            rec["verifications_persisted"] = claims["verifications"]
            if claims["verified"]:
                rec["state"] = CLAIMS_VERIFIED
        objects.append(rec)

    total_planned = sum(o["planned_requests"] for o in objects)
    return {
        "ok": True,
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "source_snapshot_id": snap_id,
        "tree_completeness": snap.get("completeness_status"),
        "tree_entries": len(entries),
        "content_scope": list(scope),
        "objects": objects,
        "planned_requests_total": total_planned,
        # ★ 三种完整性分开报
        "completeness": {
            "tree_enumeration": snap.get("completeness_status"),
            "selected_content_capture": (
                "COMPLETE" if all(o["captured_content_asset_id"]
                                  or o["state"] in (CONTENT_NOT_CAPTURED,)
                                  for o in objects) and not total_planned
                else "PARTIAL"),
            "knowledge_processing": (
                "COMPLETE" if all(o["state"] in (CLAIMS_VERIFIED, KNOWLEDGE_QUERYABLE)
                                  for o in objects) else "PARTIAL"),
        },
    }


def content_integrity_status_ok(meta):
    return (meta.get("completeness_status") or "").upper() in ("COMPLETE", "")


def _load_snapshot(store, repository_id, commit_sha):
    import json
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='repository_snapshot' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if str(pl.get("commit_sha")) != str(commit_sha):
            continue
        pl = dict(pl, _snapshot_asset_id=r["asset_id"])
        return pl
    return None


def _count_claims(store, repository_id, commit_sha, path):
    import verification_store as VS
    n_claims = n_verifs = 0
    verified = False
    for r in store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='claim_candidate' "
            "AND repository_id=?", (str(repository_id),)).fetchall():
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if str(pl.get("commit_sha")) != str(commit_sha):
            continue
        if (pl.get("normalized_path") or pl.get("subject", {}).get("file_path")) != path:
            continue
        n_claims += 1
    for r in store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='claim_verification' "
            "AND repository_id=?", (str(repository_id),)).fetchall():
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("status") == "supported":
            verified = True
        n_verifs += 1
    return {"claims": n_claims, "verifications": n_verifs, "verified": verified}


def build_request_plan(*, inventory, budget):
    """把缺口盘点转成请求计划。★ 只读。"""
    plan = []
    for o in inventory.get("objects") or []:
        if o["planned_requests"] <= 0:
            plan.append({
                "file_path": o["file_path"], "needed": False,
                "reason": o["state"], "planned_requests": 0,
                "endpoint": None,
            })
            continue
        plan.append({
            "file_path": o["file_path"], "needed": True,
            "reason": o["state"],
            "endpoint": f"/repos/{inventory['repository_id']}/git/blobs/"
                        f"{o['git_blob_oid']}",
            "intended_object": o["git_blob_oid"],
            "purpose": "capture_missing_blob_content",
            "planned_requests": o["planned_requests"],
            "required_or_optional": "required",
        })
    return {
        "target_repository": inventory["repository_id"],
        "target_commit": inventory["commit_sha"],
        "known_snapshot": inventory["tree_completeness"],
        "objects": plan,
        "estimated_requests": inventory["planned_requests_total"],
        "actual_requests": 0,
        "budget": budget.to_dict() if budget else None,
        "read_only": True,
    }
