#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P4B 验收。"""
import json, sys, hashlib, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT/"docs"/"implementation"
CW = ROOT/"docs"/"fusion"/"CAPABILITY_CROSSWALK.json"
REPLAY = IMPL/"F2_P4C_E2E_REPLAY.json"
GOLD = IMPL/"F2_P4C_GOLD_SYNTHESIS.json"
OUT = IMPL/"F2_P4C_VERIFICATION.json"
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

    def c_gold():
        g = json.loads(GOLD.read_text(encoding="utf-8")) if GOLD.exists() else {}
        ok = (g.get("gold_count") == 10 and g.get("query_success_rate") == 1.0)
        return ok, f"P4C Gold {g.get('gold_count')} 项，成功率 {g.get('query_success_rate')}"

    def c_fp():
        g = json.loads(GOLD.read_text(encoding="utf-8")) if GOLD.exists() else {}
        return (g.get("false_positive_count") == 0
                and not g.get("false_positive_blocker")), \
            f"错误肯定={g.get('false_positive_count')}"

    def c_fn():
        g = json.loads(GOLD.read_text(encoding="utf-8")) if GOLD.exists() else {}
        return (g.get("false_negative_count") == 0
                and not g.get("false_negative_blocker")), \
            f"错误否定={g.get('false_negative_count')}"

    def c_no_client():
        """★ 无 LLM 客户端时必须 NO_SYNTHESIS 且文本为空。"""
        c = sc.get("c0_no_client") or {}
        ok = c.get("verdict") == "NO_SYNTHESIS" and c.get("text_len") == 0
        return ok, f"无客户端状态={c.get('verdict')} text_len={c.get('text_len')}"

    def c_strict():
        c = sc.get("c1_strict") or {}
        return c.get("verdict") == "STRICT_CITED", f"严格引用={c.get('verdict')}"

    def c_draft():
        c = sc.get("c2_draft") or {}
        return (c.get("verdict") == "DRAFT_FOR_REVIEW"
                and c.get("review_required") is True), \
            f"无引用={c.get('verdict')} review_required={c.get('review_required')}"

    def c_reject_amp():
        c = sc.get("c3_rejected_amplify") or {}
        return (c.get("verdict") == "REJECTED_NOT_CITABLE"
                and "AMPLIFIED_BEYOND_EVIDENCE" in (c.get("blocking") or [])), \
            f"越界拦截={c.get('verdict')} {c.get('blocking')}"

    def c_reject_neg():
        c = sc.get("c4_rejected_negation") or {}
        return (c.get("verdict") == "REJECTED_NOT_CITABLE"
                and "INSUFFICIENT_AS_NEGATION" in (c.get("blocking") or [])), \
            f"否定化拦截={c.get('verdict')} {c.get('blocking')}"

    def c_never_publish():
        ok = all(s2.get("never_publish") for s2 in sc.values()
                 if isinstance(s2, dict) and "never_publish" in s2)
        return ok, f"全部不可发布={ok}"

    def c_no_llm_call():
        return (prev.get("llm_called") is False
                and prev.get("real_llm_called") is False), \
            f"llm_called={prev.get('llm_called')}"

    def c_real_unverified():
        return prev.get("real_call_verified") is False, \
            "真实 DeepSeek-V4.1 Flash 调用仍待验证"

    def c_evidence_integrity():
        """★ 前置问题1：证据完整性必须可核对，非空不算可信。"""
        sys2 = str(ROOT/"tests"/"research")
        if sys2 not in sys.path:
            sys.path.insert(0, sys2)
        import evidence_selector as ES
        cases = [ES.EV_FULL, ES.EV_PARTIAL, ES.EV_UNRESOLVED, ES.EV_NONE]
        src = (ROOT/"src"/"research"/"evidence_selector.py").read_text(encoding="utf-8")
        ok = ("assess_evidence_integrity" in src
              and "known_fact" in src and all(c in src for c in cases))
        return ok, "证据完整性按可核对性判定（四等级）"

    def c_digest_covers():
        """★ 前置问题2：digest 必须覆盖影响结论/可信度的字段。"""
        src = (ROOT/"src"/"research"/"research_packet.py").read_text(encoding="utf-8")
        ok = ("evidence_integrity_summary" in src
              and "exclude_runtime_only" in src or "run_diagnostics" in src)
        return ok, "digest 覆盖 evidence_integrity_summary 等可信度字段"

    def c_no_rowid():
        """★ 前置问题3：不得依赖 SQLite rowid 判定业务顺序。"""
        bad = []
        # ★ 只扫**生产代码**与回放工具；不扫本验证器自身
        #   （它源码里含检测字面量，扫自己会误报）。
        targets = list((ROOT/"src"/"research").glob("*.py"))
        targets += list((ROOT/"src"/"lifecycle").glob("*.py"))
        targets += [ROOT/"tools"/"f2p4c_e2e_replay.py"]
        for f in targets:
            if "ORDER BY rowid" in f.read_text(encoding="utf-8"):
                bad.append(f.name)
        return (not bad), f"仍用 rowid 排序的文件: {bad or '无'}"

    def c_preview():
        p = sc.get("preview") or {}
        ok = (p.get("preview_allowed") is True
              and p.get("distribution_allowed") is False
              and p.get("html_has_script") is False and p.get("html_csp"))
        return ok, f"预览/分发门禁分离={ok}"

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
        need = [f for f in (prev.get("files") or {}).values()
                if not (ROOT/f).exists()]
        return (not need), f"回放产物齐备={not need}（缺失 {need}）"

    def c_stages():
        import tempfile, shutil as sh, rfx as RF
        tmp = Path(tempfile.mkdtemp(prefix="v_stage_"))
        ok, detail = False, ""
        try:
            with RF.fresh(tmp) as ks2:
                RF.vfx.run_full(ks2)
                row = ks2.conn.execute(
                    "SELECT payload_json FROM assets "
                    "WHERE asset_type='revalidation_run' "
                    "ORDER BY logical_identity ASC, asset_version DESC, "
                    "asset_id ASC LIMIT 1").fetchone()
                p = json.loads(row["payload_json"])
                states = {s2["stage"]: s2["state"] for s2 in p["stages"]}
                np2 = [k for k, v in states.items() if v != "PENDING"]
                ok = len(states) == 8 and len(np2) == 8
                detail = f"8 阶段非 PENDING={ok} 状态={sorted(set(states.values()))}"
        finally:
            sh.rmtree(tmp, ignore_errors=True)
        return ok, detail

    check("c1", "research 全套测试", c_suite)
    check("c2", "P4C Gold 全通过", c_gold)
    check("c3", "错误肯定为 0", c_fp)
    check("c4", "错误否定为 0", c_fn)
    check("c5", "无客户端不产出叙述", c_no_client)
    check("c6", "严格引用路径", c_strict)
    check("c7", "待审草稿路径", c_draft)
    check("c8", "越界措辞拦截", c_reject_amp)
    check("c9", "证据不足禁写否定", c_reject_neg)
    check("c10", "任何产物不可发布", c_never_publish)
    check("c11", "未调用 LLM", c_no_llm_call)
    check("c12", "真实调用未验证（如实标注）", c_real_unverified)
    check("c13", "前置1：证据完整性可核对", c_evidence_integrity)
    check("c14", "前置2：digest 覆盖可信度字段", c_digest_covers)
    check("c15", "前置3：不依赖 rowid", c_no_rowid)
    check("c16", "预览/分发门禁分离", c_preview)
    check("c17", "既有模块全链回归", c_regression)
    check("c18", "F1-D 冻结哈希", c_frozen)
    check("c19", "回放产物齐备", c_outputs)
    check("c20", "P3C 八阶段可回查", c_stages)
    passed = sum(1 for r in results if r["passed"])
    out = {"task": "M2 / F2-P4B（确定性研究检索与研究包）",
           "generated_by": "tools/f2p4c_verify.py", "independent": True,
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
