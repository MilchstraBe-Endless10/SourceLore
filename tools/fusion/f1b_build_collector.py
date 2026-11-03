#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Collector 模块：把 Collector 的 canonical 能力增量并入交叉表草稿。

增量原则：
  - 只追加，不改写 Facts 已有的 SL-CAP-0001..0010；
  - 只新增 SL-CAP-0011 起的编号；
  - 原始索引只读，不重算、不覆盖。

统计语义（本批纠正）：
  mapped        = 已归属某个 canonical_id 的原始身份
  routed_pending= 已裁决去向但仍待该模块接手（不等于 mapped）
  unreviewed    = 既未 mapped 也未 routed
  三者互斥，和 = 原始身份全集
"""
import json, sys, hashlib, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "fusion"
RAW = OUT_DIR / "RAW_CAPABILITY_INDEX.json"
DRAFT = OUT_DIR / "CAPABILITY_CROSSWALK.draft.json"
PROG = OUT_DIR / "CROSSWALK_PROGRESS.json"
TZ = timezone(timedelta(hours=8))

MODULE = "Collector"
FIRST_ID = "SL-CAP-0011"

sys.path.insert(0, str(ROOT / "tools" / "fusion"))
from f1b_collector_def import CANON, DEFERRED_TO_OTHER_MODULE, PROMOTED_FROM_FACTS
import f1b_stats

SOURCES = ["UPSTREAM-01", "UPSTREAM-02", "UPSTREAM-03",
           "UPSTREAM-04", "UPSTREAM-05", "UPSTREAM-06"]


def main() -> int:
    errors = []
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    items = raw["items"]
    by_key = {(i["upstream_id"], i["original_capability_id"]): i for i in items}
    if len(by_key) != len(items):
        errors.append("原始索引存在重复身份键")
    if len(items) != 143:
        errors.append(f"原始索引项数 {len(items)} != 143")
    raw_sha = hashlib.sha256(RAW.read_bytes()).hexdigest()

    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    if draft["source_index_sha256"] != raw_sha:
        errors.append("草稿记录的原始索引哈希与现值不符")

    # ── 既有归属（Facts 批次产出，只读） ───────────────────────────────
    # 幂等：先剔除本批上一次运行残留的 Collector 条目与分流，再从干净基线上重建
    COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}
    existing_canon = [c for c in draft["canonical_capabilities"]
                      if c["canonical_id"] not in COLLECTOR_IDS
                      and c.get("owner_module") != MODULE]
    # 注意：分流记录的 owner_module 是「目标模块」而非本模块，不能据此判断归属；
    # 只按本批 DEFERRED 定义的五个身份键剔除，Facts 原有的其余分流一概保留
    _own_keys = {(u, o) for (u, o) in DEFERRED_TO_OTHER_MODULE}
    # 晋升判定必须在本批剥离之前取材：记录一被剥离，就无法再区分
    # 「本批接手的」与「从来不曾分流的」，晋升记录会永久丢失
    _promo_source = list(draft["cross_module_redirections"])
    draft["cross_module_redirections"] = [
        r for r in draft["cross_module_redirections"]
        if (r["upstream_id"], r["original_capability_id"]) not in _own_keys
    ]
    # 本批上一次运行写入的晋升记录同样剔除，避免重复计入
    _prev_promotions = [
        r for r in draft.get("routed_promotions", [])
        if r.get("to_canonical_id") not in COLLECTOR_IDS
    ]
    existing_ids = [c["canonical_id"] for c in existing_canon]
    owner_of = {}
    for c in existing_canon:
        for r in c["upstream_refs"]:
            owner_of[(r["upstream_id"], r["original_capability_id"])] = c["canonical_id"]
    existing_routed = {(r["upstream_id"], r["original_capability_id"]): r
                       for r in draft["cross_module_redirections"]}
    if len(existing_routed) != len(draft["cross_module_redirections"]):
        errors.append("既有跨模块去向存在重复身份键")

    # ── ID 连续性：新编号必须从既有最大号 +1 起 ────────────────────────
    max_existing = max(int(c.split("-")[-1]) for c in existing_ids)
    expect_start = max_existing + 1
    got_start = int(FIRST_ID.split("-")[-1])
    if got_start != expect_start:
        errors.append(f"新编号起点 {got_start} 应为 {expect_start}")

    new_ids = [c["id"] for c in CANON]
    if new_ids != [f"SL-CAP-{n:04d}" for n in range(expect_start, expect_start + len(new_ids))]:
        errors.append("新增 canonical_id 不连续或未从起点递增")
    clash = set(new_ids) & set(existing_ids)
    if clash:
        errors.append(f"新增编号与既有编号冲突：{sorted(clash)}")

    # ── 归属唯一性 ────────────────────────────────────────────────────
    for c in CANON:
        if not c["refs"] and not c["notes"]:
            errors.append(f"{c['id']} 无 upstream_refs 且未说明独立设计理由")
        for uid, oid, verdict in c["refs"]:
            key = (uid, oid)
            if key not in by_key:
                errors.append(f"{c['id']} 引用不存在的原始身份 {uid}::{oid}")
                continue
            if key in owner_of:
                errors.append(f"原始身份 {uid}::{oid} 被重复归属：{owner_of[key]} 与 {c['id']}")
            if key in existing_routed and existing_routed[key]["owner_module"] != MODULE:
                errors.append(
                    f"原始身份 {uid}::{oid} 已被分流到 {existing_routed[key]['owner_module']}，"
                    f"不能由 Collector 承接")
            if key in DEFERRED_TO_OTHER_MODULE:
                errors.append(f"原始身份 {uid}::{oid} 既归入 Collector 又分流到其他模块")
            if verdict not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                errors.append(f"{cid_txt(c)}::{uid}::{oid} 非法裁决 {verdict}")
            owner_of[key] = c["id"]

    for key in DEFERRED_TO_OTHER_MODULE:
        if key not in by_key:
            errors.append(f"跨模块去向引用不存在的原始身份 {key[0]}::{key[1]}")
        if key in owner_of and owner_of[key] in new_ids:
            errors.append(f"原始身份 {key[0]}::{key[1]} 既归入 Collector 又分流")
        mod, _ = DEFERRED_TO_OTHER_MODULE[key]
        if mod == MODULE:
            errors.append(f"跨模块去向指向本模块自身：{key}")
        if mod not in {"Facts", "Evidence-Claims", "Product", "Research",
                       "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}:
            errors.append(f"跨模块去向模块名非法：{mod}")

    # ── 构建 Collector canonical 条目 ──────────────────────────────────
    collector_out = []
    for c in CANON:
        up_refs = []
        for uid, oid, verdict in c["refs"]:
            it = by_key[(uid, oid)]
            up_refs.append({
                "upstream_id": uid,
                "original_capability_id": oid,
                "identity_key": it["identity_key"],
                "upstream_capability": it["capability"],
                "upstream_where": it["where"],
                "upstream_disposition": it["disposition"],
                "verdict": verdict,
                "evidence": it["evidence"],
                "license": it["license"],
            })
        perms = []
        for r in up_refs:
            lp = dict(r["license"])
            lp["upstream_id"] = r["upstream_id"]
            perms.append(lp)
        no_copy = [p for p in perms if not p.get("copy_permitted")]
        if not perms:
            lic = {"per_upstream": [], "copy_permitted": True,
                   "constraint": "无上游来源，本条为独立架构设计，不涉及第三方著作权"}
        elif no_copy:
            lic = {"per_upstream": perms, "copy_permitted": False,
                   "constraint": "任一来源不允许复制，实现必须独立完成；仅可取非著作权的一般思想"}
        else:
            lic = {"per_upstream": perms, "copy_permitted": True,
                   "constraint": "按各来源许可逐项履行署名/许可链接/修改声明/notice 义务"}
        collector_out.append({
            "canonical_id": c["id"],
            "name": c["name"],
            "description": c["description"],
            "owner_module": MODULE,
            "upstream_refs": up_refs,
            "disposition": c["disposition"],
            "license_permission": lic,
            "dependencies": c["depends_on_modules"],
            "overlaps": c["overlaps"],
            "v1_scope": c["v1_scope"],
            "input_boundary": c["inputs"],
            "output_boundary": c["outputs"],
            "evidence": {
                "raw_index_sha256": raw_sha,
                "ref_count": len(up_refs),
                "sources": sorted({r["upstream_id"] for r in up_refs}),
            },
            "unresolved": c["unresolved"],
            "merge_note": c["notes"],
        })

    # ── 跨模块去向（增量） ─────────────────────────────────────────────
    promoted_keys = {(u, o) for c in CANON for (u, o, _v) in c["refs"]}
    kept_routed = [r for r in draft["cross_module_redirections"]
                   if (r["upstream_id"], r["original_capability_id"]) not in promoted_keys]
    # 晋升记录由定义文件声明，不从草稿反推。原因：草稿合并后原始分流记录已被本批消费，
    # 而原始索引不携带分流信息 —— 从运行时状态反推会在第二次运行时凭空丢失证据。
    promotions = []
    for (uid, oid), (cid, why) in sorted(PROMOTED_FROM_FACTS.items()):
        k = (uid, oid)
        # 声明必须与事实一致：该身份确实由 Collector 的这条 canonical 持有
        if k not in promoted_keys:
            errors.append(f"晋升声明与归属不符：{uid}::{oid} 并未被 Collector 任何 canonical 引用")
            continue
        if owner_of.get(k) != cid:
            errors.append(f"晋升声明的承接方不符：{uid}::{oid} 声明为 {cid}，实际为 {owner_of.get(k)}")
            continue
        # 真实从分流迁移而来时，旧分流记录必须存在于本批运行前的快照里
        was_routed = any(
            (r["upstream_id"], r["original_capability_id"]) == k for r in _promo_source
        )
        promotions.append({
            "upstream_id": uid,
            "original_capability_id": oid,
            "from": "cross_module_redirections" if was_routed else "def_declared",
            "to_canonical_id": cid,
            "promoted_in_batch": "F1-B/Collector",
            "reason": why,
        })

    routed_out = []
    for (uid, oid), (mod, why) in sorted(DEFERRED_TO_OTHER_MODULE.items()):
        it = by_key[(uid, oid)]
        routed_out.append({
            "upstream_id": uid, "original_capability_id": oid,
            "identity_key": it["identity_key"],
            "upstream_capability": it["capability"],
            "owner_module": mod,
            "reason": why,
            "status": "DEFERRED_TO_MODULE",
        })

    # ── 合并进草稿（既有条目原样保留顺序） ─────────────────────────────
    all_canon = existing_canon + collector_out
    all_routed = kept_routed + routed_out

    mapped = {(r["upstream_id"], r["original_capability_id"])
              for c in all_canon for r in c["upstream_refs"]}
    routed = {(r["upstream_id"], r["original_capability_id"]) for r in all_routed}
    unreviewed = set(by_key) - mapped - routed

    if mapped & routed:
        errors.append(f"分流与已映射重叠：{sorted(mapped & routed)}")
    if len(mapped) + len(routed) + len(unreviewed) != len(by_key):
        errors.append("三态计数之和不等于原始身份总数")
    unknown = (mapped | routed | unreviewed) - set(by_key)
    if unknown:
        errors.append(f"统计覆盖了不存在的身份：{sorted(unknown)}")

    all_ids = [c["canonical_id"] for c in all_canon]
    if len(set(all_ids)) != len(all_ids):
        errors.append("canonical_id 存在重复")
    if sorted(all_ids) != [f"SL-CAP-{n:04d}" for n in range(1, len(all_ids) + 1)]:
        errors.append("canonical_id 全集非从 0001 起连续")
    for c in all_canon:
        if c["owner_module"] not in {"Collector", "Facts", "Evidence-Claims", "Product",
                                     "Research", "Lifecycle", "Security", "Renderer",
                                     "Storage", "DSH-Adapter"}:
            errors.append(f"{c['canonical_id']} owner_module 非法：{c['owner_module']}")

    col_mapped = {(r["upstream_id"], r["original_capability_id"])
                  for c in collector_out for r in c["upstream_refs"]}

    draft["generated_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    draft["generator"] = "tools/fusion/f1b_build_collector.py（增量：Facts 由 f1b_build_facts.py 产出）"
    draft["modules_covered_this_batch"] = ["Facts", "Collector"]
    draft["canonical_capabilities"] = all_canon
    draft["cross_module_redirections"] = all_routed
    # 晋升记录必须落盘：这是「ROUTED -> MAPPED」的唯二证据之一，
    # 只算不写等同于没有发生过晋升
    draft["routed_promotions"] = _prev_promotions + promotions
    # 批次视图统一从草稿现算：任何单个构建器只持有自己那一批的数字，
    # 各自 append 会导致后跑的覆盖先跑的（实测 Facts 批次条目被 Collector 重建抹掉）。
    draft["batches"] = f1b_stats.batches_from_draft(draft)
    _b_collector = next(b for b in draft["batches"] if b["module"] == MODULE)
    # batch_summary 指向最近完成的批次（同一对象，不复制），保持向后兼容。
    draft["batch_summary"] = _b_collector
    # 累计视图：与 f1b_build_facts.py 同一实现，全部从草稿真实身份状态现算。
    draft["global_state_counts"] = f1b_stats.global_state_counts(draft, raw)
    draft["module_rollup"] = f1b_stats.module_rollup(draft)
    draft.pop("state_counts", None)  # 旧口径名，已由 global_state_counts 取代
    draft["invariants_asserted"] = list(dict.fromkeys(draft["invariants_asserted"] + [
        "ROUTED 不等于 MAPPED：分流只表示去向已裁决，能力尚未被该模块真正承接",
        "commit_sha / root_tree_sha / tree_query_ref 是三个独立字段，禁止互相替代",
        "Collector 只存在一个逻辑实现，传输适配可替换但不得出现第二套客户端",
    ]))

    # ── 进度回填（全部由草稿推导） ──────────────────────────────────────
    prog = json.loads(PROG.read_text(encoding="utf-8"))
    prog["phase"] = "F1-A_DONE / F1-B_IN_PROGRESS (Facts DONE, Collector DONE)"
    prog["module_progress"][MODULE] = {
        "canonical_count": len(collector_out),
        "canonical_ids": new_ids,
        "raw_mapped": len(col_mapped),
        "raw_redirected": len(routed_out),
        "status": "DONE",
    }
    prog["next_batch_start"] = {
        "module_hint": "Evidence-Claims",
        "note": "Facts 与 Collector 已完成；剩余八个模块待办。下一步从 Evidence-Claims 开始，"
                "承接 UPSTREAM-01 C03、UPSTREAM-03 C03、UPSTREAM-04 C07/C08/C10、"
                "UPSTREAM-05 C05/C06、UPSTREAM-06 C05。",
    }
    prog["progress_computed_from"] = "docs/fusion/CAPABILITY_CROSSWALK.draft.json"
    prog["last_updated"] = datetime.now(TZ).isoformat(timespec="seconds")
    _g = draft["global_state_counts"]
    prog["totals"] = {
        "raw_total": _g["raw_total"],
        "mapped_count": _g["mapped_count"],
        "routed_pending_count": _g["routed_pending_count"],
        "unreviewed_count": _g["unreviewed_count"],
        "canonical_count": _g["canonical_count"],
        "sum_check": _g["sum_check"],
        "definitions": {
            "mapped_count": "已归属某个 canonical_id 的原始身份数",
            "routed_pending_count": "去向已裁决但尚未被目标模块承接，不计入 mapped",
            "unreviewed_count": "既未映射也未分流的原始身份数",
            "canonical_count": "canonical 能力条目总数（非原始数量）",
        },
    }
    for k in ("raw_assigned", "raw_pending", "canonical_total"):
        prog["totals"].pop(k, None)

    print(f"raw_total             = {len(by_key)}")
    print(f"collector canonical   = {len(collector_out)}  {new_ids}")
    print(f"collector raw mapped  = {len(col_mapped)}")
    print(f"collector redirected  = {len(routed_out)}")
    print(f"mapped_count          = {len(mapped)}")
    print(f"routed_pending_count  = {len(routed)}")
    print(f"unreviewed_count      = {len(unreviewed)}")
    print(f"canonical_count       = {len(all_canon)}")
    print(f"per_source_mapped     = {json.dumps({u: sum(1 for k in col_mapped if k[0]==u) for u in SOURCES})}")
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        print("RESULT: FAIL", file=sys.stderr)
        print("未写入任何文件。", file=sys.stderr)
        return 1
    # 同步 Facts 条目中关于 U02-C08 的旧说明：该身份已由本批 SL-CAP-0017 承接
    for c in draft["canonical_capabilities"]:
        if c["canonical_id"] == "SL-CAP-0007":
            c["unresolved"] = [
                "U02-C08（summarize_repo 三处 except 吞异常）判 REJECT。本条只借用它的诉求——"
                "缺失值必须给出 unavailable 原因——不引用该原始身份；U02-C08 已在 F1-B 第二批"
                "由 Collector 的 SL-CAP-0017「失败即异常与错误分类」正式承接（作为反面证据，verdict=REJECT），"
                "本条与之一条身份不重复计算。"
            ]

    DRAFT.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROG.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RESULT: OK")
    return 0


def cid_txt(c):
    return c.get("id", "?")


if __name__ == "__main__":
    sys.exit(main())
