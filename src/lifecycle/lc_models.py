#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lifecycle 数据模型。

契约：SL-CAP-0040～0045。

**五类状态必须独立，任何一类都不能替代另一类：**
  verification_status  EC 的证据裁决（supported/refuted/insufficient）
  knowledge_freshness  Lifecycle 的时效评估（本模块产出）
  review_status        人类审核（只能人改）
  execution_status     任务执行（Runtime/Checkpoint）
  source_completeness  Collector 的来源覆盖完整性

**六条禁止（写死在代码里，不靠约定）：**
  possibly_stale      -> refuted          ✗
  supported           -> 永久新鲜        ✗
  新 Commit           -> 旧 Claim 自动 false ✗
  Checkpoint 恢复成功  -> 知识仍有效      ✗
  人工审核通过         -> 跳过事实验证    ✗
  PARTIAL 来源        -> 自动判定过时    ✗
"""

import hashlib, json, re
from dataclasses import dataclass, field
from typing import Optional

# ── 适用范围 ────────────────────────────────────────────────
PINNED_COMMIT = "PINNED_COMMIT"
TRACKING_REF = "TRACKING_REF"
APPLICABILITY_SCOPES = frozenset({PINNED_COMMIT, TRACKING_REF})

# ── 新鲜度状态 ──────────────────────────────────────────────
NOT_APPLICABLE_TO_PINNED = "NOT_APPLICABLE_TO_PINNED"
VERSION_ALIGNED = "VERSION_ALIGNED"
POSSIBLY_STALE = "POSSIBLY_STALE"
UNKNOWN = "UNKNOWN"
FRESHNESS_STATES = frozenset({NOT_APPLICABLE_TO_PINNED, VERSION_ALIGNED,
                              POSSIBLY_STALE, UNKNOWN})

# ── 观测状态 ────────────────────────────────────────────────
OBS_OK = "OBSERVED"
OBS_FAILED = "OBSERVATION_FAILED"
OBS_UNAVAILABLE = "REF_UNAVAILABLE"
OBS_STATUSES = frozenset({OBS_OK, OBS_FAILED, OBS_UNAVAILABLE})

# ── Ref 种类 ────────────────────────────────────────────────
REF_KIND_BRANCH = "BRANCH"
REF_KIND_TAG = "TAG"
REF_KIND_COMMIT = "COMMIT_SHA"
REF_KINDS = frozenset({REF_KIND_BRANCH, REF_KIND_TAG, REF_KIND_COMMIT})

# ── UNKNOWN 原因码 ──────────────────────────────────────────
U_NO_OBSERVATION = "NO_TRUSTED_OBSERVATION"
U_OBSERVATION_FAILED = "OBSERVATION_FAILED"
U_REF_UNAVAILABLE = "REF_UNAVAILABLE"
U_PERMISSION_DENIED = "PERMISSION_DENIED"
U_RATE_LIMITED = "RATE_LIMITED"
U_SNAPSHOT_MISSING = "SOURCE_SNAPSHOT_MISSING"
U_SNAPSHOT_INTEGRITY = "SOURCE_SNAPSHOT_INTEGRITY_FAILED"
U_SCOPE_MISMATCH = "SCOPE_MISMATCH"
U_REPO_MISMATCH = "REPOSITORY_MISMATCH"
U_REF_MISMATCH = "REF_MISMATCH"
U_COMMIT_MALFORMED = "COMMIT_SHA_MALFORMED"
U_NOT_A_COMMIT_OBJECT = "NOT_A_COMMIT_OBJECT"

UNKNOWN_REASONS = frozenset({
    U_NO_OBSERVATION, U_OBSERVATION_FAILED, U_REF_UNAVAILABLE,
    U_PERMISSION_DENIED, U_RATE_LIMITED, U_SNAPSHOT_MISSING,
    U_SNAPSHOT_INTEGRITY, U_SCOPE_MISMATCH, U_REPO_MISMATCH,
    U_REF_MISMATCH, U_COMMIT_MALFORMED, U_NOT_A_COMMIT_OBJECT})

# ── POSSIBLY_STALE 原因码 ──────────────────────────────────
R_REF_MOVED = "TRACKED_REF_MOVED"
R_REF_MOVED_FORCE = "TRACKED_REF_MOVED_NO_ANCESTRY_EVIDENCE"

SAFE_WATCH_ID = re.compile(r"^SL-WATCH-[0-9a-f]{32}$")
SAFE_OBS_ID = re.compile(r"^SL-REFOBS-[0-9a-f]{32}$")
SAFE_ASSESS_ID = re.compile(r"^SL-FRESH-[0-9a-f]{32}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def _sid(prefix: str, payload: dict) -> str:
    return prefix + sha256_of(payload)[:32]


def is_commit_sha(s) -> bool:
    return isinstance(s, str) and bool(COMMIT_RE.match(s))


@dataclass
class RefObservation:
    """一次可信的 Ref 版本观测。

    ★ `observed_at` **不进确定性身份**（题面 §7）。
    ★ 失败观测不会生成假的 HEAD。
    """
    observation_id: str
    repository_id: str
    requested_ref: str
    ref_kind: str
    resolved_commit_sha: Optional[str]
    source_snapshot_ref: Optional[str]
    retrieval_scope: str
    observation_status: str
    evidence_refs: list
    collector_version: str
    input_digest: str
    observed_at: str = ""
    provenance_level: str = ""
    failure_reason: Optional[str] = None

    def __post_init__(self):
        if not SAFE_OBS_ID.match(self.observation_id):
            raise ValueError(f"非法 observation_id: {self.observation_id!r}")
        if self.ref_kind not in REF_KINDS:
            raise ValueError(f"非法 ref_kind: {self.ref_kind!r}")
        if self.observation_status not in OBS_STATUSES:
            raise ValueError(f"非法 observation_status: {self.observation_status!r}")
        if self.observation_status == OBS_OK:
            if not is_commit_sha(self.resolved_commit_sha):
                raise ValueError("成功观测必须带合法 40 位 commit sha")
            if self.failure_reason is not None:
                raise ValueError("成功观测不得带 failure_reason")
        else:
            if self.resolved_commit_sha is not None:
                raise ValueError(
                    "失败观测不得带 resolved_commit_sha（不得伪造新 HEAD）")
            if self.failure_reason is None:
                raise ValueError("失败观测必须带 failure_reason")

    def identity_payload(self) -> dict:
        """确定性身份载荷：**不含 observed_at**。"""
        return {
            "repository_id": self.repository_id,
            "requested_ref": self.requested_ref,
            "ref_kind": self.ref_kind,
            "resolved_commit_sha": self.resolved_commit_sha,
            "source_snapshot_ref": self.source_snapshot_ref,
            "retrieval_scope": self.retrieval_scope,
            "observation_status": self.observation_status,
            "collector_version": self.collector_version,
        }

    def to_dict(self) -> dict:
        d = self.identity_payload()
        d.update({"observation_id": self.observation_id,
                  "evidence_refs": self.evidence_refs,
                  "input_digest": self.input_digest,
                  "observed_at": self.observed_at,
                  "provenance_level": self.provenance_level,
                  "failure_reason": self.failure_reason})
        return d


def make_observation_id(*, repository_id, requested_ref, ref_kind,
                        resolved_commit_sha, observation_status,
                        collector_version) -> str:
    return _sid("SL-REFOBS-", {
        "repository_id": str(repository_id), "requested_ref": requested_ref,
        "ref_kind": ref_kind, "resolved_commit_sha": resolved_commit_sha,
        "observation_status": observation_status,
        "collector_version": collector_version})


@dataclass
class LifecycleWatch:
    """一条跟踪关系：某个已裁决的 Claim 被用于某个移动 Ref。"""
    watch_id: str
    repository_id: str
    requested_ref: str
    ref_kind: str
    retrieval_scope: str
    baseline_commit_sha: str
    claim_id: str
    applicability_scope: str
    created_at: str = ""

    def __post_init__(self):
        if not SAFE_WATCH_ID.match(self.watch_id):
            raise ValueError(f"非法 watch_id: {self.watch_id!r}")
        if self.applicability_scope not in APPLICABILITY_SCOPES:
            raise ValueError(f"非法 applicability_scope: {self.applicability_scope!r}")
        if self.ref_kind not in REF_KINDS:
            raise ValueError(f"非法 ref_kind: {self.ref_kind!r}")
        if not is_commit_sha(self.baseline_commit_sha):
            raise ValueError("baseline_commit_sha 必须是 40 位 commit sha")
        # ★ PINNED_COMMIT 的 watch 没有意义（固定版本不跟踪移动 Ref）
        if self.applicability_scope == PINNED_COMMIT:
            raise ValueError(
                "PINNED_COMMIT 不得建立 TRACKING_REF watch（固定版本不跟踪移动 Ref）")

    def identity_payload(self) -> dict:
        return {
            "repository_id": self.repository_id,
            "requested_ref": self.requested_ref,
            "ref_kind": self.ref_kind,
            "retrieval_scope": self.retrieval_scope,
            "baseline_commit_sha": self.baseline_commit_sha,
            "claim_id": self.claim_id,
            "applicability_scope": self.applicability_scope,
        }

    def to_dict(self) -> dict:
        d = self.identity_payload()
        d.update({"watch_id": self.watch_id, "created_at": self.created_at})
        return d


def make_watch_id(*, repository_id, requested_ref, ref_kind, retrieval_scope,
                  baseline_commit_sha, claim_id,
                  applicability_scope=TRACKING_REF) -> str:
    return _sid("SL-WATCH-", {
        "repository_id": str(repository_id), "requested_ref": requested_ref,
        "ref_kind": ref_kind, "retrieval_scope": retrieval_scope,
        "baseline_commit_sha": baseline_commit_sha, "claim_id": claim_id,
        "applicability_scope": applicability_scope})


def build_watch(*, repository_id, requested_ref, ref_kind, retrieval_scope,
                baseline_commit_sha, claim_id, created_at="") -> LifecycleWatch:
    return LifecycleWatch(
        watch_id=make_watch_id(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=retrieval_scope,
            baseline_commit_sha=baseline_commit_sha, claim_id=claim_id),
        repository_id=str(repository_id), requested_ref=requested_ref,
        ref_kind=ref_kind, retrieval_scope=retrieval_scope,
        baseline_commit_sha=baseline_commit_sha, claim_id=claim_id,
        applicability_scope=TRACKING_REF, created_at=created_at)


@dataclass
class FreshnessAssessment:
    """一次新鲜度评估。

    ★ **不等于 claim_verification**：不覆盖 EC 的身份、内容或历史。
    ★ `assessed_at` 不进确定性身份。
    """
    assessment_id: str
    watch_id: str
    claim_id: str
    repository_id: str
    requested_ref: str
    baseline_commit_sha: str
    observed_commit_sha: Optional[str]
    freshness_state: str
    reason_code: Optional[str]
    evidence_refs: list
    rule_version: str
    input_digest: str
    applicability_scope: str
    observed_at: str = ""
    assessed_at: str = ""
    detail: str = ""

    def __post_init__(self):
        if not SAFE_ASSESS_ID.match(self.assessment_id):
            raise ValueError(f"非法 assessment_id: {self.assessment_id!r}")
        if self.freshness_state not in FRESHNESS_STATES:
            raise ValueError(f"非法 freshness_state: {self.freshness_state!r}")
        if self.freshness_state == UNKNOWN:
            if self.reason_code is None:
                raise ValueError("UNKNOWN 必须带 reason_code")
            if self.reason_code not in UNKNOWN_REASONS:
                raise ValueError(f"非法 UNKNOWN reason_code: {self.reason_code!r}")
        elif self.freshness_state == POSSIBLY_STALE:
            if self.reason_code is None:
                raise ValueError("POSSIBLY_STALE 必须带 reason_code")
            if not is_commit_sha(self.observed_commit_sha):
                raise ValueError("POSSIBLY_STALE 必须有可信的新 commit")
            if self.observed_commit_sha == self.baseline_commit_sha:
                raise ValueError(
                    "observed 与 baseline 相同不能判 POSSIBLY_STALE")
        else:
            if self.reason_code is not None:
                raise ValueError("非 UNKNOWN/POSSIBLY_STALE 不得带 reason_code")
        if self.freshness_state == VERSION_ALIGNED:
            if not is_commit_sha(self.observed_commit_sha):
                raise ValueError("VERSION_ALIGNED 必须有可信观测 commit")
            if self.observed_commit_sha != self.baseline_commit_sha:
                raise ValueError("VERSION_ALIGNED 要求 observed == baseline")

    def identity_payload(self) -> dict:
        """确定性身份：**不含 assessed_at / observed_at**。"""
        return {
            "watch_id": self.watch_id, "claim_id": self.claim_id,
            "repository_id": self.repository_id,
            "requested_ref": self.requested_ref,
            "baseline_commit_sha": self.baseline_commit_sha,
            "observed_commit_sha": self.observed_commit_sha,
            "freshness_state": self.freshness_state,
            "reason_code": self.reason_code,
            "rule_version": self.rule_version,
            "applicability_scope": self.applicability_scope,
        }

    def to_dict(self) -> dict:
        d = self.identity_payload()
        d.update({"assessment_id": self.assessment_id,
                  "evidence_refs": self.evidence_refs,
                  "input_digest": self.input_digest,
                  "observed_at": self.observed_at,
                  "assessed_at": self.assessed_at,
                  "detail": self.detail})
        return d


def make_assessment_id(*, watch_id, claim_id, repository_id, requested_ref,
                       baseline_commit_sha, observed_commit_sha,
                       freshness_state, reason_code, rule_version,
                       applicability_scope) -> str:
    return _sid("SL-FRESH-", {
        "watch_id": watch_id, "claim_id": claim_id,
        "repository_id": str(repository_id), "requested_ref": requested_ref,
        "baseline_commit_sha": baseline_commit_sha,
        "observed_commit_sha": observed_commit_sha,
        "freshness_state": freshness_state, "reason_code": reason_code,
        "rule_version": rule_version,
        "applicability_scope": applicability_scope})
