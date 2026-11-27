#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技术语义知识持久化（P2-D3）。

复用既有 Storage A/B/C 层（同一个 kb.db），**不建第四套知识存储**：
  - A 层 assets：命题 payload 作为 `semantic_proposition` 权威资产，A 层不可变
  - B 层 current_view：按 proposition_id 维护当前指针（幂等更新）
  - C 层 index_rows / asset_fts：由 A 层重建，按 repository_id + commit_sha 隔离

★ 幂等契约：
  - 同 proposition_id + 同内容哈希 → IDEMPOTENT，不重复写
  - 同 proposition_id + 不同内容（证据增强/限定）→ 新增版本，历史保留
  - 身份不含时间戳；证据变化不改变命题身份，只改变内容哈希

★ 授权与来源：
  - 证据的 provenance/copy/distribution 已由契约层继承，本模块不改写
  - 写入只在显式调用 ingest 时发生；read/load 全程只读
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("semantic_knowledge", "storage"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import semantic_models as SM

ASSET_TYPE = "semantic_proposition"
INGESTED = "INGESTED"
IDEMPOTENT = "IDEMPOTENT_ALREADY_PRESENT"
VERSION_ADDED = "VERSION_ADDED"


def _latest(store, repository_id, logical_identity):
    try:
        row = store.conn.execute(
            "SELECT asset_id, asset_version, content_hash, payload_json "
            "FROM assets WHERE repository_id=? AND logical_identity=? "
            "ORDER BY asset_version DESC LIMIT 1",
            (str(repository_id), logical_identity)).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def ingest_proposition(store, prop: "SM.SemanticProposition", *,
                       expected_version=None) -> dict:
    """把一条已校验的语义命题写入 A 层（+B 指针 +C 索引）。幂等。"""
    from asset_models import AssetDraft, ModelError

    payload = prop.content_payload()
    chash = prop.content_hash()
    op = "OP-SEM-" + SM.sha256_of({
        "kind": ASSET_TYPE, "identity": prop.proposition_id,
        "content_hash": chash,
    })[:32]

    cur = _latest(store, prop.repository_id, prop.proposition_id)
    if cur is not None:
        if cur["content_hash"] == chash:
            return {"ok": True, "state": IDEMPOTENT,
                    "proposition_id": prop.proposition_id,
                    "asset_id": cur["asset_id"],
                    "asset_version": cur["asset_version"],
                    "detail": "同命题同内容已存在，未重复创建"}
        if expected_version is not None and expected_version != cur["asset_version"]:
            return {"ok": False, "state": "REJECTED", "error": "CONFLICT",
                    "proposition_id": prop.proposition_id,
                    "current_version": cur["asset_version"],
                    "expected_version": expected_version,
                    "detail": "CAS 失败：期望版本与当前版本不符"}
        next_v = cur["asset_version"] + 1
    else:
        next_v = 1

    try:
        draft = AssetDraft(
            asset_type=ASSET_TYPE,
            logical_identity=prop.proposition_id,
            repository_id=str(prop.repository_id),
            payload=payload,
            asset_version=next_v,
            operation_id=op,
        )
    except ModelError as e:
        return {"ok": False, "state": "REJECTED", "detail": str(e)}

    res = store.append_asset_and_advance(
        draft, expected_version=(cur["asset_version"] if cur else None),
        operation_id=op)
    if not res.get("ok"):
        return {"ok": False, "state": "REJECTED",
                "error": res.get("error"), "detail": res.get("detail", "")}
    return {"ok": True,
            "state": VERSION_ADDED if cur else INGESTED,
            "proposition_id": prop.proposition_id,
            "asset_id": res.get("asset_id"), "asset_version": next_v}


def proposition_from_payload(payload: dict) -> "SM.SemanticProposition":
    """从 A 层 payload 还原命题对象（只读路径）。"""
    ev = []
    for e in (payload.get("evidence") or []):
        ev.append(SM.SemanticEvidenceRef(
            content_asset_id=str(e.get("content_asset_id") or ""),
            content_sha256=str(e.get("content_sha256") or ""),
            git_blob_oid=str(e.get("git_blob_oid") or ""),
            file_path=str(e.get("file_path") or ""),
            heading=str(e.get("heading") or ""),
            source_category=str(e.get("source_category") or SM.SRC_UNVERIFIED),
            provenance_level=str(e.get("provenance_level") or ""),
            copy_permitted=bool(e.get("copy_permitted", False)),
            distribution_allowed=bool(e.get("distribution_allowed", False)),
            line_start=int(e.get("line_start") or 0),
            line_end=int(e.get("line_end") or 0),
            byte_start=int(e.get("byte_start") or 0),
            byte_end=int(e.get("byte_end") or 0),
        ))
    return SM.SemanticProposition(
        proposition=payload.get("proposition") or "",
        knowledge_kind=payload.get("knowledge_kind") or SM.K_ARCHITECTURE,
        repository_id=str(payload.get("repository_id") or ""),
        commit_sha=payload.get("commit_sha") or "",
        subject=payload.get("subject") or "",
        evidence=ev,
        support_level=payload.get("support_level") or SM.S_NOT_SUPPORTED,
        source_category=payload.get("source_category") or SM.SRC_UNVERIFIED,
        verification_status=(payload.get("verification_status")
                             or SM.V_INSUFFICIENT),
        coverage_state=payload.get("coverage_state") or SM.C_INSUFFICIENT,
        limitations=list(payload.get("limitations") or []),
        question=payload.get("question") or "",
        proposition_id=payload.get("proposition_id") or "",
        schema_version=payload.get("schema_version") or SM.SEMANTIC_SCHEMA_VERSION,
    )


def load_propositions(store, *, repository_id, commit_sha=None,
                      subject=None, kind=None, limit=50) -> dict:
    """只读加载当前视图的语义命题（按 repository + commit 隔离）。

    返回 {ok, repository_id, commit_sha, propositions:[...], count}。
    不联网、不写库、不修改任何资产。
    """
    clauses = ["cv.repository_id=?", "a.asset_type=?"]
    params = [str(repository_id), ASSET_TYPE]
    if commit_sha:
        clauses.append("a.payload_json LIKE ?")
        params.append('%' + str(commit_sha) + '%')
    if kind:
        clauses.append("a.payload_json LIKE ?")
        params.append('%' + str(kind) + '%')
    if subject:
        clauses.append("a.payload_json LIKE ?")
        params.append('%' + str(subject) + '%')
    sql = (
        "SELECT a.payload_json FROM current_view cv "
        "JOIN assets a ON a.asset_id=cv.current_asset_id "
        "WHERE " + " AND ".join(clauses) + " LIMIT ?"
    )
    params.append(int(limit))
    try:
        rows = store.conn.execute(sql, params).fetchall()
    except Exception as e:
        return {"ok": False, "error": str(e), "propositions": []}

    out = []
    for row in rows:
        try:
            import json as _j
            payload = _j.loads(row["payload_json"])
            if payload.get("schema_version") != SM.SEMANTIC_SCHEMA_VERSION:
                continue
            # commit 精确过滤（LIKE 只是粗筛，防止主题里含 commit 串误命中）
            if commit_sha and payload.get("commit_sha") != commit_sha:
                continue
            if kind and payload.get("knowledge_kind") != kind:
                continue
            if subject and subject not in (payload.get("subject") or ""):
                continue
            out.append(payload)
        except Exception:
            continue
    return {"ok": True, "repository_id": str(repository_id),
            "commit_sha": commit_sha, "propositions": out,
            "count": len(out)}


def find_by_id(store, proposition_id: str) -> dict:
    """按 proposition_id 读当前指针命中（只读）。"""
    try:
        row = store.conn.execute(
            "SELECT a.payload_json FROM current_view cv "
            "JOIN assets a ON a.asset_id=cv.current_asset_id "
            "WHERE cv.logical_identity=? LIMIT 1",
            (proposition_id,)).fetchone()
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not row:
        return {"ok": False, "error": "NOT_FOUND",
                "proposition_id": proposition_id}
    import json as _j
    return {"ok": True, "proposition_id": proposition_id,
            "payload": _j.loads(row["payload_json"])}
