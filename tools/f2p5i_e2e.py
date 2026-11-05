#!/usr/bin/env python3
"""F2-P5I 三进程 E2E：配置+源码写入 → 关系查询 → 关系卡片。"""
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
TMP = os.environ.get("SL_P5I_TMP") or "/tmp/sl_p5i"

APP = '''import { util } from "@/utils";
import { Button } from "@/components/Button";
import type { T } from "@/types";
export function run() { return util(); }
'''

TSCONFIG_A = '''{
  // 路径别名
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
    },
  },
}
'''

TSCONFIG_B = TSCONFIG_A.replace("./src/*", "./lib/*")

UTILS_TS = "export const util = () => 1;\n"
BTN_TSX = "export const Button = () => <div/>;\n"
TYPES_TS = "export interface T { x: number }\n"


def phase_write():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    import source_dispatch as SD, source_fact_ingest as SFI
    import content_ingest_coordinator as CIC, blob_fetcher as BF
    import content_acquisition_policy as POL
    import tsconfig_parser as TP, config_aware_resolver as RZ
    import module_config_models as CM, module_relation_ingest as MI
    import module_relation_query as MQ
    from knowledge_store import KnowledgeStore
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot

    ks = KnowledgeStore(os.path.join(TMP, "kb.db"))
    out = {}
    for label, commit, tscfg, tree in (
            ("A", COMMIT_A, TSCONFIG_A,
             {"src/app.ts", "src/utils.ts", "src/components/Button.tsx",
              "src/types.ts"}),
            ("B", COMMIT_B, TSCONFIG_B,
             {"src/app.ts", "lib/utils.ts", "lib/components/Button.tsx",
              "lib/types.ts"})):
        files = [("tsconfig.json", tscfg), ("src/app.ts", APP)]
        for p in sorted(tree):
            if p == "src/app.ts":
                continue
            files.append((p, UTILS_TS if p.endswith(".ts")
                          and "Button" not in p else
                          (BTN_TSX if p.endswith(".tsx") else TYPES_TS)))
        # 补齐 B 的 lib 路径文件
        if label == "B":
            files = [("tsconfig.json", tscfg), ("src/app.ts", APP),
                     ("lib/utils.ts", UTILS_TS),
                     ("lib/components/Button.tsx", BTN_TSX),
                     ("lib/types.ts", TYPES_TS)]

        entries = [{"path": p, "sha": BF.git_blob_oid(s.encode()),
                    "size": len(s.encode()), "type": "blob", "mode": "100644"}
                   for p, s in files]
        snap = build_snapshot(repository_id=REPO,
            requested_repository="origin/demo",
            resolved_repository="origin/demo", requested_ref="main",
            commit_sha=commit, root_tree_sha="t"*40, tree_query_ref="t"*40,
            completeness_status="COMPLETE", tree_entries=entries,
            collected_at="", evidence_refs=[f"github@{commit}"])
        sid = ingest_snapshot(ks, snap)["asset_id"]

        auth = POL.build_authorization_ref(
            authorization_kind=POL.AUTH_ORIGINAL_FIXTURE, repository_id=REPO,
            scope=[p for p, _ in files], source="project-original",
            verification_status=POL.VERIFIED)

        res = {}
        cfg_obs = None
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

            if path == "tsconfig.json":
                pr = TP.parse_tsconfig(raw, config_path=path)
                if pr["ok"]:
                    surf = TP.extract_config_surface(pr["data"], config_dir="")
                    cfg_obs = CM.build_config_observation(
                        repository_id=REPO, commit_sha=commit,
                        config_path=path, config_kind=CM.CONFIG_TSCONFIG,
                        git_blob_oid=BF.git_blob_oid(raw),
                        content_asset_id=ing["content_asset_id"],
                        content_digest=ing["content_sha256"],
                        effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED,
                        declared_paths=surf["paths"],
                        declared_base_url=surf["base_url"],
                        provenance_level="AUTHORIZED_LOCAL_FIXTURE")
                    MI.ingest_config_observation(ks, observation=cfg_obs)
                res[path] = {"config": pr["ok"]}
                continue

            o = SD.parse_source(raw, repository_id=REPO, commit_sha=commit,
                                file_path=path,
                                git_blob_oid=BF.git_blob_oid(raw),
                                content_asset_id=ing["content_asset_id"],
                                content_sha256=ing["content_sha256"],
                                provenance_level="AUTHORIZED_LOCAL_FIXTURE")
            fr = SFI.ingest_source_facts(ks, observation=o,
                                         source_snapshot_id=sid)
            res[path] = {"symbols": len(o["observed_symbols"]),
                         "imports": len(o["observed_imports"]),
                         "facts": len(fr["written"])}

        # 解析 app.ts 的导入
        if cfg_obs:
            o_app = SD.parse_source(APP.encode(), repository_id=REPO,
                                    commit_sha=commit, file_path="src/app.ts",
                                    git_blob_oid="b"*40,
                                    content_asset_id="SL-A-app",
                                    content_sha256="sha256:app")
            tc = dict(cfg_obs,
                      _base_dir=TP.resolve_base_dir(
                          config_dir="", base_url=cfg_obs.get("declared_base_url")))
            rels = 0
            for imp in o_app["observed_imports"]:
                r = RZ.resolve_with_config(
                    specifier=imp["module_specifier"],
                    importing_file_path="src/app.ts", tree_paths=tree,
                    tsconfig_observation=tc,
                    import_kind=imp["import_kind"],
                    is_type_only=imp["is_type_only"])
                if r["resolution_state"] == "LOCAL_MODULE_RESOLVED":
                    full = CM.build_resolution_observation(
                        repository_id=REPO, commit_sha=commit,
                        importing_file_path="src/app.ts",
                        importing_blob_oid="b"*40,
                        importing_content_asset_id="SL-A-app",
                        import_fact_id=imp.get("import_id") or "IMP",
                        module_specifier=imp["module_specifier"],
                        import_kind=imp["import_kind"],
                        is_type_only=imp["is_type_only"],
                        config_observation_ids=r["config_observation_ids"],
                        config_blob_oids=[cfg_obs["git_blob_oid"]],
                        resolution_policy=r["resolution_policy"],
                        matched_config_rule=r["matched_config_rule"],
                        matched_config_field=r["matched_config_field"],
                        matched_config_path=cfg_obs["config_path"],
                        candidate_paths=r["candidate_paths"],
                        resolved_target_path=r["resolved_target_path"],
                        resolution_state=r["resolution_state"],
                        evidence_refs=[
                            f"import:{imp['module_specifier']}",
                            f"config:{cfg_obs['config_observation_id']}",
                            f"tree:{r['resolved_target_path']}"],
                        provenance_level="AUTHORIZED_LOCAL_FIXTURE")
                    rr = MI.ingest_resolution(ks, resolution=full,
                                              evidence_refs=full["evidence_refs"],
                                              source_snapshot_id=sid)
                    rels += len(rr["written"])
            res["_relations"] = rels
        out[label] = res
    ks.close()
    print(json.dumps({"phase": "write", "ok": True, "summary": out},
                     ensure_ascii=False))


def phase_query():
    import module_relation_query as MQ
    for label, commit in (("A", COMMIT_A), ("B", COMMIT_B)):
        q = MQ.query_relations(repository_id=REPO, commit_sha=commit,
                               importing_file_path="src/app.ts", data_root=TMP)
        print(json.dumps({
            "phase": "query", "commit": label, "state": q["state"],
            "relations": q["counts"]["relations"],
            "resolved": q["counts"]["resolved"],
            "targets": sorted(x["resolved_target_path"]
                              for x in q["relations"]),
            "rules": sorted({x["matched_config_rule"] for x in q["relations"]}),
            "network": q["network_requests"]}, ensure_ascii=False))


def phase_card(commit_label="A"):
    import source_knowledge as SK
    commit = COMMIT_A if commit_label == "A" else COMMIT_B
    r = SK.render_relation_card(repository_id=REPO, commit_sha=commit,
                                importing_file_path="src/app.ts",
                                data_root=TMP)
    print(json.dumps({"phase": "card", **r}, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "card":
        phase_card(sys.argv[2] if len(sys.argv) > 2 else "A")
    else:
        {"write": phase_write, "query": phase_query}[mode]()
