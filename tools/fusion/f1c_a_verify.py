#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-A 独立验收。只写 F1C_A_VERIFICATION.json。

作用域：本批的 14 项验收 + 两处归属裁决的证据完整性 + 遗留基线与 Crosswalk 一致性。
不重跑 F1-B 的十个构建器（本批为只读分析）。
"""
import json, sys, hashlib, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
REG = F / "F1C_DECISION_REGISTER.json"
BASE = F / "F1C_REMAINDER_BASELINE.json"
DOC = F / "F1C_A_OWNERSHIP_DECISIONS.md"
OUT = F / "F1C_A_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

results = []


def check(cid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append({"id": cid, "name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} :: {detail}")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    reg = json.loads(REG.read_text(encoding="utf-8"))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    items = raw["items"]
    by_key = {(i["upstream_id"], i["original_capability_id"]): i for i in items}
    canon = draft["canonical_capabilities"]
    routed = draft["cross_module_redirections"]

    mapped_owner = {}
    for c in canon:
        for r in c["upstream_refs"]:
            mapped_owner[(r["upstream_id"], r["original_capability_id"])] = c["owner_module"]
    routed_keys = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
    mapped_keys = set(mapped_owner)
    all_keys = set(by_key)
    unreviewed_keys = all_keys - mapped_keys - routed_keys

    def c1():
        ok = len(items) == 143 and len(by_key) == 143
        return ok, f"原始身份 {len(items)} 项，identity_key 唯一={len(by_key)==143}"

    def c2():
        g = draft["global_state_counts"]
        ok = (len(mapped_keys) == g["mapped_count"]
              and len(mapped_keys) == base["totals"]["mapped"])
        return ok, f"已映射 {len(mapped_keys)} = Crosswalk {g['mapped_count']} = 基线 {base['totals']['mapped']}"

    def c3():
        ids = [c["canonical_id"] for c in canon]
        want = [f"SL-CAP-{i:04d}" for i in range(1, len(ids) + 1)]
        return sorted(ids) == want and len(ids) == 73, f"canonical {len(ids)} 条，0001 起连续无断号"

    def c4():
        overlap = routed_keys & unreviewed_keys
        ok = not overlap and len(routed_keys) == 11 and len(unreviewed_keys) == 20
        return ok, f"ROUTED {len(routed_keys)} 与 UNREVIEWED {len(unreviewed_keys)} 不重叠={not overlap}"

    def c5():
        ra = base["reject_audit"]
        pending = set(ra["pending_reject_items"])
        pending_keys = {(k.split("::")[0], k.split("::")[1]) for k in pending}
        inside = pending_keys <= (routed_keys | unreviewed_keys)
        extra = pending_keys - (routed_keys | unreviewed_keys)
        # 交集必须显式给出
        has_intersection = ("reject_intersection_with_routed" in ra
                            and "reject_intersection_with_unreviewed" in ra)
        cnt = len(pending_keys)
        detail = (f"待裁 REJECT {cnt} 项全部落在遗留集合内={inside}；"
                  f"交集字段齐备={has_intersection}；越界={sorted(extra) or '无'}")
        return (inside and has_intersection and cnt == ra["pending_reject_count"]), detail

    def c6():
        d = next(x for x in reg["decisions"] if x["decision_id"] == "F1C-A-001")
        has_ev = ("mechanism_verbatim" in d["source_evidence"]
                  and "original_why" in d["source_evidence"])
        has_competing = len(d["competing_interpretations"]) >= 2
        has_owner = d["proposed_owner"] == "Storage"
        has_impl = "implementation_required" in d
        has_unc = len(d["remaining_uncertainty"]) >= 1
        detail = (f"U06-C25 裁决有原文证据={has_ev}、"
                  f"竞争解释 {len(d['competing_interpretations'])} 条、"
                  f"owner={d['proposed_owner']}、影响说明={has_impl}")
        return (has_ev and has_competing and has_owner and has_impl and has_unc), detail

    def c7():
        d = next(x for x in reg["decisions"] if x["decision_id"] == "F1C-A-002")
        has_ev = "canonical_fields" in d["source_evidence"]
        has_competing = len(d["competing_interpretations"]) >= 2
        has_owner = d["proposed_owner"] == "Facts"
        has_unc = len(d["remaining_uncertainty"]) >= 1
        canon_ok = d["affected_canonical_id"] == "SL-CAP-0009"
        detail = (f"SL-CAP-0009 裁决有字段级证据={has_ev}、"
                  f"竞争解释 {len(d['competing_interpretations'])} 条、"
                  f"owner={d['proposed_owner']}")
        return (has_ev and has_competing and has_owner and has_unc and canon_ok), detail

    def c8():
        # 两项裁决都说明后续如何应用
        states = [d["decision_state"] for d in reg["decisions"]]
        has_applied_field = "applied_changes_this_batch" in reg and "pending_migrations" in reg
        has_state = all(s in {"adjudicated", "applied", "proposed"} for s in states)
        empty_applied = reg["applied_changes_this_batch"] == []
        has_rejected = len(reg.get("rejected_alternatives", [])) >= 3
        detail = (f"decision_state={states}；applied 为空={empty_applied}（本批无迁移）；"
                  f"否决替代方案 {len(reg.get('rejected_alternatives', []))} 条")
        return (has_state and has_applied_field and empty_applied and has_rejected), detail

    def c9():
        # 没有未经记录的 owner 修改：Crosswalk 的 owner 与 git HEAD 一致
        g = git("diff", "--quiet", "HEAD", "--", str(DRAFT.relative_to(ROOT)))
        return g.returncode == 0, "Crosswalk 逐字节未改（无任何 owner 变更）"

    def c10():
        # 许可证与原始处置未被改写
        bad = []
        for k, it in by_key.items():
            if k in mapped_owner:
                pass  # 只检查遗留项与基线记录一致
        for row in base["items"]:
            k = (row["upstream_id"], row["original_capability_id"])
            src = by_key[k]
            if row["original_disposition"] != src["disposition"]:
                bad.append(f"{k} disposition 被改写")
            if row["license"] != {
                "spdx": src["license"].get("spdx"),
                "copy_permitted": src["license"].get("copy_permitted"),
                "attribution_required": src["license"].get("attribution_required"),
                "license_link_required": src["license"].get("license_link_required"),
                "modification_notice_required": src["license"].get("modification_notice_required"),
            }:
                bad.append(f"{k} license 被改写")
        return not bad, f"31 项遗留身份的原始处置与许可逐项未变，问题 {bad or '无'}"

    def c11():
        g1 = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        g2 = git("diff", "--quiet", "HEAD", "--",
                 *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g1.returncode == 0 and g2.returncode == 0, "原始索引与六份审计未改动"

    def c12():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c13():
        t = base["totals"]
        ok = (t["raw_total"] == 143 and t["mapped"] == len(mapped_keys)
              and t["routed"] == len(routed_keys) and t["unreviewed"] == len(unreviewed_keys)
              and t["pending_total"] == len(routed_keys) + len(unreviewed_keys) == 31
              and t["sum_check"] == 143)
        # 逐项状态
        bad = []
        for row in base["items"]:
            k = (row["upstream_id"], row["original_capability_id"])
            cur = "ROUTED" if k in routed_keys else "UNREVIEWED" if k in unreviewed_keys else "MAPPED"
            if row["state"] != cur:
                bad.append(f"{k} 记为 {row['state']}，实际 {cur}")
        return ok and not bad, f"基线三态 {t['mapped']}/{t['routed']}/{t['unreviewed']}={t['sum_check']}，" \
                               f"pending={t['pending_total']}，逐项一致={not bad}"

    def c14():
        g = draft["global_state_counts"]
        inv = g.get("state_invariants", {})
        need = ["mutually_exclusive", "union_equals_total", "no_ghost_identities",
                "routed_not_counted_as_mapped"]
        inv_ok = all(inv.get(k) is True for k in need)
        # 守恒未被削弱：仍要求 143
        ok = inv_ok and g["sum_check"] == 143 and g["raw_total"] == 143
        return ok, f"三态守恒未削弱，sum={g['sum_check']}，不变量={inv_ok}"

    def c15():
        if not DOC.exists():
            return False, f"裁决文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        need = ["U06::C25", "SL-CAP-0009", "唯一建议 owner：Storage", "唯一建议 owner：Facts",
                "terminal_disposition", "31"]
        miss = [k for k in need if k not in txt]
        return not miss, f"文档含两项裁决与终态建议，缺 {miss or '无'}"

    def c16():
        # 本批未启动 F1-C-B：无新增 canonical、无新增 ROUTED、无 terminal_disposition 落地
        g = git("diff", "--quiet", "HEAD", "--", str(DRAFT.relative_to(ROOT)))
        no_f1d = not (F / "CAPABILITY_CROSSWALK.json").exists()
        return g.returncode == 0 and no_f1d, "未改动 Crosswalk、未冻结正式交叉表"

    check("c1", "143 项原始身份完整", c1)
    check("c2", "已映射 112 项保持不变", c2)
    check("c3", "73 条 canonical 完整保留", c3)
    check("c4", "ROUTED 与 UNREVIEWED 不重叠", c4)
    check("c5", "待裁 REJECT 与遗留集合关系已明确", c5)
    check("c6", "U06-C25 裁决有证据支持", c6)
    check("c7", "SL-CAP-0009 裁决有证据支持", c7)
    check("c8", "两项裁决说明后续如何应用", c8)
    check("c9", "无未经记录的 owner 修改", c9)
    check("c10", "许可证与原始处置未被改写", c10)
    check("c11", "原始索引与六份审计未改动", c11)
    check("c12", "正式引擎/Schema/测试未改动", c12)
    check("c13", "基线与 Crosswalk 一致", c13)
    check("c14", "三态守恒检查未削弱", c14)
    check("c15", "裁决文档完整", c15)
    check("c16", "未提前进入 F1-C-B / F1-D", c16)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-C-A（归属争议裁决与遗留基线核对）",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_a_verify.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "scope_note": "只读分析批次：未重跑 F1-B 构建器、未改动 Crosswalk、未启动 F1-C-B",
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
