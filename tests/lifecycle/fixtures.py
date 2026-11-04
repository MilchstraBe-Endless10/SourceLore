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
