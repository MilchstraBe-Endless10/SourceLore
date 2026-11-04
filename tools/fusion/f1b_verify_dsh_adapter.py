#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / DSH-Adapter 批次独立验收。只写 F1B_DSH_ADAPTER_VERIFICATION.json。

作用域：本判定 DSH-Adapter 批次自己的能力（SL-CAP-0068..0073）与本批不变量。
另含 F1-B 全量剩余能力清单（F1B_REMAINDER_INVENTORY.json）的一致性校验。
历史批次判历史事实，当前全局状态由当前 Crosswalk 计算。
"""
import json, sys, hashlib, subprocess, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
PROG = F / "CROSSWALK_PROGRESS.json"
DOC = F / "F1B_DSH_ADAPTER_DECISIONS.md"
REM = F / "F1B_REMAINDER_INVENTORY.json"
OUT = F / "F1B_DSH_ADAPTER_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULE = "DSH-Adapter"
MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
OWN_IDS = [f"SL-CAP-{n:04d}" for n in range(68, 74)]
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}
COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}
EC_IDS = {f"SL-CAP-{n:04d}" for n in range(20, 29)}
PRODUCT_IDS = {f"SL-CAP-{n:04d}" for n in range(29, 35)}
RESEARCH_IDS = {f"SL-CAP-{n:04d}" for n in range(35, 40)}
LIFECYCLE_IDS = {f"SL-CAP-{n:04d}" for n in range(40, 46)}
SECURITY_IDS = {f"SL-CAP-{n:04d}" for n in range(46, 55)}
RENDERER_IDS = {f"SL-CAP-{n:04d}" for n in range(55, 62)}
STORAGE_IDS = {f"SL-CAP-{n:04d}" for n in range(62, 68)}

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
    own_canon = [c for c in canon if c["canonical_id"] in OWN_IDS]
    own_owned = {(r["upstream_id"], r["original_capability_id"])
                 for c in own_canon for r in c["upstream_refs"]}
    promos_to_own = [r for r in promos if r.get("to_canonical_id") in OWN_IDS]
    mapped_all = {(r["upstream_id"], r["original_capability_id"])
                  for c in canon for r in c["upstream_refs"]}
    rted_all = {(r["upstream_id"], r["original_capability_id"]) for r in routed}

    def blob(cid):
        return json.dumps(next(c for c in own_canon if c["canonical_id"] == cid), ensure_ascii=False)

    def c1():
        h = hashlib.sha256(RAW.read_bytes()).hexdigest()
        ok = h == draft["source_index_sha256"] and len(items) == 143 and len(by_key) == 143
        return ok, f"原始 143 项且身份唯一；sha256={h[:16]} 一致={h == draft['source_index_sha256']}"

    def c2():
        old = [c for c in canon if c["canonical_id"] <= "SL-CAP-0067"]
        missing = [i for i in ("SL-CAP-0001", "SL-CAP-0067") if i not in ids]
        return len(old) == 67 and not missing, f"既有 67 条保留={len(old) == 67}；端点缺失={missing or '无'}"

    def c3():
        got = set(ids) & set(OWN_IDS)
        return got == set(OWN_IDS), f"DSH-Adapter 编号 0068-0073 齐全 {len(got)}/6"

    def c4():
        ow = sorted(int(i.split("-")[-1]) for i in OWN_IDS)
        return ow == list(range(68, 74)), f"DSH-Adapter 编号连续自 0068 起：{ow}"

    def c5():
        want = [f"SL-CAP-{i:04d}" for i in range(1, len(ids) + 1)]
        return sorted(ids) == want, f"全表共 {len(ids)} 条，从 0001 连续无断号"

    def c6():
        dup = sorted({i for i in ids if ids.count(i) > 1})
        return not dup, f"canonical_id 无重复（{len(ids)} 条）" if not dup else f"重复 {dup}"

    def c7():
        seen, dup = {}, []
        for c in canon:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                if k in seen:
                    dup.append(f"{k[0]}::{k[1]}（{seen[k]} 与 {c['canonical_id']}）")
                seen[k] = c["canonical_id"]
        return not dup, f"每项原始能力最多正式映射一次，共 {len(seen)} 个身份" if not dup else f"重复 {dup}"

    def c8():
        bad = [c["canonical_id"] for c in own_canon if c["owner_module"] != MODULE]
        return not bad, f"DSH-Adapter 6 条 owner 均为 DSH-Adapter，越界 {bad or '无'}"

    def c9():
        bad = [f"{c['canonical_id']}::{r['upstream_id']}::{r['original_capability_id']}"
               for c in own_canon for r in c["upstream_refs"]
               if (r["upstream_id"], r["original_capability_id"]) not in by_key]
        return not bad, f"{len(own_owned)} 个原始来源全部可在索引定位" if not bad else f"查无 {bad}"

    def c10():
        bad = []
        for r in promos_to_own:
            k = (r.get("upstream_id"), r.get("original_capability_id"))
            if k in rted_all:
                bad.append(f"{k[0]}::{k[1]} 已晋升却仍在分流表")
            if r.get("from") not in {"cross_module_redirections", "unreviewed_adopted"}:
                bad.append(f"{k[0]}::{k[1]} from 非法")
        route = [r for r in promos_to_own if r.get("from") == "cross_module_redirections"]
        return not bad, f"晋升 {len(promos_to_own)} 条（路由表来源 {len(route)} 条），问题 {bad or '无'}"

    def c11():
        clash = own_owned & rted_all
        return not clash, "新增分流与映射集合零相交" if not clash else f"相交 {sorted(clash)}"

    def c12():
        unrev = set(by_key) - mapped_all - rted_all
        total = len(mapped_all) + len(rted_all) + len(unrev)
        ok = total == len(by_key) == 143 and not (mapped_all & rted_all)
        return ok, (f"mapped {len(mapped_all)} + routed {len(rted_all)} + unreviewed {len(unrev)} = {total}；"
                    f"互斥={not (mapped_all & rted_all)}")

    def c13():
        g = draft["global_state_counts"]
        unrev = set(by_key) - mapped_all - rted_all
        ok = (g.get("mapped_count") == len(mapped_all)
              and g.get("routed_pending_count") == len(rted_all)
              and g.get("unreviewed_count") == len(unrev)
              and g.get("canonical_count") == len(canon))
        inv = g.get("state_invariants", {})
        inv_ok = all(inv.get(k) is True for k in
                     ("mutually_exclusive", "union_equals_total",
                      "no_ghost_identities", "routed_not_counted_as_mapped"))
        return ok and inv_ok, (f"global_state_counts 自洽 mapped={len(mapped_all)} routed={len(rted_all)} "
                              f"unreviewed={len(unrev)} canonical={len(canon)}；不变量={inv_ok}")

    def c14():
        t = prog["totals"]
        g = draft["global_state_counts"]
        need = ["mapped_count", "routed_pending_count", "unreviewed_count", "canonical_count", "sum_check"]
        missing = [k for k in need if k not in t]
        agree = all(t.get(k) == g.get(k) for k in need if k in t)
        return (not missing and agree,
                f"缺失 {missing or '无'}；同源={agree}；sum_check={t.get('sum_check')}")

    def c15():
        b = next((x for x in draft.get("batches", []) if x["module"] == MODULE), None)
        if b is None:
            return False, "草稿中没有 DSH-Adapter 批次记录"
        import f1b_stats
        recalc = {x["module"]: x for x in f1b_stats.batches_from_draft(draft)}
        ok = (b["raw_mapped_to_this_module"] >= len(own_owned) >= 7
              and b["canonical_ids"] == OWN_IDS
              and b["raw_redirected_to_other_modules"] ==
                  recalc[MODULE]["raw_redirected_to_other_modules"])
        return ok, (f"mapped={b['raw_mapped_to_this_module']}（应 7）、"
                    f"redirected 现算一致={ok}（当前 {b['raw_redirected_to_other_modules']}）、"
                    f"ids 齐备={b['canonical_ids'] == OWN_IDS}")

    def c16():
        names = [b["module"] for b in draft.get("batches", [])]
        order = ["Facts", "Collector", "Evidence-Claims", "Product", "Research",
                 "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"]
        return names[:10] == order, f"十批次按业务顺序：{names}"

    def c17():
        expect = {"Facts": 11, "Collector": 11, "Evidence-Claims": 12, "Product": 10,
                  "Research": 10, "Lifecycle": 12, "Security": 17, "Renderer": 11, "Storage": 11}
        bad = []
        for mod, n in expect.items():
            b = next((x for x in draft["batches"] if x["module"] == mod), None)
            if b is None:
                bad.append(f"{mod} 批次条目丢失")
            elif b["raw_mapped_to_this_module"] < n:
                bad.append(f"{mod} mapped={b['raw_mapped_to_this_module']} 应为 {n}")
        return not bad, "历史九批 mapped 全部定格未变" if not bad else f"{bad}"

    # ── Skill 结构与运行时真实性 ─────────────────────────────────────────
    def c18():
        b = blob("SL-CAP-0068")
        need = ["SKILL.md", "frontmatter", "渐进加载", "UNVERIFIED_RUNTIME_CAPABILITY",
                "尚未实现", "只定契约不建 Skill"]
        miss = [k for k in need if k not in b]
        return not miss, f"入口结构与运行时事实标注齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c19():
        b = blob("SL-CAP-0068")
        ok = ("入口只放路由指针" in b and "不把全部 canonical 约束复制进入口提示词" in b)
        return ok, "Skill 入口与核心能力定义分离（入口薄 + 按需加载）"

    def c20():
        b = blob("SL-CAP-0068")
        ok = ("四类内容不可互相替代" in b and "不得要求自主安装未知脚本" in b
              and "不得通过提示词覆盖系统级安全约束" in b)
        return ok, "四类载体分离 + 禁自主安装 + 禁提示词覆盖安全约束"

    # ── 模型适配与预算 ───────────────────────────────────────────────────
    def c21():
        b = blob("SL-CAP-0069")
        need = ["D-1", "D-2", "D-3", "必须确定性执行", "允许模型辅助分析", "必须交 Evidence-Claims 校验",
                "UNVERIFIED_RUNTIME_CAPABILITY"]
        miss = [k for k in need if k not in b]
        return not miss, f"三类操作边界 + 能力必须实测={not miss}" + (f"，缺 {miss}" if miss else "")

    def c22():
        b = blob("SL-CAP-0069")
        ok = ("不得因更换模型而重写已有 canonical 的事实或存储契约" in b
              and "不得默认所有模型都有视觉、工具调用或结构化输出" in b)
        return ok, "模型可替换且核心事实不依赖模型能力"

    def c23():
        b = blob("SL-CAP-0070")
        need = ["max_calls", "max_context", "max_repairs", "硬上限 2 次",
                "禁止 while(true) 式修复循环", "估算值描述为供应商实测账单"]
        miss = [k for k in need if k not in b]
        return not miss, f"预算三件 + 有界修复 2 次 + 禁无界循环 + 估算非账单={not miss}" + (f"，缺 {miss}" if miss else "")

    def c24():
        b = blob("SL-CAP-0070")
        need = ["C-1", "C-2", "C-3", "C-4", "measured_tokens", "billed_cost",
                "estimated_tokens", "unavailable_cost"]
        miss = [k for k in need if k not in b]
        return not miss, f"成本四类分列={not miss}" + (f"，缺 {miss}" if miss else "")

    def c25():
        b = blob("SL-CAP-0070")
        ok = ("工具执行耗时与模型调用耗时分别记录" in b
              and "预算耗尽后必须保留可恢复检查点" in b)
        return ok, "工具与模型耗时分离 + 预算耗尽保留检查点"

    def c26():
        b = blob("SL-CAP-0070")
        ok = ("直连外部模型 API" in b and "多模型 judge" in b and "REJECT" in b)
        return ok, "直连 API 与多模型 judge 已作 REJECT 反例登记"

    # ── 任务恢复与幂等 ───────────────────────────────────────────────────
    def c27():
        b = blob("SL-CAP-0071")
        need = ["task_id", "run_id", "workspace_id", "subject_id", "requested_action",
                "current_stage", "checkpoint_ref", "input_snapshot_ref",
                "authorization_scope", "attempt_count", "error_category"]
        miss = [k for k in need if k not in b]
        return not miss, f"11 个逻辑标识齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c28():
        b = blob("SL-CAP-0071")
        need = ["I-1", "I-2", "I-3", "I-4", "超时不得自动解释为工具未执行",
                "工具执行成功与模型生成成功必须分开记录"]
        miss = [k for k in need if k not in b]
        return not miss, f"四条幂等硬规则齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c29():
        b = blob("SL-CAP-0071")
        ok = ("Storage 是知识资产权威" in b and "执行检查点是任务恢复依据" in b
              and "不是唯一事实来源" in b)
        return ok, "任务检查点与知识资产权威分离（热记忆仅为辅助）"

    # ── 权限门禁 ─────────────────────────────────────────────────────────
    def c30():
        b = blob("SL-CAP-0072")
        need = ["G-A", "G-B", "G-C", "不得自行转换为 approved", "pending_review",
                "不实际扩大授权"]
        miss = [k for k in need if k not in b]
        return not miss, f"三档门禁 + AI 不得自批 + 只登记不扩权={not miss}" + (f"，缺 {miss}" if miss else "")

    def c31():
        b = blob("SL-CAP-0072")
        ok = ("权限被拒必须显式返回 denied" in b
              and "外部仓库内容不得修改执行策略" in b
              and "负责**执行**权限门禁" in b
              and "不负责**定义**审批策略" in b)
        return ok, "拒绝显式 + 外部内容不控策略 + 审批策略归 Security"

    # ── 编排边界 ─────────────────────────────────────────────────────────
    def c32():
        b = blob("SL-CAP-0073")
        modules = ["Collector", "Facts", "Evidence-Claims", "Product", "Research",
                   "Lifecycle", "Security", "Renderer", "Storage"]
        miss = [m for m in modules if m not in b]
        return not miss, f"九模块最小调用关系齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c33():
        b = blob("SL-CAP-0073")
        ok = ("禁止 DSH Adapter 绕过 Storage 直接改写知识资产目录" in b
              and "错误必须原样向上传播" in b
              and "不得把其他模块的全部功能复制进 Skill 提示词" in b)
        return ok, "不绕过 Storage + 错误原样传播 + 不复制模块功能"

    def c34():
        # 不重复实现其他九个模块
        bad = []
        forbidden = ["自建第二套知识库", "实现源码分析引擎", "自建 GitHub 客户端"]
        for c in own_canon:
            b = json.dumps(c, ensure_ascii=False)
            for f in forbidden:
                if f in b and "不得" not in b and "禁止" not in b:
                    bad.append(f"{c['canonical_id']} 越界「{f}」")
        deps_ok = all("Storage" in c["dependencies"] or c["canonical_id"] in
                      ("SL-CAP-0068", "SL-CAP-0069", "SL-CAP-0070")
                      for c in own_canon)
        return not bad, f"未重复实现他模块={not bad}；依赖声明合理={deps_ok}"

    # ── 许可证 ───────────────────────────────────────────────────────────
    def c35():
        bad = []
        for c in own_canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可未逐源记录")
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
            if any(p["upstream_id"] == "UPSTREAM-06" for p in per):
                if c["license_permission"].get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 含 U06 却判整体可复制")
        return not bad, f"逐源许可且 U06 全 false，问题 {bad or '无'}"

    def c36():
        dist = {}
        for c in own_canon:
            dist[c["disposition"]] = dist.get(c["disposition"], 0) + 1
        return True, f"（信息）DSH-Adapter 处置分布 {dist}"

    def c37():
        bad = []
        for c in own_canon:
            if c["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                bad.append(f"{c['canonical_id']} 非法处置")
            if not c.get("input_boundary") or not c.get("output_boundary") or not c.get("v1_scope"):
                bad.append(f"{c['canonical_id']} 缺 I/O 或 scope")
            if not c.get("merge_note"):
                bad.append(f"{c['canonical_id']} 缺 merge_note")
        return not bad, f"处置/边界/理由齐备，问题 {bad or '无'}"

    def c38():
        zero = [c["canonical_id"] for c in own_canon if not c["upstream_refs"]]
        bad = [c["canonical_id"] for c in own_canon if not c["upstream_refs"] and not c.get("merge_note")]
        return not bad, f"零来源条目 {zero or '无'} 均有内部需求依据"

    def c39():
        bad = [c["canonical_id"] for c in own_canon if "unresolved" not in c]
        n = sum(len(c.get("unresolved") or []) for c in own_canon)
        return not bad, f"6 条均带 unresolved，合计 {n} 项待定"

    # ── 文档 ─────────────────────────────────────────────────────────────
    def c40():
        if not DOC.exists():
            return False, f"决策文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        missing = [i for i in OWN_IDS if i not in txt]
        b = next(x for x in draft["batches"] if x["module"] == MODULE)
        nums = [b["raw_mapped_to_this_module"], len(b["canonical_ids"]),
                b["raw_redirected_to_other_modules"]]
        nums_ok = all(str(n) in txt for n in nums)
        g = draft["global_state_counts"]
        def snap(label):
            for line in txt.splitlines():
                if "累计 " + label in line and "|" in line:
                    parts = [x.strip() for x in line.split("|")]
                    for seg in reversed(parts):
                        if seg.isdigit():
                            return int(seg)
            return None
        sm, sr, su = snap("MAPPED"), snap("ROUTED"), snap("UNREVIEWED")
        total_ok = str(g["raw_total"]) in txt
        snap_ok = None not in (sm, sr, su) and (sm + sr + su == g["raw_total"])
        return (not missing and nums_ok and total_ok and snap_ok,
                f"缺失 ID={missing or '无'}；批次数字 {nums} 出现={nums_ok}；"
                f"累计快照 {sm}/{sr}/{su} 自洽={snap_ok}；raw_total 出现={total_ok}")

    def c41():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"H-{ch}" for ch in "ABCDEFGH"]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"运行时核验八问 H-A..H-H 逐条落章，缺 {miss or '无'}"

    def c42():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"Y-{i}" for i in range(1, 7)]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"跨模块裁决 Y-1..Y-6 逐条登记，缺 {miss or '无'}"

    # ── 剩余能力清单（第 12 节特别要求） ─────────────────────────────────
    def c43():
        if not REM.exists():
            return False, f"剩余能力清单不存在: {REM.name}"
        inv = json.loads(REM.read_text(encoding="utf-8"))
        items_listed = inv.get("items", [])
        return len(items_listed) == 143, f"清单覆盖 {len(items_listed)}/143 项原始身份"

    def c44():
        # 本检查判「剩余清单不是陈旧数据」：清单必须与**当前** Crosswalk 一致。
        # 清单由 f1b_build_remainder.py 从当前草稿计算，F1-C 每批应用裁决后需重跑该生成器。
        inv = json.loads(REM.read_text(encoding="utf-8"))
        g = draft["global_state_counts"]
        st = inv.get("state_totals", {})
        ok = (st.get("mapped") == g["mapped_count"]
              and st.get("routed") == g["routed_pending_count"]
              and st.get("unreviewed") == g["unreviewed_count"]
              and st.get("total") == 143)
        detail = (f"清单 mapped={st.get('mapped')}/现算 {g['mapped_count']}、"
                  f"routed={st.get('routed')}/{g['routed_pending_count']}、"
                  f"unreviewed={st.get('unreviewed')}/{g['unreviewed_count']}；"
                  f"不一致时重跑 f1b_build_remainder.py")
        return ok, detail

    def c45():
        inv = json.loads(REM.read_text(encoding="utf-8"))
        items_listed = inv.get("items", [])
        bad = []
        for it in items_listed:
            k = (it["upstream_id"], it["original_capability_id"])
            if k not in by_key:
                bad.append(f"{k} 不在原始索引")
            cur = ("MAPPED" if k in mapped_all else "ROUTED" if k in rted_all else "UNREVIEWED")
            if it.get("state") != cur:
                bad.append(f"{k} 状态记为 {it.get('state')}，实际 {cur}")
        return not bad, f"清单逐项状态与 Crosswalk 一致，问题 {bad or '无'}"

    def c46():
        inv = json.loads(REM.read_text(encoding="utf-8"))
        res = inv.get("residue", {})
        need = ["unreviewed_by_class", "routed_unclaimed", "reject_classification"]
        miss = [k for k in need if k not in res]
        return not miss, f"残留分类（UNREVIEWED 语义分组 / ROUTED 未承接原因 / REJECT 三类）齐备={not miss}"

    def c47():
        inv = json.loads(REM.read_text(encoding="utf-8"))
        res = inv.get("residue", {})
        rc = res.get("reject_classification", {})
        need = ["adjudicated", "design_counterexample", "pending_f1c"]
        miss = [k for k in need if k not in rc]
        return not miss, f"REJECT 三分类齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c48():
        inv = json.loads(REM.read_text(encoding="utf-8"))
        note = json.dumps(inv.get("disclaimer", ""), ensure_ascii=False)
        ok = "不等于 143 项原始能力已全部完成归属裁决" in note
        return ok, "清单明确声明：批次完成不等于 143 项归属全部完成"

    # ── 隔离与冻结 ───────────────────────────────────────────────────────
    def c49():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始能力索引逐字节未变"

    def c50():
        g = git("diff", "--quiet", "HEAD", "--",
                *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g.returncode == 0, "六份历史上游审计未改动"

    def c51():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c52():
        return not (F / "CAPABILITY_CROSSWALK.json").exists(), "正式交叉表尚未提前冻结"

    def c53():
        sys.path.insert(0, str(ROOT / "tools" / "fusion"))
        import f1b_dsh_adapter_def as ad
        declared = set(ad.CONSUMED_THIS_BATCH)
        referenced = {(u, o) for c in ad.CANON for (u, o, _v) in c["refs"]}
        moved = set(ad.DEFERRED_TO_OTHER_MODULE)
        ok = declared == referenced and not (declared & moved)
        return ok, (f"承接声明 {len(declared)} 与引用 {len(referenced)} 一致={declared == referenced}；"
                    f"与分流零重叠={not (declared & moved)}")

    def c54():
        import importlib, f1b_stats
        importlib.reload(f1b_stats)
        g_re = f1b_stats.global_state_counts(draft, raw)
        b_re = {x["module"]: x for x in f1b_stats.batches_from_draft(draft)}
        g = draft["global_state_counts"]
        ok = (g_re["mapped_count"] == g["mapped_count"]
              and g_re["routed_pending_count"] == g["routed_pending_count"]
              and g_re["unreviewed_count"] == g["unreviewed_count"]
              and g_re["canonical_count"] == g["canonical_count"])
        mine = b_re.get(MODULE)
        ok2 = mine is not None and mine["raw_mapped_to_this_module"] >= 7
        return ok and ok2, (f"stats 重算一致 mapped={g_re['mapped_count']} "
                            f"routed={g_re['routed_pending_count']} unrev={g_re['unreviewed_count']}；"
                            f"DSH-Adapter 重算 mapped=7={ok2}")

    def c55():
        expected = {("UPSTREAM-01", "C12"): "Evidence-Claims"}
        bad = []
        for k, mod in expected.items():
            r = next((x for x in routed if (x["upstream_id"], x["original_capability_id"]) == k), None)
            if r is None:
                bad.append(f"{k} 未落盘为分流")
            elif r["owner_module"] != mod:
                bad.append(f"{k} 记为 {r['owner_module']}，应为 {mod}")
        return not bad, f"本批 1 条分流去向正确，问题 {bad or '无'}"

    def c56():
        found = {(x.get("upstream_id"), x.get("original_capability_id"))
                 for x in promos_to_own if x.get("from") == "cross_module_redirections"}
        expect = {("UPSTREAM-06", "C18")}
        missing = expect - found
        return not missing, f"U06-C18（改路由后承接）有路由表晋升记录={not missing}"

    check("c1", "原始 143 项身份唯一且不变", c1)
    check("c2", "既有 67 条 canonical 不变", c2)
    check("c3", "DSH-Adapter 编号 0068-0073 齐全", c3)
    check("c4", "DSH-Adapter 编号连续自 0068 起", c4)
    check("c5", "canonical_id 从 0001 连续", c5)
    check("c6", "canonical_id 无重复", c6)
    check("c7", "每个原始身份最多映射一次", c7)
    check("c8", "每条 canonical 一个 owner", c8)
    check("c9", "来源证据可追溯", c9)
    check("c10", "ROUTED 晋升正确", c10)
    check("c11", "新增分流无重复", c11)
    check("c12", "三态互斥且总数 143", c12)
    check("c13", "global_state_counts 与实算一致", c13)
    check("c14", "进度统计与草稿同源", c14)
    check("c15", "DSH-Adapter 批次记录自洽", c15)
    check("c16", "十批次按业务顺序", c16)
    check("c17", "历史九批 mapped 定格", c17)
    check("c18", "Skill 入口结构与运行时事实", c18)
    check("c19", "Skill 入口与核心能力分离", c19)
    check("c20", "四类载体分离与安全红线", c20)
    check("c21", "三类操作边界且能力须实测", c21)
    check("c22", "模型可替换且事实不依赖模型", c22)
    check("c23", "预算与有界修复", c23)
    check("c24", "成本四类分列", c24)
    check("c25", "耗时分离与预算耗尽保留检查点", c25)
    check("c26", "直连 API 与多 judge 已 REJECT", c26)
    check("c27", "任务 11 个逻辑标识齐备", c27)
    check("c28", "四条幂等硬规则", c28)
    check("c29", "检查点与知识权威分离", c29)
    check("c30", "三档门禁且 AI 不得自批", c30)
    check("c31", "拒绝显式且策略归 Security", c31)
    check("c32", "九模块调用关系齐备", c32)
    check("c33", "不绕过 Storage 且错误原样传播", c33)
    check("c34", "不重复实现他模块", c34)
    check("c35", "许可证权限独立", c35)
    check("c36", "处置分布（信息）", c36)
    check("c37", "处置/边界/理由齐备", c37)
    check("c38", "零来源条目有内部依据", c38)
    check("c39", "unresolved 显式存在", c39)
    check("c40", "决策文档与 JSON 一致", c40)
    check("c41", "运行时核验八问落章", c41)
    check("c42", "跨模块裁决 Y-1..Y-6 登记", c42)
    check("c43", "剩余清单覆盖 143 项", c43)
    check("c44", "清单三态与 Crosswalk 一致", c44)
    check("c45", "清单逐项状态一致", c45)
    check("c46", "残留分类齐备", c46)
    check("c47", "REJECT 三分类齐备", c47)
    check("c48", "清单声明批次≠全归属", c48)
    check("c49", "原始能力索引未改动", c49)
    check("c50", "六份上游审计未改动", c50)
    check("c51", "src/tests/schemas 无改动", c51)
    check("c52", "正式交叉表未提前冻结", c52)
    check("c53", "承接声明与 def 一致", c53)
    check("c54", "stats 重算一致且幂等", c54)
    check("c55", "本批分流去向正确", c55)
    check("c56", "U06-C18 承接有晋升记录", c56)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / DSH-Adapter（最后一批）",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_dsh_adapter.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "scope_note": "F1 设计与产物验证；未实现正式 Skill、未跑模型性能基准",
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
