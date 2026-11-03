"""F1-B / Lifecycle 批次独立验收。只写 F1B_LIFECYCLE_VERIFICATION.json。

作用域：本验证器只判定 Lifecycle 批次自己的能力（SL-CAP-0040..0045）与本批不变量，
不替前五个批次的条目下结论（各自验证器负责）。
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
DOC = F / "F1B_LIFECYCLE_DECISIONS.md"
OUT = F / "F1B_LIFECYCLE_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULE = "Lifecycle"
MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
OWN_IDS = [f"SL-CAP-{n:04d}" for n in range(40, 46)]
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}
COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}
EC_IDS = {f"SL-CAP-{n:04d}" for n in range(20, 29)}
PRODUCT_IDS = {f"SL-CAP-{n:04d}" for n in range(29, 35)}
RESEARCH_IDS = {f"SL-CAP-{n:04d}" for n in range(35, 40)}

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

    def c1():
        h = hashlib.sha256(RAW.read_bytes()).hexdigest()
        ok = h == draft["source_index_sha256"] and len(items) == 143 and len(by_key) == 143
        return ok, f"原始 143 项且身份唯一；sha256={h[:16]} 与草稿一致={h == draft['source_index_sha256']}"

    def c2():
        old = [c for c in canon if c["canonical_id"] <= "SL-CAP-0039"]
        missing = [i for i in ("SL-CAP-0001", "SL-CAP-0039") if i not in ids]
        return len(old) == 39 and not missing, f"原有 39 条保留={len(old) == 39}；端点缺失={missing or '无'}"

    def c3():
        got = set(ids) & set(OWN_IDS)
        return got == set(OWN_IDS), f"Lifecycle 编号 0040-0045 齐全 {len(got)}/6"

    def c4():
        ow = sorted(int(i.split("-")[-1]) for i in OWN_IDS)
        return ow == list(range(40, 46)), f"Lifecycle 编号连续自 0040 起：{ow}"

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
        return not bad, f"Lifecycle 6 条 owner 均为 Lifecycle，越界 {bad or '无'}"

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
            if k in rted_all:
                bad.append(f"{k[0]}::{k[1]} 已晋升却仍在分流表")
            if r.get("from") not in {"cross_module_redirections", "unreviewed_adopted"}:
                bad.append(f"{k[0]}::{k[1]} from 非法 {r.get('from')}")
        route_promos = [r for r in promos_to_own if r.get("from") == "cross_module_redirections"]
        return not bad, f"晋升 {len(promos_to_own)} 条（其中来自路由表 {len(route_promos)} 条），问题 {bad or '无'}"

    def c11():
        clash = own_owned & rted_all
        return not clash, "本批新增分流与映射集合零相交" if not clash else f"相交 {sorted(clash)}"

    def c12():
        unrev = set(by_key) - mapped_all - rted_all
        total = len(mapped_all) + len(rted_all) + len(unrev)
        ok = total == len(by_key) == 143 and not (mapped_all & rted_all)
        return ok, (f"mapped {len(mapped_all)} + routed {len(rted_all)} + unreviewed {len(unrev)} = {total}；"
                    f"mapped∩routed 空={not (mapped_all & rted_all)}")

    def c13():
        g = draft["global_state_counts"]
        unrev = set(by_key) - mapped_all - rted_all
        ok = (g.get("mapped_count") == len(mapped_all) and
              g.get("routed_pending_count") == len(rted_all) and
              g.get("unreviewed_count") == len(unrev) and
              g.get("canonical_count") == len(canon))
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
                f"缺失 {missing or '无'}；旧口径 {stale or '无'}；与草稿一致={agree}；sum_check={t.get('sum_check')}")

    def c15():
        b = next((x for x in draft.get("batches", []) if x["module"] == MODULE), None)
        if b is None:
            return False, "草稿中没有 Lifecycle 批次记录"
        # mapped 定格为 12；出向分流按统计契约是现算视图（def 声明 − 已晋升），
        # 下游承接后会递减（Security 批次接手 U05-C20，故 5→4）。改为与现算自洽。
        import f1b_stats
        recalc = {x["module"]: x for x in f1b_stats.batches_from_draft(draft)}
        ok = (b["raw_mapped_to_this_module"] == len(own_owned) == 12
              and b["canonical_ids"] == OWN_IDS
              and b["raw_redirected_to_other_modules"] ==
                  recalc[MODULE]["raw_redirected_to_other_modules"])
        return ok, (f"mapped={b['raw_mapped_to_this_module']}（应 12）、"
                    f"redirected 现算一致={ok}（当前 {b['raw_redirected_to_other_modules']}）、"
                    f"ids 齐备={b['canonical_ids'] == OWN_IDS}")

    def c16():
        names = [b["module"] for b in draft.get("batches", [])]
        order = ["Facts", "Collector", "Evidence-Claims", "Product", "Research", "Lifecycle"]
        return names[:6] == order, f"批次按业务顺序：{names}"

    def c17():
        expect = {"Facts": 11, "Collector": 11, "Evidence-Claims": 12, "Product": 10, "Research": 10}
        bad = []
        for mod, n in expect.items():
            b = next((x for x in draft["batches"] if x["module"] == mod), None)
            if b is None:
                bad.append(f"{mod} 批次条目丢失")
            elif b["raw_mapped_to_this_module"] != n:
                bad.append(f"{mod} mapped={b['raw_mapped_to_this_module']} 应为 {n}")
        return not bad, "历史五批 mapped 全部定格未变" if not bad else f"{bad}"

    def c18():
        forbidden = ["自建 GitHub 客户端", "直接调用 GitHub REST", "第二套事实库", "urllib", "requests 旁路"]
        bad = []
        for c in own_canon:
            blob = json.dumps(c, ensure_ascii=False)
            for f in forbidden:
                if f in blob and "不得" not in blob and "禁止" not in blob:
                    bad.append(f"{c['canonical_id']} 越界「{f}」")
        return not bad, f"未重复实现 Collector，问题 {bad or '无'}"

    def c19():
        # 不得绕过 EC：裁决仍归 EC
        bad = []
        for c in own_canon:
            blob = json.dumps(c, ensure_ascii=False)
            if "refuted" in blob and "不改判" not in blob and "不得" not in blob:
                bad.append(f"{c['canonical_id']} 可能自行改判 claim 状态")
        c42 = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0042")
        b42 = json.dumps(c42, ensure_ascii=False)
        ok42 = "不改判 claim 状态" in b42
        return (not bad and ok42), f"未绕过 EC 裁决={not bad and ok42}；0042 明写不改判 claim 状态={ok42}"

    def c20():
        bad = []
        for c in own_canon:
            for d in c["dependencies"]:
                if d not in MODULES:
                    bad.append(f"{c['canonical_id']} 依赖非法模块 {d}")
        return not bad, f"依赖取值合法，问题 {bad or '无'}"

    def c21():
        bad = []
        for cid in FACTS_IDS | COLLECTOR_IDS | EC_IDS | PRODUCT_IDS | RESEARCH_IDS:
            c = next((x for x in canon if x["canonical_id"] == cid), None)
            if c is None:
                bad.append(f"{cid} 丢失")
                continue
            expect = ("Facts" if cid in FACTS_IDS else
                      "Collector" if cid in COLLECTOR_IDS else
                      "Evidence-Claims" if cid in EC_IDS else
                      "Product" if cid in PRODUCT_IDS else "Research")
            if c["owner_module"] != expect:
                bad.append(f"{cid} owner 变为 {c['owner_module']}")
        return not bad, "前五批 39 条 owner 全部未变" if not bad else f"{bad}"

    # ── 知识状态正交（门禁 11、12、13） ──────────────────────────────────
    def c22():
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0043")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("确定性检查" in blob and "模型辅助判断" in blob and "人工审批" in blob
              and "decision_class" in blob)
        return ok, "三类判定来源（确定性/模型辅助/人工）显式标注且落字段"

    def c23():
        # 任务执行失败不得自动使知识失效
        hits = []
        for c in own_canon:
            blob = json.dumps(c, ensure_ascii=False)
            if "任务执行失败" in blob or "失败动作" in blob:
                hits.append(c["canonical_id"])
        ok = bool(hits)
        return ok, f"任务失败与知识失效分离已在 {hits or '无'} 中声明"

    def c24():
        # 新 commit 不得自动把旧 claim 判 refuted
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0042")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("进入重验证队列" in blob and "不改判" in blob)
        return ok, "内容变化只进重验证队列，不自动改判 claim 状态"

    def c25():
        # 已知依赖检测与新事实发现分离
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0044")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("路径 A" in blob and "路径 B" in blob
              and "不得合并" in blob and "共享同一份" in blob)
        return ok, "路径 A / 路径 B 分离且声明共享元数据不合并算法"

    def c26():
        # 历史不可变与当前理解更新责任明确
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0041")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["不可变层", "可变层", "只追加", "被取代不删除旧证据", "prev_version_ref"]
        miss = [k for k in need if k not in blob]
        return not miss, f"两层分离与版本记录齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c27():
        # Subject 身份不得与仓库路径/Commit 混淆
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0040")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["repository_id", "不可互换", "改名", "Fork", "subject_key"]
        miss = [k for k in need if k not in blob]
        return not miss, f"身份三件套与四者不可互换已声明={not miss}" + (f"，缺 {miss}" if miss else "")

    def c28():
        # 确定性候选匹配与模型辅助判断分离
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0040")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("确定性候选匹配" in blob and "模型辅助" in blob
              and "不得被记录为" in blob)
        return ok, "两段判定分离，模型判断不得记为确定性校验通过"

    def c29():
        # 失效检测用哈希不用 mtime；变化集不完整要降级
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0042")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["content_hash", "detection_incomplete", "mtime", "不得把"]
        miss = [k for k in need if k not in blob]
        return not miss, f"哈希驱动 + 不完整降级 + 禁 mtime + 禁止扩大解释 齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c30():
        # 外部来源新鲜度分层
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0045")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["verified_against_commit 不是通用", "retrieved_at 只能证明",
                "unverifiable_since", "不得伪造来源支持"]
        miss = [k for k in need if k not in blob]
        return not miss, f"外部来源新鲜度三条硬规则齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c31():
        # U06-C26 只能作为需求来源，不得宣称上游已实现
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0042")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("上游该能力处标注为「缺失」" in blob and "不得宣称上游已提供实现" in blob)
        return ok, "U06-C26 明确标注为上游缺失、仅作需求来源"

    def c32():
        # 零来源条目必须写明独立设计理由
        zero = [c for c in own_canon if not c["upstream_refs"]]
        bad = [c["canonical_id"] for c in zero if not c.get("merge_note")]
        return not bad, f"零来源条目 {[c['canonical_id'] for c in zero] or '无'} 均有独立设计理由={not bad}"

    def c33():
        bad = []
        for c in own_canon:
            if c["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                bad.append(f"{c['canonical_id']} 非法处置")
            if not c.get("input_boundary") or not c.get("output_boundary") or not c.get("v1_scope"):
                bad.append(f"{c['canonical_id']} 缺 I/O 或 scope")
            if not c.get("merge_note"):
                bad.append(f"{c['canonical_id']} 缺 merge_note")
        return not bad, f"处置/边界/理由齐备，问题 {bad or '无'}"

    def c34():
        bad = []
        for c in own_canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可未逐源记录")
        n = sum(len(c["license_permission"]["per_upstream"]) for c in own_canon)
        return not bad, f"逐源许可 {n} 条独立存在，问题 {bad or '无'}"

    def c35():
        bad = []
        for c in own_canon:
            per = c["license_permission"]["per_upstream"]
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
            if any(p["upstream_id"] == "UPSTREAM-06" for p in per):
                if c["license_permission"].get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 含 U06 却判可复制")
                if any(p["upstream_id"] == "UPSTREAM-05" for p in per):
                    pass
        return not bad, f"U06 复制许可全为 false，问题 {bad or '无'}"

    def c36():
        dist = {}
        for c in own_canon:
            dist[c["disposition"]] = dist.get(c["disposition"], 0) + 1
        return True, f"（信息）Lifecycle 处置分布 {dist}"

    def c37():
        bad = [c["canonical_id"] for c in own_canon if "unresolved" not in c]
        n = sum(len(c.get("unresolved") or []) for c in own_canon)
        return not bad, f"6 条均带 unresolved，合计 {n} 项待定"

    def c38():
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

    def c39():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"S-{ch}" for ch in "ABCDEF"]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"Subject 身份六问 S-A..S-F 逐条落章，缺 {miss or '无'}"

    def c40():
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = [f"X-{i}" for i in range(1, 7)]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"跨模块 unresolved X-1..X-6 逐条登记，缺 {miss or '无'}"

    def c41():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始能力索引逐字节未变"

    def c42():
        g = git("diff", "--quiet", "HEAD", "--",
                *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g.returncode == 0, "六份历史上游审计未改动"

    def c43():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c44():
        return not (F / "CAPABILITY_CROSSWALK.json").exists(), "正式交叉表尚未冻结（F1-D 前不得发布）"

    def c45():
        sys.path.insert(0, str(ROOT / "tools" / "fusion"))
        import f1b_lifecycle_def as ld
        declared = set(ld.CONSUMED_THIS_BATCH)
        referenced = {(u, o) for c in ld.CANON for (u, o, _v) in c["refs"]}
        moved = set(ld.DEFERRED_TO_OTHER_MODULE)
        ok = declared == referenced and not (declared & moved)
        return ok, (f"承接声明 {len(declared)} 与引用 {len(referenced)} 一致={declared == referenced}；"
                    f"与分流零重叠={not (declared & moved)}")

    def c46():
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
        ok2 = mine is not None and mine["raw_mapped_to_this_module"] == 12
        return ok and ok2, (f"stats 重算与落盘一致 mapped={g_re['mapped_count']} "
                            f"routed={g_re['routed_pending_count']} unrev={g_re['unreviewed_count']}；"
                            f"Lifecycle 批次重算 mapped=12 成立={ok2}")

    def c47():
        expected = {("UPSTREAM-04", "C03"): "Storage",
                    ("UPSTREAM-04", "C22"): "Storage",
                    ("UPSTREAM-04", "C23"): "Storage",
                    ("UPSTREAM-05", "C04"): "Evidence-Claims",
                    ("UPSTREAM-05", "C20"): "Security"}
        # 作用域修正：本检查判「推出去的那几条去向写对了没有」，不是「必须永远留在分流表」。
        # 下游承接后它们会移入 mapped，这是晋升的正常结果。判据改为：要么仍在分流表且去向正确，
        # 要么已被预期目标模块以 canonical 承接（有晋升记录可查）。
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
        import f1b_lifecycle_def as _ld
        own_declared = set(_ld.DEFERRED_TO_OTHER_MODULE)
        for r in routed:
            if r["owner_module"] not in MODULES:
                bad.append(f"模块名非法 {r['owner_module']}")
            if (r["owner_module"] == MODULE
                    and (r["upstream_id"], r["original_capability_id"]) in own_declared):
                bad.append(f"{r['upstream_id']}::{r['original_capability_id']} 分流指向自身")
        return not bad, f"本批 5 条新增分流去向正确，问题 {bad or '无'}"

    def c48():
        found = {(x.get("upstream_id"), x.get("original_capability_id"))
                 for x in promos_to_own if x.get("from") == "cross_module_redirections"}
        expect = {("UPSTREAM-03", "C08"), ("UPSTREAM-05", "C17")}
        missing = expect - found
        return not missing, (f"两条 ROUTED 均有路由表晋升记录={not missing}"
                             f"（缺 {sorted(missing) or '无'}）")

    check("c1", "原始索引 143 项且身份唯一", c1)
    check("c2", "原有 39 条 canonical 保留", c2)
    check("c3", "Lifecycle 编号 0040-0045 齐全", c3)
    check("c4", "Lifecycle 编号连续自 0040 起", c4)
    check("c5", "canonical_id 从 0001 连续", c5)
    check("c6", "canonical_id 无重复", c6)
    check("c7", "每项原始能力最多正式映射一次", c7)
    check("c8", "每条 canonical 只有一个 owner", c8)
    check("c9", "来源证据可追溯", c9)
    check("c10", "ROUTED 承接有晋升记录", c10)
    check("c11", "新增分流与映射集合不相交", c11)
    check("c12", "三态守恒合计 143", c12)
    check("c13", "global_state_counts 与实算一致", c13)
    check("c14", "进度统计与草稿同源", c14)
    check("c15", "Lifecycle 批次记录自洽", c15)
    check("c16", "批次按业务顺序", c16)
    check("c17", "历史五批 mapped 定格", c17)
    check("c18", "未重复实现 Collector", c18)
    check("c19", "未绕过 Evidence-Claims 裁决", c19)
    check("c20", "依赖模块取值合法", c20)
    check("c21", "前五批 owner 未变", c21)
    check("c22", "三类判定来源显式标注", c22)
    check("c23", "任务失败不自动使知识失效", c23)
    check("c24", "新 commit 不自动判 refuted", c24)
    check("c25", "路径 A 与路径 B 分离", c25)
    check("c26", "历史不可变与当前理解责任明确", c26)
    check("c27", "Subject 身份不混淆", c27)
    check("c28", "确定性匹配与模型辅助分离", c28)
    check("c29", "哈希驱动失效检测", c29)
    check("c30", "外部来源新鲜度分层", c30)
    check("c31", "U06-C26 仅作需求来源", c31)
    check("c32", "零来源条目有独立设计理由", c32)
    check("c33", "处置/边界/理由齐备", c33)
    check("c34", "许可证权限独立存在", c34)
    check("c35", "U06 复制许可全为 false", c35)
    check("c36", "处置分布（信息）", c36)
    check("c37", "unresolved 显式存在", c37)
    check("c38", "决策文档与 JSON 一致", c38)
    check("c39", "Subject 身份六问逐条落章", c39)
    check("c40", "跨模块 unresolved 逐条登记", c40)
    check("c41", "原始能力索引未改动", c41)
    check("c42", "六份上游审计未改动", c42)
    check("c43", "src/tests/schemas 无改动", c43)
    check("c44", "正式交叉表未提前冻结", c44)
    check("c45", "承接声明与 def 一致", c45)
    check("c46", "stats 重算一致且幂等", c46)
    check("c47", "新增分流去向正确", c47)
    check("c48", "两条 ROUTED 有路由表晋升记录", c48)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / Lifecycle",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_lifecycle.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
