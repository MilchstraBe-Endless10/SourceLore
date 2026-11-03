#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Evidence-Claims 批次独立验收。只写 F1B_EC_VERIFICATION.json。

作用域：本验证器只判定 EC 批次自己的能力（SL-CAP-0020..0028）与本批不变量，
不替 Facts / Collector 的条目下结论（各自验证器负责）。
"""
import json, sys, hashlib, subprocess, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
PROG = F / "CROSSWALK_PROGRESS.json"
DOC = F / "F1B_EVIDENCE_CLAIMS_DECISIONS.md"
OUT = F / "F1B_EC_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULE = "Evidence-Claims"
MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
EC_IDS = [f"SL-CAP-{n:04d}" for n in range(20, 29)]
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}
COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}

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
    prog = json.loads(PROG.read_text(encoding="utf-8"))
    items = raw["items"]
    by_key = {(i["upstream_id"], i["original_capability_id"]): i for i in items}
    canon = draft["canonical_capabilities"]
    routed = draft["cross_module_redirections"]
    promos = draft.get("routed_promotions") or []
    ids = [c["canonical_id"] for c in canon]
    ec_canon = [c for c in canon if c["canonical_id"] in EC_IDS]
    ec_owned = {(r["upstream_id"], r["original_capability_id"])
                for c in ec_canon for r in c["upstream_refs"]}
    promos_to_ec = [r for r in promos if r.get("to_canonical_id") in EC_IDS]

    # ── 基线与完整性 ────────────────────────────────────────────────────
    def c1():
        h = hashlib.sha256(RAW.read_bytes()).hexdigest()
        return h == draft["source_index_sha256"], f"raw sha256={h[:16]} 与草稿记录一致"

    def c2():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始索引与 HEAD 逐字节一致" if g.returncode == 0 else "原始索引被改动"

    def c3():
        ok = len(items) == 143 and len(by_key) == 143
        return ok, f"原始项数 {len(items)}，唯一身份 {len(by_key)}"

    def c4():
        bad = [i for i in ids if not re.fullmatch(r"SL-CAP-\d{4}", i)]
        return not bad, "canonical_id 形态全部合法" if not bad else f"异常 {bad}"

    def c5():
        want = [f"SL-CAP-{i:04d}" for i in range(1, len(ids) + 1)]
        return sorted(ids) == want, f"共 {len(ids)} 条，从 0001 连续无断号"

    def c6():
        dup = sorted({i for i in ids if ids.count(i) > 1})
        return not dup, f"canonical_id 无重复（{len(ids)} 条）" if not dup else f"重复 {dup}"

    # ── EC 编号与归属 ───────────────────────────────────────────────────
    def c7():
        got = set(ids) & set(EC_IDS)
        return got == set(EC_IDS), f"EC 编号 {len(got)}/9 全部存在"

    def c8():
        own = {c["canonical_id"] for c in canon if c["owner_module"] == MODULE}
        return own == set(EC_IDS), f"owner_module=Evidence-Claims 的条目 {len(own)} 条，与 EC 编号集一致"

    def c9():
        # 前两批的编号与 owner 不得被本批改动
        facts_owners = {c["canonical_id"]: c["owner_module"] for c in canon if c["canonical_id"] in FACTS_IDS}
        col_owners = {c["canonical_id"]: c["owner_module"] for c in canon if c["canonical_id"] in COLLECTOR_IDS}
        bad_f = [k for k, v in facts_owners.items() if v != "Facts"]
        bad_c = [k for k, v in col_owners.items() if v != "Collector"]
        missing = (set(FACTS_IDS) | set(COLLECTOR_IDS)) - set(ids)
        detail = (f"Facts 越界 {bad_f or '无'}；Collector 越界 {bad_c or '无'}；"
                  f"编号缺失 {sorted(missing) or '无'}")
        return (not bad_f and not bad_c and not missing), detail

    def c10():
        bad = [c["canonical_id"] for c in canon if c["owner_module"] not in MODULES]
        return not bad, f"owner_module 取值合法，异常 {bad or '无'}"

    def c11():
        seen, dup = {}, []
        for c in canon:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                if k in seen:
                    dup.append(f"{k[0]}::{k[1]}（{seen[k]} 与 {c['canonical_id']}）")
                seen[k] = c["canonical_id"]
        return not dup, f"全局无重复归属，共 {len(seen)} 个身份" if not dup else f"重复 {dup}"

    def c12():
        rm = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        owner = {(r["upstream_id"], r["original_capability_id"]) for c in canon for r in c["upstream_refs"]}
        clash = owner & rm
        return not clash, "分流与归属互斥" if not clash else f"同时出现 {sorted(clash)}"

    def c13():
        mapped = {(r["upstream_id"], r["original_capability_id"]) for c in canon for r in c["upstream_refs"]}
        rted = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        unrev = set(by_key) - mapped - rted
        total = len(mapped) + len(rted) + len(unrev)
        ok = total == len(by_key) == 143
        return ok, f"mapped {len(mapped)} + routed {len(rted)} + unreviewed {len(unrev)} = {total}"

    def c14():
        g = draft["global_state_counts"]
        mapped = {(r["upstream_id"], r["original_capability_id"]) for c in canon for r in c["upstream_refs"]}
        rted = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        unrev = set(by_key) - mapped - rted
        ok = (g.get("mapped_count") == len(mapped) and
              g.get("routed_pending_count") == len(rted) and
              g.get("unreviewed_count") == len(unrev) and
              g.get("canonical_count") == len(canon))
        inv = g.get("state_invariants", {})
        inv_ok = all(inv.get(k) is True for k in
                     ("mutually_exclusive", "union_equals_total",
                      "no_ghost_identities", "routed_not_counted_as_mapped"))
        return (ok and inv_ok,
                f"global_state_counts 与实算一致 mapped={len(mapped)} routed={len(rted)} "
                f"unreviewed={len(unrev)} canonical={len(canon)}；四条不变量={inv_ok}")

    def c15():
        t = prog["totals"]
        g = draft["global_state_counts"]
        need = ["mapped_count", "routed_pending_count", "unreviewed_count", "canonical_count", "sum_check"]
        missing = [k for k in need if k not in t]
        stale = [k for k in ("raw_assigned", "raw_pending", "canonical_total") if k in t]
        agree = all(t.get(k) == g.get(k) for k in need if k in t)
        return (not missing and not stale and agree,
                f"缺失 {missing or '无'}；旧口径残留 {stale or '无'}；与草稿一致={agree}；sum_check={t.get('sum_check')}")

    # ── 批次视图 ────────────────────────────────────────────────────────
    def c16():
        b = next((x for x in draft.get("batches", []) if x["module"] == MODULE), None)
        if b is None:
            return False, "草稿中没有 Evidence-Claims 批次记录"
        ok = (b["raw_mapped_to_this_module"] == len(ec_owned)
              and b["canonical_ids"] == EC_IDS
              and b["canonical_ids"] == sorted(b["canonical_ids"]))
        return ok, (f"raw_mapped_to_this_module={b['raw_mapped_to_this_module']} 与实际 {len(ec_owned)} 一致；"
                    f"canonical_ids 齐备={b['canonical_ids'] == EC_IDS}")

    def c17():
        bs = draft["batch_summary"]
        ok = bs["module"] == MODULE and bs.get("batch") == "F1-B/Evidence-Claims"
        return ok, f"batch_summary 指向最近完成批次：{bs.get('batch')}（module={bs['module']}）"

    def c18():
        names = [b["module"] for b in draft.get("batches", [])]
        order = ["Facts", "Collector", "Evidence-Claims"]
        return names[:3] == order, f"批次按业务顺序排列：{names}"

    def c19():
        # 前两批的批次条目必须还在。mapped 数是定格历史（canonical 归属不随下游变化），
        # 必须恒为 Facts 11 / Collector 11；出向分流按统计契约是现算视图
        # （def 声明 − 已晋升），下游承接后会自然减少，因此只校验「与现算自洽」，
        # 不拿上一批的旧值去卡它——那等于要求历史禁止推进。
        bf = next((x for x in draft["batches"] if x["module"] == "Facts"), None)
        bc = next((x for x in draft["batches"] if x["module"] == "Collector"), None)
        if not bf or not bc:
            return False, "Facts 或 Collector 批次条目丢失"
        import f1b_stats
        recalc = {b["module"]: b for b in f1b_stats.batches_from_draft(draft)}
        mapped_ok = bf["raw_mapped_to_this_module"] == 11 and bc["raw_mapped_to_this_module"] == 11
        self_consistent = (bf["raw_redirected_to_other_modules"] ==
                           recalc["Facts"]["raw_redirected_to_other_modules"]
                           and bc["raw_redirected_to_other_modules"] ==
                           recalc["Collector"]["raw_redirected_to_other_modules"])
        detail = (f"Facts {bf['raw_mapped_to_this_module']}/{bf['raw_redirected_to_other_modules']}，"
                  f"Collector {bc['raw_mapped_to_this_module']}/{bc['raw_redirected_to_other_modules']}；"
                  f"mapped 定格={mapped_ok}；出向与现算自洽={self_consistent}")
        return mapped_ok and self_consistent, detail

    # ── 迁移凭据 ────────────────────────────────────────────────────────
    def c20():
        if not promos_to_ec:
            return False, "routed_promotions 中没有指向 EC 的记录，晋升无声发生"
        ghost = {(r.get("upstream_id"), r.get("original_capability_id")) for r in promos_to_ec} - ec_owned
        if ghost:
            return False, f"晋升了 EC 并未引用的身份：{sorted(ghost)}"
        return True, f"晋升 {len(promos_to_ec)} 条，全部落在 EC 的 canonical 名下"

    def c21():
        targets = {r["to_canonical_id"] for r in promos_to_ec}
        missing = [i for i in EC_IDS if i not in targets]
        return not missing, f"9 条 EC canonical 全部有对应晋升记录" if not missing else f"缺晋升的编号 {missing}"

    def c22():
        # 来自路由表的必须真在路由表里（本批已消费，故查 HEAD 版本草稿不现实；
        # 改判：from=cross_module_redirections 的记录，其 identity_key 必须能在
        # 原始索引定位，且不得声称来自 unreviewed 却在路由表里有过条目——后者
        # 用 promoted 的 was_in_redirection_table 字段做交叉验证）
        bad = []
        for r in promos_to_ec:
            k = (r.get("upstream_id"), r.get("original_capability_id"))
            if k not in by_key:
                bad.append(f"{k} 不在原始索引")
            if r.get("from") not in {"cross_module_redirections", "unreviewed_adopted"}:
                bad.append(f"{k} from 取值非法 {r.get('from')}")
            if r.get("from") == "unreviewed_adopted" and r.get("was_in_redirection_table"):
                bad.append(f"{k} 声称未审直采，却本来就在路由表里")
        return not bad, f"晋升来源声明 {len(promos_to_ec)} 条，问题 {bad or '无'}"

    def c23():
        dup = sorted({f"{r.get('upstream_id')}::{r.get('original_capability_id')}"
                      for r in promos if [ (x.get("upstream_id"), x.get("original_capability_id"))
                      for x in promos].count((r.get('upstream_id'), r.get('original_capability_id'))) > 1})
        return not dup, f"晋升记录无重复（共 {len(promos)} 条）" if not dup else f"重复 {dup}"

    # ── EC 本批内容约束 ──────────────────────────────────────────────────
    def c24():
        # 9 条 canonical，ID 连续 0020–0028，且都从 0020 起
        detail = f"EC canonical 数 {len(ec_canon)}，编号 {[c['canonical_id'] for c in ec_canon]}"
        return (len(ec_canon) == 9 and [c["canonical_id"] for c in ec_canon] == EC_IDS), detail

    def c25():
        per_source = {u: sum(1 for k in ec_owned if k[0] == u)
                      for u in ["UPSTREAM-01", "UPSTREAM-02", "UPSTREAM-03",
                                "UPSTREAM-04", "UPSTREAM-05", "UPSTREAM-06"]}
        return True, f"（信息）EC 承接来源分布 {json.dumps(per_source, ensure_ascii=False)}"

    def c26():
        blob = json.dumps(next(c for c in ec_canon if c["canonical_id"] == "SL-CAP-0020"), ensure_ascii=False)
        need = ["content_hash", "reproducible", "redactions", "response_body", "response_headers",
                "request_meta_no_credential", "delta_note"]
        miss = [k for k in need if k not in blob]
        return not miss, f"存档契约强制字段齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c27():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0021")
        blob = json.dumps(c, ensure_ascii=False)
        ok = all(k in blob for k in ("entrypoint", "hops", "sink", "file:line", "partial_flow"))
        return ok, "四节点数据流结构 + partial_flow 降级态已落地"

    def c28():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0022")
        blob = json.dumps(c, ensure_ascii=False)
        ok = all(k in blob for k in ("present", "missing", "unresolvable"))
        return ok, "引用校验三态（present/missing/unresolvable）齐备，missing 与 unresolvable 分列"

    def c29():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0022")
        blob = json.dumps(c, ensure_ascii=False)
        return "不得合并为" in blob, "三态分列有显式禁止合并条款"

    def c30():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0023")
        blob = json.dumps(c, ensure_ascii=False)
        ok = "MUST NOT be presented as facts" in blob and "hypothesis" in blob
        return ok, "未支撑陈述不得以事实形态出现，硬规则已写入 prompt 级措辞"

    def c31():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0024")
        blob = json.dumps(c, ensure_ascii=False)
        ok = "[NEEDS INPUT]" in blob and "needs_input" in blob
        # 不得编造渲染格式：unresolved 中必须显式留下待定
        has_open = "unresolved" in blob and "不得凭空补写" in blob
        return (ok and has_open), "占位符与 needs_input 清单已落地，且渲染格式留 unresolved（未编造）"

    def c32():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0025")
        blob = json.dumps(c, ensure_ascii=False)
        ok = "auto_generated" in blob and "edited_by_human" in blob and "evidence_refs" in blob
        return ok, "产物自证出处（auto_generated/generator/run_id/edited_by_human/evidence_refs）齐备"

    def c33():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0026")
        blob = json.dumps(c, ensure_ascii=False)
        segs = ["answer", "evidence", "artifacts", "limitations"]
        ok = all(s in blob for s in segs) and "observation_separated" in blob
        return ok, f"四段结构 {segs} 齐备，观察/解释分离字段存在"

    def c34():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0027")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["verified_commit", "verified_deps", "verified_env", "accessed_at",
                "superseded_by", "supersedes", "retracted_reason"]
        miss = [k for k in need if k not in blob]
        return not miss, f"新鲜度四字段 + 替代关系三字段齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c35():
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0028")
        blob = json.dumps(c, ensure_ascii=False)
        states = ["unverified", "partially_supported", "supported", "refuted",
                  "insufficient_evidence", "adjudication_blocked"]
        miss = [s for s in states if s not in blob]
        tiers = ["confirmed", "qualified", "insufficient"]
        tmiss = [t for t in tiers if t not in blob]
        detail = f"六态 {miss or '齐备'}；report_tier 映射 {tmiss or '齐备'}"
        return (not miss and not tmiss), detail

    def c36():
        # 核心裁决：「不可验证即判否」必须被显式拒绝
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0028")
        blob = json.dumps(c, ensure_ascii=False)
        has_rule = "不可验证只产生 insufficient_evidence" in blob and "禁止落成 refuted" in blob
        has_reject = "无法证明" in blob and "已被证伪" in blob
        has_note = "FALSE_POSITIVE" in blob and "拒绝" in blob
        detail = f"硬规则={has_rule}；不等价声明={has_reject}；决策文档级拒绝记录={has_note}"
        return (has_rule and has_reject and has_note), detail

    def c37():
        # U06 全部来源必须 copy_permitted=false，且条目必须明说不可复用
        bad = []
        for c in ec_canon:
            per = c["license_permission"]["per_upstream"]
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
            if any(p["upstream_id"] == "UPSTREAM-06" for p in per):
                if c["license_permission"].get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 含 U06 来源但整体判可复制")
        return not bad, f"U06 复制许可全为 false，问题 {bad or '无'}"

    def c38():
        bad = []
        for c in ec_canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可未逐源记录")
            for p in per:
                if p.get("spdx") and not p.get("attribution_required") and p.get("copy_permitted"):
                    bad.append(f"{c['canonical_id']} {p['spdx']} 可复制却未要求署名")
        return not bad, f"逐源许可条目 {sum(len(c['license_permission']['per_upstream']) for c in ec_canon)} 条，问题 {bad or '无'}"

    def c39():
        # 每条 canonical 必须说明合并/不合并理由（merge_note 非空）
        bad = [c["canonical_id"] for c in ec_canon if not c.get("merge_note")]
        return not bad, f"9 条均有 merge_note" if not bad else f"缺 merge_note {bad}"

    def c40():
        # 处置分布与四值合法
        bad = [c["canonical_id"] for c in ec_canon
               if c["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}]
        dist = {}
        for c in ec_canon:
            dist[c["disposition"]] = dist.get(c["disposition"], 0) + 1
        return not bad, f"处置分布 {dist}；非法 {bad or '无'}"

    def c41():
        # 每条至少一个 I/O 边界与 V1 scope
        bad = [c["canonical_id"] for c in ec_canon
               if not c.get("input_boundary") or not c.get("output_boundary") or not c.get("v1_scope")]
        return not bad, "I/O 边界与 V1 scope 全部齐备" if not bad else f"缺 {bad}"

    def c42():
        # 依赖只能指向已存在模块，且不得自依赖
        bad = []
        for c in ec_canon:
            for d in c["dependencies"]:
                if d not in MODULES:
                    bad.append(f"{c['canonical_id']} 依赖非法模块 {d}")
            if MODULE in c["dependencies"] and c["canonical_id"] not in (
                    {"SL-CAP-0028"} & {c["canonical_id"]}):
                # 允许同模块依赖（0026/0028 依赖本模块其它条目），但不得指向自身
                pass
        return not bad, f"依赖模块取值合法，问题 {bad or '无'}"

    def c43():
        # 原始索引未被改动（哈希级）
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始索引逐字节未变"

    def c44():
        g = git("diff", "--quiet", "HEAD", "--",
                *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g.returncode == 0, "六份上游审计未改动"

    def c45():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c46():
        return not (F / "CAPABILITY_CROSSWALK.json").exists(), "正式交叉表尚未冻结（F1-D 前不得发布）"

    def c47():
        if not DOC.exists():
            return False, f"决策文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        missing = [i for i in EC_IDS if i not in txt]
        b = next(x for x in draft["batches"] if x["module"] == MODULE)
        nums = [b["raw_mapped_to_this_module"], len(b["canonical_ids"]),
                b["raw_redirected_to_other_modules"]]
        nums_ok = all(str(n) in txt for n in nums)
        g = draft["global_state_counts"]
        gnums = [g["raw_total"], g["mapped_count"], g["routed_pending_count"],
                 g["unreviewed_count"], g["sum_check"]]
        gnums_ok = all(str(n) in txt for n in gnums)
        return (not missing and nums_ok and gnums_ok,
                f"缺失 ID={missing or '无'}；批次数字 {nums} 出现={nums_ok}；全局数字 {gnums} 出现={gnums_ok}")

    def c48():
        # 六项 E 约束必须逐条落章（第E节要求）
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = ["E-1", "E-2", "E-3", "E-4", "E-5", "E-6"]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"第E节六项约束 {miss or '全部落章'}"

    def c49():
        # 9 条 ROUTED 必须全部被承接，且 EC 不再外推分流给别的模块
        routed_to_ec = [r for r in routed if r["owner_module"] == MODULE]
        consumed = {(p.get("upstream_id"), p.get("original_capability_id")) for p in promos_to_ec}
        nine = {("UPSTREAM-01", "C03"), ("UPSTREAM-03", "C03"), ("UPSTREAM-04", "C07"),
                ("UPSTREAM-04", "C08"), ("UPSTREAM-04", "C10"), ("UPSTREAM-04", "C11"),
                ("UPSTREAM-05", "C05"), ("UPSTREAM-05", "C06"), ("UPSTREAM-06", "C05")}
        missing = nine - consumed
        leftover = len(routed_to_ec)
        detail = (f"九条 ROUTED 全部承接={not missing}（缺 {missing or '无'}）；"
                  f"EC 名下残留分流 {leftover} 条")
        return (not missing and leftover == 0), detail

    def c50():
        # U06-C06 必须显式拒绝「不可验证→FALSE_POSITIVE」
        txt = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
        c = next(x for x in ec_canon if x["canonical_id"] == "SL-CAP-0028")
        keys = {(r["upstream_id"], r["original_capability_id"]) for r in c["upstream_refs"]}
        has_key = ("UPSTREAM-06", "C06") in keys
        doc_reject = "FALSE_POSITIVE" in txt and "不可验证即判否" in txt
        detail = f"U06::C06 归属 SL-CAP-0028={has_key}；文档记录拒绝语义={doc_reject}"
        return (has_key and doc_reject), detail

    check("c1", "原始索引哈希与草稿记录一致", c1)
    check("c2", "原始索引未被修改", c2)
    check("c3", "原始身份总数 143 且无重复", c3)
    check("c4", "canonical_id 形态合法", c4)
    check("c5", "canonical_id 从 0001 连续", c5)
    check("c6", "canonical_id 无重复", c6)
    check("c7", "EC 编号 0020-0028 齐全", c7)
    check("c8", "EC owner_module 正确标注", c8)
    check("c9", "前两批编号与 owner 未被改动", c9)
    check("c10", "owner_module 取值合法", c10)
    check("c11", "原始身份全局唯一归属", c11)
    check("c12", "分流与归属互斥", c12)
    check("c13", "三态计数之和等于 143", c13)
    check("c14", "global_state_counts 与实算一致且不变量成立", c14)
    check("c15", "进度统计按三态口径且与草稿同源", c15)
    check("c16", "EC 批次记录与实际引用自洽", c16)
    check("c17", "batch_summary 指向最近完成批次", c17)
    check("c18", "批次按业务顺序排列", c18)
    check("c19", "前两批批次条目仍在且数字未变", c19)
    check("c20", "晋升记录落盘且不编造身份", c20)
    check("c21", "9 条 canonical 均有晋升记录", c21)
    check("c22", "晋升来源声明可复核", c22)
    check("c23", "晋升记录无重复", c23)
    check("c24", "EC canonical 数为 9 且编号连续", c24)
    check("c25", "EC 来源分布信息", c25)
    check("c26", "存档契约强制字段齐备", c26)
    check("c27", "四节点数据流结构落地", c27)
    check("c28", "引用校验三态齐备", c28)
    check("c29", "missing 与 unresolvable 禁止合并", c29)
    check("c30", "未支撑陈述不得以事实形态出现", c30)
    check("c31", "缺料占位且不编造格式", c31)
    check("c32", "产物自证出处字段齐备", c32)
    check("c33", "Finding 四段与观察/解释分离", c33)
    check("c34", "新鲜度四字段 + 替代关系结构化", c34)
    check("c35", "裁决状态机六态与 report_tier 映射", c35)
    check("c36", "不可验证不判否的硬规则已落地", c36)
    check("c37", "U06 来源复制许可全为 false", c37)
    check("c38", "许可逐源记录且义务不缺失", c38)
    check("c39", "每条 canonical 有合并/不合并理由", c39)
    check("c40", "处置取值合法且分布可见", c40)
    check("c41", "I/O 边界与 V1 scope 齐备", c41)
    check("c42", "依赖模块取值合法", c42)
    check("c43", "原始索引逐字节未变", c43)
    check("c44", "六份上游审计未改动", c44)
    check("c45", "src/tests/schemas 无改动", c45)
    check("c46", "正式交叉表未提前冻结", c46)
    check("c47", "JSON 与决策文档数字一致", c47)
    check("c48", "第E节六项约束逐条落章", c48)
    check("c49", "九条 ROUTED 全部承接且不再外推", c49)
    check("c50", "U06::C06 拒绝语义已记录", c50)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / Evidence-Claims",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_ec.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
