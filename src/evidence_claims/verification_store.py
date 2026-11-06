#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claim 与 Verification 的持久化。

契约：SL-CAP-0062/0063/0064（权威存储、历史、CAS）。

**不建第二套数据库。** 只用 Storage 的 A/B/C API。
Claim 候选与验证记录都是可追溯权威资产。
"""

import hashlib, sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from asset_models import AssetDraft, ModelError
import ec_models as M

CLAIM_ASSET_TYPE = "claim_candidate"
VERIF_ASSET_TYPE = "claim_verification"

INGESTED = "INGESTED"
IDEMPOTENT = "IDEMPOTENT_ALREADY_PRESENT"
VERSION_ADDED = "VERSION_ADDED"
CONFLICT = "CONFLICT"
REJECTED = "REJECTED"


def _op_id(kind: str, identity: str, content_hash: str, version: str) -> str:
    raw = M.canonical_json({"kind": kind, "identity": identity,
                            "content_hash": content_hash, "version": version})
    return "OP-EC-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _latest(store, repo_id: str, logical_identity: str) -> Optional[dict]:
    try:
        row = store.conn.execute(
            "SELECT asset_id, asset_version, content_hash, payload_json FROM assets "
            "WHERE repository_id=? AND logical_identity=? "
            "ORDER BY asset_version DESC LIMIT 1",
            (repo_id, logical_identity)).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _append_version(store, draft, expected_version) -> dict:
    """新增一个版本（历史不被覆盖）。"""
    return store.append_asset_and_advance(
        draft, expected_version=expected_version,
        operation_id=draft.operation_id)


def ingest_claim(store, claim, *, expected_version=None) -> dict:
    """写入 Claim 候选。

    claim_id 是 logical_identity。同 claim_id 同内容 → 幂等；
    同 claim_id 不同内容 → 新增版本（历史保留），不是覆盖。
    """
    payload = claim.to_dict()
    payload.pop("created_at", None)   # 时间不进内容身份
    chash = M.sha256_of(payload)
    op = _op_id("claim", claim.claim_id, chash, M.CLAIM_SCHEMA_VERSION)

    cur = _latest(store, claim.repository_id, claim.claim_id)
    if cur is not None:
        try:
            import json as _j
            prev = _j.loads(cur["payload_json"])
        except Exception:
            prev = {}
        prev_hash = M.sha256_of({k: v for k, v in prev.items()
                                 if k not in ("created_at", "asset_version")})
        if prev_hash == chash:
            return {"ok": True, "state": IDEMPOTENT, "claim_id": claim.claim_id,
                    "asset_id": cur["asset_id"],
                    "detail": "同命题已存在，未重复创建"}
        # ★ 调用方给了 expected_version 就必须校验它（CAS）——
        # 曾经这里直接硬编码 cur["asset_version"]，把调用方的期望版本**忽略了**，
        # 导致错误的 expected_version 也能推进版本（本批实测抓到的真实缺陷）。
        if expected_version is not None and expected_version != cur["asset_version"]:
            return {"ok": False, "state": REJECTED, "error": "CONFLICT",
                    "claim_id": claim.claim_id,
                    "current_version": cur["asset_version"],
                    "expected_version": expected_version,
                    "detail": "CAS 失败：期望版本与当前版本不符"}
        # 内容变化（例如 review_status 变）→ 新版本
        next_v = cur["asset_version"] + 1
        try:
            draft = AssetDraft(asset_type=CLAIM_ASSET_TYPE,
                               logical_identity=claim.claim_id,
                               repository_id=claim.repository_id,
                               payload=payload, asset_version=next_v,
                               operation_id=op)
        except ModelError as e:
            return {"ok": False, "state": REJECTED, "detail": str(e)}
        res = _append_version(store, draft, cur["asset_version"])
        if not res.get("ok"):
            return {"ok": False, "state": REJECTED,
                    "error": res.get("error"), "detail": res.get("detail", "")}
        return {"ok": True, "state": VERSION_ADDED, "claim_id": claim.claim_id,
                "asset_id": res["asset_id"], "asset_version": next_v}

    try:
        draft = AssetDraft(asset_type=CLAIM_ASSET_TYPE,
                           logical_identity=claim.claim_id,
                           repository_id=claim.repository_id,
                           payload=payload, asset_version=1,
                           operation_id=op)
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "detail": str(e)}
    res = store.append_asset_and_advance(draft, expected_version=expected_version,
                                         operation_id=op)
    if not res.get("ok"):
        return {"ok": False, "state": REJECTED,
                "error": res.get("error"), "detail": res.get("detail", "")}
    return {"ok": True, "state": INGESTED, "claim_id": claim.claim_id,
            "asset_id": res["asset_id"], "asset_version": 1}


def ingest_verification(store, verif, *, repository_id: str,
                        commit_sha=None, expected_version=None) -> dict:
    """写入一次评估。

    verification_id 是 logical_identity —— 同证据同规则同 id → 幂等。
    新证据 → 新 verification_id → 新版本，历史保留。
    """
    payload = verif.to_dict()
    payload.pop("verified_at", None)
    chash = M.sha256_of(payload)
    op = _op_id("verification", verif.verification_id, chash,
                verif.rule_version)

    cur = _latest(store, repository_id, verif.verification_id)
    if cur is not None:
        return {"ok": True, "state": IDEMPOTENT,
                "verification_id": verif.verification_id,
                "asset_id": cur["asset_id"],
                "detail": "同评估已存在，未重复写入"}

    try:
        # ★ D-67：Verification.to_dict() 不含 commit_sha，_index_asset 的三级回退
        #   因此全落空 → index_rows.commit_sha 恒为 NULL → 查询按 commit 过滤读不回来。
        #   这里显式构造 SourceSnapshot 走回退①。
        #   ★ 只影响 C 层索引，不改 payload、不改资产哈希、不动权威正文。
        _snap = None
        if commit_sha:
            import asset_models as _AM
            _snap = _AM.SourceSnapshot(commit_sha=str(commit_sha))
        draft = AssetDraft(asset_type=VERIF_ASSET_TYPE,
                           logical_identity=verif.verification_id,
                           repository_id=repository_id,
                           payload=payload, asset_version=1,
                           operation_id=op, source_snapshot=_snap)
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "detail": str(e)}
    res = store.append_asset_and_advance(draft, expected_version=expected_version,
                                         operation_id=op)
    if not res.get("ok"):
        return {"ok": False, "state": REJECTED,
                "error": res.get("error"), "detail": res.get("detail", "")}
    return {"ok": True, "state": INGESTED,
            "verification_id": verif.verification_id,
            "asset_id": res["asset_id"], "asset_version": 1}


def read_verification(store, verification_id: str, repository_id: str) -> dict:
    """读回历史评估（含旧版本）。"""
    rows = []
    try:
        rows = store.conn.execute(
            "SELECT asset_id, asset_version FROM assets "
            "WHERE repository_id=? AND logical_identity=? "
            "ORDER BY asset_version", (repository_id, verification_id)).fetchall()
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    if not rows:
        return {"ok": False, "error": "NOT_FOUND"}
    out = []
    for r in rows:
        g = store.get_asset(r["asset_id"], verify=True)
        if not g.get("ok"):
            return {"ok": False, "error": g.get("error")}
        out.append(g["asset"])
    return {"ok": True, "versions": out}
