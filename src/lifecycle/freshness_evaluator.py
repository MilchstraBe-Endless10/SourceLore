#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新鲜度评估：把观测结果翻译成 freshness_state。

契约：SL-CAP-0042（内容变化与失效处理）、SL-CAP-0045（外部可变来源与时效）。

**核心铁律：**
  F1 固定 Commit 的 Claim 不因 HEAD 移动而改变 → NOT_APPLICABLE_TO_PINNED
  F2 观测不到 → UNKNOWN，绝不推断已更新
  F3 observed != baseline → POSSIBLY_STALE，**不标 refuted**
  F4 不同仓库/不同 Ref 不互相影响
  F5 强制推送不假定快进
  F6 本模块**不修改**任何 EC 对象
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "collector"),
           str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lc_models as L

ASSESS_RULE_VERSION = "freshness-eval/v1"


def assess(*, watch, observation, observed_at: str = "",
           assessed_at: str = "", rule_version: str = ASSESS_RULE_VERSION
           ) -> L.FreshnessAssessment:
    """对一条 watch + 一次观测产出新鲜度评估。"""
    base = dict(
        watch_id=watch.watch_id, claim_id=watch.claim_id,
        repository_id=watch.repository_id,
        requested_ref=watch.requested_ref,
        baseline_commit_sha=watch.baseline_commit_sha,
        rule_version=rule_version,
        applicability_scope=watch.applicability_scope,
        observed_at=observed_at, assessed_at=assessed_at)

    # F1：固定版本不追踪移动 Ref
    if watch.applicability_scope == L.PINNED_COMMIT:
        return _build(**base, observed_commit_sha=None,
                      state=L.NOT_APPLICABLE_TO_PINNED, reason=None,
                      evidence_refs=[], detail="固定 Commit 的命题不追踪移动 Ref")

    # 归属校验：仓库 / Ref 必须匹配
    if str(observation.repository_id) != str(watch.repository_id):
        return _unknown(**base, reason=L.U_REPO_MISMATCH, observed=None,
                        detail="观测仓库与 watch 不匹配")
    if observation.requested_ref != watch.requested_ref:
        return _unknown(**base, reason=L.U_REF_MISMATCH, observed=None,
                        detail="观测 Ref 与 watch 不匹配")

    # F2：没有可信观测 → UNKNOWN
    if observation.observation_status != L.OBS_OK:
        return _unknown(**base,
                        reason=(observation.failure_reason
                                or L.U_OBSERVATION_FAILED),
                        observed=None,
                        detail="无可信 Ref 观测",
                        evidence=observation.evidence_refs)

    obs_sha = observation.resolved_commit_sha
    if not L.is_commit_sha(obs_sha):
        return _unknown(**base, reason=L.U_COMMIT_MALFORMED, observed=None,
                        detail="观测到的 commit 非法")

    if observation.retrieval_scope != watch.retrieval_scope:
        return _unknown(**base, reason=L.U_SCOPE_MISMATCH, observed=obs_sha,
                        detail="采集范围与 watch 不一致")

    # 情况 A：Commit 未变
    if obs_sha == watch.baseline_commit_sha:
        return _build(**base, observed_commit_sha=obs_sha,
                      state=L.VERSION_ALIGNED, reason=None,
                      evidence_refs=observation.evidence_refs,
                      detail="跟踪 Ref 的 Commit 与基线一致（仅版本对齐）")

    # 情况 B/F：Commit 变化 → POSSIBLY_STALE（不假定快进、不标 refuted）
    return _build(**base, observed_commit_sha=obs_sha,
                  state=L.POSSIBLY_STALE, reason=L.R_REF_MOVED,
                  evidence_refs=observation.evidence_refs,
                  detail=(f"跟踪 Ref 由 {watch.baseline_commit_sha[:12]}… 移动到 "
                          f"{obs_sha[:12]}…；旧 Claim 可能不再适用，但**未被推翻**。"
                          "未验证祖先关系（不假定快进）"))


def _assess_id(**kw) -> str:
    return L.make_assessment_id(
        watch_id=kw["watch_id"], claim_id=kw["claim_id"],
        repository_id=kw["repository_id"],
        requested_ref=kw["requested_ref"],
        baseline_commit_sha=kw["baseline_commit_sha"],
        observed_commit_sha=kw.get("observed_commit_sha"),
        freshness_state=kw["state"], reason_code=kw.get("reason"),
        rule_version=kw["rule_version"],
        applicability_scope=kw["applicability_scope"])


def _build(*, watch_id, claim_id, repository_id, requested_ref,
           baseline_commit_sha, rule_version, applicability_scope,
           observed_commit_sha, state, reason, evidence_refs,
           observed_at="", assessed_at="", detail="") -> L.FreshnessAssessment:
    aid = L.make_assessment_id(
        watch_id=watch_id, claim_id=claim_id, repository_id=repository_id,
        requested_ref=requested_ref, baseline_commit_sha=baseline_commit_sha,
        observed_commit_sha=observed_commit_sha, freshness_state=state,
        reason_code=reason, rule_version=rule_version,
        applicability_scope=applicability_scope)
    digest = L.sha256_of({"kind": "freshness", "id": aid,
                          "baseline": baseline_commit_sha,
                          "observed": observed_commit_sha,
                          "state": state, "reason": reason})
    return L.FreshnessAssessment(
        assessment_id=aid, watch_id=watch_id, claim_id=claim_id,
        repository_id=repository_id, requested_ref=requested_ref,
        baseline_commit_sha=baseline_commit_sha,
        observed_commit_sha=observed_commit_sha, freshness_state=state,
        reason_code=reason, evidence_refs=list(evidence_refs),
        rule_version=rule_version, input_digest=digest,
        applicability_scope=applicability_scope,
        observed_at=observed_at, assessed_at=assessed_at, detail=detail)


def _unknown(*, watch_id, claim_id, repository_id, requested_ref,
             baseline_commit_sha, rule_version, applicability_scope,
             reason, observed, observed_at="", assessed_at="",
             detail="", evidence=()) -> L.FreshnessAssessment:
    if reason not in L.UNKNOWN_REASONS:
        reason = L.U_OBSERVATION_FAILED
    return _build(watch_id=watch_id, claim_id=claim_id,
                  repository_id=repository_id, requested_ref=requested_ref,
                  baseline_commit_sha=baseline_commit_sha,
                  rule_version=rule_version,
                  applicability_scope=applicability_scope,
                  observed_commit_sha=observed, state=L.UNKNOWN, reason=reason,
                  evidence_refs=list(evidence), observed_at=observed_at,
                  assessed_at=assessed_at, detail=detail)
