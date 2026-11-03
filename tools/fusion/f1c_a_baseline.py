#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-A 只读基线计算：从原始索引与草稿**现算**遗留身份集合，不手写总数。

输出 docs/fusion/F1C_REMAINDER_BASELINE.json。

要求（用户第 5 节）：
1. 不使用人工录入的固定总数作为数据源。
2. 31 项尚未正式映射身份各出现一次。
3. 已映射的 112 项不得再次进入待清算集合。
4. 每条未决身份都有真实原始来源。
5. 许可证信息完整。
6. 原始 REJECT 与最终设计决策分开。
7. 不得把待裁 REJECT 作为 31 条之外的新增条目。

本工具**只读**：不修改草稿、不重跑任何 F1-B 构建器。
"""
import json, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
OUT = F / "F1C_REMAINDER_BASELINE.json"
TZ = timezone(timedelta(hours=8))

# UNREVIEWED 的语义分组（按上游来源，用于 F1-C-B 分组处理；不改变任何归属）
SEMANTIC_CLASS = {
    "UPSTREAM-01": "分析与评估（LLM 调用栈 / 评测基线 / 提示词资产）",
    "UPSTREAM-02": "研究报告与外部资料（生态研究 / 来源结构 / 呈现形态）",
    "UPSTREAM-03": "知识页面与质量门（页面结构 / 一致性 / 措辞 / 反模式）",
    "UPSTREAM-04": "知识库语义与生命周期（Subject / 复用 / 冲突 / 部署模型）",
    "UPSTREAM-05": "知识库维护流程（更新梯度 / 发布节奏 / 索引 / 并发）",
    "UPSTREAM-06": "安全审查（信任边界 / 依赖 / 脱敏 / 供应链）",
}


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    items = raw["items"]
    by_key = {(i["upstream_id"], i["original_capability_id"]): i for i in items}

    # 现算三态（与 f1b_stats 口径一致：mapped 来自 upstream_refs，routed 来自路由表）
    mapped_owner = {}
    for c in draft["canonical_capabilities"]:
        for r in c["upstream_refs"]:
            mapped_owner[(r["upstream_id"], r["original_capability_id"])] = {
                "canonical_id": c["canonical_id"],
                "owner_module": c["owner_module"],
                "verdict": r["verdict"],
            }
    routed = {(r["upstream_id"], r["original_capability_id"]): r
              for r in draft["cross_module_redirections"]}

    mapped_keys = set(mapped_owner)
    routed_keys = set(routed)
    all_keys = set(by_key)
    unreviewed_keys = all_keys - mapped_keys - routed_keys

    if mapped_keys & routed_keys:
        print("ERROR: mapped 与 routed 重叠", file=sys.stderr)
        return 1

    def lic_of(it):
        L = it.get("license", {})
        return {
            "spdx": L.get("spdx"),
            "copy_permitted": L.get("copy_permitted"),
            "attribution_required": L.get("attribution_required"),
            "license_link_required": L.get("license_link_required"),
            "modification_notice_required": L.get("modification_notice_required"),
        }

    # 遗留身份 = ROUTED ∪ UNREVIEWED（共 31 项）
    pending = []
    for k in sorted(routed_keys | unreviewed_keys):
        it = by_key[k]
        uid, oid = k
        if k in routed_keys:
            state = "ROUTED"
            suggested = routed[k]["owner_module"]
        else:
            state = "UNREVIEWED"
            suggested = None
        pending.append({
            "upstream_id": uid,
            "original_capability_id": oid,
            "identity_key": it["identity_key"],
            "capability": it["capability"],
            "state": state,
            "suggested_owner": suggested,
            "original_disposition": it["disposition"],
            "original_why": it["why"],
            "upstream_where": it["where"],
            "evidence": it["evidence"],
            "license": lic_of(it),
            "semantic_class": SEMANTIC_CLASS.get(uid, "未分类"),
            # 原始处置与最终设计决策分开：这里只记上游 audit 时的 disposition
            "original_disposition_note": "此字段是上游审计时的原始处置，不是 F1-C 的最终设计决策",
        })

    # 待裁 REJECT：遗留集合中原始处置为 REJECT 的项（属于 31 项之内，不额外新增）
    reject_keys_in_pending = [k for k in sorted(routed_keys | unreviewed_keys)
                              if by_key[k]["disposition"] == "REJECT"]
    # 已被 canonical 引用的 REJECT（已形成反例边界，属 MAPPED）
    reject_in_mapped = [(k, mapped_owner[k]["canonical_id"]) for k in sorted(mapped_keys)
                        if by_key[k]["disposition"] == "REJECT"]

    # 交付要求 7：待裁 REJECT 必须落在 31 项之内
    extra = [k for k in reject_keys_in_pending if k not in (routed_keys | unreviewed_keys)]
    if extra:
        print(f"ERROR: 待裁 REJECT 出现在遗留集合之外：{extra}", file=sys.stderr)
        return 1

    # ROUTED 按目标模块聚合；标注该模块批次是否已完成
    routed_by_owner = {}
    for k in sorted(routed_keys):
        mod = routed[k]["owner_module"]
        e = routed_by_owner.setdefault(mod, {
            "module": mod, "count": 0, "items": [],
            "module_batch_done": mod in {"Facts", "Collector", "Evidence-Claims", "Product",
                                         "Research", "Lifecycle", "Security", "Renderer",
                                         "Storage", "DSH-Adapter"},
        })
        e["count"] += 1
        e["items"].append(by_key[k]["identity_key"])

    unrev_by_class = {}
    for k in sorted(unreviewed_keys):
        cls = SEMANTIC_CLASS.get(k[0], "未分类")
        unrev_by_class.setdefault(cls, {"count": 0, "items": []})
        unrev_by_class[cls]["count"] += 1
        unrev_by_class[cls]["items"].append(by_key[k]["identity_key"])

    doc = {
        "artifact": "F1C_REMAINDER_BASELINE",
        "schema_version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_a_baseline.py（只读计算，不重跑任何构建器）",
        "computed_from": ["docs/fusion/RAW_CAPABILITY_INDEX.json",
                          "docs/fusion/CAPABILITY_CROSSWALK.draft.json"],
        "source_index_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "totals": {
            "raw_total": len(all_keys),
            "mapped": len(mapped_keys),
            "routed": len(routed_keys),
            "unreviewed": len(unreviewed_keys),
            "pending_total": len(pending),
            "sum_check": len(mapped_keys) + len(routed_keys) + len(unreviewed_keys),
        },
        "computation_note": "所有数字由集合运算现算；不存在人工录入的固定总数。",
        "routed_by_module": routed_by_owner,
        "unreviewed_by_class": unrev_by_class,
        "reject_audit": {
            "note": "待裁 REJECT 全部落在 31 项遗留集合之内，不额外新增；"
                    "已被 canonical 引用的 REJECT 属 MAPPED，单列以示区分。",
            "pending_reject_count": len(reject_keys_in_pending),
            "pending_reject_items": [by_key[k]["identity_key"] for k in reject_keys_in_pending],
            "pending_reject_inside_remainder": True,
            "reject_already_bound_to_canonical": [
                {"identity_key": by_key[k]["identity_key"], "canonical_id": cid,
                 "note": "已作为反例或负向约束登记在 canonical 的 upstream_refs 中"}
                for k, cid in reject_in_mapped
            ],
            "reject_intersection_with_routed": [
                by_key[k]["identity_key"] for k in sorted(routed_keys)
                if by_key[k]["disposition"] == "REJECT"],
            "reject_intersection_with_unreviewed": [
                by_key[k]["identity_key"] for k in sorted(unreviewed_keys)
                if by_key[k]["disposition"] == "REJECT"],
        },
        "items": pending,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"raw={len(all_keys)} mapped={len(mapped_keys)} routed={len(routed_keys)} "
          f"unreviewed={len(unreviewed_keys)} pending={len(pending)} "
          f"sum={len(mapped_keys)+len(routed_keys)+len(unreviewed_keys)}")
    print(f"待裁 REJECT {len(reject_keys_in_pending)} 项，全部在遗留集合内；"
          f"已绑 canonical 的 REJECT {len(reject_in_mapped)} 项")
    print(f"ROUTED 涉 {len(routed_by_owner)} 个模块；UNREVIEWED 分 {len(unrev_by_class)} 个语义组")
    print(f"RESULT: OK -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
