#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revalidation_run 执行记录 + 结果登记。

**候选状态与执行状态严格分离。** 候选只从 PROPOSED→SUPERSEDED/CANCELLED，
执行记录自己走 SUCCESS/FAILED/TIMEOUT/CANCELLED/UNKNOWN（复用 Runtime 词表）。
"""

import hashlib, json, sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage"), str(_HERE.parent / "runtime")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from asset_models import AssetDraft, ModelError
import lc_models as L

RUN_ASSET = "revalidation_run"
RESULT_ASSET = "revalidation_result"

# 执行状态（复用 Runtime 词表）
SUCCESS = "SUCCESS"
FAILED = "FAILED"
TIMEOUT = "TIMEOUT"
CANCELLED = "CANCELLED"
UNKNOWN = "UNKNOWN"
EXEC_STATES = frozenset({SUCCESS, FAILED, TIMEOUT, CANCELLED, UNKNOWN})

# 内部阶段状态（不冒充 Harness 原生状态）
STAGE_PENDING = "PENDING"
STAGE_RUNNING = "RUNNING"
STAGE_COMMITTED = "COMMITTED"
STAGE_FAILED_RETRYABLE = "FAILED_RETRYABLE"
STAGE_FAILED_FATAL = "FAILED_FATAL"
STAGE_UNKNOWN = "UNKNOWN"

STAGES = ("PREFLIGHT", "AUTHORIZATION_CHECK", "SNAPSHOT_COLLECT",
          "FACT_EXTRACT", "TARGET_CLAIM_CREATE", "EVIDENCE_VERIFY",
          "RESULT_PERSIST", "COMPLETION_CHECK")

INGESTED = "INGESTED"
IDEMPOTENT = "IDEMPOTENT_ALREADY_PRESENT"
VERSION_ADDED = "VERSION_ADDED"
CONFLICT = "CONFLICT"
REJECTED = "REJECTED"


def make_run_id(*, candidate_id: str, plan_digest: str,
                authorization_id: str) -> str:
    """同一候选 + 同一计划 + 同一授权 → 同一 run_id（幂等基础）。"""
    return "SL-RUN-" + L.sha256_of({
        "candidate_id": candidate_id, "plan_digest": plan_digest,
        "authorization_id": authorization_id})[:32]


def _op(kind, ident, chash, ver):
    raw = L.canonical_json({"kind": kind, "identity": ident,
                            "content_hash": chash, "version": ver})
    return "OP-RUN-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _latest(store, asset_type, li, repo_id):
    try:
        row = store.conn.execute(
            "SELECT asset_id, asset_version, payload_json FROM assets "
            "WHERE asset_type=? AND logical_identity=? AND repository_id=? "
            "ORDER BY asset_version DESC LIMIT 1",
            (asset_type, li, repo_id)).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _write(store, *, asset_type, li, repo_id, payload, op_id,
           expected_version=None, drop=()) -> dict:
    chash = L.sha256_of({k: v for k, v in payload.items()
                         if k not in set(drop) | {"asset_version"}})
    cur = _latest(store, asset_type, li, repo_id)
    if cur is not None:
        try:
            prev = json.loads(cur["payload_json"])
        except Exception:
            prev = {}
        if L.sha256_of({k: v for k, v in prev.items()
                        if k not in set(drop) | {"asset_version"}}) == chash:
            return {"ok": True, "state": IDEMPOTENT,
                    "asset_id": cur["asset_id"],
                    "asset_version": cur["asset_version"]}
        if expected_version is not None and expected_version != cur["asset_version"]:
            return {"ok": False, "state": CONFLICT, "error": "CONFLICT",
                    "current_version": cur["asset_version"],
                    "expected_version": expected_version,
                    "detail": "CAS 失败：期望版本与当前版本不符"}
        nv = cur["asset_version"] + 1
        try:
            draft = AssetDraft(asset_type=asset_type, logical_identity=li,
                               repository_id=repo_id, payload=payload,
                               asset_version=nv, operation_id=op_id)
        except ModelError as e:
            return {"ok": False, "state": REJECTED, "detail": str(e)}
        res = store.append_asset_and_advance(
            draft, expected_version=cur["asset_version"], operation_id=op_id)
        if not res.get("ok"):
            return {"ok": False, "state": REJECTED, "error": res.get("error"),
                    "detail": res.get("detail", "")}
        if res.get("idempotent"):
            return {"ok": True, "state": IDEMPOTENT,
                    "asset_id": res.get("asset_id", cur["asset_id"]),
                    "asset_version": cur["asset_version"]}
        return {"ok": True, "state": VERSION_ADDED, "asset_id": res["asset_id"],
                "asset_version": nv}
    try:
        draft = AssetDraft(asset_type=asset_type, logical_identity=li,
                           repository_id=repo_id, payload=payload,
                           asset_version=1, operation_id=op_id)
    except ModelError as e:
        return {"ok": False, "state": REJECTED, "detail": str(e)}
    res = store.append_asset_and_advance(draft, expected_version=expected_version,
                                         operation_id=op_id)
    if not res.get("ok"):
        return {"ok": False, "state": REJECTED, "error": res.get("error"),
                "detail": res.get("detail", "")}
    return {"ok": True, "state": INGESTED, "asset_id": res["asset_id"],
            "asset_version": 1}


def create_run(store, *, candidate, plan_digest: str, authorization_id: str,
               authorization_ref: str, created_at: str = "",
               require_production: bool = False) -> dict:
    """登记执行记录（幂等：同候选+同计划+同授权 → 同 run_id）。"""
    rid = make_run_id(candidate_id=candidate["candidate_id"],
                      plan_digest=plan_digest,
                      authorization_id=authorization_id)
    payload = {
        "run_id": rid,
        "candidate_id": candidate["candidate_id"],
        "plan_digest": plan_digest,
        # ★ Storage 的 FORBIDDEN_FIELDS 含 "authorization"（防凭据泄漏）。
        #   run 记录只存**引用**（id），不存授权对象本体。
        "auth_ref": authorization_ref,
        "auth_id": authorization_id,
        "repository_id": str(candidate["repository_id"]),
        "source_claim_id": candidate["source_claim_id"],
        "source_verification_id": candidate["source_verification_id"],
        "target_commit_sha": candidate["target_commit_sha"],
        "baseline_commit_sha": candidate["baseline_commit_sha"],
        "requested_ref": candidate["requested_ref"],
        "execution_status": UNKNOWN,       # 尚未开始
        "current_stage": STAGES[0],
        "stages": [{"stage": s, "state": STAGE_PENDING} for s in STAGES],
        "checkpoint_ref": None, "result_ref": None,
        "created_at": created_at, "updated_at": created_at,
        "require_production": bool(require_production),
    }
    res = _write(store, asset_type=RUN_ASSET, li=rid,
                 repo_id=str(candidate["repository_id"]), payload=payload,
                 op_id=_op("run", rid,
                           L.sha256_of({k: v for k, v in payload.items()
                                        if k not in ("created_at",
                                                     "updated_at")}), "run/1"),
                 expected_version=None,
                 drop=("created_at", "updated_at"))
    res["run_id"] = rid
    return res


def read_run(store, *, run_id: str, repository_id: str) -> dict:
    row = _latest(store, RUN_ASSET, run_id, repository_id)
    if row is None:
        return {"ok": False, "error": "NOT_FOUND"}
    return {"ok": True, "payload": json.loads(row["payload_json"]),
            "asset_version": row["asset_version"]}


def update_run(store, *, run_id: str, repository_id: str, mutate,
               updated_at: str = "") -> dict:
    """读-改-写 run 记录。`mutate(payload)` 就地修改。

    ★ 使用 expected_version（当前版本）做 CAS。
    """
    got = read_run(store, run_id=run_id, repository_id=repository_id)
    if not got.get("ok"):
        return {"ok": False, "state": REJECTED,
                "reason_code": "RUN_NOT_FOUND"}
    p = got["payload"]
    mutate(p)
    p["updated_at"] = updated_at
    res = _write(store, asset_type=RUN_ASSET, li=run_id,
                 repo_id=repository_id, payload=p,
                 op_id=_op("run", run_id,
                           L.sha256_of({k: v for k, v in p.items()
                                        if k not in ("created_at",
                                                     "updated_at")}),
                           f"run/v{got['asset_version']+1}"),
                 expected_version=got["asset_version"],
                 drop=("created_at", "updated_at"))
    return res


def set_stage(store, *, run_id: str, repository_id: str, stage: str,
              state: str, input_digest: str = "", operation_id: str = "",
              expected_outputs=None, actual_outputs=None,
              error_code: str = None, updated_at: str = "") -> dict:
    """记录阶段状态。"""
    if stage not in STAGES:
        return {"ok": False, "state": REJECTED, "reason_code": "UNKNOWN_STAGE"}

    def _mut(p):
        for s in p["stages"]:
            if s["stage"] == stage:
                s["state"] = state
                s["input_digest"] = input_digest
                s["operation_id"] = operation_id
                s["expected_outputs"] = list(expected_outputs or [])
                s["actual_outputs"] = list(actual_outputs or [])
                s["error_code"] = error_code
                s["checkpoint_version"] = p.get("checkpoint_version", 0)
                break
        p["current_stage"] = stage
        if state == STAGE_FAILED_FATAL:
            p["execution_status"] = FAILED
        elif state == STAGE_FAILED_RETRYABLE:
            p["execution_status"] = FAILED
        elif state == STAGE_UNKNOWN:
            p["execution_status"] = UNKNOWN
        elif state == STAGE_RUNNING:
            p["execution_status"] = UNKNOWN   # 运行中不算 SUCCESS
    return update_run(store, run_id=run_id,
                      repository_id=repository_id, mutate=_mut,
                      updated_at=updated_at)


def finish_run(store, *, run_id: str, repository_id: str, execution_status: str,
               result_ref: str = None, updated_at: str = "") -> dict:
    if execution_status not in EXEC_STATES:
        return {"ok": False, "state": REJECTED,
                "reason_code": "INVALID_EXECUTION_STATUS"}

    def _mut(p):
        p["execution_status"] = execution_status
        p["result_ref"] = result_ref
        if execution_status == SUCCESS:
            for s in p["stages"]:
                if s["state"] == STAGE_RUNNING:
                    s["state"] = STAGE_COMMITTED
    return update_run(store, run_id=run_id, repository_id=repository_id,
                      mutate=_mut, updated_at=updated_at)


def stage_view(store, *, run_id: str, repository_id: str) -> dict:
    """阶段确定性判定：未开始 / 已提交 / 未知 / 失败可重试 / 失败不可重试。"""
    got = read_run(store, run_id=run_id, repository_id=repository_id)
    if not got.get("ok"):
        return {"ok": False, "error": "NOT_FOUND"}
    p = got["payload"]
    return {"ok": True,
            "execution_status": p["execution_status"],
            "current_stage": p["current_stage"],
            "stages": {s["stage"]: s["state"] for s in p["stages"]}}


def ingest_result(store, *, run_id: str, repository_id: str,
                  result: dict, completed_at: str = "") -> dict:
    """登记最小完成结果。**execution_status 与 verification_status 分开。**"""
    li = "SL-RESULT-" + L.sha256_of({"run_id": run_id})[:32]
    payload = dict(result)
    payload["run_id"] = run_id
    payload["result_id"] = li
    payload.pop("completed_at", None)
    payload.pop("created_at", None)
    return _write(store, asset_type=RESULT_ASSET, li=li,
                  repo_id=repository_id, payload=payload,
                  op_id=_op("result", li,
                            L.sha256_of(payload), "result/1"),
                  expected_version=None,
                  drop=("completed_at", "created_at"))


def read_result(store, *, run_id: str, repository_id: str) -> dict:
    li = "SL-RESULT-" + L.sha256_of({"run_id": run_id})[:32]
    row = _latest(store, RESULT_ASSET, li, repository_id)
    if row is None:
        return {"ok": False, "error": "NOT_FOUND"}
    return {"ok": True, "payload": json.loads(row["payload_json"])}


def count_runs(store, *, repository_id: str, candidate_id: str = None) -> dict:
    """统计执行记录。"""
    try:
        rows = store.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type=? AND repository_id=?",
            (RUN_ASSET, repository_id)).fetchall()
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    out = []
    for r in rows:
        p = json.loads(r["payload_json"])
        if candidate_id and p.get("candidate_id") != candidate_id:
            continue
        out.append(p)
    return {"ok": True, "runs": out, "total": len(out)}
