#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P2A 端到端回放：**历史真实数据**（P1C 已采集），不是本轮实时 API 访问。

链路：P1C 真实快照记录 → 重建 SourceSnapshot → 入 Storage → Facts 抽取 → 入 Storage。
"""
import json, sys, tempfile, shutil, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT/"src"/"collector"), str(ROOT/"src"/"storage"),
          str(ROOT/"src"/"runtime"), str(ROOT/"src"/"facts")):
    if p not in sys.path: sys.path.insert(0, p)

from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot
from knowledge_store import KnowledgeStore
import extractor
import ingest as FI

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"implementation"/"F2_P2A_E2E_REPLAY.json"

rec = json.loads((ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json").read_text(encoding="utf-8"))
assert rec["result"] == "REAL_GITHUB_OK", "P1C 记录不是成功记录"

# 重建 P1C 当时的快照（v2 清单：README 一条）
ents = [{"path": "README", "type": "blob",
         "sha": rec["blob"]["blob_sha"], "size": rec["blob"]["size"],
         "mode": "100644", "mode_kind": "file", "depth": 0}]

snap = build_snapshot(
    repository_id=rec["repository_id"],
    requested_repository=rec["target"],
    resolved_repository=rec["resolved_repository"],
    requested_ref=rec["requested_ref"],
    commit_sha=rec["commit_sha"],
    root_tree_sha=rec["root_tree_sha"],
    tree_query_ref=rec["tree_query_ref"],
    completeness_status="COMPLETE",
    tree_entries=ents,
    collected_at=rec["attempted_at"],
    evidence_refs=[f"github:repos/{rec['target']}@{rec['commit_sha']}"])

out = {"artifact": "F2_P2A_E2E_REPLAY", "data_provenance": "HISTORICAL_REAL_DATA",
       "note": "这是 P1C 真实采集数据的回放，不是本轮实时 GitHub 访问",
       "source_record": "docs/implementation/F2_P1C_REAL_GITHUB.json",
       "replayed_at": datetime.datetime.now(TZ).isoformat(timespec="seconds"),
       "snapshot": {"repository_id": snap.repository_id,
                    "commit_sha": snap.commit_sha,
                    "root_tree_sha": snap.root_tree_sha,
                    "logical_identity": snap.logical_identity(),
                    "content_hash": snap.content_hash()}}

tmp = Path(tempfile.mkdtemp(prefix="p2a_e2e_"))
try:
    with KnowledgeStore(str(tmp/"kb.db")) as ks:
        r1 = ingest_snapshot(ks, snap)
        out["snapshot_ingest"] = {"state": r1["state"], "asset_id": r1.get("asset_id")}
        aid = r1["asset_id"]

        o_present = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="README")
        out["fact_readme"] = {"observation": o_present.observation,
                              "fact_id": o_present.fact_id,
                              "object_kind": o_present.observed_value.get("object_kind"),
                              "blob_sha": o_present.observed_value.get("blob_sha")}

        o_absent = extractor.extract_file_path_observation(
            ks, snapshot_asset_id=aid, target_path="package.json")
        out["fact_absent"] = {"observation": o_absent.observation,
                              "scope_statement": o_absent.observed_value.get("scope_statement")}

        ing1 = FI.ingest_fact(ks, o_present)
        ing2 = FI.ingest_fact(ks, o_present)
        out["fact_ingest"] = {"first": ing1["state"], "second": ing2["state"],
                              "asset_id": ing1.get("asset_id"),
                              "pointer_version": ing1.get("pointer_version")}

        n_facts = ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='extracted_fact'").fetchone()["n"]
        n_snaps = ks.conn.execute(
            "SELECT count(*) AS n FROM assets WHERE asset_type='repository_snapshot'").fetchone()["n"]
        out["summary"] = {"snapshot_assets": n_snaps, "fact_assets": n_facts}
finally:
    shutil.rmtree(tmp, ignore_errors=True)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(out["summary"], ensure_ascii=False))
print("README:", out["fact_readme"]["observation"], "| absent:", out["fact_absent"]["observation"])
print("ingest:", out["fact_ingest"]["first"], "->", out["fact_ingest"]["second"])
print("written ->", OUT.name)
