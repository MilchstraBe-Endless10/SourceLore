#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collector → Storage 入库协调器。

契约：SL-CAP-0074（阶段产物完整性）、SL-CAP-0071（检查点）。

**立场：**
  C1 Collector 只能通过 Storage 的 `append_asset_and_advance` 写入，**不碰 A/B/C 表**
  C2 采集资产 ≠ 已验证的 Facts/Claims —— 入库只是"记录采集事实"，不做语义升级
  C3 同快照重复采集：不重复建资产、不推进 B 指针、不增历史版本
  C4 同 operation_id 不同输入摘要 → 显式 CONFLICT
"""

import hashlib
import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
_RT = _HERE.parent / "runtime"
_ST = _HERE.parent / "storage"
for _p in (str(_HERE), str(_RT), str(_ST)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from asset_models import AssetDraft, ModelError
from knowledge_store import KnowledgeStore
from source_snapshot import SourceSnapshot, canonical_json, sha256_of

ASSET_TYPE = "repository_snapshot"

# 入库结果码（与执行状态正交）
INGESTED = "INGESTED"
IDEMPOTENT = "IDEMPOTENT_ALREADY_PRESENT"
CONFLICT = "CONFLICT"
REJECTED = "REJECTED"


def stable_operation_id(*, repository_id: str, commit_sha: str,
                        retrieval_scope: str, collector_version: str) -> str:
    """稳定 operation_id：**由确定性输入派生**，重试不改变。

    刻意不含时间戳 —— 否则每次重试都会换 id，"幂等"就名存实亡。
    """
    raw = canonical_json({
        "repository_id": str(repository_id),
        "commit_sha": commit_sha,
        "retrieval_scope": retrieval_scope,
        "collector_version": collector_version,
        "kind": "collector_ingest",
    })
    return "OP-COL-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def ingest_snapshot(store: KnowledgeStore, snapshot: SourceSnapshot, *,
                    operation_id: Optional[str] = None,
                    expected_version: Optional[int] = None,
                    run_id: Optional[str] = None) -> dict:
    """把快照写入 A/B。

    只调用 Storage 公开 API，不执行任何直接 SQL 写入。
    """
    op_id = operation_id or stable_operation_id(
        repository_id=snapshot.repository_id,
        commit_sha=snapshot.commit_sha,
        retrieval_scope=snapshot.retrieval_scope,
        collector_version=snapshot.collector_version)

    li = snapshot.logical_identity()
    chash = snapshot.content_hash()

    # C4 预检：同 operation_id 但内容不同 → CONFLICT（在写库之前就拦）
    try:
        prev = store.conn.execute(
            "SELECT asset_id, result_hash FROM operation_log WHERE operation_id=?",
            (op_id,)).fetchone()
    except Exception as e:
        return {"ok": False, "state": REJECTED, "error": "CHECKPOINT_CORRUPT",
                "detail": str(e)[:150], "operation_id": op_id}
    if prev is not None and prev["result_hash"] != chash:
        return {"ok": False, "state": CONFLICT, "operation_id": op_id,
                "detail": (f"同一 operation_id 对应不同输入摘要："
                           f"已存 {prev['result_hash'][:12]}… ≠ 本次 {chash[:12]}…")}

    # 已存在同身份同内容 → 幂等（不改 B 指针、不增版本）
    try:
        existing = store.conn.execute(
            "SELECT asset_id, content_hash FROM assets "
            "WHERE repository_id=? AND logical_identity=? AND asset_version=1",
            (snapshot.repository_id, li)).fetchone()
    except Exception as e:
        return {"ok": False, "state": REJECTED, "error": "CHECKPOINT_CORRUPT",
                "detail": str(e)[:150], "operation_id": op_id}

    if existing is not None:
        if existing["content_hash"] == chash:
            # 完全相同的快照 —— 不重复入库
            return {"ok": True, "state": IDEMPOTENT, "operation_id": op_id,
                    "asset_id": existing["asset_id"], "logical_identity": li,
                    "content_hash": chash,
                    "detail": "同快照已存在，未重复创建资产、未推进指针"}
        return {"ok": False, "state": CONFLICT, "operation_id": op_id,
                "detail": (f"同身份但内容不同：已存 {existing['content_hash'][:12]}… "
                           f"≠ 本次 {chash[:12]}…（快照内容变了）")}

    # 正常入库：走 Storage 的单一写入口
    try:
        draft = AssetDraft(
            asset_type=ASSET_TYPE,
            logical_identity=li,
            repository_id=snapshot.repository_id,
            payload=snapshot.to_asset_payload(),
            asset_version=1,
            operation_id=op_id,
        )
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "error": "PERMISSION_DENIED",
                "detail": f"模型校验失败: {e}", "operation_id": op_id}

    res = store.append_asset_and_advance(
        draft, expected_version=expected_version, operation_id=op_id)

    if not res.get("ok"):
        return {"ok": False, "state": REJECTED, "operation_id": op_id,
                "error": res.get("error"), "detail": res.get("detail", ""),
                "current_version": res.get("current_version")}

    return {"ok": True, "state": INGESTED, "operation_id": op_id,
            "asset_id": res["asset_id"], "pointer_version": res["pointer_version"],
            "logical_identity": li, "content_hash": chash,
            "detail": "快照已入库（未做任何语义升级，仍为原始采集资产）"}


def verify_ingest(store: KnowledgeStore, snapshot: SourceSnapshot,
                  *, asset_id: str) -> dict:
    """入库后校验：读回资产，比对 content_hash。"""
    got = store.get_asset(asset_id, verify=True)
    if not got.get("ok"):
        return {"ok": False, "error": got.get("error"),
                "detail": got.get("detail", "")}
    a = got["asset"]
    expected = snapshot.content_hash()
    return {"ok": a["content_hash"] == expected,
            "asset_content_hash": a["content_hash"],
            "snapshot_content_hash": expected,
            "asset_version": a["asset_version"],
            "logical_identity": a["logical_identity"]}
