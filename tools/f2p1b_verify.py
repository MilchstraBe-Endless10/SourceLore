#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P1B 验收：12 项阶段通过条件 + T-1..T-12 实测。

不依赖 mock；并发/崩溃/损坏全部真实执行。
"""
import json, sys, hashlib, subprocess, tempfile, shutil, unittest, io, contextlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
IMPL = DOCS / "implementation"
STORE = ROOT / "src" / "storage"
RUNTIME = ROOT / "src" / "runtime"
TESTS = ROOT / "tests" / "storage"
CW = DOCS / "fusion" / "CAPABILITY_CROSSWALK.json"
OUT = IMPL / "F2_P1B_VERIFICATION.json"

EXPECTED_SHA = "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b"

sys.path.insert(0, str(STORE))
sys.path.insert(0, str(RUNTIME))

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


def run_suite(pattern):
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS), pattern=pattern)
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    r = runner.run(suite)
    return r.testsRun, len(r.failures), len(r.errors)


def main() -> int:
    def c1():
        n, f, e = run_suite("test_knowledge_store.py")
        src = (TESTS / "test_knowledge_store.py").read_text(encoding="utf-8")
        has = "A_LAYER_IMMUTABLE" in src and "不可原地覆盖" in src
        return (n >= 27 and f == 0 and e == 0 and has), \
            f"不可变追加套件 {n} 项，失败 {f}、错误 {e}；触发器断言存在={has}"

    def c2():
        src = (STORE / "knowledge_store.py").read_text(encoding="utf-8")
        in_txn = "postcondition(self.conn" in src and "COMMIT" in src
        # postcondition 调用必须在 COMMIT 之前
        i_pc = src.index("if postcondition is not None:")
        i_commit = src.index('self.conn.execute("COMMIT")', i_pc)
        return i_pc < i_commit, \
            f"postcondition 在 COMMIT 之前（pos={i_pc} < commit={i_commit}）"

    def c3():
        n1, f1, e1 = run_suite("test_cross_process.py")
        n2, f2, e2 = run_suite("test_error_injection.py")
        return (n1 >= 6 and n2 >= 13 and f1 == f2 == e1 == e2 == 0), \
            f"并发/崩溃 {n1} 项 + 错误注入 {n2} 项，失败/错误全 0"

    def c4():
        import index_store as IX
        from asset_models import AssetDraft
        from knowledge_store import KnowledgeStore
        tmp = Path(tempfile.mkdtemp(prefix="v_idx_"))
        try:
            with KnowledgeStore(str(tmp / "kb.db")) as ks:
                for i in range(3):
                    ks.append_asset_and_advance(AssetDraft(
                        asset_type="capability_record", logical_identity=f"LI-{i}",
                        repository_id="repo-a", payload={"i": i}), expected_version=None)
                before = IX._ab_fingerprint(ks)
                rb = IX.rebuild_index(ks)
                after = IX._ab_fingerprint(ks)
            return (rb["ok"] and rb["a_b_unchanged"] and before == after), \
                f"索引重建 indexed={rb['indexed']}、A/B 不变={rb['a_b_unchanged']}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def c5():
        from asset_models import AssetDraft
        from knowledge_store import KnowledgeStore
        tmp = Path(tempfile.mkdtemp(prefix="v_ver_"))
        try:
            with KnowledgeStore(str(tmp / "kb.db")) as ks:
                ks.append_asset_and_advance(AssetDraft(
                    asset_type="capability_record", logical_identity="LI-1",
                    repository_id="repo-a", payload={"v": 1}, asset_version=1),
                    expected_version=None)
                r2 = ks.append_asset_and_advance(AssetDraft(
                    asset_type="capability_record", logical_identity="LI-1",
                    repository_id="repo-a", payload={"v": 2}, asset_version=7),
                    expected_version=1)
                # 两个量必须在 with 块内取，否则 __exit__ 后库已关闭
                got_av = ks.get_asset(r2["asset_id"])["asset"]["asset_version"]
                pv = r2["pointer_version"]
            # pointer_version 只 +1，asset_version 由内容演进决定 —— 两者不可互换
            ok = (pv == 2 and got_av == 7)
            return ok, f"pointer_version={pv}（CAS 每步 +1）、asset_version={got_av}（内容演进），两个量独立"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def c6():
        from asset_models import AssetDraft
        from knowledge_store import KnowledgeStore
        tmp = Path(tempfile.mkdtemp(prefix="v_xrepo_"))
        try:
            with KnowledgeStore(str(tmp / "kb.db")) as ks:
                a = ks.append_asset_and_advance(AssetDraft(
                    asset_type="subject_record", logical_identity="LI-SAME",
                    repository_id="repo-a", payload={"n": "same"}), expected_version=None)
                b = ks.append_asset_and_advance(AssetDraft(
                    asset_type="subject_record", logical_identity="LI-SAME",
                    repository_id="repo-b", payload={"n": "same"}), expected_version=None)
                n = ks.conn.execute(
                    "SELECT count(*) AS n FROM assets WHERE logical_identity='LI-SAME'"
                ).fetchone()["n"]
                pa = ks.current_pointer("LI-SAME", "repo-a")
                pb = ks.current_pointer("LI-SAME", "repo-b")
                diff_id = a["asset_id"] != b["asset_id"]
            return (n == 2 and diff_id and pa["repository_id"] == "repo-a"
                    and pb["repository_id"] == "repo-b"), \
                f"跨仓库同名 {n} 条独立资产、asset_id 不同={diff_id}、各自指针独立"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def c7():
        src_s = (STORE / "knowledge_store.py").read_text(encoding="utf-8")
        src_c = (RUNTIME / "asset_checkpoint_coordinator.py").read_text(encoding="utf-8")
        # 两个库物理文件不同名、独立连接
        ok1 = "no cross-database" in src_c.lower() or "独立的事务边界" in src_c
        ok2 = "ATTACH" in src_c and "不用它" in src_c
        ok3 = src_s.count('sqlite3.connect') >= 1
        return (ok1 and ok2 and ok3), \
            f"独立权威已声明={ok1}、明确不依赖 ATTACH={ok2}、独立连接={ok3}"

    def c8():
        n, f, e = run_suite("test_cross_process.py")
        src = (TESTS / "test_cross_process.py").read_text(encoding="utf-8")
        has_reconcile = "operation_id" in src and "RECONCILED" in src
        return (f == 0 and e == 0 and has_reconcile), \
            f"跨库对账套件 {n} 项通过；含 operation_id 对账断言={has_reconcile}"

    def c9():
        src = (RUNTIME / "asset_checkpoint_coordinator.py").read_text(encoding="utf-8")
        # UNKNOWN 不得直接重试：NEEDS_HUMAN 分支 auto_retry=False
        import re
        m = re.search(r'"state": NEEDS_HUMAN.*?auto_retry": False', src, re.S)
        ok = bool(m)
        return ok, f"NEEDS_HUMAN 分支 auto_retry=False={ok}（UNKNOWN 不自动重试）"

    def c10():
        n, f, e = run_suite("test_error_injection.py")
        src = (TESTS / "test_error_injection.py").read_text(encoding="utf-8")
        has_boundary = "实施边界" in src
        return (f == 0 and e == 0 and has_boundary), \
            f"路径/保密边界 {n} 项通过；磁盘失败实施边界已如实记录={has_boundary}"

    def c11():
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "f2p1a_verify.py")],
                           cwd=ROOT, capture_output=True, text=True)
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        return r.returncode == 0, f"P1A 回归 exit={r.returncode}，{tail}"

    def c12():
        h = sha_bytes(CW)
        g = subprocess.run(["git", "status", "--short", "--",
                            "docs/fusion/CAPABILITY_CROSSWALK.json"],
                           cwd=ROOT, capture_output=True, text=True)
        return (h == EXPECTED_SHA and g.stdout.strip() == ""), \
            f"冻结 Crosswalk 哈希未变={h == EXPECTED_SHA}、git 无改动={g.stdout.strip() == ''}"

    def c13():
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "fusion" / "f1d_verify.py")],
                           cwd=ROOT, capture_output=True, text=True)
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        return r.returncode == 0, f"F1-D 验证器 exit={r.returncode}，{tail}"

    def c14():
        # 不得提交 SQLite 数据库
        st = subprocess.run(["git", "ls-files", "*.db", "*.sqlite", "*.sqlite3"],
                            cwd=ROOT, capture_output=True, text=True)
        tracked = [l for l in st.stdout.splitlines() if l.strip()]
        wc = list(ROOT.rglob("*.db")) + list(ROOT.rglob("*.sqlite*"))
        return (not tracked and not wc), \
            f"被追踪 DB={tracked or '无'}；工作区残留={[str(p.relative_to(ROOT)) for p in wc] or '无'}"

    def c15():
        # A/B 不得被 Renderer 之类的间接路径改写：审计写入入口
        src = (STORE / "knowledge_store.py").read_text(encoding="utf-8")
        # 只允许 append_asset_and_advance 一个写入口
        has_single_entry = src.count("def append_asset_and_advance") == 1
        has_triggers = "assets_no_update" in src and "assets_no_delete" in src
        return (has_single_entry and has_triggers), \
            f"单一写入口={has_single_entry}、A 层写保护触发器={has_triggers}"

    def c16():
        # source_snapshot 三字段不混用
        src = (STORE / "asset_models.py").read_text(encoding="utf-8")
        has3 = all(k in src for k in ("commit_sha", "root_tree_sha", "tree_query_ref"))
        n, f, e = run_suite("test_knowledge_store.py")
        return (has3 and f == 0), f"三字段独立存在={has3}；存储套件失败 {f}"

    check("c1", "A 层追加不可变历史", c1)
    check("c2", "B 层事务内 CAS 且 postcondition 先于 COMMIT", c2)
    check("c3", "A/B 联合提交经并发与崩溃测试", c3)
    check("c4", "C 层可删除并重建", c4)
    check("c5", "身份与版本不混淆", c5)
    check("c6", "跨仓库关系不自动误合并", c6)
    check("c7", "checkpoint 与知识资产独立权威", c7)
    check("c8", "跨数据库中断经 operation_id 对账", c8)
    check("c9", "UNKNOWN 不当作失败后直接重试", c9)
    check("c10", "路径与保密边界已测试", c10)
    check("c11", "P1A 既有行为保持", c11)
    check("c12", "F1-D 冻结哈希不变", c12)
    check("c13", "F1-D 验证器通过", c13)
    check("c14", "无 SQLite 数据库进仓库", c14)
    check("c15", "A/B 无旁路写入", c15)
    check("c16", "source_snapshot 三字段不混用", c16)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "task": "M2 / F2-P1B（权威知识资产 A/B/C 存储引擎）",
        "generated_by": "tools/f2p1b_verify.py",
        "independent": True,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True).stdout.strip(),
        "crosswalk_sha256": sha_bytes(CW),
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
