#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-B 裁决应用层：从 F1-B 基线 + 裁决数据，确定性生成 Crosswalk。

设计要点（用户第 6 节）：
- **从基线重建**：每次运行都从 `docs/fusion/F1B_FROZEN_BASELINE.json`（F1-B 收官快照）
  重新派生 Crosswalk，再叠加 F1-C 已批准的裁决。不是「在当前草稿上打补丁」。
- 因此**撤销或修改一项裁决后重跑，不会遗留历史路由**——残留无从产生。
- 幂等：同一输入跑两次，输出逐字节相同（generated_at 用基线时间戳 + 固定值）。

用法：
    python3 tools/fusion/f1c_apply_routed.py            # 应用
    python3 tools/fusion/f1c_apply_routed.py --dry-run  # 只报告差异
"""
import json, sys, copy, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
BASELINE = F / "F1B_FROZEN_BASELINE.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
RAW = F / "RAW_CAPABILITY_INDEX.json"
RECON = F / "F1C_B_ROUTED_RECONCILIATION.json"

sys.path.insert(0, str(Path(__file__).parent))
import f1c_routed_decisions as DEC
try:
    import f1c_c1_decisions as DEC2
except ImportError:
    DEC2 = None
try:
    import f1c_c2_decisions as DEC3
except ImportError:
    DEC3 = None
try:
    import f1c_c3_decisions as DEC4
except ImportError:
    DEC4 = None
import f1c_terminal_model as TM

BATCH = "F1-C-B"


def load():
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    return base, raw


def next_id(canon):
    n = max(int(c["canonical_id"].split("-")[-1]) for c in canon)
    return f"SL-CAP-{n+1:04d}", n + 1


def ref_from_raw(it, verdict):
    lic = it.get("license") or {}
    return {
        "upstream_id": it["upstream_id"],
        "original_capability_id": it["original_capability_id"],
        "identity_key": it["identity_key"],
        "upstream_capability": it["capability"],
        "upstream_where": it["where"],
        "upstream_disposition": it["disposition"],
        "verdict": verdict,
        "evidence": it["evidence"],
        "license": {
            "spdx": lic.get("spdx"),
            "copy_permitted": lic.get("copy_permitted"),
            "attribution_required": lic.get("attribution_required"),
            "license_link_required": lic.get("license_link_required"),
            "modification_notice_required": lic.get("modification_notice_required"),
        },
    }


def apply(base, raw, dry):
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    d = copy.deepcopy(base)
    canon = d["canonical_capabilities"]
    routed = d["cross_module_redirections"]
    routed_keys = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
    mapped_keys = {(r["upstream_id"], r["original_capability_id"])
                   for c in canon for r in c["upstream_refs"]}

    changes = []
    created = []

    for tested in DEC.DECISIONS:
        k = tuple(tested["identity"])
        if k not in routed_keys:
            raise SystemExit(f"ERROR: {k} 不在基线 ROUTED 中，裁决无法应用")
        if k in mapped_keys:
            raise SystemExit(f"ERROR: {k} 已映射，重复应用会二次映射")
        it = by[k]
        direction = tested["direction"]

        if direction == "ADOPT_EXISTING":
            target = tested["target_canonical"]
            c = next((x for x in canon if x["canonical_id"] == target), None)
            if c is None:
                raise SystemExit(f"ERROR: 目标 {target} 不存在")
            if c["owner_module"] != tested["current_owner"]:
                raise SystemExit(f"ERROR: {target} owner={c['owner_module']}，裁决写 {tested['current_owner']}")
            # 幂等：已在 refs 中则跳过
            if any((r["upstream_id"], r["original_capability_id"]) == k for r in c["upstream_refs"]):
                continue
            c["upstream_refs"].append(ref_from_raw(it, tested["verdict"]))
            lic = it.get("license") or {}
            c["license_permission"]["per_upstream"].append({
                "spdx": lic.get("spdx"),
                "copy_permitted": lic.get("copy_permitted"),
                "attribution_required": lic.get("attribution_required"),
                "license_link_required": lic.get("license_link_required"),
                "modification_notice_required": lic.get("modification_notice_required"),
                "upstream_id": k[0],
            })
            d["routed_promotions"].append({
                "upstream_id": k[0], "original_capability_id": k[1],
                "from": "cross_module_redirections",
                "to_canonical_id": target,
                "promoted_in_batch": BATCH,
                "reason": tested["reason"][:400],
            })
            routed[:] = [r for r in routed
                         if (r["upstream_id"], r["original_capability_id"]) != k]
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "ADOPT_EXISTING",
                            "target": target, "owner": c["owner_module"],
                            "license_note": tested.get("license_note")})
            if tested.get("canonical_amendment"):
                amend_canonical(canon, tested["canonical_amendment"], changes)

        elif direction == "NEW_CANONICAL":
            defn = tested["new_canonical_def"]
            want, num = next_id(canon)
            if defn["id"] != want:
                pass  # 允许定义里写的 ID 落后，但必须连续；下面强制校验
            cid = next_id(canon)[0]
            if defn["id"] != cid:
                raise SystemExit(f"ERROR: 定义的 {defn['id']} 与真实下一个 ID {cid} 不符，"
                                 f"新 ID 只能从真实最大 ID 后分配")
            lic = it.get("license") or {}
            newc = {
                "canonical_id": cid,
                "name": defn["name"],
                "description": defn["description"],
                "owner_module": defn["owner_module"],
                "upstream_refs": [ref_from_raw(it, tested["verdict"])],
                "disposition": "REIMPLEMENT",
                "license_permission": {
                    "per_upstream": [{
                        "spdx": lic.get("spdx"),
                        "copy_permitted": lic.get("copy_permitted"),
                        "attribution_required": lic.get("attribution_required"),
                        "license_link_required": lic.get("license_link_required"),
                        "modification_notice_required": lic.get("modification_notice_required"),
                        "upstream_id": k[0],
                    }],
                    "copy_permitted": bool(lic.get("copy_permitted")),
                    "constraint": "UPSTREAM-06 无复制许可：只借抽象结构，不复制模板/脚本/格式",
                },
                "dependencies": defn["dependencies"],
                "overlaps": [],
                "v1_scope": defn["v1_scope"],
                "input_boundary": defn["input_boundary"],
                "output_boundary": defn["output_boundary"],
                "evidence": {"raw_index_sha256": d["source_index_sha256"],
                             "ref_count": 1, "sources": [k[0]]},
                "unresolved": defn["unresolved"],
                "merge_note": defn["merge_note"],
                "created_in_batch": BATCH,
            }
            canon.append(newc)
            d["routed_promotions"].append({
                "upstream_id": k[0], "original_capability_id": k[1],
                "from": "cross_module_redirections",
                "to_canonical_id": cid,
                "promoted_in_batch": BATCH,
                "reason": tested["reason"][:400],
            })
            routed[:] = [r for r in routed
                         if (r["upstream_id"], r["original_capability_id"]) != k]
            created.append({"canonical_id": cid, "name": defn["name"],
                            "from_identity": f"{k[0]}::{k[1]}"})
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "NEW_CANONICAL",
                            "target": cid, "license_note": tested.get("license_note")})

        elif direction in ("DEFER_WITH_REASON", "REJECT_WITH_REASON"):
            # 保持 ROUTED 状态不变（不假称 MAPPED），只在 reconciliation 里记录终态
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": direction,
                            "target": None, "owner": tested["current_owner"],
                            "note": "保持 ROUTED 状态；终态处置待 terminal_disposition 迁移"})
        else:
            raise SystemExit(f"ERROR: 未知方向 {direction}")

    return d, changes, created


def amend_canonical(canon, amend, changes):
    c = next((x for x in canon if x["canonical_id"] == amend["target"]), None)
    if c is None:
        raise SystemExit(f"ERROR: 修订目标 {amend['target']} 不存在")
    # 幂等：已含则不重复追加
    if amend["append_note"] in (c.get("f1c_amendments") or []):
        return
    c.setdefault("f1c_amendments", []).append(amend["append_note"])
    changes.append({"identity": "-", "action": "AMEND_CANONICAL",
                    "target": amend["target"], "note": "追加 F1-C-B 修订" })


def apply_c1(d, raw, dry):
    """F1-C-C 阶段 1：在三项 DEFER 身份上叠加本批裁决。

    前置约束：这三项必须仍在 ROUTED 中且未被任何 canonical 承接——
    否则说明 F1-C-B 的 DEFER 已被别处改动，必须停止。
    """
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = d["canonical_capabilities"]
    routed = d["cross_module_redirections"]
    routed_keys = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
    mapped_keys = {(r["upstream_id"], r["original_capability_id"])
                   for c in canon for r in c["upstream_refs"]}
    changes, created = [], []

    for tested in DEC2.DECISIONS:
        k = tuple(tested["identity"])
        if k not in routed_keys:
            raise SystemExit(f"ERROR: {k} 不在当前 ROUTED 中，无法应用本批裁决")
        if k in mapped_keys:
            raise SystemExit(f"ERROR: {k} 已被映射，重复应用会二次映射")
        it = by[k]
        direction = tested["direction"]

        if direction == "ADOPT_EXISTING":
            target = tested["target_canonical"]
            c = next((x for x in canon if x["canonical_id"] == target), None)
            if c is None:
                raise SystemExit(f"ERROR: 目标 {target} 不存在")
            if c["owner_module"] != tested["final_owner"]:
                raise SystemExit(f"ERROR: {target} owner={c['owner_module']}，"
                                 f"裁决写 {tested['final_owner']}")
            if not any((r["upstream_id"], r["original_capability_id"]) == k
                       for r in c["upstream_refs"]):
                c["upstream_refs"].append(ref_from_raw(it, tested["verdict"]))
                lic = it.get("license") or {}
                c["license_permission"]["per_upstream"].append({
                    "spdx": lic.get("spdx"),
                    "copy_permitted": lic.get("copy_permitted"),
                    "attribution_required": lic.get("attribution_required"),
                    "license_link_required": lic.get("license_link_required"),
                    "modification_notice_required": lic.get("modification_notice_required"),
                    "upstream_id": k[0],
                })
            d["routed_promotions"].append({
                "upstream_id": k[0], "original_capability_id": k[1],
                "from": "cross_module_redirections",
                "to_canonical_id": target,
                "promoted_in_batch": DEC2.BATCH,
                "reason": tested["reason"][:400],
            })
            routed[:] = [r for r in routed
                         if (r["upstream_id"], r["original_capability_id"]) != k]
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "ADOPT_EXISTING",
                            "target": target, "owner": c["owner_module"],
                            "previous_owner": tested["previous_owner"],
                            "owner_changed": tested["previous_owner"] != tested["final_owner"],
                            "license_note": tested["license_note"]})
            amend_canonical(canon, tested["amendment"], changes)

        elif direction == "NEW_CANONICAL":
            defn = tested["new_canonical_def"]
            cid = next_id(canon)[0]
            lic = it.get("license") or {}
            newc = {
                "canonical_id": cid,
                "name": defn["name"],
                "description": defn["description"],
                "owner_module": defn["owner_module"],
                "upstream_refs": [ref_from_raw(it, tested["verdict"])],
                "disposition": "ADAPT",
                "license_permission": {
                    "per_upstream": [{
                        "spdx": lic.get("spdx"),
                        "copy_permitted": lic.get("copy_permitted"),
                        "attribution_required": lic.get("attribution_required"),
                        "license_link_required": lic.get("license_link_required"),
                        "modification_notice_required": lic.get("modification_notice_required"),
                        "upstream_id": k[0],
                    }],
                    "copy_permitted": bool(lic.get("copy_permitted")),
                    "constraint": "MIT；只借 gold+确定性指标的形态，未复制其 judge 实现与评测数据",
                },
                "dependencies": defn["dependencies"],
                "overlaps": [],
                "v1_scope": defn["v1_scope"],
                "input_boundary": defn["input_boundary"],
                "output_boundary": defn["output_boundary"],
                "evidence": {"raw_index_sha256": d["source_index_sha256"],
                             "ref_count": 1, "sources": [k[0]]},
                "unresolved": defn["unresolved"],
                "merge_note": defn["merge_note"],
                "created_in_batch": DEC2.BATCH,
            }
            canon.append(newc)
            d["routed_promotions"].append({
                "upstream_id": k[0], "original_capability_id": k[1],
                "from": "cross_module_redirections",
                "to_canonical_id": cid,
                "promoted_in_batch": DEC2.BATCH,
                "reason": tested["reason"][:400],
            })
            routed[:] = [r for r in routed
                         if (r["upstream_id"], r["original_capability_id"]) != k]
            created.append({"canonical_id": cid, "name": defn["name"],
                            "from_identity": f"{k[0]}::{k[1]}",
                            "owner": defn["owner_module"]})
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "NEW_CANONICAL",
                            "target": cid, "owner": defn["owner_module"],
                            "previous_owner": tested["previous_owner"],
                            "owner_changed": tested["previous_owner"] != tested["final_owner"],
                            "license_note": tested["license_note"]})
        else:
            raise SystemExit(f"ERROR: 本批不接受方向 {direction}（3 项 DEFER 必须给出终裁）")

    return d, changes, created


def apply_c2(d, raw, dry):
    """F1-C-C2：U05 剩余 UNREVIEWED 终裁。

    两类方向：
      ADOPT_EXISTING      → 写入 refs + amendment + 晋升记录，离开 UNREVIEWED
      REJECT_WITH_REASON  → **保持 UNREVIEWED**（三态模型无法表达 REJECT 终态），
                            终态只记在裁决数据与 reconciliation 里，等 F1-C-D 迁移。
    """
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = d["canonical_capabilities"]
    mapped_keys = {(r["upstream_id"], r["original_capability_id"])
                   for c in canon for r in c["upstream_refs"]}
    routed_keys = {(r["upstream_id"], r["original_capability_id"])
                   for r in d["cross_module_redirections"]}
    changes = []

    for tested in DEC3.DECISIONS:
        k = tuple(tested["identity"])
        if k in mapped_keys or k in routed_keys:
            raise SystemExit(f"ERROR: {k} 已映射或已分流，本批不应再处理")
        direction = tested["direction"]

        if direction == "ADOPT_EXISTING":
            target = tested["target_canonical"]
            c = next((x for x in canon if x["canonical_id"] == target), None)
            if c is None:
                raise SystemExit(f"ERROR: 目标 {target} 不存在")
            if c["owner_module"] != tested["final_owner"]:
                raise SystemExit(f"ERROR: {target} owner={c['owner_module']}，"
                                 f"裁决写 {tested['final_owner']}")
            if not any((r["upstream_id"], r["original_capability_id"]) == k
                       for r in c["upstream_refs"]):
                c["upstream_refs"].append(ref_from_raw(by[k], tested["verdict"]))
                lic = by[k].get("license") or {}
                c["license_permission"]["per_upstream"].append({
                    "spdx": lic.get("spdx"),
                    "copy_permitted": lic.get("copy_permitted"),
                    "attribution_required": lic.get("attribution_required"),
                    "license_link_required": lic.get("license_link_required"),
                    "modification_notice_required": lic.get("modification_notice_required"),
                    "upstream_id": k[0],
                })
            d["routed_promotions"].append({
                "upstream_id": k[0], "original_capability_id": k[1],
                "from": "unreviewed_adopted",
                "to_canonical_id": target,
                "promoted_in_batch": DEC3.BATCH,
                "reason": tested["reason"][:400],
            })
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "ADOPT_EXISTING",
                            "target": target, "owner": c["owner_module"],
                            "license_note": tested["license_note"]})
            if tested.get("amendment"):
                amend_canonical(canon, tested["amendment"], changes)

        elif direction == "REJECT_WITH_REASON":
            # 不改变三态：保持 UNREVIEWED，仅记录终态处置
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "REJECT_WITH_REASON",
                            "target": None, "owner": None,
                            "terminal_disposition": tested["terminal_disposition"],
                            "note": "保持 UNREVIEWED；终态处置待 F1-C-D 的 terminal_disposition 迁移",
                            "license_note": tested["license_note"]})
        else:
            raise SystemExit(f"ERROR: 未知方向 {direction}")

    return d, changes


def apply_c3(d, raw, dry):
    """F1-C-C3：剩余 10 项终裁。

    ADOPT_EXISTING → 写入 refs + amendment + 晋升记录，离开 UNREVIEWED
    REJECT_WITH_REASON → **保持 UNREVIEWED**，终态只记在裁决数据与 reconciliation
    """
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = d["canonical_capabilities"]
    mapped_keys = {(r["upstream_id"], r["original_capability_id"])
                   for c in canon for r in c["upstream_refs"]}
    routed_keys = {(r["upstream_id"], r["original_capability_id"])
                   for r in d["cross_module_redirections"]}
    changes = []

    for tested in DEC4.DECISIONS:
        k = tuple(tested["identity"])
        if k in mapped_keys or k in routed_keys:
            raise SystemExit(f"ERROR: {k} 已映射或已分流，本批不应再处理")
        direction = tested["direction"]

        if direction == "ADOPT_EXISTING":
            target = tested["target_canonical"]
            c = next((x for x in canon if x["canonical_id"] == target), None)
            if c is None:
                raise SystemExit(f"ERROR: 目标 {target} 不存在")
            if c["owner_module"] != tested["final_owner"]:
                raise SystemExit(f"ERROR: {target} owner={c['owner_module']}，"
                                 f"裁决写 {tested['final_owner']}")
            if not any((r["upstream_id"], r["original_capability_id"]) == k
                       for r in c["upstream_refs"]):
                c["upstream_refs"].append(ref_from_raw(by[k], tested["verdict"]))
                lic = by[k].get("license") or {}
                c["license_permission"]["per_upstream"].append({
                    "spdx": lic.get("spdx"),
                    "copy_permitted": lic.get("copy_permitted"),
                    "attribution_required": lic.get("attribution_required"),
                    "license_link_required": lic.get("license_link_required"),
                    "modification_notice_required": lic.get("modification_notice_required"),
                    "upstream_id": k[0],
                })
            d["routed_promotions"].append({
                "upstream_id": k[0], "original_capability_id": k[1],
                "from": "unreviewed_adopted",
                "to_canonical_id": target,
                "promoted_in_batch": DEC4.BATCH,
                "reason": tested["reason"][:400],
            })
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "ADOPT_EXISTING",
                            "target": target, "owner": c["owner_module"],
                            "license_note": tested["license_note"]})
            if tested.get("amendment"):
                amend_canonical(canon, tested["amendment"], changes)

        elif direction == "REJECT_WITH_REASON":
            changes.append({"identity": f"{k[0]}::{k[1]}", "action": "REJECT_WITH_REASON",
                            "target": None, "owner": None,
                            "terminal_disposition": tested["terminal_disposition"],
                            "note": "保持 UNREVIEWED；终态处置待 F1-C-D 的 terminal_disposition 迁移",
                            "license_note": tested["license_note"]})
        else:
            raise SystemExit(f"ERROR: 未知方向 {direction}")

    return d, changes


def recompute(d, base):
    canon = d["canonical_capabilities"]
    mapped = {(r["upstream_id"], r["original_capability_id"])
              for c in canon for r in c["upstream_refs"]}
    routed = {(r["upstream_id"], r["original_capability_id"])
              for r in d["cross_module_redirections"]}
    g = d["global_state_counts"]
    d["global_state_counts"].update({
        "mapped_count": len(mapped),
        "routed_pending_count": len(routed),
        "unreviewed_count": g["raw_total"] - len(mapped) - len(routed),
        "canonical_count": len(canon),
    })
    d["global_state_counts"]["sum_check"] = (
        d["global_state_counts"]["mapped_count"]
        + d["global_state_counts"]["routed_pending_count"]
        + d["global_state_counts"]["unreviewed_count"])
    # routed_promotions 去重（幂等保险）
    seen, uniq = set(), []
    for p in d["routed_promotions"]:
        key = (p["upstream_id"], p["original_capability_id"], p["to_canonical_id"])
        if key in seen:
            continue
        seen.add(key); uniq.append(p)
    d["routed_promotions"] = uniq
    # batches 的 redirected 是「声明 − 已晋升」，重算
    import f1b_stats
    recalc = {x["module"]: x for x in f1b_stats.batches_from_draft(d)}
    for b in d["batches"]:
        r = recalc.get(b["module"])
        if r:
            b["raw_mapped_to_this_module"] = r["raw_mapped_to_this_module"]
            b["raw_redirected_to_other_modules"] = r["raw_redirected_to_other_modules"]
            b["canonical_ids"] = r["canonical_ids"]
    return d


def update_progress(d):
    """同步 CROSSWALK_PROGRESS.json。这是应用层的职责——否则验证器读到的进度会落后于草稿。"""
    PROG = F / "CROSSWALK_PROGRESS.json"
    p = json.loads(PROG.read_text(encoding="utf-8"))
    g = d["global_state_counts"]
    t = p["totals"]
    t["mapped_count"] = g["mapped_count"]
    t["routed_pending_count"] = g["routed_pending_count"]
    t["unreviewed_count"] = g["unreviewed_count"]
    t["canonical_count"] = g["canonical_count"]
    t["sum_check"] = g["sum_check"]
    p["phase"] = "F1-A_DONE / F1-B_ALL_BATCHES_DONE / F1-C_IN_PROGRESS"
    batches = {x["module"]: x for x in d["batches"]}
    if "f1c_batches" not in p:
        p["f1c_batches"] = {}
    p["f1c_batches"]["F1-C-B"] = "DONE"
    p["f1c_batches"]["F1-C-C1"] = "DONE"
    p["f1c_batches"]["F1-C-C2"] = "DONE"
    p["f1c_batches"]["F1-C-C3"] = "DONE"
    p["f1c_batches"]["F1-C"] = "IN_PROGRESS"
    p["next_batch_start"] = "F1-C-D"
    p["note"] = ("F1-C-B 清算 11 项 ROUTED；F1-C-C1 终裁 3 项 DEFER；"
                 "F1-C-C2 终裁 U05 剩余 10 项；F1-C-C3 终裁 U03/U04/U06 剩余 10 项"
                 "（8 承接已有 + 2 REJECT）。全部 143 项已有终裁；"
                 "剩 4 项 REJECT 待 F1-C-D 的 terminal_disposition 迁移。")
    PROG.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"updated  -> {PROG.name}")


def main() -> int:
    dry = "--dry-run" in sys.argv
    base, raw = load()
    d, changes, created = apply(base, raw, dry)
    c1_changes, c1_created = [], []
    if DEC2 is not None:
        d, c1_changes, c1_created = apply_c1(d, raw, dry)
        created = created + c1_created
    c2_changes = []
    if DEC3 is not None:
        d, c2_changes = apply_c2(d, raw, dry)
    c3_changes = []
    if DEC4 is not None:
        d, c3_changes = apply_c3(d, raw, dry)
    d = recompute(d, base)
    # 终态推导并入应用链：任何重跑都会重新生成，不会因下游步骤缺失而丢失。
    decided_reject = {}
    for mod in (DEC, DEC2, DEC3, DEC4):
        if mod is None:
            continue
        for dd in getattr(mod, "DECISIONS", []):
            if dd.get("direction") == "REJECT_WITH_REASON":
                decided_reject[tuple(dd["identity"])] = {
                    "terminal_disposition": dd.get("terminal_disposition",
                                                   "REJECTED_WITH_REASON"),
                    "reason": dd.get("reason"),
                    "batch": getattr(mod, "BATCH", None),
                }
    tdist, odist, rdist = TM.derive(d, raw, decided_reject)
    g = d["global_state_counts"]
    print(f"mapped={g['mapped_count']} routed={g['routed_pending_count']} "
          f"unreviewed={g['unreviewed_count']} sum={g['sum_check']} canonical={g['canonical_count']}")
    for label, ch in (("B", changes), ("C1", c1_changes), ("C2", c2_changes), ("C3", c3_changes)):
        for c in ch:
            print(f"  [F1-C-{label}] {c['action']:18s} {c['identity']:20s} "
                  f"-> {c.get('target') or '(保持)'}")
    for c in created:
        print(f"  * 新建 {c['canonical_id']}: {c['name']}")
    print(f"  terminal: {tdist}")
    print(f"  origin  : {odist}")
    print(f"  role    : {rdist}")

    recon = {
        "artifact": "F1C_B_ROUTED_RECONCILIATION",
        "schema_version": 1,
        "generated_by": "tools/fusion/f1c_apply_routed.py",
        "source_baseline": "docs/fusion/F1B_FROZEN_BASELINE.json",
        "decision_source": "tools/fusion/f1c_routed_decisions.py",
        "principle": ("每次运行都从 F1-B 基线重建再叠加裁决；不是打补丁，故撤销裁决不会遗留历史路由。"
                      "叠加顺序：F1-B 基线 → F1-C-B（8 项 ROUTED 清算）→ F1-C-C1（3 项 DEFER 终裁）"
                      "→ F1-C-C2（U05 剩余 10 项）→ F1-C-C3（U03/U04/U06 剩余 10 项）。"),
        "terminal_model_snapshot": {
            "terminal_disposition_counts": tdist,
            "canonical_origin_counts": odist,
            "adoption_role_counts": rdist,
        },
        "totals_after": {
            "mapped": g["mapped_count"], "routed": g["routed_pending_count"],
            "unreviewed": g["unreviewed_count"], "canonical": g["canonical_count"],
            "sum_check": g["sum_check"],
        },
        "changes": changes,
        "changes_c1": c1_changes,
        "changes_c2": c2_changes,
        "changes_c3": c3_changes,
        "created_canonicals": created,
        "errata": DEC.ERRATA,
    }
    RECON.write_text(json.dumps(recon, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not dry:
        DRAFT.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"written -> {DRAFT.name}")
        update_progress(d)
    else:
        print("(dry-run，未写盘)")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
