#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容采集入库协调：元数据入 A 层，字节入内容寻址存储。

★ 不使用 source_snapshot 传参（P5B 教训：ingest 不传导致 index 列 NULL），
  元数据 payload 里直接写 commit_sha，索引靠 P5B 的三级回退即可命中。

★ 幂等：同 (repo, commit, path, git_oid, content_sha256) 复用既有资产。
"""

import blob_content_store as BS

ASSET_TYPE = "captured_blob_content"
CAPTURE_SCOPE = "single_blob_root_readme_or_manifest"

SCHEDULE_VERSION = "captured-blob-content/1"


def _safe_path_token(file_path: str) -> str:
    """★ logical_identity 只允许 [字母数字 ._:-]。
    路径含 / 与空格，用可逆编码替换（保留可读性）。"""
    # ★ 只允许 alnum 与 ._:- ；其它字符用 _XX_ 形式（下划线本身在允许集内）
    out = []
    for ch in file_path:
        if ch.isalnum() or ch in "._-":
            out.append(ch)
        else:
            out.append(f"_x{ord(ch):02x}_")
    return "".join(out)


def make_content_asset_id(*, logical_identity, content_sha256):
    """★ 确定性资产 ID：同身份同内容 → 同 ID（幂等前提）。"""
    import hashlib
    h = hashlib.sha256((logical_identity + "|" + content_sha256)
                       .encode("utf-8")).hexdigest()
    return "SL-CBLOB-" + h[:40]


def make_logical_identity(*, repository_id, commit_sha, file_path, git_blob_oid):
    """★ 同一 blob 在多路径/多 Commit/多仓库 → 各自独立身份。"""
    return (f"SL-BLOB-{repository_id}::{commit_sha[:12]}::"
            f"{_safe_path_token(file_path)}::{git_blob_oid[:12]}")


def ingest_captured_blob(store, *, data_root, repository_id, commit_sha,
                         source_snapshot_id, file_path, git_blob_oid,
                         git_object_format, raw, source_declared_size,
                         acquisition_policy, acquisition_policy_ref,
                         provenance_level="SYNTHETIC_FIXTURE",
                         captured_at="", source_api="github.git.blobs",
                         source_response_digest=None):
    """返回 {ok, content_asset_id, reused, content_sha256, byte_length}。"""
    from asset_models import AssetDraft

    digest = "sha256:" + __import__("hashlib").sha256(raw).hexdigest()

    # 1) 字节先落内容寻址存储（幂等）
    put = BS.put_bytes(data_root=data_root, raw=raw, expected_sha256=digest)
    if not put.get("ok"):
        return {"ok": False, "error": put.get("error"),
                "detail": put.get("detail") or put.get("computed")}

    li = make_logical_identity(repository_id=repository_id,
                               commit_sha=commit_sha, file_path=file_path,
                               git_blob_oid=git_blob_oid)

    # 2) 已存在同身份同摘要 → 复用，不重复写入
    existing = _find_existing(store, li, digest)
    if existing:
        return {"ok": True, "content_asset_id": existing,
                "reused": True, "content_sha256": digest,
                "byte_length": len(raw),
                "bytes_reused": put.get("reused", False)}

    # ★ A 层不可改：content_asset_id 必须在写入前确定
    content_asset_id = make_content_asset_id(
        logical_identity=li, content_sha256=digest)

    payload = {
        "payload_schema": SCHEDULE_VERSION,
        "content_asset_id": content_asset_id,
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "source_snapshot_id": source_snapshot_id,
        "file_path": file_path,
        "git_blob_oid": git_blob_oid,
        "git_object_format": git_object_format,
        "raw_byte_length": len(raw),
        "source_declared_size": source_declared_size,
        "content_sha256": digest,
        "capture_status": "CAPTURED",
        "completeness_status": "COMPLETE",
        "capture_scope": CAPTURE_SCOPE,
        "acquisition_policy": acquisition_policy,
        "acquisition_policy_ref": acquisition_policy_ref,
        "provenance_level": provenance_level,
        "captured_at": captured_at,
        "source_api": source_api,
        "source_response_digest": source_response_digest,
        # ★ 分发限制继承既有门禁，不因采集成功而解除
        "distribution_allowed": False,
        "copy_permitted": False,
    }

    draft = AssetDraft(asset_type=ASSET_TYPE, logical_identity=li,
                       repository_id=str(repository_id), payload=payload,
                       asset_version=1)
    res = store.append_asset_and_advance(draft, expected_version=None)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error_code") or res.get("error"),
                "detail": res.get("detail")}

    return {"ok": True, "content_asset_id": res.get("asset_id"), "reused": False,
            "content_sha256": digest, "byte_length": len(raw),
            "bytes_reused": put.get("reused", False)}


def _find_existing(store, li, digest):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type=? AND logical_identity=?",
        (ASSET_TYPE, li)).fetchall()
    import json
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("content_sha256") == digest:
            return r["asset_id"]
    return None


def find_content_asset(store, *, repository_id, commit_sha, file_path):
    """按 (repo, commit, path) 找内容资产。★ 严格三键匹配，不跨 Commit 混用。"""
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type=? AND repository_id=?",
        (ASSET_TYPE, str(repository_id))).fetchall()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("commit_sha") != str(commit_sha):
            continue
        if pl.get("file_path") != file_path:
            continue
        return pl
    return None
