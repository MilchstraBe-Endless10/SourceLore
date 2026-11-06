#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恢复盘点：只读、零网络，按真实 Storage 说清「已完成 / 缺失 / 需几次请求」。

★ 不信日志，只信 Storage。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("collector", "storage", "runtime", "content", "content_persistence",
           "skill_interface", "facts", "evidence_claims", "source_analysis"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)


def inventory(*, data_root, repository_id=None, commit=None, url=None,
              content_paths=None):
    """输出恢复盘点。★ 不发任何请求。"""
    import content_ingest_coordinator as CIC
    import knowledge_store as KS
    from paths import db_path

    rid = repository_id
    if rid is None and url:
        # 从已有 storage 反查（不联网）
        try:
            ks = KS.KnowledgeStore(str(db_path(data_root)), create=False)
            try:
                rows = ks.conn.execute(
                    "SELECT DISTINCT repository_id FROM index_rows "
                    "WHERE asset_type='repository_snapshot'").fetchall()
                cand = [r[0] for r in rows]
                rid = cand[-1] if cand else None
            finally:
                ks.close()
        except Exception:
            rid = None
    if rid is None:
        return {"ok": False, "error": "无法确定 repository_id（不联网反查失败）",
                "network_requests": 0}

    ks = KS.KnowledgeStore(str(db_path(data_root)), create=False)
    try:
        snaps = ks.conn.execute(
            "SELECT DISTINCT commit_sha, asset_id FROM index_rows "
            "WHERE asset_type='repository_snapshot' AND repository_id=? "
            "ORDER BY commit_sha", (str(rid),)).fetchall()
        commits = [r[0] for r in snaps]
        csha = commit or (commits[-1] if commits else None)
        if not csha:
            return {"ok": False, "error": "无该仓库快照", "repository_id": str(rid),
                    "network_requests": 0}

        # Tree 条目：复用已有的只读快照加载（index_rows 不含 payload，
        # payload 在 assets 表；自己拼 SQL 会查错列）
        import capture_request_plan as PLAN
        snap = PLAN._load_snapshot(ks, str(rid), str(csha))
        entries = (snap or {}).get("tree_entries") or []

        scope = list(content_paths or [])
        if not scope:
            low = {e["path"].lower(): e["path"] for e in entries}
            scope = [low[k] for k in ("license", "readme.md", "package.json",
                                      "index.js") if k in low]

        done, missing = [], []
        for fp in scope:
            m = CIC.find_content_asset(ks, repository_id=str(rid),
                                       commit_sha=str(csha), file_path=fp)
            ok = bool(m) and (m.get("completeness_status") or "").upper() == "COMPLETE"
            rec = {"file_path": fp,
                   "asset": (m or {}).get("content_asset_id"),
                   "sha256": (m or {}).get("content_sha256")}
            (done if ok else missing).append(rec)

        return {
            "ok": True,
            "read_only": True,
            "network_requests": 0,
            "repository_id": str(rid),
            "commit_sha": str(csha),
            "commit_candidates": commits,
            "tree_entries": len(entries),
            "selected_scope": scope,
            "persisted_verified": done,
            "missing": missing,
            "planned_requests": len(missing),
            "next_action": ("无需采集" if not missing
                            else "需 %d 次 blob 请求" % len(missing)),
            "note": ("只信 Storage，不信日志；已完成的不会再下载"),
        }
    finally:
        ks.close()
