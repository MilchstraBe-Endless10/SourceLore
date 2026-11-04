#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lifecycle 测试夹具。

提供：确定性本地 Ref 观测、真实 Storage 入库、真实 EC Claim/Verification 构造。
"""
import sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"src"/"lifecycle"), str(ROOT/"src"/"storage"),
          str(ROOT/"src"/"facts"), str(ROOT/"src"/"collector"),
          str(ROOT/"src"/"runtime"), str(ROOT/"src"/"evidence_claims"),
          str(ROOT/"tests"/"evidence_claims")):
    if p not in sys.path: sys.path.insert(0, p)

from knowledge_store import KnowledgeStore
import lc_models as L
import ref_observer as RO

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
COMMIT_C = "c" * 40
REPO = "1296269"
REPO_FORK = "999888"
SCOPE = "full_tree_enumeration"


def fresh(tmp):
    return KnowledgeStore(str(Path(tmp) / "kb.db"))


class FakeClient:
    """确定性本地 Collector 替身：只实现 commit_for_ref。

    ★ 这是 SYNTHETIC_FIXTURE 级别，测试里必须如实标注，不得冒充真实观测。
    """
    def __init__(self, mapping, *, ok=True, error_code=None):
        self.mapping = dict(mapping)
        self._ok = ok
        self._error_code = error_code
        self.calls = []

    def commit_for_ref(self, owner, name, ref):
        self.calls.append((owner, name, ref))
        if not self._ok:
            class E:
                def __init__(self, c): self.error_code = c
            class R:
                def __init__(self, c):
                    self.ok = False; self.data = None; self.error = E(c)
            return R(self._error_code or "NETWORK_TIMEOUT")
        class R2:
            def __init__(self, sha):
                self.ok = True; self.data = {"sha": sha}; self.error = None
        sha = self.mapping.get(ref)
        if sha is None:
            class E2:
                error_code = "REPO_NOT_FOUND"
            class R3:
                ok = False; data = None
                error = E2()
            return R3()
        return R2(sha)


def observe_ok(*, repo=REPO, ref="master", commit=COMMIT_A, at="",
               provenance=RO.PROV_SYNTHETIC):
    return RO.observe_ref_from_snapshot(
        snapshot_asset={"asset_id": "snap-" + commit[:8], "payload": {
            "repository_id": repo, "commit_sha": commit, "requested_ref": ref,
            "retrieval_scope": SCOPE,
            "collector_version": "sourcelore-collector/1.0.0"}},
        repository_id=repo, requested_ref=ref, observed_at=at,
        provenance_level=provenance)


def observe_via_client(client, *, repo=REPO, ref="master", at=""):
    return RO.observe_ref_via_collector(
        client, owner="octocat", name="Hello-World",
        repository_id=repo, requested_ref=ref, observed_at=at)


def make_watch(*, repo=REPO, ref="master", baseline=COMMIT_A,
               claim_id=None, scope=SCOPE):
    return L.build_watch(
        repository_id=repo, requested_ref=ref, ref_kind=L.REF_KIND_BRANCH,
        retrieval_scope=scope, baseline_commit_sha=baseline,
        claim_id=claim_id or ("SL-CLAIM-" + "1" * 40))


def make_pinned_watch():
    """★ PINNED_COMMIT 的 watch 构造非法 —— 固定版本不该有跟踪关系。

    这个夹具用于验证"不能给 PINNED_COMMIT 建 watch"。
    """
    return dict(repository_id=REPO, requested_ref="master",
                ref_kind=L.REF_KIND_BRANCH, retrieval_scope=SCOPE,
                baseline_commit_sha=COMMIT_A,
                claim_id="SL-CLAIM-" + "1" * 40,
                applicability_scope=L.PINNED_COMMIT)


# ── P3B：真实 EC 对象 + 可生成候选的完整栈 ──────────────────
import importlib.util as _ilu
_s = _ilu.spec_from_file_location(
    "ec_fx_for_lc", str(ROOT / "tests" / "evidence_claims" / "fixtures.py"))
EF = _ilu.module_from_spec(_s); _s.loader.exec_module(EF)


import ec_models as EM
import verifier as ECV
import verification_store as VS


def make_full_stack(ks, *, repo=REPO, commit=COMMIT_A, ref="master",
                    target=None, provenance_real=True, conflict=None,
                    path="README", expected_exists=True):
    """建出 EC Claim/Verification + watch + assessment 的完整栈。

    返回 dict，含所有 id，供 P3B 测试直接使用。
    """
    import freshness_evaluator as FE
    import ref_observer as RO
    import lifecycle_store as LS

    snap = EF.make_snapshot(ks, repo=repo, commit=commit)
    fact = EF.make_fact(ks, snap["asset_id"], path)
    claim = EM.build_path_claim(repository_id=repo, commit_sha=commit,
                                target_path=path, expected_exists=expected_exists,
                                claim_origin="human_specified")
    verif = ECV.verify_path_claim(ks, claim, [fact["fact_id"]])
    VS.ingest_claim(ks, claim)
    VS.ingest_verification(ks, verif, repository_id=repo)

    watch = L.build_watch(repository_id=repo, requested_ref=ref,
                          ref_kind=L.REF_KIND_BRANCH, retrieval_scope=SCOPE,
                          baseline_commit_sha=commit,
                          claim_id=claim.claim_id)
    LS.ingest_watch(ks, watch)

    tgt = target or COMMIT_B
    if provenance_real:
        class _C:
            def commit_for_ref(self, o, n, r):
                class R:
                    ok = True
                    error = None
                    data = {"sha": tgt, "commit": {"tree": {"sha": "1" * 40}}}
                return R()
        obs = RO.observe_ref_via_collector(
            _C(), owner="octocat", name="Hello-World",
            repository_id=repo, requested_ref=ref)
    else:
        obs = RO.observe_ref_from_snapshot(
            snapshot_asset={"asset_id": "synth", "payload": {
                "repository_id": repo, "commit_sha": tgt, "requested_ref": ref,
                "retrieval_scope": SCOPE,
                "collector_version": "sourcelore-collector/1.0.0"}},
            repository_id=repo, requested_ref=ref,
            provenance_level=RO.PROV_SYNTHETIC)

    assess = FE.assess(watch=watch, observation=obs,
                       source_evidence_conflict=(conflict if conflict is not None
                                                 else L.CONFLICT_NONE))
    LS.ingest_assessment(ks, assess)

    return {"snapshot": snap, "fact": fact, "claim": claim, "verification": verif,
            "watch": watch, "observation": obs, "assessment": assess,
            "claim_id": claim.claim_id, "verification_id": verif.verification_id,
            "watch_id": watch.watch_id, "assessment_id": assess.assessment_id,
            "snapshot_asset_id": snap["asset_id"], "fact_id": fact["fact_id"]}


def make_pinned_stack(ks, *, repo=REPO, commit=COMMIT_A):
    """只建 EC 对象 + 固定版本语义（不建 watch）。"""
    snap = EF.make_snapshot(ks, repo=repo, commit=commit)
    fact = EF.make_fact(ks, snap["asset_id"], "README")
    claim = EM.build_path_claim(repository_id=repo, commit_sha=commit,
                                target_path="README", expected_exists=True)
    verif = ECV.verify_path_claim(ks, claim, [fact["fact_id"]])
    VS.ingest_claim(ks, claim)
    VS.ingest_verification(ks, verif, repository_id=repo)
    return {"claim": claim, "verification": verif, "snapshot": snap}
