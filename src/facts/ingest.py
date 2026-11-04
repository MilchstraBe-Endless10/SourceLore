#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Facts 入库：只能经 Storage 公开 API 写入。

契约：SL-CAP-0009（Facts Registry 边界）、SL-CAP-0062（四层资产）。

**Registry 负责身份语义，Storage 负责权威持久化。**
本模块**不另建数据库**，不直写 A/B/C 表。
"""

import hashlib, sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from models import canonical_json, UNKNOWN
from asset_models import AssetDraft, ModelError
from rules import EXTRACTOR_VERSION

FACT_ASSET_TYPE = "extracted_fact"

INGESTED = "INGESTED"
IDEMPOTENT = "IDEMPOTENT_ALREADY_PRESENT"
CONFLICT = "CONFLICT"
REJECTED = "REJECTED"


def stable_operation_id(*, fact_id: str, content_hash: str,
                        extractor_version: str = EXTRACTOR_VERSION) -> str:
    """稳定 operation_id：由事实身份 + 内容摘要派生，重试不变。"""
    raw = canonical_json({
        "kind": "facts_ingest", "fact_id": fact_id,
        "content_hash": content_hash, "extractor_version": extractor_version,
    })
    return "OP-FACT-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def ingest_fact(store, fact, *, operation_id=None,
                expected_version=None) -> dict:
    """把一条**确定性**事实写入 A/B。

    UNKNOWN 观察不入库（我们没有把它当事实），但仍会被调用方审计记录。
    """
    if fact.observation == UNKNOWN or not fact.is_deterministic():
        return {"ok": False, "state": REJECTED, "error": "PERMISSION_DENIED",
                "detail": "UNKNOWN 观察不是确定性事实，不入 A 层",
                "fact_id": fact.fact_id}

    op_id = operation_id or stable_operation_id(
        fact_id=fact.fact_id, content_hash=fact.content_hash)

    # 事实资产用 fact_id 做 logical_identity；用 repository_id 做隔离维度
    li = fact.fact_id
    payload = fact.to_dict()

    try:
        prev = store.conn.execute(
            "SELECT asset_id, result_hash, logical_identity, pointer_version "
            "FROM operation_log WHERE operation_id=?", (op_id,)).fetchone()
    except Exception as e:
        return {"ok": False, "state": REJECTED, "error": "CHECKPOINT_CORRUPT",
                "detail": str(e)[:150], "fact_id": fact.fact_id}
    if prev is not None:
        # 同上：operation_log.result_hash 是 Storage 的 payload 哈希，
        # 不能与 fact.content_hash 直接比。要看该 operation 指向的
        # 事实资产里记录的 fact 摘要。
        import json as _json
        prev_fact_hash = None
        try:
            row = store.conn.execute(
                "SELECT payload_json FROM assets WHERE asset_id=?",
                (prev["asset_id"],)).fetchone()
            if row is not None:
                prev_fact_hash = _json.loads(row["payload_json"]).get("content_hash")
        except Exception:
            prev_fact_hash = None
        if prev_fact_hash != fact.content_hash:
            return {"ok": False, "state": CONFLICT, "operation_id": op_id,
                    "fact_id": fact.fact_id,
                    "detail": (f"同一 operation_id 对应不同事实摘要："
                               f"已存 {str(prev_fact_hash)[:12]}… ≠ "
                               f"本次 {fact.content_hash[:12]}…")}

    try:
        existing = store.conn.execute(
            "SELECT asset_id, content_hash, payload_json FROM assets "
            "WHERE repository_id=? AND logical_identity=? AND asset_version=1",
            (fact.repository_id, li)).fetchone()
    except Exception as e:
        return {"ok": False, "state": REJECTED, "error": "CHECKPOINT_CORRUPT",
                "detail": str(e)[:150], "fact_id": fact.fact_id}

    if existing is not None:
        # ★ 口径修正（本批实测发现的真实缺陷）：
        # Storage 的 assets.content_hash 是对**整个 payload** 算的；
        # fact.content_hash 是对**观测结论**算的。两者不在同一哈希空间，
        # 直接比较永远不等 → 幂等被误判成 CONFLICT。
        # 正确做法：读出已存 payload 里的 content_hash 字段来比。
        import json as _json
        try:
            prev_payload = _json.loads(existing["payload_json"])
            prev_fact_hash = prev_payload.get("content_hash")
        except Exception:
            prev_fact_hash = None

        if prev_fact_hash == fact.content_hash:
            return {"ok": True, "state": IDEMPOTENT, "operation_id": op_id,
                    "asset_id": existing["asset_id"], "fact_id": fact.fact_id,
                    "detail": "同事实已存在，未重复创建"}
        return {"ok": False, "state": CONFLICT, "operation_id": op_id,
                "fact_id": fact.fact_id,
                "detail": (f"同 fact_id 内容不同：已存事实摘要 "
                           f"{str(prev_fact_hash)[:12]}… ≠ 本次 "
                           f"{fact.content_hash[:12]}…（规则版本或观测结论发生变化）")}

    try:
        draft = AssetDraft(
            asset_type=FACT_ASSET_TYPE, logical_identity=li,
            repository_id=fact.repository_id,
            payload=payload, asset_version=1, operation_id=op_id)
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "error": "PERMISSION_DENIED",
                "detail": f"模型校验失败: {e}", "fact_id": fact.fact_id}

    res = store.append_asset_and_advance(
        draft, expected_version=expected_version, operation_id=op_id)
    if not res.get("ok"):
        return {"ok": False, "state": REJECTED, "operation_id": op_id,
                "error": res.get("error"), "detail": res.get("detail", ""),
                "fact_id": fact.fact_id}

    return {"ok": True, "state": INGESTED, "operation_id": op_id,
            "asset_id": res["asset_id"],
            "pointer_version": res["pointer_version"],
            "fact_id": fact.fact_id, "content_hash": fact.content_hash,
            "detail": "事实已入库（观测，不是已验证 Claim）"}
