#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新验证候选的数据模型。

**候选只表示：某历史 Claim 对某个新观测 Commit 可能不再适用，建议重查。**
候选不表示：旧 Claim 已 false、旧 Verification 已 refuted、新 Commit 已 supported、
用户已批准、Harness 已执行、新知识可发布。
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import lc_models as L

# ── 候选状态（最小集）──────────────────────────────────────
PROPOSED = "PROPOSED"
BLOCKED = "BLOCKED"
SUPERSEDED = "SUPERSEDED"
CANCELLED = "CANCELLED"
# ★ 本轮不实现 AUTHORIZED（P3B 没通过 Y6-P3 审批门禁）
CANDIDATE_STATES = frozenset({PROPOSED, BLOCKED, SUPERSEDED, CANCELLED})

# ── 候选生成拒绝原因 ─────────────────────────────────────
RJ_ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
RJ_ASSESSMENT_INTEGRITY = "ASSESSMENT_INTEGRITY_FAILED"
RJ_NOT_POSSIBLY_STALE = "NOT_POSSIBLY_STALE"
RJ_NOT_TRACKING_REF = "NOT_TRACKING_REF"
RJ_WATCH_MISMATCH = "WATCH_MISMATCH"
RJ_WATCH_NOT_FOUND = "WATCH_NOT_FOUND"
RJ_REPO_MISMATCH = "REPOSITORY_MISMATCH"
RJ_REF_MISMATCH = "REF_MISMATCH"
RJ_BASELINE_MISMATCH = "BASELINE_COMMIT_MISMATCH"
RJ_TARGET_INVALID = "TARGET_COMMIT_INVALID"
RJ_TARGET_SAME_AS_BASE = "TARGET_EQUALS_BASELINE"
RJ_CLAIM_NOT_FOUND = "CLAIM_NOT_FOUND"
RJ_VERIFICATION_NOT_FOUND = "VERIFICATION_NOT_FOUND"
RJ_UNRESOLVED_CONFLICT = "UNRESOLVED_CONFLICT"
RJ_CONFLICT_UNKNOWN = "CONFLICT_NOT_VERIFIED"
RJ_OBSERVATION_NOT_TRUSTED = "OBSERVATION_NOT_TRUSTED"
RJ_SYNTHETIC_NOT_DISPATCHABLE = "SYNTHETIC_SOURCE_NOT_DISPATCHABLE"
RJ_ALREADY_EXISTS = "CANDIDATE_ALREADY_EXISTS"
RJ_ACTIVE_EXISTS = "ACTIVE_CANDIDATE_EXISTS"
RJ_STORAGE_ERROR = "STORAGE_ERROR"

REJECT_REASONS = frozenset({
    RJ_ASSESSMENT_NOT_FOUND, RJ_ASSESSMENT_INTEGRITY, RJ_NOT_POSSIBLY_STALE,
    RJ_NOT_TRACKING_REF, RJ_WATCH_MISMATCH, RJ_WATCH_NOT_FOUND,
    RJ_REPO_MISMATCH, RJ_REF_MISMATCH, RJ_BASELINE_MISMATCH,
    RJ_TARGET_INVALID, RJ_TARGET_SAME_AS_BASE, RJ_CLAIM_NOT_FOUND,
    RJ_VERIFICATION_NOT_FOUND, RJ_UNRESOLVED_CONFLICT, RJ_CONFLICT_UNKNOWN,
    RJ_OBSERVATION_NOT_TRUSTED, RJ_SYNTHETIC_NOT_DISPATCHABLE,
    RJ_ALREADY_EXISTS, RJ_ACTIVE_EXISTS, RJ_STORAGE_ERROR})

# ── 来源等级 ───────────────────────────────────────────────
SRC_REAL = "REAL_LIVE_API"
SRC_HISTORICAL = "HISTORICAL_REAL_DATA"
SRC_SYNTHETIC = "SYNTHETIC_FIXTURE"
SOURCE_LEVELS = frozenset({SRC_REAL, SRC_HISTORICAL, SRC_SYNTHETIC})

# ★ 只有 REAL_LIVE_API 能进真实可执行调度
DISPATCHABLE_SOURCES = frozenset({SRC_REAL})

# ── 调度闸门状态 ───────────────────────────────────────────
GATE_PLAN_READY = "PLAN_READY"
GATE_EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
GATE_EXECUTION_COMPLETED = "EXECUTION_COMPLETED"

REVALIDATION_RULE_VERSION = "revalidation-proposal/v1"

SAFE_CANDIDATE_ID = re.compile(r"^SL-REVAL-[0-9a-f]{32}$")
SAFE_QUEUE_ID = re.compile(r"^SL-RVQ-[0-9a-f]{32}$")


def make_candidate_id(*, watch_id: str, source_claim_id: str,
                      target_commit_sha: str, repository_id: str,
                      revalidation_rule_version: str = REVALIDATION_RULE_VERSION,
                      canonical_scope: str = "full_tree_enumeration") -> str:
    """候选身份。

    ★ 不含时间戳；不含自由文本；参数顺序固定。
    ★ 含 repository_id —— 不同仓库即使 watch 撞名也不碰撞。
    """
    payload = {
        "watch_id": watch_id,
        "source_claim_id": source_claim_id,
        "target_commit_sha": target_commit_sha,
        "repository_id": str(repository_id),
        "revalidation_rule_version": revalidation_rule_version,
        "canonical_scope": canonical_scope,
    }
    return "SL-REVAL-" + L.sha256_of(payload)[:32]


def make_queue_id(*, watch_id: str) -> str:
    """每个 watch 一个队列状态资产（§7 方案 A）。"""
    return "SL-RVQ-" + L.sha256_of({"kind": "revalidation_queue",
                                    "watch_id": watch_id})[:32]


@dataclass
class RevalidationCandidate:
    """一条重新验证提议。"""
    candidate_id: str
    watch_id: str
    source_claim_id: str
    source_verification_id: str
    repository_id: str
    requested_ref: str
    baseline_commit_sha: str
    target_commit_sha: str
    canonical_scope: str
    revalidation_rule_version: str
    status: str
    reason_code: Optional[str]
    source_level: str
    source_assessment_id: str
    observation_id: Optional[str]
    expected_target_claim_identity: Optional[str]
    revalidation_of: str
    state_reason: str = ""
    created_at: str = ""
    superseded_by: Optional[str] = None
    conflict_state: str = L.CONFLICT_UNKNOWN
    conflict_fact_ids: list = field(default_factory=list)
    # ★ P3C 需要它来确定目标路径与命题参数（由门禁从源 Claim 拷贝）
    target_claim_parameters: dict = field(default_factory=dict)

    def __post_init__(self):
        if not SAFE_CANDIDATE_ID.match(self.candidate_id):
            raise ValueError(f"非法 candidate_id: {self.candidate_id!r}")
        if self.status not in CANDIDATE_STATES:
            raise ValueError(f"非法候选状态: {self.status!r}")
        if self.source_level not in SOURCE_LEVELS:
            raise ValueError(f"非法来源等级: {self.source_level!r}")
        if not L.is_commit_sha(self.baseline_commit_sha):
            raise ValueError("baseline_commit_sha 必须是 40 位 commit")
        if not L.is_commit_sha(self.target_commit_sha):
            raise ValueError("target_commit_sha 必须是 40 位 commit")
        if self.target_commit_sha == self.baseline_commit_sha:
            raise ValueError("target 与 baseline 相同不得生成候选")
        if self.conflict_state not in L.CONFLICT_STATES:
            raise ValueError(f"非法 conflict_state: {self.conflict_state!r}")
        # ★ 冲突未决 → 不允许是 PROPOSED
        if (self.status == PROPOSED
                and self.conflict_state != L.CONFLICT_NONE):
            raise ValueError(
                "冲突未核验/已检测到冲突时不得进入 PROPOSED")
        # ★ 合成来源不得进入可执行调度
        # ★ 非可调度来源必须是 BLOCKED（不能伪装成 PROPOSED）。
        #   但隔离测试可以在 BLOCKED 上执行（executor 会检查 test_only 授权）。
        if self.status == PROPOSED and self.source_level not in DISPATCHABLE_SOURCES:
            raise ValueError(
                f"{self.source_level} 来源不得进入可执行队列的 PROPOSED")

    def identity_payload(self) -> dict:
        return {
            "watch_id": self.watch_id,
            "source_claim_id": self.source_claim_id,
            "target_commit_sha": self.target_commit_sha,
            "repository_id": self.repository_id,
            "revalidation_rule_version": self.revalidation_rule_version,
            "canonical_scope": self.canonical_scope,
        }

    def to_dict(self) -> dict:
        d = self.identity_payload()
        d.update({
            "candidate_id": self.candidate_id,
            "source_verification_id": self.source_verification_id,
            "requested_ref": self.requested_ref,
            "baseline_commit_sha": self.baseline_commit_sha,
            "status": self.status, "reason_code": self.reason_code,
            "source_level": self.source_level,
            "source_assessment_id": self.source_assessment_id,
            "observation_id": self.observation_id,
            "expected_target_claim_identity": self.expected_target_claim_identity,
            "revalidation_of": self.revalidation_of,
            "state_reason": self.state_reason,
            "created_at": self.created_at,
            "superseded_by": self.superseded_by,
            "conflict_state": self.conflict_state,
            "conflict_fact_ids": self.conflict_fact_ids,
            "target_claim_parameters": self.target_claim_parameters,
        })
        return d


@dataclass
class WatchQueueState:
    """每个 watch 的单一版本化队列状态（§7 方案 A）。

    `active_candidate_id` 是**唯一**的活动槽位。
    所有变更都通过这一个资产的 CAS 推进 —— 因此天然原子。
    """
    queue_id: str
    watch_id: str
    repository_id: str
    active_candidate_id: Optional[str]
    active_target_commit_sha: Optional[str]
    history_candidate_ids: list
    updated_at: str = ""

    def __post_init__(self):
        if not SAFE_QUEUE_ID.match(self.queue_id):
            raise ValueError(f"非法 queue_id: {self.queue_id!r}")
        if self.active_candidate_id is None:
            if self.active_target_commit_sha is not None:
                raise ValueError("无活动候选时不得设 active_target_commit_sha")
        else:
            if not SAFE_CANDIDATE_ID.match(self.active_candidate_id):
                raise ValueError("active_candidate_id 形态非法")
            if not L.is_commit_sha(self.active_target_commit_sha):
                raise ValueError("有活动候选时必须带目标 commit")

    def to_dict(self) -> dict:
        return {
            "queue_id": self.queue_id, "watch_id": self.watch_id,
            "repository_id": self.repository_id,
            "active_candidate_id": self.active_candidate_id,
            "active_target_commit_sha": self.active_target_commit_sha,
            "history_candidate_ids": list(self.history_candidate_ids),
            "updated_at": self.updated_at,
        }


def empty_queue(watch) -> WatchQueueState:
    return WatchQueueState(
        queue_id=make_queue_id(watch_id=watch.watch_id),
        watch_id=watch.watch_id, repository_id=watch.repository_id,
        active_candidate_id=None, active_target_commit_sha=None,
        history_candidate_ids=[])
