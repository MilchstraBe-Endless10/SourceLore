#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Storage 批次独立验收。只写 F1B_STORAGE_VERIFICATION.json。

作用域：本验证器只判定 Storage 批次自己的能力（SL-CAP-0062..0067）与本批不变量，
不替前八个批次的条目下结论（各自验证器负责）。
历史批次判历史事实，当前全局状态由当前 Crosswalk 计算。

注意：这是 F1 的设计与产物验证，不宣称真实数据库的事务与并发性能已被测试。
"""
import json, sys, hashlib, subprocess, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
PROG = F / "CROSSWALK_PROGRESS.json"
DOC = F / "F1B_STORAGE_DECISIONS.md"
OUT = F / "F1B_STORAGE_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULE = "Storage"
MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
OWN_IDS = [f"SL-CAP-{n:04d}" for n in range(62, 68)]
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}
COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}
EC_IDS = {f"SL-CAP-{n:04d}" for n in range(20, 29)}
PRODUCT_IDS = {f"SL-CAP-{n:04d}" for n in range(29, 35)}
RESEARCH_IDS = {f"SL-CAP-{n:04d}" for n in range(35, 40)}
LIFECYCLE_IDS = {f"SL-CAP-{n:04d}" for n in range(40, 46)}
SECURITY_IDS = {f"SL-CAP-{n:04d}" for n in range(46, 55)}
RENDERER_IDS = {f"SL-CAP-{n:04d}" for n in range(55, 62)}

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
        old = [c for c in canon if c["canonical_id"] <= "SL-CAP-0061"]
        missing = [i for i in ("SL-CAP-0001", "SL-CAP-0061") if i not in ids]
        return len(old) == 61 and not missing, f"既有 61 条保留={len(old) == 61}；端点缺失={missing or '无'}"

    def c3():
        got = set(ids) & set(OWN_IDS)
        return got == set(OWN_IDS), f"Storage 编号 0062-0067 齐全 {len(got)}/6"

    def c4():
        ow = sorted(int(i.split("-")[-1]) for i in OWN_IDS)
        return ow == list(range(62, 68)), f"Storage 编号连续自 0062 起：{ow}"

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
        return not bad, f"Storage 6 条 owner 均为 Storage，越界 {bad or '无'}"

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
        stale = [k for k in ("raw_assigned", "raw_pending", "canonical_total") if k in t]
        agree = all(t.get(k) == g.get(k) for k in need if k in t)
        return (not missing and not stale and agree,
                f"缺失 {missing or '无'}；旧口径 {stale or '无'}；同源={agree}；sum_check={t.get('sum_check')}")

    def c15():
        b = next((x for x in draft.get("batches", []) if x["module"] == MODULE), None)
        if b is None:
            return False, "草稿中没有 Storage 批次记录"
        import f1b_stats
        recalc = {x["module"]: x for x in f1b_stats.batches_from_draft(draft)}
        ok = (b["raw_mapped_to_this_module"] == len(own_owned) == 11
              and b["canonical_ids"] == OWN_IDS
              and b["raw_redirected_to_other_modules"] ==
                  recalc[MODULE]["raw_redirected_to_other_modules"])
        return ok, (f"mapped={b['raw_mapped_to_this_module']}（应 11）、"
                    f"redirected 现算一致={ok}（当前 {b['raw_redirected_to_other_modules']}）、"
                    f"ids 齐备={b['canonical_ids'] == OWN_IDS}")

    def c16():
        names = [b["module"] for b in draft.get("batches", [])]
        order = ["Facts", "Collector", "Evidence-Claims", "Product", "Research",
                 "Lifecycle", "Security", "Renderer", "Storage"]
        return names[:9] == order, f"批次按业务顺序：{names}"

    def c17():
        expect = {"Facts": 11, "Collector": 11, "Evidence-Claims": 12, "Product": 10,
                  "Research": 10, "Lifecycle": 12, "Security": 17, "Renderer": 11}
        bad = []
        for mod, n in expect.items():
            b = next((x for x in draft["batches"] if x["module"] == mod), None)
            if b is None:
                bad.append(f"{mod} 批次条目丢失")
            elif b["raw_mapped_to_this_module"] != n:
                bad.append(f"{mod} mapped={b['raw_mapped_to_this_module']} 应为 {n}")
        return not bad, "历史八批 mapped 全部定格未变" if not bad else f"{bad}"

    # ── 四层资产模型（门禁 9、10、11） ───────────────────────────────────
    def c18():
        b = blob("SL-CAP-0062")
        need = ["A 层", "B 层", "C 层", "D 层", "只允许追加", "必须能从 A+B 层完整重建",
                "禁止作为唯一权威来源", "不得同时存在两个可独立修改的权威副本"]
        miss = [k for k in need if k not in b]
        return not miss, f"四层模型与单一权威契约齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c19():
        b = blob("SL-CAP-0062")
        ok = ("删除后权威数据不受影响" in b and "重建后查询结果等价" in b)
        return ok, "派生索引可整体删除并重建，结果等价"

    def c20():
        b = blob("SL-CAP-0062")
        ok = ("更新当前指针不得破坏 A 层任何记录" in b and "D 层不得回写 A/B 层" in b)
        return ok, "当前指针变更不覆盖历史；展示产物不回写权威层"

    # ── 身份与版本（门禁 15） ────────────────────────────────────────────
    def c21():
        b = blob("SL-CAP-0063")
        need = ["repository_id", "subject_id", "commit_sha", "root_tree_sha",
                "artifact_version", "content_hash", "不得互相替代"]
        miss = [k for k in need if k not in b]
        return not miss, f"六标识分列且不得互替={not miss}" + (f"，缺 {miss}" if miss else "")

    def c22():
        b = blob("SL-CAP-0063")
        ok = ("不得用仓库 URL、文件路径或 Commit SHA 作为 Subject 的永久唯一身份" in b
              and "不得自动等同于所有知识 Subject 的唯一身份" in b)
        return ok, "Subject 身份不与仓库 URL / Commit 混淆"

    # ── 写入与恢复（门禁 12、13） ────────────────────────────────────────
    def c23():
        b = blob("SL-CAP-0064")
        need = ["W-1", "W-2", "W-3", "W-4", "W-5", "临时", "expected_version", "静默覆盖"]
        miss = [k for k in need if k not in b]
        return not miss, f"写入五步契约齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c24():
        b = blob("SL-CAP-0064")
        ok = ("并发冲突必须明确返回" in b and "不得吞掉并降级为空结果" in b)
        return ok, "并发冲突显式返回，不静默覆盖也不伪装空结果"

    def c25():
        b = blob("SL-CAP-0064")
        ok = ("多文件重命名不得宣称跨文件原子事务" in b and "如实声明原子性范围" in b)
        return ok, "原子性范围如实声明，不夸大跨文件原子性"

    def c26():
        b = blob("SL-CAP-0064")
        ok = ("崩溃恢复后必须能判断哪些写入已提交" in b and "按 content_hash 幂等" in b)
        return ok, "崩溃恢复可判定 + 不可变对象按哈希幂等"

    # ── 查询（门禁 14） ──────────────────────────────────────────────────
    def c27():
        b = blob("SL-CAP-0065")
        need = ["Q-1", "Q-2", "Q-3", "source_snapshot", "retrieved_from_layer"]
        miss = [k for k in need if k not in b]
        return not miss, f"三类查询 + 结果来源与层标识={not miss}" + (f"，缺 {miss}" if miss else "")

    def c28():
        b = blob("SL-CAP-0065")
        ok = ("检索命中不能自动成为已验证的新 Claim" in b
              and "不意味着被查仓库的实时状态" in b)
        return ok, "检索命中不等于实时状态，不自动成为已验证 Claim"

    def c29():
        b = blob("SL-CAP-0065")
        ok = ("权限拒绝必须显式返回 denied" in b and "不得伪装成空结果" in b)
        return ok, "权限拒绝不伪装成无数据"

    def c30():
        b = blob("SL-CAP-0065")
        ok = ("不得在没有必要时引入向量数据库或图数据库" in b)
        return ok, "不预设向量/图数据库"

    # ── 多仓库关系（门禁 16） ────────────────────────────────────────────
    def c31():
        b = blob("SL-CAP-0066")
        need = ["R-1", "R-2", "R-3", "R-4", "R-5", "relation_kind", "evidence_refs", "verification_status"]
        miss = [k for k in need if k not in b]
        return not miss, f"五类关系分离 + 三件套字段={not miss}" + (f"，缺 {miss}" if miss else "")

    def c32():
        b = blob("SL-CAP-0066")
        ok = ("不得因为两个仓库名称相同、依赖同名包、或作者相同" in b
              and "跨仓库影响推断不属 Storage" in b)
        return ok, "不凭空推断影响关系；影响判定不归 Storage"

    # ── 根目录隔离 ────────────────────────────────────────────────────────
    def c33():
        b = blob("SL-CAP-0067")
        need = ["P-1", "P-2", "P-3", "P-4", "路径穿越", "符号链接", "知识资产根目录不得位于被分析仓库内部"]
        miss = [k for k in need if k not in b]
        return not miss, f"四层隔离与路径安全={not miss}" + (f"，缺 {miss}" if miss else "")

    def c34():
        b = blob("SL-CAP-0067")
        ok = ("自动扫描结果永不写回被分析仓库" in b
              and "不得通过任何方式访问本地私有文件或环境变量" in b)
        return ok, "扫描结果不回写被分析仓库；不可信内容不得触及私有文件"

    # ── 许可证与处置 ──────────────────────────────────────────────────────
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
        # 两条 REJECT 作为反例登记：C25/C26 须在 0067 的 refs 里 verdict=REJECT
        b = blob("SL-CAP-0067")
        ok = ("绝不写在仓库内" in b and "明确拒绝" in b)
        zero_owner = next((c for c in own_canon if c["canonical_id"] == "SL-CAP-0063"), None)
        ok2 = zero_owner is not None and not zero_owner["upstream_refs"] and zero_owner.get("merge_note")
        return (ok and ok2), f"REJECT 作反例登记={ok}；零来源条目有内部需求依据={ok2}"

    def c37():
        dist = {}
        for c in own_canon:
            dist[c["disposition"]] = dist.get(c["disposition"], 0) + 1
        return True, f"（信息）Storage 处置分布 {dist}"

    # ── 结构完整性 ────────────────────────────────────────────────────────
    def c38():
        bad = []
        for c in own_canon:
            if c["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                bad.append(f"{c['canonical_id']} 非法处置")
            if not c.get("input_boundary") or not c.get("output_boundary") or not c.get("v1_scope"):
                bad.append(f"{c['canonical_id']} 缺 I/O 或 scope")
            if not c.get("merge_note"):
                bad.append(f"{c['canonical_id']} 缺 merge_note")
        return not bad, f"处置/边界/理由齐备，问题 {bad or '无'}"

    def c39():
        zero = [c["canonical_id"] for c in own_canon if not c["upstream_refs"]]
        bad = [c["canonical_id"] for c in own_canon if not c["upstream_refs"] and not c.get("merge_note")]
        return not bad, f"零来源条目 {zero or '无'} 均有内部需求依据"

    def c40():
        bad = [c["canonical_id"] for c in own_canon if "unresolved" not in c]
        n = sum(len(c.get("unresolved") or []) for c in own_canon)
        return not bad, f"6 条均带 unresolved，合计 {n} 项待定"

    # ── 文档 ──────────────────────────────────────────────────────────────
    def c41():
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

    def c42():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"M-{ch}" for ch in "ABCDEFGH"]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"跨模块边界裁决 M-A..M-H 逐条登记，缺 {miss or '无'}"

    def c43():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"X-{i}" for i in range(1, 8)]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"F1-C 待裁决项 X-1..X-7 逐条登记，缺 {miss or '无'}"

    def c44():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        # 必须如实声明「未做真实数据库测试」
        ok = "不安装任何依赖" in txt and "不实现持久化引擎" in txt
        return ok, "文档如实声明本轮未安装依赖、未建库、未实现引擎"

    # ── 隔离与冻结 ────────────────────────────────────────────────────────
    def c45():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始能力索引逐字节未变"

    def c46():
        g = git("diff", "--quiet", "HEAD", "--",
                *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g.returncode == 0, "六份历史上游审计未改动"

    def c47():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c48():
        return not (F / "CAPABILITY_CROSSWALK.json").exists(), "正式交叉表尚未提前冻结"

    def c49():
        sys.path.insert(0, str(ROOT / "tools" / "fusion"))
        import f1b_storage_def as sd
        declared = set(sd.CONSUMED_THIS_BATCH)
        referenced = {(u, o) for c in sd.CANON for (u, o, _v) in c["refs"]}
        moved = set(sd.DEFERRED_TO_OTHER_MODULE)
        ok = declared == referenced and not (declared & moved)
        return ok, (f"承接声明 {len(declared)} 与引用 {len(referenced)} 一致={declared == referenced}；"
                    f"与分流零重叠={not (declared & moved)}")

    def c50():
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
        ok2 = mine is not None and mine["raw_mapped_to_this_module"] == 11
        return ok and ok2, (f"stats 重算一致 mapped={g_re['mapped_count']} "
                            f"routed={g_re['routed_pending_count']} unrev={g_re['unreviewed_count']}；"
                            f"Storage 重算 mapped=11={ok2}")

    def c51():
        expected = {("UPSTREAM-05", "C19"): "Evidence-Claims", ("UPSTREAM-05", "C14"): "Renderer"}
        bad = []
        for k, mod in expected.items():
            r = next((x for x in routed if (x["upstream_id"], x["original_capability_id"]) == k), None)
            if r is None:
                bad.append(f"{k} 未落盘为分流")
            elif r["owner_module"] != mod:
                bad.append(f"{k} 记为 {r['owner_module']}，应为 {mod}")
        import f1b_storage_def as sd
        own_declared = set(sd.DEFERRED_TO_OTHER_MODULE)
        for r in routed:
            if r["owner_module"] not in MODULES:
                bad.append(f"模块名非法 {r['owner_module']}")
            if (r["owner_module"] == MODULE
                    and (r["upstream_id"], r["original_capability_id"]) in own_declared):
                bad.append(f"{r['upstream_id']}::{r['original_capability_id']} 分流指向自身")
        return not bad, f"本批 2 条分流去向正确，问题 {bad or '无'}"

    def c52():
        found = {(x.get("upstream_id"), x.get("original_capability_id"))
                 for x in promos_to_own if x.get("from") == "cross_module_redirections"}
        expect = {("UPSTREAM-04", "C03"), ("UPSTREAM-04", "C22"),
                  ("UPSTREAM-04", "C23"), ("UPSTREAM-06", "C19")}
        missing = expect - found
        return not missing, f"四条 ROUTED 有路由表晋升记录={not missing}（缺 {sorted(missing) or '无'}）"

    def c53():
        # U06-C25 保持原判：仍是 Storage 分流，本批不改其归属（存疑入 F1-C）
        r = next((x for x in routed
                  if (x["upstream_id"], x["original_capability_id"]) == ("UPSTREAM-06", "C25")), None)
        if r is None:
            return False, "U06-C25 原分流记录丢失（第 11 节要求不得擅自更改归属）"
        ok = r["owner_module"] == "Storage"
        return ok, f"U06-C25 保持原判 owner={r['owner_module']}（未擅自改归属）"

    def c54():
        # 不重复定义 EC/Lifecycle/Security 的状态
        bad = []
        forbidden = [("SL-CAP-0062", ["claim_status", "verification_status 的取值定义"]),
                     ("SL-CAP-0065", ["staleness_verdict 的判定"])]
        for cid, keys in forbidden:
            b = blob(cid)
            for k in keys:
                if k in b:
                    bad.append(f"{cid} 疑似重定义 {k}")
        b6 = blob("SL-CAP-0066")
        ok = "verification_status 三件" in b6 or "verification_status" in b6
        # 关键：0066 必须声明「影响判定不归 Storage」
        ok2 = "Storage 只提供关系持久化与查询，不做影响判定" in b6
        return (not bad and ok2), f"未重定义他模块状态={not bad}；影响判定不归 Storage={ok2}"

    check("c1", "原始 143 项身份唯一且不变", c1)
    check("c2", "既有 61 条 canonical 保持稳定", c2)
    check("c3", "Storage 编号 0062-0067 齐全", c3)
    check("c4", "Storage 编号连续自 0062 起", c4)
    check("c5", "canonical_id 从 0001 连续", c5)
    check("c6", "canonical_id 无重复", c6)
    check("c7", "每个原始身份最多映射一次", c7)
    check("c8", "每条 canonical 一个 owner", c8)
    check("c9", "来源证据可追溯", c9)
    check("c10", "ROUTED 晋升可追踪", c10)
    check("c11", "新增分流与映射零相交", c11)
    check("c12", "三态守恒合计 143", c12)
    check("c13", "global_state_counts 与实算一致", c13)
    check("c14", "进度统计与草稿同源", c14)
    check("c15", "Storage 批次记录自洽", c15)
    check("c16", "批次按业务顺序", c16)
    check("c17", "历史八批 mapped 定格", c17)
    check("c18", "四层资产与单一权威", c18)
    check("c19", "派生索引可重建且等价", c19)
    check("c20", "当前指针不覆盖历史", c20)
    check("c21", "六标识分列不互替", c21)
    check("c22", "Subject 身份不混淆", c22)
    check("c23", "写入五步契约齐备", c23)
    check("c24", "并发冲突显式返回", c24)
    check("c25", "原子性范围如实证", c25)
    check("c26", "崩溃恢复与幂等", c26)
    check("c27", "三类查询与来源标识", c27)
    check("c28", "检索命中不等于已验 Claim", c28)
    check("c29", "权限拒绝不伪装空结果", c29)
    check("c30", "不预设向量/图数据库", c30)
    check("c31", "五类关系分离", c31)
    check("c32", "不凭空推断影响关系", c32)
    check("c33", "根目录四层隔离与路径安全", c33)
    check("c34", "不回写被分析仓库", c34)
    check("c35", "来源与许可证完整", c35)
    check("c36", "REJECT 作反例与零来源依据", c36)
    check("c37", "处置分布（信息）", c37)
    check("c38", "处置/边界/理由齐备", c38)
    check("c39", "零来源能力有内部依据", c39)
    check("c40", "unresolved 显式存在", c40)
    check("c41", "决策文档与 JSON 一致", c41)
    check("c42", "跨模块裁决 M-A..M-H 登记", c42)
    check("c43", "F1-C 待裁决 X-1..X-7 登记", c43)
    check("c44", "如实声明未实现引擎", c44)
    check("c45", "原始能力索引未改动", c45)
    check("c46", "六份上游审计未改动", c46)
    check("c47", "src/tests/schemas 无改动", c47)
    check("c48", "正式交叉表未提前冻结", c48)
    check("c49", "承接声明与 def 一致", c49)
    check("c50", "stats 重算一致且幂等", c50)
    check("c51", "新增分流去向正确", c51)
    check("c52", "四条 ROUTED 有晋升记录", c52)
    check("c53", "U06-C25 未擅自改归属", c53)
    check("c54", "不重复定义他模块状态", c54)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / Storage",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_storage.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "scope_note": "F1 设计与产物验证；未测试真实数据库的事务与并发性能",
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
