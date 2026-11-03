#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / DSH-Adapter 模块：把 DSH-Adapter 的 canonical 能力增量并入交叉表草稿。

增量原则：
  - 只在既有草稿上追加 SL-CAP-0020..0028，不改写 Facts(0001–0010) 与 Collector(0011–0019)；
  - 原始索引只读，不重算、不覆盖；
  - 承接身份必须留迁移痕迹：来自路由表的记 cross_module_redirections，
    直接从 UNREVIEWED 采纳的记 unreviewed_adopted。

统计语义（沿用 F1-B 统计契约修订）：
  mapped        = 已归属某个 canonical_id 的原始身份
  routed_pending= 已裁决去向但仍待该模块接手（不等于 mapped）
  unreviewed    = 既未 mapped 也未 routed
  三者互斥，和 = 原始身份全集 143。
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

MODULE = "DSH-Adapter"

sys.path.insert(0, str(ROOT / "tools" / "fusion"))
from f1b_dsh_adapter_def import CANON, DEFERRED_TO_OTHER_MODULE, CONSUMED_THIS_BATCH, FIRST_ID
import f1b_stats

SOURCES = ["UPSTREAM-01", "UPSTREAM-02", "UPSTREAM-03",
           "UPSTREAM-04", "UPSTREAM-05", "UPSTREAM-06"]
ALLOWED_MODULES = {"Facts", "Collector", "Evidence-Claims", "Product", "Research",
                   "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}


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

    # ── 幂等基线：剔除本批上一次运行留下的条目、分流与晋升 ────────────────
    OWN_IDS = {f"SL-CAP-{n:04d}" for n in range(68, 68 + len(CANON))}
    existing_canon = [c for c in draft["canonical_capabilities"]
                      if c["canonical_id"] not in OWN_IDS
                      and c.get("owner_module") != MODULE]
    # 分流记录的 owner_module 是目标模块；只剔除本批自己声明要承接的键，其余一概保留
    # 本批的「自有键」= 承接键 ∪ 本批声明的出向分流键。
    # 漏掉后者会让构建器每跑一次就把同样的分流记录追加一遍（实测累积成 5 份，
    # 由 Collector c4c 抓到）。分流的剥离必须按同一个键集合做，否则幂等在分流侧失效。
    own_keys = set(CONSUMED_THIS_BATCH) | set(DEFERRED_TO_OTHER_MODULE)
    _pre_draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    _promo_source = list(_pre_draft.get("routed_promotions") or [])
    draft["cross_module_redirections"] = [
        r for r in draft["cross_module_redirections"]
        if (r["upstream_id"], r["original_capability_id"]) not in own_keys
    ]
    _prev_promotions = [
        r for r in (draft.get("routed_promotions") or [])
        if r.get("to_canonical_id") not in OWN_IDS
    ]
    existing_ids = [c["canonical_id"] for c in existing_canon]
    owner_of = {}
    for c in existing_canon:
        for r in c["upstream_refs"]:
            owner_of[(r["upstream_id"], r["original_capability_id"])] = c["canonical_id"]
    existing_routed = {(r["upstream_id"], r["original_capability_id"]): r
                       for r in draft["cross_module_redirections"]}

    # ── ID 连续性：新编号必须从既有最大号 +1 起 ─────────────────────────
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

    # ── 归属唯一性与来源合法性 ─────────────────────────────────────────
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
                errors.append(f"原始身份 {uid}::{oid} 已被分流到 "
                              f"{existing_routed[key]['owner_module']}，不能由 Research 承接")
            if verdict not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                errors.append(f"{c['id']}::{uid}::{oid} 非法裁决 {verdict}")
            owner_of[key] = c["id"]

    # 承接声明必须与 refs 完全一致（多一条 = 编造迁移，少一条 = 丢失迁移凭据）
    declared = set(CONSUMED_THIS_BATCH)
    referenced = {(u, o) for c in CANON for (u, o, _v) in c["refs"]}
    if declared != referenced:
        errors.append(f"承接声明与 canonical 引用不一致：声明多出 {sorted(declared - referenced)}，"
                      f"引用多出 {sorted(referenced - declared)}")

    for key in DEFERRED_TO_OTHER_MODULE:
        if key not in by_key:
            errors.append(f"跨模块去向引用不存在的原始身份 {key[0]}::{key[1]}")
        if key in owner_of:
            errors.append(f"原始身份 {key[0]}::{key[1]} 既归入 EC 又分流")
        mod = DEFERRED_TO_OTHER_MODULE[key][0]
        if mod == MODULE:
            errors.append(f"跨模块去向指向本模块自身：{key}")
        if mod not in ALLOWED_MODULES:
            errors.append(f"跨模块去向模块名非法：{mod}")

    # ── 构建 EC canonical 条目 ────────────────────────────────────────────
    own_out = []
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
        own_out.append({
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

    # ── 晋升记录（ROUTED/UNREVIEWED → MAPPED 的唯一凭据） ────────────────
    promotions = []
    for (uid, oid), (cid, source) in sorted(CONSUMED_THIS_BATCH.items()):
        k = (uid, oid)
        if owner_of.get(k) != cid:
            errors.append(f"承接声明的承接方不符：{uid}::{oid} 声明为 {cid}，实际为 {owner_of.get(k)}")
            continue
        was_routed = any((r["upstream_id"], r["original_capability_id"]) == k
                         and r.get("to_canonical_id") not in OWN_IDS
                         for r in _promo_source)
        # 声明来源必须在磁盘上可复核：说来自路由表，路由表里就必须真有这条
        in_routed_now = any((r["upstream_id"], r["original_capability_id"]) == k
                            for r in _pre_draft.get("cross_module_redirections") or [])
        if source == "cross_module_redirections" and not in_routed_now:
            errors.append(f"{uid}::{oid} 声明来自路由表，但草稿中查无此分流记录")
        if source == "unreviewed_adopted" and in_routed_now:
            errors.append(f"{uid}::{oid} 声明为未审直采，但草稿中路表中已有该分流记录")
        promotions.append({
            "upstream_id": uid,
            "original_capability_id": oid,
            "from": source,
            "to_canonical_id": cid,
            "promoted_in_batch": "F1-B/DSH-Adapter",
            "reason": (
                "Security 批次判定该身份属运行可观测性、改路由指向 DSH-Adapter，本批建 canonical 正式承接"
                if source == "cross_module_redirections"
                else "第2节候选核验后判定归入 DSH-Adapter，本批直接承接（草稿路表中无此分流记录）"
            ),
            "was_in_redirection_table": was_routed,
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

    kept_routed = list(draft["cross_module_redirections"])

    # ── 合并进草稿（既有条目原样保留顺序） ────────────────────────────────
    all_canon = existing_canon + own_out
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
        if c["owner_module"] not in ALLOWED_MODULES:
            errors.append(f"{c['canonical_id']} owner_module 非法：{c['owner_module']}")

    own_mapped = {(r["upstream_id"], r["original_capability_id"])
                 for c in own_out for r in c["upstream_refs"]}

    draft["generated_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    draft["generator"] = ("tools/fusion/f1b_build_dsh_adapter.py"
                          "（增量：前九模块由各自构建器产出）")
    draft["modules_covered_this_batch"] = ["Facts", "Collector", "Evidence-Claims", "Product",
                                           "Research", "Lifecycle", "Security", "Renderer",
                                           "Storage", "DSH-Adapter"]
    draft["canonical_capabilities"] = all_canon
    draft["cross_module_redirections"] = all_routed
    draft["routed_promotions"] = _prev_promotions + promotions
    draft["batches"] = f1b_stats.batches_from_draft(draft)
    _b_own = next(b for b in draft["batches"] if b["module"] == MODULE)
    draft["batch_summary"] = _b_own
    draft["global_state_counts"] = f1b_stats.global_state_counts(draft, raw)
    draft["module_rollup"] = f1b_stats.module_rollup(draft)
    draft.pop("state_counts", None)
    draft["invariants_asserted"] = list(dict.fromkeys(draft["invariants_asserted"] + [
        "四层资产（不可变历史/当前视图/派生索引/展示产物）读写权限各不相同，同一事实只有一个权威副本",
        "派生索引可被整体删除并重建；重建后查询结果等价，且不得作为唯一权威来源",
        "展示产物不得回写权威层；Renderer 的重生成只产新产物",
        "对象逻辑身份、内容哈希、业务版本三者分离；六个标识分列不得互相替代",
        "不得用仓库 URL、文件路径或 Commit SHA 作 Subject 的永久唯一身份",
        "写入五步契约：临时区→校验→记录预期版本→CAS 提交→失败留旧值",
        "并发冲突必须显式返回，不得静默覆盖；权限拒绝不得伪装成空结果",
        "多文件重命名不得宣称跨文件原子事务；原子性范围必须如实声明",
        "不可变对象按内容哈希幂等，重试不得重复创建",
        "查询结果保留来源与版本；检索命中不意味着实时状态，不能自动成为已验证 Claim",
        "不得因为仓库名相同或依赖同名就认定存在经验证的影响关系",
        "知识资产根目录独立于被分析仓库；路径穿越与符号链接必须校验真实路径",
        "位置存在 / 数据流链完整 / 安全影响成立 / 运行时可达 是四项独立检查，任一不可推出另一",
        "没有足够证据的风险只能停在 unconfirmed，不得直接成为确认漏洞",
        "无法验证不得自动标记为 false_positive；它停在 inconclusive（继承 F0 与 EC 对 can't prove → FALSE_POSITIVE 的拒绝）",
        "并非所有安全发现都需要完整数据流链；缺链路必须在 detection_limitations 写明",
        "安全证据一律引用 Evidence-Claims 的证据记录 ID，不得另建 Security Evidence Registry",
        "环境失败绝不改判：工具没跑不是证据",
        "认证覆盖未知时 Boundary Gate 不生效；不得用模型推断的 auth_coverage 自动降级高风险发现",
        "有界静态搜索未发现调用路径时不得宣称 UNREACHABLE，只判 INDETERMINATE",
        "技术严重度与修复优先级是两个独立字段，不得压成一个数字",
        "未运行扫描器或未覆盖规则时，禁止输出「不存在该类漏洞」",
        "族扫描必须扫全族；否定结论携带 family_swept 与 class_negatives",
        "动态验证的双重控制（留证据 / 执行）互不蕴含，默认全关，构造点钉在验证之后",
        "外部内容是不可信数据，不得提升为系统指令；审查步骤由 SourceLore 决定而非被分析仓库",
        "脱敏通过不等于允许发布；分级完成 / 脱敏完成 / 人工审查 / 发布批准 四级互不推导",
        "AI 不得自行把需要人工批准的产物标记为 approved",
        "原始扫描输出不落盘是结构约束，不是事后删除",
        "PR Diff 审查的核心证据在删除侧；只看新增不得判「本次 PR 无安全影响」",
    ]))

    # ── 进度回填（全部由草稿推导） ──────────────────────────────────────
    prog = json.loads(PROG.read_text(encoding="utf-8"))
    prog["phase"] = "F1-A_DONE / F1-B_ALL_BATCHES_DONE"
    prog["module_progress"][MODULE] = {
        "canonical_count": len(own_out),
        "canonical_ids": new_ids,
        "raw_mapped": len(own_mapped),
        "raw_redirected": len(routed_out),
        "status": "DONE",
    }
    prog["next_batch_start"] = {
        "module_hint": "F1-C",
        "note": "F1-B 十个模块批次全部完成。剩余待裁决项进入 F1-C："
                "十项冲突裁决、27 项 UNREVIEWED 归属、11 项 ROUTED 去向、"
                "以及各批次登记的跨模块 owner 争议（U06-C25、SL-CAP-0009 等）。",
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
    print(f"dsh-adapter canonical          = {len(own_out)}  {new_ids}")
    print(f"ec raw mapped         = {len(own_mapped)}")
    print(f"ec redirected         = {len(routed_out)}")
    print(f"mapped_count          = {len(mapped)}")
    print(f"routed_pending_count  = {len(routed)}")
    print(f"unreviewed_count      = {len(unreviewed)}")
    print(f"canonical_count       = {len(all_canon)}")
    print(f"per_source_mapped     = "
          f"{json.dumps({u: sum(1 for k in own_mapped if k[0] == u) for u in SOURCES})}")
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        print("RESULT: FAIL", file=sys.stderr)
        print("未写入任何文件。", file=sys.stderr)
        return 1

    DRAFT.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROG.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
