#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lifecycle 持久化。

契约：SL-CAP-0041（不可变历史与当前视图）、0063/0064（历史与 CAS）。

**铁律：**
  S1 不建第二套 Lifecycle 数据库 —— 只用 Storage 的 A/B/C API
  S2 freshness_assessment ≠ claim_verification（身份、内容、历史都不共用）
  S3 不改写 EC 的 B 层当前验证指针
  S4 不改写不可变 Claim 资产来更新 knowledge_freshness
  S5 调用方给 expected_version 就必须校验（P2B 修过的缺陷不许复发）
"""

import hashlib, json, sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from asset_models import AssetDraft, ModelError
import lc_models as L

WATCH_ASSET = "lifecycle_watch"
OBS_ASSET = "ref_observation"
FRESH_ASSET = "freshness_assessment"

INGESTED = "INGESTED"
IDEMPOTENT = "IDEMPOTENT_ALREADY_PRESENT"
VERSION_ADDED = "VERSION_ADDED"
CONFLICT = "CONFLICT"
REJECTED = "REJECTED"


def _op(kind: str, ident: str, chash: str, ver: str) -> str:
    raw = L.canonical_json({"kind": kind, "identity": ident,
                            "content_hash": chash, "version": ver})
    return "OP-LC-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _latest(store, repo_id: str, logical_identity: str) -> Optional[dict]:
    try:
        row = store.conn.execute(
            "SELECT asset_id, asset_version, payload_json FROM assets "
            "WHERE repository_id=? AND logical_identity=? "
            "ORDER BY asset_version DESC LIMIT 1",
            (repo_id, logical_identity)).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _payload_hash(payload: dict, drop=()) -> str:
    return L.sha256_of({k: v for k, v in payload.items()
                        if k not in set(drop) | {"asset_version"}})


def _write(store, *, asset_type, logical_identity, repository_id, payload,
           op_id, drop_fields, expected_version=None) -> dict:
    """统一的写入路径：幂等 / 新版本 / CAS 三重语义。"""
    chash = _payload_hash(payload, drop=drop_fields)
    cur = _latest(store, repository_id, logical_identity)

    if cur is not None:
        try:
            prev = json.loads(cur["payload_json"])
        except Exception:
            prev = {}
        if _payload_hash(prev, drop=drop_fields) == chash:
            return {"ok": True, "state": IDEMPOTENT,
                    "asset_id": cur["asset_id"], "logical_identity": logical_identity}
        # ★ S5：CAS —— 调用方的期望版本必须校验（P2B 曾忽略，这里不许复发）
        if expected_version is not None and expected_version != cur["asset_version"]:
            return {"ok": False, "state": CONFLICT, "error": "CONFLICT",
                    "current_version": cur["asset_version"],
                    "expected_version": expected_version,
                    "detail": "CAS 失败：期望版本与当前版本不符"}
        next_v = cur["asset_version"] + 1
        try:
            draft = AssetDraft(asset_type=asset_type,
                               logical_identity=logical_identity,
                               repository_id=repository_id, payload=payload,
                               asset_version=next_v, operation_id=op_id)
        except ModelError as e:
            return {"ok": False, "state": REJECTED, "detail": str(e)}
        res = store.append_asset_and_advance(
            draft, expected_version=cur["asset_version"], operation_id=op_id)
        if not res.get("ok"):
            return {"ok": False, "state": REJECTED, "error": res.get("error"),
                    "detail": res.get("detail", "")}
        # ★ store 在 K2 / operation 幂等时返回 ok=True + idempotent=True。
        # 初版忽略了这个标记，把幂等当成新版本 —— 并发 CAS 实验抓到：
        # 4 个进程同时推进，2 个报 VERSION_ADDED（本应只有 1 个）。
        if res.get("idempotent"):
            return {"ok": True, "state": IDEMPOTENT,
                    "asset_id": res.get("asset_id", cur["asset_id"]),
                    "asset_version": cur["asset_version"],
                    "logical_identity": logical_identity}
        return {"ok": True, "state": VERSION_ADDED, "asset_id": res["asset_id"],
                "asset_version": next_v, "logical_identity": logical_identity}

    try:
        draft = AssetDraft(asset_type=asset_type,
                           logical_identity=logical_identity,
                           repository_id=repository_id, payload=payload,
                           asset_version=1, operation_id=op_id)
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "detail": str(e)}
    res = store.append_asset_and_advance(draft, expected_version=expected_version,
                                         operation_id=op_id)
    if not res.get("ok"):
        return {"ok": False, "state": REJECTED, "error": res.get("error"),
                "detail": res.get("detail", "")}
    return {"ok": True, "state": INGESTED, "asset_id": res["asset_id"],
            "asset_version": 1, "logical_identity": logical_identity}


def ingest_watch(store, watch, *, expected_version=None) -> dict:
    payload = watch.to_dict()
    payload.pop("created_at", None)
    return _write(store, asset_type=WATCH_ASSET, logical_identity=watch.watch_id,
                  repository_id=watch.repository_id, payload=payload,
                  op_id=_op("watch", watch.watch_id,
                            _payload_hash(payload, ("created_at",)),
                            "watch/1"),
                  drop_fields=("created_at",),
                  expected_version=expected_version)


def ingest_observation(store, obs, *, expected_version=None) -> dict:
    """观测写入。

    ★ 观测事件的**时间戳不参与身份**：同一 (repo, ref, commit, status)
    重复观测得到同一 observation_id，重复写入幂等。
    ★ 每次观测的时间仍保留在 payload 的 observed_at 里，但不进幂等键。
    """
    payload = obs.to_dict()
    payload.pop("observed_at", None)          # 时间不进内容哈希
    for ev in payload.get("evidence_refs", []):
        ev.pop("at", None)                    # 证据里的观测时刻同样剔除
    return _write(store, asset_type=OBS_ASSET,
                  logical_identity=obs.observation_id,
                  repository_id=obs.repository_id, payload=payload,
                  op_id=_op("observation", obs.observation_id,
                            _payload_hash(payload, ("observed_at",)), "obs/1"),
                  drop_fields=("observed_at",),
                  expected_version=expected_version)


def ingest_assessment(store, assessment, *, expected_version=None) -> dict:
    """评估写入。assessed_at / observed_at 均不进确定性身份。"""
    payload = assessment.to_dict()
    payload.pop("assessed_at", None)
    payload.pop("observed_at", None)
    return _write(store, asset_type=FRESH_ASSET,
                  logical_identity=assessment.assessment_id,
                  repository_id=assessment.repository_id, payload=payload,
                  op_id=_op("assessment", assessment.assessment_id,
                            _payload_hash(payload), "fresh/1"),
                  drop_fields=("assessed_at", "observed_at"),
                  expected_version=expected_version)


def read_assessment_versions(store, assessment_id: str, repository_id: str) -> dict:
    """读回历史评估（含旧版本）。"""
    try:
        rows = store.conn.execute(
            "SELECT asset_id, asset_version FROM assets "
            "WHERE repository_id=? AND logical_identity=? ORDER BY asset_version",
            (repository_id, assessment_id)).fetchall()
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


def current_freshness(store, *, repository_id: str, claim_id: str) -> dict:
    """按 claim 取最新新鲜度评估（不读改 Claim 资产）。

    ★ S4：knowledge_freshness 通过关联评估资产提供，不改写原始 Claim。
    """
    try:
        rows = store.conn.execute(
            "SELECT asset_id, payload_json FROM assets "
            "WHERE asset_type=? AND repository_id=? ORDER BY asset_version DESC",
            (FRESH_ASSET, repository_id)).fetchall()
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    hits = []
    for r in rows:
        try:
            p = json.loads(r["payload_json"])
        except Exception:
            continue
        if p.get("claim_id") == claim_id:
            hits.append({"asset_id": r["asset_id"], **p})
    if not hits:
        return {"ok": True, "state": "NO_ASSESSMENT", "claim_id": claim_id}
    return {"ok": True, "state": "HAS_ASSESSMENT", "claim_id": claim_id,
            "latest": hits[0], "count": len(hits)}
