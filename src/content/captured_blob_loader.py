#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线读取已捕获 Blob。★ 绝不访问网络。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("storage", "collector"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import blob_content_store as BS


def load_captured_blob(*, store, data_root, repository_id, commit_sha,
                       file_path, verify=True) -> dict:
    """按 (repo, commit, path) 读回已验证字节。

    状态：CONTENT_AVAILABLE_VERIFIED / CONTENT_NOT_CAPTURED /
          CONTENT_ASSET_MISSING / CONTENT_INTEGRITY_FAILED /
          CONTENT_ACQUISITION_BLOCKED / CONTENT_PARTIAL /
          CONTENT_COMMIT_MISMATCH
    """
    import content_ingest_coordinator as CIC

    # 1) 找元数据（严格三键）
    meta = CIC.find_content_asset(store, repository_id=repository_id,
                                  commit_sha=commit_sha, file_path=file_path)
    if not meta:
        # 区分「有资产但 commit 不对」与「完全没有」
        other = _find_by_repo_path(store, repository_id, file_path)
        if other and other.get("commit_sha") != str(commit_sha):
            return {"status": BS.COMMIT_MISMATCH, "raw": None,
                    "found_commit": other.get("commit_sha"),
                    "requested_commit": str(commit_sha),
                    "message": "该路径内容属于另一个 Commit，拒绝跨版本读取"}
        return {"status": BS.NOT_CAPTURED, "raw": None,
                "message": "本地未捕获该路径内容（需显式 analyze --include-content）"}

    # 2) 采集授权状态
    policy = meta.get("acquisition_policy")
    if policy in ("AUTHORIZATION_UNKNOWN", "ACQUISITION_BLOCKED", "METADATA_ONLY"):
        return {"status": BS.ACQUISITION_BLOCKED, "raw": None,
                "acquisition_policy": policy,
                "message": "采集授权未通过，不得读取原始字节"}

    completeness = meta.get("completeness_status")
    if completeness and completeness != "COMPLETE":
        return {"status": BS.PARTIAL, "raw": None,
                "completeness_status": completeness}

    # 3) 读字节（纯本地）
    got = BS.get_bytes(data_root=data_root,
                       content_sha256=meta.get("content_sha256"),
                       verify=verify)
    if not got.get("ok"):
        return {"status": got.get("error") or BS.ASSET_MISSING,
                "raw": None,
                "content_asset_id": meta.get("content_asset_id"),
                "message": "字节不可读或摘要不符"}

    return {"status": BS.AVAILABLE_VERIFIED, "raw": got["raw"],
            "byte_length": got["byte_length"],
            "content_asset_id": meta.get("content_asset_id"),
            "git_blob_oid": meta.get("git_blob_oid"),
            "content_sha256": meta.get("content_sha256"),
            "repository_id": meta.get("repository_id"),
            "commit_sha": meta.get("commit_sha"),
            "file_path": meta.get("file_path"),
            "provenance_level": meta.get("provenance_level"),
            "distribution_allowed": meta.get("distribution_allowed", False)}


def _find_by_repo_path(store, repository_id, file_path):
    import content_ingest_coordinator as CIC
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type=? AND repository_id=?",
        (CIC.ASSET_TYPE, str(repository_id))).fetchall()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if got.get("ok"):
            pl = (got["asset"] or {}).get("payload") or {}
            if pl.get("file_path") == file_path:
                return pl
    return None
