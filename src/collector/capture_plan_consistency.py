#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划-执行一致性：统一上下文标识 + 计划失效重校验。

★ 核心：plan 和 execute 必须用**同一个**只读完整性判定函数，否则两边结论会分叉。
"""

import hashlib
import json


def database_identity(data_root):
    """库身份。★ 内部比对用绝对路径的哈希，输出可脱敏。"""
    import os
    from pathlib import Path
    p = str(Path(str(data_root)).resolve())
    return {"db_id": hashlib.sha256(p.encode()).hexdigest()[:16],
            "db_path_masked": "…/" + os.path.basename(p)}


def inventory_digest(objects):
    """盘点指纹：把每个对象的状态压成一个摘要，用于判断计划是否过期。"""
    canon = sorted(
        (o.get("file_path"), o.get("git_blob_oid") or "",
         o.get("state") or "", int(o.get("planned_requests") or 0))
        for o in (objects or []))
    raw = json.dumps(canon, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def build_plan_context(*, repository_id, commit_sha, data_root,
                       source_snapshot_id, selected_scope, created_at=""):
    return {
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        **database_identity(data_root),
        "source_snapshot_id": source_snapshot_id,
        "plan_created_at": created_at,
        "selected_scope": list(selected_scope or []),
    }


def finalize_plan(*, context, inventory):
    """给计划补 plan_id / inventory_digest。"""
    digest = inventory_digest(inventory.get("objects") or [])
    pid = hashlib.sha256(
        (json.dumps(context, sort_keys=True, separators=(",", ":"))
         + digest).encode()).hexdigest()[:24]
    return {
        **context,
        "plan_id": pid,
        "inventory_digest": digest,
        "planned_requests": inventory.get("planned_requests_total", 0),
    }


REVALIDATED = "PLAN_STALE_REVALIDATED"
FRESH = "PLAN_FRESH"
ABORTED = "PLAN_CONTEXT_MISMATCH"


def revalidate(plan, fresh_inventory, *, data_root, repository_id, commit_sha):
    """执行前重核。★ 计划一旦过期，以**新鲜盘点结果**为准，绝不按旧计划发请求。"""
    cur = database_identity(data_root)
    mismatches = []
    if plan.get("db_id") != cur["db_id"]:
        mismatches.append("data_root")
    if str(plan.get("repository_id")) != str(repository_id):
        mismatches.append("repository_id")
    if str(plan.get("commit_sha")) != str(commit_sha):
        mismatches.append("commit_sha")

    if mismatches:
        return {"state": ABORTED, "mismatches": mismatches,
                "use_inventory": fresh_inventory,
                "note": "计划与当前上下文不符，必须用新鲜盘点"}

    fresh_digest = inventory_digest(fresh_inventory.get("objects") or [])
    if fresh_digest != plan.get("inventory_digest"):
        return {"state": REVALIDATED,
                "previous_digest": plan.get("inventory_digest"),
                "current_digest": fresh_digest,
                "use_inventory": fresh_inventory,
                "note": "存储状态已变化，按新盘点执行，不按旧计划"}
    return {"state": FRESH, "use_inventory": fresh_inventory}
