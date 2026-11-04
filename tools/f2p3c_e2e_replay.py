#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P3C 本地受控端到端回放。

数据级别：基线 HISTORICAL_REAL_DATA（P1C 记录）；目标 Commit 与内容是 SYNTHETIC_FIXTURE。
**本轮未联网，未使用真实授权。**
"""
import json, sys, tempfile, shutil, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("src/collector", "src/storage", "src/runtime", "src/facts",
          "src/evidence_claims", "src/lifecycle"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot
from knowledge_store import KnowledgeStore
import importlib
extractor = importlib.import_module("extractor")
FI = importlib.import_module("ingest")
import ec_models as EM, verifier as V, verification_store as VS
import lc_models as L, ref_observer as RO, freshness_evaluator as FE
import lifecycle_store as LS
import revalidation_models as R
import revalidation_queue as RQ
import revalidation_authorization as AUTH
import revalidation_executor as EX
import revalidation_run_store as RS
import collector_adapter as CA

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"implementation"/"F2_P3C_E2E_REPLAY.json"
rec = json.loads((ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json").read_text(encoding="utf-8"))
assert rec["result"] == "REAL_GITHUB_OK"

A = rec["commit_sha"]
B = "b" * 40
C = "c" * 40
NOW = "2026-11-05T00:00:00+08:00"

out = {"artifact": "F2_P3C_E2E_REPLAY",
       "data_provenance": "HISTORICAL_REAL_DATA + SYNTHETIC_FIXTURE",
       "live_github_refetch": False,
       "real_human_authorization": False,
       "authorization_kind_used": "TEST_ONLY",
       "note": ("基线来自 P1C 真实采集记录；目标 Commit B 与 tree 内容是 "
                "SYNTHETIC_FIXTURE。授权是 TEST_ONLY 隔离凭证，"
                "**不证明平台审批通过**"),
       "replayed_at": datetime.datetime.now(TZ).isoformat(timespec="seconds")}

def _plan(c, commit, *, path=None):
    params = c["target_claim_parameters"] if path is None else {
        "normalized_path": path,
        "expected_exists": c["target_claim_parameters"]["expected_exists"]}
    p = {"candidate_id": c["candidate_id"], "repository_id": rec["repository_id"],
         "requested_ref": rec["requested_ref"], "target_commit_sha": commit,
         "intended_collector_scope": "full_tree_enumeration",
         "intended_fact_rules": ["file_path_observation@v1"],
         "intended_ec_rule_version": "path-exists-verifier/v1",
         "target_claim_parameters": params,
         "required_operations": sorted(AUTH.ALLOWED_OPERATIONS)}
    p["plan_digest"] = AUTH.plan_digest_of(p)
    return p

def _auth(c, plan, commit):
    return AUTH.make_test_authorization(
        candidate_id=c["candidate_id"], repository_id=rec["repository_id"],
        requested_ref=rec["requested_ref"], target_commit_sha=commit,
        plan_digest=plan["plan_digest"],
        authorized_scope="full_tree_enumeration",
        issued_at="2026-11-04T00:00:00+08:00",
        expires_at="2027-01-01T00:00:00+08:00")

tmp = Path(tempfile.mkdtemp(prefix="p3c_e2e_"))
try:
    with KnowledgeStore(str(tmp/"kb.db")) as ks:
        # 1) A 上的源 Claim（用 P1C 真实快照）
        ents = [{"path": "README", "type": "blob", "sha": rec["blob"]["blob_sha"],
                 "size": rec["blob"]["size"], "mode": "100644",
                 "mode_kind": "file", "depth": 0}]
        snap = build_snapshot(
            repository_id=rec["repository_id"],
            requested_repository=rec["target"],
            resolved_repository=rec["resolved_repository"],
            requested_ref=rec["requested_ref"], commit_sha=A,
            root_tree_sha=rec["root_tree_sha"],
            tree_query_ref=rec["tree_query_ref"], completeness_status="COMPLETE",
            tree_entries=ents, collected_at=rec["attempted_at"],
            evidence_refs=[f"github:repos/{rec['target']}@{A}"])
        r1 = ingest_snapshot(ks, snap); aid = r1["asset_id"]
        f = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="README")
        FI.ingest_fact(ks, f)
        claim_a = EM.build_path_claim(repository_id=rec["repository_id"],
                                      commit_sha=A, target_path="README",
                                      expected_exists=True,
                                      claim_origin="human_specified")
        v_a = V.verify_path_claim(ks, claim_a, [f.fact_id])
        VS.ingest_claim(ks, claim_a)
        VS.ingest_verification(ks, v_a, repository_id=rec["repository_id"])
        out["source"] = {"commit": A, "claim_id": claim_a.claim_id,
                         "verification_id": v_a.verification_id,
                         "status": v_a.status}

        # 2) watch + 观测 B（来源用真实记录入口，commit 换成合成 B）
        watch = L.build_watch(repository_id=rec["repository_id"],
                              requested_ref=rec["requested_ref"],
                              ref_kind=L.REF_KIND_BRANCH,
                              retrieval_scope="full_tree_enumeration",
                              baseline_commit_sha=A, claim_id=claim_a.claim_id)
        LS.ingest_watch(ks, watch)
        synth_rec = dict(rec); synth_rec["commit_sha"] = B
        obs_b = RO.observe_ref_from_record(
            record=synth_rec, repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"])
        a_b = FE.assess(watch=watch, observation=obs_b,
                        source_evidence_conflict=L.CONFLICT_NONE)
        LS.ingest_assessment(ks, a_b)
        prop = RQ.propose_candidate(ks, assessment_id=a_b.assessment_id)
        out["candidate"] = {"state": prop.get("state"),
                            "candidate_id": prop.get("candidate_id"),
                            "status": prop.get("candidate_status"),
                            "source_level": prop.get("source_level")}

        if not prop.get("ok"):
            out["candidate"]["note"] = "候选未能生成（源等级不可调度）"
        else:
            c = RQ.read_candidate(ks, candidate_id=prop["candidate_id"],
                                  repository_id=rec["repository_id"])["payload"]
            plan = _plan(c, B)
            auth = _auth(c, plan, B)
            out["plan"] = {"gate": "PLAN_READY", "plan_digest": plan["plan_digest"],
                           "intended_scope": plan["intended_collector_scope"]}
            out["authorization"] = {k: auth[k] for k in
                                    ("authorization_id", "authorization_kind",
                                     "test_only", "expires_at")}

            # 3) 执行：B 上 README 不存在 → refuted
            adapter = CA.FakeGhAdapter({B: "1" * 40},
                {"1" * 40: {"entries": [
                    {"path": "docs", "type": "tree", "sha": "d" * 40,
                     "mode": "040000"}], "truncated": False}})
            res = EX.execute_revalidation(
                ks, candidate_id=c["candidate_id"],
                repository_id=rec["repository_id"], authorization=auth,
                plan=plan, adapter=adapter, now=NOW)
            out["execution_absent"] = {
                "execution_status": res.execution_status,
                "verification_status": res.verification_status,
                "error": res.error_code,
                "source_snapshot": res.payload.get("source_snapshot_ref"),
                "collector_calls": [list(x) for x in adapter.calls]}

            # 4) 变体：B 上 README 存在 → supported
            s2 = FX = None
            st2 = LS.ingest_watch  # noop
            # 重建一个独立 store 才能有第二个候选（同 watch 单活动）
        # 独立 store 跑三个变体
        variants = {}
        for label, entries, truncated, expect in [
            ("b_present", [{"path": "README", "type": "blob", "sha": "9"*40,
                            "size": 13, "mode": "100644"}], False, "supported"),
            ("b_partial", [{"path": "docs", "type": "tree", "sha": "d"*40,
                            "mode": "040000"}], True, "insufficient_evidence"),
        ]:
            vtmp = Path(tempfile.mkdtemp(prefix=f"p3c_var_{label}_"))
            try:
                with KnowledgeStore(str(vtmp/"kb.db")) as vks:
                    r1v = ingest_snapshot(vks, snap); aidv = r1v["asset_id"]
                    fv = extractor.extract_file_path_observation(
                        vks, snapshot_asset_id=aidv, target_path="README")
                    FI.ingest_fact(vks, fv)
                    ca = EM.build_path_claim(repository_id=rec["repository_id"],
                                             commit_sha=A, target_path="README",
                                             expected_exists=True)
                    va = V.verify_path_claim(vks, ca, [fv.fact_id])
                    VS.ingest_claim(vks, ca)
                    VS.ingest_verification(vks, va, repository_id=rec["repository_id"])
                    wv = L.build_watch(repository_id=rec["repository_id"],
                                       requested_ref=rec["requested_ref"],
                                       ref_kind=L.REF_KIND_BRANCH,
                                       retrieval_scope="full_tree_enumeration",
                                       baseline_commit_sha=A,
                                       claim_id=ca.claim_id)
                    LS.ingest_watch(vks, wv)
                    ob = RO.observe_ref_from_record(
                        record=synth_rec, repository_id=rec["repository_id"],
                        requested_ref=rec["requested_ref"])
                    ab = FE.assess(watch=wv, observation=ob,
                                   source_evidence_conflict=L.CONFLICT_NONE)
                    LS.ingest_assessment(vks, ab)
                    pr = RQ.propose_candidate(vks, assessment_id=ab.assessment_id)
                    if not pr.get("ok"):
                        variants[label] = {"error": pr.get("reason_code")}
                        continue
                    cv = RQ.read_candidate(vks, candidate_id=pr["candidate_id"],
                                           repository_id=rec["repository_id"])["payload"]
                    pv = _plan(cv, B)
                    av = _auth(cv, pv, B)
                    ad = CA.FakeGhAdapter({B: "1"*40},
                        {"1"*40: {"entries": entries, "truncated": truncated}})
                    rv = EX.execute_revalidation(
                        vks, candidate_id=cv["candidate_id"],
                        repository_id=rec["repository_id"],
                        authorization=av, plan=pv, adapter=ad, now=NOW)
                    variants[label] = {
                        "execution_status": rv.execution_status,
                        "verification_status": rv.verification_status,
                        "expected": expect,
                        "match": rv.verification_status == expect}
            finally:
                shutil.rmtree(vtmp, ignore_errors=True)
        out["variants"] = variants
finally:
    shutil.rmtree(tmp, ignore_errors=True)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("source   :", out["source"]["status"], out["source"]["commit"][:12])
print("candidate:", out["candidate"].get("status"), out["candidate"].get("source_level"))
print("exec     :", out["execution_absent"]["execution_status"],
      "/", out["execution_absent"]["verification_status"])
print("calls    :", out["execution_absent"]["collector_calls"])
for k, v in out["variants"].items():
    print(f"variant {k}: {v}")
print("live API :", out["live_github_refetch"], "| real human auth:",
      out["real_human_authorization"])
