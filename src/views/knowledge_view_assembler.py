#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KnowledgeViewAssembler —— 纯只读、确定性投影。

★ 本模块**绝不做**：采集、抽 Fact、验 Claim、推新鲜度、改 review、
   改指针、入队、联网。它只读已提交的权威资产并投影。

★ 五条状态轴各自独立输出，不合并成 is_valid。
"""

import sys, json
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "lifecycle"), str(_HERE.parent / "storage"),
           str(_HERE.parent / "evidence_claims"), str(_HERE.parent / "runtime")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import view_models as VM
import view_integrity as VI
import lc_models as L

RUN_ASSET = "revalidation_run"
QUEUE_ASSET = "revalidation_queue"
ASSESS_ASSET = "freshness_assessment"


def assemble_from_verification(store, *, verification_id=None,
                               verification_asset_id=None,
                               repository_id=None,
                               query_scope="claim_version") -> dict:
    """装配单个 (Claim, Verification) 的只读视图。

    失败时返回明确诊断码，**不返回"没有知识"**。
    """
    repo = str(repository_id) if repository_id is not None else None

    verif, err = VI.resolve_verification(
        store, verification_id=verification_id,
        asset_id=verification_asset_id, repository_id=repo)
    if verif is None:
        return _fail(err or VM.E_VERIFICATION_NOT_FOUND,
                     "Verification 无法定位")
    if not repo:
        repo = str(verif["repository_id"])

    vp = verif["payload"]
    claim, cerr = VI.resolve_claim(store, claim_id=vp.get("claim_id"),
                                   repository_id=repo)
    if claim is None:
        return _fail(cerr or VM.E_CLAIM_NOT_FOUND,
                     f"Verification 引用的 Claim {vp.get('claim_id')} 无法定位")

    link_err = VI.check_link(claim, verif)
    if link_err:
        return _fail(link_err, "Claim 与 Verification 关联不成立")

    chain_err, chain = VI.check_fact_chain(store, verif)
    if chain_err == VM.E_EVIDENCE_CORRUPT:
        return _fail(VM.E_EVIDENCE_CORRUPT,
                     f"证据链损坏: {chain['damaged'][:2]}")
    # ★ no_evidence（本次裁决无可用证据）不是损坏 —— 视图照常装配，
    #   并由 verification_status=insufficient_evidence 与 limitations 表达。

    cp = claim["payload"]
    claim_commit = cp.get("commit_sha")
    vparams = vp.get("normalized_verification_params") or {}
    v_commit = vparams.get("commit_sha")
    if claim_commit and v_commit and claim_commit != v_commit:
        return _fail(VM.E_COMMIT_MISMATCH,
                     f"Claim commit {claim_commit} != Verification commit {v_commit}")

    # ── A. 证据裁决（只读 EC 结果，不重算）───────────────
    verification_status = vp.get("status")
    if verification_status not in ("supported", "refuted", "insufficient_evidence"):
        return _fail(VM.E_VIEW_INTEGRITY_FAILED,
                     f"非法裁决状态 {verification_status!r}")

    # ── B. 新鲜度（只读 Lifecycle 结果）──────────────────
    run = _read_run_for_target(store, target_claim_id=cp.get("claim_id"),
                               repository_id=repo)
    fresh = _read_freshness(store, claim_id=cp.get("claim_id"),
                            repository_id=repo, run=run)
    freshness_state = fresh.get("freshness_state")
    if freshness_state is not None and freshness_state not in L.FRESHNESS_STATES:
        return _fail(VM.E_VIEW_INTEGRITY_FAILED,
                     f"非法新鲜度状态 {freshness_state!r}")

    # ── C. 人工审核（只读，绝不改）──────────────────────
    review_status = cp.get("review_status", "pending_review")

    # ── D. 执行（只读 run；上面已读）─────────────────────
    execution_status = run.get("execution_status") if run else None
    auth_class = _auth_class_of(run)

    # ── E. 来源与授权（**分别判断**）─────────────────────
    provenance = _provenance_of(fresh=fresh, run=run, chain=chain)

    # ★ 局部覆盖的判断要看**快照本身的完整性**，不能只依赖 EC 的
    #   local_coverage_only 标记（那是 EC 的判定，不是来源事实）。
    coverage_scope = None
    snapshot_partial = False
    for s in chain.get("snapshots", []):
        comp = (s["payload"].get("completeness_status") or "").upper()
        trunc = bool(s["payload"].get("tree_truncated_seen"))
        if comp and comp != "COMPLETE":
            snapshot_partial = True
            coverage_scope = comp
        elif trunc:
            snapshot_partial = True
            coverage_scope = coverage_scope or "TRUNCATED"
    # ★ 证据链里没有快照时（no_usable_evidence），覆盖率信息只能来自执行记录。
    run_cov = (run or {}).get("source_snapshot_completeness")
    if run_cov and str(run_cov).upper() != "COMPLETE":
        snapshot_partial = True
        coverage_scope = coverage_scope or str(run_cov).upper()
    partial = bool(vp.get("local_coverage_only")) or snapshot_partial
    if partial and coverage_scope is None:
        coverage_scope = "PARTIAL"

    limitations = VM.limitations_of(
        verification_status=verification_status,
        freshness_state=freshness_state,
        review_status=review_status,
        provenance_level=provenance.get("provenance_level"),
        execution_status=execution_status,
        partial_coverage=partial,
        coverage_scope=coverage_scope)

    # 证据不足不得当成否定
    if verification_status == "insufficient_evidence":
        limitations.append("insufficient_evidence 不得转写为否定结论")

    source_refs = sorted({claim["asset_id"], verif["asset_id"]}
                         | {f["asset_id"] for f in chain.get("facts", [])}
                         | {s["asset_id"] for s in chain.get("snapshots", [])})
    digests = sorted({claim["content_hash"], verif["content_hash"]}
                     | {f["content_hash"] for f in chain.get("facts", [])}
                     | {s["content_hash"] for s in chain.get("snapshots", [])})

    history_refs = {
        "source_claim_id": run.get("source_claim_id") if run else None,
        "source_verification_id": run.get("source_verification_id") if run else None,
        "candidate_id": run.get("candidate_id") if run else None,
        "revalidation_of": run.get("source_claim_id") if run else None,
        "relation": "revalidated_at_newer_commit" if run else None,
    }

    view_id = VM.make_view_id(
        query_scope=query_scope, source_asset_refs=source_refs,
        content_digests=digests, subject_id=cp.get("normalized_path"))

    out = {
        "view_id": view_id,
        "view_schema_version": VM.VIEW_SCHEMA_VERSION,
        "projection_rule_version": VM.PROJECTION_RULE_VERSION,
        "query_scope": query_scope,
        "status": VM.OK,

        "repository_id": repo,
        "subject_id": cp.get("normalized_path"),

        # A. 证据裁决
        "claim_id": cp.get("claim_id"),
        "claim_type": cp.get("claim_type"),
        "claim_commit_sha": claim_commit,
        "claim_payload": _claim_summary(cp),
        "verification_id": vp.get("verification_id"),
        "verification_status": verification_status,
        "verification_rule_version": vp.get("rule_version"),
        "verification_evidence_level": vp.get("evidence_level"),

        # B. 新鲜度
        "applicability_scope": fresh.get("applicability_scope"),
        "freshness_state": freshness_state,
        "watch_id": fresh.get("watch_id"),
        "requested_ref": fresh.get("requested_ref"),
        "observed_commit_sha": fresh.get("observed_commit_sha"),
        "baseline_commit_sha": fresh.get("baseline_commit_sha"),
        "last_observed_at": fresh.get("observed_at"),
        "freshness_reason_code": fresh.get("reason_code"),
        "source_evidence_conflict": fresh.get("source_evidence_conflict"),
        "current_applicability": _current_applicability(fresh),

        # C. 人工审核
        "review_status": review_status,
        "human_authored": cp.get("human_authored"),

        # D. 执行
        "execution_run_ref": run.get("run_id") if run else None,
        "execution_status": execution_status,
        "execution_stages": run.get("current_stage") if run else None,

        # E. 来源 + 授权（分开）
        "provenance_level": provenance.get("provenance_level"),
        "provenance_basis": provenance.get("basis"),
        # ★ 分层保留，不合并成单一"来源"
        "evidence_source_level": provenance.get("evidence_source_level"),
        "execution_source_level": provenance.get("execution_source_level"),
        "snapshot_source_level": provenance.get("snapshot_source_level"),
        "snapshot_source_provider": provenance.get("snapshot_source_provider"),
        "mixed_provenance": provenance.get("mixed_provenance", False),
        "authorization_class": auth_class.get("authorization_class"),
        "authorization_kind": auth_class.get("authorization_kind"),
        "authorization_is_test_only": auth_class.get("test_only"),

        # 证据
        "evidence_refs": _normalize_refs(vp.get("evidence_refs"),
                                         fresh.get("evidence_refs")),
        "source_snapshot_refs": sorted({s["asset_id"]
                                        for s in chain.get("snapshots", [])}),
        "fact_refs": sorted({f["payload"].get("fact_id")
                             for f in chain.get("facts", [])}),
        "local_coverage_only": partial,
        # ★ 明确区分"没有可用证据"与"证据损坏"
        "no_usable_evidence": bool(chain.get("no_evidence")),
        "coverage_scope": coverage_scope,

        # 限制与门禁
        "limitations": limitations,
        "conflict_indicators": {
            "evidence_conflict_detected": bool(vp.get("conflict_detected")),
            "evidence_conflict_fact_ids": list(vp.get("conflict_fact_ids") or []),
            "source_evidence_conflict": fresh.get("source_evidence_conflict"),
        },
        "history_refs": history_refs,
        "distribution_restrictions": VM.distribution_restrictions(),
    }
    return {"ok": True, "view": out, "view_id": view_id}


# ── 只读辅助 ───────────────────────────────────────────────
def _read_freshness(store, *, claim_id, repository_id,
                    run=None) -> dict:
    """读取与**本 Claim** 相关的新鲜度评估。

    ★ 新鲜度评估绑定的是 watch 的基线 Claim（例如 A），
      而重新验证的目标 Claim（B）通常没有对应评估 —— 这种情况下
      不得借用 A 的评估冒充 B 的，必须如实返回"无对应评估"。
    """
    row = store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type=? AND repository_id=? "
        "ORDER BY asset_version DESC LIMIT 1",
        (ASSESS_ASSET, repository_id)).fetchall()
    best = None
    for r in row:
        try:
            p = json.loads(r["payload_json"])
        except Exception:
            continue
        if p.get("claim_id") == claim_id:
            best = p
            break
    if best:
        return best
    # 目标版本没有直接评估：只用**同一 run** 携带的 freshness_context 作
    # 上下文提示，并明确标注它不是该 Claim 的评估结论。
    if run and run.get("freshness_context"):
        return {"freshness_state": None,
                "context_only": True,
                "observed_commit_sha": run["freshness_context"].get(
                    "observed_commit_sha"),
                "baseline_commit_sha": run["freshness_context"].get(
                    "baseline_commit_sha"),
                "detail": "该版本无对应的新鲜度评估，仅有执行上下文"}
    return {}


def _read_run_for_target(store, *, target_claim_id, repository_id) -> dict:
    rows = store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type=? AND repository_id=? "
        "ORDER BY asset_version DESC", (RUN_ASSET, repository_id)).fetchall()
    for r in rows:
        try:
            p = json.loads(r["payload_json"])
        except Exception:
            continue
        if p.get("target_claim_id") == target_claim_id:
            return p
    # 结果资产里也有 run_id
    rows = store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type='revalidation_result' "
        "AND repository_id=? ORDER BY asset_version DESC", (repository_id,)).fetchall()
    for r in rows:
        try:
            p = json.loads(r["payload_json"])
        except Exception:
            continue
        if p.get("target_claim_id") == target_claim_id:
            return p
    return {}


def _auth_class_of(run) -> dict:
    if not run:
        return {"authorization_class": None, "authorization_kind": None,
                "test_only": None}
    kind = run.get("auth_kind")
    test_only = run.get("test_only")
    if test_only is True:
        cls = "TEST_ONLY_ISOLATED"
    elif kind in ("HUMAN_OPERATOR", "PLATFORM_APPROVAL") and not test_only:
        cls = "VERIFIABLE_PRODUCTION"
    elif kind == "DEV_BATCH_APPROVAL":
        cls = "DEVELOPMENT_BATCH_ONLY"
    elif kind is None:
        cls = None
    else:
        cls = "UNKNOWN"
    return {"authorization_class": cls, "authorization_kind": kind,
            "test_only": test_only, "auth_ref": run.get("auth_ref")}


def _provenance_of(*, fresh, run, chain) -> dict:
    """★ 来源真实性与授权有效性**分别**判断。

    两个层次分开记录，绝不混为一谈：
      evidence_source_level  —— 候选/评估观测的来源（决定知识可不可信）
      execution_source_level —— 本次实际取数用的 adapter 来源
      snapshot_source_provider —— 快照采集自哪个 provider（如 github）

    合成来源不因"有真实历史数据"被标成历史；
    真实 GitHub 输入不因"用了测试授权"自动变成生产运行。
    """
    layers = {}
    basis = []

    ev = (fresh or {}).get("provenance_level")
    if ev:
        layers["evidence_source_level"] = ev
        basis.append("freshness_observation")

    ex = (run or {}).get("execution_source_level")
    if ex:
        layers["execution_source_level"] = ex
        basis.append("executor_adapter")

    providers = set()
    for s_ in chain.get("snapshots", []):
        sp = s_["payload"]
        ne = sp.get("normalized_evidence") or {}
        pl = ne.get("provenance_level") or sp.get("provenance_level")
        if pl:
            layers.setdefault("snapshot_source_level", pl)
            basis.append("snapshot")
        if sp.get("source_provider"):
            providers.add(sp["source_provider"])
    if providers:
        layers["snapshot_source_provider"] = sorted(providers)

    # 综合等级：以最弱的一层为准（保守）
    order = {"REAL_LIVE_API": 3, "HISTORICAL_REAL_DATA": 2,
             "SYNTHETIC_FIXTURE": 1}
    levels = [v for k, v in layers.items() if k.endswith("_level")]
    if levels:
        weakest = min(levels, key=lambda x: order.get(x, 0))
        layers["provenance_level"] = weakest
        if len(set(levels)) > 1:
            layers["mixed_provenance"] = True
    else:
        # ★ 无法判定就报未知，绝不猜成真实
        layers["provenance_level"] = None
        basis.append("undetermined")

    layers["basis"] = sorted(set(basis))
    return layers


def _current_applicability(fresh) -> str:
    """★ 历史观测绝不冒充当前实时状态。"""
    if not fresh:
        return VM.E_CURRENT_APPLICABILITY_UNKNOWN
    if fresh.get("provenance_level") == "SYNTHETIC_FIXTURE":
        return "SYNTHETIC_ONLY"
    state = fresh.get("freshness_state")
    if state == L.VERSION_ALIGNED:
        return "ALIGNED_AT_OBSERVATION_TIME_ONLY"
    if state == L.POSSIBLY_STALE:
        return "STALE_AT_OBSERVATION_TIME"
    if state == L.UNKNOWN:
        return VM.E_CURRENT_APPLICABILITY_UNKNOWN
    if state == L.NOT_APPLICABLE_TO_PINNED:
        return "PINNED_COMMIT_IMMUTABLE"
    return VM.E_CURRENT_APPLICABILITY_UNKNOWN


def _normalize_refs(*sources) -> list:
    """evidence_refs 可能是字符串或结构化 dict；统一成可排序的规范形态。

    ★ 不做语义改写，只做确定性规范化：dict 转成按键排序的 JSON 串。
    """
    seen = []
    for src in sources:
        for r in (src or []):
            if isinstance(r, str):
                key = r
            elif isinstance(r, dict):
                key = json.dumps(r, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"))
            else:
                key = json.dumps(r, ensure_ascii=False, default=str)
            if key not in seen:
                seen.append(key)
    return sorted(seen)


def _claim_summary(cp) -> dict:
    return {k: cp.get(k) for k in
            ("claim_type", "normalized_path", "expected_exists",
             "claim_scope", "claim_schema_version")}


def _fail(code, detail) -> dict:
    return {"ok": False, "status": code, "error_code": code,
            "detail": detail, "view": None}
