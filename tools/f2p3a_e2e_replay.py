#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P3A 端到端回放：Collector → Storage → Facts → EC → Lifecycle。

数据级别：HISTORICAL_REAL_DATA（P1C 真实采集记录），**不是本轮实时 GitHub 观测**。
"""
import json, sys, tempfile, shutil, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("src/collector","src/storage","src/runtime","src/facts",
          "src/evidence_claims","src/lifecycle"):
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
import impact_resolver as IR, lifecycle_store as LS

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"implementation"/"F2_P3A_E2E_REPLAY.json"
rec = json.loads((ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json").read_text(encoding="utf-8"))
assert rec["result"] == "REAL_GITHUB_OK"

COMMIT_BASELINE = rec["commit_sha"]
# ★ 本轮**未重新联网**：所谓"新 Commit"是合成对位，明确标注 SYNTHETIC_FIXTURE
COMMIT_SYNTH_NEW = "f" * 40

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

out = {"artifact": "F2_P3A_E2E_REPLAY",
       "data_provenance": "HISTORICAL_REAL_DATA",
       "live_github_refetch": False,
       "note": ("本轮**未重新访问 GitHub**。基线 Commit 来自 P1C 真实采集；"
                "所谓'新 Commit'是 SYNTHETIC_FIXTURE 合成对位，"
                "**不是实时 Ref 更新检测**"),
       "replayed_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
       "baseline_commit_sha": COMMIT_BASELINE}

tmp = Path(tempfile.mkdtemp(prefix="p3a_e2e_"))
try:
    with KnowledgeStore(str(tmp/"kb.db")) as ks:
        # 1) Collector → Storage
        r1 = ingest_snapshot(ks, snap)
        aid = r1["asset_id"]
        out["snapshot"] = {"state": r1["state"], "asset_id": aid,
                           "logical_identity": snap.logical_identity()}

        # 2) Facts
        f = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="README")
        FI.ingest_fact(ks, f)

        # 3) EC
        c = EM.build_path_claim(repository_id=rec["repository_id"],
                                commit_sha=COMMIT_BASELINE,
                                target_path="README", expected_exists=True,
                                claim_origin="human_specified")
        v = V.verify_path_claim(ks, c, [f.fact_id])
        VS.ingest_claim(ks, c)
        VS.ingest_verification(ks, v, repository_id=rec["repository_id"])
        out["ec"] = {"claim_id": c.claim_id, "status": v.status,
                     "verification_id": v.verification_id,
                     "review_status": c.review_status}

        # 4) Lifecycle：把已裁决的 Claim 挂到 master 的跟踪上
        w = L.build_watch(repository_id=rec["repository_id"],
                          requested_ref=rec["requested_ref"],
                          ref_kind=L.REF_KIND_BRANCH,
                          retrieval_scope="full_tree_enumeration",
                          baseline_commit_sha=COMMIT_BASELINE,
                          claim_id=c.claim_id)
        LS.ingest_watch(ks, w)
        out["watch"] = {"watch_id": w.watch_id,
                        "applicability_scope": w.applicability_scope}

        # 4a) 用**历史真实采集执行记录**构造观测。
        # ★ 为什么不用快照：快照的 identity 与 payload 都**不含 requested_ref**
        #   （见 F2_P3A_REF_OBSERVATION_AUDIT），无法证明"master 当时指向该 commit"。
        #   执行记录同时含 requested_ref 与 commit_sha，才是合法的 Ref→Commit 对位证据。
        obs_real = RO.observe_ref_from_record(
            record=rec, repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"])
        # 反证：用快照构造会被正确拒绝
        snap_asset = ks.get_asset(aid)["asset"]
        obs_from_snapshot = RO.observe_ref_from_snapshot(
            snapshot_asset=snap_asset, repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"],
            provenance_level=RO.PROV_HISTORICAL)
        out["snapshot_cannot_prove_ref"] = {
            "observation_status": obs_from_snapshot.observation_status,
            "reason": obs_from_snapshot.failure_reason,
            "note": "快照不含 requested_ref，故不能证明该 Ref 指向该 Commit"}
        LS.ingest_observation(ks, obs_real)
        a_real = FE.assess(watch=w, observation=obs_real)
        LS.ingest_assessment(ks, a_real)
        out["assess_baseline"] = {"state": a_real.freshness_state,
                                  "observation_status": obs_real.observation_status,
                                  "provenance": obs_real.provenance_level}

        # 4b) 合成"新 Commit"观测（明确标 SYNTHETIC，不冒充真实）
        obs_new = RO.observe_ref_from_snapshot(
            snapshot_asset={"asset_id": "synth-new", "payload": {
                "repository_id": rec["repository_id"],
                "commit_sha": COMMIT_SYNTH_NEW,
                "requested_ref": rec["requested_ref"],
                "retrieval_scope": "full_tree_enumeration",
                "collector_version": "sourcelore-collector/1.0.0"}},
            repository_id=rec["repository_id"],
            requested_ref=rec["requested_ref"],
            provenance_level=RO.PROV_SYNTHETIC)
        a_new = FE.assess(watch=w, observation=obs_new)
        LS.ingest_assessment(ks, a_new)
        out["assess_moved"] = {"state": a_new.freshness_state,
                               "reason": a_new.reason_code,
                               "provenance": obs_new.provenance_level,
                               "note": "SYNTHETIC_FIXTURE，非真实 Ref 更新"}

        # 4c) 无观测 → UNKNOWN（网络失败不得伪装成更新）
        ro_client = type("C", (), {
            "commit_for_ref": lambda s, o, n, r: type("R", (), {
                "ok": False, "data": None,
                "error": type("E", (), {"error_code": "NETWORK_TIMEOUT"})()})()})()
        obs_fail = RO.observe_ref_via_collector(
            ro_client, owner="octocat", name="Hello-World",
            repository_id=rec["repository_id"], requested_ref=rec["requested_ref"])
        a_fail = FE.assess(watch=w, observation=obs_fail)
        out["assess_unobservable"] = {"state": a_fail.freshness_state,
                                      "reason": a_fail.reason_code,
                                      "observed_commit": obs_fail.resolved_commit_sha}

        # 5) 隔离验证：EC 未被改动
        pay = ks.get_asset(v.verification_id) if False else None
        row = ks.conn.execute(
            "SELECT payload_json FROM assets WHERE logical_identity=?",
            (v.verification_id,)).fetchone()
        p = json.loads(row["payload_json"])
        out["ec_unchanged_after_lifecycle"] = {
            "status": p["status"],
            "still_supported": p["status"] == "supported",
            "claim_review_status": c.review_status}

        # 6) 影响范围
        res = IR.resolve_affected([w], assessment_list=[a_real, a_new, a_fail])
        out["impact"] = {"affected": res["affected_claim_ids"],
                         "unaffected_count": len(res["unaffected"])}

        out["counts"] = {t: ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type=?",
            (t,)).fetchone()["n"]
            for t in ("repository_snapshot", "extracted_fact", "claim_candidate",
                      "claim_verification", "lifecycle_watch", "ref_observation",
                      "freshness_assessment")}
finally:
    shutil.rmtree(tmp, ignore_errors=True)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("baseline  :", out["assess_baseline"]["state"], "/", out["assess_baseline"]["provenance"])
print("moved     :", out["assess_moved"]["state"], "/", out["assess_moved"]["provenance"])
print("unobserv. :", out["assess_unobservable"]["state"], out["assess_unobservable"]["reason"])
print("EC 未变   :", out["ec_unchanged_after_lifecycle"]["still_supported"], p["status"])
print("affected  :", out["impact"]["affected"])
print("counts    :", json.dumps(out["counts"], ensure_ascii=False))
print("live API  :", out["live_github_refetch"])
