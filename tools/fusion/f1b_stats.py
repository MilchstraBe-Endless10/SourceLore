"""分批统计与累计统计的单一权威实现。

契约（F1-B 统计契约修订后）：

1. batch_summary 作用域严格限于单个批次，字段名一律带批次语义
   （raw_mapped_to_this_module 等），不写全局口径。
2. global_state_counts 是累计视图，每次构建都从草稿的真实内容现算：
   原始身份来自 RAW_CAPABILITY_INDEX，MAPPED 来自各 canonical 的 upstream_refs，
   ROUTED 来自未被晋升消费掉的 cross_module_redirections。
3. 三态互斥且并集为全集；ROUTED 绝不计入 MAPPED。
4. 任何数字都从磁盘算，不接受调用方传入的期望值，因此不存在「为了让验证通过
   而写死一个数字」的余地。
"""

from __future__ import annotations

UPSTREAMS = ["UPSTREAM-01", "UPSTREAM-02", "UPSTREAM-03", "UPSTREAM-04",
             "UPSTREAM-05", "UPSTREAM-06"]


def identity_key(item: dict) -> tuple[str, str]:
    """原始身份键：(upstream_id, original_capability_id)。"""
    return item["upstream_id"], item["original_capability_id"]


def raw_index_keys(index_doc: dict) -> list[tuple[str, str]]:
    return [identity_key(i) for i in index_doc["items"]]


def mapped_keys(draft: dict) -> set[tuple[str, str]]:
    out = set()
    for cap in draft.get("canonical_capabilities", []):
        for ref in cap.get("upstream_refs", []):
            out.add((ref["upstream_id"], ref["original_capability_id"]))
    return out


def promoted_keys(draft: dict) -> set[tuple[str, str]]:
    """已被晋升记录消费掉的身份——这些身份已经挂在某个 canonical 名下，
    不再是 ROUTED。晋升正是「分流 → 映射」的状态迁移凭据。"""
    out = set()
    for p in draft.get("routed_promotions", []):
        out.add((p["upstream_id"], p["original_capability_id"]))
    return out


def routed_keys(draft: dict) -> set[tuple[str, str]]:
    """仍然待办的分流身份：分流表里未被晋升消费的那部分。"""
    promoted = promoted_keys(draft)
    out = set()
    for r in draft.get("cross_module_redirections", []):
        k = (r["upstream_id"], r["original_capability_id"])
        if k in promoted:
            continue
        out.add(k)
    return out


def global_state_counts(draft: dict, index_doc: dict) -> dict:
    """累计三态视图，全部现算。"""
    raw = raw_index_keys(index_doc)
    raw_set = set(raw)
    m = mapped_keys(draft)
    r = routed_keys(draft)
    u = raw_set - m - r
    canonical_ids = [c["canonical_id"] for c in draft.get("canonical_capabilities", [])]
    return {
        "note": "三态互斥；routed_pending 不得计入 mapped；三态并集等于 raw_total",
        "computed_from": [
            "docs/fusion/RAW_CAPABILITY_INDEX.json",
            "docs/fusion/CAPABILITY_CROSSWALK.draft.json",
        ],
        "raw_total": len(raw),
        "raw_unique": len(raw_set),
        "mapped_count": len(m),
        "routed_pending_count": len(r),
        "unreviewed_count": len(u),
        "sum_check": len(m) + len(r) + len(u),
        "canonical_count": len(canonical_ids),
        "routed_promotions_count": len(promoted_keys(draft)),
        "state_invariants": {
            "mutually_exclusive": len(m & r) == 0 and len(m & u) == 0 and len(r & u) == 0,
            "union_equals_total": (m | r | u) == raw_set,
            "no_ghost_identities": (m | r) <= raw_set,
            "routed_not_counted_as_mapped": len(m & r) == 0,
        },
        "by_upstream": {
            up: {
                "mapped": sum(1 for k in m if k[0] == up),
                "routed": sum(1 for k in r if k[0] == up),
                "unreviewed": sum(1 for k in u if k[0] == up),
            } for up in UPSTREAMS
        },
    }


def module_rollup(draft: dict) -> list[dict]:
    """按 owner_module 汇总 canonical 数与承接身份数。"""
    roll: dict[str, dict] = {}
    for cap in draft.get("canonical_capabilities", []):
        mod = cap["owner_module"]
        row = roll.setdefault(mod, {"module": mod, "canonical_count": 0,
                                    "canonical_ids": [], "raw_mapped": 0})
        row["canonical_count"] += 1
        row["canonical_ids"].append(cap["canonical_id"])
        row["raw_mapped"] += len(cap.get("upstream_refs", []))
    return [roll[k] for k in sorted(roll)]


def batch_entry(batch: str, module: str, canonical_ids: list[str],
                raw_mapped: int, raw_redirected: int, per_source_mapped: dict) -> dict:
    """单个批次的自身统计。字段名明确表态是「本批次」。"""
    return {
        "batch": batch,
        "module": module,
        "canonical_ids": canonical_ids,
        "raw_mapped_to_this_module": raw_mapped,
        "raw_redirected_to_other_modules": raw_redirected,
        "dedup_ratio": round(raw_mapped / len(canonical_ids), 3) if canonical_ids else None,
        "dedup_ratio_definition": "raw_mapped_to_this_module / canonical_count",
        "per_source_mapped": {u: per_source_mapped.get(u, 0) for u in UPSTREAMS},
    }


BATCH_NAMES = {"Facts": "F1-B/Facts", "Collector": "F1-B/Collector",
               "Evidence-Claims": "F1-B/Evidence-Claims", "Product": "F1-B/Product",
               "Research": "F1-B/Research"}
# 批次的业务顺序（不是字母序）：batch_summary 取最后一批，必须是真正最近完成的那一批。
BATCH_ORDER = ["Facts", "Collector", "Evidence-Claims", "Product", "Research",
               "Lifecycle", "Security", "Renderer", "Storage", "DSH Adapter"]

# 出向分流的权威是「各模块 def 文件的 DEFERRED_TO_OTHER_MODULE 声明」，不是草稿里
# 的 cross_module_redirections——后者是逐批落盘的不完整记录（哪个批次后跑就只有
# 谁的分流），拿它当上限会漏数。声明再减去已被晋升消费的键，才是真正的挂起分流。
_MODULE_DEFS = {"Facts": "f1b_facts_def", "Collector": "f1b_collector_def",
                "Evidence-Claims": "f1b_ec_def", "Product": "f1b_product_def",
                "Research": "f1b_research_def"}


def _module_def(module: str):
    if module not in _MODULE_DEFS:
        return None
    import importlib
    return importlib.import_module(_MODULE_DEFS[module])


def batches_from_draft(draft) -> list:
    """从草稿现算全部已落盘批次的自身统计。

    为什么不在各构建器里各自 append：批次是横切视图，任何单个构建器都只持有
    自己那一批的数字。让每个构建器 append 自己那一批、再删自己那一批重写，
    结果是「后跑的覆盖先跑的」——本轮实测：Collector 重建后 Facts 批次条目消失。
    所以统一按 canonical 的 owner_module 分组现算，与谁最后跑无关。

    分流的归属取「本源身份所属的那个模块」，不是重定向记录里的 owner_module——
    owner_module 记的是分流去向（目标模块），拿它当归属会把数算到别人头上。
    判据：本源身份不在任何 canonical 的 upstream_refs 里（即未承接），且存在一条
    指向它的重定向，则它算作「该源模块分流出去」的一条。

    批次顺序取 BATCH_ORDER 的业务顺序，不按字母排 —— 否则 Collector 会排在
    Facts 前面，batch_summary（= 最后一批）就指错了批次。
    """
    # 分流去向（保留读取以便诊断；出向计数不依赖它，见下方按 def 声明现算）
    redirected_ids = {identity_key(r)
                      for r in draft.get("cross_module_redirections") or []}
    promoted = promoted_keys(draft)

    groups = {}
    for c in draft.get("canonical_capabilities") or []:
        g = groups.setdefault(c.get("owner_module"), {"ids": [], "mapped": set()})
        g["ids"].append(c["canonical_id"])
        for ref in c.get("upstream_refs") or []:
            g["mapped"].add(identity_key(ref))
    all_mapped = set().union(*(g["mapped"] for g in groups.values())) if groups else set()

    # 出向分流按模块现算：def 声明 − 已被晋升消费的键。草稿里的
    # cross_module_redirections 只是落盘残影，不参与上限。
    out_redirects = {}
    for mod in set(list(groups) + list(_MODULE_DEFS)):
        dmod = _module_def(mod)
        if dmod is None:
            continue
        declared = {tuple(k) for k in getattr(dmod, "DEFERRED_TO_OTHER_MODULE", {})}
        pending = declared - promoted
        if pending:
            out_redirects[mod] = pending

    order = {m: i for i, m in enumerate(BATCH_ORDER)}
    mods = sorted(groups, key=lambda m: (order.get(m, len(order)), m))

    out = []
    for mod in mods:
        g = groups[mod]
        out.append(batch_entry(
            batch=BATCH_NAMES.get(mod, f"F1-B/{mod}"), module=mod,
            canonical_ids=sorted(g["ids"]),
            raw_mapped=len(g["mapped"]),
            raw_redirected=len(out_redirects.get(mod, ())),
            per_source_mapped={u: sum(1 for k in g["mapped"] if k[0] == u)
                               for u in UPSTREAMS},
        ))
    return out
