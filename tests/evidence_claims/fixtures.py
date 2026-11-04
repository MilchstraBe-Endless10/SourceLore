#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EC 测试夹具：在 Storage 里真实写入 snapshot / fact，供裁决使用。"""
import sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"src"/"evidence_claims"), str(ROOT/"src"/"storage"),
          str(ROOT/"src"/"facts"), str(ROOT/"src"/"collector"), str(ROOT/"src"/"runtime"),
          str(ROOT/"tests"/"facts")):
    if p not in sys.path: sys.path.insert(0, p)

from knowledge_store import KnowledgeStore
from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot
import extractor
import importlib
FI = importlib.import_module('ingest')  # src/facts/ingest.py

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40

# 两个不同的采集范围 —— 同一 commit 下可产生两个不同身份的快照，
# 这是构造"同 Commit 同路径冲突"的唯一合法方式（不能靠改 commit 或 repo）。
SCOPE_FULL = "full_tree_enumeration"
SCOPE_ALT = "full_tree_enumeration_alt"

README = {"path": "README", "type": "blob", "sha": "9"*40, "size": 13,
          "mode": "100644", "mode_kind": "file", "depth": 0}
DOCS = {"path": "docs", "type": "tree", "sha": "d"*40, "size": None,
        "mode": "040000", "mode_kind": "file", "depth": 0}


def fresh(tmp):
    return KnowledgeStore(str(Path(tmp) / "kb.db"))


def make_snapshot(store, *, repo="1296269", commit=COMMIT_A,
                  entries=None, completeness="COMPLETE", truncated=False,
                  manifest_v1=False, scope=SCOPE_FULL):
    ent = entries if entries is not None else [README, DOCS]
    snap = build_snapshot(
        repository_id=repo, requested_repository="o/r", resolved_repository="o/r",
        requested_ref="master", commit_sha=commit,
        root_tree_sha="t"*40, tree_query_ref="t"*40,
        completeness_status=completeness, tree_entries=ent,
        collected_at="t", evidence_refs=["ev"],
        truncated_seen=truncated, manifest_v1=manifest_v1,
        retrieval_scope=scope)
    r = ingest_snapshot(store, snap)
    return {"asset_id": r.get("asset_id"), "snapshot": snap,
            "state": r.get("state")}


def make_fact(store, snapshot_asset_id, path):
    """抽取并入库一条事实，返回 fact 资产 id。"""
    o = extractor.extract_file_path_observation(
        store, snapshot_asset_id=snapshot_asset_id, target_path=path)
    r = FI.ingest_fact(store, o)
    return {"obs": o, "result": r, "fact_id": o.fact_id,
            "asset_id": r.get("asset_id"), "state": r.get("state")}


def inject_synthetic_absent_fact(store, snapshot_asset_id, *, path, commit):
    """★ 仅用于测试：直接向 Storage 写入一条"同 Commit 的 ABSENT 事实"。

    这不是正常采集路径，而是**模拟来源数据损坏**的场景（题面第 7 节）。
    用途：验证裁决器遇到同范围矛盾时不会强行裁决（不得多数票、不得取最新）。
    """
    from asset_models import AssetDraft
    import facts_models_proxy as PROXY
    import ec_models as ECM

    snap = store.get_asset(snapshot_asset_id, verify=True)
    assert snap.get("ok"), snap
    sa = snap["asset"]
    sp = sa["payload"]
    snap_li = sa["logical_identity"]          # 在 asset 层，不在 payload 里
    norm = ECM.normalize_path(path)

    seed = ECM.sha256_of({"synthetic": True, "path": norm, "commit": commit})
    fact_logical = "SL-FACT-INJ-" + seed[:32]

    observed = {"path": norm, "completeness_status": "COMPLETE",
                "injected_for_test": True, "synthetic_provenance": True}
    chash = PROXY.fact_content_hash_of(
        observation="OBSERVED_ABSENT_IN_COVERED_SCOPE",
        observed_value=observed, unknown_reason=None,
        commit_sha=commit, completeness_status="COMPLETE")

    payload = {
        "fact_id": fact_logical,
        "fact_type": "file_path_observation",
        "observation": "OBSERVED_ABSENT_IN_COVERED_SCOPE",
        "repository_id": sp["repository_id"],
        "commit_sha": commit,
        "snapshot_asset_id": snapshot_asset_id,
        "snapshot_logical_identity": snap_li,
        "normalized_parameters": {"target_path": norm},
        "observed_value": observed,
        "completeness_status": "COMPLETE",
        "content_hash": chash,
        "evidence_refs": [{"kind": "synthetic_test_injection"}],
        "unknown_reason": None,
    }

    d = AssetDraft(asset_type="extracted_fact", logical_identity=fact_logical,
                   repository_id=sp["repository_id"], payload=payload,
                   asset_version=1, operation_id="OP-INJ-" + seed[:24])
    r = store.append_asset_and_advance(d, expected_version=None,
                                       operation_id="OP-INJ-" + seed[:24])
    assert r.get("ok"), r
    return {"fact_id": fact_logical, "asset_id": r["asset_id"]}
