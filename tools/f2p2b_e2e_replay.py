#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P2B 端到端回放：Collector → Storage → Facts → Storage → EC → Storage。

数据级别：HISTORICAL_REAL_DATA（P1C 真实采集记录的回放，**不是**本轮实时 API）。
并按 §1A 核验结论，对 package.json 的"不存在"命题**必须 abstain**。
"""
import json, sys, tempfile, shutil, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT/"src"/"collector"), str(ROOT/"src"/"storage"),
          str(ROOT/"src"/"runtime"), str(ROOT/"src"/"facts"),
          str(ROOT/"src"/"evidence_claims")):
    if p not in sys.path: sys.path.insert(0, p)

from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot
from knowledge_store import KnowledgeStore
import importlib
extractor = importlib.import_module("extractor")
FI = importlib.import_module("ingest")
import ec_models as M
import verifier as V
import verification_store as VS

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"implementation"/"F2_P2B_E2E_REPLAY.json"
rec = json.loads((ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json").read_text(encoding="utf-8"))
assert rec["result"] == "REAL_GITHUB_OK"

# 依 §1A：只放**真实存在依据**的条目（README 有真实 blob），
# 不放人工补录的完整清单 —— 因此 package.json 的"不存在"只能 abstain。
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

out = {"artifact": "F2_P2B_E2E_REPLAY",
       "data_provenance": "HISTORICAL_REAL_DATA",
       "note": ("P1C 真实采集记录的回放，不是本轮实时 GitHub 访问；"
                "并按 §1A 核验结论：manifest 只有真实 blob 依据，无完整原始 Tree 清单"),
       "precondition_A_impact": ("package.json 的'不存在'命题缺真实完整覆盖证据 → 必须 abstain"),
       "replayed_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
       "snapshot": {"repository_id": snap.repository_id,
                    "commit_sha": snap.commit_sha,
                    "root_tree_sha": snap.root_tree_sha,
                    "logical_identity": snap.logical_identity()}}

tmp = Path(tempfile.mkdtemp(prefix="p2b_e2e_"))
try:
    with KnowledgeStore(str(tmp/"kb.db")) as ks:
        r1 = ingest_snapshot(ks, snap)
        aid = r1["asset_id"]
        out["snapshot_ingest"] = {"state": r1["state"], "asset_id": aid}

        # Facts
        f_readme = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="README")
        fi1 = FI.ingest_fact(ks, f_readme)
        f_pkg = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="package.json")
        out["facts"] = {
            "readme": {"observation": f_readme.observation, "state": fi1["state"]},
            # 注意：这份回放清单**不含完整 Tree**（依 §1A），所以 package.json 是 ABSENT…
            # 但这正是被 §1A 判为"证据不足"的那类结论，本批不据此裁决。
            "package_json": {"observation": f_pkg.observation,
                             "ingested": False,
                             "why": "依 §1A，该清单缺真实完整 Tree 依据，不据此产出裁决证据"},
        }

        # EC：README 存在命题 → supported
        c_readme = M.build_path_claim(repository_id=rec["repository_id"],
                                      commit_sha=rec["commit_sha"],
                                      target_path="README", expected_exists=True,
                                      claim_origin="human_specified")
        v_readme = V.verify_path_claim(ks, c_readme, [f_readme.fact_id])
        out["claim_readme_exists"] = {"status": v_readme.status,
                                      "reason": v_readme.reason_code,
                                      "verification_id": v_readme.verification_id}

        # EC：README 不存在命题 → refuted
        c_not = M.build_path_claim(repository_id=rec["repository_id"],
                                   commit_sha=rec["commit_sha"],
                                   target_path="README", expected_exists=False)
        v_not = V.verify_path_claim(ks, c_not, [f_readme.fact_id])
        out["claim_readme_not_exists"] = {"status": v_not.status,
                                          "verification_id": v_not.verification_id}

        # EC：package.json 不存在命题 → 必须 abstain（§1A）
        c_pkg = M.build_path_claim(repository_id=rec["repository_id"],
                                   commit_sha=rec["commit_sha"],
                                   target_path="package.json", expected_exists=False)
        v_pkg = V.verify_path_claim(ks, c_pkg, [])   # 无合法证据
        out["claim_package_json_absent"] = {
            "status": v_pkg.status, "reason": v_pkg.reason_code,
            "expected_by_precondition_A": "insufficient_evidence",
            "abstained": v_pkg.status == M.INSUFFICIENT}

        # 错误 Commit 证据不被接受
        c_wrong = M.build_path_claim(repository_id=rec["repository_id"],
                                     commit_sha="9"*40, target_path="README",
                                     expected_exists=True)
        v_wrong = V.verify_path_claim(ks, c_wrong, [f_readme.fact_id])
        out["wrong_commit_rejected"] = {"status": v_wrong.status,
                                        "reason": v_wrong.reason_code}

        # 持久化 + 幂等
        VS.ingest_claim(ks, c_readme)
        a = VS.ingest_verification(ks, v_readme, repository_id=rec["repository_id"])
        b = VS.ingest_verification(ks, v_readme, repository_id=rec["repository_id"])
        out["persistence"] = {"first": a["state"], "second": b["state"]}

        out["summary"] = {
            "snapshot_assets": ks.conn.execute(
                "SELECT count(*) AS n FROM assets "
                "WHERE asset_type='repository_snapshot'").fetchone()["n"],
            "fact_assets": ks.conn.execute(
                "SELECT count(*) AS n FROM assets "
                "WHERE asset_type='extracted_fact'").fetchone()["n"],
            "claim_assets": ks.conn.execute(
                "SELECT count(*) AS n FROM assets "
                "WHERE asset_type='claim_candidate'").fetchone()["n"],
            "verification_assets": ks.conn.execute(
                "SELECT count(*) AS n FROM assets "
                "WHERE asset_type='claim_verification'").fetchone()["n"],
        }
finally:
    shutil.rmtree(tmp, ignore_errors=True)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("README exists :", out["claim_readme_exists"]["status"])
print("README absent :", out["claim_readme_not_exists"]["status"])
print("pkg.json abstain:", out["claim_package_json_absent"]["abstained"])
print("wrong commit  :", out["wrong_commit_rejected"]["status"],
      out["wrong_commit_rejected"]["reason"])
print("idempotent    :", out["persistence"]["first"], "->", out["persistence"]["second"])
print("summary       :", json.dumps(out["summary"], ensure_ascii=False))
