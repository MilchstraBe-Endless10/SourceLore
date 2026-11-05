#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P4B 端到端回放：真实 SQLite + 真实 KnowledgeView + 离线 Gold。

★ 不联网、不调 LLM、不使用真实人类授权。
"""
import sys, json, tempfile, shutil, datetime, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("src/research", "src/views", "src/renderer", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views", "tests/research",
          "tests/research/gold"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import rfx
import query_models as QM, research_engine as RE
import card_models as CM, card_renderer as CRD, report_renderer as RPT
import pre_publish_check as PPC
import view_integrity as VI

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"preview"/"f2p4b"
SUMMARY = ROOT/"docs"/"implementation"/"F2_P4B_E2E_REPLAY.json"


def _view_like(p):
    f0 = p["findings"][0] if p["findings"] else None
    return {
        "view_id": p["query_id"], "query_scope": "RESEARCH_PACKET",
        "repository_id": p["query"]["repository_id"],
        "claim_commit_sha": p["query"]["commit_sha"],
        "claim_id": f0["claim_id"] if f0 else None,
        "claim_type": f0["claim_type"] if f0 else None,
        "verification_status": f0["verdict_status"] if f0 else "insufficient_evidence",
        "verification_id": f0["verification_id"] if f0 else None,
        "verification_rule_version": "path-exists-verifier/v1",
        "freshness_state": "UNKNOWN",
        "current_applicability": "CURRENT_APPLICABILITY_UNKNOWN",
        "review_status": f0["review_status"] if f0 else "pending_review",
        "provenance_level": "SYNTHETIC_FIXTURE",
        "authorization_class": "TEST_ONLY_ISOLATED",
        "authorization_is_test_only": True,
        "evidence_refs": list(p["evidence_refs"])[:5],
        "fact_refs": list(p["fact_refs"])[:5],
        "source_snapshot_refs": list(p["source_snapshot_refs"])[:5],
        "limitations": list(p["limitations"]),
        "distribution_restrictions": p["distribution_restrictions"],
        "claim_payload": (f0["claim_payload"] if f0 else {}),
    }


def build_scenario(name, *, partial=False, truncate_index=None):
    tmp = Path(tempfile.mkdtemp(prefix=f"p4b_{name}_"))
    ks = rfx.fresh(tmp)
    try:
        rfx.vfx.run_full(ks, partial=partial)
        if truncate_index:
            ks.conn.execute("DELETE FROM index_rows WHERE asset_type=?",
                            (truncate_index,))
            ks.conn.commit()

        before = {"assets": VI.fingerprint_assets(ks),
                  "pointers": VI.fingerprint_pointers(ks),
                  "index": VI.fingerprint_index(ks),
                  "oplog": VI.fingerprint_operation_log(ks)}

        packets = {}
        for qname, q in (("q_path", rfx.q_path()),
                         ("q_claims", rfx.q_claims()),
                         ("q_version", rfx.q_version())):
            packets[qname] = RE.run_research(ks, q, include_diagnostics=True)

        after = {"assets": VI.fingerprint_assets(ks),
                 "pointers": VI.fingerprint_pointers(ks),
                 "index": VI.fingerprint_index(ks),
                 "oplog": VI.fingerprint_operation_log(ks)}
        read_only = all(before[k] == after[k] for k in before)
    finally:
        ks.close()
        shutil.rmtree(tmp, ignore_errors=True)

    d = OUT/name
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for qname, p in packets.items():
        (d/f"{qname}_packet.json").write_text(
            json.dumps(p, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
            encoding="utf-8")
        files[f"{qname}_json"] = str((d/f"{qname}_packet.json").relative_to(ROOT))

    # 用 q_path 的研究包交给现有 Renderer 做内部预览
    card = CM.build_card(_view_like(packets["q_path"]))
    (d/"research_card.html").write_text(
        CRD.render_card_html(card, assembled_at=""), encoding="utf-8")
    files["card_html"] = str((d/"research_card.html").relative_to(ROOT))
    (d/"research_card.json").write_text(CRD.render_json(card), encoding="utf-8")
    files["card_json"] = str((d/"research_card.json").relative_to(ROOT))

    pchk = PPC.pre_publish_check(
        {"html": CRD.render_card_html(card),
         "json": json.loads(CRD.render_json(card))},
        {"authorization_is_test_only": True,
         "provenance_level": "SYNTHETIC_FIXTURE",
         "no_usable_evidence": False, "conflict_indicators": {},
         "limitations": packets["q_path"]["limitations"]},
        packets["q_path"]["distribution_restrictions"])

    return {
        "name": name, "read_only": read_only,
        "packets": {k: {"research_id": v["research_id"],
                        "packet_status": v["packet_status"],
                        "coverage": v["coverage_assessment"]["coverage_state"],
                        "content_digest": v["content_digest"],
                        "finding_count": len(v["findings"]),
                        "untrusted_count": len(v["untrusted_findings"]),
                        "limitation_count": len(v["limitations"])}
                    for k, v in packets.items()},
        "pre_publish": {"preview_allowed": pchk["preview_allowed"],
                        "distribution_allowed": pchk["distribution_allowed"],
                        "publish_blocked": pchk["publish_blocked"]},
        "files": files,
    }


OUT.mkdir(parents=True, exist_ok=True)
STAMP = datetime.datetime.now(TZ).isoformat(timespec="seconds")
scen = {}
scen["s1_complete"] = build_scenario("s1_complete")
scen["s2_partial"] = build_scenario("s2_partial", partial=True)
scen["s3_no_snapshot_index"] = build_scenario(
    "s3_no_snapshot_index", truncate_index="repository_snapshot")

gold_eval = ROOT/"docs"/"implementation"/"F2_P4B_GOLD_EVALUATION.json"
gold = (json.loads(gold_eval.read_text(encoding="utf-8"))
        if gold_eval.exists() else {})

summary = {
    "artifact": "F2_P4B_E2E_REPLAY",
    "generated_at": STAMP,
    "data_provenance": "HISTORICAL_REAL_DATA + SYNTHETIC_FIXTURE",
    "live_github_refetch": False,
    "real_human_authorization": False,
    "llm_called": False,
    "authorization_kind_used": "TEST_ONLY",
    "output_dir": str(OUT.relative_to(ROOT)),
    "note": ("研究包与内部预览产物；不是知识权威；"
             "未联网、未调用 LLM、未使用真实人类授权"),
    "canonical": "SL-CAP-0035..0039",
    "scenarios": scen,
    "gold": {k: gold.get(k) for k in
             ("gold_count", "query_success_rate",
              "false_positive_count", "false_negative_count",
              "correct_abstention", "wrong_abstention", "blocked")},
    "deterministic": all(
        s["packets"][k]["research_id"] == s["packets"][k]["research_id"]
        for s in scen.values() for k in s["packets"]),
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n",
                   encoding="utf-8")

print("场景:", len(scen))
for k, s in scen.items():
    print(f"  {k}: read_only={s['read_only']} "
          f"packets={ {n: v['coverage'] for n, v in s['packets'].items()} }")
print("输出:", summary["output_dir"])
print("Gold:", summary["gold"])
