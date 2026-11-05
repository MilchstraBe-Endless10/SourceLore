#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P4B 验收。"""
import json, sys, hashlib, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT/"docs"/"implementation"
CW = ROOT/"docs"/"fusion"/"CAPABILITY_CROSSWALK.json"
REPLAY = IMPL/"F2_P4B_E2E_REPLAY.json"
GOLD = IMPL/"F2_P4B_GOLD_EVALUATION.json"
OUT = IMPL/"F2_P4B_VERIFICATION.json"
EXPECTED_SHA = "42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b"

for p in ("src/research", "src/views", "src/renderer", "src/lifecycle",
          "src/storage", "src/facts", "src/collector", "src/runtime",
          "src/evidence_claims", "tests/research", "tests/views"):
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
    args = [sys.executable, "-m", "unittest", "discover",
            "-s", str(d), "-p", pattern]
    # ★ 有 __init__.py 且有同名历史条目的目录需要 -t
    if Path(d).name in ("research", "renderer", "views"):
        args += ["-t", str(ROOT)]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"Ran (\d+) test", r.stderr + r.stdout)
    return (int(m.group(1)) if m else 0), r.returncode


def main() -> int:
    prev = json.loads(REPLAY.read_text(encoding="utf-8")) if REPLAY.exists() else {}
    gold = json.loads(GOLD.read_text(encoding="utf-8")) if GOLD.exists() else {}
    sc = prev.get("scenarios", {})

    def c_suite():
        n, rc = run_dir(ROOT/"tests"/"research")
        return rc == 0, f"research 套件 {n} 项 exit={rc}"

    def c_gold_ok():
        ok = (gold.get("gold_count", 0) >= 20
              and gold.get("query_success_rate") == 1.0)
        return ok, (f"Gold {gold.get('gold_count')} 项，"
                    f"成功率 {gold.get('query_success_rate')}")

    def c_no_false_pos():
        return (gold.get("false_positive_count") == 0
                and not gold.get("false_positive_blocker")), \
            f"错误肯定={gold.get('false_positive_count')}"

    def c_no_false_neg():
        return (gold.get("false_negative_count") == 0
                and not gold.get("false_negative_blocker")), \
            f"错误否定={gold.get('false_negative_count')}"

    def c_abstention():
        return (gold.get("correct_abstention", 0) > 0
                and gold.get("wrong_abstention") == 0), \
            (f"正确abstention={gold.get('correct_abstention')} "
             f"错误={gold.get('wrong_abstention')}")

    def c_gold_not_derived():
        return gold.get("not_derived_from_research") is True, \
            "Gold 由人工定义，不由 Research 输出反推"

    def c_gold_has_negative():
        return gold.get("has_negative_examples") is True, \
            "Gold 含实际负例"

    def c_limitation_rate():
        r = gold.get("limitation_retention_rate")
        return (r is not None and r == 1.0), f"限制保留率={r}"

    def c_readonly():
        ok = all(s.get("read_only") for s in sc.values()) and bool(sc)
        return ok, f"{len(sc)} 个场景全部只读={ok}"

    def c_no_network():
        bad = []
        for f in (ROOT/"src"/"research").glob("*.py"):
            t = f.read_text(encoding="utf-8")
            for tok in ("import requests", "urllib.request", "http.client",
                        "socket", "GitHubClient"):
                if tok in t:
                    bad.append(f"{f.name}:{tok}")
        return (not bad), f"网络客户端: {bad or '无'}"

    def c_no_llm():
        pat = re.compile(
            r"\b(import|from)\s+(openai|anthropic|google\.generativeai|cohere)\b",
            re.I)
        bad = [f.name for f in (ROOT/"src"/"research").glob("*.py")
               if pat.search(f.read_text(encoding="utf-8"))]
        return (not bad), f"LLM 依赖: {bad or '无'}"

    def c_no_second_db():
        bad = [f.name for f in (ROOT/"src"/"research").glob("*.py")
               if "CREATE TABLE" in f.read_text(encoding="utf-8")]
        return (not bad), f"新建表: {bad or '无'}"

    def c_no_verifier():
        bad = [f.name for f in (ROOT/"src"/"research").glob("*.py")
               if "verify_path_claim" in f.read_text(encoding="utf-8")]
        return (not bad), f"重新裁决: {bad or '无'}"

    def c_no_writes():
        bad = []
        for f in (ROOT/"src"/"research").glob("*.py"):
            t = f.read_text(encoding="utf-8")
            for tok in ("append_asset_and_advance", "ingest_fact",
                        "ingest_claim", "ingest_verification", "extract_"):
                if tok in t:
                    bad.append(f"{f.name}:{tok}")
        return (not bad), f"写操作: {bad or '无'}"

    def c_canonical():
        f = IMPL/"F2_P4B_RESEARCH_CANONICAL_AUDIT.json"
        if not f.exists():
            return False, "canonical 审计缺失"
        a = json.loads(f.read_text(encoding="utf-8"))
        ids = [x["id"] for x in a["research_canonicals"]]
        return (ids == ["SL-CAP-0035", "SL-CAP-0036", "SL-CAP-0037",
                        "SL-CAP-0038", "SL-CAP-0039"]), \
            f"Research canonical = {ids}"

    def c_retrieval_audit():
        f = IMPL/"F2_P4B_RETRIEVAL_CAPABILITY_AUDIT.json"
        if not f.exists():
            return False, "检索能力审计缺失"
        a = json.loads(f.read_text(encoding="utf-8"))
        no_fts = any("FTS5" in x for x in a["verdict"]["not_available"])
        return no_fts, "明确记录 FTS5 全文检索不可用（index_rows 无 text 列）"

    def c_times():
        ok = (prev.get("live_github_refetch") is False
              and prev.get("real_human_authorization") is False
              and prev.get("llm_called") is False)
        return ok, (f"live={prev.get('live_github_refetch')} "
                    f"real_auth={prev.get('real_human_authorization')} "
                    f"llm={prev.get('llm_called')}")

    def c_not_authority():
        ok = all(s["packets"][k]["packet_status"] != ""
                 for s in sc.values() for k in s["packets"])
        return ok and bool(sc), f"研究包状态齐备={ok}"

    def c_preview_gate():
        ok = all(s["pre_publish"]["preview_allowed"] is True
                 and s["pre_publish"]["distribution_allowed"] is False
                 for s in sc.values())
        return ok, f"预览允许/分发拒绝={ok}"

    def c_p4a_regression():
        n, rc = run_dir(ROOT/"tests"/"research", "test_p4a_regression.py")
        return rc == 0, f"P4A 回归 {n} 项 exit={rc}"

    def c_stages():
        """P3C 八阶段：真实写入且非全 PENDING。"""
        import tempfile, shutil
        import rfx
        tmp = Path(tempfile.mkdtemp(prefix="v_stage_"))
        ok = False
        detail = ""
        try:
            with rfx.fresh(tmp) as ks:
                rfx.vfx.run_full(ks)
                row = ks.conn.execute(
                    "SELECT payload_json FROM assets "
                    "WHERE asset_type='revalidation_run' "
                    "ORDER BY rowid DESC LIMIT 1").fetchone()
                p = json.loads(row["payload_json"])
                states = {s["stage"]: s["state"] for s in p["stages"]}
                non_pending = [k for k, v in states.items() if v != "PENDING"]
                ok = len(states) == 8 and len(non_pending) == 8
                detail = f"8 阶段均非 PENDING={ok}；状态={sorted(set(states.values()))}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return ok, detail

    def c_regression():
        dirs = ["runtime", "storage", "collector", "facts",
                "evidence_claims", "lifecycle", "views", "renderer"]
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
            f"SHA={h[:16]}… 未变={h == EXPECTED_SHA} f1d exit={r.returncode}"

    def c_outputs():
        need = []
        for k, s in sc.items():
            for f in (s.get("files") or {}).values():
                p = ROOT/f
                if not p.exists() or p.stat().st_size == 0:
                    need.append(f)
        return (not need), f"回放产物齐备={not need}（缺失 {need}）"

    def c_output_dir():
        p = prev.get("output_dir") or ""
        ok = p.startswith("docs/preview/") and not any(
            x in p for x in ("docs/fusion", "progress/", "kb.db"))
        return ok, f"输出目录受控={p}"

    check("c1", "research 全套测试", c_suite)
    check("c2", "离线 Gold 全通过", c_gold_ok)
    check("c3", "错误肯定为 0", c_no_false_pos)
    check("c4", "错误否定为 0", c_no_false_neg)
    check("c5", "abstention 正确", c_abstention)
    check("c6", "Gold 非反推", c_gold_not_derived)
    check("c7", "Gold 含负例", c_gold_has_negative)
    check("c8", "限制保留率 100%", c_limitation_rate)
    check("c9", "只读性（A/B/C/oplog）", c_readonly)
    check("c10", "无网络客户端", c_no_network)
    check("c11", "无 LLM 依赖", c_no_llm)
    check("c12", "未建第二套数据库", c_no_second_db)
    check("c13", "不重新裁决", c_no_verifier)
    check("c14", "无写操作", c_no_writes)
    check("c15", "Research canonical 对应", c_canonical)
    check("c16", "检索能力缺口如实记录", c_retrieval_audit)
    check("c17", "如实报告未联网/无授权/未用 LLM", c_times)
    check("c18", "研究包状态齐备", c_not_authority)
    check("c19", "预览与分发门禁独立", c_preview_gate)
    check("c20", "P4A 两项回归核验", c_p4a_regression)
    check("c21", "P3C 八阶段真实写入", c_stages)
    check("c22", "既有模块全链回归", c_regression)
    check("c23", "F1-D 冻结哈希", c_frozen)
    check("c24", "回放产物齐备", c_outputs)
    check("c25", "输出目录受控", c_output_dir)

    passed = sum(1 for r in results if r["passed"])
    out = {"task": "M2 / F2-P4B（确定性研究检索与研究包）",
           "generated_by": "tools/f2p4b_verify.py", "independent": True,
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      capture_output=True, text=True).stdout.strip(),
           "crosswalk_sha256": hashlib.sha256(CW.read_bytes()).hexdigest(),
           "llm_called": False,
           "live_github_refetch": prev.get("live_github_refetch"),
           "real_human_authorization": prev.get("real_human_authorization"),
           "summary": {"passed": passed, "total": len(results),
                       "result": "PASS" if passed == len(results) else "FAIL"},
           "checks": results}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n",
                   encoding="utf-8")
    print(f"\n{passed}/{len(results)} PASS -> {OUT.name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
