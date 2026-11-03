#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Research 批次独立验收。只写 F1B_RESEARCH_VERIFICATION.json。

作用域：本验证器只判定 Research 批次自己的能力（SL-CAP-0035..0039）与本批不变量，
不替前四个批次的条目下结论（各自验证器负责）。
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
DOC = F / "F1B_RESEARCH_DECISIONS.md"
OUT = F / "F1B_RESEARCH_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULE = "Research"
MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
OWN_IDS = [f"SL-CAP-{n:04d}" for n in range(35, 40)]
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}
COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}
EC_IDS = {f"SL-CAP-{n:04d}" for n in range(20, 29)}
PRODUCT_IDS = {f"SL-CAP-{n:04d}" for n in range(29, 35)}

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

    # ── 基线与完整性 ────────────────────────────────────────────────────
    def c1():
        h = hashlib.sha256(RAW.read_bytes()).hexdigest()
        ok = h == draft["source_index_sha256"] and len(items) == 143 and len(by_key) == 143
        return ok, f"原始 143 项且身份唯一；sha256={h[:16]} 与草稿一致={h == draft['source_index_sha256']}"

    def c2():
        old = [c for c in canon if c["canonical_id"] <= "SL-CAP-0034"]
        missing = [i for i in ("SL-CAP-0001", "SL-CAP-0034") if i not in ids]
        return (len(old) == 34 and not missing), f"已存在 34 条保留={len(old) == 34}；端点缺失={missing or '无'}"

    def c3():
        got = set(ids) & set(OWN_IDS)
        return got == set(OWN_IDS), f"Research 编号 0035-0039 齐全 {len(got)}/5"

    def c4():
        ow = sorted(int(i.split("-")[-1]) for i in OWN_IDS)
        return ow == list(range(35, 40)), f"Research 编号连续自 0035 起：{ow}"

    def c5():
        want = [f"SL-CAP-{i:04d}" for i in range(1, len(ids) + 1)]
        return sorted(ids) == want, f"全表共 {len(ids)} 条，从 0001 连续无断号"

    def c6():
        dup = sorted({i for i in ids if ids.count(i) > 1})
        return not dup, f"canonical_id 无重复（{len(ids)} 条）" if not dup else f"重复 {dup}"

    # ── 归属唯一性与身份完整性 ───────────────────────────────────────────
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
        return not bad, f"Research 5 条 owner 唯一且均为 Research，越界 {bad or '无'}"

    def c9():
        bad = []
        for c in own_canon:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                if k not in by_key:
                    bad.append(f"{c['canonical_id']}::{k[0]}::{k[1]}")
        return not bad, f"{len(own_owned)} 个原始来源全部可在索引定位" if not bad else f"查无 {bad}"

    def c10():
        bad = []
        for r in promos_to_own:
            k = (r.get("upstream_id"), r.get("original_capability_id"))
            still = any((x["upstream_id"], x["original_capability_id"]) == k
                        and x["owner_module"] == MODULE for x in routed)
            if still:
                bad.append(f"{k[0]}::{k[1]} 已晋升却仍留在 Research 分流表")
            if r.get("from") not in {"cross_module_redirections", "unreviewed_adopted"}:
                bad.append(f"{k[0]}::{k[1]} from 非法 {r.get('from')}")
        return not bad, f"晋升 {len(promos_to_own)} 条，问题 {bad or '无'}"

    def c11():
        allrouted = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        clash = own_owned & allrouted
        return not clash, "新增分流与本批已映射身份零重叠" if not clash else f"重叠 {sorted(clash)}"

    def c12():
        mapped = {(r["upstream_id"], r["original_capability_id"]) for c in canon for r in c["upstream_refs"]}
        rted = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        unrev = set(by_key) - mapped - rted
        total = len(mapped) + len(rted) + len(unrev)
        ok = total == len(by_key) == 143 and not (mapped & rted)
        return ok, (f"mapped {len(mapped)} + routed {len(rted)} + unreviewed {len(unrev)} = {total}；"
                    f"mapped∩routed 空={not (mapped & rted)}")

    def c13():
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
        return ok and inv_ok, (f"global_state_counts 自洽 mapped={len(mapped)} routed={len(rted)} "
                              f"unreviewed={len(unrev)} canonical={len(canon)}；不变量={inv_ok}")

    def c14():
        t = prog["totals"]
        g = draft["global_state_counts"]
        need = ["mapped_count", "routed_pending_count", "unreviewed_count", "canonical_count", "sum_check"]
        missing = [k for k in need if k not in t]
        stale = [k for k in ("raw_assigned", "raw_pending", "canonical_total") if k in t]
        agree = all(t.get(k) == g.get(k) for k in need if k in t)
        return (not missing and not stale and agree,
                f"缺失 {missing or '无'}；旧口径 {stale or '无'}；与草稿一致={agree}；sum_check={t.get('sum_check')}")

    # ── 批次视图 ─────────────────────────────────────────────────────────
    def c15():
        b = next((x for x in draft.get("batches", []) if x["module"] == MODULE), None)
        if b is None:
            return False, "草稿中没有 Research 批次记录"
        # mapped 定格为 10；出向分流是现算视图（def 声明 − 已晋升），
        # 下游承接后会递减（Renderer 接手 U02-C17，故 3→2）。改为与现算自洽。
        import f1b_stats
        recalc = {x["module"]: x for x in f1b_stats.batches_from_draft(draft)}
        ok = (b["raw_mapped_to_this_module"] == len(own_owned) == 10
              and b["canonical_ids"] == OWN_IDS
              and b["raw_redirected_to_other_modules"] ==
                  recalc[MODULE]["raw_redirected_to_other_modules"])
        return ok, (f"mapped={b['raw_mapped_to_this_module']}（应 10）、"
                    f"redirected 现算一致={ok}（当前 {b['raw_redirected_to_other_modules']}）、"
                    f"ids 齐备={b['canonical_ids'] == OWN_IDS}")

    def c16():
        names = [b["module"] for b in draft.get("batches", [])]
        order = ["Facts", "Collector", "Evidence-Claims", "Product", "Research"]
        return names[:5] == order, f"批次按业务顺序：{names}"

    def c17():
        # 历史四批的 mapped 定格未变
        expect = {"Facts": 11, "Collector": 11, "Evidence-Claims": 12, "Product": 10}
        bad = []
        for mod, n in expect.items():
            b = next((x for x in draft["batches"] if x["module"] == mod), None)
            if b is None:
                bad.append(f"{mod} 批次条目丢失")
            elif b["raw_mapped_to_this_module"] != n:
                bad.append(f"{mod} mapped={b['raw_mapped_to_this_module']} 应为 {n}")
        return not bad, f"历史四批 mapped 全部定格未变" if not bad else f"{bad}"

    # ── 职责边界 ─────────────────────────────────────────────────────────
    def c18():
        # 不得重复实现 Collector：不得声明自建客户端或第二套事实库
        forbidden = ["自建 GitHub 客户端", "直接调用 GitHub REST", "第二套事实库", "第二份配额",
                     "urllib", "requests 旁路"]
        bad = []
        for c in own_canon:
            blob = json.dumps(c, ensure_ascii=False)
            for f in forbidden:
                if f in blob and "不得" not in blob and "禁止" not in blob:
                    bad.append(f"{c['canonical_id']} 越界表述「{f}」")
        # 正向判据：必须明确经 Collector 取数
        uses_collector = any("Collector" in c["dependencies"] for c in own_canon)
        detail = f"未声明自建采集通道={not bad}；经 Collector 取数的条目={uses_collector}"
        return (not bad and uses_collector), detail

    def c19():
        # 不得绕过 Evidence-Claims：不得自行裁决真伪
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0035")
        blob = json.dumps(c, ensure_ascii=False)
        ok1 = "不自行裁决真伪" in blob
        c2 = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0038")
        blob2 = json.dumps(c2, ensure_ascii=False)
        ok2 = "不得自行裁决" in blob2 and "Evidence-Claims" in blob2
        return (ok1 and ok2), f"R3 明令不自行裁决={ok1}；冲突移交 EC={ok2}"

    def c20():
        # 依赖只能指向合法模块
        bad = []
        for c in own_canon:
            for d in c["dependencies"]:
                if d not in MODULES:
                    bad.append(f"{c['canonical_id']} 依赖非法模块 {d}")
        return not bad, f"依赖取值合法，问题 {bad or '无'}"

    def c21():
        # 前四批 owner 未被本批改动
        bad = []
        for cid in FACTS_IDS | COLLECTOR_IDS | EC_IDS | PRODUCT_IDS:
            c = next((x for x in canon if x["canonical_id"] == cid), None)
            if c is None:
                bad.append(f"{cid} 丢失")
                continue
            expect = ("Facts" if cid in FACTS_IDS else
                      "Collector" if cid in COLLECTOR_IDS else
                      "Evidence-Claims" if cid in EC_IDS else "Product")
            if c["owner_module"] != expect:
                bad.append(f"{cid} owner 变为 {c['owner_module']}")
        return not bad, f"前四批 34 条 owner 全部未变" if not bad else f"{bad}"

    # ── 研究语义（第 5 节第 13、14、15 项） ──────────────────────────────
    def c22():
        # complete / partial / facts_only 有明确适用边界
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0038")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["complete", "partial", "facts_only"]
        miss = [k for k in need if k not in blob]
        has_boundary = "质量状态描述" in blob and "不描述" in blob
        detail = f"三态齐备={not miss}；质量状态≠执行状态的边界声明={has_boundary}"
        return (not miss and has_boundary), detail

    def c23():
        # 缺失资料不会被写成空结果
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0037")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("partial" in blob and "truncated" in blob and "unavailable" in blob
              and "empty" in blob and "禁止把「没拿到」写成「没有」" in blob)
        return ok, "partial/truncated/unavailable/empty 四态分列 + 禁止混同规则已落地"

    def c24():
        # 研究预算与恢复策略落实在设计里
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0035")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["stage_budget", "resume_point", "remaining_questions", "只补缺口"]
        miss = [k for k in need if k not in blob]
        return not miss, f"预算/恢复点/剩余问题/只补缺口 齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c25():
        # 阶段完成 ≠ 结论正确，读全 ≠ 研究完成
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0035")
        blob = json.dumps(c, ensure_ascii=False)
        ok1 = "阶段完成不等于结论正确" in blob
        ok2 = "资料读完不等于研究完成" in blob
        return (ok1 and ok2), f"阶段完成≠结论正确={ok1}；读全≠研究完成={ok2}"

    def c26():
        # 来源优先级不替代验证 + 禁未校准百分比
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0037")
        blob = json.dumps(c, ensure_ascii=False)
        ok1 = "来源类型不构成真伪排序" in blob
        ok2 = "不得使用未校准的置信度百分比" in blob
        return (ok1 and ok2), f"来源类型不构成真伪排序={ok1}；禁未校准百分比={ok2}"

    def c27():
        # 采集时刻与 commit 锚点分开保存
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0037")
        blob = json.dumps(c, ensure_ascii=False)
        ok = "retrieved_at" in blob and "verified_against_commit" in blob and "不可互换" in blob
        return ok, "retrieved_at 与 verified_against_commit 分列且声明不可互换"

    def c28():
        # 引用校验由校验器执行而非提示词
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0039")
        blob = json.dumps(c, ensure_ascii=False)
        ok = "校验器" in blob and "提示词" in blob and "citation_check" in blob
        return ok, "引用纪律由校验器执行、提示词只负责尽量做对"

    def c29():
        # 去重与规范化
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0036")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("normalized_source" in blob and "content_hash" in blob
              and "independent_source_count" in blob and "negative_result" in blob)
        return ok, "URL 规范化 + 内容哈希折叠 + 独立来源计数 + 负结果留痕齐备"

    # ── 内容完整性 ───────────────────────────────────────────────────────
    def c30():
        bad = []
        for c in own_canon:
            if not c.get("upstream_refs") and not c.get("merge_note"):
                bad.append(f"{c['canonical_id']} 无来源且无理由")
            if c["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                bad.append(f"{c['canonical_id']} 非法处置")
            if not c.get("input_boundary") or not c.get("output_boundary") or not c.get("v1_scope"):
                bad.append(f"{c['canonical_id']} 缺 I/O 或 scope")
            if not c.get("merge_note"):
                bad.append(f"{c['canonical_id']} 缺 merge_note")
        return not bad, f"来源/处置/边界/理由齐备，问题 {bad or '无'}"

    def c31():
        bad = []
        for c in own_canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可未逐源记录")
        n = sum(len(c["license_permission"]["per_upstream"]) for c in own_canon)
        return not bad, f"逐源许可 {n} 条独立存在，问题 {bad or '无'}"

    def c32():
        # U06 无许可证：涉及 U06 来源的条目整体不得可复制
        bad = []
        for c in own_canon:
            per = c["license_permission"]["per_upstream"]
            if any(p["upstream_id"] == "UPSTREAM-06" for p in per):
                if c["license_permission"].get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 含 U06 却判可复制")
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
        return not bad, f"U06 复制许可全为 false，问题 {bad or '无'}"

    def c33():
        dist = {}
        for c in own_canon:
            dist[c["disposition"]] = dist.get(c["disposition"], 0) + 1
        return True, f"（信息）Research 处置分布 {dist}"

    def c34():
        bad = [c["canonical_id"] for c in own_canon if "unresolved" not in c]
        n = sum(len(c.get("unresolved") or []) for c in own_canon)
        return not bad, f"5 条均带 unresolved，合计 {n} 项待定"

    # ── 文档一致性 ───────────────────────────────────────────────────────
    def c35():
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
            # 逐行扫描，避免正则转义在不同写法下退化（实测 `\\n` 在类里被当字面反斜杠与 n）
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

    def c36():
        # 第 5 节八项冲突裁决逐条落章
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"C-{i}" for i in range(1, 9)]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"冲突裁决 C-1..C-8 逐条落章，缺 {miss or '无'}"

    def c37():
        # 第 4 节 A–G 七项工程约束逐条落章
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = ["R-A", "R-B", "R-C", "R-D", "R-E", "R-F", "R-G"]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"工程约束 R-A..R-G 逐条落章，缺 {miss or '无'}"

    # ── 隔离与冻结 ───────────────────────────────────────────────────────
    def c38():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始能力索引逐字节未变"

    def c39():
        g = git("diff", "--quiet", "HEAD", "--",
                *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g.returncode == 0, "六份历史上游审计未改动"

    def c40():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c41():
        return not (F / "CAPABILITY_CROSSWALK.json").exists(), "正式交叉表尚未冻结（F1-D 前不得发布）"

    def c42():
        g = git("status", "--short", "--", "schemas/")
        new = [l for l in g.stdout.splitlines() if "research" in l.lower() or "schema" in l.lower()]
        return not new, f"未新增 Research schema（schemas/ 相关变动 {new or '无'}）"

    # ── 幂等与声明一致性 ─────────────────────────────────────────────────
    def c43():
        sys.path.insert(0, str(ROOT / "tools" / "fusion"))
        import f1b_research_def as rd
        declared = set(rd.CONSUMED_THIS_BATCH)
        referenced = {(u, o) for c in rd.CANON for (u, o, _v) in c["refs"]}
        moved = set(rd.DEFERRED_TO_OTHER_MODULE)
        ok = declared == referenced and not (declared & moved)
        return ok, (f"承接声明 {len(declared)} 与引用 {len(referenced)} 一致={declared == referenced}；"
                    f"与分流零重叠={not (declared & moved)}")

    def c44():
        import importlib, f1b_stats
        importlib.reload(f1b_stats)
        g_re = f1b_stats.global_state_counts(draft, raw)
        b_re = f1b_stats.batches_from_draft(draft)
        g = draft["global_state_counts"]
        ok = (g_re["mapped_count"] == g["mapped_count"]
              and g_re["routed_pending_count"] == g["routed_pending_count"]
              and g_re["unreviewed_count"] == g["unreviewed_count"]
              and g_re["canonical_count"] == g["canonical_count"])
        mine = next((x for x in b_re if x["module"] == MODULE), None)
        ok2 = mine is not None and mine["raw_mapped_to_this_module"] == 10
        return ok and ok2, (f"stats 重算与落盘一致 mapped={g_re['mapped_count']} "
                            f"routed={g_re['routed_pending_count']} unrev={g_re['unreviewed_count']}；"
                            f"Research 批次重算 mapped=10 成立={ok2}")

    def c45():
        # 分流去向合法且不等于 Research 自身
        expected = {("UPSTREAM-04", "C24"): "Evidence-Claims",
                    ("UPSTREAM-05", "C24"): "Evidence-Claims",
                    ("UPSTREAM-02", "C17"): "Renderer"}
        bad = []
        for k, mod in expected.items():
            r = next((x for x in routed if (x["upstream_id"], x["original_capability_id"]) == k), None)
            if r is not None:
                if r["owner_module"] != mod:
                    bad.append(f"{k} 去向记为 {r['owner_module']}，应为 {mod}")
                continue
            promoted = next((x for x in promos
                             if (x.get("upstream_id"), x.get("original_capability_id")) == k), None)
            if promoted is None:
                bad.append(f"{k} 既不在分流表也无晋升记录")
            else:
                owner = next((c["owner_module"] for c in canon
                              if c["canonical_id"] == promoted.get("to_canonical_id")), None)
                if owner != mod:
                    bad.append(f"{k} 被 {owner} 承接，预期去向 {mod}")
        import f1b_research_def as _rd
        own_declared = set(_rd.DEFERRED_TO_OTHER_MODULE)
        for r in routed:
            if r["owner_module"] not in MODULES:
                bad.append(f"模块名非法 {r['owner_module']}")
            if (r["owner_module"] == MODULE
                    and (r["upstream_id"], r["original_capability_id"]) in own_declared):
                bad.append(f"{r['upstream_id']}::{r['original_capability_id']} 分流指向自身")
        return not bad, f"本批 3 条新增分流去向正确，问题 {bad or '无'}"

    def c46():
        # 已承接一条 ROUTED（U02-C11）必须有来自路由表的晋升记录
        found = [r for r in promos_to_own
                 if r.get("from") == "cross_module_redirections"
                 and (r.get("upstream_id"), r.get("original_capability_id")) == ("UPSTREAM-02", "C11")]
        return bool(found), ("U02::C11 有 cross_module_redirections 晋升记录" if found
                             else "缺少 U02::C11 的路由表晋升记录")

    check("c1", "原始索引 143 项且身份唯一", c1)
    check("c2", "已存在 34 条 canonical 保留", c2)
    check("c3", "Research 编号 0035-0039 齐全", c3)
    check("c4", "Research 编号连续自 0035 起", c4)
    check("c5", "canonical_id 从 0001 连续", c5)
    check("c6", "canonical_id 无重复", c6)
    check("c7", "每项原始能力最多正式映射一次", c7)
    check("c8", "每条 canonical 只有一个 owner", c8)
    check("c9", "Research 来源证据可追溯", c9)
    check("c10", "已承接 ROUTED 项有正确晋升记录", c10)
    check("c11", "新分流不与已映射集合相交", c11)
    check("c12", "三态守恒合计 143", c12)
    check("c13", "global_state_counts 与实算一致", c13)
    check("c14", "进度统计与草稿同源", c14)
    check("c15", "Research 批次记录自洽", c15)
    check("c16", "批次按业务顺序", c16)
    check("c17", "历史四批 mapped 定格", c17)
    check("c18", "Research 未重复实现 Collector", c18)
    check("c19", "Research 未绕过 Evidence-Claims", c19)
    check("c20", "依赖模块取值合法", c20)
    check("c21", "前四批 owner 未变", c21)
    check("c22", "三态质量适用边界明确", c22)
    check("c23", "缺失资料不写成空结果", c23)
    check("c24", "预算与恢复策略已落实", c24)
    check("c25", "阶段完成≠结论正确、读全≠研究完成", c25)
    check("c26", "来源优先级不替代验证、禁百分比", c26)
    check("c27", "采集时刻与 commit 锚点分列", c27)
    check("c28", "引用校验由校验器执行", c28)
    check("c29", "去重与规范化落地", c29)
    check("c30", "来源/处置/边界/理由齐备", c30)
    check("c31", "许可证权限独立存在", c31)
    check("c32", "U06 复制许可全为 false", c32)
    check("c33", "处置分布（信息）", c33)
    check("c34", "unresolved 显式存在", c34)
    check("c35", "决策文档与 JSON 一致", c35)
    check("c36", "八项冲突裁决逐条落章", c36)
    check("c37", "工程约束 R-A..R-G 逐条落章", c37)
    check("c38", "原始能力索引未改动", c38)
    check("c39", "六份上游审计未改动", c39)
    check("c40", "src/tests/schemas 无改动", c40)
    check("c41", "正式交叉表未提前冻结", c41)
    check("c42", "未新增 Research schema", c42)
    check("c43", "承接声明与 def 一致", c43)
    check("c44", "stats 重算与落盘一致且幂等", c44)
    check("c45", "新增分流去向正确", c45)
    check("c46", "U02::C11 有路由表晋升记录", c46)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / Research",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_research.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
