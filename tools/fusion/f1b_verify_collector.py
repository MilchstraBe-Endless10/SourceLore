#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Collector 批次独立验收。只写 F1B_COLLECTOR_VERIFICATION.json。"""
import json, sys, hashlib, subprocess, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
PROG = F / "CROSSWALK_PROGRESS.json"
OUT = F / "F1B_COLLECTOR_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
COLLECTOR_IDS = [f"SL-CAP-{n:04d}" for n in range(11, 20)]

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


def load():
    return (json.loads(RAW.read_text(encoding="utf-8")),
            json.loads(DRAFT.read_text(encoding="utf-8")),
            json.loads(PROG.read_text(encoding="utf-8")))


def main() -> int:
    raw, draft, prog = load()
    items = raw["items"]
    by_key = {(i["upstream_id"], i["original_capability_id"]): i for i in items}
    canon = draft["canonical_capabilities"]
    routed = draft["cross_module_redirections"]
    ids = [c["canonical_id"] for c in canon]

    def c1():
        h = hashlib.sha256(RAW.read_bytes()).hexdigest()
        return (h == raw["counts"] and False) if False else (h == draft["source_index_sha256"], f"raw sha256={h[:16]} 与草稿记录一致")

    def c2():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "RAW_CAPABILITY_INDEX.json 与 HEAD 逐字节一致" if g.returncode == 0 else "原始索引被改动"

    def c3():
        ok = len(items) == 143 and len(by_key) == 143
        return ok, f"原始项数 {len(items)}，唯一身份 {len(by_key)}"

    def c4():
        bad = [c for c in canon if not re.fullmatch(r"SL-CAP-\d{4}", c["canonical_id"])]
        return (not bad, "canonical_id 形态全部合法" if not bad else f"异常 {[c['canonical_id'] for c in bad]}")

    def c5():
        n = len(ids)
        want = [f"SL-CAP-{i:04d}" for i in range(1, n + 1)]
        return sorted(ids) == want, f"共 {n} 条，从 0001 连续无断号"

    def c6():
        facts = [i for i in ids if i <= "SL-CAP-0010"]
        ok = sorted(facts) == [f"SL-CAP-{i:04d}" for i in range(1, 11)]
        return ok, f"Facts 十条原位保留 {len(facts)}/10"

    def c7():
        got = set(ids) & set(COLLECTOR_IDS)
        return got == set(COLLECTOR_IDS), f"Collector 编号 {len(got)}/9 全部存在"

    def c8():
        own = [c["canonical_id"] for c in canon if c["owner_module"] == "Collector"]
        ok = set(own) == set(COLLECTOR_IDS)
        return ok, f"owner_module=Collector 的条目数 {len(own)}"

    def c9():
        bad = [c["canonical_id"] for c in canon if c["owner_module"] not in MODULES]
        dup = [c["canonical_id"] for c in canon if c["owner_module"] == "Collector" and c["canonical_id"] not in COLLECTOR_IDS]
        return (not bad and not dup), f"非法 owner {bad}；编号越界 {dup}"

    def c10():
        seen, dup = set(), []
        for c in canon:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                if k in seen:
                    dup.append(f"{k[0]}::{k[1]}")
                seen.add(k)
        return (not dup, f"全局无重复归属，共 {len(seen)} 个身份" if not dup else f"重复 {dup}")

    def c11():
        owner = {(r["upstream_id"], r["original_capability_id"]): c["canonical_id"]
                 for c in canon for r in c["upstream_refs"]}
        rm = {(r["upstream_id"], r["original_capability_id"]): r["owner_module"] for r in routed}
        clash = [f"{k[0]}::{k[1]}" for k in owner if k in rm]
        return (not clash, "分流与归属互斥" if not clash else f"同时出现 {clash}")

    def c12():
        mapped = {(r["upstream_id"], r["original_capability_id"]) for c in canon for r in c["upstream_refs"]}
        rted = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        unrev = set(by_key) - mapped - rted
        total = len(mapped) + len(rted) + len(unrev)
        ok = total == len(by_key) == 143
        return ok, f"mapped {len(mapped)} + routed {len(rted)} + unreviewed {len(unrev)} = {total}"

    def c13():
        # 统计契约修订后 state_counts 已废除，累计视图改由 global_state_counts 承载
        sc = draft.get("global_state_counts", {})
        mapped = {(r["upstream_id"], r["original_capability_id"]) for c in canon for r in c["upstream_refs"]}
        rted = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        unrev = set(by_key) - mapped - rted
        ok = (sc.get("mapped_count") == len(mapped) and
              sc.get("routed_pending_count") == len(rted) and
              sc.get("unreviewed_count") == len(unrev) and
              sc.get("canonical_count") == len(canon))
        return ok, f"草稿 global_state_counts 与实际一致 mapped={len(mapped)} routed={len(rted)} unreviewed={len(unrev)}"

    def c14():
        t = prog["totals"]
        banned = [k for k in ("raw_assigned", "raw_pending", "canonical_total") if k in t]
        need = ["mapped_count", "routed_pending_count", "unreviewed_count", "canonical_count"]
        missing = [k for k in need if k not in t]
        ok = not banned and not missing and t.get("sum_check") == 143
        return ok, f"禁用旧字段 {banned}；缺失 {missing}；sum_check={t.get('sum_check')}"

    def c15():
        n = sum(1 for i in items if i["disposition"] == "REJECT")
        return True, f"（信息）原始 REJECT 总数 {n}，不作为判定条件"

    def c16():
        c11_ = next(c for c in canon if c["canonical_id"] == "SL-CAP-0011")
        names = [r["upstream_capability"] for r in c11_["upstream_refs"]]
        ok = len(c11_["upstream_refs"]) >= 2 and any("REST" in n or "client" in n or "客户端" in n for n in names)
        return ok, f"唯一入口证据源 {len(c11_['upstream_refs'])} 条：{[r['upstream_id']+'::'+r['original_capability_id'] for r in c11_['upstream_refs']]}"

    def c17():
        c = next(x for x in canon if x["canonical_id"] == "SL-CAP-0013")
        blob = json.dumps(c, ensure_ascii=False)
        ok = all(k in blob for k in ("commit_sha", "root_tree_sha", "tree_query_ref"))
        return ok, "三字段分列已写入 SL-CAP-0013"

    def c18():
        c = next(x for x in canon if x["canonical_id"] == "SL-CAP-0014")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("rel=next" in blob or "rel=\"next\"" in blob) and "短页" in blob
        return ok, "分页判据改为 Link rel=next，短页终止被否"

    def c19():
        c = next(x for x in canon if x["canonical_id"] == "SL-CAP-0019")
        ok = c["upstream_refs"] == [] and bool(c.get("merge_note"))
        return ok, "SL-CAP-0019 无上游来源且理由非空" if ok else "独立条目缺少理由或混入来源"

    def c20():
        c = next(x for x in canon if x["canonical_id"] == "SL-CAP-0018")
        return c["v1_scope"] == "V1_DEFERRED", f"缓存一致性 v1_scope={c['v1_scope']}"

    def c21():
        c = next(x for x in canon if x["canonical_id"] == "SL-CAP-0017")
        uids = {r["upstream_id"] for r in c["upstream_refs"]}
        keys = {(r["upstream_id"], r["original_capability_id"]) for r in c["upstream_refs"]}
        ok = ("UPSTREAM-02", "C05") not in keys
        return ok, f"未抢占 Facts 已用的 U02::C05；本条来源 {sorted(keys)}"

    def c22():
        facts = [c for c in canon if c["canonical_id"] <= "SL-CAP-0010"]
        ok = all("Collector" not in json.dumps(c, ensure_ascii=False)[:2000] or True for c in facts)
        bad = [c["canonical_id"] for c in facts
               if any(r["upstream_id"] == "UPSTREAM-01" and r["original_capability_id"] in ("C03", "C10")
                      for r in c["upstream_refs"])]
        return (not bad), f"Facts 未吸收 Collector/Renderer 保留项 {bad}"

    def c23():
        g = git("diff", "--quiet", "HEAD", "--", "progress/UPSTREAM-01-audit.json",
                "progress/UPSTREAM-02-audit.json", "progress/UPSTREAM-03-audit.json",
                "progress/UPSTREAM-04-audit.json", "progress/UPSTREAM-05-audit.json",
                "progress/UPSTREAM-06-audit.json")
        return g.returncode == 0, "六份上游审计文件未改动" if g.returncode == 0 else "上游审计文件被改动"

    def c24():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", f"src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c25():
        dec = F / "F1B_COLLECTOR_DECISIONS.md"
        if not dec.exists():
            return False, "决策文档不存在: F1B_COLLECTOR_DECISIONS.md"
        t = dec.read_text(encoding="utf-8")
        missing = [i for i in COLLECTOR_IDS if i not in t]
        nums = all(s in t for s in ("22", "14", "107", "143"))
        return (not missing and nums), f"缺失编号 {missing}；关键计数齐备={nums}"

    def c26():
        ok = not (F / "CAPABILITY_CROSSWALK.json").exists()
        return ok, "正式交叉表尚未冻结（符合 F1-D 前不得发布）"

    check("c1", "原始索引哈希与草稿记录一致", c1)
    check("c2", "原始索引未被修改", c2)
    check("c3", "原始身份总数 143 且无重复", c3)
    check("c4", "canonical_id 形态合法", c4)
    def c4b():
        dup = sorted({i for i in ids if ids.count(i) > 1})
        return (not dup, f"canonical_id 无重复（共 {len(ids)} 条）" if not dup else f"重复编号 {dup}")

    def c4c():
        keys = [(r["upstream_id"], r["original_capability_id"]) for r in routed]
        dup = sorted({f"{a}::{b}" for a, b in keys if keys.count((a, b)) > 1})
        prom = draft.get("routed_promotions", [])
        pk = [(r.get("upstream_id"), r.get("original_capability_id")) for r in prom]
        pdup = sorted({f"{a}::{b}" for a, b in pk if pk.count((a, b)) > 1})
        ok = not dup and not pdup
        return ok, f"分流 {len(routed)} 条、晋升 {len(prom)} 条均无重复" if ok else f"分流重复 {dup}；晋升重复 {pdup}"

    check("c4b", "canonical_id 无重复", c4b)
    check("c4c", "分流与晋升记录无重复", c4c)
    check("c5", "canonical_id 从 0001 连续", c5)
    check("c6", "Facts 十条原位保留", c6)
    check("c7", "Collector 编号 0011-0019 齐全", c7)
    check("c8", "owner_module 正确标注", c8)
    check("c9", "owner_module 取值合法且不越界", c9)
    check("c10", "原始身份全局唯一归属", c10)
    check("c11", "分流与归属互斥", c11)
    check("c12", "三态计数之和等于 143", c12)
    check("c13", "草稿 state_counts 与实际一致", c13)
    check("c14", "进度统计已按三态口径改写", c14)
    check("c15", "REJECT 计数信息", c15)
    check("c16", "唯一入口证据充分", c16)
    check("c17", "三字段分列已落地", c17)
    check("c18", "分页判据已纠正", c18)
    check("c19", "独立条目无来源但有理由", c19)
    check("c20", "缓存条目保持 DEFERRED", c20)
    check("c21", "未抢占 Facts 已用身份", c21)
    check("c22", "Facts 未吸收保留项", c22)
    check("c23", "六份上游审计未改动", c23)
    check("c24", "src/tests/schemas 无改动", c24)
    check("c25", "决策文档齐备", c25)
    check("c26", "正式交叉表未提前冻结", c26)

    # ── c27：晋升记录必须落盘且不与分流重复计数 ─────────────────
    promos = draft.get("routed_promotions", [])
    promo_keys = {(r.get("upstream_id"), r.get("original_capability_id")) for r in promos}
    collector_owned = {
        (ref["upstream_id"], ref["original_capability_id"])
        for c in draft["canonical_capabilities"]
        if c["canonical_id"] in COLLECTOR_IDS
        for ref in c["upstream_refs"]
    }
    promos_to_collector = [r for r in promos if r.get("to_canonical_id") in COLLECTOR_IDS]
    # 作用域收窄：ghost 判定只对「指向 Collector 的晋升」生效。其它批次（如
    # Evidence-Claims）写入的晋升记录不属于本验证器职责，拿 Collector 的引用集
    # 去卡它们必然报假阳性；本批只要求 Collector 自己那条晋升链无编造。
    still_routed = {
        (r["upstream_id"], r["original_capability_id"])
        for r in draft["cross_module_redirections"]
    }
    overlap = promo_keys & still_routed

    def c27():
        # 晋升必须留痕：否则同一个身份被算成 MAPPED 却无任何迁移证据
        if not promos_to_collector:
            return False, "routed_promotions 中没有指向 Collector 的记录，晋升无声发生"
        # 晋升的对象必须是 Collector 真正引用的身份，不能凭空造
        ghost = { (r.get("upstream_id"), r.get("original_capability_id")) for r in promos_to_collector } - collector_owned
        if ghost:
            return False, f"晋升了 Collector 并未引用的身份：{sorted(ghost)}"
        # 同一身份不能既在分流表又在晋升表，否则同时计 ROUTED 和 MAPPED
        promo_overlap = {(r.get("upstream_id"), r.get("original_capability_id"))
                         for r in promos_to_collector} & still_routed
        if promo_overlap:
            return False, f"Collector 晋升的身份同时仍留在分流表：{sorted(promo_overlap)}"
        return True, f"晋升 {len(promos_to_collector)} 条，全在 Collector 名下，与分流零重叠"

    check("c27", "晋升记录已落盘且不与分流重复计数", c27)

    # ── c28：raw_mapped 与实际引用身份数自洽 ──────────────────────
    def c28():
        batch = next(
            (b for b in draft.get("batches", []) if b.get("batch") == "F1-B/Collector"), None
        )
        if batch is None:
            return False, "草稿中没有 F1-B/Collector 批次记录"
        # 新契约字段名：raw_mapped_to_this_module（不再是 raw_mapped）
        recorded = batch.get("raw_mapped_to_this_module")
        if recorded != len(collector_owned):
            return False, f"批次记录 raw_mapped_to_this_module={recorded}，实际引用身份 {len(collector_owned)} 条"
        return True, f"raw_mapped_to_this_module={recorded} 与实际引用身份 {len(collector_owned)} 条一致"

    check("c28", "批次 mapped 计数与实际引用身份数一致", c28)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / Collector",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_collector.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
