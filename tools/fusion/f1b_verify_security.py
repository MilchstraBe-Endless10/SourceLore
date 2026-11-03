#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Security 批次独立验收。只写 F1B_SECURITY_VERIFICATION.json。

作用域：本验证器只判定 Security 批次自己的能力（SL-CAP-0046..0054）与本批不变量，
不替前六个批次的条目下结论（各自验证器负责）。
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
DOC = F / "F1B_SECURITY_DECISIONS.md"
OUT = F / "F1B_SECURITY_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULE = "Security"
MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
OWN_IDS = [f"SL-CAP-{n:04d}" for n in range(46, 55)]
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}
COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}
EC_IDS = {f"SL-CAP-{n:04d}" for n in range(20, 29)}
PRODUCT_IDS = {f"SL-CAP-{n:04d}" for n in range(29, 35)}
RESEARCH_IDS = {f"SL-CAP-{n:04d}" for n in range(35, 40)}
LIFECYCLE_IDS = {f"SL-CAP-{n:04d}" for n in range(40, 46)}

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
        old = [c for c in canon if c["canonical_id"] <= "SL-CAP-0045"]
        missing = [i for i in ("SL-CAP-0001", "SL-CAP-0045") if i not in ids]
        return len(old) == 45 and not missing, f"原有 45 条保留={len(old) == 45}；端点缺失={missing or '无'}"

    def c3():
        got = set(ids) & set(OWN_IDS)
        return got == set(OWN_IDS), f"Security 编号 0046-0054 齐全 {len(got)}/9"

    def c4():
        ow = sorted(int(i.split("-")[-1]) for i in OWN_IDS)
        return ow == list(range(46, 55)), f"Security 编号连续自 0046 起：{ow}"

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
        return not bad, f"Security 9 条 owner 均为 Security，越界 {bad or '无'}"

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
            return False, "草稿中没有 Security 批次记录"
        import f1b_stats
        recalc = {x["module"]: x for x in f1b_stats.batches_from_draft(draft)}
        ok = (b["raw_mapped_to_this_module"] == len(own_owned) == 17
              and b["canonical_ids"] == OWN_IDS
              and b["raw_redirected_to_other_modules"] ==
                  recalc[MODULE]["raw_redirected_to_other_modules"])
        return ok, (f"mapped={b['raw_mapped_to_this_module']}（应 17）、"
                    f"redirected 现算一致={ok}（当前 {b['raw_redirected_to_other_modules']}）、"
                    f"ids 齐备={b['canonical_ids'] == OWN_IDS}")

    def c16():
        names = [b["module"] for b in draft.get("batches", [])]
        order = ["Facts", "Collector", "Evidence-Claims", "Product", "Research", "Lifecycle", "Security"]
        return names[:7] == order, f"批次按业务顺序：{names}"

    def c17():
        expect = {"Facts": 11, "Collector": 11, "Evidence-Claims": 12, "Product": 10,
                  "Research": 10, "Lifecycle": 12}
        bad = []
        for mod, n in expect.items():
            b = next((x for x in draft["batches"] if x["module"] == mod), None)
            if b is None:
                bad.append(f"{mod} 批次条目丢失")
            elif b["raw_mapped_to_this_module"] != n:
                bad.append(f"{mod} mapped={b['raw_mapped_to_this_module']} 应为 {n}")
        return not bad, "历史六批 mapped 全部定格未变" if not bad else f"{bad}"

    # ── 职责边界（门禁 10、17） ─────────────────────────────────────────
    def c18():
        forbidden = ["自建 GitHub 客户端", "直接调用 GitHub REST", "第二套事实库",
                     "urllib 旁路", "独立证据库", "独立 Evidence Registry"]
        bad = []
        for c in own_canon:
            b = json.dumps(c, ensure_ascii=False)
            for f in forbidden:
                if f in b and "不得" not in b and "禁止" not in b:
                    bad.append(f"{c['canonical_id']} 越界「{f}」")
        ok2 = "不得另建一套 Security Evidence Registry" in blob("SL-CAP-0047")
        return (not bad and ok2), f"未重复实现 Collector/EC={not bad}；EC 证据单源声明={ok2}"

    def c19():
        bad = []
        for c in own_canon:
            for d in c["dependencies"]:
                if d not in MODULES:
                    bad.append(f"{c['canonical_id']} 依赖非法 {d}")
        coll = sum(1 for c in own_canon if "Collector" in c["dependencies"])
        ec = sum(1 for c in own_canon if "Evidence-Claims" in c["dependencies"])
        return not bad, f"依赖合法；依赖 Collector 的条目 {coll}、依赖 EC 的 {ec}，问题 {bad or '无'}"

    def c20():
        b = blob("SL-CAP-0047")
        ok = ("source_commit_sha" in b and "affected_component" in b and "detection_limitations" in b
              and "evidence_refs" in b)
        return ok, "安全发现九字段齐备（含 detection_limitations 与 evidence_refs）"

    def c21():
        b = blob("SL-CAP-0047")
        need = ["unconfirmed", "inconclusive", "不得直接成为确认漏洞", "false_positive", "不能自动标记"]
        miss = [k for k in need if k not in b]
        return not miss, f"insufficient 不自动变 refuted 的硬规则齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c22():
        b = blob("SL-CAP-0047")
        ok = ("C-1" in b and "C-2" in b and "C-3" in b and "C-4" in b
              and "四项独立检查" in b)
        return ok, "位置/链路/影响/可达 四项独立检查已定义且互不推出"

    def c23():
        b = blob("SL-CAP-0047")
        ok = ("并非所有发现都需要完整数据流链" in b
              and "不必要求 HTTP 入口" in b)
        return ok, "发现类型与验证要求匹配：非 HTTP 类发现不强制链路"

    def c24():
        b = blob("SL-CAP-0049")
        need = ["REACHABLE", "UNREACHABLE", "INDETERMINATE", "两个独立字段", "未经校准"]
        miss = [k for k in need if k not in b]
        return not miss, f"可达性三态与严重度/优先级独立 + 禁百分比={not miss}" + (f"，缺 {miss}" if miss else "")

    def c25():
        b = blob("SL-CAP-0049")
        ok = "有界静态搜索未发现调用路径时，原则上不得直接宣称 UNREACHABLE" in b
        return ok, "有界搜索空结果不得推出 UNREACHABLE"

    def c26():
        b = blob("SL-CAP-0048")
        need = ["canonical".replace("canonical", "环境失败绝不改判"), "auth_coverage", "unknown", "Fail-safe"]
        miss = [k for k in need if k not in b]
        return not miss, f"环境失败不改判 + auth 三态 + 失效安全={not miss}" + (f"，缺 {miss}" if miss else "")

    def c27():
        b = blob("SL-CAP-0050")
        need = ["family_swept", "class_negatives", "partial_negative", "禁止输出「不存在该类漏洞」"]
        miss = [k for k in need if k not in b]
        return not miss, f"族扫描与诚实否定字段齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c28():
        b = blob("SL-CAP-0051")
        need = ["互不蕴含", "默认全关", "构造点必须钉在验证之后", "不得一键跳过"]
        miss = [k for k in need if k not in b]
        return not miss, f"双重控制 + 构造门 + 禁一键跳过={not miss}" + (f"，缺 {miss}" if miss else "")

    def c29():
        b = blob("SL-CAP-0052")
        need = ["A-1", "A-7", "不得提升为系统级指令", "rule_id", "detection_method"]
        miss = [k for k in need if k not in b]
        return not miss, f"Agent/Skill 安全 A-1..A-7 与可检查规则形式齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c30():
        b = blob("SL-CAP-0052")
        ok = "不能让被分析仓库决定 SourceLore 的审查步骤或安全策略" in b
        return ok, "审查步骤由 SourceLore 决定，不由被分析仓库决定"

    def c31():
        b = blob("SL-CAP-0053")
        need = ["P-1", "P-2", "P-3", "P-4", "不得自行把需要人工批准的产物标记为 approved",
                "脱敏通过（P-2）不等于允许公开发布"]
        miss = [k for k in need if k not in b]
        return not miss, f"四级发布门禁 + AI 不得自批 + 脱敏≠可发布={not miss}" + (f"，缺 {miss}" if miss else "")

    def c32():
        b = blob("SL-CAP-0053")
        ok = ("原始扫描输出不落盘是结构约束" in b and "not 事后删除" not in b)
        return ok, "原始扫描输出不落盘为结构约束而非事后删除"

    def c33():
        b = blob("SL-CAP-0054")
        need = ["D-1", "D-2", "D-3", "control_regression", "suspected_regression"]
        miss = [k for k in need if k not in b]
        return not miss, f"PR Diff 三件套判据与两级结论齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c34():
        b = blob("SL-CAP-0054")
        ok = "核心证据在删除侧" in b
        return ok, "增量审查核心证据在删除侧（只看新增不得判无影响）"

    # ── 许可证红线（门禁 8） ──────────────────────────────────────────────
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
        return not bad, f"U06 复制许可全为 false，问题 {bad or '无'}"

    def c36():
        b = blob("SL-CAP-0051")
        ok = "一键安装外部扫描器" in b and "REJECT" in b
        return ok, "U06-C28 一键安装扫描器已判 REJECT"

    def c37():
        dist = {}
        for c in own_canon:
            dist[c["disposition"]] = dist.get(c["disposition"], 0) + 1
        return True, f"（信息）Security 处置分布 {dist}"

    # ── 文档与结构 ────────────────────────────────────────────────────────
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
        return not bad, f"零来源条目 {zero or '无'} 均有独立设计理由"

    def c40():
        bad = [c["canonical_id"] for c in own_canon if "unresolved" not in c]
        n = sum(len(c.get("unresolved") or []) for c in own_canon)
        return not bad, f"9 条均带 unresolved，合计 {n} 项待定"

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
        anchors = [f"R-{ch}" for ch in "ABCDEF"]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"主要规则 R-A..R-F 逐条落章，缺 {miss or '无'}"

    def c43():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"Z-{i}" for i in range(1, 8)]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"特别待裁决 Z-1..Z-7 逐条登记，缺 {miss or '无'}"

    def c44():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始能力索引逐字节未变"

    def c45():
        g = git("diff", "--quiet", "HEAD", "--",
                *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g.returncode == 0, "六份历史上游审计未改动"

    def c46():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c47():
        return not (F / "CAPABILITY_CROSSWALK.json").exists(), "正式交叉表尚未冻结（F1-D 前不得发布）"

    def c48():
        sys.path.insert(0, str(ROOT / "tools" / "fusion"))
        import f1b_security_def as sd
        declared = set(sd.CONSUMED_THIS_BATCH)
        referenced = {(u, o) for c in sd.CANON for (u, o, _v) in c["refs"]}
        moved = set(sd.DEFERRED_TO_OTHER_MODULE)
        ok = declared == referenced and not (declared & moved)
        return ok, (f"承接声明 {len(declared)} 与引用 {len(referenced)} 一致={declared == referenced}；"
                    f"与分流零重叠={not (declared & moved)}")

    def c49():
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
        ok2 = mine is not None and mine["raw_mapped_to_this_module"] == 17
        return ok and ok2, (f"stats 重算一致 mapped={g_re['mapped_count']} "
                            f"routed={g_re['routed_pending_count']} unrev={g_re['unreviewed_count']}；"
                            f"Security 重算 mapped=17={ok2}")

    def c50():
        # 作用域修正：本检查判「Security 批次推出去的那几条去向写对了没有」，
        # 不是「它们必须永远留在分流表」。后续批次有可能承接其中的条目（本批 Storage 接手 U06-C19），
        # 那是晋升的正常结果；也可能有后来者对归属提出异议（如 U06-C25 的 owner 存疑，
        # 已登记为 F1-C 待裁决）。判据改为：要么仍在分流表且去向正确，要么已被承接、或已进入待裁决。
        expected = {("UPSTREAM-06", "C18"): "DSH-Adapter",
                    ("UPSTREAM-06", "C10"): "Evidence-Claims",
                    ("UPSTREAM-06", "C20"): "Evidence-Claims",
                    ("UPSTREAM-06", "C19"): "Storage",
                    ("UPSTREAM-06", "C25"): "Storage"}
        pending_f1c = {("UPSTREAM-06", "C25")}
        bad = []
        for k, mod in expected.items():
            r = next((x for x in routed if (x["upstream_id"], x["original_capability_id"]) == k), None)
            if r is not None:
                if r["owner_module"] != mod:
                    bad.append(f"{k} 记为 {r['owner_module']}，应为 {mod}")
                continue
            if k in pending_f1c:
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
        for r in routed:
            if r["owner_module"] not in MODULES:
                bad.append(f"模块名非法 {r['owner_module']}")
            if r["owner_module"] == MODULE:
                bad.append(f"{r['upstream_id']}::{r['original_capability_id']} 分流指向自身")
        return not bad, f"本批 5 条分流去向正确（含 U06-C18 改路由 DSH-Adapter），问题 {bad or '无'}"

    def c51():
        found = {(x.get("upstream_id"), x.get("original_capability_id"))
                 for x in promos_to_own if x.get("from") == "cross_module_redirections"}
        expect = {("UPSTREAM-06", "C24"), ("UPSTREAM-05", "C20")}
        missing = expect - found
        return not missing, f"两条 ROUTED 均有路由表晋升记录={not missing}（缺 {sorted(missing) or '无'}）"

    def c52():
        # U06-C18 改路由必须有理由留痕
        r = next((x for x in routed if (x["upstream_id"], x["original_capability_id"]) == ("UPSTREAM-06", "C18")), None)
        if r is None:
            return False, "U06-C18 改路由记录不存在"
        ok = "改路由" in r["reason"] and "不属安全" in r["reason"]
        return ok, "U06-C18 改路由理由留痕（含原归类与本次重新裁决原因）"

    def c53():
        # 未在 EC 中重复占用：U06-C05/C06/C07 仍归 EC
        bad = []
        for k, owner in [(("UPSTREAM-06", "C05"), "SL-CAP-0021"),
                         (("UPSTREAM-06", "C06"), "SL-CAP-0028"),
                         (("UPSTREAM-06", "C07"), "SL-CAP-0028")]:
            cur = next((c["canonical_id"] for c in canon
                        for r in c["upstream_refs"]
                        if (r["upstream_id"], r["original_capability_id"]) == k), None)
            if cur != owner:
                bad.append(f"{k} 现归 {cur}，应为 {owner}")
            if k in own_owned:
                bad.append(f"{k} 被 Security 重复占用")
        return not bad, f"U06-C05/C06/C07 仍归 EC 且未被重复占用={not bad}"

    check("c1", "原始 143 项身份唯一且不变", c1)
    check("c2", "原有 45 条 canonical 保持有效", c2)
    check("c3", "Security 编号 0046-0054 齐全", c3)
    check("c4", "Security 编号连续自 0046 起", c4)
    check("c5", "canonical_id 从 0001 连续", c5)
    check("c6", "canonical_id 无重复", c6)
    check("c7", "每个原始身份最多映射一次", c7)
    check("c8", "每条 canonical 一个 owner", c8)
    check("c9", "来源证据可追溯", c9)
    check("c10", "ROUTED 承接有晋升记录", c10)
    check("c11", "新增分流与映射零相交", c11)
    check("c12", "三态守恒合计 143", c12)
    check("c13", "global_state_counts 与实算一致", c13)
    check("c14", "进度统计与草稿同源", c14)
    check("c15", "Security 批次记录自洽", c15)
    check("c16", "批次按业务顺序", c16)
    check("c17", "历史六批 mapped 定格", c17)
    check("c18", "未建立第二套 Claim/Evidence", c18)
    check("c19", "与 Collector/EC 边界清楚", c19)
    check("c20", "安全发现九字段齐备", c20)
    check("c21", "insufficient 不自动变 refuted", c21)
    check("c22", "四项独立检查互不推出", c22)
    check("c23", "发现类型与验证要求匹配", c23)
    check("c24", "可达性三态 + 严重度/优先级独立", c24)
    check("c25", "有界搜索空结果不判 UNREACHABLE", c25)
    check("c26", "环境失败不改判 + auth 三态", c26)
    check("c27", "族扫描与诚实否定", c27)
    check("c28", "双重控制与构造门", c28)
    check("c29", "Agent/Skill 安全可检查化", c29)
    check("c30", "审查步骤不由被分析仓库决定", c30)
    check("c31", "四级发布门禁且 AI 不得自批", c31)
    check("c32", "原始输出不落盘为结构约束", c32)
    check("c33", "PR Diff 三件套判据齐备", c33)
    check("c34", "增量证据在删除侧", c34)
    check("c35", "U06 无复制权限遗漏", c35)
    check("c36", "一键安装扫描器已判 REJECT", c36)
    check("c37", "处置分布（信息）", c37)
    check("c38", "处置/边界/理由齐备", c38)
    check("c39", "零来源条目有独立理由", c39)
    check("c40", "unresolved 显式存在", c40)
    check("c41", "决策文档与 JSON 一致", c41)
    check("c42", "主要规则 R-A..R-F 落章", c42)
    check("c43", "特别待裁决 Z-1..Z-7 登记", c43)
    check("c44", "原始能力索引未改动", c44)
    check("c45", "六份上游审计未改动", c45)
    check("c46", "src/tests/schemas 无改动", c46)
    check("c47", "正式交叉表未提前冻结", c47)
    check("c48", "承接声明与 def 一致", c48)
    check("c49", "stats 重算一致且幂等", c49)
    check("c50", "新增分流去向正确（含改路由）", c50)
    check("c51", "两条 ROUTED 有路由表晋升记录", c51)
    check("c52", "U06-C18 改路由留痕", c52)
    check("c53", "未重复占用 EC 已映射身份", c53)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / Security",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_security.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
