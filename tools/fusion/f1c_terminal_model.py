#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终态模型推导（纯函数，供 f1c_apply_routed.py 在写盘前调用）。

三个正交概念：
  mapping_status         MAPPED / ROUTED / UNREVIEWED（进度，不改）
  terminal_disposition   ADOPTED / ADOPTED_AS_COUNTEREXAMPLE / REJECTED_WITH_REASON / DEFERRED_WITH_REASON
  canonical_origin_type  UPSTREAM_DERIVED / INTERNAL_DESIGN_ONLY
"""

VALID_TERMINAL = ["ADOPTED", "ADOPTED_AS_COUNTEREXAMPLE",
                  "REJECTED_WITH_REASON", "DEFERRED_WITH_REASON"]
VALID_ORIGIN = ["UPSTREAM_DERIVED", "INTERNAL_DESIGN_ONLY"]
VALID_ROLE = ["positive", "counterexample", "mixed"]


def derive(draft, raw, decided_reject):
    """从 draft + raw 推导终态。decided_reject: {(uid,cid): {reason,batch,...}}。

    纯函数：输出只依赖输入内容，遍历前显式排序，不依赖 dict 顺序。
    """
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = draft["canonical_capabilities"]

    uses = {}
    for c in canon:
        for r in c["upstream_refs"]:
            k = (r["upstream_id"], r["original_capability_id"])
            uses.setdefault(k, []).append({
                "canonical_id": c["canonical_id"],
                "verdict": r["verdict"],
                "upstream_disposition": r["upstream_disposition"],
                "upstream_capability": r["upstream_capability"],
            })

    mapped = set(uses)
    routed = {(r["upstream_id"], r["original_capability_id"])
              for r in draft["cross_module_redirections"]}

    out, origins = {}, {}
    for k in sorted(by):
        it = by[k]
        u = uses.get(k, [])
        positive = [x for x in u if x["verdict"] != "REJECT"]
        counter = [x for x in u if x["verdict"] == "REJECT"]

        if k in mapped:
            if positive and counter:
                td, role, basis = "ADOPTED", "mixed", "同一身份既有正向承接、又有反例绑定"
            elif positive:
                td, role, basis = "ADOPTED", "positive", "以非 REJECT verdict 正向承接"
            else:
                td, role, basis = ("ADOPTED_AS_COUNTEREXAMPLE", "counterexample",
                                   "仅以 REJECT verdict 登记为反例约束，不采纳其行为")
            ms = "MAPPED"
        elif k in routed:
            td, role, basis = "DEFERRED_WITH_REASON", "positive", "已裁决去向但目标模块尚未承接"
            ms = "ROUTED"
        elif k in decided_reject:
            td, role, basis = decided_reject[k]["terminal_disposition"], "counterexample", \
                "已裁决为拒绝，未建立任何 canonical 关联"
            ms = "UNREVIEWED"
        else:
            raise SystemExit(
                f"ERROR: 身份 {k[0]}::{k[1]} 无法推导终态"
                f"（不在映射、不在分流、也无拒绝裁决）——数据不支持，拒绝默认 ADOPTED。")

        if td not in VALID_TERMINAL:
            raise SystemExit(f"ERROR: {k} 终态 {td} 非法")
        if role not in VALID_ROLE:
            raise SystemExit(f"ERROR: {k} 角色 {role} 非法")

        inconsistent = [x for x in u
                        if (x["upstream_disposition"] == "REJECT") != (x["verdict"] == "REJECT")]
        key = f"{k[0]}::{k[1]}"
        out[key] = {
            "value": td,
            "basis": basis,
            "role": role,
            "mapping_status": ms,
            "upstream_disposition": it["disposition"],
            "upstream_capability": it["capability"],
            "adopted_parts": [f"{x['canonical_id']}：{x['upstream_capability']}" for x in positive],
            "rejected_parts": [f"{x['canonical_id']}：{x['upstream_capability']}" for x in counter],
            "upstream_verdict_inconsistent": [
                {"canonical_id": x["canonical_id"],
                 "upstream_disposition": x["upstream_disposition"],
                 "verdict": x["verdict"]} for x in inconsistent],
            "copy_permitted": (it.get("license") or {}).get("copy_permitted"),
            "license_note": ("终态与复制权限无关：ADOPTED 不等于获得复制许可"
                             if (it.get("license") or {}).get("copy_permitted") is False else None),
        }

    for c in canon:
        c["origin_type"] = ("UPSTREAM_DERIVED" if c["upstream_refs"] else "INTERNAL_DESIGN_ONLY")
        if c["origin_type"] not in VALID_ORIGIN:
            raise SystemExit(f"ERROR: {c['canonical_id']} origin 非法")
        origins[c["canonical_id"]] = {
            "origin_type": c["origin_type"],
            "upstream_ref_count": len(c["upstream_refs"]),
            "internal_need_basis": (c.get("merge_note")
                                    if c["origin_type"] == "INTERNAL_DESIGN_ONLY" else None),
        }

    from collections import Counter
    td_dist = dict(sorted(Counter(v["value"] for v in out.values()).items()))
    or_dist = dict(sorted(Counter(v["origin_type"] for v in origins.values()).items()))
    rl_dist = dict(sorted(Counter(v["role"] for v in out.values()).items()))

    draft["terminal_model"] = {
        "schema_version": 1,
        "orthogonal_fields": ["mapping_status", "terminal_disposition", "canonical_origin_type"],
        "laws": [
            "终态与 mapping_status 正交：REJECTED_WITH_REASON 可对应 UNREVIEWED，不伪造 MAPPED",
            "终态与复制权限正交：ADOPTED 不推导 copy_permitted；U06 仍为 false",
            "ADOPTED_AS_COUNTEREXAMPLE 只表示把被拒机制当反面约束，不表示采纳其行为",
            "INTERNAL_DESIGN_ONLY 是 canonical 的来源性质，不强制赋给任何上游身份",
        ],
        "terminal_dispositions": out,
        "canonical_origins": origins,
    }
    draft["global_state_counts"]["terminal_disposition_counts"] = td_dist
    draft["global_state_counts"]["canonical_origin_counts"] = or_dist
    draft["global_state_counts"]["adoption_role_counts"] = rl_dist
    return td_dist, or_dist, rl_dist
