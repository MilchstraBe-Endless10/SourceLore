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
    source_entries, config_entries = [], []
    captured_meta = {}  # file_path → 完整身份（供共享关系组件使用）
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

        # ★ 内容命题 + 验证：内容事实必须有自己的 Claim/Verification，
        #   否则查询会（正确地）判 INSUFFICIENT_EVIDENCE —— P6A 只建了路径命题。
        content_claims = _build_content_claims(
            store, repository_id=repository_id, commit_sha=commit_sha,
            file_path=path, extraction=fr, facts=ex.get("facts") or [],
            snapshot_asset_id=snapshot_asset_id, evidence_refs=[])

        results.append({
            "file_path": path,
            "status": "EXTRACTED",
            "content_claims": content_claims,
            "content_asset_id": ing["content_asset_id"],
            "content_sha256": ing["content_sha256"],
            "facts": len(fr.get("written") or []),
            "reused": len(fr.get("reused") or []),
            "struct_facts": struct_facts,
            "struct_status": struct_status,
        })

        # ★ 收集到统一输入：配置与源码分别登记，身份不混用。
        identity = {
            "git_blob_oid": sha,
            "content_asset_id": ing["content_asset_id"],
            "content_sha256": ing["content_sha256"],
        }
        captured_meta[path] = identity
        name = path.rsplit("/", 1)[-1]
        if name in ("tsconfig.json", "jsconfig.json"):
            config_entries.append({
                "config_path": path, "raw": raw,
                "blob_oid": sha,
                "content_asset_id": ing["content_asset_id"],
                "content_digest": ing["content_sha256"],
            })
        elif struct_status == "EXTRACTED":
            source_entries.append({
                "file_path": path, "raw": raw,
                "git_blob_oid": sha,
                "content_asset_id": ing["content_asset_id"],
                "content_sha256": ing["content_sha256"],
            })

    # ★ 本地链路接入共享关系组件（在线/本地同一契约，零网络）。
    relation_report = {"written": 0, "reused": 0, "resolutions": 0,
                       "status": "NOT_RUN"}
    if source_entries or config_entries:
        try:
            import module_relation_pipeline as MRP
            relation_report = MRP.process_source_relations(
                store, repository_id=repository_id, commit_sha=commit_sha,
                file_sources=source_entries,
                config_sources=config_entries,
                tree_paths=set(blobs),
                source_snapshot_id=snapshot_asset_id,
                provenance_level=provenance_level)
        except Exception as e:
            relation_report = {"status": f"ERROR:{type(e).__name__}:{e}"}
    # 附在首个真实文件结果上，避免被 analyze.py 误计为"跳过的文件"。
    if results and relation_report.get("status") != "NOT_RUN":
        results[0]["relation"] = relation_report
    return results


def _ingest_config_observation(store, *, repository_id, commit_sha,
                               config_path, raw, blob_oid, content_asset_id,
                               content_digest, provenance_level):
    """仅生成配置观察事实（共享关系流程会按路径复用它）。"""
    import tsconfig_parser as TP
    import module_config_models as CM
    import module_relation_ingest as MRI
    import tsconfig_expansion as EC

    out = {"config_facts": 0}
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
    out["config_observation_id"] = cfg_obs["config_observation_id"]
    return out


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


def _build_content_claims(store, *, repository_id, commit_sha, file_path,
                          extraction, facts, snapshot_asset_id, evidence_refs):
    """为内容事实建立命题与验证。

    ★ build_content_claim 返回 (claim, subject_binding)，裁决必须用
      verify_content_claim 并显式传 subject_binding —— Claim 模型不存它。
    """
    import ec_models as M
    import content_claim_adapter as CCA
    import content_claim_ingest as CCI

    written = extraction.get("written") or []
    out = {"claims": 0, "verifications": 0, "ids": [], "errors": []}
    if not written:
        return out

    # 一个文件只建一条主命题（同类同主体去重）
    # ★ 直接用**已入库事实自身**的 subject 建组 —— 不依赖 written/原始 facts 的 subject，
    #   它们是两种不同对象，id 与字段都不保证对齐（D-49）。
    import content_knowledge_query as _CKQ
    stored = _CKQ.query_content_facts(
        store=store, repository_id=repository_id,
        commit_sha=commit_sha, file_path=file_path, limit=500)
    groups = {}
    for f in stored:
        rid = f.get("rule_id") or ""
        subj = f.get("subject") or {}
        w = {"fact_id": f.get("fact_id")}
        if rid not in ("README_HEADING_EXISTS", "MANIFEST_DEPENDENCY_DECLARED",
                       "MANIFEST_FIELD_PRESENT"):
            continue
        # ★ 不要在这里重新取 rid：w 只有 fact_id，会把 rid 覆盖成空串，
        #   导致下面所有分支都落进 else: continue（D-50，静默零命题）。

        if rid == "README_HEADING_EXISTS":
            ctype = M.CLAIM_README_HEADING
            # ★ 用事实自身的 level，不硬编码 1 —— 否则只有一级标题能命中
            csubj = {"level": subj.get("level")}
        elif rid == "MANIFEST_DEPENDENCY_DECLARED":
            ctype = M.CLAIM_MANIFEST_DEP
            csubj = {"dependency_name": subj.get("dependency_name"),
                     "dependency_scope": subj.get("dependency_scope")}
        elif rid == "MANIFEST_FIELD_PRESENT":
            ctype = M.CLAIM_MANIFEST_FIELD
            csubj = {"field_name": subj.get("field_name")}
        else:
            continue
        # ★ 每个 (类型, 主体) 组合独立成组；标题按 level+title 归组，
        #   避免不同标题挤进同一组后只拿第一条事实去裁决。
        if ctype == M.CLAIM_README_HEADING:
            key = (ctype, repr(sorted((k, str(v)) for k, v in csubj.items())),
                   str(subj.get("title")))
        else:
            key = (ctype, repr(sorted((k, str(v)) for k, v in csubj.items())))
        groups.setdefault(key, {"ctype": ctype, "csubject": csubj,
                                "fids": [], "hashes": []})
        groups[key]["fids"].append(w.get("fact_id"))
        groups[key]["hashes"].append(w.get("content_hash"))

    for key, g in groups.items():
        try:
            claim, binding = CCA.build_content_claim(
                claim_type=g["ctype"], repository_id=repository_id,
                commit_sha=commit_sha, file_path=file_path,
                subject=g["csubject"], expected_present=True,
                claim_origin="skill_analyze_content")
            # ★ 必须传**真实事实对象**（rule_id/normalized_parameters/
            #   commit_sha/repository_id），否则 _matches 一律 False ——
            #   这正是"逻辑存在但事实没传对"的静默失败。
            real_facts = stored
            pick = [f for f in real_facts
                    if f.get("rule_id") == CCA._rule_of(g["ctype"])] or real_facts
            verdict = CCA.verify_content_claim(
                claim=claim, facts=pick,
                content_available=True, completeness_status="COMPLETE",
                parser_ok=True, subject_binding=binding)
            if verdict.get("status") != "supported":
                # ★ 带上第一条候选事实的关键字段，便于定位契约差异
                probe = {}
                if pick:
                    f0 = pick[0]
                    np0 = f0.get("normalized_parameters") or {}
                    probe = {"rule": f0.get("rule_id"),
                             "np_file": np0.get("file_path"),
                             "np_subj": np0.get("subject"),
                             "commit": str(f0.get("commit_sha"))[:12],
                             "repo": f0.get("repository_id")}
                out["errors"].append(
                    f"NOT_SUPPORTED {g['ctype']}: {verdict.get('reason_code')} "
                    f"(候选 {len(pick)}/{len(real_facts)}) bind={binding} "
                    f"claim_commit={str(commit_sha)[:12]} "
                    f"claim_repo={repository_id} probe={probe}")
                continue
            r = CCI.ingest_content_claim(
                store, claim=claim, verdict=verdict,
                facts_payload=[{"content_hash": h} for h in g["hashes"]],
                repository_id=repository_id, evidence_refs=evidence_refs)
            if r.get("ok"):
                out["claims"] += 1
                out["verifications"] += 1
                out["ids"].append({"claim_id": r["claim_id"],
                                   "verification_id": r["verification_id"],
                                   "status": r["status"]})
            else:
                out["errors"].append(f"{r.get('stage')}: {r.get('error')}")
        except Exception as e:
            out["errors"].append(f"{type(e).__name__}: {e}")
    return out
