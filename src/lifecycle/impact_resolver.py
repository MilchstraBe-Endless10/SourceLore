#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""影响范围解析：一次 Ref 更新事件影响哪些 Claim。

契约：SL-CAP-0044（关联文件及依赖更新）。

**必须依据（题面 §9）：**
  repository_id / watch_id / requested_ref / baseline_commit_sha / claim_id / retrieval_scope

**禁止：**只按相同文件名查找。
不同仓库的 README 不互相影响；同仓库不同分支不自动互相影响；
固定 Commit 的历史 Claim 不因其他 Commit 更新而失效。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, _HERE)

import lc_models as L


def resolve_affected(watches, *, assessment_list) -> dict:
    """按评估结果划分受影响 / 未受影响集合。

    只由 watch 与 assessment 的**结构化字段**决定，不看文件名。
    """
    affected, unaffected, unknown = [], [], []
    # 同一 watch 可能有多条评估（不同观测）——按"最需要关注的状态"取：
    # POSSIBLY_STALE 优先于 UNKNOWN 优先于 VERSION_ALIGNED。
    _rank = {L.POSSIBLY_STALE: 0, L.UNKNOWN: 1,
             L.NOT_APPLICABLE_TO_PINNED: 2, L.VERSION_ALIGNED: 3}
    by_watch = {}
    for a in assessment_list:
        prev = by_watch.get(a.watch_id)
        if prev is None or _rank.get(a.freshness_state, 9) < _rank.get(
                prev.freshness_state, 9):
            by_watch[a.watch_id] = a

    for w in watches:
        a = by_watch.get(w.watch_id)
        if a is None:
            # 无对应评估 → 归入 unknown，且统一为结构化 dict（不混入对象）
            unknown.append({"watch_id": w.watch_id, "claim_id": w.claim_id,
                            "repository_id": w.repository_id,
                            "requested_ref": w.requested_ref,
                            "reason_code": None,
                            "detail": "NO_ASSESSMENT"})
            continue
        if a.freshness_state == L.POSSIBLY_STALE:
            affected.append({"watch_id": w.watch_id, "claim_id": w.claim_id,
                             "repository_id": w.repository_id,
                             "requested_ref": w.requested_ref,
                             "baseline_commit_sha": w.baseline_commit_sha,
                             "observed_commit_sha": a.observed_commit_sha,
                             "reason_code": a.reason_code})
        elif a.freshness_state == L.VERSION_ALIGNED:
            unaffected.append({"watch_id": w.watch_id, "claim_id": w.claim_id,
                               "repository_id": w.repository_id,
                               "requested_ref": w.requested_ref,
                               "freshness_state": a.freshness_state})
        elif a.freshness_state == L.NOT_APPLICABLE_TO_PINNED:
            unaffected.append({"watch_id": w.watch_id, "claim_id": w.claim_id,
                               "repository_id": w.repository_id,
                               "requested_ref": w.requested_ref,
                               "freshness_state": a.freshness_state})
        else:
            unknown.append({"watch_id": w.watch_id, "claim_id": w.claim_id,
                            "repository_id": w.repository_id,
                            "requested_ref": w.requested_ref,
                            "reason_code": a.reason_code})

    keys = {(str(w.repository_id), w.requested_ref) for w in watches}
    return {
        "affected_claim_ids": sorted({x["claim_id"] for x in affected}),
        "unaffected_claim_ids": sorted({x["claim_id"] for x in unaffected
                                        if isinstance(x, dict)
                                        and "claim_id" in x}),
        "unknown_claim_ids": sorted({x["claim_id"] for x in unknown
                                     if isinstance(x, dict)
                                     and "claim_id" in x}),
        "affected": affected, "unaffected": unaffected,
        "unknown": unknown,
        "watched_pairs": sorted([list(k) for k in keys]),
        "basis": ["repository_id", "watch_id", "requested_ref",
                  "baseline_commit_sha", "claim_id", "retrieval_scope"],
        "explicitly_not_used": ["file_name_matching"],
    }


def filter_watches(watches, *, repository_id, requested_ref) -> list:
    """严格按 (repository_id, requested_ref) 过滤。

    ★ 不同仓库的同名 Ref 不互相影响；同仓库不同 Ref 不互相影响。
    """
    rid = str(repository_id)
    return [w for w in watches
            if str(w.repository_id) == rid and w.requested_ref == requested_ref]
