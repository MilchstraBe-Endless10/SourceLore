#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Facts 模块：从 143 项原始能力中确定性筛出 Facts 候选，
生成 CAPABILITY_CROSSWALK.draft.json（只写 Facts 部分）与回填映射进度。

不修改 RAW_CAPABILITY_INDEX.json。不做模糊匹配：候选 = 显式白名单。
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

MODULE = "Facts"

# ── canonical 定义（本模块） ──────────────────────────────────────────────
sys.path.insert(0, str(ROOT / "tools" / "fusion"))
sys.path.insert(0, "/tmp")
from f1b_facts_def import CANON, DEFERRED_TO_OTHER_MODULE
import f1b_stats

# ── 明确排除：属于 Facts 之外模块的候选（保留去向，不计入本模块） ──────────
# 未列出的原始能力 = 本轮未处理，仍为 UNMAPPED / PENDING

# 本构建器拥有的 canonical 编号（Facts 批次为 0001~0010）
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}

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

    # 1. 收集 refs，校验唯一性
    owner_of = {}
    ref_verdict = {}
    for c in CANON:
        if not c["refs"]:
            errors.append(f"{c['id']} 无 upstream_refs")
        for uid, oid, verdict in c["refs"]:
            key = (uid, oid)
            if key not in by_key:
                errors.append(f"{c['id']} 引用不存在的原始身份 {uid}::{oid}")
                continue
            if key in owner_of:
                errors.append(f"原始身份 {uid}::{oid} 被重复归属：{owner_of[key]} 与 {c['id']}")
            owner_of[key] = c["id"]
            ref_verdict[key] = verdict
    for key in DEFERRED_TO_OTHER_MODULE:
        if key not in by_key:
            errors.append(f"跨模块去向引用不存在的原始身份 {key[0]}::{key[1]}")
        if key in owner_of:
            errors.append(f"原始身份 {key[0]}::{key[1]} 既属 Facts 又归入其他模块")

    facts_keys = set(owner_of)
    other_keys = set(DEFERRED_TO_OTHER_MODULE)
    pending_keys = set(by_key) - facts_keys - other_keys

    # 2. 构建 canonical 条目
    canon_out = []
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
        # 处置与许可相互独立：处置取本模块裁决，许可逐源照抄
        perms = []
        for r in up_refs:
            lp = dict(r["license"])
            lp["upstream_id"] = r["upstream_id"]
            perms.append(lp)
        no_copy = [p for p in perms if not p.get("copy_permitted")]
        canon_out.append({
            "canonical_id": c["id"],
            "name": c["name"],
            "description": c["description"],
            "owner_module": MODULE,
            "upstream_refs": up_refs,
            "disposition": c["disposition"],
            "license_permission": {
                "per_upstream": perms,
                "copy_permitted": len(no_copy) == 0,
                "constraint": ("任一来源不允许复制，实现必须独立完成；仅可取非著作权的一般思想"
                               if no_copy else "按各来源许可逐项履行署名/许可链接/修改声明/notice 义务"),
            },
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

    # 3. 跨模块去向
    # 已被下游批次承接（晋升）的身份不再算「挂起分流」：留在 DEFERRED 里会让它
    # 同时出现在 routed 与 mapped 两处，状态就不再互斥。晋升关系只从草稿已有的
    # routed_promotions 读，本构建器不自己造数 —— 首次运行时草稿里还没有，即为空。
    _prev_doc = {}
    _prev_path = OUT_DIR / "CAPABILITY_CROSSWALK.draft.json"
    if _prev_path.exists():
        try:
            _prev_doc = json.loads(_prev_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            _prev_doc = {}
    promoted_elsewhere = {(p["upstream_id"], p["original_capability_id"])
                          for p in (_prev_doc.get("routed_promotions") or [])
                          if p.get("to_canonical_id") not in FACTS_IDS}
    # 本模块自己声明过的分流目标：outbound 计数只认这些，不用推断
    other_out = []
    for (uid, oid), (mod, why) in sorted(DEFERRED_TO_OTHER_MODULE.items()):
        if (uid, oid) in promoted_elsewhere:
            continue
        it = by_key[(uid, oid)]
        other_out.append({
            "upstream_id": uid, "original_capability_id": oid,
            "identity_key": it["identity_key"],
            "upstream_capability": it["capability"],
            "owner_module": mod,
            "reason": why,
            "status": "DEFERRED_TO_MODULE",
        })

    # 4. 校验
    ids = [c["canonical_id"] for c in canon_out]
    if len(set(ids)) != len(ids):
        errors.append("canonical_id 重复")
    for cid in ids:
        if not re.fullmatch(r"SL-CAP-\d{4}", cid):
            errors.append(f"canonical_id 形态异常: {cid}")
    if sorted(ids) != [f"SL-CAP-{n:04d}" for n in range(1, len(ids) + 1)]:
        errors.append("canonical_id 非从 0001 起连续")
    for c in canon_out:
        if c["owner_module"] != MODULE:
            errors.append(f"{c['canonical_id']} owner_module 非唯一 Facts")
        if c["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
            errors.append(f"{c['canonical_id']} 非法处置")
    if len(facts_keys) + len(other_keys) + len(pending_keys) != len(by_key):
        errors.append("分区计数不等于总数")

    # 5. 写草稿
    doc = {
        "artifact": "CAPABILITY_CROSSWALK",
        "schema_version": 1,
        "task": "M1-FUSION-GATE-F1 / F1-B",
        "status": "DRAFT — 未冻结，F1-D 全量验收前不得发布为 CAPABILITY_CROSSWALK.json",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generator": "tools/fusion/f1b_build_facts.py",
        "source_index": "docs/fusion/RAW_CAPABILITY_INDEX.json",
        "source_index_sha256": raw_sha,
        "id_policy": {
            "prefix": "SL-CAP-",
            "first_allocated": "SL-CAP-0001",
            "monotonic": True,
            "renumber_forbidden": True,
            "reclassification_requires_migration_record": True,
        },
        "disposition_semantics": {
            "REUSE": "形态与语义可直接沿用（不等于可复制代码，许可另计）",
            "ADAPT": "方向正确但存在明确缺陷或形态不兼容，需修改后采纳",
            "REIMPLEMENT": "目标正确但上游实现缺失或不可执行，须自行设计",
            "REJECT": "不采纳其实现或形态，仅保留经裁决的可取思想",
        },
        "modules_covered_this_batch": [MODULE],
        "canonical_capabilities": canon_out,
        "cross_module_redirections": other_out,
        # 分批统计契约：batch_summary 只承载本批次自身数字，作用域由 scope 字段声明。
        # 全局口径（143 总数、尚未初审数、三态计数）一律不写在这里，改由
        # global_state_counts 从真实身份状态现算，防止读者把全局数字误读成本批次数字。
        "batch_summary": {
            "scope": "batch",
            "batch": "F1-B/Facts",
            "module": MODULE,
            "raw_considered": len(facts_keys) + len(other_keys),
            "raw_mapped_to_this_module": len(facts_keys),
            "raw_redirected_to_other_modules": len(other_keys),
            "canonical_count": len(canon_out),
            "canonical_ids": ids,
            "per_source_consumed": {
                u: sum(1 for k in facts_keys if k[0] == u) for u in
                ["UPSTREAM-01", "UPSTREAM-02", "UPSTREAM-03", "UPSTREAM-04", "UPSTREAM-05", "UPSTREAM-06"]
            },
            # 语义：本模块承接的原始身份数 ÷ 本模块 canonical 数，是重复度不是压缩百分比。
            "dedup_ratio": round(len(facts_keys) / len(canon_out), 3) if canon_out else None,
            "dedup_ratio_definition": "raw_mapped_to_this_module / canonical_count",
        },
        "b3_placeholder": None,
        "invariants_asserted": [
            "每条原始身份最多归属一个 canonical_id",
            "每个 canonical 能力只有一个 owner_module",
            "处置（disposition）与许可（license_permission）分别记录，互不推导",
            "原始索引为不可变源快照，本轮未修改",
            "未处理的原始能力仍为 UNREVIEWED/PENDING，不视为已裁决",
            "batch_summary 只统计本批次；全台账口径见 global_state_counts",
        ],
    }
    # 写入延后到校验通过之后（失败时不得留下半成品草稿）

    # 5b. 分批视图与累计视图分离
    # batches[] 只装各批次的自身统计；batch_summary 保留为「最近一批」的别名，
    # 指向同一个批次作用域对象，避免两处数字漂移。
    del doc["b3_placeholder"]
    doc["batches"] = f1b_stats.batches_from_draft(doc)
    b_facts = next(b for b in doc["batches"] if b["module"] == MODULE)
    doc["batch_summary"] = b_facts
    # 累计视图：从草稿的真实身份状态现算，不引用任何传入的期望值。
    doc["global_state_counts"] = f1b_stats.global_state_counts(doc, raw)
    doc["module_rollup"] = f1b_stats.module_rollup(doc)

    # 6. 回填进度（从草稿推导，不信索引初值）
    prog = json.loads(PROG.read_text(encoding="utf-8"))
    prog["phase"] = "F1-A_DONE / F1-B_IN_PROGRESS (Facts DONE)"
    prog["module_progress"][MODULE] = {
        "canonical_count": len(canon_out),
        "raw_consumed": len(facts_keys),
        "raw_redirected": len(other_keys),
        "status": "DONE",
    }
    prog["next_batch_start"] = {
        "module_hint": "Collector",
        "note": "Facts 已完成；其余九个模块待办。UPSTREAM-01 C03/C10 已保留给 Evidence-Claims 与 Renderer。",
    }
    prog["progress_computed_from"] = "docs/fusion/CAPABILITY_CROSSWALK.draft.json"
    prog["last_updated"] = datetime.now(TZ).isoformat(timespec="seconds")
    # totals 与草稿 global_state_counts 同源：三态分离，不把 routed 计成 mapped。
    g = doc["global_state_counts"]
    prog["totals"] = {
        "raw_total": g["raw_total"],
        "mapped_count": g["mapped_count"],
        "routed_pending_count": g["routed_pending_count"],
        "unreviewed_count": g["unreviewed_count"],
        "canonical_count": g["canonical_count"],
        "sum_check": g["sum_check"],
    }

    print(f"raw_total            = {len(items)}")
    print(f"facts raw consumed   = {len(facts_keys)}")
    print(f"redirected elsewhere = {len(other_keys)}")
    print(f"canonical count      = {len(canon_out)}  {ids}")
    print(f"per_source_consumed  = {json.dumps(b_facts['per_source_mapped'])}")
    print(f"dedup_ratio          = {b_facts['dedup_ratio']}")
    print(f"global state         = mapped {g['mapped_count']} / routed {g['routed_pending_count']}"
          f" / unreviewed {g['unreviewed_count']}  sum={g['sum_check']}")
    # 防误跑：本构建器只拥有 Facts 的 SL-CAP-0001~0010，若草稿已被后续批次扩展，
    # 直接写入会抹掉其它模块的条目，因此拒绝执行并要求用对应批次的构建器。
    _existing = OUT_DIR / "CAPABILITY_CROSSWALK.draft.json"
    other = []
    if _existing.exists():
        _prev = json.loads(_existing.read_text(encoding="utf-8"))
        other = [c.get("canonical_id") for c in _prev.get("canonical_capabilities", [])
                 if c.get("canonical_id") not in FACTS_IDS]
    if other:
        print("ERROR: 草稿已包含其它模块的能力条目 %s，本构建器会抹除它们。" % other, file=sys.stderr)
        print("请改用对应模块批次的构建器（如 f1b_build_collector.py）。未写入任何文件。", file=sys.stderr)
        return 2

    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        print("RESULT: FAIL", file=sys.stderr)
        print("未写入任何文件。", file=sys.stderr)
        return 1

    DRAFT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROG.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
