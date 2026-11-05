#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""缓存策略：LOCAL_KNOWLEDGE_LOOKUP → CACHE_DECISION → OPTIONAL_REMOTE_REFRESH。

★ 缓存命中不看文件存在，看九个判据。损坏 ≠ 未命中。
"""

from paths import ensure_import_path

ensure_import_path()

SNAPSHOT_TYPE = "repository_snapshot"

# 决策结果
CACHE_HIT_COMPLETE = "CACHE_HIT_COMPLETE"
CACHE_HIT_PARTIAL = "CACHE_HIT_PARTIAL"
CACHE_MISS = "CACHE_MISS"
CACHE_INTEGRITY_FAILED = "CACHE_INTEGRITY_FAILED"
CACHE_BRANCH_UNKNOWN = "BRANCH_CURRENT_UNKNOWN"


def _sha_of(store, asset_id):
    """资产内容摘要（用既有 verify 机制，不自己造哈希）。"""
    got = store.get_asset(asset_id, verify=True)
    if not got.get("ok"):
        return None, got.get("error_code")
    return got.get("content_hash") or (got.get("asset") or {}).get("content_hash"), None


def lookup(store, *, repository_id, commit_sha=None, requested_ref=None):
    """本地知识查找。返回 {decision, snapshot, checks, reasons}。

    ★ commit_sha 为 None 时（可变 Branch），只能证明"过去观测过"，
      不能断言该 Branch 当前仍指向该 Commit。
    """
    rows = store.conn.execute(
        "SELECT asset_id, commit_sha, asset_version FROM index_rows "
        "WHERE asset_type=? AND repository_id=? ORDER BY asset_version DESC, asset_id",
        (SNAPSHOT_TYPE, repository_id)).fetchall()

    checks = {"repository_id": repository_id, "requested_commit": commit_sha,
              "requested_ref": requested_ref, "snapshot_rows": len(rows)}
    reasons = []
    candidates = []

    for r in rows:
        aid = r["asset_id"]
        got = store.get_asset(aid, verify=True)
        if not got.get("ok"):
            reasons.append(f"{aid}: 资产不可校验 {got.get('error_code')}")
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        csha = pl.get("commit_sha") or r["commit_sha"]
        candidates.append({"asset_id": aid, "commit_sha": csha,
                           "completeness": pl.get("completeness_status") or "UNKNOWN",
                           "retrieval_scope": pl.get("retrieval_scope"),
                           "tree_entries": len(pl.get("tree_entries") or []),
                           "digest": got.get("content_hash")})

    if not rows:
        return {"decision": CACHE_MISS, "checks": checks, "reasons":
                ["本地无该仓库的 Snapshot 资产"], "candidates": [], "snapshot": None}

    if commit_sha:
        matched = [c for c in candidates if c["commit_sha"] == commit_sha]
        if not matched:
            return {"decision": CACHE_MISS, "checks": checks, "candidates": candidates,
                    "reasons": [f"本地无 commit {commit_sha} 的 Snapshot"],
                    "snapshot": None}
    else:
        matched = candidates

    if not matched:
        return {"decision": CACHE_INTEGRITY_FAILED, "checks": checks,
                "reasons": reasons or ["Snapshot 行存在但全部无法校验"],
                "candidates": candidates, "snapshot": None}

    # ★ 取最新一个可校验的
    best = matched[0]
    comp = (best["completeness"] or "").upper()
    if comp == "COMPLETE":
        decision = CACHE_HIT_COMPLETE
    elif comp == "PARTIAL":
        decision = CACHE_HIT_PARTIAL
        reasons.append("缓存仅 PARTIAL，复用只覆盖已观察范围，不得冒充 COMPLETE")
    else:
        decision = CACHE_HIT_PARTIAL
        reasons.append(f"完整性状态未知（{best['completeness']}），按部分覆盖处理")

    if not commit_sha:
        decision_ref = CACHE_BRANCH_UNKNOWN
        reasons.append("未指定固定 Commit：本地快照只能证明过去观测过的版本，"
                       "不能确认该 Branch 当前仍指向它")

    return {"decision": decision, "checks": checks, "candidates": candidates,
            "snapshot": best, "reasons": reasons,
            "branch_current_unknown": bool(not commit_sha)}


def no_network(mode):
    return mode == "offline"
