#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候选生成门禁（15 条严格条件）。

**任何一条不成立 → 不入可执行队列，返回明确 reason_code。**
缺失、冲突、损坏都不得被转换成"没有待办"。
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

ASSESS_ASSET = "freshness_assessment"
WATCH_ASSET = "lifecycle_watch"
OBS_ASSET = "ref_observation"
CLAIM_ASSET = "claim_candidate"
VERIF_ASSET = "claim_verification"


class Gate:
    """一次门禁判定结果。"""

    def __init__(self, ok: bool, reason: str = None, detail: str = "",
                 ctx: dict = None):
        self.ok = ok
        self.reason = reason
        self.detail = detail
        self.ctx = ctx or {}


def _fail(reason, detail=""):
    return Gate(False, reason, detail)


def _asset_payload(store, asset_id: str) -> dict:
    got = store.get_asset(asset_id, verify=True)
    if not got.get("ok"):
        return {"_error": got.get("error"), "_detail": got.get("detail", "")}
    return got["asset"]


def _by_logical_identity(store, asset_type: str, logical_identity: str,
                         repository_id: str) -> dict:
    try:
        row = store.conn.execute(
            "SELECT asset_id FROM assets WHERE asset_type=? AND logical_identity=? "
            "AND repository_id=? ORDER BY asset_version DESC LIMIT 1",
            (asset_type, logical_identity, repository_id)).fetchone()
    except Exception as e:
        return {"_error": "CHECKPOINT_CORRUPT", "_detail": str(e)[:150]}
    if row is None:
        return None
    return _asset_payload(store, row["asset_id"])


def _resolve_assessment(store, assessment_id: str) -> dict:
    """按 logical_identity（assessment_id）或 asset_id 解析评估资产。"""
    if isinstance(assessment_id, str) and assessment_id.startswith("SL-A-"):
        return store.get_asset(assessment_id, verify=True)
    try:
        row = store.conn.execute(
            "SELECT asset_id FROM assets WHERE asset_type=? AND logical_identity=? "
            "ORDER BY asset_version DESC LIMIT 1",
            (ASSESS_ASSET, assessment_id)).fetchone()
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    if row is None:
        return {"ok": False, "error": "NOT_FOUND", "detail": "评估资产不存在"}
    return store.get_asset(row["asset_id"], verify=True)


def evaluate_eligibility(store, *, assessment_id: str,
                         observation_provenance: str | None = None) -> Gate:
    """逐条执行 15 个条件。返回 Gate（ok=True 时 ctx 带齐全部上下文）。"""
    # 1/2/3 Assessment 真实存在、类型正确、内容哈希可核验
    # ★ assessment_id 是 logical_identity，不是 asset_id。
    #   （初版直接当 asset_id 传，实测返回 ASSESSMENT_NOT_FOUND —— 已修）
    got = _resolve_assessment(store, assessment_id)
    if not got.get("ok"):
        if got.get("error") == "CHECKPOINT_CORRUPT":
            return _fail(R.RJ_ASSESSMENT_INTEGRITY, got.get("detail", ""))
        return _fail(R.RJ_ASSESSMENT_NOT_FOUND, "评估资产不存在")
    a_asset = got["asset"]
    if a_asset.get("asset_type") != ASSESS_ASSET:
        return _fail(R.RJ_ASSESSMENT_NOT_FOUND,
                     f"资产类型不是 {ASSESS_ASSET}")
    ap = a_asset["payload"]

    # 4 freshness_state 必须是 POSSIBLY_STALE
    if ap.get("freshness_state") != L.POSSIBLY_STALE:
        return _fail(R.RJ_NOT_POSSIBLY_STALE,
                     f"freshness_state={ap.get('freshness_state')}")

    # 5 applicability_scope 必须是 TRACKING_REF
    if ap.get("applicability_scope") != L.TRACKING_REF:
        return _fail(R.RJ_NOT_TRACKING_REF,
                     f"scope={ap.get('applicability_scope')}")

    # 14 冲突必须已核验且无冲突（缺失=未核验，不等于无冲突）
    cs = ap.get("source_evidence_conflict", L.CONFLICT_UNKNOWN)
    if cs == L.CONFLICT_DETECTED:
        return _fail(R.RJ_UNRESOLVED_CONFLICT,
                     f"冲突事实 {ap.get('conflict_fact_ids')}")
    if cs != L.CONFLICT_NONE:
        return _fail(R.RJ_CONFLICT_UNKNOWN,
                     f"冲突状态未核验: {cs}（不得当作无冲突）")

    # 6/7/8 watch 存在且一致
    w_asset = _by_logical_identity(store, WATCH_ASSET,
                                   ap.get("watch_id"),
                                   ap.get("repository_id"))
    if w_asset is None:
        return _fail(R.RJ_WATCH_NOT_FOUND, "watch 资产不存在")
    if "_error" in w_asset:
        return _fail(R.RJ_STORAGE_ERROR, w_asset["_detail"])
    wp = w_asset["payload"]
    if wp.get("watch_id") != ap.get("watch_id"):
        return _fail(R.RJ_WATCH_MISMATCH, "watch_id 不一致")
    if str(wp.get("repository_id")) != str(ap.get("repository_id")):
        return _fail(R.RJ_REPO_MISMATCH, "watch 与评估仓库不一致")
    if wp.get("requested_ref") != ap.get("requested_ref"):
        return _fail(R.RJ_REF_MISMATCH, "watch 与评估 Ref 不一致")

    # 9 baseline 与 watch 一致（Claim 的 Commit 通过 watch 传递）
    if wp.get("baseline_commit_sha") != ap.get("baseline_commit_sha"):
        return _fail(R.RJ_BASELINE_MISMATCH, "watch baseline 与评估不一致")
    if wp.get("claim_id") != ap.get("claim_id"):
        return _fail(R.RJ_CLAIM_NOT_FOUND, "watch 的 claim_id 与评估不一致")

    # 10/11 目标 Commit 可信且不同于 baseline
    target = ap.get("observed_commit_sha")
    if not L.is_commit_sha(target):
        return _fail(R.RJ_TARGET_INVALID, f"target={target!r}")
    if target == ap.get("baseline_commit_sha"):
        return _fail(R.RJ_TARGET_SAME_AS_BASE)

    # 12 Claim 真实存在
    c_asset = _by_logical_identity(store, CLAIM_ASSET, ap.get("claim_id"),
                                   ap.get("repository_id"))
    if c_asset is None:
        return _fail(R.RJ_CLAIM_NOT_FOUND, "Claim 资产不存在")
    if "_error" in c_asset:
        return _fail(R.RJ_STORAGE_ERROR, c_asset["_detail"])

    # 13 历史 Verification 可定位
    v_asset = None
    try:
        row = store.conn.execute(
            "SELECT asset_id FROM assets WHERE asset_type=? AND repository_id=? "
            "ORDER BY asset_version DESC",
            (VERIF_ASSET, wp.get("repository_id"))).fetchall()
    except Exception as e:
        return _fail(R.RJ_STORAGE_ERROR, str(e)[:150])
    src_vid = None
    for r in row:
        v_full = _asset_payload(store, r["asset_id"])
        if "_error" in v_full:
            return _fail(R.RJ_STORAGE_ERROR, v_full["_detail"])
        # ★ _asset_payload 返回的是**整个 asset**，claim_id 在其 payload 内部。
        #   （初版直接 vp.get("claim_id") 取不到 → 误报 VERIFICATION_NOT_FOUND）
        vp = v_full.get("payload") or {}
        if vp.get("claim_id") == ap.get("claim_id"):
            v_asset = vp
            src_vid = vp.get("verification_id")
            break
    if v_asset is None:
        return _fail(R.RJ_VERIFICATION_NOT_FOUND, "找不到源 Claim 的评估记录")

    # 15 观测来源级别（由调用方给出的观测 provenance，或从 evidence 推断）
    prov = observation_provenance
    if prov is None:
        prov = _infer_provenance(store, ap)
    if prov not in R.SOURCE_LEVELS:
        return _fail(R.RJ_OBSERVATION_NOT_TRUSTED, f"provenance={prov!r}")

    return Gate(True, None, "", {
        "assessment": a_asset,
        "assessment_id": ap.get("assessment_id") or a_asset["logical_identity"],
        "assessment_asset_id": a_asset["asset_id"],
        "watch": wp, "claim": c_asset, "verification": v_asset,
        "source_verification_id": src_vid,
        "target_commit_sha": target,
        "baseline_commit_sha": ap.get("baseline_commit_sha"),
        "repository_id": wp.get("repository_id"),
        "requested_ref": wp.get("requested_ref"),
        "source_level": prov,
        "conflict_state": cs,
        "claim_id": ap.get("claim_id"),
        "watch_id": ap.get("watch_id"),
        "canonical_scope": (ap.get("canonical_scope")
                            or wp.get("retrieval_scope")
                            or "full_tree_enumeration"),
    })


def _infer_provenance(store, ap: dict) -> str:
    """从评估的 evidence_refs 推断观测来源等级。"""
    evs = ap.get("evidence_refs") or []
    # ★ 先扫一遍 synthetic 标记 —— 它优先级最高，不能被后续分支覆盖
    for ev in evs:
        if isinstance(ev, dict):
            if (ev.get("kind") == "synthetic_test_injection"
                    or ev.get("synthetic_provenance") is True):
                return R.SRC_SYNTHETIC
    for ev in evs:
        if isinstance(ev, dict):
            kind = ev.get("kind", "")
            lvl = ev.get("provenance_level")
            if lvl in R.SOURCE_LEVELS:
                return lvl
            if kind == "ref_resolution":
                return R.SRC_REAL
            if kind == "ref_resolution_failed":
                return R.SRC_HISTORICAL
            if ev.get("ref", "").startswith(("record:", "snapshot:")):
                return R.SRC_HISTORICAL
    # 无法推断 → 不可信
    return "UNKNOWN_SOURCE"


def build_candidate(gate_ctx: dict, *, created_at: str = "") -> R.RevalidationCandidate:
    """由已通过门禁的上下文构造候选。"""
    cid = R.make_candidate_id(
        watch_id=gate_ctx["watch_id"],
        source_claim_id=gate_ctx["claim_id"],
        target_commit_sha=gate_ctx["target_commit_sha"],
        repository_id=gate_ctx["repository_id"],
        canonical_scope=gate_ctx["canonical_scope"])

    # ★ 新目标 Commit 的 Claim 身份可确定性计算（P2B 契约：身份含 commit）
    expected_target_claim = _expected_target_claim_id(gate_ctx)

    status = R.PROPOSED
    state_reason = ""
    if gate_ctx["source_level"] not in R.DISPATCHABLE_SOURCES:
        # 非 REAL_LIVE_API → 只能 BLOCKED（保留可追溯性，不伪造可执行性）
        status = R.BLOCKED
        state_reason = R.RJ_SYNTHETIC_NOT_DISPATCHABLE

    return R.RevalidationCandidate(
        candidate_id=cid, watch_id=gate_ctx["watch_id"],
        source_claim_id=gate_ctx["claim_id"],
        source_verification_id=gate_ctx["source_verification_id"],
        repository_id=str(gate_ctx["repository_id"]),
        requested_ref=gate_ctx["requested_ref"],
        baseline_commit_sha=gate_ctx["baseline_commit_sha"],
        target_commit_sha=gate_ctx["target_commit_sha"],
        canonical_scope=gate_ctx["canonical_scope"],
        revalidation_rule_version=R.REVALIDATION_RULE_VERSION,
        status=status, reason_code=None, source_level=gate_ctx["source_level"],
        source_assessment_id=gate_ctx["assessment_id"],
        observation_id=None, expected_target_claim_identity=expected_target_claim,
        revalidation_of=gate_ctx["source_verification_id"],
        state_reason=state_reason, created_at=created_at,
        conflict_state=gate_ctx["conflict_state"])


def _expected_target_claim_id(ctx: dict) -> str | None:
    """按 P2B 的 Claim 身份契约计算目标 Commit 的 Claim 身份。

    P2B: claim_id = H(repo, commit, claim_type, 规范化参数, schema)
    参数来自源 Claim 的 payload（路径、expected_exists）。
    缺必要参数 → 返回 None（记录待生成条件，不猜）。
    """
    try:
        cp = ctx["claim"]["payload"]
        path = cp["normalized_path"]
        expected_exists = cp["expected_exists"]
        claim_type = cp["claim_type"]
        schema = cp.get("claim_schema_version", "claim-schema/1")
    except (KeyError, TypeError):
        return None
    import hashlib as _h, json as _j
    params = {"normalized_path": path, "expected_exists": expected_exists}
    payload = {"repository_id": str(ctx["repository_id"]),
               "commit_sha": ctx["target_commit_sha"],
               "claim_type": claim_type,
               "normalized_parameters": params,
               "claim_schema_version": schema}
    raw = _j.dumps(payload, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"))
    return "SL-CLAIM-" + _h.sha256(raw.encode()).hexdigest()[:40]
