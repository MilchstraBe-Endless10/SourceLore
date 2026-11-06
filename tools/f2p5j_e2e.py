#!/usr/bin/env python3
"""F2-P5J 三进程 E2E：项目配置+源码写入 → 项目/关系查询 → 卡片。"""
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
TMP = os.environ.get("SL_P5J_TMP") or "/tmp/sl_p5j"

ROOT_TS_A = '''{
  "files": [],
  "references": [
    { "path": "./packages/app" },
    { "path": "./packages/core" }
  ]
}
'''

ROOT_TS_B = '''{
  "files": [],
  "references": [
    { "path": "./packages/app" },
    { "path": "./packages/util" }
  ]
}
'''

APP_TS = '''{
  "extends": "../../base.json",
  "include": ["src/**/*.ts"],
  "exclude": ["src/generated/**"]
}
'''

BASE_TS = '''{
  "compilerOptions": { "composite": true },
  "include": ["unused/**/*.ts"]
}
'''

CORE_TS = '''{
  "compilerOptions": { "composite": true, "rootDir": "src", "outDir": "dist" },
  "include": ["src/**/*.ts"]
}
'''

UTIL_TS = '''{
  "files": ["src/u.ts"]
}
'''

APP_MAIN = "export function run() { return 1; }\n"
APP_GEN = "export const gen = 1;\n"
CORE_MAIN = "export const core = 1;\n"
UTIL_MAIN = "export const u = 1;\n"


def phase_write():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    import content_ingest_coordinator as CIC, blob_fetcher as BF
    import content_acquisition_policy as POL
    import ts_project_context as C
    import ts_project_ingest as TI
    from knowledge_store import KnowledgeStore
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot

    ks = KnowledgeStore(os.path.join(TMP, "kb.db"))
    out = {}

    for label, commit, root_ts, extra in (
            ("A", COMMIT_A, ROOT_TS_A, {}),
            ("B", COMMIT_B, ROOT_TS_B, {"packages/util/tsconfig.json": UTIL_TS,
                                        "packages/util/src/u.ts": UTIL_MAIN})):
        files = {
            "tsconfig.json": root_ts,
            "base.json": BASE_TS,
            "packages/app/tsconfig.json": APP_TS,
            "packages/app/src/main.ts": APP_MAIN,
            "packages/app/src/generated/gen.ts": APP_GEN,
            "packages/core/tsconfig.json": CORE_TS,
            "packages/core/src/core.ts": CORE_MAIN,
        }
        files.update(extra)

        entries = [{"path": p, "sha": BF.git_blob_oid(s.encode()),
                    "size": len(s.encode()), "type": "blob", "mode": "100644"}
                   for p, s in files.items()]
        snap = build_snapshot(repository_id=REPO,
            requested_repository="origin/demo",
            resolved_repository="origin/demo", requested_ref="main",
            commit_sha=commit, root_tree_sha="t"*40, tree_query_ref="t"*40,
            completeness_status="COMPLETE", tree_entries=entries,
            collected_at="", evidence_refs=[f"github@{commit}"])
        sid = ingest_snapshot(ks, snap)["asset_id"]

        auth = POL.build_authorization_ref(
            authorization_kind=POL.AUTH_ORIGINAL_FIXTURE, repository_id=REPO,
            scope=list(files), source="project-original",
            verification_status=POL.VERIFIED)

        blobs = {}
        for path, src in files.items():
            raw = src.encode()
            dec = POL.evaluate_all(repository_id=REPO, commit_sha=commit,
                                   file_path=path, authorization=auth)
            if dec["PERSIST_DECISION"]["decision"] != POL.ALLOW:
                continue
            ing = CIC.ingest_captured_blob(
                ks, data_root=TMP, repository_id=REPO, commit_sha=commit,
                source_snapshot_id=sid, file_path=path,
                git_blob_oid=BF.git_blob_oid(raw), git_object_format="sha1",
                raw=raw, source_declared_size=len(raw),
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            blobs[path] = {"raw": raw,
                           "blob_oid": BF.git_blob_oid(raw),
                           "content_asset_id": ing["content_asset_id"],
                           "content_digest": ing["content_sha256"]}

        tree_paths = set(files)
        bundle = C.build_all_projects(
            tree_paths=tree_paths, config_blobs=blobs, repository_id=REPO,
            commit_sha=commit, provenance_level="AUTHORIZED_LOCAL_FIXTURE")

        memberships = []
        for p in bundle["projects"]:
            if p["discovery_status"] != "PROJECT_CONFIG_VERIFIED":
                continue
            for target in ("packages/app/src/main.ts",
                           "packages/app/src/generated/gen.ts",
                           "packages/core/src/core.ts"):
                memberships.extend(C.build_memberships(
                    project=p, details=bundle["details"],
                    tree_paths=tree_paths, target_files=[target]))

        r = TI.ingest_project_bundle(store=ks, bundle=bundle,
                                     memberships=memberships)
        out[label] = {
            "projects": [{"path": p["config_path"],
                          "status": p["discovery_status"],
                          "solution": p["is_solution_style"],
                          "include": p["declared_include"]}
                         for p in bundle["projects"]],
            "references": [{"from": x["from_config_path"],
                            "declared": x["declared_path"],
                            "to": x["to_config_path"],
                            "status": x["status"]}
                           for x in bundle["references"]],
            "written": len(r["written"]),
        }
    ks.close()
    print(json.dumps({"phase": "write", "ok": True, "summary": out},
                     ensure_ascii=False))


def phase_query():
    import ts_project_query as TQ
    for label, commit in (("A", COMMIT_A), ("B", COMMIT_B)):
        q = TQ.query_projects(repository_id=REPO, commit_sha=commit,
                              data_root=TMP, show_references=True)
        print(json.dumps({
            "phase": "query", "commit": label, "state": q["state"],
            "projects": q["counts"]["projects"],
            "solution": q["counts"]["solution_style"],
            "refs": q["counts"]["references"],
            "memberships": q["counts"]["memberships"],
            "net": q["network_requests"]}, ensure_ascii=False))
        m = TQ.resolve_file_membership(
            repository_id=REPO, file_path="packages/app/src/main.ts",
            commit_sha=commit, data_root=TMP)
        print(json.dumps({"phase": "membership", "commit": label,
                          "state": m["state"],
                          "candidates": len(m.get("candidates") or []),
                          "net": m["network_requests"]}, ensure_ascii=False))


def phase_card(kind="project"):
    import ts_project_knowledge as TK
    if kind == "reference":
        r = TK.render_ts_project_card(repository_id=REPO, commit_sha=COMMIT_A,
                                      card_type="reference", data_root=TMP)
    elif kind == "membership":
        r = TK.render_ts_project_card(
            repository_id=REPO, commit_sha=COMMIT_A,
            file_path="packages/app/src/main.ts",
            card_type="membership", data_root=TMP)
    else:
        r = TK.render_ts_project_card(repository_id=REPO, commit_sha=COMMIT_A,
                                      card_type="project", data_root=TMP)
    print(json.dumps({"phase": "card", **r}, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "card":
        phase_card(sys.argv[2] if len(sys.argv) > 2 else "project")
    else:
        {"write": phase_write, "query": phase_query}[mode]()
