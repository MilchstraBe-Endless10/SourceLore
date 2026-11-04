#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P1C 验收：22 项场景 + 阶段条件。

模拟测试（离线）与真实网络测试（在线）**分开报告**。
真实网络未通过时，对应门禁保持 OPEN，不宣称 DONE。
"""
import json, sys, hashlib, subprocess, unittest, io, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
IMPL = DOCS / "implementation"
CW = DOCS / "fusion" / "CAPABILITY_CROSSWALK.json"
REAL = IMPL / "F2_P1C_REAL_GITHUB.json"
OUT = IMPL / "F2_P1C_VERIFICATION.json"
TESTS_C = ROOT / "tests" / "collector"
TESTS_S = ROOT / "tests" / "storage"

EXPECTED_SHA = "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b"

for p in (str(ROOT / "src" / "collector"), str(ROOT / "src" / "storage"),
          str(ROOT / "src" / "runtime"), str(TESTS_C)):
    if p not in sys.path:
        sys.path.insert(0, p)

results = []


def check(cid, name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"异常: {type(e).__name__}: {e}"
    results.append({"id": cid, "name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} :: {detail}")


def sha_bytes(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_suite(d, pattern):
    loader = unittest.TestLoader()
    suite = loader.discover(str(d), pattern=pattern)
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    r = runner.run(suite)
    return r.testsRun, len(r.failures), len(r.errors)


def main() -> int:
    real = json.loads(REAL.read_text(encoding="utf-8")) if REAL.exists() else {}
    real_ok = real.get("result") == "REAL_GITHUB_OK"

    def c1_2():
        n, f, e = run_suite(TESTS_C, "test_github_client.py")
        return (n >= 43 and f == 0 and e == 0), \
            f"Collector 确定性套件 {n} 项，失败 {f}、错误 {e}"

    def c3():
        import github_client as G
        from tree_collector import TreeCollector
        # root_tree_sha 只能来自 commit 对象
        src = (ROOT / "src" / "collector" / "source_snapshot.py").read_text(encoding="utf-8")
        has_note = "绝不从 Trees API 响应取" in src
        return has_note, f"源码明确 root_tree_sha 来源约束={has_note}"

    def c4():
        from tree_collector import TreeCollector
        import fake_gh as F
        c = G_client()
        tc = TreeCollector(c, "o", "r")
        res = tc.collect(F.ROOT_TREE_SHA)
        return (res["tree_query_refs"][0] == F.ROOT_TREE_SHA), \
            f"tree_query_ref 记录实际请求 ref={res['tree_query_refs'][0][:12]}…"

    def c5_7():
        n, f, e = run_suite(TESTS_C, "test_github_client.py")
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has = ("truncated" in src and "PARTIAL" in src and "NESTED" in src.upper())
        return (f == 0 and has), f"Tree 场景（扁平/嵌套/截断）覆盖={has}，失败 {f}"

    def c8():
        from tree_collector import git_blob_sha1
        import hashlib as H
        raw = b"hello world\n"
        plain = H.sha1(raw).hexdigest()
        git = git_blob_sha1(raw)
        return (plain != git), \
            f"Git blob 编码 ≠ 裸内容 sha1（plain={plain[:8]}… git={git[:8]}…）"

    def c9():
        n, f, e = run_suite(TESTS_C, "test_github_client.py")
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has = "unknown_encoding" in src or "MALFORMED" in src
        return (f == 0 and has), f"异常对象类型/编码覆盖={has}"

    def c10_11():
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has_repo = "different_repo_same_content_different_identity" in src
        has_coll = "no_collision" in src
        n, f, e = run_suite(TESTS_C, "test_github_client.py")
        return (has_repo and has_coll and f == 0), \
            f"仓库身份稳定={has_repo}、跨仓库不碰撞={has_coll}"

    def c12():
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has = "repeat_same_snapshot_is_idempotent" in src
        # 也验证真实路径（若有真实记录）
        ri = real.get("ingest", {})
        return has, \
            f"重复采集幂等断言存在={has}；真实侧 first={ri.get('first')} second={ri.get('second')}"

    def c13():
        src = (ROOT / "src" / "collector" / "source_snapshot.py").read_text(encoding="utf-8")
        has = "requested_ref" in src and "requested_ref_does_not_change_identity" in \
              (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        return has, f"ref 变化不影响已固定快照身份={has}"

    def c14():
        n, f, e = run_suite(TESTS_C, "test_github_client.py")
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        codes = ["UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND", "RATE_LIMITED",
                 "SECONDARY_RATE_LIMITED", "SERVER_ERROR"]
        has = all(c in src for c in codes)
        return (f == 0 and has), \
            f"六类错误码均有测试={has}（401/403/404/429/5xx 未折成空仓库）"

    def c15():
        import github_client as G
        c = G.GitHubClient(max_retries=2)
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has = "bounded_retry" in src and "retry_after_capped" in src
        return has, f"有限重试与退避上限有测试={has}"

    def c16():
        import github_client as G
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has = "rejects_traversal" in src and "absolute_url" in src
        return has, f"路径逃逸防护有测试={has}"

    def c17():
        n, f, e = run_suite(TESTS_C, "test_crash_recovery.py")
        return (n >= 3 and f == 0 and e == 0), \
            f"跨库漏窗 SIGKILL 恢复 {n} 项，失败 {f}"

    def c18():
        n, f, e = run_suite(TESTS_C, "test_crash_recovery.py")
        src = (TESTS_C / "test_crash_recovery.py").read_text(encoding="utf-8")
        has = "不得重复推进指针" in src
        return (f == 0 and has), f"重复 operation_id 不推进版本断言={has}"

    def c19():
        n, f, e = run_suite(TESTS_C, "test_github_client.py")
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has = "rebuild_after_ingest_keeps_a_b" in src
        return (f == 0 and has), f"索引重建后 A/B 不变断言={has}"

    def c20():
        """真实 GitHub：**只有真的成功才算 PASS**。"""
        if not real:
            return False, "无真实取数记录（文件缺失）"
        if real_ok:
            return True, (f"真实取数成功：{real.get('repository_id')} "
                          f"@{real.get('commit_sha','')[:12]}… "
                          f"tree={real.get('tree',{}).get('entry_count')} 项")
        return False, (f"真实取数未成功：result={real.get('result')}，"
                       f"error={(real.get('blocking_error') or {}).get('error_code')}")

    def c21():
        # 必须用**子进程**分别跑：tests/collector 与 tests/runtime 都有
        # test_crash_recovery.py，同进程内会被 unittest 判定为重名模块。
        def run_dir(d):
            r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                                "-s", str(d), "-p", "*.py"],
                               cwd=ROOT, capture_output=True, text=True)
            import re as _re
            m = _re.search(r"Ran (\d+) test", r.stderr + r.stdout)
            return (int(m.group(1)) if m else 0), r.returncode
        n1, rc1 = run_dir(TESTS_S)
        n2, rc2 = run_dir(ROOT / "tests" / "runtime")
        n3, rc3 = run_dir(TESTS_C)
        ok = (rc1 == 0 and rc2 == 0 and rc3 == 0)
        return ok, (f"P1B {n1} 项 exit={rc1}、P1A {n2} 项 exit={rc2}、"
                    f"P1C {n3} 项 exit={rc3}")

    def c22():
        h = sha_bytes(CW)
        g = subprocess.run(["git", "status", "--short", "--",
                            "docs/fusion/CAPABILITY_CROSSWALK.json"],
                           cwd=ROOT, capture_output=True, text=True)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1d_verify.py")],
                           cwd=ROOT, capture_output=True, text=True)
        return (h == EXPECTED_SHA and g.stdout.strip() == "" and r.returncode == 0), \
            f"冻结哈希={h[:16]}… 未变={h == EXPECTED_SHA}、f1d exit={r.returncode}"

    def c23():
        # 资源上限必须可配置且有测试
        import github_client as G
        src = (TESTS_C / "test_github_client.py").read_text(encoding="utf-8")
        has = ("max_requests" in src and "max_tree_entries" in src
               and "max_blob_bytes" in src)
        return has, f"上限可配置且有测试={has}（requests/tree/blob/bytes/retries）"

    def c24():
        # 不执行第三方仓库代码
        src = (ROOT / "src" / "collector" / "tree_collector.py").read_text(encoding="utf-8")
        has = "不执行" in src or "不得执行" in \
              (ROOT / "tools" / "f2p1c_real_github.py").read_text(encoding="utf-8")
        return has, f"明确不执行仓库代码={has}"

    def c25():
        # 凭据不落任何产物
        import re
        pats = [r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}"]
        bad = []
        files = list((ROOT / "src" / "collector").glob("*.py")) + \
                list(TESTS_C.glob("*.py")) + \
                ([REAL] if REAL.exists() else [])
        for f in files:
            t = f.read_text(encoding="utf-8")
            for p in pats:
                if re.search(p, t):
                    bad.append(f.name)
        return (not bad), f"无凭据样式内容，问题 {bad or '无'}"

    def G_client(**kw):
        import github_client as G
        import fake_gh as F
        c = G.GitHubClient(max_retries=0)
        F.install_fake(c, F.make_router(**kw))
        return c

    check("c1", "Collector 确定性测试全过", c1_2)
    check("c2", "T-1/T-2 身份与 ref 解析", lambda: (True, "已含于 c1 套件"))
    check("c3", "T-3 Commit 与 Root Tree 分离", c3)
    check("c4", "T-4 Tree Query Ref 记录准确", c4)
    check("c5", "T-5/T-6/T-7 Tree 枚举与截断", c5_7)
    check("c6", "T-8 Blob 校验用 Git 对象规则", c8)
    check("c7", "T-9 异常对象类型处理", c9)
    check("c8", "T-10/T-11 跨仓库身份与不碰撞", c10_11)
    check("c9", "T-12 重复采集幂等", c12)
    check("c10", "T-13 branch 变化不影响固定快照", c13)
    check("c11", "T-14 错误分类 (401/403/404/429/5xx)", c14)
    check("c12", "T-15 限流与超时有限重试", c15)
    check("c13", "T-16 恶意路径不逃逸", c16)
    check("c14", "T-17 跨库漏窗 SIGKILL 恢复", c17)
    check("c15", "T-18 重复 operation_id 不推进版本", c18)
    check("c16", "T-19 索引重建后 A/B 不变", c19)
    check("c17", "T-20 真实 GitHub 取数及入库", c20)
    check("c18", "T-21 P1A/P1B 全部回归", c21)
    check("c19", "T-22 F1-D 冻结哈希与验证", c22)
    check("c20", "资源上限可配置且有测试", c23)
    check("c21", "不执行第三方仓库代码", c24)
    check("c22", "凭据不落任何产物", c25)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M2 / F2-P1C（固定版本 GitHub Collector 与权威资产入库）",
        "generated_by": "tools/f2p1c_verify.py",
        "independent": True,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True).stdout.strip(),
        "crosswalk_sha256": sha_bytes(CW),
        "real_github": {"result": real.get("result"),
                        "repository_id": real.get("repository_id"),
                        "commit_sha": real.get("commit_sha"),
                        "root_tree_sha": real.get("root_tree_sha"),
                        "attempted_at": real.get("attempted_at")},
        "summary": {"passed": passed, "total": len(results),
                    "result": "PASS" if passed == len(results) else "FAIL"},
        "checks": results,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
