#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态模块关系只读查询。★ 纯本地、零网络、不写库。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "source_analysis", "content_persistence",
           "skill_interface"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

STATE_FOUND = "RELATIONS_FOUND"
STATE_NONE = "NO_RELATIONS"
STATE_NOT_ANALYZED = "SOURCE_NOT_ANALYZED"


def query_relations(*, repository_id, commit_sha=None, importing_file_path=None,
                    module_specifier=None, limit=200, data_root=None):
    """查询静态模块关系事实。"""
    from knowledge_store import KnowledgeStore
    from paths import db_path, DEFAULT_DATA_ROOT

    root = data_root or DEFAULT_DATA_ROOT
    p = db_path(root)
    if not p.exists():
        return _shell(repository_id, commit_sha, importing_file_path,
                      module_specifier, "REPOSITORY_NOT_REGISTERED",
                      "知识库未建立")

    store = KnowledgeStore(str(p), create=False)
    try:
        rows = store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
            "AND repository_id=?", (str(repository_id),)).fetchall()
        if not rows:
            return _shell(repository_id, commit_sha, importing_file_path,
                          module_specifier, "REPOSITORY_NOT_REGISTERED",
                          "该仓库从未登记")

        relations, configs = [], []
        for r in rows:
            got = store.get_asset(r["asset_id"], verify=True)
            if not got.get("ok"):
                continue
            pl = (got["asset"] or {}).get("payload") or {}
            ftype = pl.get("fact_type")
            np = pl.get("normalized_parameters") or {}
            if commit_sha and pl.get("commit_sha") != str(commit_sha):
                continue

            if ftype == "static_module_resolution":
                subj = np.get("subject") or {}
                if importing_file_path and \
                        subj.get("importing_file_path") != importing_file_path:
                    continue
                if module_specifier and \
                        subj.get("module_specifier") != module_specifier:
                    continue
                relations.append(_relation_row(pl, np, subj, r["asset_id"]))
            elif ftype == "module_resolution_config":
                configs.append(_config_row(pl, np))

        if not relations:
            st = dict(_shell(repository_id, commit_sha, importing_file_path,
                             module_specifier, STATE_NONE, "无静态模块关系"),
                      configs=configs)
            return st

        return {
            "state": STATE_FOUND,
            "repository_id": str(repository_id),
            "commit_sha": commit_sha,
            "importing_file_path": importing_file_path,
            "module_specifier": module_specifier,
            "relations": relations[:limit],
            "configs": configs,
            "counts": {"relations": len(relations),
                       "resolved": sum(1 for x in relations
                                       if x["resolution_state"]
                                       == "LOCAL_MODULE_RESOLVED"),
                       "configs": len(configs)},
            "network_requests": 0,
            "limitations": [
                "静态模块映射 ≠ 运行时模块加载成功",
                "tsconfig.paths 不自动改写输出代码的导入路径",
                "未验证构建或运行",
            ],
            "distribution_restrictions": {"distribution_allowed": False,
                                          "copy_permitted": False},
        }
    finally:
        store.close()


def _relation_row(pl, np, subj, asset_id):
    # ★ 必须带 rule_id：裁决端的第一道检查就是它
    return {
        "fact_id": pl.get("fact_id"),
        "asset_id": asset_id,
        "rule_id": pl.get("rule_id"),
        "rule_version": pl.get("rule_version"),
        "repository_id": str(pl.get("repository_id") or ""),
        "resolution_id": np.get("resolution_id"),
        "importing_file_path": subj.get("importing_file_path"),
        "module_specifier": subj.get("module_specifier"),
        "import_kind": subj.get("import_kind"),
        "is_type_only": subj.get("is_type_only"),
        "resolution_state": subj.get("resolution_state"),
        "resolution_policy": subj.get("resolution_policy"),
        "matched_config_rule": subj.get("matched_config_rule"),
        "matched_config_field": np.get("matched_config_field"),
        "matched_config_path": np.get("matched_config_path"),
        "config_observation_ids": np.get("config_observation_ids") or [],
        "config_blob_oids": np.get("config_blob_oids") or [],
        "candidate_paths": np.get("candidate_paths") or [],
        "resolved_target_path": subj.get("resolved_target_path"),
        "import_fact_id": np.get("import_fact_id"),
        "importing_blob_oid": np.get("importing_blob_oid"),
        "importing_content_asset_id": np.get("importing_content_asset_id"),
        "condition_candidates": np.get("condition_candidates") or [],
        "unresolved_reason": np.get("unresolved_reason"),
        "resolver_version": np.get("resolver_version"),
        "commit_sha": pl.get("commit_sha"),
        "evidence_refs": pl.get("evidence_refs") or [],
        "limitations": ["静态映射 ≠ 运行时加载"],
    }


def _config_row(pl, np):
    return {
        "fact_id": pl.get("fact_id"),
        "config_path": np.get("config_path"),
        "config_kind": np.get("config_kind"),
        "git_blob_oid": np.get("git_blob_oid"),
        "content_asset_id": np.get("content_asset_id"),
        "config_observation_id": np.get("config_observation_id"),
        "rule_id": pl.get("rule_id"),
        "subject": np.get("subject"),
        "module_resolution_mode": np.get("module_resolution_mode"),
    }


def _shell(repository_id, commit_sha, path, spec, state, note):
    return {"state": state, "note": note,
            "repository_id": str(repository_id), "commit_sha": commit_sha,
            "importing_file_path": path, "module_specifier": spec,
            "relations": [], "configs": [],
            "counts": {"relations": 0, "resolved": 0, "configs": 0},
            "network_requests": 0, "limitations": [note]}
