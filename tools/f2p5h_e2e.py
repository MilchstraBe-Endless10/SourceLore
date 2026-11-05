#!/usr/bin/env python3
"""F2-P5H 三进程 E2E：JS/TS 写入 → 查询 → 卡片。"""
import sys, os, json, shutil
from pathlib import Path
R = Path(__file__).resolve().parents[1]
for p in ("runtime","storage","collector","facts","evidence_claims","lifecycle",
          "views","renderer","research","content","content_persistence",
          "source_analysis","skill_interface"):
    sys.path.insert(0, str(R/"src"/p))

REPO = "990001"
COMMIT_A = "a"*40
COMMIT_B = "b"*40
TMP = os.environ.get("SL_P5H_TMP") or "/tmp/sl_p5h"

JS_A = '''export class Worker {
  run() { return 1; }
  static make() { return new Worker(); }
}
export function helper() { return 2; }
const start = () => 3;
import os from "./os.js";
import { util } from "./util.js";
export default Worker;
'''

JS_B = JS_A.replace("run() {", "execute() {")

TS = '''interface User { id: number }
type Id = string;
enum Color { Red }
import type { T } from "./types";
export type { T };
export class Svc { go(): void {} }
'''


def phase_write():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    import source_dispatch as SD, source_fact_ingest as SFI
    import content_ingest_coordinator as CIC, blob_fetcher as BF
    import content_acquisition_policy as POL
    from knowledge_store import KnowledgeStore
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot

    ks = KnowledgeStore(os.path.join(TMP, "kb.db"))
    auth = POL.build_authorization_ref(
        authorization_kind=POL.AUTH_ORIGINAL_FIXTURE, repository_id=REPO,
        scope=["app.js", "types.ts"], source="project-original",
        verification_status=POL.VERIFIED)
    out = {}
    for label, commit, files in (
            ("A", COMMIT_A, [("app.js", JS_A), ("types.ts", TS)]),
            ("B", COMMIT_B, [("app.js", JS_B), ("types.ts", TS)])):
        entries = [{"path": p, "sha": BF.git_blob_oid(s.encode()),
                    "size": len(s.encode()), "type": "blob", "mode": "100644"}
                   for p, s in files]
        snap = build_snapshot(repository_id=REPO, requested_repository="origin/demo",
            resolved_repository="origin/demo", requested_ref="main",
            commit_sha=commit, root_tree_sha="t"*40, tree_query_ref="t"*40,
            completeness_status="COMPLETE", tree_entries=entries,
            collected_at="", evidence_refs=[f"github@{commit}"])
        sid = ingest_snapshot(ks, snap)["asset_id"]
        res = {}
        for path, src in files:
            raw = src.encode()
            dec = POL.evaluate_all(repository_id=REPO, commit_sha=commit,
                                   file_path=path, authorization=auth)
            if dec["PERSIST_DECISION"]["decision"] != POL.ALLOW:
                res[path] = {"blocked": True}; continue
            ing = CIC.ingest_captured_blob(
                ks, data_root=TMP, repository_id=REPO, commit_sha=commit,
                source_snapshot_id=sid, file_path=path,
                git_blob_oid=BF.git_blob_oid(raw), git_object_format="sha1",
                raw=raw, source_declared_size=len(raw),
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            o = SD.parse_source(raw, repository_id=REPO, commit_sha=commit,
                                file_path=path, git_blob_oid=BF.git_blob_oid(raw),
                                content_asset_id=ing["content_asset_id"],
                                content_sha256=ing["content_sha256"],
                                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            fr = SFI.ingest_source_facts(ks, observation=o,
                                         source_snapshot_id=sid)
            res[path] = {"status": o.get("parse_status"),
                         "language": o.get("language"),
                         "grammar": o.get("grammar_version"),
                         "symbols": len(o["observed_symbols"]),
                         "imports": len(o["observed_imports"]),
                         "exports": len(o["observed_exports"]),
                         "written": len(fr["written"]),
                         "content": ing["content_asset_id"]}
        out[label] = res
    ks.close()
    print(json.dumps({"phase": "write", "ok": True, "summary": out},
                     ensure_ascii=False))


def phase_query():
    import source_knowledge_query as Q
    for label, commit in (("A", COMMIT_A), ("B", COMMIT_B)):
        q = Q.source_query(repository_id=REPO, commit_sha=commit,
                           file_path="app.js", data_root=TMP)
        names = sorted(s["subject"]["qualified_name"] for s in q["symbols"])
        print(json.dumps({"phase": "query", "commit": label,
                          "state": q["state"], "symbols": names,
                          "imports": q["counts"]["imports"],
                          "exports": q["counts"]["exports"],
                          "network": q["network_requests"]},
                         ensure_ascii=False))


def phase_card(kind="js"):
    import source_knowledge as SK
    path = "app.js" if kind == "js" else "types.ts"
    r = SK.render_source_card(repository_id=REPO, commit_sha=COMMIT_A,
                              file_path=path, data_root=TMP)
    print(json.dumps({"phase": "card", **r}, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "card":
        phase_card(sys.argv[2] if len(sys.argv) > 2 else "js")
    else:
        {"write": phase_write, "query": phase_query}[mode]()
