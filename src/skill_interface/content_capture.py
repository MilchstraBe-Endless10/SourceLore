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

# ★ P2-D2 / D2-D：真实 GitHub 采集入口的来源等级。
#   本模块只通过 GitHubClient（BF.fetch_blob 已校验 Git OID/SHA）采集真实远程 blob，
#   写入的是 captured_blob_content 资产层 provenance。真实远程 blob 的既定值见
#   src/collector/github_knowledge_extract.py:110-118 —— 抽取产物继承被抽取 blob 的
#   provenance，真实远程 blob 为 AUTHORIZED_REMOTE_SOURCE。硬编码 SYNTHETIC_FIXTURE
#   会把真实字节谎报为合成夹具（P2-D1 PROVENANCE_DEFECT），必须纠正。
#   注意：这与 ref_observer 的观测层三值（REAL_LIVE_API/HISTORICAL_REAL_DATA/
#   SYNTHETIC_FIXTURE）是两套体系，不要混用；合成夹具只在显式传入时产生。
PROVENANCE_AUTHORIZED_REMOTE = "AUTHORIZED_REMOTE_SOURCE"
PROVENANCE_SYNTHETIC = "SYNTHETIC_FIXTURE"


def resolve_provenance(explicit=None):
    """决定本次采集写入资产层的来源等级。

    ★ 默认真实远程采集 = AUTHORIZED_REMOTE_SOURCE；只有显式传入
      SYNTHETIC_FIXTURE 才是合成夹具，绝不默认谎报为 fixture。
    """
    return explicit or PROVENANCE_AUTHORIZED_REMOTE


def capture(*, repository_id, commit_sha, data_root=None, paths=None,
            owner=None, repo=None, license_known=False,
            repo_looks_third_party=True, max_requests=20,
            use_token=True, offline=False, dry_run=False,
            authorization_kind=None, extract_facts=False,
            budget=None, provenance_level=None):
    """采集并入库。返回逐路径独立结果。

    ★ F2-P6F：`budget` 为外部（验收编排器）预检通过后的 GitHubRequestBudget。
    传入时每个 blob 采集前都要过一次 can_spend，采完用真实响应头 consume。
    不传则保留原行为（内部自建 client 自限流）。
    """
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

        prov = resolve_provenance(provenance_level)
        report = {
        "authorization_basis": (POL.AUTH_LICENSE_OBSERVED if license_known
                                and not authorization_kind
                                else authorization_kind),
            "ok": True, "repository_id": repository_id,
            "commit_sha": commit_sha, "offline": offline,
            "selected_paths": len(paths or []), "eligible_paths": len(eligible),
            "blocked_paths": blocked, "results": [],
            "fetched_blobs": 0, "verified_blobs": 0, "persisted_blobs": 0,
            "reused_blobs": 0, "skipped_blobs": 0,
            "network_requests": 0, "content_bytes_stored": 0,
            "distribution_allowed": False,
            "provenance": prov,
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

        # ★ D2/FIX-B3：批次字节/文件计数与外部 GitHubRequestBudget 严格分离。
        #   此前本行用 budget 覆盖外部预算对象，随后的 can_spend/consume 触发 INTERNAL_ERROR。
        byte_budget = {"used_bytes": 0, "paths": 0}
        client = None
        if not dry_run:
            _tok = __import__("os").environ.get("GITHUB_TOKEN") if use_token else None
            client = GitHubClient(token=_tok or None, limits={
                "max_requests": max_requests, "max_retries": 0,
                "max_retry_after": 0, "request_timeout": 20})

        for item in eligible:
            fp = item["file_path"]
            entry = item["entry"]

            if byte_budget["paths"] >= MAX_PATHS:
                report["results"].append({"file_path": fp,
                                          "status": "BATCH_PATH_LIMIT"})
                continue
            byte_budget["paths"] += 1

            # ★ D-52：已有完整本地资产 → 直接复用，绝不重新下载。
            #   （此前会无条件发请求，撞限流后把已存好的内容标记为失败。）
            _have = CIC.find_content_asset(store,
                                           repository_id=str(repository_id),
                                           commit_sha=str(commit_sha),
                                           file_path=fp)
            if _have is not None and \
                    (_have.get("completeness_status") or "").upper() == "COMPLETE":
                report["results"].append({
                    "file_path": fp, "status": "ALREADY_CAPTURED",
                    "content_asset_id": _have.get("content_asset_id"),
                    "reused": True, "network_requests": 0})
                report["reused_paths"] = report.get("reused_paths", 0) + 1
                continue

            otype = entry.get("type") or "blob"
            # ★ F2-P5E：五维分别判，不再用含糊的单一状态
            # ★ D-46：license_known 原本是"声明式空参数"，接收但从不使用。
            #   现在把它落到真实授权依据 LICENSE_OBSERVED_AND_APPLICABLE。
            authz = None
            _kind = authorization_kind
            if not _kind and license_known:
                _kind = POL.AUTH_LICENSE_OBSERVED
            if _kind:
                authz = POL.build_authorization_ref(
                    authorization_kind=_kind,
                    repository_id=repository_id, scope=[fp],
                    source="cli-declared" if authorization_kind else "cli-license-known",
                    verification_status=POL.VERIFIED)
            dec = POL.evaluate_all(repository_id=repository_id,
                                   commit_sha=commit_sha, file_path=fp,
                                   authorization=authz, object_type=otype)
            if dec["FETCH_DECISION"]["decision"] != POL.ALLOW:
                report["results"].append({
                    "file_path": fp, "status": "FETCH_BLOCKED",
                    "reason": dec["FETCH_DECISION"]["reason_code"],
                    "note": dec["FETCH_DECISION"]["limitations"],
                    "bytes_written": 0, "decisions": dec})
                report["skipped_blobs"] += 1
                continue
            persist_ok = dec["PERSIST_DECISION"]["decision"] == POL.ALLOW
            if not persist_ok and not dry_run:
                # 允许临时读取但不允许持久化 → 不发请求，避免采集无用数据
                report["results"].append({
                    "file_path": fp, "status": "PERSIST_BLOCKED",
                    "reason": dec["PERSIST_DECISION"]["reason_code"],
                    "note": "读取可允许但持久化被阻断；不发起请求",
                    "bytes_written": 0, "decisions": dec})
                report["skipped_blobs"] += 1
                continue
            st, code = dec["PERSIST_DECISION"]["decision"], "AUTHORIZED"

            size = entry.get("size")
            allow, why = BF.declared_size_gate(size, MAX_BLOB_BYTES)
            if not allow:
                report["results"].append({"file_path": fp, "status": why,
                                          "declared_size": size,
                                          "note": "前置预算拒绝，未发请求"})
                report["skipped_blobs"] += 1
                continue
            if byte_budget["used_bytes"] + int(size) > MAX_BATCH_BYTES:
                report["results"].append({"file_path": fp,
                                          "status": "BATCH_BYTE_LIMIT"})
                report["skipped_blobs"] += 1
                continue

            if dry_run:
                report["results"].append({"file_path": fp, "status": "DRY_RUN_OK",
                                          "declared_size": size,
                                          "note": "计划可采集，未发请求"})
                continue

            # ★ F2-P6F：编排器预检通过后，每个 blob 仍要单独过闸门。
            #   预算不够就停，已落盘的照常保留（逐 blob 独立完成）。
            if budget is not None and not dry_run:
                _ok, _why = budget.can_spend(1)
                if not _ok:
                    report["results"].append({
                        "file_path": fp, "status": "BUDGET_BLOCKED",
                        "reason": _why,
                        "note": "预算不足，未发请求；此前已落盘的不受影响"})
                    report["skipped_blobs"] += 1
                    report["budget_blocked"] = report.get("budget_blocked", 0) + 1
                    continue

            got = BF.fetch_blob(client, owner=owner, name=repo,
                                blob_sha=entry.get("sha"),
                                expected_size=size,
                                max_bytes=MAX_BLOB_BYTES,
                                repository_id=repository_id,
                                commit_sha=commit_sha)
            report["network_requests"] += got.get("network_requests", 0)
            if budget is not None and got.get("network_requests"):
                budget.consume(headers=got.get("headers") or {},
                               status=got.get("http_status") or 200,
                               result="SUCCESS" if got["status"] == BF.OK else "ERROR",
                               at=__import__("time").time())

            if got["status"] != BF.OK:
                report["results"].append({
                    "file_path": fp, "status": got["status"],
                    "reasons": got.get("reasons"),
                    "error_code": got.get("error_code")})
                report["skipped_blobs"] += 1
                continue

            report["fetched_blobs"] += 1
            report["verified_blobs"] += 1
            byte_budget["used_bytes"] += got["byte_length"]

            ing = CIC.ingest_captured_blob(
                store, data_root=data_root or DEFAULT_DATA_ROOT,
                repository_id=repository_id, commit_sha=commit_sha,
                source_snapshot_id=snap["asset_id"], file_path=fp,
                git_blob_oid=got["git_blob_oid"],
                git_object_format="sha1", raw=got["raw"],
                source_declared_size=size,
                acquisition_policy=st, acquisition_policy_ref=code,
                provenance_level=prov,
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

        report["provenance"] = prov
        report["budget"] = {"used_bytes": byte_budget["used_bytes"], "paths": byte_budget["paths"],
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
