#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容级查询：只读已有内容事实，不触发采集、不写库。"""

from paths import ensure_import_path
from result import SkillError

ensure_import_path()

COVERAGE_NONE = "NO_CONTENT_KNOWLEDGE"
COVERAGE_HIT = "CONTENT_FACTS_FOUND"


def content_query(*, repository_id, commit_sha, file_path=None,
                  fact_type=None, data_root=None):
    """★ 纯只读。库里没有内容事实 ≠ 该文件没有内容。"""
    import content_models as CM
    from knowledge_store import KnowledgeStore
    from paths import db_path

    p = db_path(data_root)
    if not p.exists():
        return {"ok": True, "coverage_state": COVERAGE_NONE,
                "observations": [],
                "reason": "知识库未建立；无内容级知识",
                "insertion_hint": ("如需内容知识，须显式执行 "
                                   "analyze --include-content（写操作）")}
    store = KnowledgeStore(str(p), create=False)
    try:
        rows = store.conn.execute(
            "SELECT asset_id FROM index_rows "
            "WHERE asset_type='file_content_observation' "
            "AND repository_id=?", (repository_id,)).fetchall()
        obs = []
        for r in rows:
            got = store.get_asset(r["asset_id"], verify=True)
            if not got.get("ok"):
                continue
            pl = (got["asset"] or {}).get("payload") or {}
            if commit_sha and pl.get("commit_sha") != commit_sha:
                continue
            if file_path and pl.get("file_path") != file_path:
                continue
            obs.append(pl)
        return {
            "ok": True,
            "coverage_state": COVERAGE_HIT if obs else COVERAGE_NONE,
            "count": len(obs),
            "observations": obs[:50],
            "reason": (None if obs else
                       "本地无该范围内的内容级观察；"
                       "这不代表文件不存在或无该内容，只是尚未抽取"),
            "note": ("内容事实只覆盖已抽取范围；"
                     "未抽取路径不得据此推断为不存在"),
        }
    finally:
        store.close()
