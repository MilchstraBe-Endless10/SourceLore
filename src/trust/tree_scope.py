#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0/D5：Tree 覆盖度派生判定（只读 A 层，不改冻结快照）。

历史快照把 ROOT_ONLY 标成 COMPLETE。本模块从 snapshot payload 的客观字段
重新推导真实覆盖范围，作为可重建派生视图供查询/裁决使用。
不改 assets、不访问 GitHub、不伪造 COMPLETE。
"""

TREE_COMPLETE = "COMPLETE"          # 复用合法码：真正完整
TREE_ROOT_ONLY = "ROOT_ONLY"        # 仅根层，有未展开子树
TREE_PARTIAL = "PARTIAL"            # 复用合法码：部分展开/截断


def derive_tree_scope(snapshot_payload):
    """从快照 payload 客观字段推导覆盖度。

    返回 {scope, reason, complete, deep_walk_used, has_subtrees, max_depth}。
    """
    sp = snapshot_payload if isinstance(snapshot_payload, dict) else {}
    entries = [e for e in (sp.get("tree_entries") or []) if isinstance(e, dict)]
    has_subtrees = any(e.get("type") == "tree" for e in entries)
    max_depth = max((str(e.get("path") or "").count("/") for e in entries), default=0)
    deep = bool(sp.get("deep_walk_used"))
    truncated = bool(sp.get("tree_truncated_seen"))
    claimed = str(sp.get("completeness_status") or "").upper()

    if truncated:
        return {"scope": TREE_PARTIAL, "reason": "TRUNCATED", "complete": False,
                "deep_walk_used": deep, "has_subtrees": has_subtrees, "max_depth": max_depth}
    if deep and claimed == TREE_COMPLETE:
        # 逐层遍历走完且未截断 → 真正完整
        return {"scope": TREE_COMPLETE, "reason": "DEEP_WALK_COMPLETE", "complete": True,
                "deep_walk_used": True, "has_subtrees": has_subtrees, "max_depth": max_depth}
    if has_subtrees and not deep:
        # 根层枚举但有未展开子树 —— 历史误标 COMPLETE，派生为 ROOT_ONLY
        return {"scope": TREE_ROOT_ONLY, "reason": "ROOT_ONLY_SUBTREES_UNENUMERATED",
                "complete": False, "deep_walk_used": False,
                "has_subtrees": True, "max_depth": max_depth}
    if not has_subtrees and claimed == TREE_COMPLETE:
        # 纯根级文件（无子目录）且未截断 → 根树完整，允许 COMPLETE
        return {"scope": TREE_COMPLETE, "reason": "ROOT_TREE_ENUMERATED_NO_SUBTREES",
                "complete": True, "deep_walk_used": False,
                "has_subtrees": False, "max_depth": 0}
    return {"scope": TREE_PARTIAL, "reason": "UNKNOWN_COVERAGE", "complete": False,
            "deep_walk_used": deep, "has_subtrees": has_subtrees, "max_depth": max_depth}


def snapshot_for_commit(store, repository_id, commit_sha):
    """取该仓库该 Commit 的当前快照 payload（优先 B 层指针，回退 A 层唯一快照）。"""
    rows = store.conn.execute(
        "SELECT asset_id, payload_json FROM assets WHERE asset_type='repository_snapshot' "
        "AND repository_id=?", (repository_id,)).fetchall()
    current_ids = set()
    for r in store.conn.execute(
            "SELECT cv.current_asset_id FROM current_view cv JOIN assets a "
            "ON a.asset_id=cv.current_asset_id WHERE cv.repository_id=? "
            "AND a.asset_type='repository_snapshot'", (repository_id,)):
        current_ids.add(r[0])
    import json
    for r in rows:
        if r["asset_id"] not in current_ids:
            continue
        pl = json.loads(r["payload_json"] or "{}")
        if str(pl.get("commit_sha")) == str(commit_sha):
            return pl
    for r in rows:
        pl = json.loads(r["payload_json"] or "{}")
        if str(pl.get("commit_sha")) == str(commit_sha):
            return pl
    return None
