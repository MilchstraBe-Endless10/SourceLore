#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P4C 端到端回放：packet → bank → adapter → 校验 → 分级。

★ 不联网、不调真实 LLM。stub 只验证校验通路。
"""
import sys, json, tempfile, shutil, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("src/research", "src/views", "src/renderer", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views", "tests/research"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import rfx
import statement_bank as SB, llm_adapter as LA, synthesis_engine as SE
import card_models as CM, card_renderer as CRD, pre_publish_check as PPC

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"preview"/"f2p4c"
SUMMARY = ROOT/"docs"/"implementation"/"F2_P4C_E2E_REPLAY.json"


def _run_case(pkt, preset):
    bank = SB.build_bank(pkt)
    ids = {s["kind"]: [x["statement_id"] for x in bank["statements"]
                       if x["kind"] == s["kind"]]
           for s in bank["statements"]}
    src = preset.pop("_refs_from", None)   # ★ 未指定即**无引用**
    preset["statement_refs"] = (ids.get(src, []) if src else [])
    return SE.synthesize(pkt, client=LA.make_stub_client(preset))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="p4c_"))
    ks = rfx.fresh(tmp)
    scen = {}
    try:
        rfx.vfx.run_full(ks)
        pkt = rfx.run(ks, rfx.q_claims())

        cases = {
            "c1_strict": {"text": "在固定 Commit 上，该路径存在命题的裁决为 supported（支持）。",
                          "_refs_from": SB.S_SUPPORTED},
            "c2_draft": {"text": "该路径存在。"},
            "c3_rejected_amplify": {"text": "该软件完全正确，功能完备。",
                                    "_refs_from": SB.S_SUPPORTED},
            "c4_rejected_negation": {"text": "该命题为假。",
                                     "_refs_from": SB.S_SUPPORTED},
        }
        for name, preset in cases.items():
            r = _run_case(pkt, dict(preset))
            scen[name] = {
                "verdict": r["verdict"],
                "adapter_state": r["adapter_state"],
                "blocking": r["validation"]["blocking_failures"],
                "uncited": r["validation"]["uncited_count"],
                "ungrounded": r["validation"].get("ungrounded_count", 0),
                "review_required": r["review_required"],
                "never_publish": not r["publishable"]
                and not r["is_knowledge_authority"],
                "synthesis_id": r.get("synthesis_id"),
            }

        # 无客户端
        r0 = SE.synthesize(pkt)
        scen["c0_no_client"] = {"verdict": r0["synthesis_state"],
                                "llm_used": r0["llm_used"],
                                "text_len": len(r0["text"])}

        # 用 P4A Renderer 呈现 STRICT 产物
        bank = SB.build_bank(pkt)
        sid = [s["statement_id"] for s in bank["statements"]
               if s["kind"] == SB.S_SUPPORTED]
        r = SE.synthesize(pkt, client=LA.make_stub_client(
            {"text": "在固定 Commit 上，该路径存在命题的裁决为 supported（支持）。",
             "statement_refs": sid}))
        f0 = pkt["findings"][0]
        view_like = {
            "view_id": pkt["query_id"], "query_scope": "RESEARCH_SYNTHESIS",
            "repository_id": pkt["query"]["repository_id"],
            "claim_commit_sha": pkt["query"]["commit_sha"],
            "claim_id": f0["claim_id"], "claim_type": f0["claim_type"],
            "verification_status": f0["verdict_status"],
            "verification_id": f0["verification_id"],
            "verification_rule_version": "path-exists-verifier/v1",
            "freshness_state": "UNKNOWN",
            "current_applicability": "CURRENT_APPLICABILITY_UNKNOWN",
            "review_status": f0["review_status"],
            "provenance_level": "SYNTHETIC_FIXTURE",
            "authorization_class": "TEST_ONLY_ISOLATED",
            "authorization_is_test_only": True,
            "evidence_refs": list(pkt["evidence_refs"])[:5],
            "fact_refs": list(pkt["fact_refs"])[:5],
            "source_snapshot_refs": list(pkt["source_snapshot_refs"])[:5],
            "limitations": list(r["limitations"]),
            "distribution_restrictions": pkt["distribution_restrictions"],
            "claim_payload": f0["claim_payload"],
        }
        card = CM.build_card(view_like)
        html = CRD.render_card_html(card)
        pchk = PPC.pre_publish_check(
            {"html": html, "json": json.loads(CRD.render_json(card))},
            {"authorization_is_test_only": True,
             "provenance_level": "SYNTHETIC_FIXTURE",
             "no_usable_evidence": False, "conflict_indicators": {},
             "limitations": r["limitations"]},
            pkt["distribution_restrictions"])

        d = OUT/"s1_synthesis"
        d.mkdir(parents=True, exist_ok=True)
        (d/"synthesis.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
            encoding="utf-8")
        (d/"bank.json").write_text(
            json.dumps(bank, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
            encoding="utf-8")
        (d/"preview.html").write_text(html, encoding="utf-8")
        (d/"packet.json").write_text(
            json.dumps(pkt, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
            encoding="utf-8")

        scen["preview"] = {
            "preview_allowed": pchk["preview_allowed"],
            "distribution_allowed": pchk["distribution_allowed"],
            "html_has_script": "<script" in html.lower(),
            "html_csp": "Content-Security-Policy" in html,
        }
        files = {k: str((d/k).relative_to(ROOT)) for k in
                 ("synthesis.json", "bank.json", "preview.html", "packet.json")}
    finally:
        ks.close()
        shutil.rmtree(tmp, ignore_errors=True)

    OUT.mkdir(parents=True, exist_ok=True)
    gold_f = ROOT/"docs"/"implementation"/"F2_P4C_GOLD_SYNTHESIS.json"
    gold = (json.loads(gold_f.read_text(encoding="utf-8"))
            if gold_f.exists() else {})

    summary = {
        "artifact": "F2_P4C_E2E_REPLAY",
        "generated_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
        "llm_called": False,
        "real_llm_called": False,
        "real_call_verified": False,
        "live_github_refetch": False,
        "real_human_authorization": False,
        "adapter_used": "OFFLINE_STUB (校验通路验证)",
        "note": ("stub 输出只验证引用校验通路，不代表任何真实模型能力；"
                 "真实 DeepSeek-V4.1 Flash 调用仍待验证"),
        "output_dir": str(OUT.relative_to(ROOT)),
        "scenarios": scen,
        "gold": {k: gold.get(k) for k in
                 ("gold_count", "query_success_rate",
                  "false_positive_count", "false_negative_count", "blocked")},
        "files": files,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n",
                       encoding="utf-8")

    print("P4C 场景:")
    for k, v in scen.items():
        print(f"  {k}: {v}")
    print("Gold:", summary["gold"])
    print("输出:", summary["output_dir"])


if __name__ == "__main__":
    main()
