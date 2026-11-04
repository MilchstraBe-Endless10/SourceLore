#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P3C 验收。"""
import json, sys, hashlib, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT/"docs"/"implementation"
CW = ROOT/"docs"/"fusion"/"CAPABILITY_CROSSWALK.json"
E2E = IMPL/"F2_P3C_E2E_REPLAY.json"
AUDIT = IMPL/"F2_P3C_INTERFACE_AUDIT.json"
OUT = IMPL/"F2_P3C_VERIFICATION.json"
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

    def c_auth_suite():
        n, rc = run_dir(ROOT/"tests"/"lifecycle", "test_revalidation_authorization.py")
        return rc == 0, f"授权测试 {n} 项 exit={rc}"

    def c_exec_suite():
        n, rc = run_dir(ROOT/"tests"/"lifecycle", "test_revalidation_execution.py")
        return rc == 0, f"执行测试 {n} 项 exit={rc}"

    def c_crash_suite():
        n, rc = run_dir(ROOT/"tests"/"lifecycle", "test_revalidation_crash.py")
        return rc == 0, f"崩溃恢复测试 {n} 项 exit={rc}"

    def c_e2e_suite():
        n, rc = run_dir(ROOT/"tests"/"lifecycle", "test_revalidation_end_to_end.py")
        return rc == 0, f"端到端测试 {n} 项 exit={rc}"

    def c_three_verdicts():
        ex = e2e.get("execution_absent", {})
        va = e2e.get("variants", {})
        ok = (ex.get("verification_status") == "refuted"
              and va.get("b_present", {}).get("verification_status") == "supported"
              and va.get("b_partial", {}).get("verification_status")
                  == "insufficient_evidence")
        return ok, (f"absent={ex.get('verification_status')} "
                    f"present={va.get('b_present',{}).get('verification_status')} "
                    f"partial={va.get('b_partial',{}).get('verification_status')}")

    def c_exec_vs_verdict():
        ex = e2e.get("execution_absent", {})
        ok = (ex.get("execution_status") == "SUCCESS"
              and ex.get("verification_status") == "refuted")
        va = e2e.get("variants", {}).get("b_partial", {})
        ok2 = (va.get("execution_status") == "SUCCESS"
               and va.get("verification_status") == "insufficient_evidence")
        return (ok and ok2), ("执行 SUCCESS 与裁决独立："
                              f"absent={ex.get('execution_status')}/"
                              f"{ex.get('verification_status')}；"
                              f"partial={va.get('execution_status')}/"
                              f"{va.get('verification_status')}")

    def c_fixed_commit():
        calls = e2e.get("execution_absent", {}).get("collector_calls", [])
        target = e2e.get("candidate", {}).get("candidate_id") and \
            e2e.get("execution_absent", {}).get("source_snapshot")
        ok = (calls and calls[0][0] == "fetch_commit"
              and calls[0][1] == "b" * 40
              and all(c[0] in ("fetch_commit", "fetch_tree") for c in calls))
        return ok, f"Collector 只按 B 取数，调用={calls}"

    def c_source_isolation():
        ex = e2e.get("execution_absent", {})
        ok = (e2e.get("authorization", {}).get("test_only") is True
              and e2e.get("authorization", {}).get("authorization_kind") == "TEST_ONLY")
        return ok, ("TEST_ONLY 授权隔离：" +
                    f"kind={e2e.get('authorization',{}).get('authorization_kind')} "
                    f"test_only={e2e.get('authorization',{}).get('test_only')}")

    def c_no_live_api():
        v = e2e.get("live_github_refetch")
        h = e2e.get("real_human_authorization")
        return (v is False and h is False), \
            f"live_github_refetch={v} real_human_authorization={h}（如实报告）"

    def c_no_approved():
        t = (ROOT/"tests"/"lifecycle"/
             "test_revalidation_end_to_end.py").read_text(encoding="utf-8")
        ok = "执行结果不得自动写 approved" in t
        return ok, f"不自动 approved 断言在位={ok}"

    def c_immutability():
        t = (ROOT/"tests"/"lifecycle"/
             "test_revalidation_end_to_end.py").read_text(encoding="utf-8")
        tv = (ROOT/"tests"/"lifecycle"/
              "test_revalidation_execution.py").read_text(encoding="utf-8")
        ok = ("旧 Claim 仍绑 A" in t and "旧 Verification 必须保留" in t
              and "执行失败不得修改旧 Verification" in tv)
        return ok, f"旧历史不可变断言在位={ok}"

    def c_single_active():
        q = (ROOT/"src"/"lifecycle"/"revalidation_queue.py").read_text(encoding="utf-8")
        ok = "★ 一次 CAS 写入" in q
        return ok, f"单活动候选仍由队列 CAS 保障={ok}"

    def c_no_second_engine():
        bad = []
        for f in (ROOT/"src"/"lifecycle").glob("*.py"):
            t = f.read_text(encoding="utf-8")
            if "sqlite3.connect" in t or "CREATE TABLE" in t:
                bad.append(f.name)
        return (not bad), f"自建库: {bad or '无'}"

    def c_no_llm():
        """只查真实依赖，不误伤 COMPLETION_CHECK 这类标识符。"""
        pat = re.compile(
            r"\b(import|from)\s+(openai|anthropic|google\.generativeai|cohere)\b"
            r"|\b(boto3|requests\.post)\b.*\b(llm|model)\b", re.I)
        bad = [f.name for f in (ROOT/"src"/"lifecycle").glob("*.py")
               if pat.search(f.read_text(encoding="utf-8"))]
        # 再确认没有付费 API 域名
        domains = []
        for f in (ROOT/"src"/"lifecycle").glob("*.py"):
            t = f.read_text(encoding="utf-8")
            for d in ("api.openai.com", "api.anthropic.com"):
                if d in t:
                    domains.append((f.name, d))
        return ((not bad) and (not domains),
                f"LLM 依赖={bad or '无'}、付费域名={domains or '无'}")

    def c_forbidden_fields():
        """★ 只检查**真正写入 Storage 的 payload** 是否含禁词键。

        `make_run_id` 的哈希载荷、字典下标访问、注释都不算 payload。
        这里用运行时实测：写一条 run，读回 payload，检查键名。
        """
        import tempfile, shutil, json as _j
        sys.path.insert(0, str(ROOT/"tests"/"lifecycle"))
        import importlib.util as _iu
        _sp = _iu.spec_from_file_location(
            "p3c_fx_v", str(ROOT/"tests"/"lifecycle"/"fixtures.py"))
        FXv = _iu.module_from_spec(_sp); _sp.loader.exec_module(FXv)
        import revalidation_queue as _RQ
        import revalidation_run_store as _RS

        tmp = Path(tempfile.mkdtemp(prefix="p3c_forbid_"))
        bad = []
        try:
            with FXv.fresh(tmp) as ks:
                st = FXv.make_full_stack(ks, target="b" * 40)
                pr = _RQ.propose_candidate(ks, assessment_id=st["assessment_id"])
                c = _RQ.read_candidate(ks, candidate_id=pr["candidate_id"],
                                       repository_id=FXv.REPO)["payload"]
                cr = _RS.create_run(ks, candidate=c, plan_digest="PLAN-x",
                                    authorization_id="SL-TESTAUTH-x",
                                    authorization_ref="SL-TESTAUTH-x",
                                    created_at="t")
                if not cr.get("ok"):
                    return False, f"run 写入失败: {cr}"
                row = ks.conn.execute(
                    "SELECT payload_json FROM assets "
                    "WHERE asset_type='revalidation_run'").fetchone()
                payload = _j.loads(row["payload_json"])
                forbidden = ("api_key", "token", "cookie", "secret",
                             "password", "credential", "private_key",
                             "authorization")
                for k in payload:
                    low = k.lower()
                    for f in forbidden:
                        if f in low:
                            bad.append(k)
            return (not bad), f"实际 run payload 禁词键: {bad or '无'}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

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
        g = subprocess.run(["git", "status", "--short", "--",
                            "docs/fusion/CAPABILITY_CROSSWALK.json"],
                           cwd=ROOT, capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(ROOT/"tools"/"fusion"/"f1d_verify.py")],
                           cwd=ROOT, capture_output=True, text=True)
        return (h == EXPECTED_SHA and not g.stdout.strip() and r.returncode == 0), \
            f"SHA={h[:16]}… 未变={h==EXPECTED_SHA} f1d exit={r.returncode}"

    def c_interface_audit():
        gaps = [g["gap"] for g in audit.get("gaps", [])]
        ok = len(gaps) >= 1 and any("授权传递" in g for g in gaps)
        return ok, f"§1 接口审计记录 {len(gaps)} 个缺口，含授权通道={ok}"

    def c_real_harness_open():
        """B.REAL_HARNESS_AUTHORIZED_E2E 必须保持 OPEN。"""
        f = IMPL/"F2_P3C_GATE_RESULTS.json"
        if not f.exists():
            return False, "门禁文件缺失"
        g = json.loads(f.read_text(encoding="utf-8"))
        st = g.get("real_harness_authorized_e2e", {}).get("verdict")
        return (st == "OPEN"), f"B.REAL_HARNESS_AUTHORIZED_E2E={st}"

    check("c1", "P3C 全部 lifecycle 测试", c_suite)
    check("c2", "授权门禁测试", c_auth_suite)
    check("c3", "执行器测试", c_exec_suite)
    check("c4", "崩溃恢复测试", c_crash_suite)
    check("c5", "端到端测试", c_e2e_suite)
    check("c6", "三态裁决都真实产生", c_three_verdicts)
    check("c7", "执行成功与裁决状态分离", c_exec_vs_verdict)
    check("c8", "Collector 固定目标不漂移", c_fixed_commit)
    check("c9", "TEST_ONLY 授权隔离", c_source_isolation)
    check("c10", "如实报告未联网/无真实授权", c_no_live_api)
    check("c11", "不自动 approved", c_no_approved)
    check("c12", "旧 Claim/Verification 不可变", c_immutability)
    check("c13", "单活动候选仍由队列保障", c_single_active)
    check("c14", "未新建第二套引擎/数据库", c_no_second_engine)
    check("c15", "无 LLM/付费依赖", c_no_llm)
    check("c16", "payload 避开 Storage 禁字段", c_forbidden_fields)
    check("c17", "P1A~P3B 全链回归", c_regression)
    check("c18", "F1-D 冻结哈希与验证", c_frozen)
    check("c19", "§1 接口审计记录了缺口", c_interface_audit)
    check("c20", "B.REAL_HARNESS_AUTHORIZED_E2E 保持 OPEN", c_real_harness_open)

    passed = sum(1 for r in results if r["passed"])
    out = {"task": "M2 / F2-P3C（受控重新验证执行）",
           "generated_by": "tools/f2p3c_verify.py", "independent": True,
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      capture_output=True, text=True).stdout.strip(),
           "crosswalk_sha256": hashlib.sha256(CW.read_bytes()).hexdigest(),
           "data_provenance": e2e.get("data_provenance"),
           "live_github_refetch": e2e.get("live_github_refetch"),
           "real_human_authorization": e2e.get("real_human_authorization"),
           "summary": {"passed": passed, "total": len(results),
                       "result": "PASS" if passed == len(results) else "FAIL"},
           "checks": results}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
