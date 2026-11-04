#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P2B 验收。"""
import json, sys, hashlib, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/"docs"; IMPL = DOCS/"implementation"
CW = DOCS/"fusion"/"CAPABILITY_CROSSWALK.json"
E2E = IMPL/"F2_P2B_E2E_REPLAY.json"
AUDIT = IMPL/"F2_P2B_PRECONDITION_AUDIT.json"
OUT = IMPL/"F2_P2B_VERIFICATION.json"
EXPECTED_SHA = "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b"

for p in (str(ROOT/"src"/"evidence_claims"), str(ROOT/"src"/"storage"),
          str(ROOT/"src"/"facts"), str(ROOT/"src"/"collector"),
          str(ROOT/"src"/"runtime"), str(ROOT/"tests"/"evidence_claims")):
    if p not in sys.path: sys.path.insert(0, p)

results = []

def check(cid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append({"id": cid, "name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} :: {detail}")

def run_dir(d, pattern="*.py"):
    r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                        "-s", str(d), "-p", pattern],
                       cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"Ran (\d+) test", r.stderr + r.stdout)
    return (int(m.group(1)) if m else 0), r.returncode

def main() -> int:
    e2e = json.loads(E2E.read_text(encoding="utf-8")) if E2E.exists() else {}
    audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {}

    def c_ec_suite():
        n, rc = run_dir(ROOT/"tests"/"evidence_claims")
        return rc == 0, f"EC 套件 {n} 项 exit={rc}"

    def c_gold():
        n, rc = run_dir(ROOT/"tests"/"evidence_claims", "test_gold.py")
        return rc == 0, f"Gold+变异 {n} 项 exit={rc}"

    def c_three_states():
        ok = (e2e.get("claim_readme_exists", {}).get("status") == "supported"
              and e2e.get("claim_readme_not_exists", {}).get("status") == "refuted"
              and e2e.get("claim_package_json_absent", {}).get("status")
                  == "insufficient_evidence")
        d = (f"supported={e2e.get('claim_readme_exists',{}).get('status')} "
             f"refuted={e2e.get('claim_readme_not_exists',{}).get('status')} "
             f"abstain={e2e.get('claim_package_json_absent',{}).get('status')}")
        return ok, d

    def c_precondition_A():
        f = audit.get("A_p2a_manifest_provenance", {}).get("finding", "")
        ok = "证据不足" in f
        # 且本批确实 abstain 了 package.json
        abst = e2e.get("claim_package_json_absent", {}).get("abstained")
        return (ok and abst), f"§1A 判定={f}；package.json abstain={abst}"

    def c_precondition_B():
        d = audit.get("B_collector_test_count", {})
        conc = d.get("true_source_of_'45'_discrepancy", {}).get("conclusion", "")
        ok = "没有任何测试被删除" in conc
        return ok, conc or "未记录"

    def c_backoff_not_fake():
        n, rc = run_dir(ROOT/"tests"/"collector", "test_github_client.py")
        src = (ROOT/"tests"/"collector"/"test_github_client.py").read_text(encoding="utf-8")
        ok = rc == 0 and "self.assertTrue(slept" in src
        return ok, f"非空断言在位={('self.assertTrue(slept' in src)}，collector {n} 项 exit={rc}"

    def c_wrong_commit():
        v = e2e.get("wrong_commit_rejected", {})
        ok = (v.get("status") == "insufficient_evidence"
              and v.get("reason") == "COMMIT_MISMATCH")
        return ok, f"{v.get('status')}/{v.get('reason')}"

    def c_idempotent():
        p = e2e.get("persistence", {})
        ok = p.get("second") == "IDEMPOTENT_ALREADY_PRESENT"
        return ok, f"{p.get('first')} -> {p.get('second')}"

    def c_no_second_db():
        """不得有 EC 私有的第二套权威数据库。"""
        bad = []
        for f in (ROOT/"src"/"evidence_claims").glob("*.py"):
            t = f.read_text(encoding="utf-8")
            if "sqlite3.connect" in t or "CREATE TABLE" in t:
                bad.append(f.name)
        return (not bad), f"自建库文件 {bad or '无'}"

    def c_no_llm():
        bad = []
        for f in (ROOT/"src"/"evidence_claims").glob("*.py"):
            t = f.read_text(encoding="utf-8")
            if re.search(r"openai|anthropic|llm|gpt|completion", t, re.I):
                bad.append(f.name)
        return (not bad), f"LLM 依赖 {bad or '无'}"

    def c_review_separation():
        src = (ROOT/"src"/"evidence_claims"/"ec_models.py").read_text(encoding="utf-8")
        ok = ("review_status=approved 必须有 human_authored=True" in src)
        return ok, f"AI 不得自批约束在位={ok}"

    def c_regression():
        dirs = ["runtime", "storage", "collector", "facts"]
        out = []
        allok = True
        for d in dirs:
            n, rc = run_dir(ROOT/"tests"/d)
            out.append(f"{d} {n} exit={rc}")
            allok = allok and rc == 0
        return allok, "; ".join(out)

    def c_frozen():
        h = hashlib.sha256(CW.read_bytes()).hexdigest()
        g = subprocess.run(["git","status","--short","--",
                            "docs/fusion/CAPABILITY_CROSSWALK.json"],
                           cwd=ROOT, capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(ROOT/"tools"/"fusion"/"f1d_verify.py")],
                           cwd=ROOT, capture_output=True, text=True)
        return (h == EXPECTED_SHA and not g.stdout.strip() and r.returncode == 0), \
            f"SHA={h[:16]}… 未变={h==EXPECTED_SHA} f1d exit={r.returncode}"

    def c_provenance():
        p = e2e.get("data_provenance")
        ok = p == "HISTORICAL_REAL_DATA"
        return ok, f"数据级别={p}（未标 REAL_LIVE_API，未把合成清单当真实）"

    def c_evidence_levels():
        """三种数据级别必须可区分且被正确标注。"""
        src = (ROOT/"tools"/"f2p2b_e2e_replay.py").read_text(encoding="utf-8")
        ok = "HISTORICAL_REAL_DATA" in src
        return ok, f"回放脚本标注={ok}"

    def c_unsupported():
        n, rc = run_dir(ROOT/"tests"/"evidence_claims", "test_verifier.py")
        # 断言文案在 verifier.py 的 reason 与 test_gold 的 gold 依据里
        t = (ROOT/"tests"/"evidence_claims"/"test_gold.py").read_text(encoding="utf-8")
        v = (ROOT/"src"/"evidence_claims"/"verifier.py").read_text(encoding="utf-8")
        ok = (rc == 0 and 'unsupported_type' in t
              and "R_UNSUPPORTED_TYPE" in v
              and "R_UNSUPPORTED_TYPE" in
              (ROOT/"tests"/"evidence_claims"/"test_verifier.py").read_text(encoding="utf-8"))
        return ok, (f"verifier 返回 R_UNSUPPORTED_TYPE={('R_UNSUPPORTED_TYPE' in v)}、"
                    f"gold 场景 unsupported_type={('unsupported_type' in t)}")

    def c_conflict():
        t = (ROOT/"tests"/"evidence_claims"/"test_gold.py").read_text(encoding="utf-8")
        tv = (ROOT/"tests"/"evidence_claims"/"test_verifier.py").read_text(encoding="utf-8")
        ok = ("conflicting_evidence" in t) and ("冲突不得强行裁决" in tv)
        return ok, f"gold 覆盖冲突场景={('conflicting_evidence' in t)}，verifier 断言在位={('冲突不得强行裁决' in tv)}"

    def c_partial_limit():
        tv = (ROOT/"tests"/"evidence_claims"/"test_verifier.py").read_text(encoding="utf-8")
        tg = (ROOT/"tests"/"evidence_claims"/"test_gold.py").read_text(encoding="utf-8")
        a = "PARTIAL 下的支持必须保留局部覆盖限制" in tv
        b = "partial_not_covering" in tg          # gold: PARTIAL 未命中场景
        c = "partial_local_present" in tg         # gold: PARTIAL 局部存在场景
        ok = a and b and c
        return ok, f"PARTIAL 存在限制={a}、未命中不推否证={b}、gold 局部存在用例={c}"

    check("c1", "EC 测试套件", c_ec_suite)
    check("c2", "离线 Gold + 变异测试", c_gold)
    check("c3", "三态裁决都有真实执行证据", c_three_states)
    check("c4", "§1A 前置核验并据此 abstain", c_precondition_A)
    check("c5", "§1B 前置核验（无测试被删）", c_precondition_B)
    check("c6", "退避测试非空断言可捕获假通过", c_backoff_not_fake)
    check("c7", "错误 Commit 证据不被接受", c_wrong_commit)
    check("c8", "重复裁决幂等", c_idempotent)
    check("c9", "无第二套权威数据库", c_no_second_db)
    check("c10", "不引入 LLM", c_no_llm)
    check("c11", "AI 不能生成 approved", c_review_separation)
    check("c12", "P1A/P1B/P1C/P2A 全链回归", c_regression)
    check("c13", "F1-D 冻结哈希与验证", c_frozen)
    check("c14", "真实数据级别标注正确", c_provenance)
    check("c15", "不支持命题类型显式拒绝", c_unsupported)
    check("c16", "冲突不被强行裁决", c_conflict)
    check("c17", "PARTIAL 范围限制被执行", c_partial_limit)

    passed = sum(1 for r in results if r["passed"])
    out = {"task": "M2 / F2-P2B（Evidence-Claims 确定性裁决）",
           "generated_by": "tools/f2p2b_verify.py", "independent": True,
           "git_head": subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT,
                                      capture_output=True, text=True).stdout.strip(),
           "crosswalk_sha256": hashlib.sha256(CW.read_bytes()).hexdigest(),
           "data_provenance": e2e.get("data_provenance"),
           "summary": {"passed": passed, "total": len(results),
                       "result": "PASS" if passed == len(results) else "FAIL"},
           "checks": results}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
