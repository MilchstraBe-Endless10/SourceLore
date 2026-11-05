#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P3D 只读视图端到端回放。

数据级别：基线 HISTORICAL_REAL_DATA（P1C 记录）；目标 Commit 与内容 SYNTHETIC_FIXTURE。
**本轮未联网，未使用真实授权。**
"""
import json, sys, tempfile, shutil, datetime, importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("src/collector", "src/storage", "src/runtime", "src/facts",
          "src/evidence_claims", "src/lifecycle", "src/views"):
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
import revalidation_queue as RQ, revalidation_authorization as AUTH
import revalidation_executor as EX, collector_adapter as CA
import knowledge_view_assembler as KVA, view_integrity as VI
import view_models as VM

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"implementation"/"F2_P3D_E2E_REPLAY.json"
rec = json.loads((ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json").read_text(encoding="utf-8"))
assert rec["result"] == "REAL_GITHUB_OK"

A = rec["commit_sha"]
B = "b" * 40
TREE = "1" * 40
NOW = "2026-11-05T00:00:00+08:00"

out = {"artifact": "F2_P3D_E2E_REPLAY",
       "data_provenance": "HISTORICAL_REAL_DATA + SYNTHETIC_FIXTURE",
       "live_github_refetch": False,
       "real_human_authorization": False,
       "authorization_kind_used": "TEST_ONLY",
       "note": ("视图只读取已提交资产；基线来自 P1C 真实记录，"
                "目标 Commit 与 tree 是 SYNTHETIC_FIXTURE；"
                "授权是 TEST_ONLY 隔离凭证，不证明平台审批通过"),
       "replayed_at": datetime.datetime.now(TZ).isoformat(timespec="seconds")}

def _plan(c, commit):
    p = {"candidate_id": c["candidate_id"], "repository_id": rec["repository_id"],
         "requested_ref": rec["requested_ref"], "target_commit_sha": commit,
         "intended_collector_scope": "full_tree_enumeration",
         "intended_fact_rules": ["file_path_observation@v1"],
         "intended_ec_rule_version": "path-exists-verifier/v1",
         "target_claim_parameters": c["target_claim_parameters"],
         "required_operations": sorted(AUTH.ALLOWED_OPERATIONS)}
    p["plan_digest"] = AUTH.plan_digest_of(p)
    return p

def _summ(v):
    if not v.get("ok"):
        return {"ok": False, "error_code": v.get("error_code"),
                "detail": v.get("detail")}
    w = v["view"]
    return {"ok": True, "view_id": w["view_id"],
            "claim_commit_sha": w["claim_commit_sha"],
            "verification_status": w["verification_status"],
            "current_applicability": w["current_applicability"],
            "local_coverage_only": w["local_coverage_only"],
            "distribution_allowed":
                w["distribution_restrictions"]["distribution_allowed"]}


tmp = Path(tempfile.mkdtemp(prefix="p3d_e2e_"))
try:
    with KnowledgeStore(str(tmp/"kb.db")) as ks:
        ents = [{"path": "README", "type": "blob", "sha": rec["blob"]["blob_sha"],
                 "size": rec["blob"]["size"], "mode": "100644",
                 "mode_kind": "file", "depth": 0}]
        snap = build_snapshot(
            repository_id=rec["repository_id"], requested_repository=rec["target"],
            resolved_repository=rec["resolved_repository"],
            requested_ref=rec["requested_ref"], commit_sha=A,
            root_tree_sha=rec["root_tree_sha"], tree_query_ref=rec["tree_query_ref"],
            completeness_status="COMPLETE", tree_entries=ents,
            collected_at=rec["attempted_at"],
            evidence_refs=[f"github:repos/{rec['target']}@{A}"])
        r1 = ingest_snapshot(ks, snap); aid = r1["asset_id"]
        f = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="README")
        FI.ingest_fact(ks, f)
        claim_a = EM.build_path_claim(repository_id=rec["repository_id"],
                                      commit_sha=A, target_path="README",
                                      expected_exists=True, claim_origin="human")
        v_a = V.verify_path_claim(ks, claim_a, [f.fact_id])
        VS.ingest_claim(ks, claim_a)
        VS.ingest_verification(ks, v_a, repository_id=rec["repository_id"])
        out["source"] = {"commit": A, "claim_id": claim_a.claim_id,
                         "verification_id": v_a.verification_id,
                         "status": v_a.status}

        watch = L.build_watch(repository_id=rec["repository_id"],
                              requested_ref=rec["requested_ref"],
                              ref_kind=L.REF_KIND_BRANCH,
                              retrieval_scope="full_tree_enumeration",
                              baseline_commit_sha=A, claim_id=claim_a.claim_id)
        LS.ingest_watch(ks, watch)
        synth = dict(rec); synth["commit_sha"] = B
        obs = RO.observe_ref_from_record(record=synth,
                                         repository_id=rec["repository_id"],
                                         requested_ref=rec["requested_ref"])
        a_b = FE.assess(watch=watch, observation=obs,
                        source_evidence_conflict=L.CONFLICT_NONE)
        LS.ingest_assessment(ks, a_b)
        prop = RQ.propose_candidate(ks, assessment_id=a_b.assessment_id)
        out["candidate"] = {"status": prop.get("candidate_status"),
                            "source_level": prop.get("source_level")}

        c = RQ.read_candidate(ks, candidate_id=prop["candidate_id"],
                              repository_id=rec["repository_id"])["payload"]
        plan = _plan(c, B)
        auth = AUTH.make_test_authorization(
            candidate_id=c["candidate_id"], repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"], target_commit_sha=B,
            plan_digest=plan["plan_digest"],
            authorized_scope="full_tree_enumeration",
            issued_at="2026-11-04T00:00:00+08:00",
            expires_at="2027-01-01T00:00:00+08:00")
        ad = CA.FakeGhAdapter({B: TREE},
            {TREE: {"entries": [{"path": "docs", "type": "tree",
                                 "sha": "d" * 40, "mode": "040000"}],
                    "truncated": False}})
        res = EX.execute_revalidation(
            ks, candidate_id=c["candidate_id"],
            repository_id=rec["repository_id"], authorization=auth,
            plan=plan, adapter=ad, now=NOW)
        out["execution"] = {"execution_status": res.execution_status,
                            "verification_status": res.verification_status,
                            "collector_calls": [list(x) for x in ad.calls]}

        # ── 只读装配（前后指纹对比）─────────────────────
        before = VI.fingerprint_assets(ks)
        ptr_b = VI.fingerprint_pointers(ks)
        idx_b = VI.fingerprint_index(ks)
        log_b = VI.fingerprint_operation_log(ks)

        v_a_view = KVA.assemble_from_verification(
            ks, verification_id=v_a.verification_id,
            repository_id=rec["repository_id"])
        v_b_view = KVA.assemble_from_verification(
            ks, verification_id=res.payload["target_verification_id"],
            repository_id=rec["repository_id"])
        v_b_view2 = KVA.assemble_from_verification(
            ks, verification_id=res.payload["target_verification_id"],
            repository_id=rec["repository_id"])

        after = VI.fingerprint_assets(ks)
        out["read_only"] = {
            "assets_unchanged": before == after,
            "asset_count": len(before),
            "pointers_unchanged": ptr_b == VI.fingerprint_pointers(ks),
            "index_unchanged": idx_b == VI.fingerprint_index(ks),
            "operation_log_unchanged": log_b == VI.fingerprint_operation_log(ks),
            "collector_calls_during_assembly": 0,
        }
        out["views"] = {
            "a": _summ(v_a_view), "b": _summ(v_b_view),
        }
        out["determinism"] = {
            "same_input_same_id": v_b_view.get("view_id") ==
                                  v_b_view2.get("view_id"),
            "a_b_distinct": v_a_view.get("view_id") != v_b_view.get("view_id"),
        }
        out["five_axes"] = {
            "verification_status": v_b_view["view"]["verification_status"],
            "freshness_state": v_b_view["view"]["freshness_state"],
            "review_status": v_b_view["view"]["review_status"],
            "execution_status": v_b_view["view"]["execution_status"],
            "provenance_level": v_b_view["view"]["provenance_level"],
            "authorization_class": v_b_view["view"]["authorization_class"],
        }
finally:
    shutil.rmtree(tmp, ignore_errors=True)


OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("source   :", out["source"]["status"], out["source"]["commit"][:12])
print("exec     :", out["execution"]["execution_status"], "/",
      out["execution"]["verification_status"])
print("readonly :", out["read_only"])
print("five axes:", out["five_axes"])
print("determinism:", out["determinism"])
