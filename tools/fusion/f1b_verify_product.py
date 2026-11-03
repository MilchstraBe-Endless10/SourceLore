#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-B / Product 批次独立验收。只写 F1B_PRODUCT_VERIFICATION.json。

作用域：本验证器只判定 Product 批次自己的能力（SL-CAP-0029..0034）与本批不变量，
不替前三个批次的条目下结论（各自验证器负责）。

历史批次判历史事实，当前全局状态由当前 Crosswalk 计算——本轮沿用这一口径。
"""
import json, sys, hashlib, subprocess, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
PROG = F / "CROSSWALK_PROGRESS.json"
DOC = F / "F1B_PRODUCT_DECISIONS.md"
OUT = F / "F1B_PRODUCT_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

MODULE = "Product"
MODULES = {"Collector", "Facts", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}
OWN_IDS = [f"SL-CAP-{n:04d}" for n in range(29, 35)]
FACTS_IDS = {f"SL-CAP-{n:04d}" for n in range(1, 11)}
COLLECTOR_IDS = {f"SL-CAP-{n:04d}" for n in range(11, 20)}
EC_IDS = {f"SL-CAP-{n:04d}" for n in range(20, 29)}

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
    routed_by_owner = {}
    for r in routed:
        routed_by_owner.setdefault(r["owner_module"], set()).add(
            (r["upstream_id"], r["original_capability_id"]))

    # ── 基线与完整性（门禁 1、2、3） ──────────────────────────────────────
    def c1():
        h = hashlib.sha256(RAW.read_bytes()).hexdigest()
        ok = h == draft["source_index_sha256"] and len(items) == 143 and len(by_key) == 143
        return ok, f"raw 143 项且身份唯一；sha256={h[:16]} 与草稿一致={h == draft['source_index_sha256']}"

    def c2():
        missing = [i for i in ("SL-CAP-0001", "SL-CAP-0028") if i not in ids]
        old = [c for c in canon if c["canonical_id"] <= "SL-CAP-0028"]
        ok = not missing and len(old) == 28
        return ok, f"原有 28 条完整保留={len(old) == 28}；端点编号缺失={missing or '无'}"

    def c3():
        got = set(ids) & set(OWN_IDS)
        return got == set(OWN_IDS), f"Product 编号 0029-0034 齐全 {len(got)}/6"

    def c4():
        want = [f"SL-CAP-{i:04d}" for i in range(1, len(ids) + 1)]
        return sorted(ids) == want, f"共 {len(ids)} 条，从 0001 连续无断号"

    def c5():
        dup = sorted({i for i in ids if ids.count(i) > 1})
        return not dup, f"canonical_id 无重复（{len(ids)} 条）" if not dup else f"重复 {dup}"

    def c6():
        maxid = max(int(c.split("-")[-1]) for c in ids)
        return maxid == 34, f"最大编号为 {maxid}（应为 34，新 ID 从 0029 起递增分配）"

    # ── 归属唯一性与身份完整性（门禁 4、5、6、7、8） ───────────────────────
    def c7():
        seen, dup = {}, []
        for c in canon:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                if k in seen:
                    dup.append(f"{k[0]}::{k[1]}（{seen[k]} 与 {c['canonical_id']}）")
                seen[k] = c["canonical_id"]
        return not dup, f"每项原始身份最多一个 canonical，共 {len(seen)} 个身份" if not dup else f"重复 {dup}"

    def c8():
        bad = []
        for c in own_canon:
            for r in c["upstream_refs"]:
                if (r["upstream_id"], r["original_capability_id"]) not in by_key:
                    bad.append(f"{c['canonical_id']}::{r['upstream_id']}::{r['original_capability_id']}")
        return not bad, f"Product 的 {len(own_owned)} 个原始来源全部可在原始索引定位" if not bad else f"查无 {bad}"

    def c9():
        # 承接必须正确晋升：来自路由表的身份，草稿里不能再留它
        bad = []
        for r in promos_to_own:
            k = (r.get("upstream_id"), r.get("original_capability_id"))
            if k in routed_by_owner.get(MODULE, set()):
                bad.append(f"{k[0]}::{k[1]} 已晋升却仍留在 Product 分流表")
            if r.get("from") not in {"cross_module_redirections", "unreviewed_adopted"}:
                bad.append(f"{k[0]}::{k[1]} from 取值非法 {r.get('from')}")
            if r.get("from") == "unreviewed_adopted" and r.get("was_in_redirection_table"):
                bad.append(f"{k[0]}::{k[1]} 声称未审直采却本来在路由表")
        return not bad, f"晋升 {len(promos_to_own)} 条，问题 {bad or '无'}"

    def c10():
        # 本批新增分流不得与本批已映射身份重叠
        clash = own_owned & set().union(*routed_by_owner.values()) if routed_by_owner else set()
        return not clash, f"新增分流与本批映射零重叠" if not clash else f"重叠 {sorted(clash)}"

    def c11():
        mapped = {(r["upstream_id"], r["original_capability_id"]) for c in canon for r in c["upstream_refs"]}
        rted = {(r["upstream_id"], r["original_capability_id"]) for r in routed}
        unrev = set(by_key) - mapped - rted
        total = len(mapped) + len(rted) + len(unrev)
        ok = total == len(by_key) == 143 and not (mapped & rted)
        return ok, f"mapped {len(mapped)} + routed {len(rted)} + unreviewed {len(unrev)} = {total}；mapped∩routed 为空={not (mapped & rted)}"

    def c12():
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
        return ok and inv_ok, (f"global_state_counts 与实算一致 mapped={len(mapped)} routed={len(rted)} "
                              f"unreviewed={len(unrev)} canonical={len(canon)}；四条不变量={inv_ok}")

    def c13():
        t = prog["totals"]
        g = draft["global_state_counts"]
        need = ["mapped_count", "routed_pending_count", "unreviewed_count", "canonical_count", "sum_check"]
        missing = [k for k in need if k not in t]
        stale = [k for k in ("raw_assigned", "raw_pending", "canonical_total") if k in t]
        agree = all(t.get(k) == g.get(k) for k in need if k in t)
        return (not missing and not stale and agree,
                f"缺失 {missing or '无'}；旧口径残留 {stale or '无'}；与草稿一致={agree}；sum_check={t.get('sum_check')}")

    # ── 批次视图 ─────────────────────────────────────────────────────────
    def c14():
        b = next((x for x in draft.get("batches", []) if x["module"] == MODULE), None)
        if b is None:
            return False, "草稿中没有 Product 批次记录"
        # 出向分流按统计契约是现算视图（def 声明 − 已晋升）。Product 的 def 声明了 2 条
        # 分流且尚无目标模块承接，故批次值应为 2；本批映射身份里不含这两个键。
        ok = (b["raw_mapped_to_this_module"] == len(own_owned) == 10
              and b["canonical_ids"] == OWN_IDS
              and b["raw_redirected_to_other_modules"] == 2
              and len(own_owned) == 10)
        return ok, (f"mapped={b['raw_mapped_to_this_module']}（实际 {len(own_owned)}）；"
                    f"redirected={b['raw_redirected_to_other_modules']}；ids 齐备={b['canonical_ids'] == OWN_IDS}")

    def c15():
        names = [b["module"] for b in draft.get("batches", [])]
        order = ["Facts", "Collector", "Evidence-Claims", "Product"]
        return names[:4] == order, f"批次按业务顺序排列：{names}"

    def c16():
        # 历史批次条目必须仍在，且 mapped 定格
        bf = next((x for x in draft["batches"] if x["module"] == "Facts"), None)
        bc = next((x for x in draft["batches"] if x["module"] == "Collector"), None)
        be = next((x for x in draft["batches"] if x["module"] == "Evidence-Claims"), None)
        if not (bf and bc and be):
            return False, "Facts/Collector/EC 批次条目丢失"
        ok = (bf["raw_mapped_to_this_module"] == 11 and bc["raw_mapped_to_this_module"] == 11
              and be["raw_mapped_to_this_module"] == 12)
        return ok, (f"Facts {bf['raw_mapped_to_this_module']}、Collector {bc['raw_mapped_to_this_module']}、"
                    f"EC {be['raw_mapped_to_this_module']} 均定格未变")

    # ── 模块职责边界（门禁 9） ───────────────────────────────────────────
    def c17():
        # Product 的 canonical 不得声明自己实现采集/抽取/证据裁决/持久化/渲染
        forbidden = ["GitHub API", "gh api", "分页取数", "树结构采集", "裁决状态机迁移",
                     "持久化布局", "Markdown 渲染", "报告模板生成"]
        bad = []
        for c in own_canon:
            blob = json.dumps(c, ensure_ascii=False)
            for f in forbidden:
                if f in blob and "不得" not in blob:
                    bad.append(f"{c['canonical_id']} 含越界职责表述「{f}」且未加否定")
        return not bad, f"Product 六条未声明其它模块职责，问题 {bad or '无'}"

    def c18():
        # 依赖只能指向已存在模块
        bad = []
        for c in own_canon:
            for d in c["dependencies"]:
                if d not in MODULES:
                    bad.append(f"{c['canonical_id']} 依赖非法模块 {d}")
        return not bad, f"依赖模块取值合法，问题 {bad or '无'}"

    def c19():
        # 前三个批次的 owner 未被本批改动
        bad = []
        for cid in list(FACTS_IDS) + list(COLLECTOR_IDS) + list(EC_IDS):
            c = next((x for x in canon if x["canonical_id"] == cid), None)
            if c is None:
                bad.append(f"{cid} 丢失")
            elif cid in FACTS_IDS and c["owner_module"] != "Facts":
                bad.append(f"{cid} owner 变为 {c['owner_module']}")
            elif cid in COLLECTOR_IDS and c["owner_module"] != "Collector":
                bad.append(f"{cid} owner 变为 {c['owner_module']}")
            elif cid in EC_IDS and c["owner_module"] != "Evidence-Claims":
                bad.append(f"{cid} owner 变为 {c['owner_module']}")
        return not bad, f"前三批 28 条 owner 全部未变" if not bad else f"{bad}"

    # ── 语义区分（门禁 10） ───────────────────────────────────────────────
    def c20():
        # 声明不能替代实现证据：八要素必须强制 claim_type + evidence_refs
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0029")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["claim_type", "evidence_refs", "fact", "declaration", "inference", "unknown"]
        miss = [k for k in need if k not in blob]
        has_rule = "evidence_refs 为空时 claim_type 只能是 inference 或 unknown" in blob
        return (not miss and has_rule), (f"八要素与四值齐备={not miss}" +
                                         (f"，缺 {miss}" if miss else "") + f"；空引用降级硬规则={has_rule}")

    def c21():
        # 未知项必须保留：五字段全部 MUST，且带 owner/resolved_by
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0033")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["why_unknown", "owner", "resolved_by", "MUST", "open", "superseded"]
        miss = [k for k in need if k not in blob]
        return not miss, f"未知项五字段与生命周期齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c22():
        # 产品未知项 ≠ 技术执行失败 ≠ insufficient_evidence
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0033")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("不等于 insufficient_evidence" in blob and "取数失败不等于产品未知" in blob
              and "技术执行失败" in blob)
        return ok, "产品未知项 / 裁决证据不足 / 技术执行失败 三者已显式区分"

    def c23():
        # 集成三态：有配置≠在运行，且不得静默省略
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0030")
        blob = json.dumps(c, ensure_ascii=False)
        need = ["confirmed_runtime", "configured_boundary", "integration_unknown", "不得静默省略"]
        miss = [k for k in need if k not in blob]
        return not miss, f"集成三态与「有配置必须有条目」规则齐备={not miss}" + (f"，缺 {miss}" if miss else "")

    def c24():
        # 功能关系可追溯：实体关系必须带 evidence_refs
        c = next(x for x in own_canon if x["canonical_id"] == "SL-CAP-0031")
        blob = json.dumps(c, ensure_ascii=False)
        ok = ("evidence_refs" in blob and "判定清单" in blob and "entity_relation" in blob)
        return ok, "实体关系带 evidence_refs，实体判定有可核对清单"

    # ── 内容完整性与职责结构（门禁 11） ────────────────────────────────────
    def c25():
        bad = []
        for c in own_canon:
            if not c.get("upstream_refs") and not c.get("merge_note"):
                bad.append(f"{c['canonical_id']} 无来源且无独立设计理由")
            if c["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                bad.append(f"{c['canonical_id']} 非法处置 {c['disposition']}")
            if not c.get("input_boundary") or not c.get("output_boundary") or not c.get("v1_scope"):
                bad.append(f"{c['canonical_id']} 缺 I/O 边界或 V1 scope")
            if not c.get("merge_note"):
                bad.append(f"{c['canonical_id']} 缺 merge_note")
        return not bad, f"六条来源/处置/边界/理由齐备，问题 {bad or '无'}"

    def c26():
        bad = []
        for c in own_canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可未逐源记录")
            if c["owner_module"] != MODULE:
                bad.append(f"{c['canonical_id']} owner={c['owner_module']}")
        return not bad, f"逐源许可 {sum(len(c['license_permission']['per_upstream']) for c in own_canon)} 条，问题 {bad or '无'}"

    def c27():
        # CC-BY-4.0（UPSTREAM-03）的额外义务：许可链接 + 修改声明
        bad = []
        for c in own_canon:
            for p in c["license_permission"]["per_upstream"]:
                if p["upstream_id"] == "UPSTREAM-03":
                    if not (p.get("attribution_required") and p.get("license_link_required")
                            and p.get("modification_notice_required")):
                        bad.append(f"{c['canonical_id']} CC-BY 三项义务不全")
        return not bad, f"UPSTREAM-03 来源逐条履行署名/许可链接/修改声明，问题 {bad or '无'}"

    def c28():
        dist = {}
        for c in own_canon:
            dist[c["disposition"]] = dist.get(c["disposition"], 0) + 1
        return True, f"（信息）Product 处置分布 {dist}"

    # ── 文档一致性（门禁 12） ─────────────────────────────────────────────
    def c29():
        if not DOC.exists():
            return False, f"决策文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        missing = [i for i in OWN_IDS if i not in txt]
        b = next(x for x in draft["batches"] if x["module"] == MODULE)
        nums = [b["raw_mapped_to_this_module"], len(b["canonical_ids"]),
                b["raw_redirected_to_other_modules"]]
        nums_ok = all(str(n) in txt for n in nums)
        g = draft["global_state_counts"]
        gnums = [g["raw_total"], g["mapped_count"], g["routed_pending_count"],
                 g["unreviewed_count"], g["sum_check"]]
        gnums_ok = all(str(n) in txt for n in gnums)
        return (not missing and nums_ok and gnums_ok,
                f"缺失 ID={missing or '无'}；批次数字 {nums} 出现={nums_ok}；"
                f"全局数字 {gnums} 出现={gnums_ok}")

    def c30():
        # 决策文档必须逐条交代误合并防护（第 4 节六项 A–F）
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = ["A.", "B.", "C.", "D.", "E.", "F."]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"误合并防护 A–F 逐条落章，缺 {miss or '无'}"

    def c31():
        # 第 5 节五条验证语义必须落章
        if not DOC.exists():
            return False, "决策文档不存在"
        txt = DOC.read_text(encoding="utf-8")
        anchors = ["P-1", "P-2", "P-3", "P-4", "P-5"]
        miss = [a for a in anchors if a not in txt]
        return not miss, f"产品验证语义 P-1..P-5 逐条落章，缺 {miss or '无'}"

    # ── 隔离与冻结（门禁 13、14） ─────────────────────────────────────────
    def c32():
        g = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        return g.returncode == 0, "原始能力索引逐字节未变"

    def c33():
        g = git("diff", "--quiet", "HEAD", "--",
                *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        return g.returncode == 0, "六份历史上游审计未改动"

    def c34():
        g = git("status", "--short", "--", "src/", "tests/", "schemas/")
        return g.stdout.strip() == "", "src/tests/schemas 无改动" if not g.stdout.strip() else g.stdout.strip()

    def c35():
        return not (F / "CAPABILITY_CROSSWALK.json").exists(), "正式交叉表尚未冻结（F1-D 前不得发布）"

    def c36():
        # 本轮不设计数据库：不得新增 schema 文件
        g = git("status", "--short", "--", "schemas/")
        new = [l for l in g.stdout.splitlines() if "product" in l.lower() or "schema" in l.lower()]
        return not new, f"未新增 Product schema（schemas/ 无相关变动 {new or '无'}）"

    # ── 幂等与复用 ────────────────────────────────────────────────────────
    def c37():
        # 构建器必须幂等：重跑后批次与全局数字不变
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1b_build_product.py")],
                           cwd=ROOT, capture_output=True, text=True)
        return r.returncode == 0, f"重建 exit={r.returncode}（幂等性由 c38 交叉验证）"

    def c38():
        d2 = json.loads(DRAFT.read_text(encoding="utf-8"))
        g1, g2 = draft["global_state_counts"], d2["global_state_counts"]
        b1, b2 = draft["batch_summary"], d2["batch_summary"]
        ok = (g1["mapped_count"] == g2["mapped_count"] and
              g1["routed_pending_count"] == g2["routed_pending_count"] and
              g1["unreviewed_count"] == g2["unreviewed_count"] and
              g1["canonical_count"] == g2["canonical_count"] and
              b1["module"] == b2["module"] == MODULE)
        return ok, (f"重跑前后 mapped {g1['mapped_count']}→{g2['mapped_count']}、"
                    f"routed {g1['routed_pending_count']}→{g2['routed_pending_count']}、"
                    f"unrev {g1['unreviewed_count']}→{g2['unreviewed_count']}、"
                    f"canon {g1['canonical_count']}→{g2['canonical_count']}")

    def c39():
        # 承接声明数量必须与 def 一致（防编造迁移）
        sys.path.insert(0, str(ROOT / "tools" / "fusion"))
        import f1b_product_def as pd
        declared = set(pd.CONSUMED_THIS_BATCH)
        referenced = {(u, o) for c in pd.CANON for (u, o, _v) in c["refs"]}
        moved = set(pd.DEFERRED_TO_OTHER_MODULE)
        ok = declared == referenced and not (declared & moved)
        return ok, (f"承接声明 {len(declared)} 与 canonical 引用 {len(referenced)} 一致={declared == referenced}；"
                    f"与分流零重叠={not (declared & moved)}")

    def c40():
        # 每条 canonical 至少有一个来源（本批无独立设计条目）
        bad = [c["canonical_id"] for c in own_canon if not c["upstream_refs"]]
        return not bad, f"六条均有上游来源" if not bad else f"无来源 {bad}"

    def c41():
        # 所有 6 条 v1_scope 合法
        bad = [c["canonical_id"] for c in own_canon
               if c["v1_scope"] not in {"V1_REQUIRED", "V1_REQUIRED_LIMITED", "V1_DEFERRED"}]
        return not bad, f"V1 scope 取值全部合法，问题 {bad or '无'}"

    def c42():
        # unresolved 必须显式存在（不得假装没有待定项）
        bad = [c["canonical_id"] for c in own_canon if "unresolved" not in c]
        n = sum(len(c.get("unresolved") or []) for c in own_canon)
        return not bad, f"六条均带 unresolved 字段，合计 {n} 项待定"

    def c43():
        # 新增分流的目标模块必须合法且不等于 Product 自身
        bad = []
        expected = {("UPSTREAM-03", "C15"): "Renderer", ("UPSTREAM-03", "C08"): "Lifecycle"}
        for k, mod in expected.items():
            r = next((x for x in routed if (x["upstream_id"], x["original_capability_id"]) == k), None)
            if r is None:
                bad.append(f"{k} 未落盘为分流")
            elif r["owner_module"] != mod:
                bad.append(f"{k} 去向记为 {r['owner_module']}，应为 {mod}")
        for r in routed:
            if r["owner_module"] not in MODULES:
                bad.append(f"{r['upstream_id']}::{r['original_capability_id']} 模块名非法")
        return not bad, f"本批 2 条新增分流去向正确，问题 {bad or '无'}"

    check("c1", "原始索引 143 项且身份唯一", c1)
    check("c2", "原有 28 条 canonical 完整保留", c2)
    check("c3", "Product 编号 0029-0034 齐全", c3)
    check("c4", "canonical_id 从 0001 连续", c4)
    check("c5", "canonical_id 无重复", c5)
    check("c6", "最大编号为 0034（新 ID 从 0029 起）", c6)
    check("c7", "每个原始身份最多一个 canonical", c7)
    check("c8", "Product 原始来源真实存在", c8)
    check("c9", "承接的 ROUTED 身份已正确晋升", c9)
    check("c10", "新增分流与本批映射零重叠", c10)
    check("c11", "三态互斥且合计 143", c11)
    check("c12", "global_state_counts 与实算一致", c12)
    check("c13", "进度统计与草稿同源", c13)
    check("c14", "Product 批次记录与引用自洽", c14)
    check("c15", "批次按业务顺序排列", c15)
    check("c16", "历史三批 mapped 定格未变", c16)
    check("c17", "Product 未越界声明其它模块职责", c17)
    check("c18", "依赖模块取值合法", c18)
    check("c19", "前三批 28 条 owner 未变", c19)
    check("c20", "声明不可替代实现证据", c20)
    check("c21", "未知项五字段与生命周期齐备", c21)
    check("c22", "未知项/裁决不足/执行失败三者区分", c22)
    check("c23", "集成三态且不得静默省略", c23)
    check("c24", "功能关系可追溯", c24)
    check("c25", "来源/处置/边界/理由齐备", c25)
    check("c26", "逐源许可且 owner 唯一", c26)
    check("c27", "CC-BY-4.0 三项义务完整", c27)
    check("c28", "处置分布（信息）", c28)
    check("c29", "决策文档与 JSON 数量及身份一致", c29)
    check("c30", "误合并防护 A-F 逐条落章", c30)
    check("c31", "产品验证语义 P-1..P-5 逐条落章", c31)
    check("c32", "原始能力索引未改动", c32)
    check("c33", "六份上游审计未改动", c33)
    check("c34", "src/tests/schemas 无改动", c34)
    check("c35", "正式交叉表未提前冻结", c35)
    check("c36", "未新增 Product schema", c36)
    check("c37", "增量构建可重复执行", c37)
    check("c38", "重复运行幂等（数字不变）", c38)
    check("c39", "承接声明与 def 一致且与分流零重叠", c39)
    check("c40", "每条 canonical 均有来源", c40)
    check("c41", "V1 scope 取值合法", c41)
    check("c42", "unresolved 显式存在", c42)
    check("c43", "新增分流去向正确", c43)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-B / Product",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1b_verify_product.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": total, "result": "PASS" if passed == total else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} PASS -> {OUT.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
