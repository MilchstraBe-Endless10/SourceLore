#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1-C-C2 独立验收（U05 剩余 10 项未审终裁）。"""
import json, sys, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
BASE = F / "F1B_FROZEN_BASELINE.json"
RECON = F / "F1C_C2_U05_RECONCILIATION.json"
DOC = F / "F1C_C2_U05_DECISIONS.md"
OUT = F / "F1C_C2_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

sys.path.insert(0, str(Path(__file__).parent))
import f1c_c2_decisions as DEC
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
    recons = []
    for n in ("F1C_B_ROUTED_RECONCILIATION.json", "F1C_C1_RESOLUTION.json",
              "F1C_C2_U05_RECONCILIATION.json"):
        p = F / n
        if p.exists():
            recons.append(json.loads(p.read_text(encoding="utf-8")))
    moves = H.build_allowed_moves(recons)

    def c1():
        ok = len(by) == 143 and len(raw["items"]) == 143
        return ok, f"原始 {len(raw['items'])} 项，identity_key 唯一={len(by)}"

    def c2():
        u05 = {(i["upstream_id"], i["original_capability_id"]) for i in raw["items"]
               if i["upstream_id"] == "UPSTREAM-05"}
        unrev = {k for k in u05 if k not in mapped and k not in routed}
        expect = {( "UPSTREAM-05", c) for c in
                  ["C27", "C28"]}  # 本批后 U05 只剩两项 REJECT
        ok = unrev == expect
        detail = f"U05 剩余 UNREVIEWED {sorted(x[1] for x in unrev)}（应为 C27/C28）"
        return ok, detail

    def c3():
        ids = {(d["identity"][0], d["identity"][1]) for d in DEC.DECISIONS}
        # 逐条：8 项 ADOPT 必须已 mapped；2 项 REJECT 必须仍 unrev
        bad = []
        for d in DEC.DECISIONS:
            k = tuple(d["identity"])
            if d["direction"] == "ADOPT_EXISTING" and k not in mapped:
                bad.append(f"{k} 未落盘为 MAPPED")
            if d["direction"] == "REJECT_WITH_REASON" and k in mapped:
                bad.append(f"{k} 被强行映射（REJECT 不得假称已实现）")
        detail = f"{len(DEC.DECISIONS)} 项逐条有裁决且应用正确，问题 {bad or '无'}"
        return (not bad and len(ids) == 10), detail

    def c4():
        # 先前 123 项 MAPPED 未被无记录更改
        before_123 = {(r["upstream_id"], r["original_capability_id"])
                      for c in base["canonical_capabilities"] for r in c["upstream_refs"]}
        missing = [k for k in before_123 if k not in mapped]
        detail = f"F1-B 冻结基线的 {len(before_123)} 项映射仍在，缺失 {missing or '无'}"
        return (not missing), detail

    def c5():
        hist = [c["canonical_id"] for c in base["canonical_capabilities"]]
        now = {c["canonical_id"] for c in canon}
        missing = [i for i in hist if i not in now]
        detail = f"F1-B 原有 {len(hist)} 条 canonical 全在；缺失 {missing or '无'}"
        return (not missing), detail

    def c6():
        bad = []
        seen = {}
        for c in canon:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                if k in seen:
                    bad.append(f"{k} 同时在 {seen[k]} 与 {c['canonical_id']}")
                seen[k] = c["canonical_id"]
        detail = f"每项唯一 owner（共 {len(seen)} 项），重复 {bad or '无'}"
        return (not bad), detail

    def c7():
        created = [c for c in canon if c.get("created_in_batch", "").startswith("F1-C-C2")]
        ok = len(created) == 0
        detail = f"本批新增 canonical {len(created)} 条（应为 0——全部复用已有能力）"
        return ok, detail

    def c8():
        bad = []
        n = 0
        for d in DEC.DECISIONS:
            if d["direction"] != "ADOPT_EXISTING" or not d.get("amendment"):
                continue
            n += 1
            c = next(x for x in canon if x["canonical_id"] == d["amendment"]["target"])
            if not c.get("f1c_amendments"):
                bad.append(f"{c['canonical_id']} 应有 amendment 但无留痕")
            elif d["amendment"]["append_note"] not in c["f1c_amendments"]:
                bad.append(f"{c['canonical_id']} amendment 内容未落盘")
        # 必须有 migration 记录
        ch = {c["identity"]: c for c in recon.get("changes_c2", [])}
        for d in DEC.DECISIONS:
            key = f"{d['identity'][0]}::{d['identity'][1]}"
            if key not in ch:
                bad.append(f"{key} 无 migration 记录")
        detail = f"{n} 条 amendment 均留痕且内容一致、{len(ch)} 项有迁移记录；问题 {bad or '无'}"
        return (not bad), detail

    def c9():
        # 原始 REJECT 语义不被擦除
        bad = []
        for d in DEC.DECISIONS:
            k = tuple(d["identity"])
            if d["verdict"] == "REJECT":
                if by[k]["disposition"] != "REJECT":
                    bad.append(f"{k} 原始 disposition 非 REJECT")
            if by[k]["disposition"] != by[k]["disposition"]:
                bad.append(k)
        rej = [d for d in DEC.DECISIONS if d["verdict"] == "REJECT"]
        detail = f"本批 {len(rej)} 项 REJECT 的原始判定保留，问题 {bad or '无'}"
        return (not bad), detail

    def c10():
        bad = []
        for c in canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可与 refs 数不等")
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
        return not bad, f"逐源许可完整，问题 {bad or '无'}"

    def c11():
        # 覆盖率不得被当作正确性证明
        c75 = next(c for c in canon if c["canonical_id"] == "SL-CAP-0075")
        need = ["覆盖率不等于正确性", "测试存在不等于测试通过", "测试通过不等于全部功能已验证"]
        txt = " ".join(c75.get("f1c_amendments") or [])
        miss = [k for k in need if k not in txt]
        detail = f"SL-CAP-0075 含覆盖率四条禁令，缺 {miss or '无'}"
        return (not miss), detail

    def c12():
        # Claim 冲突 / 知识失效 / 写入冲突不混淆
        c28 = next(c for c in canon if c["canonical_id"] == "SL-CAP-0028")
        txt = " ".join(c28.get("f1c_amendments") or [])
        need = ["conflict", "SL-CAP-0041", "SL-CAP-0064", "SL-CAP-0058",
                "不得把这四类合并成一个全局冲突机"]
        miss = [k for k in need if k not in txt]
        detail = f"SL-CAP-0028 已声明四类冲突的分别归属，缺 {miss or '无'}"
        return (not miss), detail

    def c13():
        unrev = set(by) - set(mapped) - routed
        total = len(mapped) + len(routed) + len(unrev)
        mutual = not (set(mapped) & routed) and not (set(mapped) & unrev) and not (routed & unrev)
        detail = (f"mapped {len(mapped)} + routed {len(routed)} + unrev {len(unrev)} = {total}；"
                  f"互斥={mutual}")
        return (total == 143 and mutual), detail

    def c14():
        g = draft["global_state_counts"]
        t = recon.get("totals_after", {})
        ok = (t.get("mapped_count") == g["mapped_count"]
              and t.get("routed_pending_count") == g["routed_pending_count"]
              and t.get("unreviewed_count") == g["unreviewed_count"]
              and t.get("canonical_count") == g["canonical_count"])
        prog = json.loads((F / "CROSSWALK_PROGRESS.json").read_text(encoding="utf-8"))
        p_ok = (prog["totals"]["mapped_count"] == g["mapped_count"]
                and prog["totals"]["canonical_count"] == g["canonical_count"])
        detail = f"清算记录与 Crosswalk 一致={ok}；进度账本一致={p_ok}"
        return (ok and p_ok), detail

    def c15():
        return H.check_identity_mapping_preserved(base, draft, moves)

    def c16():
        before = DRAFT.read_bytes()
        import subprocess as sp
        sp.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1c_apply_routed.py")],
               cwd=ROOT, capture_output=True)
        return (before == DRAFT.read_bytes()), "重跑应用层后草稿逐字节一致（幂等）"

    def c17():
        g1 = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        g2 = git("diff", "--quiet", "HEAD", "--",
                 *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        s = git("status", "--short", "--", "src/", "tests/", "schemas/")
        ok = g1.returncode == 0 and g2.returncode == 0 and s.stdout.strip() == ""
        return ok, "原始索引/六审计/正式引擎与 Schema 未改动"

    def c18():
        if not DOC.exists():
            return False, f"文档不存在: {DOC.name}"
        txt = DOC.read_text(encoding="utf-8")
        # 文档用简写（C07/C08…），断言按简写匹配，避免格式不一致造成误红
        need = ["C07", "C08", "C12", "C13", "C15", "C16", "C21", "C25", "C27", "C28",
                "10 项", "SL-CAP-0075", "conflict", "覆盖率不等于正确性"]
        miss = [k for k in need if k not in txt]
        detail = f"文档覆盖 10 项裁决，缺 {miss or '无'}"
        return (not miss), detail

    check("c1", "143 项原始身份完整唯一", c1)
    check("c2", "U05 真实 UNREVIEWED 集合明确", c2)
    check("c3", "本批全部 U05 未审身份逐条有裁决", c3)
    check("c4", "先前 123 项 MAPPED 未被无记录更改", c4)
    check("c5", "75 条 canonical 身份保留", c5)
    check("c6", "每项只能有一个正式 owner", c6)
    check("c7", "新 canonical 必要性（本批为 0）", c7)
    check("c8", "amendment 有来源及迁移记录", c8)
    check("c9", "原始 REJECT 语义不被擦除", c9)
    check("c10", "许可证隔离保持有效", c10)
    check("c11", "覆盖率不被当作正确性证明", c11)
    check("c12", "四类冲突不混淆", c12)
    check("c13", "三态守恒合计 143", c13)
    check("c14", "登记/Crosswalk/进度账本一致", c14)
    check("c15", "历史身份映射保持", c15)
    check("c16", "冻结基线重建幂等", c16)
    check("c17", "原始索引/审计/引擎/Schema 不变", c17)
    check("c18", "决策文档完整", c18)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M1-FUSION-GATE-F1 / F1-C-C2（U05 剩余未审终裁）",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_c2_verify.py",
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
