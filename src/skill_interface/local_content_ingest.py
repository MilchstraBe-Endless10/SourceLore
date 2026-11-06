#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地已捕获字节 → 内容资产 → 内容事实。零网络。

★ 复用既有 ingest_captured_blob / extract_one / ingest_content_facts。
★ 只处理 README / Manifest / 源码；不执行仓库代码。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("storage", "content", "content_persistence", "source_analysis",
           "skill_interface", "collector", "facts", "evidence_claims",
           "runtime"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

TARGET_PATTERNS = ("README.md", "README", "package.json", "pyproject.toml",
                   "tsconfig.json", "jsconfig.json")


def pick_targets(tree_paths):
    """从 Tree 里挑出本轮要抽取的文件。★ 只按文件名，不做模糊匹配。"""
    out = []
    for p in tree_paths:
        name = p.rsplit("/", 1)[-1]
        if name in TARGET_PATTERNS:
            out.append(p)
        elif name.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
            out.append(p)
    return sorted(set(out))


def ingest_local_content(store, *, data_root, repository_id, commit_sha,
                         snapshot_asset_id, blobs, tree_paths,
                         provenance_level="AUTHORIZED_LOCAL_FIXTURE",
                         max_files=64):
    """逐文件：捕获字节 → 内容资产 → 抽取 → 内容事实。"""
    import content_ingest_coordinator as CIC
    import content_extractor as CX
    import content_fact_ingest as CFI

    targets = pick_targets(tree_paths)[:max_files]
    results = []
    for path in targets:
        raw = blobs.get(path)
        if raw is None:
            results.append({"file_path": path, "status": "BYTES_NOT_IN_ENTRY",
                            "facts": 0})
            continue
        sha = __import__("hashlib").sha1(
            b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        try:
            ing = CIC.ingest_captured_blob(
                store, data_root=data_root, repository_id=repository_id,
                commit_sha=commit_sha, source_snapshot_id=snapshot_asset_id,
                file_path=path, git_blob_oid=sha, git_object_format="sha1",
                raw=raw, source_declared_size=len(raw),
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
                provenance_level=provenance_level,
                source_api="local.git.objects")
        except Exception as e:
            results.append({"file_path": path,
                            "status": f"CAPTURE_FAILED:{type(e).__name__}",
                            "facts": 0})
            continue

        try:
            ex = CX.extract_one(
                repository_id=repository_id, commit_sha=commit_sha,
                file_path=path, git_blob_oid=sha,
                content_asset_id=ing["content_asset_id"], data=raw,
                source_snapshot_id=snapshot_asset_id,
                provenance_level=provenance_level,
                declared_completeness="COMPLETE")
        except Exception as e:
            results.append({"file_path": path,
                            "status": f"EXTRACT_FAILED:{type(e).__name__}",
                            "facts": 0})
            continue

        # ★ extract_one 的可用状态是 CONTENT_AVAILABLE（不是 _VERIFIED）
        if ex.get("status") not in ("CONTENT_AVAILABLE", "CONTENT_AVAILABLE_VERIFIED",
                                    "C_AVAILABLE"):
            results.append({"file_path": path,
                            "status": ex.get("status") or "NOT_AVAILABLE",
                            "facts": 0})
            continue

        try:
            fr = CFI.ingest_content_facts(
                store, repository_id=repository_id, commit_sha=commit_sha,
                snapshot_asset_id=snapshot_asset_id,
                snapshot_logical_identity=f"SL-SNAP-src:{repository_id}",
                extraction_result={"facts": ex.get("facts") or []},
                content_asset_id=ing["content_asset_id"],
                content_sha256=ing["content_sha256"],
                parser_id="content-extractor",
                parser_version="1",
                file_path=path, git_blob_oid=sha,
                completeness_status="COMPLETE",
                provenance_level=provenance_level)
        except Exception as e:
            results.append({"file_path": path,
                            "status": f"FACT_FAILED:{type(e).__name__}",
                            "facts": 0})
            continue

        # ★ 源码结构事实（Python AST / JS-TS / tsconfig 也算内容事实之外的独立链路）
        struct_facts = 0
        struct_status = "NOT_APPLICABLE"
        try:
            import source_dispatch as SD
            import source_fact_ingest as SFI
            obs = SD.parse_source(
                raw, repository_id=repository_id, commit_sha=commit_sha,
                file_path=path, git_blob_oid=sha,
                content_asset_id=ing["content_asset_id"],
                content_sha256=ing["content_sha256"],
                provenance_level=provenance_level)
            struct_status = obs.get("parse_status") or obs.get("extraction_status")
            if obs.get("extraction_status") == "EXTRACTED":
                sr = SFI.ingest_source_facts(
                    store, observation=obs, source_snapshot_id=snapshot_asset_id)
                struct_facts = len(sr.get("written") or [])
        except Exception as e:
            struct_status = f"STRUCT_FAILED:{type(e).__name__}"

        results.append({
            "file_path": path,
            "status": "EXTRACTED",
            "content_asset_id": ing["content_asset_id"],
            "content_sha256": ing["content_sha256"],
            "facts": len(fr.get("written") or []),
            "reused": len(fr.get("reused") or []),
            "struct_facts": struct_facts,
            "struct_status": struct_status,
        })

        # ★ tsconfig 走配置观察 + 项目关系链路（复用 P5I/P5J）
        if path.rsplit("/", 1)[-1] in ("tsconfig.json", "jsconfig.json"):
            cfg_meta = _ingest_config_and_relations(
                store, data_root=data_root, repository_id=repository_id,
                commit_sha=commit_sha, snapshot_asset_id=snapshot_asset_id,
                config_path=path, raw=raw, blob_oid=sha,
                content_asset_id=ing["content_asset_id"],
                content_digest=ing["content_sha256"],
                tree_paths=tree_paths, blobs=blobs,
                provenance_level=provenance_level)
            results[-1]["config"] = cfg_meta
    return results


def _ingest_config_and_relations(store, *, data_root, repository_id, commit_sha,
                                  snapshot_asset_id, config_path, raw, blob_oid,
                                  content_asset_id, content_digest, tree_paths,
                                  blobs, provenance_level):
    """tsconfig → 配置观察 → 模块关系 + TS 项目事实。"""
    import tsconfig_parser as TP
    import module_config_models as CM
    import module_relation_ingest as MRI
    import config_aware_resolver as RZ
    import ts_project_context as TPC
    import ts_project_ingest as TPI

    out = {"config_facts": 0, "relation_facts": 0, "project_facts": 0}
    pr = TP.parse_tsconfig(raw, config_path=config_path)
    if not pr["ok"]:
        out["status"] = pr["error_code"]
        return out

    surf = TP.extract_config_surface(pr["data"], config_dir="")
    cfg_obs = CM.build_config_observation(
        repository_id=repository_id, commit_sha=commit_sha,
        config_path=config_path, config_kind=CM.CONFIG_TSCONFIG,
        git_blob_oid=blob_oid, content_asset_id=content_asset_id,
        content_digest=content_digest,
        effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED,
        declared_paths=surf["paths"], declared_base_url=surf["base_url"],
        declared_references=surf["references"],
        provenance_level=provenance_level)
    cr = MRI.ingest_config_observation(store, observation=cfg_obs)
    out["config_facts"] = len(cr.get("written") or [])

    # 模块关系：对每个 .ts/.tsx 文件的导入求解
    tc = dict(cfg_obs,
              _base_dir=TP.resolve_base_dir(config_dir="",
                                            base_url=surf["base_url"]))
    tree = set(tree_paths)
    rel_written = 0
    for fpath, fraw in blobs.items():
        if not fpath.endswith((".ts", ".tsx")):
            continue
        try:
            import source_dispatch as SD
            o = SD.parse_source(
                fraw, repository_id=repository_id, commit_sha=commit_sha,
                file_path=fpath, git_blob_oid=blob_oid,
                content_asset_id=content_asset_id,
                content_sha256=content_digest,
                provenance_level=provenance_level)
        except Exception:
            continue
        for imp in o.get("observed_imports") or []:
            r = RZ.resolve_with_config(
                specifier=imp.get("module_specifier"),
                importing_file_path=fpath, tree_paths=tree,
                tsconfig_observation=tc,
                import_kind=imp.get("import_kind"),
                is_type_only=bool(imp.get("is_type_only")))
            if r["resolution_state"] != "LOCAL_MODULE_RESOLVED":
                continue
            full = CM.build_resolution_observation(
                repository_id=repository_id, commit_sha=commit_sha,
                importing_file_path=fpath, importing_blob_oid=blob_oid,
                importing_content_asset_id=content_asset_id,
                import_fact_id=imp.get("import_id") or "IMP",
                module_specifier=imp.get("module_specifier"),
                import_kind=imp.get("import_kind"),
                is_type_only=bool(imp.get("is_type_only")),
                config_observation_ids=r["config_observation_ids"],
                config_blob_oids=[blob_oid],
                resolution_policy=r["resolution_policy"],
                matched_config_rule=r["matched_config_rule"],
                matched_config_field=r["matched_config_field"],
                matched_config_path=config_path,
                candidate_paths=r["candidate_paths"],
                resolved_target_path=r["resolved_target_path"],
                resolution_state=r["resolution_state"],
                evidence_refs=[f"import:{imp.get('module_specifier')}",
                               f"config:{cfg_obs['config_observation_id']}",
                               f"tree:{r['resolved_target_path']}"],
                provenance_level=provenance_level)
            rr = MRI.ingest_resolution(
                store, resolution=full, evidence_refs=full["evidence_refs"],
                source_snapshot_id=snapshot_asset_id)
            rel_written += len(rr.get("written") or [])
    out["relation_facts"] = rel_written

    # TS 项目事实
    cb = {config_path: {"raw": raw, "blob_oid": blob_oid,
                        "content_asset_id": content_asset_id,
                        "content_digest": content_digest}}
    bundle = TPC.build_all_projects(
        tree_paths=tree, config_blobs=cb, repository_id=repository_id,
        commit_sha=commit_sha, provenance_level=provenance_level)
    ms = []
    for p in bundle["projects"]:
        if p["discovery_status"] != "PROJECT_CONFIG_VERIFIED":
            continue
        for f in tree:
            if f.endswith((".ts", ".tsx")):
                ms.extend(TPC.build_memberships(
                    project=p, details=bundle["details"], tree_paths=tree,
                    target_files=[f]))
    pr_res = TPI.ingest_project_bundle(store, bundle=bundle, memberships=ms)
    out["project_facts"] = len(pr_res.get("written") or [])
    return out
