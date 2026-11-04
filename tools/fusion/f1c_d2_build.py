#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-D2 生成器：八项冲突裁决 → 两份 JSON + 裁决登记补记。

从磁盘现算 affected_canonical_ids 的合法性、反例边数、上游许可，
不手填任何可由数据推出的事实。
"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
REG = F / "F1C_DECISION_REGISTER.json"
OUT_C = F / "F1C_D2_CONFLICT_RESOLUTIONS.json"
OUT_G = F / "F1C_D2_F2_GATES.json"
TZ = timezone(timedelta(hours=8))

sys.path.insert(0, str(Path(__file__).parent))
import f1c_d2_decisions as D2

MODULES = {"Facts", "Collector", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = {c["canonical_id"]: c for c in draft["canonical_capabilities"]}
    tm = draft["terminal_model"]["terminal_dispositions"]

    # —— 校验 affected_canonical_ids 真实存在
    bad = []
    for r in D2.RESOLUTIONS:
        for cid in r["affected_canonical_ids"]:
            if cid not in canon:
                bad.append(f"{r['conflict_id']} 引用了不存在的 {cid}")
    if bad:
        raise SystemExit("ERROR: " + "; ".join(bad))

    # —— 校验 owner 模块合法
    # owner 值可能写成「F2 决策记录（唯一 owner：Storage）」这类描述。
    # 判据：值中必须**至少含一个**合法模块名；纯「F2」不算 owner，必须点名模块。
    bad2 = []
    for r in D2.RESOLUTIONS:
        if not r.get("unique_owner"):
            bad2.append(f"{r['conflict_id']} 无 owner")
            continue
        for key, owner_val in r["unique_owner"].items():
            hit = [m for m in MODULES if m in owner_val]
            if not hit:
                bad2.append(f"{r['conflict_id']}.{key} 未点名任何合法模块：{owner_val}")
            # 若写了「F2 ... 唯一 owner：X」，X 必须在模块集中
            if "F2" in owner_val and "唯一 owner" in owner_val:
                after = owner_val.split("唯一 owner：", 1)[1].strip(" ）)")
                if after not in MODULES:
                    bad2.append(f"{r['conflict_id']}.{key} F2 决策记录的 owner 非法：{after}")
    if bad2:
        raise SystemExit("ERROR: " + "; ".join(bad2))

    # —— 反例边（现算）
    edges = [(r["identity_key"], c["canonical_id"])
             for c in draft["canonical_capabilities"]
             for r in c["upstream_refs"] if r["verdict"] == "REJECT"]
    ce_ids = sorted(k for k, v in tm.items() if v["value"] == "ADOPTED_AS_COUNTEREXAMPLE")
    rj_ids = sorted(k for k, v in tm.items() if v["value"] == "REJECTED_WITH_REASON")

    clar = dict(D2.COUNTEREXAMPLE_CLARIFICATION["correct"])
    clar["adopted_as_counterexample_unique_identities"] = len(ce_ids)
    clar["rejected_with_reason_unbound_identities"] = len(rj_ids)
    clar["actual_identity_to_canonical_edges"] = len(edges)
    clar["total_counterexample_role_identities"] = len(ce_ids) + len(rj_ids)

    # —— 反向个案校验
    rev_out = []
    for rc in D2.REVERSE_CASES:
        cid = rc["canonical_id"]
        c = canon[cid]
        ref = next((x for x in c["upstream_refs"]
                    if x["identity_key"] == rc["identity_key"]), None)
        if ref is None:
            raise SystemExit(f"ERROR: {rc['identity_key']} 未绑定到 {cid}")
        if ref["upstream_disposition"] != rc["upstream_disposition"]:
            raise SystemExit(f"ERROR: {rc['identity_key']} upstream_disposition 不符")
        if ref["verdict"] != rc["sourcelore_verdict"]:
            raise SystemExit(f"ERROR: {rc['identity_key']} verdict 不符")
        # 许可现算，不手填
        lic = by[tuple(rc["identity_key"].split("::"))].get("license") or {}
        rev_out.append({**rc,
                        "license_actual": {"spdx": lic.get("spdx"),
                                           "copy_permitted": lic.get("copy_permitted")},
                        "verified": True})

    resolutions = []
    for r in D2.RESOLUTIONS:
        each = dict(r)
        each["affected_canonical_count"] = len(r["affected_canonical_ids"])
        resolutions.append(each)

    conflicts_doc = {
        "artifact": "F1C_D2_CONFLICT_RESOLUTIONS",
        "schema_version": 1,
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_d2_build.py（数据源 f1c_d2_decisions.py）",
        "basis": {
            "identities": len(by),
            "canonicals": len(canon),
            "mapping_status": {"MAPPED": draft["global_state_counts"]["mapped_count"],
                               "ROUTED": draft["global_state_counts"]["routed_pending_count"],
                               "UNREVIEWED": draft["global_state_counts"]["unreviewed_count"]},
            "terminal_disposition": draft["global_state_counts"]["terminal_disposition_counts"],
        },
        "source_note": ("X-2/X-4/X-5/X-6/X-7 取自 F1B_STORAGE_DECISIONS.md §11；"
                        "K-7 取自 F1B_RENDERER_DECISIONS.md §10；"
                        "Y-4/Y-6 取自 F1B_DSH_ADAPTER_DECISIONS.md §10。"
                        "Lifecycle 文档另有同名 X-1…X-6，所指不同，未混用。"),
        "status_definition": {
            "DESIGN_RESOLVED": "架构责任与契约已裁定，可实施",
            "IMPLEMENTATION_DEPENDENCY": "架构已定，具体实现/实测必须在 F2（不等于已实现）",
            "BLOCKED_BY_MISSING_EVIDENCE": "现有证据不足以作架构选择",
        },
        "resolutions": resolutions,
        "reverse_dispositions": rev_out,
        "counterexample_clarification": {**D2.COUNTEREXAMPLE_CLARIFICATION, "actual_counts": clar},
        "stats": {
            "total": len(resolutions),
            "by_status": {},
            "canonical_amendments": 0,
            "f2_required_count": sum(1 for r in resolutions if r.get("f2_required")),
        },
    }
    from collections import Counter
    conflicts_doc["stats"]["by_status"] = dict(sorted(
        Counter(r["resolution_status"] for r in resolutions).items()))

    # —— F2 门禁
    gates = []
    for r in resolutions:
        for i, g in enumerate(r["verification_gate"], 1):
            gates.append({
                "gate_id": f"{r['conflict_id']}-G{i}",
                "conflict_id": r["conflict_id"],
                "owner": list((r["unique_owner"] or {}).values())[0] if r["unique_owner"] else None,
                "criterion": g,
                "stage": ("F1" if r["resolution_status"] == "DESIGN_RESOLVED" else "F2"),
                "blocking": True,
            })
    probes = []
    y6 = next(r for r in resolutions if r["conflict_id"] == "Y-6")
    for i, dep in enumerate(y6["implementation_dependencies"], 1):
        probes.append({
            "probe_id": f"Y6-P{i}",
            "target": dep,
            "owner": "DSH-Adapter",
            "pass_criterion": "接口经实测证实可用，且证据记录到 F2 探测报告",
            "fail_fallback": "走全自建路径（自有 checkpoint + 自查审批），不得停工",
            "no_go_if": "探测失败后仍依赖该接口 → 禁止上线",
        })

    gates_doc = {
        "artifact": "F1C_D2_F2_GATES",
        "schema_version": 1,
        "generated_at": conflicts_doc["generated_at"],
        "generated_by": "tools/fusion/f1c_d2_build.py",
        "principle": ("每条门禁必须有唯一 owner、可通过的判据、失败后的替代路径。"
                      "F1 阶段门禁不得以「设计上已经支持」代替实测。"),
        "gates": gates,
        "y6_probes": probes,
        "hard_rules": [
            "IMPLEMENTATION_DEPENDENCY 不得被写成「已实现」",
            "BLOCKED_BY_MISSING_EVIDENCE 不得被标为已解决",
            "未通过门禁的实现不得上线",
            "F1 不创建正式 Skill，skills/sourcelore/ 保持仅契约状态",
        ],
        "stats": {"gates": len(gates), "f1_stage": sum(1 for g in gates if g["stage"] == "F1"),
                  "f2_stage": sum(1 for g in gates if g["stage"] == "F2"),
                  "probes": len(probes)},
    }

    OUT_C.write_text(json.dumps(conflicts_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_G.write_text(json.dumps(gates_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # —— 更新裁决登记（只追加，不改旧条目）
    reg = json.loads(REG.read_text(encoding="utf-8"))
    reg.setdefault("d2_cross_module_resolutions", {})
    reg["d2_cross_module_resolutions"] = {
        "batch": D2.BATCH,
        "artifact": "F1C_D2_CONFLICT_RESOLUTIONS.json",
        "items": {r["conflict_id"]: {"status": r["resolution_status"],
                                     "owner": r["unique_owner"],
                                     "canonicals": r["affected_canonical_ids"]}
                  for r in resolutions},
        "reverse_dispositions_reviewed": [rc["identity_key"] for rc in rev_out],
        "counterexample_clarification": clar,
        "amendments_made": 0,
        "note": "本批只补架构裁决与说明，未修改任何 canonical 字段（0 条 amendment）。",
    }
    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"conflicts: {len(resolutions)}  status={conflicts_doc['stats']['by_status']}")
    print(f"gates: {len(gates)} (F1 {gates_doc['stats']['f1_stage']} / F2 {gates_doc['stats']['f2_stage']})  probes={len(probes)}")
    print(f"counterexample: {len(ce_ids)} 绑定身份 / {len(edges)} 关联边 / {len(rj_ids)} 无绑定拒绝身份")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
