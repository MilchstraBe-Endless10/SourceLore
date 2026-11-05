#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容级分析：在既有 analyze 之上做增量，不建第二个 CLI。"""

from paths import ensure_import_path
from result import SkillError
import content_models as CM

ensure_import_path()

CONTENT_CANDIDATES_LIMIT = 32


def content_analyze(*, repository_id, commit_sha, data_root=None,
                    paths=None, provenance_level="SYNTHETIC_FIXTURE"):
    """对已有快照做内容抽取。

    ★ 普通查询不写库；本函数只返回抽取结果，落库由显式写入步骤负责。
    """
    import content_extractor as EX
    from knowledge_store import KnowledgeStore
    from paths import db_path, guard_inside_project_db

    p = db_path(data_root)
    guard_inside_project_db(p)
    if not p.exists():
        raise SkillError("知识库未建立", code="KNOWLEDGE_DB_MISSING",
                         exit_code=3)
    store = KnowledgeStore(str(p), create=False)
    try:
        rows = store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='repository_snapshot' "
            "AND repository_id=? ORDER BY asset_version DESC, asset_id",
            (repository_id,)).fetchall()
        payloads = []
        for r in rows:
            got = store.get_asset(r["asset_id"], verify=True)
            if got.get("ok"):
                pl = (got["asset"] or {}).get("payload") or {}
                if pl.get("commit_sha") == commit_sha:
                    payloads.append((r["asset_id"], pl))
        if not payloads:
            raise SkillError(
                f"本地无该 Commit 的快照：{repository_id}@{commit_sha[:12]}",
                code="SNAPSHOT_NOT_FOUND", exit_code=3)

        snap_id, pl = payloads[0]
        entries = pl.get("tree_entries") or []
        if paths:
            wanted = [x for x in paths][:CONTENT_CANDIDATES_LIMIT]
        else:
            wanted = [e["path"] for e in entries
                      if e.get("type") == "blob"][:CONTENT_CANDIDATES_LIMIT]

        summary = _inventory(pl, entries, wanted)
        out = EX.extract_snapshot(
            snapshot_payload=pl, repository_id=repository_id,
            commit_sha=commit_sha, candidate_paths=wanted,
            source_snapshot_id=snap_id, provenance_level=provenance_level)
        return {
            "ok": True, "repository_id": repository_id,
            "commit_sha": commit_sha,
            "provenance_level": provenance_level,
            "snapshot_inventory": summary,
            "observations": out["observations"],
            "skipped": out["skipped"],
            "budget": out["budget"],
            "content_available": any(
                o["observation"] is not None for o in out["observations"]),
            "note": ("内容字节未采集时返回 BLOB_CONTENT_NOT_AVAILABLE，"
                     "不得凭路径猜测内容"),
        }
    finally:
        store.close()


def _inventory(pl, entries, wanted):
    blobs = [e for e in entries if e.get("type") == "blob"]
    content_map = pl.get("blob_contents") or {}
    captured = sum(1 for e in blobs if e.get("sha") in content_map)
    return {
        "tree_entries": len(entries),
        "blob_entries": len(blobs),
        "non_blob_entries": len(entries) - len(blobs),
        "content_captured": captured,
        "candidates_requested": len(wanted),
        "completeness_status": pl.get("completeness_status"),
        "note": ("content_captured=0 表示只有 Blob 引用、无内容字节"
                 if captured == 0 else None),
    }
