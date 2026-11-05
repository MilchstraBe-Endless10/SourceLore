#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容采集：Skill CLI 的唯一入口。

★ 只走既有 GitHubClient；不新建网络客户端。
★ 授权不过 → 不发请求、不写字节，只报阻断原因。
"""

from paths import ensure_import_path, db_path, guard_inside_project_db
from result import SkillError

ensure_import_path()

MAX_BLOB_BYTES = 256 * 1024
MAX_BATCH_BYTES = 2 * 1024 * 1024
MAX_PATHS = 32


def capture(*, repository_id, commit_sha, data_root=None, paths=None,
            owner=None, repo=None, license_known=False,
            repo_looks_third_party=True, max_requests=20,
            use_token=True, offline=False, dry_run=False):
    """采集并入库。返回逐路径独立结果。"""
    import content_acquisition_policy as POL
    import blob_fetcher as BF
    import content_ingest_coordinator as CIC
    from knowledge_store import KnowledgeStore
    from github_client import GitHubClient
    from paths import DEFAULT_DATA_ROOT

    p = db_path(data_root)
    guard_inside_project_db(p)
    if not p.exists():
        raise SkillError("知识库未建立", code="KNOWLEDGE_DB_MISSING", exit_code=3)

    store = KnowledgeStore(str(p), create=False)
    try:
        snap = _pick_snapshot(store, repository_id, commit_sha)
        if not snap:
            raise SkillError(f"本地无该 Commit 快照：{commit_sha[:12]}",
                             code="SNAPSHOT_NOT_FOUND", exit_code=3)

        entries = snap["payload"].get("tree_entries") or []
        eligible, blocked = POL.candidate_paths(entries, explicit=paths)

        report = {
            "ok": True, "repository_id": repository_id,
            "commit_sha": commit_sha, "offline": offline,
            "selected_paths": len(paths or []), "eligible_paths": len(eligible),
            "blocked_paths": blocked, "results": [],
            "fetched_blobs": 0, "verified_blobs": 0, "persisted_blobs": 0,
            "reused_blobs": 0, "skipped_blobs": 0,
            "network_requests": 0, "content_bytes_stored": 0,
            "distribution_allowed": False,
            "provenance": "SYNTHETIC_FIXTURE_TO_BE_SET",
        }

        if not eligible and not blocked:
            report["ok"] = False
            report["error"] = "NO_ELIGIBLE_CONTENT_PATHS"
            report["note"] = "快照中没有匹配白名单的根目录文件"
            return report

        # 离线：只读状态，不联网
        if offline:
            for item in eligible:
                got = _status_only(store, data_root, repository_id,
                                   commit_sha, item["file_path"])
                report["results"].append(got)
            report["note"] = "离线模式：未发起任何网络请求"
            return report

        budget = {"used": 0, "paths": 0}
        client = None
        if not dry_run:
            _tok = __import__("os").environ.get("GITHUB_TOKEN") if use_token else None
            client = GitHubClient(token=_tok or None, limits={
                "max_requests": max_requests, "max_retries": 0,
                "max_retry_after": 0, "request_timeout": 20})

        for item in eligible:
            fp = item["file_path"]
            entry = item["entry"]

            if budget["paths"] >= MAX_PATHS:
                report["results"].append({"file_path": fp,
                                          "status": "BATCH_PATH_LIMIT"})
                continue
            budget["paths"] += 1

            otype = entry.get("type") or "blob"
            st, code, note = POL.preflight(
                repository_id=repository_id, commit_sha=commit_sha,
                file_path=fp, object_type=otype,
                repo_looks_third_party=repo_looks_third_party,
                license_known=license_known)
            if st != POL.ACQ_ALLOWED:
                report["results"].append({
                    "file_path": fp, "status": st, "reason": code,
                    "note": note, "bytes_written": 0})
                report["skipped_blobs"] += 1
                continue

            size = entry.get("size")
            allow, why = BF.declared_size_gate(size, MAX_BLOB_BYTES)
            if not allow:
                report["results"].append({"file_path": fp, "status": why,
                                          "declared_size": size,
                                          "note": "前置预算拒绝，未发请求"})
                report["skipped_blobs"] += 1
                continue
            if budget["used"] + int(size) > MAX_BATCH_BYTES:
                report["results"].append({"file_path": fp,
                                          "status": "BATCH_BYTE_LIMIT"})
                report["skipped_blobs"] += 1
                continue

            if dry_run:
                report["results"].append({"file_path": fp, "status": "DRY_RUN_OK",
                                          "declared_size": size,
                                          "note": "计划可采集，未发请求"})
                continue

            got = BF.fetch_blob(client, owner=owner, name=repo,
                                blob_sha=entry.get("sha"),
                                expected_size=size,
                                max_bytes=MAX_BLOB_BYTES,
                                repository_id=repository_id,
                                commit_sha=commit_sha)
            report["network_requests"] += got.get("network_requests", 0)

            if got["status"] != BF.OK:
                report["results"].append({
                    "file_path": fp, "status": got["status"],
                    "reasons": got.get("reasons"),
                    "error_code": got.get("error_code")})
                report["skipped_blobs"] += 1
                continue

            report["fetched_blobs"] += 1
            report["verified_blobs"] += 1
            budget["used"] += got["byte_length"]

            ing = CIC.ingest_captured_blob(
                store, data_root=data_root or DEFAULT_DATA_ROOT,
                repository_id=repository_id, commit_sha=commit_sha,
                source_snapshot_id=snap["asset_id"], file_path=fp,
                git_blob_oid=got["git_blob_oid"],
                git_object_format="sha1", raw=got["raw"],
                source_declared_size=size,
                acquisition_policy=st, acquisition_policy_ref=code,
                provenance_level="SYNTHETIC_FIXTURE",
            )
            if not ing.get("ok"):
                report["results"].append({"file_path": fp,
                                          "status": "PERSIST_FAILED",
                                          "error": ing.get("error")})
                continue

            if ing.get("reused"):
                report["reused_blobs"] += 1
            else:
                report["persisted_blobs"] += 1
                report["content_bytes_stored"] += got["byte_length"]

            report["results"].append({
                "file_path": fp, "status": "CAPTURED_VERIFIED",
                "git_blob_oid": got["git_blob_oid"],
                "content_sha256": got["content_sha256"],
                "byte_length": got["byte_length"],
                "content_asset_id": ing.get("content_asset_id"),
                "reused": ing.get("reused"),
                "acquisition_policy": st})

        report["provenance"] = "SYNTHETIC_FIXTURE"
        report["budget"] = {"used_bytes": budget["used"], "paths": budget["paths"],
                            "max_blob": MAX_BLOB_BYTES, "max_batch": MAX_BATCH_BYTES}
        return report
    finally:
        store.close()


def _pick_snapshot(store, repository_id, commit_sha):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='repository_snapshot' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        pl = (got["asset"] or {}).get("payload") or {}
        if pl.get("commit_sha") == str(commit_sha):
            return {"asset_id": r["asset_id"], "payload": pl}
    return None


def _status_only(store, data_root, repository_id, commit_sha, file_path):
    from paths import DEFAULT_DATA_ROOT
    import captured_blob_loader as L
    got = L.load_captured_blob(
        store=store, data_root=data_root or DEFAULT_DATA_ROOT,
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, verify=True)
    return {"file_path": file_path, "status": got["status"],
            "content_asset_id": got.get("content_asset_id"),
            "git_blob_oid": got.get("git_blob_oid"),
            "byte_length": got.get("byte_length")}
