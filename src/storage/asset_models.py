#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore 知识资产模型（A/B/C 层共用）。

契约：SL-CAP-0062（四层资产）、0063（身份与版本）、0066（跨仓库关系）。

**核心立场：**
  逻辑身份（logical_identity）≠ 内容哈希（content_hash）≠ 物理版本（asset_version）。
  三者任一都不能替代另一个。

**source_snapshot 三字段不可互换（F0 勘误 E-01..E-06 的直接后果）：**
  commit_sha      —— 提交标识
  root_tree_sha   —— 根 tree 标识
  tree_query_ref  —— 查询 ref（可能只是请求标识）
  GitHub Trees API 以 commit-ish 为 ref 时，返回的 sha 回显的是请求标识而不是 tree 的 sha。
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Optional

# ── 合法取值 ────────────────────────────────────────────────
ASSET_TYPES = frozenset({
    "repository_snapshot",   # 仓库快照
    "capability_record",     # 能力记录
    "subject_record",        # 知识主体
    "evidence_record",       # 证据
    "claim_record",          # 主张（本轮不做状态机）
    "relationship_record",   # 跨仓库关系
})

# 敏感字段（按名拦截，不靠调用方自觉）
FORBIDDEN_FIELDS = frozenset({
    "api_key", "apikey", "api-key", "token", "cookie", "secret", "password",
    "passwd", "credential", "private_key", "authorization", "env", "environ",
    "envvars", "access_token", "refresh_token",
})

# 身份标识符：只允许安全字符，避免用户输入直接决定文件路径
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SAFE_SHA = re.compile(r"^[0-9a-f]{40}$")


class ModelError(ValueError):
    """模型层校验失败（在写库之前就拒绝）。"""


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash_of(payload: dict) -> str:
    """内容哈希：只由 payload 决定，与逻辑身份无关。"""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def reject_sensitive(mapping: dict, where: str):
    low = {str(k).lower() for k in mapping}
    hit = sorted(f for f in FORBIDDEN_FIELDS if any(f in k for k in low))
    if hit:
        raise ModelError(f"{where}: 拒绝持久化敏感字段 {hit}")


def validate_id(value: str, fieldname: str):
    if not isinstance(value, str) or not SAFE_ID.match(value):
        raise ModelError(f"{fieldname} 非法：{value!r}（只允许字母数字与 ._:-，1~128 字符）")


@dataclass(frozen=True)
class SourceSnapshot:
    """来源快照。三字段**语义不同，不得混用**。"""
    commit_sha: Optional[str] = None
    root_tree_sha: Optional[str] = None
    tree_query_ref: Optional[str] = None

    def __post_init__(self):
        for name in ("commit_sha", "root_tree_sha"):
            v = getattr(self, name)
            if v is not None and not SAFE_SHA.match(v):
                raise ModelError(f"{name} 必须是 40 位小写十六进制：{v!r}")
        if self.tree_query_ref is not None:
            if not isinstance(self.tree_query_ref, str) or len(self.tree_query_ref) > 256:
                raise ModelError("tree_query_ref 必须是 ≤256 字符的字符串")

    def to_dict(self) -> dict:
        return {"commit_sha": self.commit_sha,
                "root_tree_sha": self.root_tree_sha,
                "tree_query_ref": self.tree_query_ref}

    def is_consistent(self) -> bool:
        """tree_query_ref 若与 commit_sha 相同，说明是把 commit 当 ref 用了 —— 允许但不等于 tree sha。"""
        return True


@dataclass
class AssetDraft:
    """待写入的资产（尚未提交）。"""
    asset_type: str
    logical_identity: str
    repository_id: str
    payload: dict
    asset_version: int = 1
    subject_id: Optional[str] = None
    source_snapshot: Optional[SourceSnapshot] = None
    operation_id: Optional[str] = None

    def __post_init__(self):
        if self.asset_type not in ASSET_TYPES:
            raise ModelError(f"非法 asset_type：{self.asset_type!r}")
        validate_id(self.logical_identity, "logical_identity")
        validate_id(self.repository_id, "repository_id")
        if self.subject_id is not None:
            validate_id(self.subject_id, "subject_id")
        if self.operation_id is not None:
            validate_id(self.operation_id, "operation_id")
        if not isinstance(self.payload, dict):
            raise ModelError("payload 必须是 dict")
        reject_sensitive(self.payload, "AssetDraft.payload")
        if not isinstance(self.asset_version, int) or self.asset_version < 1:
            raise ModelError("asset_version 必须是 ≥1 的整数")

    @property
    def content_hash(self) -> str:
        return content_hash_of(self.payload)


@dataclass
class Asset:
    """已提交的 A 层资产（不可变）。"""
    asset_id: str
    asset_type: str
    logical_identity: str
    repository_id: str
    asset_version: int
    content_hash: str
    payload: dict
    created_at: str
    operation_id: Optional[str] = None
    subject_id: Optional[str] = None
    source_snapshot: Optional[dict] = None

    def verify_integrity(self) -> bool:
        """读取时验证内容哈希。不匹配即表示资产被篡改或损坏。"""
        return content_hash_of(self.payload) == self.content_hash

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "logical_identity": self.logical_identity,
            "repository_id": self.repository_id,
            "asset_version": self.asset_version,
            "content_hash": self.content_hash,
            "payload": self.payload,
            "created_at": self.created_at,
            "operation_id": self.operation_id,
            "subject_id": self.subject_id,
            "source_snapshot": self.source_snapshot,
        }
