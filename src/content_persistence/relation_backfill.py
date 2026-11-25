#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-A：已有知识离线增量补全关系。★ 纯本地、零网络、幂等、A 层不变。

对某个 repository_id + commit_sha，扫描已保存的 captured_blob_content，
用已验证字节重跑共享静态模块关系管线。不重新采集、不访问 GitHub。

A 层不变保证：所有写入都通过既有 ingest_* 去重接口；重复执行只会
written=[] / reused=N，既有资产（事实、配置、项目）不会被改写或删除。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("storage", "collector", "content_persistence", "source_analysis",
           "skill_interface", "content"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx")
CONFIG_NAMES = ("tsconfig.json", "jsconfig.json")


def _list_captured(store, repository_id, commit_sha):
    """列出该仓库该 Commit 已保存的所有内容资产元数据（零网络）。"""
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
        if str(pl.get("commit_sha") or "") != str(commit_sha):
            continue
        if not pl.get("file_path"):
            continue
        out.append(pl)
    return out


def _load_bytes(data_root, meta):
    import blob_content_store as BS
    got = BS.get_bytes(data_root=data_root,
                       content_sha256=meta.get("content_sha256"), verify=True)
    return got.get("raw") if got.get("ok") else None


def backfill_relations(*, repository_id, commit_sha, data_root,
                       source_snapshot_id=None):
    """离线补全静态模块关系。返回结构化报告（含 written/reused/skipped）。"""
    from knowledge_store import KnowledgeStore
    from paths import db_path, DEFAULT_DATA_ROOT
    import content_ingest_coordinator as CIC
    import module_relation_pipeline as MRP
    from github_knowledge_extract import _tree_paths_from_snapshot

    # ★ CLI 的 --data-root 默认为 None；统一回退到 DEFAULT_DATA_ROOT，
    #   避免 blob 字节加载收到 None 而崩溃（store/db_path 自身有回退）。
    root = data_root or DEFAULT_DATA_ROOT
    store = KnowledgeStore(str(db_path(root)), create=False)
    try:
        metas = _list_captured(store, repository_id, commit_sha)
        file_sources, config_sources = [], []
        skipped = []
        for meta in metas:
            path = meta["file_path"]
            name = path.rsplit("/", 1)[-1]
            is_cfg = name in CONFIG_NAMES
            is_src = path.endswith(SOURCE_SUFFIXES)
            if not (is_cfg or is_src):
                continue
            policy = meta.get("acquisition_policy")
            if policy in ("AUTHORIZATION_UNKNOWN", "ACQUISITION_BLOCKED", "METADATA_ONLY"):
                skipped.append({"path": path, "reason": "ACQUISITION_BLOCKED"})
                continue
            raw = _load_bytes(root, meta)
            if raw is None:
                skipped.append({"path": path, "reason": "BYTES_UNREADABLE"})
                continue
            prov = meta.get("provenance_level")
            if not prov:
                skipped.append({"path": path, "reason": "PROVENANCE_UNKNOWN"})
                continue
            identity = {
                "git_blob_oid": meta.get("git_blob_oid"),
                "content_asset_id": meta.get("content_asset_id"),
                "content_sha256": meta.get("content_sha256"),
                "provenance_level": prov,
            }
            if is_cfg:
                config_sources.append({
                    "config_path": path, "config_kind": name, "raw": raw,
                    "blob_oid": meta.get("git_blob_oid"),
                    "content_asset_id": meta.get("content_asset_id"),
                    "content_digest": meta.get("content_sha256"),
                })
            else:
                file_sources.append(dict(identity, file_path=path, raw=raw))

        tree_paths, tree_completeness = _tree_paths_from_snapshot(
            store, repository_id, commit_sha)
        # 已捕获路径也纳入 tree（快照可能只登记根层），让解析尽量精确。
        tree_paths = set(tree_paths) | {m["file_path"] for m in metas}

        report = {"ok": True,
                  "repository_id": str(repository_id),
                  "commit_sha": str(commit_sha),
                  "network_requests": 0,
                  "captured_total": len(metas),
                  "source_files": len(file_sources),
                  "config_files": len(config_sources),
                  "skipped": skipped,
                  "tree_completeness": tree_completeness,
                  "tree_paths": len(tree_paths)}
        if not (file_sources or config_sources):
            report.update({"status": "NO_CAPTURED_SOURCE",
                           "note": "无已捕获源码/配置字节；未重采、未写库。",
                           "written": [], "reused": [], "counts": {}})
            return report

        prov = None
        for m in metas:
            if m.get("provenance_level"):
                prov = m["provenance_level"]
                break
        result = MRP.process_source_relations(
            store, repository_id=str(repository_id), commit_sha=str(commit_sha),
            file_sources=file_sources, config_sources=config_sources,
            tree_paths=tree_paths, provenance_level=prov or "OBSERVED",
            source_snapshot_id=source_snapshot_id or "")
        report.update({
            "status": "COMPLETED",
            "written": result.get("written") or [],
            "reused": result.get("reused") or [],
            "counts": result.get("counts") or {},
            "outcomes": result.get("outcomes") or {},
        })
        return report
    finally:
        store.close()
