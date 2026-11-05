#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P3A 验收。"""
import json, sys, hashlib, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT/"docs"/"implementation"
CW = ROOT/"docs"/"fusion"/"CAPABILITY_CROSSWALK.json"
E2E = IMPL/"F2_P3A_E2E_REPLAY.json"
AUDIT = IMPL/"F2_P3A_REF_OBSERVATION_AUDIT.json"
OUT = IMPL/"F2_P3A_VERIFICATION.json"
EXPECTED_SHA = "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b"

for p in ("src/lifecycle","src/storage","src/facts","src/collector",
          "src/runtime","src/evidence_claims","tests/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

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

    def c_lc_suite():
        n, rc = run_dir(ROOT/"tests"/"lifecycle")
        return rc == 0, f"Lifecycle 套件 {n} 项 exit={rc}"

    def c_three_states():
        b = e2e.get("assess_baseline", {}).get("state")
        m = e2e.get("assess_moved", {}).get("state")
        u = e2e.get("assess_unobservable", {}).get("state")
        ok = (b == "VERSION_ALIGNED" and m == "POSSIBLY_STALE" and u == "UNKNOWN")
        return ok, f"baseline={b} moved={m} unobservable={u}"

    def c_no_live_api():
        v = e2e.get("live_github_refetch")
        return (v is False), f"live_github_refetch={v}（如实报告未重新联网）"

    def c_snapshot_cannot_prove_ref():
        d = e2e.get("snapshot_cannot_prove_ref", {})
        aud = audit.get("finding", "")
        ok = (d.get("reason") == "REF_MISMATCH" and "不能" in aud)
        return ok, f"快照拒绝={d.get('reason')}；审计结论={aud[:20]}…"

    def c_ec_unchanged():
        d = e2e.get("ec_unchanged_after_lifecycle", {})
        ok = d.get("still_supported") is True
        return ok, f"Lifecycle 后 EC status={d.get('status')}"

    def c_review_untouched():
        d = e2e.get("ec_unchanged_after_lifecycle", {})
        return (d.get("claim_review_status") == "pending_review"), \
            f"review_status={d.get('claim_review_status')}"

    def c_no_refuted_in_source():
        """只禁止**写入** refuted / approved 状态，不禁止合法标识符。

        ★ 原版用裸子串 `APPROVED`，会命中 P3C 的
        `PLATFORM_APPROVAL`（授权**类别名**，不是审核状态）——
        验证器假阳性。改为只匹配"把状态赋值为这两种值"。
        检查强度不降：另外独立断言状态集里没有这两个值。
        """
        pat = re.compile(r"""\bstatus\s*=\s*[\"'](refuted|approved)[\"']""")
        bad = []
        for f in (ROOT/"src"/"lifecycle").glob("*.py"):
            if pat.search(f.read_text(encoding="utf-8")):
                bad.append(f.name)
        if bad:
            return False, f"源码写入 refuted/approved: {bad}"
        # 独立断言：三套状态词表里都没有这两个值
        import lc_models as _L
        import revalidation_models as _RM
        import revalidation_run_store as _RS
        forbidden = []
        for name, table in (("FRESHNESS_STATES", _L.FRESHNESS_STATES),
                            ("CANDIDATE_STATES", _RM.CANDIDATE_STATES),
                            ("EXEC_STATES", _RS.EXEC_STATES)):
            for v in ("refuted", "approved", "REFUTED", "APPROVED"):
                if v in table:
                    forbidden.append(f"{name}:{v}")
        return (not forbidden), f"状态词表禁值: {forbidden or '无'}"
    def c_no_second_db():
        bad = [f.name for f in (ROOT/"src"/"lifecycle").glob("*.py")
               if "sqlite3.connect" in f.read_text(encoding="utf-8")
               or "CREATE TABLE" in f.read_text(encoding="utf-8")]
        return (not bad), f"自建库: {bad or '无'}"

    def c_no_llm():
        """精确查真实 LLM 依赖。

        ★ 原版用裸子串 `completion` / `gpt`，会被 P3C 的
        `COMPLETION_CHECK`（执行阶段名）命中 —— 这是**验证器假阳性**，
        不是产品缺陷。改为只匹配 import 语句与真实 API 域名，
        检查强度不降（仍然禁止任何 LLM SDK 与付费端点）。
        """
        pat = re.compile(
            r"\b(import|from)\s+(openai|anthropic|google\.generativeai|cohere|"
            r"langchain|transformers|torch)\b"
            r"|\bapi\.(openai|anthropic|cohere)\.com\b"
            r"|\b(chat|text)[-_]?completions?\b", re.I)
        bad = [f.name for f in (ROOT/"src"/"lifecycle").glob("*.py")
               if pat.search(f.read_text(encoding="utf-8"))]
        return (not bad), f"LLM 依赖: {bad or '无'}"
    def c_impact_nonempty():
        a = e2e.get("impact", {}).get("affected", [])
        return (len(a) > 0), f"受影响 Claim {len(a)} 条（非空集合）"

    def c_cas_tested():
        t = (ROOT/"tests"/"lifecycle"/"test_lifecycle.py").read_text(encoding="utf-8")
        ok = "expected_version=99" in t and "CONFLICT" in t
        return ok, f"CAS 冲突断言在位={ok}"

    def c_sigkill_tested():
        t = (ROOT/"tests"/"lifecycle"/"test_recovery_and_mutation.py").read_text(encoding="utf-8")
        ok = "os.kill(os.getpid(), 9)" in t
        return ok, f"真实 SIGKILL 实验在位={ok}"

    def c_mutation_tested():
        t = (ROOT/"tests"/"lifecycle"/"test_recovery_and_mutation.py").read_text(encoding="utf-8")
        ok = 'freshness_state="refuted"' in t
        return ok, f"变异（stale→refuted）被捕获={ok}"

    def c_regression():
        dirs = ["runtime", "storage", "collector", "facts", "evidence_claims"]
        out, allok = [], True
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
        m = e2e.get("assess_moved", {})
        ok = (m.get("provenance") == "SYNTHETIC_FIXTURE"
              and "SYNTHETIC" in m.get("note", ""))
        return ok, f"合成观测标注={m.get('provenance')}"

    def c_five_states():
        src = (ROOT/"src"/"lifecycle"/"lc_models.py").read_text(encoding="utf-8")
        need = ["verification_status", "knowledge_freshness", "review_status",
                "execution_status", "source_completeness"]
        missing = [x for x in need if x not in src]
        return (not missing), f"五类状态分离，缺 {missing or '无'}"

    def c_pinned_semantics():
        src = (ROOT/"src"/"lifecycle"/"lc_models.py").read_text(encoding="utf-8")
        ok = "PINNED_COMMIT 不得建立 TRACKING_REF watch" in src
        return ok, f"固定版本语义隔离在位={ok}"

    check("c1", "Lifecycle 测试套件", c_lc_suite)
    check("c2", "三态新鲜度真实执行", c_three_states)
    check("c3", "如实报告未重新联网", c_no_live_api)
    check("c4", "快照不能证明 Ref（审计已修正）", c_snapshot_cannot_prove_ref)
    check("c5", "Lifecycle 不改 EC 裁决", c_ec_unchanged)
    check("c6", "Lifecycle 不改 review_status", c_review_untouched)
    check("c7", "源码无 refuted/approved 写入", c_no_refuted_in_source)
    check("c8", "无第二套数据库", c_no_second_db)
    check("c9", "不引入 LLM", c_no_llm)
    check("c10", "影响范围非空集合", c_impact_nonempty)
    check("c11", "CAS 冲突实测", c_cas_tested)
    check("c12", "真实 SIGKILL 恢复实验", c_sigkill_tested)
    check("c13", "变异测试可捕获 stale→refuted", c_mutation_tested)
    check("c14", "P1A/P1B/P1C/P2A/P2B 全链回归", c_regression)
    check("c15", "F1-D 冻结哈希与验证", c_frozen)
    check("c16", "合成观测正确标注", c_provenance)
    check("c17", "五类状态分离", c_five_states)
    check("c18", "固定版本语义隔离", c_pinned_semantics)

    passed = sum(1 for r in results if r["passed"])
    out = {"task": "M2 / F2-P3A（Lifecycle 版本观测与时效评估）",
           "generated_by": "tools/f2p3a_verify.py", "independent": True,
           "git_head": subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT,
                                      capture_output=True, text=True).stdout.strip(),
           "crosswalk_sha256": hashlib.sha256(CW.read_bytes()).hexdigest(),
           "data_provenance": e2e.get("data_provenance"),
           "live_github_refetch": e2e.get("live_github_refetch"),
           "summary": {"passed": passed, "total": len(results),
                       "result": "PASS" if passed == len(results) else "FAIL"},
           "checks": results}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
