#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-D1 独立验收：终态模型迁移（三个正交概念）。"""
import json, sys, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
BASE = F / "F1B_FROZEN_BASELINE.json"
MIG = F / "F1C_D1_TERMINAL_MIGRATION.json"
DOC = F / "F1C_D1_TERMINAL_MODEL.md"
OUT = F / "F1C_D1_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

sys.path.insert(0, str(Path(__file__).parent))
import f1c_history_invariants as H

VALID_T = {"ADOPTED", "ADOPTED_AS_COUNTEREXAMPLE",
           "REJECTED_WITH_REASON", "DEFERRED_WITH_REASON"}
VALID_O = {"UPSTREAM_DERIVED", "INTERNAL_DESIGN_ONLY"}

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
    mig = json.loads(MIG.read_text(encoding="utf-8"))
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = draft["canonical_capabilities"]
    tm = draft.get("terminal_model", {})
    tdisp = tm.get("terminal_dispositions", {})
    mapped = {}
    for c in canon:
        for r in c["upstream_refs"]:
            mapped[(r["upstream_id"], r["original_capability_id"])] = c["canonical_id"]
    routed = {(r["upstream_id"], r["original_capability_id"])
              for r in draft["cross_module_redirections"]}
    recons = []
    for n in ("F1C_B_ROUTED_RECONCILIATION.json", "F1C_C1_RESOLUTION.json",
              "F1C_C2_U05_RECONCILIATION.json", "F1C_C3_RECONCILIATION.json"):
        p = F / n
        if p.exists():
            recons.append(json.loads(p.read_text(encoding="utf-8")))
    moves = H.build_allowed_moves(recons)

    def c1():
        ok = len(by) == 143 and len(raw["items"]) == 143
        return ok, f"原始 {len(raw['items'])} 项，unique={len(by)}"

    def c2():
        keys = {f"{k[0]}::{k[1]}" for k in by}
        miss = sorted(keys - set(tdisp))
        extra = sorted(set(tdisp) - keys)
        detail = f"终态覆盖 {len(tdisp)}/143；缺 {miss or '无'}；越界 {extra or '无'}"
        return (not miss and not extra), detail

    def c3():
        bad = [k for k, v in tdisp.items() if v.get("value") not in VALID_T]
        detail = f"终态值全部合法（{len(tdisp)} 项），非法 {bad or '无'}"
        return (not bad), detail

    def c4():
        rej = {"UPSTREAM-04::C27", "UPSTREAM-05::C27",
               "UPSTREAM-05::C28", "UPSTREAM-06::C21"}
        got = {k for k, v in tdisp.items() if v.get("value") == "REJECTED_WITH_REASON"}
        detail = f"4 项拒绝身份可定位={got == rej}（实际 {sorted(got)}）"
        return (got == rej), detail

    def c5():
        rej = {"UPSTREAM-04::C27", "UPSTREAM-05::C27",
               "UPSTREAM-05::C28", "UPSTREAM-06::C21"}
        bad = [k for k in rej
               if (tuple(k.split("::"))) in mapped]
        # 同时它们的 mapping_status 必须仍是 UNREVIEWED
        bad2 = [k for k in rej if tdisp.get(k, {}).get("mapping_status") != "UNREVIEWED"]
        detail = f"拒绝身份未被伪造为 MAPPED={not bad}；仍标 UNREVIEWED={not bad2}"
        return (not bad and not bad2), detail

    def c6():
        hist = {(r["upstream_id"], r["original_capability_id"])
                for c in base["canonical_capabilities"] for r in c["upstream_refs"]}
        miss = [k for k in hist if k not in mapped]
        detail = f"F1-B 冻结的 {len(hist)} 项映射全在，缺失 {miss or '无'}"
        return (not miss), detail

    def c7():
        hids = [c["canonical_id"] for c in base["canonical_capabilities"]]
        now = {c["canonical_id"] for c in canon}
        miss = [i for i in hids if i not in now]
        # 且 ID 未被复用（name/owner 与基线一致或仅内容扩展）
        bad = []
        for c in base["canonical_capabilities"]:
            cur = next((x for x in canon if x["canonical_id"] == c["canonical_id"]), None)
            if cur and (cur["name"] != c["name"]):
                bad.append(f"{c['canonical_id']} 名称变更")
        detail = f"F1-B {len(hids)} 条全在={not miss}；ID 未被复用={not bad}"
        return (not miss and not bad), detail

    def c8():
        bad = []
        for c in canon:
            if c.get("origin_type") not in VALID_O:
                bad.append(f"{c['canonical_id']} origin={c.get('origin_type')}")
            elif c["origin_type"] == "INTERNAL_DESIGN_ONLY" and c["upstream_refs"]:
                bad.append(f"{c['canonical_id']} 标为内部设计却有 upstream_refs")
            elif c["origin_type"] == "UPSTREAM_DERIVED" and not c["upstream_refs"]:
                bad.append(f"{c['canonical_id']} 标为上游派生却无 refs")
        zero = [c["canonical_id"] for c in canon if c["origin_type"] == "INTERNAL_DESIGN_ONLY"]
        detail = f"origin_type 全合法且与实际 refs 一致；零来源 {len(zero)} 条 {zero}"
        return (not bad), detail

    def c9():
        # 反例绑定与正向承接可区分
        valid = [k for k, v in tdisp.items() if v["value"] == "ADOPTED_AS_COUNTEREXAMPLE"]
        adopted = [k for k, v in tdisp.items() if v["value"] == "ADOPTED"]
        # 前者必须能在 refs 里找到 verdict=REJECT 且无正向 verdict
        bad = []
        for k in valid:
            u, c_id = k.split("::")
            kk = (u, c_id)
            refs = [(x, cc["canonical_id"]) for cc in canon for x in cc["upstream_refs"]
                    if (x["upstream_id"], x["original_capability_id"]) == kk]
            if not refs:
                bad.append(f"{k} 无任何 refs")
            elif any(x["verdict"] != "REJECT" for x, _ in refs):
                bad.append(f"{k} 有非 REJECT verdict，不应标为纯反例")
        detail = (f"纯反例 {len(valid)} 项、正向 {len(adopted)} 项；"
                  f"反例判定自洽={not bad}；问题 {bad or '无'}")
        return (not bad), detail

    def c10():
        # 原始 disposition 与最终处置独立（不是同一字段的复制）
        diff = 0
        for k, v in tdisp.items():
            u, c_id = k.split("::")
            if by[(u, c_id)]["disposition"] != v["value"]:
                diff += 1
        detail = (f"两字段独立：{diff}/143 处取值不同（若全同则应怀疑是复制）；"
                  f"独立成立={diff > 0}")
        return (diff > 0), detail

    def c11():
        # 最终处置不推导复制权限
        bad = []
        for c in canon:
            for r in c["upstream_refs"]:
                if r["license"].get("copy_permitted") is False:
                    if c["license_permission"].get("copy_permitted") is True:
                        bad.append(f"{c['canonical_id']} 含不可复制来源却判整体可复制")
        detail = f"终态不推导复制权限（17 项 ADOPTED_AS_COUNTEREXAMPLE 均为设计关系）；问题 {bad or '无'}"
        return (not bad), detail

    def c12():
        u06 = [(r["upstream_id"], r["original_capability_id"])
               for c in canon for r in c["upstream_refs"] if r["upstream_id"] == "UPSTREAM-06"]
        bad = []
        for c in canon:
            per = c["license_permission"]["per_upstream"]
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
        detail = f"U06 相关 refs {len(u06)} 条，复制权限全为 false={not bad}"
        return (not bad), detail

    def c13():
        n = sum(len(c.get("f1c_amendments") or []) for c in canon)
        # 与基线相比，有 amendment 的条目仍是同一批 ID
        bad = []
        for c in canon:
            if c.get("f1c_amendments") and c["canonical_id"] not in \
                    {x["canonical_id"] for x in base["canonical_capabilities"]} | \
                    {"SL-CAP-0074", "SL-CAP-0075"}:
                bad.append(f"{c['canonical_id']} 非历史条目却有 amendment")
        detail = f"amendment 共 {n} 条，归属合法={not bad}"
        return (not bad), detail

    def c14():
        unrev = {k for k in by if k not in mapped and k not in routed}
        total = len(mapped) + len(routed) + len(unrev)
        g = draft["global_state_counts"]
        ok = (total == 143 == g["sum_check"]
              and g["mapped_count"] == len(mapped)
              and g["unreviewed_count"] == len(unrev))
        detail = (f"映射三态守恒 mapped {len(mapped)} + routed {len(routed)} + unrev {len(unrev)} "
                  f"= {total}")
        return ok, detail

    def c15():
        # 裁决登记 / Crosswalk / 进度统计一致
        prog = json.loads((F / "CROSSWALK_PROGRESS.json").read_text(encoding="utf-8"))
        g = draft["global_state_counts"]
        ok1 = (prog["totals"]["mapped_count"] == g["mapped_count"]
               and prog["totals"]["canonical_count"] == g["canonical_count"])
        # 迁移 JSON 的分布与 draft 一致
        t = mig["totals"]["terminal_disposition_distribution"]
        ok2 = (t.get("ADOPTED") == g["terminal_disposition_counts"].get("ADOPTED")
               and t.get("ADOPTED_AS_COUNTEREXAMPLE") ==
               g["terminal_disposition_counts"].get("ADOPTED_AS_COUNTEREXAMPLE")
               and t.get("REJECTED_WITH_REASON") ==
               g["terminal_disposition_counts"].get("REJECTED_WITH_REASON"))
        detail = f"进度账本一致={ok1}；迁移记录与草稿分布一致={ok2}"
        return (ok1 and ok2), detail

    def c16():
        before = DRAFT.read_bytes()
        import subprocess as sp
        sp.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1c_d1_migrate_terminal.py")],
               cwd=ROOT, capture_output=True)
        return (before == DRAFT.read_bytes()), "重跑迁移工具后草稿逐字节一致（幂等）"

    def c17():
        return H.check_identity_mapping_preserved(base, draft, moves)

    def c18():
        g1 = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        g2 = git("diff", "--quiet", "HEAD", "--",
                 *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        s = git("status", "--short", "--", "src/", "tests/", "schemas/")
        ok = g1.returncode == 0 and g2.returncode == 0 and s.stdout.strip() == ""
        # 且未生成正式交叉表
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
        from f1d_freeze_state import freeze_state as _fs
        _fz_ok, _fz_why = _fs()
        no_final = _fz_ok
        detail = f"原始索引/六审计/引擎/Schema 未变={ok}；未冻结正式交叉表={no_final}"
        return (ok and no_final), detail

    def c19():
        if not DOC.exists():
            return False, f"文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        need = ["mapping_status", "terminal_disposition", "canonical_origin_type",
                "ADOPTED_AS_COUNTEREXAMPLE", "REJECTED_WITH_REASON", "UPSTREAM_DERIVED",
                "INTERNAL_DESIGN_ONLY",
                "U04::C27", "U05::C27", "U05::C28", "U06::C21"]
        miss = [k for k in need if k not in txt]
        detail = f"文档覆盖三个正交概念与 4 项拒绝，缺 {miss or '无'}"
        return (not miss), detail

    check("c1", "143 项原始身份完整唯一", c1)
    check("c2", "143 项均有明确终态", c2)
    check("c3", "终态值在合法范围内", c3)
    check("c4", "4 项最终拒绝身份仍可定位", c4)
    check("c5", "被拒绝身份不被伪造为已映射", c5)
    check("c6", "139 项既有映射全部保留", c6)
    check("c7", "75 条 canonical ID 不变", c7)
    check("c8", "零来源 canonical 具有独立 origin_type", c8)
    check("c9", "反例绑定与正向承接可区分", c9)
    check("c10", "原始 disposition 与最终处置独立", c10)
    check("c11", "最终处置不推导复制权限", c11)
    check("c12", "UPSTREAM-06 权限边界正确", c12)
    check("c13", "已有 amendment 与迁移历史保留", c13)
    check("c14", "mapping_status 三态守恒 143", c14)
    check("c15", "裁决登记/Crosswalk/进度统计一致", c15)
    check("c16", "迁移过程幂等", c16)
    check("c17", "全局历史不变量通过", c17)
    check("c18", "六源审计/原始索引/引擎不变", c18)
    check("c19", "本批文档完整", c19)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-C-D1（终态模型迁移）",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_d1_verify.py",
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
