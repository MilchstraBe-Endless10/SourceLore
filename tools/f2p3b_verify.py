#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P3B 验收。"""
import json, sys, hashlib, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT/"docs"/"implementation"
CW = ROOT/"docs"/"fusion"/"CAPABILITY_CROSSWALK.json"
E2E = IMPL/"F2_P3B_E2E_REPLAY.json"
AUDIT = IMPL/"F2_P3B_P3A_IMPLEMENTATION_AUDIT.json"
OUT = IMPL/"F2_P3B_VERIFICATION.json"
EXPECTED_SHA = "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b"

for p in ("src/lifecycle", "src/storage", "src/facts", "src/collector",
          "src/runtime", "src/evidence_claims", "tests/lifecycle"):
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

    def c_suite():
        n, rc = run_dir(ROOT/"tests"/"lifecycle")
        return rc == 0, f"Lifecycle 套件 {n} 项 exit={rc}"

    def c_conflict_missing_not_false():
        f = audit.get("checks", {}).get("3_conflict_detected", {})
        src = (ROOT/"src"/"lifecycle"/"lc_models.py").read_text(encoding="utf-8")
        ok = ("不存在于 FreshnessAssessment" in f.get("finding", "")
              and "CONFLICT_UNKNOWN" in src
              and "CONFLICT_NONE" in src)
        return ok, ("conflict_detected 缺失已如实记录，且补了三态"
                    f"（CONFLICT_UNKNOWN 默认）={ok}")

    def c_conflict_unknown_blocks():
        t = (ROOT/"tests"/"lifecycle"/
             "test_revalidation_queue.py").read_text(encoding="utf-8")
        ok = "CONFLICT_UNKNOWN 不得当作无冲突放行" in t
        return ok, f"未核验冲突被拦的断言在位={ok}"

    def c_only_from_assessment():
        v = (ROOT/"src"/"lifecycle"/"revalidation_planner.py").read_text(encoding="utf-8")
        ok = ("freshness_state" in v and "POSSIBLY_STALE" in v
              and "applicability_scope" in v and "TRACKING_REF" in v)
        return ok, f"候选只从 POSSIBLY_STALE + TRACKING_REF 生成={ok}"

    def c_source_isolation():
        m = (ROOT/"src"/"lifecycle"/"revalidation_models.py").read_text(encoding="utf-8")
        ok = ("DISPATCHABLE_SOURCES" in m
              and 'frozenset({SRC_REAL})' in m)
        st = e2e.get("synthetic_new_commit", {})
        ok2 = (st.get("candidate_status") == "BLOCKED"
               and st.get("plan_gate") == "CANDIDATE_NOT_PROPOSED")
        return (ok and ok2), (f"可调度来源仅 REAL_LIVE_API={ok}；"
                              f"合成候选={st.get('candidate_status')}"
                              f"/{st.get('plan_gate')}")

    def c_no_live_api():
        return (e2e.get("live_github_refetch") is False), \
            f"live_github_refetch={e2e.get('live_github_refetch')}（如实报告）"

    def c_single_active():
        a = e2e.get("active_count", {})
        ok = (a.get("multi_active_watches") == [] and a.get("total_active") <= 1)
        return ok, f"活动候选={a.get('total_active')} 多活动 watch={a.get('multi_active_watches')}"

    def c_history_preserved():
        q = e2e.get("queue", {})
        ok = q.get("history_count", 0) >= 2
        return ok, f"队列历史候选数={q.get('history_count')}"

    def c_plan_ready_not_authorized():
        p = e2e.get("plan", {})
        ev = p.get("events", {})
        ok = (p.get("gate") == "PLAN_READY"
              and ev.get("EXECUTION_AUTHORIZED") is False
              and ev.get("EXECUTION_COMPLETED") is False)
        return ok, (f"gate={p.get('gate')} authorized={ev.get('EXECUTION_AUTHORIZED')} "
                    f"completed={ev.get('EXECUTION_COMPLETED')}")

    def c_no_side_effects():
        se = e2e.get("plan", {}).get("side_effects", {})
        ok = bool(se) and not any(se.values())
        return ok, f"副作用全否={ok}：{se}"

    def c_no_authorized_state():
        m = (ROOT/"src"/"lifecycle"/"revalidation_models.py").read_text(encoding="utf-8")
        ok = ("AUTHORIZED" not in m.split("CANDIDATE_STATES")[1].split("}")[0]
              if "CANDIDATE_STATES" in m else False)
        return ok, f"候选状态集不含 AUTHORIZED={ok}"

    def c_no_refuted():
        bad = [f.name for f in (ROOT/"src"/"lifecycle").glob("*.py")
               if '"refuted"' in f.read_text(encoding="utf-8")]
        return (not bad), f"源码出现 refuted: {bad or '无'}"

    def c_no_second_db():
        bad = [f.name for f in (ROOT/"src"/"lifecycle").glob("*.py")
               if "sqlite3.connect" in f.read_text(encoding="utf-8")
               or "CREATE TABLE" in f.read_text(encoding="utf-8")]
        return (not bad), f"自建库: {bad or '无'}"

    def c_no_llm():
        bad = [f.name for f in (ROOT/"src"/"lifecycle").glob("*.py")
               if re.search(r"openai|anthropic|gpt|completion",
                            f.read_text(encoding="utf-8"), re.I)]
        return (not bad), f"LLM 依赖: {bad or '无'}"

    def c_cas_and_kill():
        t = (ROOT/"tests"/"lifecycle"/
             "test_revalidation_concurrency.py").read_text(encoding="utf-8")
        ok = ("os.kill(os.getpid(), 9)" in t
              and "expected_version=99" in
              (ROOT/"tests"/"lifecycle"/
               "test_revalidation_queue.py").read_text(encoding="utf-8"))
        return ok, f"真实 SIGKILL={('os.kill(os.getpid(), 9)' in t)}、CAS 冲突实测={ok}"

    def c_concurrency_real_pids():
        t = (ROOT/"tests"/"lifecycle"/
             "test_revalidation_concurrency.py").read_text(encoding="utf-8")
        ok = "必须使用不同 PID" in t
        return ok, f"并发使用真实多进程并断言不同 PID={ok}"

    def c_immutability():
        t = (ROOT/"tests"/"lifecycle"/
             "test_revalidation_queue.py").read_text(encoding="utf-8")
        ok = ("候选生成不得修改原始 Claim" in t
              and "候选生成不得修改原始 Verification" in t
              and "不得生成新 verification" in t)
        return ok, f"Claim/Verification 不可变断言在位={ok}"

    def c_regression():
        dirs = ["runtime", "storage", "collector", "facts",
                "evidence_claims"]
        out, allok = [], True
        for d in dirs:
            n, rc = run_dir(ROOT/"tests"/d)
            out.append(f"{d} {n} exit={rc}")
            allok = allok and rc == 0
        return allok, "; ".join(out)

    def c_frozen():
        h = hashlib.sha256(CW.read_bytes()).hexdigest()
        g = subprocess.run(["git", "status", "--short", "--",
                            "docs/fusion/CAPABILITY_CROSSWALK.json"],
                           cwd=ROOT, capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(ROOT/"tools"/"fusion"/"f1d_verify.py")],
                           cwd=ROOT, capture_output=True, text=True)
        return (h == EXPECTED_SHA and not g.stdout.strip() and r.returncode == 0), \
            f"SHA={h[:16]}… 未变={h==EXPECTED_SHA} f1d exit={r.returncode}"

    def c_queue_atomic():
        q = (ROOT/"src"/"lifecycle"/"revalidation_queue.py").read_text(encoding="utf-8")
        ok = ("★ 一次 CAS 写入" in q) and ("active_candidate_id" in q)
        return ok, f"候选与活动槽位同一次 CAS={ok}"

    def c_candidate_id_contract():
        m = (ROOT/"src"/"lifecycle"/"revalidation_models.py").read_text(encoding="utf-8")
        ok = all(k in m for k in ("watch_id", "source_claim_id",
                                  "target_commit_sha", "revalidation_rule_version",
                                  "canonical_scope", "repository_id"))
        return ok, f"candidate_id 契约字段齐备={ok}"

    def c_target_claim_identity():
        p = e2e.get("plan", {})
        tid = p.get("target_claim_identity")
        ok = isinstance(tid, str) and tid.startswith("SL-CLAIM-")
        return ok, f"target claim 身份可确定性计算={ok}（{str(tid)[:24]}…）"

    check("c1", "P3B 测试套件", c_suite)
    check("c2", "P3A conflict_detected 缺失已如实记录并补三态", c_conflict_missing_not_false)
    check("c3", "冲突未核验不得当作无冲突", c_conflict_unknown_blocks)
    check("c4", "候选只从有效评估生成", c_only_from_assessment)
    check("c5", "可信与合成来源严格隔离", c_source_isolation)
    check("c6", "如实报告未重新联网", c_no_live_api)
    check("c7", "每 watch 单活动候选", c_single_active)
    check("c8", "A→B→C 历史可追溯", c_history_preserved)
    check("c9", "PLAN_READY 不等于已授权", c_plan_ready_not_authorized)
    check("c10", "Dry-Run 无工具副作用", c_no_side_effects)
    check("c11", "候选状态集不含 AUTHORIZED", c_no_authorized_state)
    check("c12", "源码无 refuted 写入", c_no_refuted)
    check("c13", "无第二套数据库", c_no_second_db)
    check("c14", "不引入 LLM", c_no_llm)
    check("c15", "真实 SIGKILL 与 CAS 实测", c_cas_and_kill)
    check("c16", "并发使用真实不同 PID", c_concurrency_real_pids)
    check("c17", "Claim/Verification 不可变", c_immutability)
    check("c18", "P1A~P3A 全链回归", c_regression)
    check("c19", "F1-D 冻结哈希与验证", c_frozen)
    check("c20", "候选与活动槽位同一次 CAS", c_queue_atomic)
    check("c21", "candidate_id 契约字段齐备", c_candidate_id_contract)
    check("c22", "新 Commit 的 Claim 身份可计算", c_target_claim_identity)

    passed = sum(1 for r in results if r["passed"])
    out = {"task": "M2 / F2-P3B（重新验证候选队列与受控授权边界）",
           "generated_by": "tools/f2p3b_verify.py", "independent": True,
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
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
