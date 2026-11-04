#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P3B 端到端回放：评估 → 候选 → 队列 → Dry-Run 计划。

数据级别：HISTORICAL_REAL_DATA（P1C 真实采集记录）作为基线来源；
"新 Commit"是 SYNTHETIC_FIXTURE。**本轮未重新联网**。
"""
import json, sys, tempfile, shutil, datetime, importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("src/collector", "src/storage", "src/runtime", "src/facts",
          "src/evidence_claims", "src/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot
from knowledge_store import KnowledgeStore
extractor = importlib.import_module("extractor")
FI = importlib.import_module("ingest")
import ec_models as EM, verifier as V, verification_store as VS
import lc_models as L, ref_observer as RO, freshness_evaluator as FE
import lifecycle_store as LS
import revalidation_models as R
import revalidation_queue as RQ
import revalidation_dispatch_gate as DG

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"implementation"/"F2_P3B_E2E_REPLAY.json"
rec = json.loads((ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json").read_text(encoding="utf-8"))
assert rec["result"] == "REAL_GITHUB_OK"

BASE = rec["commit_sha"]
SYNTH_B = "b" * 40
SYNTH_C = "c" * 40

ents = [{"path": "README", "type": "blob", "sha": rec["blob"]["blob_sha"],
         "size": rec["blob"]["size"], "mode": "100644", "mode_kind": "file",
         "depth": 0}]
snap = build_snapshot(
    repository_id=rec["repository_id"], requested_repository=rec["target"],
    resolved_repository=rec["resolved_repository"], requested_ref=rec["requested_ref"],
    commit_sha=rec["commit_sha"], root_tree_sha=rec["root_tree_sha"],
    tree_query_ref=rec["tree_query_ref"], completeness_status="COMPLETE",
    tree_entries=ents, collected_at=rec["attempted_at"],
    evidence_refs=[f"github:repos/{rec['target']}@{rec['commit_sha']}"])

out = {"artifact": "F2_P3B_E2E_REPLAY",
       "data_provenance": "HISTORICAL_REAL_DATA",
       "live_github_refetch": False,
       "note": ("本轮**未重新访问 GitHub**。基线来自 P1C 真实采集记录；"
                "新 Commit 是 SYNTHETIC_FIXTURE，**不是实时 Ref 更新**"),
       "replayed_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
       "baseline_commit_sha": BASE}

tmp = Path(tempfile.mkdtemp(prefix="p3b_e2e_"))
try:
    with KnowledgeStore(str(tmp/"kb.db")) as ks:
        r1 = ingest_snapshot(ks, snap); aid = r1["asset_id"]
        f = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="README")
        FI.ingest_fact(ks, f)
        claim = EM.build_path_claim(repository_id=rec["repository_id"],
                                    commit_sha=BASE, target_path="README",
                                    expected_exists=True,
                                    claim_origin="human_specified")
        verif = V.verify_path_claim(ks, claim, [f.fact_id])
        VS.ingest_claim(ks, claim)
        VS.ingest_verification(ks, verif, repository_id=rec["repository_id"])

        watch = L.build_watch(repository_id=rec["repository_id"],
                              requested_ref=rec["requested_ref"],
                              ref_kind=L.REF_KIND_BRANCH,
                              retrieval_scope="full_tree_enumeration",
                              baseline_commit_sha=BASE, claim_id=claim.claim_id)
        LS.ingest_watch(ks, watch)

        # 基线观测：历史真实记录 → VERSION_ALIGNED（不产生候选）
        obs_base = RO.observe_ref_from_record(
            record=rec, repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"])
        a_base = FE.assess(watch=watch, observation=obs_base,
                           source_evidence_conflict=L.CONFLICT_NONE)
        LS.ingest_assessment(ks, a_base)
        r_base = RQ.propose_candidate(ks, assessment_id=a_base.assessment_id)
        out["baseline"] = {"state": a_base.freshness_state,
                           "candidate": r_base.get("reason_code")
                           or r_base.get("state")}

        # 合成新 Commit B → POSSIBLY_STALE，但来源 SYNTHETIC → BLOCKED
        obs_b = RO.observe_ref_from_snapshot(
            snapshot_asset={"asset_id": "synth-b", "payload": {
                "repository_id": rec["repository_id"], "commit_sha": SYNTH_B,
                "requested_ref": rec["requested_ref"],
                "retrieval_scope": "full_tree_enumeration",
                "collector_version": "sourcelore-collector/1.0.0"}},
            repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"],
            provenance_level=RO.PROV_SYNTHETIC)
        a_b = FE.assess(watch=watch, observation=obs_b,
                        source_evidence_conflict=L.CONFLICT_NONE)
        LS.ingest_assessment(ks, a_b)
        r_b = RQ.propose_candidate(ks, assessment_id=a_b.assessment_id)
        out["synthetic_new_commit"] = {
            "freshness": a_b.freshness_state,
            "provenance": obs_b.provenance_level,
            "candidate_state": r_b.get("state"),
            "candidate_status": r_b.get("candidate_status"),
            "state_reason": r_b.get("state_reason"),
            "candidate_id": r_b.get("candidate_id")}
        plan_b = DG.prepare_revalidation_plan(
            ks, candidate_id=r_b["candidate_id"],
            repository_id=rec["repository_id"]) if r_b.get("ok") else {}
        out["synthetic_new_commit"]["plan_gate"] = plan_b.get("gate")

        # 真实来源（live API 替身）→ 可以 PROPOSED 并产出 PLAN_READY
        class _LiveClient:
            def commit_for_ref(self, o, n, ref):
                class Rr:
                    ok = True; error = None
                    data = {"sha": SYNTH_C, "commit": {"tree": {"sha": "1"*40}}}
                return Rr()
        obs_c = RO.observe_ref_via_collector(
            _LiveClient(), owner=rec["target"].split("/")[0],
            name=rec["target"].split("/")[1],
            repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"])
        a_c = FE.assess(watch=watch, observation=obs_c,
                        source_evidence_conflict=L.CONFLICT_NONE)
        LS.ingest_assessment(ks, a_c)
        r_c = RQ.propose_candidate(ks, assessment_id=a_c.assessment_id)
        out["real_source_new_commit"] = {
            "freshness": a_c.freshness_state,
            "provenance": obs_c.provenance_level,
            "candidate_state": r_c.get("state"),
            "candidate_status": r_c.get("candidate_status"),
            "superseded": r_c.get("superseded_candidate_id"),
            "candidate_id": r_c.get("candidate_id")}
        plan_c = DG.prepare_revalidation_plan(
            ks, candidate_id=r_c["candidate_id"],
            repository_id=rec["repository_id"]) if r_c.get("ok") else {}
        out["real_source_new_commit"]["plan_gate"] = plan_c.get("gate")
        if plan_c.get("ok"):
            out["plan"] = {
                "gate": plan_c["plan"]["gate"],
                "events": plan_c["plan"]["events_distinguished"],
                "side_effects": plan_c["plan"]["side_effects"],
                "target_claim_identity":
                    plan_c["plan"]["target_claim_parameters"]
                    .get("expected_target_claim_identity"),
            }

        q = RQ.read_queue(ks, watch_id=watch.watch_id,
                          repository_id=rec["repository_id"])
        out["queue"] = {"active": q["active_candidate_id"],
                        "history_count": len(q["history_candidate_ids"]),
                        "history": q["history_candidate_ids"]}
        cnt = RQ.count_active(ks, repository_id=rec["repository_id"])
        out["active_count"] = cnt
        out["counts"] = {t: ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type=?",
            (t,)).fetchone()["n"]
            for t in ("repository_snapshot", "extracted_fact", "claim_candidate",
                      "claim_verification", "lifecycle_watch",
                      "freshness_assessment", "revalidation_queue",
                      "revalidation_candidate")}
finally:
    shutil.rmtree(tmp, ignore_errors=True)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("baseline      :", out["baseline"])
print("synthetic B   :", out["synthetic_new_commit"]["candidate_status"],
      "/", out["synthetic_new_commit"]["plan_gate"])
print("real C        :", out["real_source_new_commit"]["candidate_status"],
      "/", out["real_source_new_commit"]["plan_gate"])
print("plan gate     :", out.get("plan", {}).get("gate"))
print("side effects  :", out.get("plan", {}).get("side_effects"))
print("active count  :", out["active_count"]["total_active"],
      "multi:", out["active_count"]["multi_active_watches"])
print("counts        :", json.dumps(out["counts"], ensure_ascii=False))
