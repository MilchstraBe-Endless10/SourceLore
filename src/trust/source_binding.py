#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D3：跨来源身份绑定（可追溯、非破坏性）。

设计纪律：
  - 不合并 repository_id；GitHub 骨架库与本地 Git 完整库仍是两条独立资产。
  - 用内容寻址锚点（commit_sha + root_tree_sha）**证明两份快照指向同一份内容**，
    锚点只作为 subject_id 参与 repo_bindings，不写回 A 层快照。
  - 绑定必须有 evidence_ref（引用两条快照的 asset_id + 锚点），拒绝无证据合并。
  - 全程只 INSERT repo_bindings（B 层关系表），不改 assets / current_view / index_rows。

隔离要求：任何写入先在副本验证；真实库写入须由显式验收流程触发，
本模块默认只提供 derive（计算锚点/证据）与 verify（只读核对）两个纯函数。
"""
import hashlib

ANCHOR_PREFIX = "CONTENT-ANCHOR-"


def content_anchor(commit_sha: str, root_tree_sha: str) -> str:
    """由内容寻址字段派生 subject_id；同内容不同来源得到同一锚点。"""
    if not commit_sha or not root_tree_sha:
        raise ValueError("commit_sha 与 root_tree_sha 均不得为空")
    return ANCHOR_PREFIX + hashlib.sha256(
        (str(commit_sha) + "\x00" + str(root_tree_sha)).encode()).hexdigest()[:24]


def snapshot_anchor(snapshot_payload: dict) -> dict:
    """从一条 source_snapshot 的入库 payload 提取锚点字段。"""
    return {
        "repository_id": str(snapshot_payload.get("repository_id") or ""),
        "commit_sha": snapshot_payload.get("commit_sha"),
        "root_tree_sha": snapshot_payload.get("root_tree_sha"),
        "asset_id": snapshot_payload.get("asset_id"),
    }


def verify_same_content(left: dict, right: dict) -> dict:
    """核对两条快照是否指向同一内容。

    ★ 只核对 commit_sha 与 root_tree_sha 两个客观内容寻址字段；
      completeness_status / tree_entry_count 允许不同（根层 vs 递归是正常的）。
    """
    reasons = []
    if not left.get("commit_sha") or not right.get("commit_sha"):
        reasons.append("MISSING_COMMIT")
    if not left.get("root_tree_sha") or not right.get("root_tree_sha"):
        reasons.append("MISSING_ROOT_TREE")
    commit_ok = bool(left.get("commit_sha")) and left["commit_sha"] == right.get("commit_sha")
    tree_ok = bool(left.get("root_tree_sha")) and left["root_tree_sha"] == right.get("root_tree_sha")
    if not commit_ok:
        reasons.append("COMMIT_MISMATCH")
    if not tree_ok:
        reasons.append("ROOT_TREE_MISMATCH")
    ok = commit_ok and tree_ok
    return {
        "ok": ok,
        "reasons": reasons,
        "subject_id": content_anchor(left["commit_sha"], left["root_tree_sha"]) if ok else None,
        "left_repository_id": left.get("repository_id"),
        "right_repository_id": right.get("repository_id"),
        "same_repository": left.get("repository_id") == right.get("repository_id"),
    }


def build_evidence_ref(left: dict, right: dict, subject_id: str) -> str:
    """构造可追溯证据引用：锚点 + 两条快照 asset_id。"""
    return ("content_anchor:commit=%s;root_tree=%s;subject=%s;"
            "left_snapshot=%s;right_snapshot=%s") % (
        left.get("commit_sha"), left.get("root_tree_sha"), subject_id,
        left.get("asset_id"), right.get("asset_id"))
