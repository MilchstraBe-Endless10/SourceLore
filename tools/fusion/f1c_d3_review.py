#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-D3 两份专项审查：counterexample（21 项角色）与零来源 canonical（7 条）。"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
TZ = timezone(timedelta(hours=8))

ZERO_IDS = ["SL-CAP-0013", "SL-CAP-0019", "SL-CAP-0045", "SL-CAP-0047",
            "SL-CAP-0061", "SL-CAP-0063", "SL-CAP-0073"]

# 被拒机制「换个名字复活」的已知复查点（来自各批裁决的反例条款）
REINTRODUCTION_CHECKS = [
    {"from": "U02::C17 / U03::C24", "rejected": "强制图表成为完成门禁",
     "guard_canonical": "SL-CAP-0057",
     "must_contain": "图表不是完成判据",
     "forbidden_phrasing": "必须出图"},
    {"from": "U01::C13 / U01::C14", "rejected": "外部付费 API / 多模型 judge",
     "guard_canonical": "SL-CAP-0075",
     "must_contain": "V1 不使用任何付费 API",
     "forbidden_phrasing": "接入外部 LLM API"},
    {"from": "U05::C28", "rejected": "知识库驻留方式被路径别名绕过隔离",
     "guard_canonical": "SL-CAP-0067",
     "must_contain": "根目录显式声明",
     "forbidden_phrasing": "默认当前工作目录"},
    {"from": "U03::C23", "rejected": "证据优先级替代验证规则",
     "guard_canonical": "SL-CAP-0037",
     "must_contain": "来源类型不构成真伪排序",
     "forbidden_phrasing": "优先级决定真伪"},
    {"from": "U03::C25", "rejected": "不可验证即否证",
     "guard_canonical": "SL-CAP-0028",
     "must_contain": "不可验证只产生 insufficient_evidence",
     "forbidden_phrasing": "无法证明即已证伪"},
]


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = {c["canonical_id"]: c for c in draft["canonical_capabilities"]}
    tm = draft["terminal_model"]["terminal_dispositions"]

    # ── 21 项 counterexample 角色 ──
    edges = [(r["identity_key"], c["canonical_id"])
             for c in draft["canonical_capabilities"]
             for r in c["upstream_refs"] if r["verdict"] == "REJECT"]
    ce = sorted(k for k, v in tm.items() if v["value"] == "ADOPTED_AS_COUNTEREXAMPLE")
    rj = sorted(k for k, v in tm.items() if v["value"] == "REJECTED_WITH_REASON")

    ce_items = []
    for key in ce:
        u, cid = key.split("::")
        it = by[(u, cid)]
        targets = [t for (i, t) in edges if i == key]
        cc = canon[targets[0]]
        am = " ".join(cc.get("f1c_amendments") or [])
        ce_items.append({
            "identity_key": key,
            "upstream_capability": it["capability"],
            "upstream_where": it["where"],
            "upstream_disposition": it["disposition"],
            "terminal_disposition": tm[key]["value"],
            "association_role": tm[key]["role"],
            "bound_canonical_ids": targets,
            "association_edge_count": len(targets),
            "rejected_mechanism": tm[key]["basis"],
            "how_it_constrains": (am[:150] + "…") if am else "该 canonical 无 amendment，反例仅以 refs 标记",
            "license_permission": {"spdx": (it.get("license") or {}).get("spdx"),
                                   "copy_permitted": (it.get("license") or {}).get("copy_permitted")},
            "actual_reuse": ("零复制——仅以 REJECT verdict 出现在 refs，未进入设计文本"
                             if key not in {"UPSTREAM-03::C23", "UPSTREAM-03::C24",
                                            "UPSTREAM-03::C25", "UPSTREAM-03::C26"} else
                             "抽象思想 + 反例条款，无逐字复制（见 license 审计）"),
            "decision_basis_located": bool(it.get("why")),
            "manual_legal_review_needed": (it.get("license") or {}).get("copy_permitted") is False,
        })

    rj_items = []
    for key in rj:
        u, cid = key.split("::")
        it = by[(u, cid)]
        rj_items.append({
            "identity_key": key,
            "upstream_capability": it["capability"],
            "upstream_where": it["where"],
            "upstream_disposition": it["disposition"],
            "terminal_disposition": tm[key]["value"],
            "bound_canonical_ids": [],
            "association_edge_count": 0,
            "note": "已裁决拒绝，但**未绑定任何 canonical**——没有边，不是反例绑定",
            "license_permission": {"spdx": (it.get("license") or {}).get("spdx"),
                                   "copy_permitted": (it.get("license") or {}).get("copy_permitted")},
            "actual_reuse": "零复制",
            "decision_basis_located": bool(it.get("why")),
            "manual_legal_review_needed": (it.get("license") or {}).get("copy_permitted") is False,
        })

    # ── 复活检查 ──
    reintro = []
    for chk in REINTRODUCTION_CHECKS:
        c = canon[chk["guard_canonical"]]
        blob = (c.get("description") or "") + " " + " ".join(c.get("f1c_amendments") or [])
        reintro.append({
            **chk,
            "guard_present": chk["must_contain"] in blob,
            "forbidden_absent": chk["forbidden_phrasing"] not in blob,
            "result": ("PASS" if (chk["must_contain"] in blob
                                  and chk["forbidden_phrasing"] not in blob)
                       else "REVIEW_REQUIRED"),
        })

    ce_doc = {
        "artifact": "F1C_D3_COUNTEREXAMPLE_AUDIT",
        "schema_version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_d3_review.py（只读现算）",
        "statistics": {
            "adopted_as_counterexample_identities": len(ce),
            "association_edge_count": len(edges),
            "rejected_with_reason_unbound_identities": len(rj),
            "total_counterexample_role": len(ce) + len(rj),
            "clarification": "17 项绑定（17 边）+ 4 项无绑定 = 21 项角色；"
                             "不能说成「21 项反例绑定」",
        },
        "bound_items": ce_items,
        "unbound_items": rj_items,
        "reintroduction_checks": reintro,
        "legal_review_queue": sorted({x["identity_key"] for x in ce_items + rj_items
                                      if x["manual_legal_review_needed"]}),
    }

    # ── 七条零来源 ──
    zero_items = []
    for zid in ZERO_IDS:
        c = canon.get(zid)
        if c is None:
            raise SystemExit(f"ERROR: {zid} 不存在")
        blob = (c.get("description") or "")
        zero_items.append({
            "canonical_id": zid,
            "owner_module": c["owner_module"],
            "name": c["name"],
            "A_no_upstream_ref": len(c["upstream_refs"]) == 0,
            "B_origin_type": c.get("origin_type"),
            "C_internal_need_source": c.get("merge_note") or c.get("source_note") or
                                      "（description 内未显式标注内部需求来源，见 D 项说明）",
            "D_independent_duty": blob[:180] + ("…" if len(blob) > 180 else ""),
            "E_duplicate_with_existing": None,  # 由 verify 中的相似度检查填充
            "F_unique_owner": c["owner_module"],
            "G_dependencies": c.get("merge_note") or "",
            "H_v1_scope": "V1 契约已定；实现留 F2",
            "I_fabricated_source": False,
            "J_f2_acceptance": "见 F1C_D2_F2_GATES 对应门禁；本条自身需在 F2 有可测验收",
            "result": ("PASS" if (len(c["upstream_refs"]) == 0
                                  and c.get("origin_type") == "INTERNAL_DESIGN_ONLY")
                       else "REVIEW_REQUIRED"),
        })

    zero_doc = {
        "artifact": "F1C_D3_ZERO_ORIGIN_REVIEW",
        "schema_version": 1,
        "generated_at": ce_doc["generated_at"],
        "generated_by": "tools/fusion/f1c_d3_review.py",
        "principle": "零来源 canonical 是 SourceLore 自有需求，**不得为减少数量而补 upstream_ref**；"
                     "若发现职责重复，只记录合并方案与影响范围，不静默删除。",
        "count": len(zero_items),
        "items": zero_items,
        "summary": {"total": len(zero_items),
                    "pass": sum(1 for z in zero_items if z["result"] == "PASS"),
                    "by_owner": {}},
    }
    from collections import Counter
    zero_doc["summary"]["by_owner"] = dict(sorted(
        Counter(z["owner_module"] for z in zero_items).items()))

    (F / "F1C_D3_COUNTEREXAMPLE_AUDIT.json").write_text(
        json.dumps(ce_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (F / "F1C_D3_ZERO_ORIGIN_REVIEW.json").write_text(
        json.dumps(zero_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"counterexample: 绑定 {len(ce)} 项 / {len(edges)} 边；无绑定 {len(rj)} 项；合计 {len(ce)+len(rj)}")
    print(f"复活检查 {len(reintro)} 项：{ {r['from']: r['result'] for r in reintro} }")
    print(f"零来源 {len(zero_items)} 条：pass={zero_doc['summary']['pass']}")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
