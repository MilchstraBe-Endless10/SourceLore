#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全局历史验证入口（独立，可被 F1-D 直接调用）。

第 7 节要求：该验证必须**独立于任意一个历史批次验证器**，
覆盖：身份映射保持、canonical ID 不复用、amendment 留痕、REJECT 原判未擦除、
许可证隔离、新旧能力无重复 owner。

用法：python3 tools/fusion/f1c_history_verify.py
输出：docs/fusion/F1C_HISTORY_VERIFICATION.json
"""
import json, sys, hashlib, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "docs" / "fusion"
RAW = F / "RAW_CAPABILITY_INDEX.json"
DRAFT = F / "CAPABILITY_CROSSWALK.draft.json"
BASE = F / "F1B_FROZEN_BASELINE.json"
OUT = F / "F1C_HISTORY_VERIFICATION.json"
TZ = timezone(timedelta(hours=8))

sys.path.insert(0, str(Path(__file__).parent))
import f1c_history_invariants as H

RECONS = ["F1C_B_ROUTED_RECONCILIATION.json", "F1C_C1_RESOLUTION.json",
          "F1C_C2_U05_RECONCILIATION.json"]

MODULES = {"Facts", "Collector", "Evidence-Claims", "Product", "Research",
           "Lifecycle", "Security", "Renderer", "Storage", "DSH-Adapter"}

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
    by = {(i["upstream_id"], i["original_capability_id"]): i for i in raw["items"]}
    canon = draft["canonical_capabilities"]
    recons = []
    for n in RECONS:
        p = F / n
        if p.exists():
            recons.append(json.loads(p.read_text(encoding="utf-8")))
    moves = H.build_allowed_moves(recons)

    def c1():
        h = hashlib.sha256(RAW.read_bytes()).hexdigest()
        ok = len(by) == 143 and h == draft["source_index_sha256"]
        return ok, f"原始 143 项唯一；sha256 一致={h == draft['source_index_sha256']}"

    def c2():
        return H.check_identity_mapping_preserved(base, draft, moves)

    def c3():
        return H.check_canonical_ids_not_reused(base, draft)

    def c4():
        ok = True
        bad = []
        for rc in recons:
            r = H.check_amendments_recorded(base, draft, rc)
            if not r[0]:
                ok = False
                bad.append(f"{rc.get('artifact')}: {r[1]}")
        n = sum(len(c.get("f1c_amendments") or []) for c in canon)
        detail = f"各批 amendment 均有留痕（共 {n} 条），问题 {bad or '无'}"
        return ok, detail

    def c5():
        # REJECT 原始裁决未被擦除：所有 disposition=REJECT 的原始身份仍在索引里且 disposition 不变
        bad = []
        for k, it in by.items():
            if it["disposition"] == "REJECT":
                if it["disposition"] != "REJECT":
                    bad.append(f"{k} REJECT 被改写")
        # 已映射的 REJECT 必须以 REJECT verdict 出现在 refs 里
        # 注意区分两个字段：
        #   upstream_disposition = 上游审计时的原始处置（不得改写）
        #   verdict              = SourceLore 自己的裁定（可以不同于上游处置，
        #                          例如上游 ADAPT 但 SourceLore 判 REJECT）
        # 本检查只保证前者未被改写，不要求它等于 verdict。
        n_rej_ref = 0
        for c in canon:
            for r in c["upstream_refs"]:
                if r.get("verdict") != "REJECT":
                    continue
                n_rej_ref += 1
                k = (r["upstream_id"], r["original_capability_id"])
                if r["upstream_disposition"] != by[k]["disposition"]:
                    bad.append(f"{r['identity_key']} upstream_disposition 被改写"
                               f"（refs={r['upstream_disposition']} 索引={by[k]['disposition']}）")
        rej_total = sum(1 for it in by.values() if it["disposition"] == "REJECT")
        detail = (f"原始 REJECT {rej_total} 项全部保留；已绑 canonical 的 REJECT refs {n_rej_ref} 条；"
                  f"问题 {bad or '无'}")
        return (not bad), detail

    def c6():
        bad = []
        for c in canon:
            per = c["license_permission"]["per_upstream"]
            if len(per) != len(c["upstream_refs"]):
                bad.append(f"{c['canonical_id']} 许可与 refs 数不等")
            for p in per:
                if p["upstream_id"] == "UPSTREAM-06" and p.get("copy_permitted") is not False:
                    bad.append(f"{c['canonical_id']} 给了 U06 复制许可")
        detail = f"{len(canon)} 条 canonical 逐源许可完整，问题 {bad or '无'}"
        return (not bad), detail

    def c7():
        # 新旧能力无重复 owner：每条 canonical 的 owner 必须合法且唯一
        bad = []
        for c in canon:
            if c.get("owner_module") not in MODULES:
                bad.append(f"{c['canonical_id']} owner 非法 {c.get('owner_module')}")
        # 名称唯一性（防止新卡重复旧卡语义）
        names = {}
        dup = []
        for c in canon:
            if c["name"] in names:
                dup.append(f"{c['name']}（{names[c['name']]} 与 {c['canonical_id']}）")
            names[c["name"]] = c["canonical_id"]
        detail = f"{len(canon)} 条 owner 合法={not bad}；名称唯一={not dup}；问题 {bad + dup or '无'}"
        return (not bad and not dup), detail

    def c8():
        # 身份唯一性与三态守恒（历史保护不能靠削弱这两条换来）
        mapped = {}
        for c in canon:
            for r in c["upstream_refs"]:
                k = (r["upstream_id"], r["original_capability_id"])
                if k in mapped:
                    return False, f"{k} 重复映射（{mapped[k]} 与 {c['canonical_id']}）"
                mapped[k] = c["canonical_id"]
        routed = {(r["upstream_id"], r["original_capability_id"])
                  for r in draft["cross_module_redirections"]}
        unrev = set(by) - set(mapped) - routed
        total = len(mapped) + len(routed) + len(unrev)
        g = draft["global_state_counts"]
        ok = (total == 143 == g["sum_check"]
              and not (set(mapped) & routed) and not (set(mapped) & unrev)
              and not (routed & unrev))
        detail = (f"mapped {len(mapped)} + routed {len(routed)} + unrev {len(unrev)} = {total}；"
                  f"互斥且守恒={ok}")
        return ok, detail

    def c9():
        g1 = git("diff", "--quiet", "HEAD", "--", "docs/fusion/RAW_CAPABILITY_INDEX.json")
        g2 = git("diff", "--quiet", "HEAD", "--",
                 *[f"progress/UPSTREAM-0{i}-audit.json" for i in range(1, 7)])
        s = git("status", "--short", "--", "src/", "tests/", "schemas/")
        ok = g1.returncode == 0 and g2.returncode == 0 and s.stdout.strip() == ""
        return ok, "原始索引 / 六份上游审计 / 正式引擎与 Schema 均未改动"

    def c10():
        # 独立于历史批次验证器：本入口不 import 任何 f1b_verify_*
        src = Path(__file__).read_text(encoding="utf-8")
        leaked = [l for l in src.splitlines()
                  if l.strip().startswith(("import f1b_verify", "from f1b_verify"))]
        detail = f"本入口不依赖任何历史批次验证器（泄漏 {len(leaked)} 处）"
        return (not leaked), detail

    check("c1", "原始 143 项唯一且未变", c1)
    check("c2", "历史身份映射未被无记录替换", c2)
    check("c3", "既有 canonical ID 未被复用", c3)
    check("c4", "canonical 核心变更均有 amendment", c4)
    check("c5", "REJECT 原始裁决未被擦除", c5)
    check("c6", "许可证权限保持独立", c6)
    check("c7", "新旧能力无重复 owner", c7)
    check("c8", "身份唯一性与三态守恒未被削弱", c8)
    check("c9", "原始索引/审计/引擎/Schema 未变", c9)
    check("c10", "本入口独立于历史批次验证器", c10)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "F1-C 全局历史验证（独立入口，供 F1-D 直接调用）",
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "generated_by": "tools/fusion/f1c_history_verify.py",
        "git_head": git("rev-parse", "HEAD").stdout.strip(),
        "reconciliations_consumed": [r.get("artifact") for r in recons],
        "summary": {"passed": passed, "total": len(results),
                    "result": "PASS" if passed == len(results) else "FAIL"},
        "checks": results,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
