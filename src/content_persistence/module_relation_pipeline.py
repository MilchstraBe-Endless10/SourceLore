#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享静态模块关系处理流程（P2-A）。

在线 GitHub 链路与本地 Git 链路复用同一契约：

    已验证源码字节 → 现有解析器 → 导入观察 → 已登记同 Commit Tree
    → 对应语言模块解析器 → 关系证据校验 → module_relation_ingest → 静态关系查询

★ 关键可信性要求：每条关系的三类证据身份严格分离，绝不互相冒充——
  导入方：源码文件自身的 blob / content_asset_id / 真实已落库 import Fact ID / 源码位置；
  配置方：配置文件的 blob / content_asset_id / config_observation_id / 匹配规则；
  目标方：同固定 Commit 的目标路径 / Tree 证据 / 可用时的目标 Blob OID。

★ import_fact_id 必须是 source_fact_ingest 口径下真实落库的 Fact ID，
  不是解析观察内部的 import_id（后者冒充前者是 P2-A 修复的核心缺陷之一）。

★ 不重新开发解析器：源码解析复用 source_dispatch（python_ast / tree-sitter），
  Python 关系复用 local_module_resolver，JS/TS 复用 config_aware_resolver。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "source_analysis", "content_persistence"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import module_config_models as CM
import source_dispatch as SD


# 结果分桶（诚实覆盖，不把缺失伪装成成功）
BUCKETS = (
    "resolved", "ambiguous", "insufficient_tree", "config_missing",
    "config_unresolved", "external", "dynamic", "unsupported", "error",
)


def _lang_of(observation):
    return observation.get("language")


def _module_specifier(imp):
    """统一说明符：Python 用 module_name，JS/TS 用 module_specifier。"""
    return imp.get("module_specifier") or imp.get("module_name")


def _import_kind(imp):
    return (imp.get("import_kind") or imp.get("import_syntax")
            or "unknown")


def _pick_config(configs, file_path, allow_root_config=False):
    """★ 配置归属：就近目录匹配，不把某个 tsconfig 无条件套给所有 TS 文件。

    规则（符合 TypeScript 项目语义）：
      - 配置所在目录必须是导入方文件的目录或其祖先目录；
      - 根配置（config_dir 为空）是仓库根，同样是所有文件的祖先；
      - 多个命中时取目录最深者（就近优先）。
    返回 (tsconfig_observation, config_blob_oids, matched_config_path)。
    """
    if not configs:
        return None, [], None
    file_dir = "/".join(file_path.split("/")[:-1])
    best = None
    for cfg in configs:
        cp = cfg.get("config_path") or ""
        cfg_dir = "/".join(cp.split("/")[:-1])
        # 根配置（cfg_dir 为空）适用于所有文件；子目录配置须是祖先目录
        if cfg_dir:
            if not (file_dir == cfg_dir or file_dir.startswith(cfg_dir + "/")):
                continue
        depth = len(cfg_dir)
        if best is None or depth > best[1]:
            best = (cfg, depth)
    if best is None:
        return None, [], None
    cfg = best[0]
    return cfg, [cfg.get("git_blob_oid")] if cfg.get("git_blob_oid") else [], cfg.get("config_path")


def _in_tree(path, tree):
    """目标路径必须在同 Commit Tree 中（含常见扩展名变体），否则不可作 tree 证据。"""
    if not path:
        return False
    if path in tree:
        return True
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py",
                ".d.ts", "/index.ts", "/index.js", "/index.py"):
        if path + ext in tree:
            return True
    return False


def _normalize(status, candidates, reason, *, tree=None, config_ids,
               config_blob_oids, matched_field, matched_path, matched_rule,
               policy, condition_candidates=None):
    cands = list(candidates or [])
    target = None
    if status == CM.LOCAL_MODULE_RESOLVED and cands:
        first = cands[0]
        candidate = first.get("path") if isinstance(first, dict) else first
        # ★ 只有经 Tree 证实的目标才能成为 resolved_target_path。
        if tree is None or _in_tree(candidate, tree):
            target = candidate
        else:
            status = CM.CONFIG_MAPPING_CANDIDATE
            reason = "TARGET_NOT_IN_TREE"
    # 兼容两种候选形态：Python resolver 给 dict{path,...}，config_aware 给路径字符串
    paths = []
    for c in cands:
        p = c.get("path") if isinstance(c, dict) else c
        if p and p not in paths:
            paths.append(p)
    return {
        "resolution_state": status,
        "candidate_paths": paths,
        "resolved_target_path": target,
        "unresolved_reason": reason,
        "config_observation_ids": list(config_ids or []),
        "config_blob_oids": list(config_blob_oids or []),
        "matched_config_field": matched_field,
        "matched_config_path": matched_path,
        "matched_config_rule": matched_rule,
        "resolution_policy": policy,
        "condition_candidates": list(condition_candidates or []),
    }


def _resolve_python(imp, file_path, tree, completeness):
    import local_module_resolver as LR
    r = LR.resolve_import(import_record=imp, source_path=file_path,
                          tree_paths=tree, source_completeness=completeness)
    return _normalize(
        r.get("status"), r.get("candidates"), r.get("reason"),
        tree=tree,
        config_ids=[], config_blob_oids=[],
        matched_field=None, matched_path=None, matched_rule=None,
        policy="local-module/1")


def _resolve_js_ts(imp, file_path, tree, completeness, cfg,
                   config_blob_oids, matched_path, allow_relative=True):
    import config_aware_resolver as RZ
    r = RZ.resolve_with_config(
        specifier=_module_specifier(imp),
        importing_file_path=file_path,
        tree_paths=tree,
        tsconfig_observation=cfg,
        import_kind=_import_kind(imp),
        is_type_only=bool(imp.get("is_type_only")),
        source_completeness=completeness,
        resolve_relative=allow_relative)
    return _normalize(
        r.get("resolution_state"), r.get("candidate_paths"),
        r.get("unresolved_reason"),
        tree=tree,
        config_ids=r.get("config_observation_ids") or [],
        config_blob_oids=config_blob_oids,
        matched_field=r.get("matched_config_field"),
        matched_path=matched_path or r.get("matched_config_path"),
        matched_rule=r.get("matched_config_rule"),
        policy=r.get("resolution_policy") or "config-aware/1",
        condition_candidates=r.get("condition_candidates"))


def build_config_observations(*, repository_id, commit_sha, config_sources,
                              provenance_level):
    """从已捕获配置字节构造配置观察（在线/本地共用，零网络）。

    config_sources: [{config_path, raw, blob_oid, content_asset_id,
                      content_digest, config_kind?}]
    返回 (observations_for_resolver, ingest_fn_ready_observations)。
    """
    import tsconfig_parser as TP
    import module_config_models as CM

    out = []
    for cs in config_sources or []:
        cfg_path = cs["config_path"]
        name = cfg_path.rsplit("/", 1)[-1]
        if name not in ("tsconfig.json", "jsconfig.json"):
            continue
        pr = TP.parse_tsconfig(cs["raw"], config_path=cfg_path)
        if not pr.get("ok"):
            continue
        config_dir = "/".join(cfg_path.split("/")[:-1])
        surf = TP.extract_config_surface(pr["data"], config_dir=config_dir)
        kind = cs.get("config_kind") or (
            CM.CONFIG_JSCONFIG if name == "jsconfig.json" else CM.CONFIG_TSCONFIG)
        cfg = CM.build_config_observation(
            repository_id=repository_id, commit_sha=commit_sha,
            config_path=cfg_path, config_kind=kind,
            git_blob_oid=cs["blob_oid"],
            content_asset_id=cs["content_asset_id"],
            content_digest=cs["content_digest"],
            effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED,
            declared_paths=surf.get("paths"),
            declared_base_url=surf.get("base_url"),
            declared_references=surf.get("references"),
            provenance_level=provenance_level)
        # resolver 需要 _base_dir/_config_dir 上下文（沿用既有调用契约）
        cfg = dict(cfg, _base_dir=TP.resolve_base_dir(
            config_dir=config_dir, base_url=surf.get("base_url")),
            _config_dir=config_dir)
        out.append(cfg)
    return out


def _bucket_for(state, reason):
    if state == CM.LOCAL_MODULE_RESOLVED:
        return "resolved"
    if state == CM.AMBIGUOUS_CANDIDATES:
        return "ambiguous"
    if state == CM.INSUFFICIENT_TREE_COVERAGE:
        return "insufficient_tree"
    if state in (CM.CONFIG_NOT_CAPTURED, CM.CONFIG_CONTENT_NOT_CAPTURED):
        return "config_missing"
    if state.startswith("CONFIG_"):
        return "config_unresolved"
    if state == CM.DYNAMIC_SPECIFIER:
        return "dynamic"
    if state in (CM.UNSUPPORTED_RESOLUTION_POLICY, "UNSUPPORTED_IMPORT_FORM"):
        return "unsupported"
    if state == CM.EXTERNAL_OR_UNRESOLVED:
        return "external"
    return "error"


def process_source_relations(store, *, repository_id, commit_sha,
                             file_sources, tree_paths, config_sources=None,
                             configs=None, tree_blob_map=None,
                             source_completeness="COMPLETE",
                             provenance_level="SYNTHETIC_FIXTURE",
                             source_snapshot_id=None,
                             allow_root_config=False):
    """处理一批已验证源码字节的静态模块关系（幂等，可重复/增量）。

    file_sources: [{file_path, raw, git_blob_oid, content_asset_id, content_sha256}]
    config_sources: [{config_path, raw, blob_oid, content_asset_id,
                      content_digest}] —— 已捕获配置字节，在线/本地均以同一形状传入。
                    组件内部据此构造并入库配置观察；无配置时传 None/[]。
    configs: 可直接传入的 config observation 列表（高级用法，优先于 config_sources）。
    tree_blob_map: {path: blob_oid}，用于记录目标 Blob（可用时）。

    返回 {written, reused, skipped, resolutions, outcomes, counts,
          config_observations_ingested}。
    """
    import module_relation_ingest as MRI
    import source_fact_ingest as SFI

    tree = set(tree_paths or [])
    tree_blob_map = dict(tree_blob_map or {})
    written, reused, skipped, resolutions = [], [], [], []
    outcomes = {b: 0 for b in BUCKETS}

    # ★ 配置观察统一在本组件内构造并入库，杜绝"配置文件冒充源码文件"。
    configs = list(configs or [])
    config_facts = {"written": 0, "reused": 0}
    if not configs and config_sources:
        configs = build_config_observations(
            repository_id=repository_id, commit_sha=commit_sha,
            config_sources=config_sources, provenance_level=provenance_level)
        for cfg in configs:
            cr = MRI.ingest_config_observation(store, observation=cfg)
            config_facts["written"] += len(cr.get("written") or [])
            config_facts["reused"] += len(cr.get("reused") or [])

    # ★ TS 项目事实也在共享组件内统一处理（在线/本地一致，零网络）。
    project_facts = {"written": 0, "reused": 0, "status": "NOT_APPLICABLE"}
    if configs:
        try:
            import ts_project_context as TPC
            import ts_project_ingest as TPI
            cb = {}
            for cfg in configs:
                cp = cfg["config_path"]
                cb[cp] = {
                    "raw": None,
                    "blob_oid": cfg.get("git_blob_oid"),
                    "content_asset_id": cfg.get("content_asset_id"),
                    "content_digest": cfg.get("content_digest"),
                    "_observation": cfg,
                }
            # 用已捕获原始配置字节重建（若调用方提供 config_sources）
            for cs in config_sources or []:
                cp = cs["config_path"]
                if cp in cb:
                    cb[cp]["raw"] = cs["raw"]
            usable = {k: v for k, v in cb.items() if v.get("raw") is not None}
            if usable:
                bundle = TPC.build_all_projects(
                    tree_paths=tree, config_blobs=usable,
                    repository_id=repository_id, commit_sha=commit_sha,
                    provenance_level=provenance_level)
                memberships = []
                for p in bundle.get("projects") or []:
                    if p.get("discovery_status") != "PROJECT_CONFIG_VERIFIED":
                        continue
                    for f in tree:
                        if f.endswith((".ts", ".tsx")):
                            memberships.extend(TPC.build_memberships(
                                project=p, details=bundle.get("details"),
                                tree_paths=tree, target_files=[f]))
                pr_res = TPI.ingest_project_bundle(
                    store, bundle=bundle, memberships=memberships)
                project_facts["written"] = len(pr_res.get("written") or [])
                project_facts["reused"] = len(pr_res.get("reused") or [])
                project_facts["status"] = "INGESTED"
        except Exception as exc:
            project_facts["status"] = f"ERROR:{type(exc).__name__}:{exc}"

    for src in file_sources:
        fp = src["file_path"]
        # 复用现有解析器；不重新开发 AST / tree-sitter。
        obs = SD.parse_source(
            src["raw"], repository_id=repository_id, commit_sha=commit_sha,
            file_path=fp, git_blob_oid=src["git_blob_oid"],
            content_asset_id=src["content_asset_id"],
            content_sha256=src["content_sha256"],
            provenance_level=provenance_level)
        if obs.get("extraction_status") != "EXTRACTED":
            outcomes["error"] += len(obs.get("observed_imports") or [])
            skipped.append({"reason": "SOURCE_NOT_PARSED",
                            "file_path": fp,
                            "status": obs.get("extraction_status")})
            continue

        # ★ 先把导入观察按正式 Fact 框架落库，确保 import_fact_id 真实可回查。
        SFI.ingest_source_facts(store, observation=obs,
                                source_snapshot_id=source_snapshot_id)

        lang = _lang_of(obs)
        cfg, cfg_blob_oids, matched_path = _pick_config(
            configs, fp, allow_root_config=allow_root_config)

        for imp in obs.get("observed_imports") or []:
            try:
                if lang == "python":
                    r = _resolve_python(imp, fp, tree, source_completeness)
                elif lang in ("javascript", "typescript"):
                    r = _resolve_js_ts(imp, fp, tree, source_completeness,
                                       cfg, cfg_blob_oids, matched_path)
                else:
                    r = _normalize(
                        "UNSUPPORTED_RESOLUTION_POLICY", [],
                        "UNSUPPORTED_LANGUAGE", config_ids=[],
                        config_blob_oids=[], matched_field=None,
                        matched_path=None, matched_rule=None,
                        policy="none")
            except Exception as exc:  # 解析异常不得伪造为已解析
                outcomes["error"] += 1
                skipped.append({"file_path": fp,
                                "reason": f"RESOLVER_ERROR:{type(exc).__name__}:{exc}"})
                continue

            bucket = _bucket_for(r["resolution_state"], r["unresolved_reason"])
            outcomes[bucket] += 1

            # ★ 导入方真实 Fact ID（不是观察内部 import_id）。
            import_fact_id = SFI.make_import_fact_id(observation=obs, imp=imp)
            spec = _module_specifier(imp)
            target = r["resolved_target_path"]

            # ★ 三类证据分离：导入方源码身份 / 配置方身份 / 目标 Tree 身份。
            ev = [f"import:{import_fact_id}"]
            ev += [f"config:{c}" for c in r["config_observation_ids"]]
            if target:
                ev.append(f"tree:{target}")
            ev.append(f"source:{src['content_asset_id']}")

            resolution = CM.build_resolution_observation(
                repository_id=repository_id, commit_sha=commit_sha,
                importing_file_path=fp,
                importing_blob_oid=src["git_blob_oid"],
                importing_content_asset_id=src["content_asset_id"],
                import_fact_id=import_fact_id,
                module_specifier=spec,
                import_kind=_import_kind(imp),
                is_type_only=bool(imp.get("is_type_only")),
                config_observation_ids=r["config_observation_ids"],
                config_blob_oids=r["config_blob_oids"],
                resolution_policy=r["resolution_policy"],
                matched_config_rule=r["matched_config_rule"],
                matched_config_field=r["matched_config_field"],
                matched_config_path=r["matched_config_path"],
                candidate_paths=r["candidate_paths"],
                resolved_target_path=target,
                resolved_target_blob_oid=tree_blob_map.get(target),
                resolution_state=r["resolution_state"],
                evidence_refs=ev,
                provenance_level=provenance_level,
                condition_candidates=r["condition_candidates"],
                unresolved_reason=r["unresolved_reason"])

            resolutions.append({
                "resolution_id": resolution["resolution_id"],
                "importing_file_path": fp,
                "importing_blob_oid": src["git_blob_oid"],
                "importing_content_asset_id": src["content_asset_id"],
                "import_fact_id": import_fact_id,
                "module_specifier": spec,
                "resolution_state": resolution["resolution_state"],
                "unresolved_reason": resolution["unresolved_reason"],
                "config_observation_ids": resolution["config_observation_ids"],
                "config_blob_oids": resolution["config_blob_oids"],
                "matched_config_path": resolution["matched_config_path"],
                "resolved_target_path": target,
                "resolved_target_blob_oid": tree_blob_map.get(target),
                "candidate_paths": resolution["candidate_paths"],
                "evidence_refs": ev,
                "bucket": bucket,
            })

            rr = MRI.ingest_resolution(
                store, resolution=resolution, evidence_refs=ev,
                source_snapshot_id=source_snapshot_id)
            written.extend(rr.get("written") or [])
            reused.extend(rr.get("reused") or [])
            skipped.extend(rr.get("skipped") or [])
            # ★ 未解析状态不伪造权威事实，但留可回查审计（供查询端诚实回答）。
            if bucket != "resolved":
                MRI.ingest_unresolved_attempt(
                    store, resolution=resolution, evidence_refs=ev)

    return {
        "written": written, "reused": reused, "skipped": skipped,
        "resolutions": resolutions, "outcomes": outcomes,
        "config_observations_ingested": config_facts,
        "project_facts": project_facts,
        "counts": {
            "written": len(written), "reused": len(reused),
            "skipped": len(skipped), "resolutions": len(resolutions),
            "observed_imports": sum(outcomes.values()),
            "config_facts_written": config_facts["written"],
            "config_facts_reused": config_facts["reused"],
            "project_facts_written": project_facts["written"],
            "project_facts_reused": project_facts["reused"],
        },
        "network_requests": 0,
        "limitations": [
            "静态模块映射 ≠ 运行时模块加载成功",
            "未解析状态不等于已证实无依赖",
            "根目录 tsconfig 默认不自动适用于所有 TS 文件",
        ],
    }
