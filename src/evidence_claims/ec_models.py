#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evidence-Claims 数据模型。

契约：SL-CAP-0020～0028。

**五个概念必须分开，任一都不能替代另一个：**
  claim_type          命题语义类别
  verification_status supported / refuted / insufficient_evidence
  review_status       pending_review / approved（**只能由人类动作产生**）
  knowledge_freshness 知识是否可能过时（本轮只留契约）
  execution_status    任务执行状态（属于运行时，不属知识裁决）

本轮只实现结构化命题 `repository_path_exists`。
不支持的命题类型显式 UNSUPPORTED_CLAIM_TYPE，**绝不强行套用路径规则**。
"""

import hashlib, json, re
from dataclasses import dataclass, field
from typing import Optional

SUPPORTED = "supported"
REFUTED = "refuted"
INSUFFICIENT = "insufficient_evidence"
VERIFICATION_STATES = frozenset({SUPPORTED, REFUTED, INSUFFICIENT})

PENDING_REVIEW = "pending_review"
APPROVED = "approved"
REJECTED_REVIEW = "rejected_review"
REVIEW_STATES = frozenset({PENDING_REVIEW, APPROVED, REJECTED_REVIEW})

R_NO_FACTS = "NO_FACTS"
R_FACT_NOT_FOUND = "FACT_NOT_FOUND"
R_FACT_INTEGRITY = "FACT_INTEGRITY_FAILED"
R_SNAPSHOT_NOT_FOUND = "SNAPSHOT_NOT_FOUND"
R_SNAPSHOT_INTEGRITY = "SNAPSHOT_INTEGRITY_FAILED"
R_REPO_MISMATCH = "REPOSITORY_MISMATCH"
R_COMMIT_MISMATCH = "COMMIT_MISMATCH"
R_PATH_MISMATCH = "PATH_MISMATCH"
R_NOT_COVERING = "SCOPE_NOT_COVERING"
R_PARTIAL_INSUFFICIENT = "PARTIAL_EVIDENCE_INSUFFICIENT"
R_PARTIAL_CANNOT_REFUTE = "PARTIAL_CANNOT_REFUTE"
R_EVIDENCE_FIELD_MISSING = "EVIDENCE_FIELD_MISSING"
R_CONFLICT = "CONFLICTING_EVIDENCE"
R_UNSUPPORTED_TYPE = "UNSUPPORTED_CLAIM_TYPE"
R_FACT_UNKNOWN = "FACT_IS_UNKNOWN"
R_STORAGE_ERROR = "STORAGE_ERROR"

INSUFFICIENT_REASONS = frozenset({
    R_NO_FACTS, R_FACT_NOT_FOUND, R_FACT_INTEGRITY, R_SNAPSHOT_NOT_FOUND,
    R_SNAPSHOT_INTEGRITY, R_REPO_MISMATCH, R_COMMIT_MISMATCH, R_PATH_MISMATCH,
    R_NOT_COVERING, R_PARTIAL_INSUFFICIENT, R_PARTIAL_CANNOT_REFUTE,
    R_EVIDENCE_FIELD_MISSING, R_CONFLICT, R_UNSUPPORTED_TYPE,
    R_FACT_UNKNOWN, R_STORAGE_ERROR})

CLAIM_PATH_EXISTS = "repository_path_exists"
# F2-P5E：内容级命题（仅覆盖可机械验证的三类）
CLAIM_README_HEADING = "readme_heading_exists"
CLAIM_MANIFEST_DEP = "manifest_dependency_declared"
CLAIM_MANIFEST_FIELD = "manifest_field_present"
CONTENT_CLAIM_TYPES = frozenset({CLAIM_README_HEADING, CLAIM_MANIFEST_DEP,
                                 CLAIM_MANIFEST_FIELD})
# F2-P5G：源码结构命题
CLAIM_SYMBOL = "source_symbol_declared"
CLAIM_IMPORT = "source_import_declared"
CLAIM_LOCAL_MODULE = "source_local_module_resolved"
CLAIM_EXPORT = "source_export_declared"
CLAIM_MODULE_RELATION = "static_module_relation_resolved"
CLAIM_CONFIG_PATHS = "module_config_paths_declared"
MODULE_CLAIM_TYPES = frozenset({CLAIM_MODULE_RELATION, CLAIM_CONFIG_PATHS})
# F2-P5J：TypeScript 项目 / 引用 / 归属
CLAIM_TS_PROJECT = "tsconfig_project_declared"
CLAIM_TS_PROJECT_REFERENCE = "tsconfig_project_reference_declared"
CLAIM_TS_MEMBERSHIP = "tsconfig_file_membership_candidate"
TS_PROJECT_CLAIM_TYPES = frozenset({CLAIM_TS_PROJECT,
                                    CLAIM_TS_PROJECT_REFERENCE,
                                    CLAIM_TS_MEMBERSHIP})
SOURCE_CLAIM_TYPES = frozenset({CLAIM_SYMBOL, CLAIM_IMPORT,
                                CLAIM_LOCAL_MODULE, CLAIM_EXPORT
                                }) | MODULE_CLAIM_TYPES | TS_PROJECT_CLAIM_TYPES
SUPPORTED_CLAIM_TYPES = (frozenset({CLAIM_PATH_EXISTS})
                         | CONTENT_CLAIM_TYPES | SOURCE_CLAIM_TYPES)
CLAIM_SCHEMA_VERSION = "claim-schema/1"

SAFE_CLAIM_ID = re.compile(r"^SL-CLAIM-[0-9a-f]{40}$")
SAFE_VERIF_ID = re.compile(r"^SL-VERIF-[0-9a-f]{40}$")


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def normalize_path(p: str) -> str:
    """与 Facts 侧同一套规则 —— 路径语义必须一致，否则 Claim 与 Fact 对不上。"""
    if not isinstance(p, str) or not p:
        raise ValueError("路径必须是非空字符串")
    if p.startswith("/"):
        raise ValueError(f"路径不得为绝对路径: {p!r}")
    if "\\" in p:
        raise ValueError(f"路径不得含反斜杠: {p!r}")
    if "\x00" in p:
        raise ValueError("路径不得含空字节")
    if p.endswith("/"):
        p = p[:-1]
    segs = p.split("/")
    if any(s == "" for s in segs):
        raise ValueError(f"路径不得含空段: {p!r}")
    if any(s == ".." for s in segs):
        raise ValueError(f"路径不得含父目录穿越: {p!r}")
    return "/".join(segs)


@dataclass
class Claim:
    """结构化命题。`claim_id` **不含事实列表** —— 换证据仍是同一 claim_id。"""
    claim_id: str
    claim_type: str
    repository_id: str
    commit_sha: str
    normalized_path: str
    expected_exists: bool
    claim_scope: str
    claim_origin: str
    claim_schema_version: str = CLAIM_SCHEMA_VERSION
    snapshot_logical_identity: Optional[str] = None
    review_status: str = PENDING_REVIEW
    human_authored: bool = False
    knowledge_freshness: Optional[str] = None
    created_at: str = ""

    def __post_init__(self):
        if not SAFE_CLAIM_ID.match(self.claim_id):
            raise ValueError(f"非法 claim_id: {self.claim_id!r}")
        if self.claim_type not in SUPPORTED_CLAIM_TYPES:
            raise ValueError(f"不支持的 claim_type: {self.claim_type!r}")
        if self.review_status not in REVIEW_STATES:
            raise ValueError(f"非法 review_status: {self.review_status!r}")
        if self.review_status == APPROVED and not self.human_authored:
            raise ValueError("review_status=approved 必须有 human_authored=True")

    def identity_payload(self) -> dict:
        return {
            "claim_type": self.claim_type,
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "normalized_path": self.normalized_path,
            "expected_exists": self.expected_exists,
            "claim_scope": self.claim_scope,
            "claim_schema_version": self.claim_schema_version,
        }

    def to_dict(self) -> dict:
        d = self.identity_payload()
        d.update({
            "claim_id": self.claim_id, "claim_origin": self.claim_origin,
            "snapshot_logical_identity": self.snapshot_logical_identity,
            "review_status": self.review_status,
            "human_authored": self.human_authored,
            "knowledge_freshness": self.knowledge_freshness,
            "created_at": self.created_at,
        })
        return d


def make_claim_id(*, repository_id: str, commit_sha: str, claim_type: str,
                  normalized_parameters: dict,
                  claim_schema_version: str = CLAIM_SCHEMA_VERSION) -> str:
    """Claim 身份：**只看命题本身**，不看证据。"""
    return "SL-CLAIM-" + sha256_of({
        "repository_id": str(repository_id),
        "commit_sha": commit_sha,
        "claim_type": claim_type,
        "normalized_parameters": normalized_parameters,
        "claim_schema_version": claim_schema_version,
    })[:40]


def build_path_claim(*, repository_id: str, commit_sha: str, target_path: str,
                     expected_exists: bool,
                     snapshot_logical_identity: Optional[str] = None,
                     claim_scope: str = "full_tree_enumeration",
                     claim_origin: str = "human_specified",
                     created_at: str = "") -> Claim:
    norm = normalize_path(target_path)
    params = {"normalized_path": norm, "expected_exists": expected_exists}
    cid = make_claim_id(repository_id=repository_id, commit_sha=commit_sha,
                        claim_type=CLAIM_PATH_EXISTS,
                        normalized_parameters=params)
    return Claim(claim_id=cid, claim_type=CLAIM_PATH_EXISTS,
                 repository_id=str(repository_id), commit_sha=commit_sha,
                 normalized_path=norm, expected_exists=expected_exists,
                 claim_scope=claim_scope, claim_origin=claim_origin,
                 snapshot_logical_identity=snapshot_logical_identity,
                 created_at=created_at)


@dataclass
class Verification:
    """一次确定性证据评估。

    `verification_id` 由证据集合 + 规则版本决定 —— 证据或规则变则新版本。
    **时间戳不参与身份。**
    """
    verification_id: str
    claim_id: str
    status: str
    reason_code: Optional[str]
    fact_ids: list
    fact_content_hashes: list
    rule_version: str
    normalized_verification_params: dict
    evidence_refs: list
    conflict_detected: bool = False
    conflict_fact_ids: list = field(default_factory=list)
    local_coverage_only: bool = False
    supporting_fact_ids: list = field(default_factory=list)
    counter_fact_ids: list = field(default_factory=list)
    storage_error: Optional[str] = None
    verified_at: str = ""
    evidence_level: str = ""

    def __post_init__(self):
        if not SAFE_VERIF_ID.match(self.verification_id):
            raise ValueError(f"非法 verification_id: {self.verification_id!r}")
        if self.status not in VERIFICATION_STATES:
            raise ValueError(f"非法裁决状态: {self.status!r}")
        if self.status == INSUFFICIENT:
            if self.reason_code is None:
                raise ValueError("insufficient_evidence 必须带 reason_code")
            if self.reason_code not in INSUFFICIENT_REASONS:
                raise ValueError(f"非法 reason_code: {self.reason_code!r}")
        else:
            if self.reason_code is not None:
                raise ValueError("非 insufficient 裁决不得带 reason_code")
        if self.status == SUPPORTED and not self.supporting_fact_ids:
            raise ValueError("supported 必须有支持性事实")

    def to_dict(self) -> dict:
        return {
            "verification_id": self.verification_id, "claim_id": self.claim_id,
            "status": self.status, "reason_code": self.reason_code,
            "fact_ids": self.fact_ids,
            "fact_content_hashes": self.fact_content_hashes,
            "rule_version": self.rule_version,
            "normalized_verification_params": self.normalized_verification_params,
            "evidence_refs": self.evidence_refs,
            "conflict_detected": self.conflict_detected,
            "conflict_fact_ids": self.conflict_fact_ids,
            "local_coverage_only": self.local_coverage_only,
            "supporting_fact_ids": self.supporting_fact_ids,
            "counter_fact_ids": self.counter_fact_ids,
            "storage_error": self.storage_error,
            "verified_at": self.verified_at,
            "evidence_level": self.evidence_level,
        }


def make_verification_id(*, claim_id: str, fact_ids_sorted: list,
                         fact_content_hashes_sorted: list,
                         rule_version: str,
                         normalized_verification_params: dict) -> str:
    """评估身份：证据（已排序）+ 规则版本 + 参数。排序保证顺序不影响身份。"""
    return "SL-VERIF-" + sha256_of({
        "claim_id": claim_id,
        "fact_ids": list(fact_ids_sorted),
        "fact_content_hashes": list(fact_content_hashes_sorted),
        "rule_version": rule_version,
        "normalized_verification_params": normalized_verification_params,
    })[:40]
