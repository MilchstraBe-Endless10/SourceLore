#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑 F2-P4C 合成 Gold。"""
import sys, json, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
for p in ("src/research", "src/views", "src/lifecycle", "src/storage",
          "src/collector", "src/facts", "src/evidence_claims", "src/runtime",
          "tests/research", "tests/views", "tests/research/gold"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import rfx
import statement_bank as SB, llm_adapter as LA, synthesis_engine as SE
import gold_synthesis as GS


def run():
    tmp = Path(tempfile.mkdtemp(prefix="gold_syn_"))
    ks = rfx.fresh(tmp)
    rows = []
    try:
        rfx.vfx.run_full(ks)
        pkt_sup = rfx.run(ks, rfx.q_claims())
        # insufficient 场景
        tmp2 = Path(tempfile.mkdtemp(prefix="gold_syn_ins_"))
        ks2 = rfx.fresh(tmp2)
        try:
            rfx.vfx.run_full(ks2, truncated=True)
            pkt_ins = rfx.run(ks2, rfx.q_claims(commit_sha=rfx.B))
        finally:
            ks2.close(); shutil.rmtree(tmp2, ignore_errors=True)

        for g in GS.GOLD_SYNTHESIS:
            case = g["case"]
            if case == "insufficient":
                pkt = pkt_ins
            else:
                pkt = pkt_sup
            bank = SB.build_bank(pkt)
            kind_map = {s["kind"]: [x["statement_id"]
                                    for x in bank["statements"]
                                    if x["kind"] == s["kind"]]
                        for s in bank["statements"]}
            if case == "fake_ref":
                refs = ["SL-ST-FAKE"]
            elif case == "uncited":
                refs = []
            elif case == "limitation":
                refs = kind_map.get(SB.S_LIMITATION, [])
            elif case == "insufficient":
                refs = kind_map.get(SB.S_INSUFFICIENT,
                                    kind_map.get(SB.S_SUPPORTED, []))
            else:
                refs = kind_map.get(SB.S_SUPPORTED,
                                    kind_map.get(SB.S_INSUFFICIENT, []))
            preset = dict(g["preset"]); preset["statement_refs"] = refs
            r = SE.synthesize(pkt, client=LA.make_stub_client(preset))
            gold = g["gold"]
            checks = {"verdict": r["verdict"] == gold["verdict"]}
            if gold.get("blocking"):
                checks["blocking"] = bool(
                    r["validation"]["blocking_failures"])
            if gold.get("must_be_review_required"):
                checks["review"] = r["review_required"]
            checks["never_publish"] = (not r["publishable"]
                                       and not r["is_knowledge_authority"])
            rows.append({"id": g["id"], "case": case,
                         "verdict": r["verdict"],
                         "blocking": list(r["validation"]["blocking_failures"]),
                         "checks": checks, "passed": all(checks.values()),
                         "false_negative": bool(gold.get("false_negative")
                                               and r["verdict"]
                                               == LA.SYN_STRICT)})
    finally:
        ks.close(); shutil.rmtree(tmp, ignore_errors=True)

    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    fp = [r["id"] for r in rows if r["verdict"] == LA.SYN_STRICT
          and not r["passed"]]
    fn = [r["id"] for r in rows if r["false_negative"]]
    return {
        "artifact": "F2_P4C_GOLD_SYNTHESIS_EVALUATION",
        "gold_count": total,
        "gold_source": "人工定义（tests/research/gold/gold_synthesis.py）",
        "not_derived_from_research": True,
        "query_success_rate": round(passed / total, 3) if total else 0,
        "false_positive_count": len(fp),
        "false_negative_count": len(fn),
        "false_positive_blocker": bool(fp),
        "false_negative_blocker": bool(fn),
        "real_llm_called": False,
        "real_call_verified": False,
        "rows": rows,
        "blocked": bool(fp or fn),
    }


if __name__ == "__main__":
    r = run()
    out = ROOT/"docs"/"implementation"/"F2_P4C_GOLD_SYNTHESIS.json"
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2)+"\n",
                   encoding="utf-8")
    print(f"P4C Gold {r['gold_count']} 项，通过 "
          f"{int(r['query_success_rate']*r['gold_count'])}")
    for row in r["rows"]:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"  [{mark}] {row['id']:26s} {row['verdict']:22s} "
              f"blocking={row['blocking']}")
    print(f"\n错误肯定={r['false_positive_count']} "
          f"错误否定={r['false_negative_count']} 阻断={r['blocked']}")
