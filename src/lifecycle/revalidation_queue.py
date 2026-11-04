#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新验证候选队列：原子协调 + 幂等 + A→B→C 历史保留。

**§7 的关键设计（方案 A 变体）：**
不做"先查有没有 pending，再插入"（两进程都能通过检查）。
而是把**候选本身**与**活动槽位**放进**同一个** WatchQueueState 资产的
**同一个 payload** 里，一次 CAS 写入完成两件事。

Storage 的 append_asset_and_advance 用 BEGIN IMMEDIATE，
且 K4 在**事务内**校验 pointer_version —— 所以"写候选 + 推槽位"是原子的。

★ 候选也各自落 A 层资产（可追溯），但**活动性**只由队列资产的
active_candidate_id 决定。两个候选不可能同时 active，因为它们共享一个槽位。
"""

import sys, json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage"),
           str(_HERE.parent / "evidence_claims")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from asset_models import AssetDraft, ModelError
import lc_models as L
import revalidation_models as R
from revalidation_planner import evaluate_eligibility, build_candidate

QUEUE_ASSET = "revalidation_queue"
CAND_ASSET = "revalidation_candidate"

INGESTED = "INGESTED"
IDEMPOTENT = "IDEMPOTENT_ALREADY_PRESENT"
VERSION_ADDED = "VERSION_ADDED"
SUPERSEDED_EXISTING = "SUPERSEDED_EXISTING_ACTIVE"
CONFLICT = "CONFLICT"
REJECTED = "REJECTED"


def _op(kind, ident, chash, ver):
    raw = L.canonical_json({"kind": kind, "identity": ident,
                            "content_hash": chash, "version": ver})
    import hashlib
    return "OP-RVQ-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _latest(store, asset_type, logical_identity, repository_id):
    try:
        row = store.conn.execute(
            "SELECT asset_id, asset_version, payload_json FROM assets "
            "WHERE asset_type=? AND logical_identity=? AND repository_id=? "
            "ORDER BY asset_version DESC LIMIT 1",
            (asset_type, logical_identity, repository_id)).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def read_queue(store, *, watch_id: str, repository_id: str) -> dict:
    qid = R.make_queue_id(watch_id=watch_id)
    row = _latest(store, QUEUE_ASSET, qid, repository_id)
    if row is None:
        return {"ok": True, "exists": False, "queue_id": qid,
                "active_candidate_id": None, "history_candidate_ids": []}
    try:
        p = json.loads(row["payload_json"])
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    return {"ok": True, "exists": True, "queue_id": qid,
            "asset_version": row["asset_version"],
            "active_candidate_id": p.get("active_candidate_id"),
            "active_target_commit_sha": p.get("active_target_commit_sha"),
            "history_candidate_ids": p.get("history_candidate_ids", []),
            "payload": p}


def _write_queue(store, *, watch, queue: R.WatchQueueState,
                 expected_version: int | None) -> dict:
    payload = queue.to_dict()
    payload.pop("updated_at", None)
    chash = L.sha256_of(payload)
    op = _op("queue", queue.queue_id, chash, "queue/1")
    try:
        draft = AssetDraft(asset_type=QUEUE_ASSET,
                           logical_identity=queue.queue_id,
                           repository_id=queue.repository_id,
                           payload=payload,
                           asset_version=(expected_version or 0) + 1,
                           operation_id=op)
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "detail": str(e)}
    res = store.append_asset_and_advance(
        draft, expected_version=expected_version, operation_id=op)
    if not res.get("ok"):
        return {"ok": False, "state": (CONFLICT if res.get("error") == "CONFLICT"
                                       else REJECTED),
                "error": res.get("error"), "detail": res.get("detail", "")}
    if res.get("idempotent"):
        return {"ok": True, "state": IDEMPOTENT,
                "asset_id": res.get("asset_id"),
                "asset_version": expected_version}
    return {"ok": True, "state": VERSION_ADDED,
            "asset_id": res["asset_id"],
            "asset_version": res.get("pointer_version", (expected_version or 0) + 1)}


def propose_candidate(store, *, assessment_id: str,
                      expected_queue_version: int | None = None,
                      created_at: str = "",
                      observation_provenance: str | None = None) -> dict:
    """从一条评估生成候选并入队（原子）。

    完整流程：
      1. 15 条门禁校验
      2. 候选身份确定性计算
      3. 读队列 → 判断是否已有活动候选 / 是否重复
      4. **一次** 写队列资产（候选列表 + 活动槽位同时更新）
      5. 候选落 A 层资产（可追溯）
    """
    gate = evaluate_eligibility(store, assessment_id=assessment_id,
                                observation_provenance=observation_provenance)
    if not gate.ok:
        return {"ok": False, "state": REJECTED, "reason_code": gate.reason,
                "detail": gate.detail}

    ctx = gate.ctx
    cand = build_candidate(ctx, created_at=created_at)

    q = read_queue(store, watch_id=ctx["watch_id"],
                   repository_id=ctx["repository_id"])
    if not q.get("ok"):
        return {"ok": False, "state": REJECTED,
                "reason_code": R.RJ_STORAGE_ERROR, "detail": q.get("detail", "")}

    history = list(q.get("history_candidate_ids", []))
    active = q.get("active_candidate_id")
    active_target = q.get("active_target_commit_sha")

    # 重复：同一候选已在历史中
    if cand.candidate_id in history:
        if active == cand.candidate_id:
            return {"ok": True, "state": IDEMPOTENT,
                    "candidate_id": cand.candidate_id,
                    "queue_id": q["queue_id"], "active": True,
                    "detail": "同一候选已入队且为活动候选"}
        return {"ok": True, "state": IDEMPOTENT,
                "candidate_id": cand.candidate_id, "queue_id": q["queue_id"],
                "active": False, "detail": "该候选已在历史中（非活动）"}

    superseded_id = None
    # 已有活动候选且目标不同 → 取代（保留历史，不静默覆盖）
    if active is not None and active != cand.candidate_id:
        if active_target == cand.target_commit_sha:
            return {"ok": True, "state": IDEMPOTENT,
                    "candidate_id": active, "queue_id": q["queue_id"],
                    "active": True,
                    "detail": "同一目标 Commit 已有活动候选"}
        superseded_id = active

    new_history = history + ([superseded_id] if superseded_id else [])
    if cand.candidate_id not in new_history:
        new_history.append(cand.candidate_id)

    queue = R.WatchQueueState(
        queue_id=q["queue_id"], watch_id=ctx["watch_id"],
        repository_id=str(ctx["repository_id"]),
        active_candidate_id=cand.candidate_id,
        active_target_commit_sha=cand.target_commit_sha,
        history_candidate_ids=sorted(set(new_history)),
        updated_at=created_at)

    # ★ 一次 CAS 写入：候选加入历史 + 活动槽位推进
    wres = _write_queue(store, watch=ctx["watch"],
                        queue=queue,
                        expected_version=(q["asset_version"]
                                          if q.get("exists") else None))
    if not wres.get("ok"):
        if wres.get("error") == "CONFLICT":
            return {"ok": False, "state": CONFLICT,
                    "reason_code": R.RJ_ACTIVE_EXISTS,
                    "detail": "队列版本冲突（另一进程已推进）"}
        return {"ok": False, "state": REJECTED,
                "reason_code": R.RJ_STORAGE_ERROR, "detail": wres.get("detail", "")}

    # 候选自身也落 A 层（可追溯）；活动性仍只由队列决定
    c_payload = cand.to_dict()
    c_payload.pop("created_at", None)
    c_op = _op("candidate", cand.candidate_id,
               L.sha256_of(c_payload), cand.revalidation_rule_version)
    existing = _latest(store, CAND_ASSET, cand.candidate_id,
                       str(ctx["repository_id"]))
    c_state = IDEMPOTENT
    if existing is None:
        try:
            draft = AssetDraft(asset_type=CAND_ASSET,
                               logical_identity=cand.candidate_id,
                               repository_id=str(ctx["repository_id"]),
                               payload=c_payload, asset_version=1,
                               operation_id=c_op)
        except ModelError as e:
            return {"ok": False, "state": REJECTED, "detail": str(e)}
        r2 = store.append_asset_and_advance(draft, expected_version=None,
                                            operation_id=c_op)
        if not r2.get("ok"):
            return {"ok": False, "state": REJECTED,
                    "reason_code": R.RJ_STORAGE_ERROR,
                    "detail": r2.get("detail", "")}
        c_state = INGESTED

    return {"ok": True, "state": (SUPERSEDED_EXISTING if superseded_id
                                  else wres["state"]),
            "candidate_id": cand.candidate_id,
            "queue_id": q["queue_id"], "active": True,
            "superseded_candidate_id": superseded_id,
            "candidate_asset_state": c_state,
            "candidate_status": cand.status,
            "state_reason": cand.state_reason,
            "source_level": cand.source_level}


def mark_superseded(store, *, candidate_id: str, repository_id: str,
                    superseded_by: str) -> dict:
    """把一条历史候选标为 SUPERSEDED —— 新版本，**不静默覆盖**。"""
    row = _latest(store, CAND_ASSET, candidate_id, repository_id)
    if row is None:
        return {"ok": False, "state": REJECTED,
                "reason_code": "CANDIDATE_NOT_FOUND"}
    p = json.loads(row["payload_json"])
    p["status"] = R.SUPERSEDED
    p["superseded_by"] = superseded_by
    p["state_reason"] = f"被 {superseded_by} 取代（新目标 Commit 到来）"
    p.pop("created_at", None)
    op = _op("candidate", candidate_id, L.sha256_of(p),
             p.get("revalidation_rule_version", R.REVALIDATION_RULE_VERSION))
    try:
        draft = AssetDraft(asset_type=CAND_ASSET, logical_identity=candidate_id,
                           repository_id=repository_id, payload=p,
                           asset_version=row["asset_version"] + 1,
                           operation_id=op)
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "detail": str(e)}
    res = store.append_asset_and_advance(draft,
                                         expected_version=row["asset_version"],
                                         operation_id=op)
    if not res.get("ok"):
        return {"ok": False, "state": CONFLICT if res.get("error") == "CONFLICT"
                else REJECTED, "detail": res.get("detail", "")}
    return {"ok": True, "state": VERSION_ADDED,
            "asset_version": row["asset_version"] + 1}


def read_candidate(store, *, candidate_id: str, repository_id: str) -> dict:
    row = _latest(store, CAND_ASSET, candidate_id, repository_id)
    if row is None:
        return {"ok": False, "error": "NOT_FOUND"}
    return {"ok": True, "payload": json.loads(row["payload_json"]),
            "asset_version": row["asset_version"]}


def read_candidate_versions(store, *, candidate_id: str,
                            repository_id: str) -> dict:
    try:
        rows = store.conn.execute(
            "SELECT asset_id, asset_version FROM assets "
            "WHERE asset_type=? AND logical_identity=? AND repository_id=? "
            "ORDER BY asset_version", (CAND_ASSET, candidate_id,
                                       repository_id)).fetchall()
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


def count_active(store, *, repository_id: str) -> dict:
    """统计活动候选数 —— 断言"每个 watch 最多一个"。

    ★ 只算**每个 watch 的最新队列版本**。
    队列是版本化资产（A 层不可变），历史版本保留是设计要求；
    但"当前活动候选"只由最新版本定义。把历史版本也算进来会误报多活动。
    """
    try:
        rows = store.conn.execute(
            "SELECT payload_json, logical_identity FROM assets "
            "WHERE asset_type=? AND repository_id=? "
            "ORDER BY asset_version DESC",
            (QUEUE_ASSET, repository_id)).fetchall()
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    actives, seen = {}, set()
    for r in rows:
        p = json.loads(r["payload_json"])
        w = p.get("watch_id")
        if w in seen:
            continue                      # 只取每个 watch 的最新版本
        seen.add(w)
        a = p.get("active_candidate_id")
        if a:
            actives.setdefault(w, set()).add(a)
    return {"ok": True,
            "active_by_watch": {k: sorted(v) for k, v in actives.items()},
            "total_active": sum(len(v) for v in actives.values()),
            "multi_active_watches": [k for k, v in actives.items() if len(v) > 1]}
