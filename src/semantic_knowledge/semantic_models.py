#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技术语义知识数据模型（P2-D3）。

设计目的：把模型已经研究、理解并有证据支持的技术命题，变成可持久化、
可跨进程复用的资产。核心问题不是「再写一份报告」，而是让下一次独立会话
直接取得已经研究过的技术命题，而不是重新读全部原文、重做同样研究。

★ 五条不可混淆的线（沿用既有 EC/Facts 纪律，不新建第四套知识存储）：
  1. 分类（knowledge_kind）        —— 命题属于哪类技术语义（架构/依赖/数据流…）
  2. 支持性（support_level）        —— 证据是否真正支持该命题（三段，不是布尔）
  3. 来源类别（source_category）    —— 文档自述 / 源码声明 / 源码观察 / 运行时推断
  4. 裁决（verification_status）    —— 借用 EC 的 supported/refuted/insufficient
  5. 覆盖（coverage_state）         —— 现有证据能否回答这个问题

★ 关键约束：
  - 来源级别**只降不升**：evidence 的 provenance / copy_permitted /
    distribution_allowed 必须原样继承，历史误标不得在本层被洗白。
  - 文档自述永远只是 documentation_self_report，不得冒充源码已验证事实。
  - 证据支持性由确定性程序校验；宿主模型只提供候选命题，不自带「已验证」光环。
  - 身份不含时间戳；同一命题同证据 → 同一 id（幂等基础）。
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Optional

SEMANTIC_SCHEMA_VERSION = "semantic-knowledge/1"

# ── 分类（技术语义知识种类）──────────────────────────────
K_ARCHITECTURE = "architecture"          # 整体架构 / 模块划分
K_DEPENDENCY = "dependency"              # 依赖声明（静态，非运行时调用）
K_DATA_FLOW = "data_flow"                # 数据流 / 请求流
K_CORE_MODULE = "core_module"            # 核心模块职责
K_INSTALL_CONFIG = "install_configuration"  # 安装与配置
K_DESIGN_RATIONALE = "design_rationale"  # 设计思路 / 取舍
K_REUSABLE_TECHNIQUE = "reusable_technique"  # 可复用技术方案
K_API_SURFACE = "api_surface"            # 对外 API 形态
K_BUILD_TEST = "build_and_test"          # 构建与测试方式
K_LIMITATION = "limitation"              # 已知限制 / 未覆盖

KNOWLEDGE_KINDS = frozenset({
    K_ARCHITECTURE, K_DEPENDENCY, K_DATA_FLOW, K_CORE_MODULE,
    K_INSTALL_CONFIG, K_DESIGN_RATIONALE, K_REUSABLE_TECHNIQUE,
    K_API_SURFACE, K_BUILD_TEST, K_LIMITATION,
})

# ── 证据支持性（三段，不是布尔）──────────────────────────
S_DIRECTLY_SUPPORTED = "DIRECTLY_SUPPORTED"  # 证据正文直接支持该命题
S_PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"  # 证据部分支持，需要保留限定
S_NOT_SUPPORTED = "NOT_SUPPORTED"        # 证据相关但不支持 / 矛盾 / 缺失
SUPPORT_LEVELS = frozenset({
    S_DIRECTLY_SUPPORTED, S_PARTIALLY_SUPPORTED, S_NOT_SUPPORTED,
})

# ── 来源类别（只降不升）───────────────────────────────────
SRC_DOC_SELF_REPORT = "documentation_self_report"   # 文档自述
SRC_SOURCE_DECLARATION = "source_declaration"       # 源码声明（import/def）
SRC_SOURCE_OBSERVATION = "source_observation"       # 源码结构观察
SRC_RUNTIME_INFERENCE = "runtime_inference"         # 运行时推断（本工具不做）
SRC_UNVERIFIED = "unverified"                       # 无证据

SOURCE_CATEGORIES = frozenset({
    SRC_DOC_SELF_REPORT, SRC_SOURCE_DECLARATION,
    SRC_SOURCE_OBSERVATION, SRC_RUNTIME_INFERENCE, SRC_UNVERIFIED,
})

# 来源可信度：只降不升。文档自述不得升级为源码事实。
_SOURCE_RANK = {
    SRC_UNVERIFIED: 0,
    SRC_RUNTIME_INFERENCE: 1,
    SRC_DOC_SELF_REPORT: 2,
    SRC_SOURCE_OBSERVATION: 3,
    SRC_SOURCE_DECLARATION: 4,
}


def effective_source_category(*categories: Optional[str]) -> str:
    """取所有来源里**最低**的类别，绝不向上升级。"""
    cats = [c for c in categories if c]
    if not cats:
        return SRC_UNVERIFIED
    unknown = [c for c in cats if c not in _SOURCE_RANK]
    if unknown:
        # 未知来源一律按最低处理，避免绕过门禁。
        return SRC_UNVERIFIED
    return min(cats, key=lambda c: _SOURCE_RANK[c])


# ── 覆盖状态（与 research packet 同口径）─────────────────
C_ANSWERABLE = "ANSWERABLE_FROM_EXISTING_EVIDENCE"
C_PARTIAL = "PARTIALLY_ANSWERABLE"
C_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
COVERAGE_STATES = frozenset({C_ANSWERABLE, C_PARTIAL, C_INSUFFICIENT})

# ── 裁决状态（复用 EC 口径，不新造状态机）────────────────
V_SUPPORTED = "supported"
V_REFUTED = "refuted"
V_INSUFFICIENT = "insufficient_evidence"
VERIFICATION_STATES = frozenset({V_SUPPORTED, V_REFUTED, V_INSUFFICIENT})

SAFE_SEM_ID = re.compile(r"^SL-SEM-[0-9a-f]{40}$")
SAFE_EVIDENCE_ID = re.compile(r"^SL-SEMEVID-[0-9a-f]{32}$")


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


@dataclass
class SemanticEvidenceRef:
    """一条指向原始正文的精确证据引用。

    所有定位字段都来自 section_fts 的召回结果，本层**不重新计算**、不美化、
    不升级 provenance。缺任一关键定位维度即 ref_complete=False。
    """
    content_asset_id: str = ""
    content_sha256: str = ""
    git_blob_oid: str = ""
    file_path: str = ""
    heading: str = ""
    source_category: str = SRC_UNVERIFIED
    provenance_level: str = ""
    copy_permitted: bool = False
    distribution_allowed: bool = False
    line_start: int = 0
    line_end: int = 0
    byte_start: int = 0
    byte_end: int = 0

    @property
    def ref_complete(self) -> bool:
        return bool(
            self.content_asset_id and self.content_sha256 and
            self.git_blob_oid and self.file_path and
            self.byte_end > self.byte_start
        )

    @classmethod
    def from_match(cls, match: dict, ref: Optional[dict] = None) -> "SemanticEvidenceRef":
        """从 section_fts 命中与其 refs[0] 构造，继承全部来源级别。"""
        m = match or {}
        r = ref or (m.get("refs") or [{}])[0]
        return cls(
            content_asset_id=str(m.get("content_asset_id") or r.get("content_asset_id") or ""),
            content_sha256=str(m.get("content_sha256") or r.get("content_sha256") or ""),
            git_blob_oid=str(m.get("git_blob_oid") or r.get("git_blob_oid") or ""),
            file_path=str(m.get("file_path") or r.get("file_path") or ""),
            heading=str(m.get("heading") or r.get("heading") or ""),
            source_category=str(m.get("source_category") or r.get("source_category")
                                or SRC_UNVERIFIED),
            provenance_level=str(m.get("provenance_level") or r.get("provenance_level") or ""),
            copy_permitted=bool(m.get("copy_permitted", r.get("copy_permitted", False))),
            distribution_allowed=bool(
                m.get("distribution_allowed", r.get("distribution_allowed", False))),
            line_start=int(m.get("line_start") or r.get("line_start") or 0),
            line_end=int(m.get("line_end") or r.get("line_end") or 0),
            byte_start=int(m.get("byte_start") or r.get("byte_start") or 0),
            byte_end=int(m.get("byte_end") or r.get("byte_end") or 0),
        )

    def to_dict(self) -> dict:
        d = {
            "content_asset_id": self.content_asset_id,
            "content_sha256": self.content_sha256,
            "git_blob_oid": self.git_blob_oid,
            "file_path": self.file_path,
            "heading": self.heading,
            "source_category": self.source_category,
            "provenance_level": self.provenance_level,
            "copy_permitted": self.copy_permitted,
            "distribution_allowed": self.distribution_allowed,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "ref_complete": self.ref_complete,
        }
        return d


@dataclass
class SemanticProposition:
    """一条技术语义命题 —— 持久化的最小知识单元。"""
    proposition: str                      # 中文技术命题陈述
    knowledge_kind: str                   # 分类
    repository_id: str
    commit_sha: str
    subject: str                          # 规范化主题（去重用）
    evidence: list = field(default_factory=list)  # list[SemanticEvidenceRef]
    support_level: str = S_NOT_SUPPORTED
    source_category: str = SRC_UNVERIFIED
    verification_status: str = V_INSUFFICIENT
    coverage_state: str = C_INSUFFICIENT
    limitations: list = field(default_factory=list)
    question: str = ""                    # 生产时的问题，便于回查研究语境
    proposition_id: str = ""
    schema_version: str = SEMANTIC_SCHEMA_VERSION

    def __post_init__(self):
        if self.knowledge_kind not in KNOWLEDGE_KINDS:
            raise ValueError(f"非法 knowledge_kind: {self.knowledge_kind!r}")
        if self.support_level not in SUPPORT_LEVELS:
            raise ValueError(f"非法 support_level: {self.support_level!r}")
        if self.verification_status not in VERIFICATION_STATES:
            raise ValueError(f"非法 verification_status: {self.verification_status!r}")
        if self.coverage_state not in COVERAGE_STATES:
            raise ValueError(f"非法 coverage_state: {self.coverage_state!r}")
        # 来源类别必须是所有证据里最低的，防止调用方洗白来源。
        cats = [e.source_category for e in self.evidence] + [self.source_category]
        self.source_category = effective_source_category(*cats)
        # 身份只由「命题本身 + 主题 + 身份 + commit」决定，不含证据、不含时间。
        if not self.proposition_id:
            self.proposition_id = make_proposition_id(
                repository_id=self.repository_id, commit_sha=self.commit_sha,
                subject=self.subject, knowledge_kind=self.knowledge_kind,
                proposition=self.proposition)

    def identity_payload(self) -> dict:
        return {
            "repository_id": str(self.repository_id),
            "commit_sha": self.commit_sha,
            "subject": self.subject,
            "knowledge_kind": self.knowledge_kind,
            "proposition": self.proposition,
        }

    def content_payload(self) -> dict:
        """写 A 层的 payload：身份 + 内容 + 证据，不含时间戳。"""
        d = self.identity_payload()
        d.update({
            "proposition_id": self.proposition_id,
            "schema_version": self.schema_version,
            "support_level": self.support_level,
            "source_category": self.source_category,
            "verification_status": self.verification_status,
            "coverage_state": self.coverage_state,
            "question": self.question,
            "limitations": sorted(set(self.limitations)),
            "evidence": [e.to_dict() for e in self.evidence],
            # ★ 最保守继承（Gate 6）：任一证据禁止分发/复制，命题即禁止。
            #   绝不能因为证据里有的允许就把命题升级为允许（历史误标也不洗白）。
            "distribution_allowed": all(
                e.distribution_allowed for e in self.evidence),
            "copy_permitted": all(
                e.copy_permitted for e in self.evidence),
        })
        return d

    def content_hash(self) -> str:
        return sha256_of(self.content_payload())


def make_proposition_id(*, repository_id, commit_sha, subject,
                        knowledge_kind, proposition) -> str:
    """命题身份：只看命题语义本身，不含证据、不含时间。"""
    return "SL-SEM-" + sha256_of({
        "repository_id": str(repository_id),
        "commit_sha": commit_sha,
        "subject": subject,
        "knowledge_kind": knowledge_kind,
        "proposition": proposition,
    })[:40]


def make_evidence_id(ref: SemanticEvidenceRef) -> str:
    return "SL-SEMEVID-" + sha256_of(ref.to_dict())[:32]


def normalize_subject(value: str) -> str:
    """主题规范化：小写 + 去多余空白；不做语义折叠，不猜。"""
    return re.sub(r"\s+", " ", (value or "").strip()).lower()
