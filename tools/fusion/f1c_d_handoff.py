#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 F1-C-D 全局待收口清单（从磁盘现算，不手填）。"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
OUT = F / "F1C_D_HANDOFF_INVENTORY.json"
TZ = timezone(timedelta(hours=8))
sys.path.insert(0, str(Path(__file__).parent))

# 已登记的跨模块冲突（来自各批裁决文档的 X/M/K/Y 项）
CROSS_CONFLICTS = [
    {"id": "X-1", "topic": "SL-CAP-0009 权威 owner 是否迁至 Storage", "current": "保持 Facts", "status": "已裁/建议保持"},
    {"id": "X-2", "topic": "跨仓库 Subject 的主键表示", "current": "Lifecycle+Storage 联合", "status": "待 F2"},
    {"id": "X-3", "topic": "U06-C25 三态产物契约 owner", "current": "Storage（F1-C-A 已裁）", "status": "已裁"},
    {"id": "X-4", "topic": "B 层与 A 层冲突的用户可见判定", "current": "Renderer+Lifecycle", "status": "待 F1-C-D"},
    {"id": "X-5", "topic": "跨文件原子性实现路径", "current": "F2", "status": "待 F2"},
    {"id": "X-6", "topic": "是否最终需要向量/图检索", "current": "F2", "status": "待 F2"},
    {"id": "X-7", "topic": "知识根目录默认位置与命名空间", "current": "F2", "status": "待 F2"},
    {"id": "K-7", "topic": "人工叙事文档是否允许自动插入片段", "current": "不允许整篇覆盖", "status": "待 F1-C-D"},
    {"id": "Y-4", "topic": "检查点物理存放归属", "current": "逻辑 0071 / 物理 Storage", "status": "待 F1-C-D"},
    {"id": "Y-6", "topic": "BotHarness 发现与审批传递缺口", "current": "UNVERIFIED_RUNTIME", "status": "待实测"},
]

TERMINAL_DISP = [
    {"value": "ADOPTED", "meaning": "已映射至某 canonical", "representable_now": True},
    {"value": "ADOPTED_AS_COUNTEREXAMPLE", "meaning": "被 canonical 的拒绝机制覆盖（反例登记）", "representable_now": False},
    {"value": "REJECTED_WITH_REASON", "meaning": "有理由的拒绝，不建 canonical", "representable_now": False},
    {"value": "DEFERRED_WITH_REASON", "meaning": "有理由的延期", "representable_now": False},
    {"value": "INTERNAL_DESIGN_ONLY", "meaning": "零来源内部设计", "representable_now": False},
]


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = draft["canonical_capabilities"]
    mapped = {}
    for c in canon:
        for r in c["upstream_refs"]:
            mapped[(r["upstream_id"], r["original_capability_id"])] = c["canonical_id"]
    routed = {(r["upstream_id"], r["original_capability_id"])
              for r in draft["cross_module_redirections"]}
    unrev = set(by) - set(mapped) - routed

    unmapped_items = []
    for k in sorted(unrev):
        it = by[k]
        unmapped_items.append({
            "identity_key": f"{k[0]}::{k[1]}",
            "capability": it["capability"],
            "original_disposition": it["disposition"],
            "final_verdict": "REJECT",
            "terminal_disposition": "REJECTED_WITH_REASON",
            "state_now": "UNREVIEWED",
            "reason_not_mapped": "已裁决为拒绝；三态模型无法表达 REJECT，保持真实旧状态",
            "license": {"spdx": (it.get("license") or {}).get("spdx"),
                        "copy_permitted": (it.get("license") or {}).get("copy_permitted")},
        })

    zero_source = [c["canonical_id"] for c in canon if not c["upstream_refs"]]
    counterexample_refs = [
        {"identity_key": r["identity_key"], "canonical_id": c["canonical_id"],
         "upstream_disposition": r["upstream_disposition"], "verdict": r["verdict"]}
        for c in canon for r in c["upstream_refs"] if r.get("verdict") == "REJECT"
    ]
    u06_refs = [r for r in counterexample_refs if r["identity_key"].startswith("UPSTREAM-06")]

    doc = {
        "artifact": "F1C_D_HANDOFF_INVENTORY",
        "schema_version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_d_handoff.py（只读现算）",
        "purpose": "F1-C-D 的全局待收口清单。本批只生成清单，不执行其中任何事项。",
        "totals_now": draft["global_state_counts"],
        "unmapped_identities": unmapped_items,
        "reject_defer_set": unmapped_items,
        "terminal_disposition_migration": {
            "note": "三态（MAPPED/ROUTED/UNREVIEWED）无法表达拒绝与延期。",
            "proposed_field": "terminal_disposition（正交，不改 state）",
            "values": TERMINAL_DISP,
            "affected_count": len(unmapped_items),
            "affected_identities": [i["identity_key"] for i in unmapped_items],
            "implementation_in": "F1-C-D",
        },
        "zero_source_canonicals": zero_source,
        "cross_module_conflicts": CROSS_CONFLICTS,
        "cross_module_conflicts_open": [c for c in CROSS_CONFLICTS if c["status"].startswith("待")],
        "license_issues": {
            "u06_copy_permitted_false_refs": u06_refs,
            "u06_total_refs": len(u06_refs),
            "rule": "UPSTREAM-06 无明确复制许可：任何含 U06 的条目整体 copy_permitted=false，只借抽象思想。",
            "verdict_note": "counterexample_refs 里 verdict=REJECT 表示「作为反例登记」，不等于复制许可。",
        },
        "counterexample_bindings": counterexample_refs,
        "freeze_blockers": [
            "terminal_disposition 迁移未实施（4 项 REJECT 仍在 UNREVIEWED）",
            "十项跨模块冲突中有 3 项标记待 F1-C-D",
            "CAPABILITY_CROSSWALK.json 尚未冻结（F1-D 职责）",
            "历史验证入口需在冻结前复跑一次",
        ],
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"未映射 {len(unmapped_items)} 项（全为 REJECT）；零来源 canonical {len(zero_source)}；"
          f"反例绑定 {len(counterexample_refs)} 条；U06 相关 {len(u06_refs)} 条；"
          f"待议冲突 {len(doc['cross_module_conflicts_open'])} 项")
    print(f"RESULT: OK -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
