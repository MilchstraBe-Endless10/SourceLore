#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库只读查询：repositories / inspect / history。

★ 全部只读。不改 A/B/C 层，不改裁决。
"""

import json
from pathlib import Path

from paths import ensure_import_path, db_path, guard_inside_project_db
from result import SkillError, EXIT_UNAVAILABLE

ensure_import_path()

SNAPSHOT_TYPE = "repository_snapshot"
CAPTURE_TYPE = "captured_blob_content"
FACT_TYPE = "extracted_fact"
CLAIM_TYPE = "claim_candidate"
VERIF_TYPE = "claim_verification"


def open_store(data_root=None):
    """打开只读用途的 store；库不存在时明确报不可用。"""
    from knowledge_store import KnowledgeStore

    p = db_path(data_root)
    guard_inside_project_db(p)
    if not p.exists():
        raise SkillError(
            f"知识库尚未建立：{p}",
            code="KNOWLEDGE_DB_MISSING", exit_code=EXIT_UNAVAILABLE,
            detail={"db_path": str(p),
                    "hint": "先运行 analyze 采集一个仓库"})
    return KnowledgeStore(str(p), create=False)


def _rows(store, sql, params=()):
    return [dict(r) for r in store.conn.execute(sql, params).fetchall()]


def list_repositories(store) -> dict:
    """★ 列出已登记仓库。

    KnowledgeStore 无现成聚合接口，故只读 index_rows（C 层，可重建）。
    """
    sql = ("SELECT repository_id, asset_type, asset_id, commit_sha "
           "FROM index_rows")
    agg = {}
    for r in _rows(store, sql):
        repo = r["repository_id"]
        slot = agg.setdefault(repo, {"repository_id": repo,
                                     "counts": {}, "commits": set()})
        slot["counts"][r["asset_type"]] = slot["counts"].get(r["asset_type"], 0) + 1
        csha = r["commit_sha"]
        # ★ 实测 index_rows.commit_sha 为 NULL —— 必须回读 payload，不能信列名
        # ★ U-2：仓库显示名从独立观测资产读（不改 snapshot 内容身份）
        if r["asset_type"] == "subject_record":
            got = store.get_asset(r["asset_id"], verify=True)
            if got.get("ok"):
                pl = ((got["asset"] or {}).get("payload") or {})
                if pl.get("record_kind") == "repository_display_name":
                    nm = pl.get("resolved_repository")
                    if nm and not slot.get("_name"):
                        slot["_name"] = nm

        if not csha and r["asset_type"] == SNAPSHOT_TYPE:
            got = store.get_asset(r["asset_id"], verify=True)
            if got.get("ok"):
                csha = ((got["asset"] or {}).get("payload") or {}).get("commit_sha")
        # ★ U-4：只有**快照/内容**支撑的 commit 才算该仓库的历史版本。
        #   命题或验证上挂的 commit 可能来自负例（如 'a'*40 的错误 commit），
        #   把它当历史版本列出来会误导用户。
        if csha and r["asset_type"] in (SNAPSHOT_TYPE, CAPTURE_TYPE):
            slot["commits"].add(csha)
            slot["_commits_supported"] = True

    out = []
    for repo, slot in sorted(agg.items()):
        out.append({
            "repository_id": repo,
            "commits": sorted(slot["commits"]),
            "snapshot_count": slot["counts"].get(SNAPSHOT_TYPE, 0),
            "fact_count": slot["counts"].get(FACT_TYPE, 0),
            "claim_count": slot["counts"].get(CLAIM_TYPE, 0),
            "verification_count": slot["counts"].get(VERIF_TYPE, 0),
            "knowledge_state": ("HAS_KNOWLEDGE"
                                if slot["counts"].get(CLAIM_TYPE) else
                                "STRUCTURE_ONLY"),
            "repository": slot.get("_name"),
            "note": ("commits 为已登记快照的 Commit，不代表该仓库当前最新状态"),
        })
    return {"repositories": out, "count": len(out)}


def inspect_repository(store, repository_id: str) -> dict:
    """★ 单仓库知识摘要。"""
    snaps = _rows(store, "SELECT asset_id, commit_sha, asset_version "
                         "FROM index_rows WHERE asset_type=? AND repository_id=? "
                         "ORDER BY commit_sha, asset_version",
                  (SNAPSHOT_TYPE, repository_id))
    if not snaps:
        raise SkillError(f"未登记该仓库：{repository_id}",
                         code="REPOSITORY_NOT_FOUND",
                         detail={"repository_id": repository_id})

    coverage = []
    for s in snaps:
        got = store.get_asset(s["asset_id"], verify=True)
        pl = (got.get("asset") or {}).get("payload") if got.get("ok") else {}
        coverage.append({
            "snapshot_asset_id": s["asset_id"],
            "commit_sha": (pl or {}).get("commit_sha") or s["commit_sha"],
            "completeness_status": (pl or {}).get("completeness_status") or "UNKNOWN",
            "tree_entry_count": len((pl or {}).get("tree_entries") or []),
            "local_coverage_only": (pl or {}).get("completeness_status") != "COMPLETE",
        })

    facts = _rows(store, "SELECT asset_id, commit_sha FROM index_rows "
                         "WHERE asset_type=? AND repository_id=?",
                  (FACT_TYPE, repository_id))
    facts_detail = []
    for f in facts:
        got = store.get_asset(f["asset_id"], verify=True)
        pl = (got.get("asset") or {}).get("payload") if got.get("ok") else {}
        facts_detail.append({
            "fact_id": (pl or {}).get("fact_id"),
            "rule_id": (pl or {}).get("rule_id"),
            "observed_path": (pl or {}).get("observed_value", {}).get("path")
            if isinstance((pl or {}).get("observed_value"), dict) else None,
        })

    claims = _rows(store, "SELECT asset_id FROM index_rows "
                          "WHERE asset_type=? AND repository_id=?",
                   (CLAIM_TYPE, repository_id))
    claims_detail = []
    for c in claims:
        got = store.get_asset(c["asset_id"], verify=True)
        pl = (got.get("asset") or {}).get("payload") if got.get("ok") else {}
        claims_detail.append({
            "claim_id": (pl or {}).get("claim_id"),
            "claim_type": (pl or {}).get("claim_type"),
            "normalized_path": (pl or {}).get("normalized_path"),
            "commit_sha": (pl or {}).get("commit_sha"),
            "review_status": (pl or {}).get("review_status", "pending_review"),
        })

    return {
        "repository_id": repository_id,
        "commits": sorted({c["commit_sha"] for c in coverage if c["commit_sha"]}),
        "tree_coverage": coverage,
        "facts": facts_detail,
        "claims": claims_detail,
        "limitations": [
            "本知识库只记录已采集的路径观察事实，不含功能实现或测试结论",
            "commit 为已登记快照的固定 Commit，非仓库当前最新状态",
        ],
    }


def history(store, repository_id: str) -> dict:
    """★ 历史版本；只列已登记 Commit，不推断祖先关系。"""
    snaps = _rows(store, "SELECT asset_id, commit_sha, asset_version "
                         "FROM index_rows WHERE asset_type=? AND repository_id=? "
                         "ORDER BY commit_sha, asset_version",
                  (SNAPSHOT_TYPE, repository_id))
    versions = []
    for s in snaps:
        got = store.get_asset(s["asset_id"], verify=True)
        pl = (got.get("asset") or {}).get("payload") if got.get("ok") else {}
        versions.append({
            "commit_sha": (pl or {}).get("commit_sha") or s["commit_sha"],
            "snapshot_asset_id": s["asset_id"],
            "completeness_status": (pl or {}).get("completeness_status") or "UNKNOWN",
        })
    return {"repository_id": repository_id, "versions": versions,
            "note": "不同 Commit 各自成立；本接口不推断先后或祖先关系"}
