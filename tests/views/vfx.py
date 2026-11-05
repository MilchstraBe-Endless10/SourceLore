#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视图测试共用夹具：真实 SQLite + 真实执行器产生的结果资产。"""
import sys, tempfile, pathlib, importlib.util as iu, importlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("src/lifecycle", "src/storage", "src/collector", "src/facts",
          "src/evidence_claims", "src/runtime", "src/views",
          "tests/evidence_claims"):
    if (ROOT/p).exists() and str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

import knowledge_store as KS
import ec_models as EM, verifier as V, verification_store as VS
import lifecycle_store as LS, freshness_evaluator as FE, ref_observer as RO
import lc_models as L
import revalidation_queue as RQ, revalidation_authorization as AUTH
import revalidation_executor as EX, collector_adapter as CA

_s = iu.spec_from_file_location("ecfx", str(ROOT/"tests"/"evidence_claims"/"fixtures.py"))
EFX = iu.module_from_spec(_s); _s.loader.exec_module(EFX)

A = "a" * 40
B = "b" * 40
C = "c" * 40
REPO = "1296269"
TREE_B = "1" * 40


def fresh(tmpdir):
    return KS.KnowledgeStore(str(pathlib.Path(tmpdir) / "kb.db"))


def make_source(ks, *, commit=A, path="README", exists=True, partial=False,
                provenance_real=True):
    """A 上的源 Claim + Verification。"""
    snap = EFX.make_snapshot(
        ks, commit=commit,
        completeness="PARTIAL" if partial else "COMPLETE",
        truncated=bool(partial))
    fact = EFX.make_fact(ks, snap["asset_id"], path)
    claim = EM.build_path_claim(repository_id=REPO, commit_sha=commit,
                                target_path=path, expected_exists=exists)
    verif = V.verify_path_claim(ks, claim, [fact["fact_id"]])
    VS.ingest_claim(ks, claim)
    VS.ingest_verification(ks, verif, repository_id=REPO)
    return {"snapshot_asset_id": snap["asset_id"], "fact_id": fact["fact_id"],
            "claim_id": claim.claim_id, "verification_id": verif.verification_id,
            "status": verif.status}


def make_candidate(ks, *, baseline=A, target=B, claim_id, provenance_real=True):
    watch = L.build_watch(repository_id=REPO, requested_ref="master",
                          ref_kind=L.REF_KIND_BRANCH,
                          retrieval_scope="full_tree_enumeration",
                          baseline_commit_sha=baseline, claim_id=claim_id)
    LS.ingest_watch(ks, watch)
    fake = type("C", (), {"commit_for_ref": lambda s, o, n, r: type("R", (), {
        "ok": True, "data": {"sha": target,
                             "commit": {"tree": {"sha": "1" * 40}}},
        "error": None})()})()
    obs = RO.observe_ref_via_collector(
        fake, owner="oc", name="hw", repository_id=REPO, requested_ref="master")
    a = FE.assess(watch=watch, observation=obs,
                  source_evidence_conflict=L.CONFLICT_NONE)
    LS.ingest_assessment(ks, a)
    r = RQ.propose_candidate(ks, assessment_id=a.assessment_id)
    return r, watch, a


def plan_for(cand, *, commit=B, path=None, exists=None):
    params = cand["target_claim_parameters"]
    p = {"candidate_id": cand["candidate_id"], "repository_id": REPO,
         "requested_ref": "master", "target_commit_sha": commit,
         "intended_collector_scope": "full_tree_enumeration",
         "intended_fact_rules": ["file_path_observation@v1"],
         "intended_ec_rule_version": "path-exists-verifier/v1",
         "target_claim_parameters": {
             "normalized_path": path or params["normalized_path"],
             "expected_exists": (params["expected_exists"]
                                 if exists is None else exists)},
         "required_operations": sorted(AUTH.ALLOWED_OPERATIONS)}
    p["plan_digest"] = AUTH.plan_digest_of(p)
    return p


def test_auth(cand, plan, *, commit=B, expires="2027-01-01T00:00:00+08:00"):
    return AUTH.make_test_authorization(
        candidate_id=cand["candidate_id"], repository_id=REPO,
        requested_ref="master", target_commit_sha=commit,
        plan_digest=plan["plan_digest"],
        authorized_scope="full_tree_enumeration",
        issued_at="2026-11-04T00:00:00+08:00", expires_at=expires)


def adapter(*, entries=None, truncated=False, **kw):
    return CA.FakeGhAdapter(
        {B: TREE_B},
        {TREE_B: {"entries": entries if entries is not None else [
            {"path": "docs", "type": "tree", "sha": "d" * 40,
             "mode": "040000"}], "truncated": truncated}}, **kw)


def run_full(ks, *, path="README", exists=True, partial=False,
             entries=None, truncated=False, commit=B, adapter_kw=None):
    """一条完整的 A→B 链路，返回 (source, cand, result, adapter)。"""
    src = make_source(ks, path=path, exists=exists, partial=partial)
    r, watch, assessment = make_candidate(ks, claim_id=src["claim_id"])
    cand = RQ.read_candidate(ks, candidate_id=r["candidate_id"],
                             repository_id=REPO)["payload"]
    plan = plan_for(cand, commit=commit)
    auth = test_auth(cand, plan, commit=commit)
    ad = adapter(entries=entries, truncated=truncated, **(adapter_kw or {}))
    res = EX.execute_revalidation(
        ks, candidate_id=cand["candidate_id"], repository_id=REPO,
        authorization=auth, plan=plan, adapter=ad,
        now="2026-11-05T00:00:00+08:00")
    return src, cand, res, ad
