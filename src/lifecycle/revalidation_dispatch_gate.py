#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控调度闸门：只产出计划，不执行任何真实工作。

**三个事件必须分开：**
  PLAN_READY          计划已生成
  EXECUTION_AUTHORIZED 有人类授权且范围覆盖本目标
  EXECUTION_COMPLETED  真正执行完成

P3B **最多完成 PLAN_READY**。绝不调用 Collector / Facts / EC。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage"),
           str(_HERE.parent / "evidence_claims")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lc_models as L
import revalidation_models as R
from revalidation_queue import read_candidate, read_queue

P_GATE_NOT_PROPOSED = "CANDIDATE_NOT_PROPOSED"
P_GATE_SOURCE_NOT_DISPATCHABLE = "SOURCE_NOT_DISPATCHABLE"
P_GATE_CONFLICT_UNRESOLVED = "CONFLICT_UNRESOLVED"
P_GATE_CANDIDATE_NOT_ACTIVE = "CANDIDATE_NOT_ACTIVE"
P_GATE_STORAGE = "STORAGE_ERROR"

PLAN_KIND = "revalidation_plan/dry-run"


def prepare_revalidation_plan(store, *, candidate_id: str,
                              repository_id: str) -> dict:
    """只读生成计划。**不触发任何工具。**"""
    got = read_candidate(store, candidate_id=candidate_id,
                         repository_id=repository_id)
    if not got.get("ok"):
        return {"ok": False, "gate": P_GATE_STORAGE, "detail": got.get("error")}
    p = got["payload"]

    if p.get("status") != R.PROPOSED:
        return {"ok": False, "gate": P_GATE_NOT_PROPOSED,
                "status": p.get("status"),
                "detail": "只有 PROPOSED 候选可生成计划"}

    if p.get("source_level") not in R.DISPATCHABLE_SOURCES:
        return {"ok": False, "gate": P_GATE_SOURCE_NOT_DISPATCHABLE,
                "source_level": p.get("source_level"),
                "detail": (f"{p.get('source_level')} 来源不得进入真实调度；"
                           "合成/历史数据只能用于测试或回放")}

    if p.get("conflict_state") != L.CONFLICT_NONE:
        return {"ok": False, "gate": P_GATE_CONFLICT_UNRESOLVED,
                "conflict_state": p.get("conflict_state")}

    q = read_queue(store, watch_id=p["watch_id"], repository_id=repository_id)
    if not q.get("ok"):
        return {"ok": False, "gate": P_GATE_STORAGE, "detail": q.get("detail")}
    if q.get("active_candidate_id") != candidate_id:
        return {"ok": False, "gate": P_GATE_CANDIDATE_NOT_ACTIVE,
                "active": q.get("active_candidate_id"),
                "detail": "候选不是当前活动候选，不生成计划"}

    plan = {
        "plan_kind": PLAN_KIND,
        "gate": R.GATE_PLAN_READY,
        "candidate_id": candidate_id,
        "watch_id": p["watch_id"],
        "repository_id": p["repository_id"],
        "requested_ref": p["requested_ref"],
        "source_claim_id": p["source_claim_id"],
        "source_verification_id": p["source_verification_id"],
        "baseline_commit_sha": p["baseline_commit_sha"],
        "target_commit_sha": p["target_commit_sha"],
        "target_claim_parameters": {
            "repository_id": p["repository_id"],
            "commit_sha": p["target_commit_sha"],
            "expected_target_claim_identity":
                p.get("expected_target_claim_identity"),
        },
        "intended_collector_scope": p["canonical_scope"],
        "intended_fact_rules": ["file_path_observation@v1"],
        "intended_ec_rule_version": "path-exists-verifier/v1",
        "authorization_required": True,
        "expected_artifacts": [
            "source_snapshot@target_commit",
            "extracted_fact@target_claim",
            "claim_candidate@target_claim",
            "claim_verification@target_claim",
        ],
        "execution_prerequisites": [
            "human_authorization_for_this_target_commit",
            "REAL_LIVE_API_observation_of_target_ref",
            "no_unresolved_conflict",
        ],
        "events_distinguished": {
            "PLAN_READY": True,
            "EXECUTION_AUTHORIZED": False,
            "EXECUTION_COMPLETED": False,
        },
        "side_effects": {
            "called_collector": False,
            "called_github": False,
            "extracted_facts": False,
            "adjudicated_claims": False,
            "modified_verification": False,
            "modified_review_status": False,
        },
        "note": ("本计划仅为建议。P3B 不执行；真正重新验证属于下一批，"
                 "且必须有可追溯的人类授权覆盖 target_commit_sha。"),
    }
    return {"ok": True, "gate": R.GATE_PLAN_READY, "plan": plan}


def assert_no_authorization(plan: dict) -> None:
    """断言计划未被误标为已授权/已完成。"""
    ev = plan.get("events_distinguished", {})
    if ev.get("EXECUTION_AUTHORIZED") is not False:
        raise AssertionError("计划不得声称已获得执行授权")
    if ev.get("EXECUTION_COMPLETED") is not False:
        raise AssertionError("计划不得声称已执行完成")
