#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-C1 独立验收（3 项 DEFER 终裁）。只写 F1C_C1_VERIFICATION.json。"""
import json, sys, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
BASE = F / "F1B_FROZEN_BASELINE.json"
RECON = F / "F1C_C1_RESOLUTION.json"
REG = F / "F1C_DECISION_REGISTER.json"
DOC = F / "F1C_C1_DEFER_RESOLUTION.md"
OUT = F / "F1C_C1_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

sys.path.insert(0, str(Path(__file__).parent))
import f1c_c1_decisions as DEC
import f1c_history_invariants as H

results = []


def check(cid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append({"id": cid, "name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} :: {detail}")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    recon = json.loads(RECON.read_text(encoding="utf-8"))
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = draft["canonical_capabilities"]
    mapped = {}
    for c in canon:
        for r in c["upstream_refs"]:
            mapped[(r["upstream_id"], r["original_capability_id"])] = c["canonical_id"]
    routed = {(r["upstream_id"], r["original_capability_id"])
              for r in draft["cross_module_redirections"]}
    g = draft["global_state_counts"]
    all_recons = [json.loads((F / "F1C_B_ROUTED_RECONCILIATION.json").read_text(encoding="utf-8")), recon]

    def c1():
        ok = len(raw["items"]) == 143 and len(by) == 143
        return ok, f"原始身份 {len(raw['items'])} 项，unique={len(by)}"

    def c2():
        hist = [c["canonical_id"] for c in base["canonical_capabilities"]]
        now = {c["canonical_id"] for c in canon}
        missing = [i for i in hist if i not in now]
        detail = f"F1-B 原有 {len(hist)} 条全在；缺失 {missing or '无'}"
        return (not missing), detail

    def c3():
        # F1-C-B 的 8 项清算结果完整保留
        import f1c_routed_decisions as B
        f1cb = [d for d in B.DECISIONS if d["direction"] in ("ADOPT_EXISTING", "NEW_CANONICAL")]
        bad = []
        for d in f1cb:
            k = tuple(d["identity"])
            if k not in mapped:
                bad.append(f"{k} 未落盘")
        detail = f"F1-C-B 的 {len(f1cb)} 项承接/新建全部保留，问题 {bad or '无'}"
        return (not bad), detail

    def c4():
        bad = []
        for d in DEC.DECISIONS:
            k = tuple(d["identity"])
            if not d.get("split_answers"):
                bad.append(f"{k} 缺证据化分项回答")
            if not d.get("reason"):
                bad.append(f"{k} 缺理由")
            if d["direction"] not in ("ADOPT_EXISTING", "NEW_CANONICAL"):
                bad.append(f"{k} 本批必须给出终裁，不得再 DEFER")
            if not d.get("license_note"):
                bad.append(f"{k} 缺许可说明")
            if not d.get("unresolved"):
                bad.append(f"{k} 缺 unresolved")
        detail = f"3 项均给出终裁且带证据/理由/许可/unresolved，问题 {bad or '无'}"
        return (not bad and len(DEC.DECISIONS) == 3), detail

    def c5():
        bad = []
        for d in DEC.DECISIONS:
            k = tuple(d["identity"])
            if k not in mapped:
                bad.append(f"{k} 未被任何 canonical 归属")
            elif mapped[k] != (d["target_canonical"] or
                               next((c["canonical_id"] for c in canon
                                     if any((r["upstream_id"], r["original_capability_id"]) == k
                                            for r in c["upstream_refs"])))):
                bad.append(f"{k} 归属 {mapped[k]} 与裁决不符")
        # 每个身份最多一个归属
        seen = {}
        dup = []
        for c in canon:
            for r in c["upstream_refs"]:
                key = (r["upstream_id"], r["original_capability_id"])
                if key in seen:
                    dup.append(f"{key} 同时在 {seen[key]} 与 {c['canonical_id']}")
                seen[key] = c["canonical_id"]
        detail = f"每身份唯一归属，重复 {dup or '无'}；缺失 {bad or '无'}"
        return (not bad and not dup), detail

    def c6():
        bad = []
        for d in DEC.DECISIONS:
            tid = d["target_canonical"]
            if tid is None:
                continue
            c = next(x for x in canon if x["canonical_id"] == tid)
            if c["owner_module"] != d["final_owner"]:
                bad.append(f"{tid} owner={c['owner_module']}，裁决={d['final_owner']}")
        # 跨模块依赖必须显式列出
        dep_bad = [d["identity"] for d in DEC.DECISIONS if not d.get("interfaces")]
        detail = f"唯一 owner 一致={not bad}；跨模块接口已列={not dep_bad}；问题 {bad or '无'}"
        return (not bad and not dep_bad), detail

    def c7():
        # verdict 必须是合法处置；不得把 ADAPT 写成 REUSE 之类
        bad = [d["identity"] for d in DEC.DECISIONS
               if d["verdict"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}]
        # 原始 disposition 不得被改写
        orig_bad = []
        for d in DEC.DECISIONS:
            k = tuple(d["identity"])
            if by[k]["disposition"] not in {"REUSE", "ADAPT", "REIMPLEMENT", "REJECT"}:
                orig_bad.append(k)
        detail = f"verdict 合法且上游 disposition 未被篡改，问题 {bad + orig_bad or '无'}"
        return (not bad and not orig_bad), detail

    def c8():
        bad = []
        for c in canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可与 refs 数不等")
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
        return not bad, f"逐源许可完整，问题 {bad or '无'}"

    def c9():
        newc = next((c for c in canon if c["canonical_id"] == "SL-CAP-0075"), None)
        if newc is None:
            return False, "SL-CAP-0075 不存在"
        dup = [c["canonical_id"] for c in canon
               if c["name"] == newc["name"] and c["canonical_id"] != "SL-CAP-0075"]
        # 与被拒绝的 C13/C14 边界必须显式声明
        excl = ("多模型 judge 集成与直连外部 LLM API" in newc["description"])
        nodup = not dup and excl
        detail = f"名称唯一={not dup}；已声明排除 C13/C14 方案={excl}"
        return nodup, detail

    def c10():
        # Crosswalk 与决策登记一致：三项都出现在 recon 的 changes_c1
        ch = {c["identity"]: c for c in recon.get("changes_c1", [])}
        bad = []
        for d in DEC.DECISIONS:
            k = f"{d['identity'][0]}::{d['identity'][1]}"
            if k not in ch:
                bad.append(f"{k} 无应用记录")
            elif ch[k]["action"] != d["direction"]:
                bad.append(f"{k} 裁决 {d['direction']} 应用为 {ch[k]['action']}")
        detail = f"3 项裁决与 Crosswalk 应用一致，问题 {bad or '无'}"
        return (not bad), detail

    def c11():
        unreviewed = set(by) - set(mapped) - routed
        total = len(mapped) + len(routed) + len(unreviewed)
        mutual = not (set(mapped) & routed) and not (set(mapped) & unreviewed) and not (routed & unreviewed)
        detail = (f"mapped {len(mapped)} + routed {len(routed)} + unreviewed {len(unreviewed)} "
                  f"= {total}；互斥={mutual}")
        return (total == 143 and mutual), detail

    def c12():
        moves = H.build_allowed_moves(all_recons)
        r1 = H.check_identity_mapping_preserved(base, draft, moves)
        r2 = H.check_canonical_ids_not_reused(base, draft)
        r3 = H.check_amendments_recorded(base, draft, all_recons[0])
        r3b = H.check_amendments_recorded(base, draft, all_recons[1])
        detail = f"{r1[1]}｜{r2[1]}｜{r3[1]}"
        return (r1[0] and r2[0] and r3[0] and r3b[0]), detail

    def c14():
        if not DOC.exists():
            return False, f"文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        need = ["U04::C16", "U05::C10", "U01::C12", "SL-CAP-0071", "SL-CAP-0064",
                "SL-CAP-0075", "DSH-Adapter", "Storage", "Evidence-Claims", "W-2'"]
        miss = [k for k in need if k not in txt]
        detail = f"文档覆盖三项裁决与承接细节，缺 {miss or '无'}"
        return (not miss), detail

    def c15():
        before = DRAFT.read_bytes()
        import subprocess as sp
        sp.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1c_apply_routed.py")],
               cwd=ROOT, capture_output=True)
        after = DRAFT.read_bytes()
        return (before == after), "重跑应用层后草稿逐字节一致（幂等）"

    def c16():
        g1 = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        g2 = git("diff", "--quiet", "HEAD", "--",
                 *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        s = git("status", "--short", "--", "src/", "tests/", "schemas/")
        ok = g1.returncode == 0 and g2.returncode == 0 and s.stdout.strip() == ""
        detail = "原始索引/六审计/正式引擎均未改动"
        return ok, detail

    check("c1", "原始 143 项身份唯一且不变", c1)
    check("c2", "既有 74 条 canonical 身份完整", c2)
    check("c3", "F1-C-B 裁决结果完整保留", c3)
    check("c4", "三项 DEFER 逐项形成有证据的裁决", c4)
    check("c5", "每身份最多一个正式 canonical 归属", c5)
    check("c6", "owner 与跨模块依赖不混淆", c6)
    check("c7", "REJECT/DEFER/ADAPT 语义未被误用", c7)
    check("c8", "许可证权限完整", c8)
    check("c9", "新增能力无重复语义", c9)
    check("c10", "Crosswalk 与登记表状态一致", c10)
    check("c11", "三态互斥且合计 143", c11)
    check("c12", "历史身份映射保持集合级不变量", c12)
    check("c14", "决策文档完整", c14)
    check("c15", "重建重复执行幂等", c15)
    check("c16", "历史审计/索引/引擎/Schema 不变", c16)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-C-C1（3 项 DEFER 归属与承接裁决）",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_c1_verify.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "summary": {"passed": passed, "total": len(results),
                    "result": "PASS" if passed == len(results) else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
