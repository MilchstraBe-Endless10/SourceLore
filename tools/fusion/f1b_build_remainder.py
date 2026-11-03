#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从当前 Crosswalk 与原始索引**计算**全量剩余能力清单，不手写。

输出 docs/fusion/F1B_REMAINDER_INVENTORY.json：
逐项列出 143 个身份的状态 / 建议 owner / disposition / 许可 / 未处理原因 / 归属争议 / 待 F1-C 决策。

核心立场：F1-B 十批次全部完成不等于 143 项原始能力已全部完成归属裁决。
本清单的意义是把「还欠多少」算清楚，而不是把统计凑成 143/0/0。
"""
import json, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
OUT = F / "F1B_REMAINDER_INVENTORY.json"
TZ = timezone(timedelta(hours=8))

# UNREVIEWED 的语义分类：按上游来源 + 能力名启发式归入所属领域，不塞进 DSH-Adapter
SEMANTIC_CLASS = {
    "UPSTREAM-01": "分析与评估（LLM 调用栈 / 评测基线 / 提示词资产）",
    "UPSTREAM-02": "研究报告与外部资料（生态研究 / 来源结构 / 呈现形态）",
    "UPSTREAM-03": "知识页面与质量门（页面结构 / 一致性 / 措辞 / 反模式）",
    "UPSTREAM-04": "知识库语义与生命周期（Subject / 复用 / 冲突 / 部署模型）",
    "UPSTREAM-05": "知识库维护流程（更新梯度 / 发布节奏 / 索引 / 并发）",
    "UPSTREAM-06": "安全审查（信任边界 / 依赖 / 脱敏 / 供应链）",
}

# 已知的归属争议（来自各批次登记的 X-1..X-7 / M-* / K-* 等），逐条列出以便 F1-C 裁决
DISPUTED = {
    ("UPSTREAM-06", "C25"): {
        "current_owner_in_crosswalk": "Storage",
        "disputed_owner": "Evidence-Claims",
        "note": "Security 批判 Storage；Storage 批复核认为其语义层（产物契约的含义）应由 EC 承接。"
                "按「不擅自改归属」保留原判，分歧交 F1-C。",
        "decision_ref": "F1B_STORAGE_DECISIONS.md 的 X-3",
    },
    ("SL-CAP-0009", "owner"): {
        "current_owner_in_crosswalk": "Facts",
        "disputed_owner": "Storage",
        "note": "Canonical Knowledge Registry 是实体消解的语义权威清单；Storage 只持久化其产物。"
                "建议保持 Facts，是否迁移交 F1-C。",
        "decision_ref": "F1B_STORAGE_DECISIONS.md 的 M-A / X-1",
    },
}


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    items = raw["items"]
    by_key = {(i["upstream_id"], i["original_capability_id"]): i for i in items}

    mapped = {}
    for c in draft["canonical_capabilities"]:
        for r in c["upstream_refs"]:
            mapped[(r["upstream_id"], r["original_capability_id"])] = {
                "canonical_id": c["canonical_id"],
                "owner_module": c["owner_module"],
                "verdict": r["verdict"],
            }
    routed = {(r["upstream_id"], r["original_capability_id"]): r
              for r in draft["cross_module_redirections"]}

    rows = []
    for (uid, oid), it in sorted(by_key.items()):
        k = (uid, oid)
        if k in mapped:
            state = "MAPPED"
            owner = mapped[k]["owner_module"]
            reason = f"已由 {mapped[k]['canonical_id']} 承接（verdict={mapped[k]['verdict']}）"
        elif k in routed:
            state = "ROUTED"
            owner = routed[k]["owner_module"]
            reason = "去向已裁决但目标模块尚未建 canonical 承接"
        else:
            state = "UNREVIEWED"
            owner = None
            reason = "尚未初审归属"
        lic = it.get("license", {})
        row = {
            "upstream_id": uid,
            "original_capability_id": oid,
            "capability": it["capability"],
            "state": state,
            "suggested_owner": owner,
            "original_disposition": it["disposition"],
            "license": {
                "spdx": lic.get("spdx"),
                "copy_permitted": lic.get("copy_permitted"),
                "attribution_required": lic.get("attribution_required"),
            },
            "unprocessed_reason": None if state == "MAPPED" else reason,
            "owner_dispute": DISPUTED.get(k) or DISPUTED.get((uid, oid)) or None,
            "f1c_decision_needed": state != "MAPPED",
        }
        if state == "UNREVIEWED":
            row["semantic_class"] = SEMANTIC_CLASS.get(uid, "未分类")
        rows.append(row)

    state_totals = {
        "mapped": sum(1 for r in rows if r["state"] == "MAPPED"),
        "routed": sum(1 for r in rows if r["state"] == "ROUTED"),
        "unreviewed": sum(1 for r in rows if r["state"] == "UNREVIEWED"),
        "total": len(rows),
    }

    # ROUTED 未承接原因（按目标模块聚合；标注目标模块是否已完成）
    finished_modules = {"Facts", "Collector", "Evidence-Claims", "Product", "Research",
                        "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
    routed_by_owner = {}
    for r in rows:
        if r["state"] != "ROUTED":
            continue
        mod = r["suggested_owner"]
        e = routed_by_owner.setdefault(mod, {"module": mod, "module_batch_done": mod in finished_modules,
                                             "count": 0, "items": []})
        e["count"] += 1
        e["items"].append(f"{r['upstream_id']}::{r['original_capability_id']}")

    # UNREVIEWED 语义分组
    unrev_by_class = {}
    for r in rows:
        if r["state"] != "UNREVIEWED":
            continue
        cls = r["semantic_class"]
        unrev_by_class.setdefault(cls, []).append(
            f"{r['upstream_id']}::{r['original_capability_id']} {r['capability'][:40]}")

    # REJECT 三分类：只看当前仍未 MAPPED 的 REJECT 项
    reject_rows = [r for r in rows
                   if r["original_disposition"] == "REJECT" and r["state"] != "MAPPED"]
    reject_classification = {
        "adjudicated": [],          # 已明确裁决的拒绝行为（但其身份已 MAPPED 的不在此列）
        "design_counterexample": [],  # 已形成 canonical 设计边界反例（其身份已 MAPPED，此处补记说明）
        "pending_f1c": [],          # 尚需 F1-C 处理的独立拒绝项
        "note": "只统计当前仍未 MAPPED 的 REJECT 身份；"
                "已被某个 canonical 作为反例引用的（design_counterexample）请在对应批次文档中查证。",
    }
    for c in draft["canonical_capabilities"]:
        for r in c["upstream_refs"]:
            if r["verdict"] == "REJECT":
                reject_classification["design_counterexample"].append(
                    f"{r['upstream_id']}::{r['original_capability_id']} → {c['canonical_id']}")
    for r in reject_rows:
        reject_classification["pending_f1c"].append(
            f"{r['upstream_id']}::{r['original_capability_id']} {r['capability'][:40]}")

    doc = {
        "artifact": "F1B_REMAINDER_INVENTORY",
        "schema_version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_build_remainder.py",
        "computed_from": ["docs/fusion/RAW_CAPABILITY_INDEX.json",
                          "docs/fusion/CAPABILITY_CROSSWALK.draft.json"],
        "source_index_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "disclaimer": (
            "F1-B 十个模块批次全部完成，但不等于 143 项原始能力已全部完成归属裁决。"
            "本清单从当前 Crosswalk 计算得出，逐项标明仍待 F1-C 处理的条目。"
            "不得为了让统计变成 143/0/0 而人为制造 canonical。"
        ),
        "state_totals": state_totals,
        "residue": {
            "unreviewed_by_class": unrev_by_class,
            "routed_unclaimed": routed_by_owner,
            "reject_classification": reject_classification,
        },
        "items": rows,
    }

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"items={len(rows)}  mapped={state_totals['mapped']}  "
          f"routed={state_totals['routed']}  unreviewed={state_totals['unreviewed']}")
    print(f"UNREVIEWED 语义分 {len(unrev_by_class)} 组；ROUTED 未承接涉 {len(routed_by_owner)} 个模块；"
          f"REJECT 待裁 {len(reject_classification['pending_f1c'])} 项")
    print(f"RESULT: OK -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
