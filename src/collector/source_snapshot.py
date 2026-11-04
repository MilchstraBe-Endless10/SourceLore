#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标准化 Source Snapshot。

契约：SL-CAP-0013 / 0019（来源快照与身份分离）。

**确定性身份规则：**
  `collected_at` 是观测时间 —— **不参与**内容身份哈希。
  同一 repository + commit + 采集范围 + 相同条目内容 ⇒ 同一 `logical_identity`。
  不同 repository 即使内容一致 ⇒ **不同身份**（repository_id 参与身份）。

**三字段硬分离（不可混用）：**
  commit_sha      —— 固定提交
  root_tree_sha   —— Commit 对象里的 `commit.tree.sha`（**绝不从 Trees API 响应取**）
  tree_query_ref  —— 实际请求使用的 ref（可能等于前两个之一，但语义不同）
"""

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

COLLECTOR_VERSION = "sourcelore-collector/1.0.0"
SOURCE_PROVIDER = "github"

# 采集范围（本批只支持全树枚举；明确声明，不冒充已做全仓库语义分析）
SCOPE_FULL_TREE = "full_tree_enumeration"


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


@dataclass
class SourceSnapshot:
    """一次成功采集的固定版本快照（已标准化）。

    `collected_at` 不在 identity_payload 里 —— 这是刻意的。
    """
    repository_id: str
    requested_repository: str
    resolved_repository: str
    requested_ref: str
    commit_sha: str
    root_tree_sha: str
    tree_query_ref: str
    retrieval_scope: str
    completeness_status: str
    tree_entry_count: int
    blob_refs: list
    collected_at: str
    source_evidence_refs: list
    tree_truncated_seen: bool = False
    deep_walk_used: bool = False
    collector_version: str = COLLECTOR_VERSION
    source_provider: str = SOURCE_PROVIDER

    # ── 确定性身份 ────────────────────────────────────────
    def identity_payload(self) -> dict:
        """参与身份哈希的字段集合。**不含 collected_at / source_evidence_refs。**"""
        return {
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "root_tree_sha": self.root_tree_sha,
            "retrieval_scope": self.retrieval_scope,
            "collector_version": self.collector_version,
        }

    def logical_identity(self) -> str:
        """逻辑身份：由 (仓库, commit, 范围, 采集器版本) 决定。

        repository_id 在内 —— 不同仓库内容相同也不会合并。
        """
        return "SL-SNAP-" + sha256_of(self.identity_payload())[:40]

    def content_payload(self) -> dict:
        """内容载荷：参与 content_hash，**不含 collected_at**。"""
        return {
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "root_tree_sha": self.root_tree_sha,
            "tree_query_ref": self.tree_query_ref,
            "retrieval_scope": self.retrieval_scope,
            "completeness_status": self.completeness_status,
            "tree_entry_count": self.tree_entry_count,
            "blob_refs": self.blob_refs,
            "tree_truncated_seen": self.tree_truncated_seen,
            "deep_walk_used": self.deep_walk_used,
            "collector_version": self.collector_version,
            "source_provider": self.source_provider,
            # 刻意不含 collected_at
        }

    def content_hash(self) -> str:
        return sha256_of(self.content_payload())

    def to_asset_payload(self) -> dict:
        """入库 payload。**必须与 content_hash() 同一口径。**

        这一点踩过坑：最初把 `collected_at` 也放进这个 payload，
        但 content_hash() 计算的是不含 collected_at 的 content_payload。
        Storage 的 AssetDraft.content_hash 由 payload 算出 —— 于是落库的哈希
        与 snapshot.content_hash() 不等，重采时被判定为 CONFLICT。

        正确做法：**入库 payload 就是 content_payload**。
        观测时间与证据引用属于"观测记录"，放在快照对象/执行记录里，
        不进入内容身份。
        """
        return dict(self.content_payload())

    def observation_record(self) -> dict:
        """观测记录（不影响内容身份）。可单独持久化为执行证据。"""
        return {
            "collected_at": self.collected_at,
            "source_evidence_refs": list(self.source_evidence_refs),
            "requested_repository": self.requested_repository,
            "resolved_repository": self.resolved_repository,
            "requested_ref": self.requested_ref,
            "logical_identity": self.logical_identity(),
            "content_hash": self.content_hash(),
        }

    def to_dict(self) -> dict:
        return {
            "repository_id": self.repository_id,
            "requested_repository": self.requested_repository,
            "resolved_repository": self.resolved_repository,
            "requested_ref": self.requested_ref,
            "commit_sha": self.commit_sha,
            "root_tree_sha": self.root_tree_sha,
            "tree_query_ref": self.tree_query_ref,
            "source_provider": self.source_provider,
            "retrieval_scope": self.retrieval_scope,
            "completeness_status": self.completeness_status,
            "tree_entry_count": self.tree_entry_count,
            "blob_refs": self.blob_refs,
            "collected_at": self.collected_at,
            "collector_version": self.collector_version,
            "source_evidence_refs": self.source_evidence_refs,
            "tree_truncated_seen": self.tree_truncated_seen,
            "deep_walk_used": self.deep_walk_used,
            "logical_identity": self.logical_identity(),
            "content_hash": self.content_hash(),
        }


def build_snapshot(*, repository_id: str, requested_repository: str,
                   resolved_repository: str, requested_ref: str,
                   commit_sha: str, root_tree_sha: str, tree_query_ref: str,
                   completeness_status: str, tree_entries: list,
                   collected_at: str, evidence_refs: list,
                   blob_refs: Optional[list] = None,
                   truncated_seen: bool = False,
                   deep_walk_used: bool = False,
                   retrieval_scope: str = SCOPE_FULL_TREE) -> SourceSnapshot:
    """构造快照。

    三字段**逐个传入**，不做任何自动回填 —— 防止把 commit_sha 当成 root_tree_sha。
    """
    if commit_sha == root_tree_sha and root_tree_sha == tree_query_ref:
        # 字面相同是允许的（有可能真的一样），但调用方必须**分别传**：
        # 这里不做额外校验，只在注释里强调语义不同。
        pass

    blobs = blob_refs if blob_refs is not None else [
        {"path": e["path"], "blob_sha": e["sha"], "size": e.get("size"),
         "mode_kind": e.get("mode_kind")}
        for e in tree_entries if e.get("type") == "blob"
    ]

    return SourceSnapshot(
        repository_id=str(repository_id),
        requested_repository=requested_repository,
        resolved_repository=resolved_repository,
        requested_ref=requested_ref,
        commit_sha=commit_sha,
        root_tree_sha=root_tree_sha,
        tree_query_ref=tree_query_ref,
        retrieval_scope=retrieval_scope,
        completeness_status=completeness_status,
        tree_entry_count=len(tree_entries),
        blob_refs=blobs,
        collected_at=collected_at,
        source_evidence_refs=list(evidence_refs),
        tree_truncated_seen=truncated_seen,
        deep_walk_used=deep_walk_used,
    )
