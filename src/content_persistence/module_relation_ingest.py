#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置观察与模块关系事实入库。★ 复用既有 Facts 框架，不建第二套。"""

import hashlib, json, sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "source_analysis", "content_persistence"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

RULE_CONFIG_PATHS = "MODULE_CONFIG_PATHS_DECLARED"
RULE_CONFIG_IMPORTS = "MODULE_CONFIG_IMPORTS_DECLARED"
RULE_CONFIG_EXPORTS = "MODULE_CONFIG_EXPORTS_DECLARED"
RULE_RELATION = "STATIC_MODULE_RELATION"
RULE_VERSION = "module-config/1"

OBSERVED = "OBSERVED_PRESENT"


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def make_fact_id(*, observation_id, rule_id, subject):
    payload = f"{observation_id}|{rule_id}|{RULE_VERSION}|{_canon(subject)}"
    return "SL-FACT-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def build_config_fact(*, observation, rule_id, subject, evidence_label):
    import models as FM
    fid = make_fact_id(observation_id=observation["config_observation_id"],
                       rule_id=rule_id, subject=subject)
    np = {
        "config_path": observation["config_path"],
        "config_kind": observation["config_kind"],
        "git_blob_oid": observation["git_blob_oid"],
        "content_asset_id": observation["content_asset_id"],
        "content_digest": observation["content_digest"],
        "parser_id": observation["parser_id"],
        "parser_version": observation["parser_version"],
        "config_observation_id": observation["config_observation_id"],
        "subject": subject,
        "evidence_label": evidence_label,
        "module_resolution_mode": observation.get("module_resolution_mode"),
        "effective_config_status": observation.get("effective_config_status"),
    }
    item_key = f"{observation['config_path']}:{rule_id}:{_canon(subject)}"
    fact = FM.FactObservation(
        fact_id=fid, fact_type="module_resolution_config",
        observation=OBSERVED,
        repository_id=str(observation["repository_id"]),
        snapshot_asset_id="", snapshot_logical_identity="SL-SNAP-src",
        commit_sha=str(observation["commit_sha"]),
        rule_id=rule_id, rule_version=RULE_VERSION,
        normalized_parameters=np, item_key=item_key,
        observed_value=dict(subject, **{
            "config_path": observation["config_path"],
            "git_blob_oid": observation["git_blob_oid"],
            "content_asset_id": observation["content_asset_id"],
            "content_digest": observation["content_digest"],
            "parser_version": observation["parser_version"],
            "provenance_level": observation["provenance_level"],
        }),
        completeness_status="COMPLETE",
        evidence_refs=[f"module_config:{observation['content_asset_id']}"],
        input_digest=FM.make_input_digest(
            snapshot_logical_identity="SL-SNAP-src",
            snapshot_content_hash=observation["content_digest"],
            rule_id=rule_id, rule_version=RULE_VERSION,
            normalized_parameters=np, item_key=item_key),
        content_hash=FM.make_content_hash(
            observation=OBSERVED,
            observed_value=dict(subject, config_digest=observation["content_digest"]),
            unknown_reason=None, commit_sha=str(observation["commit_sha"]),
            completeness_status="COMPLETE"),
        extractor_version=observation["parser_version"])
    return fact


def build_relation_fact(*, resolution, evidence_refs, source_snapshot_id=None):
    """静态模块关系事实。★ 只对确定状态产地权威事实。"""
    import models as FM
    subject = {
        "importing_file_path": resolution["importing_file_path"],
        "module_specifier": resolution["module_specifier"],
        "import_kind": resolution["import_kind"],
        "is_type_only": resolution["is_type_only"],
        "resolved_target_path": resolution.get("resolved_target_path"),
        "matched_config_rule": resolution.get("matched_config_rule"),
        "resolution_state": resolution["resolution_state"],
        "resolution_policy": resolution["resolution_policy"],
    }
    obs_id = resolution["resolution_id"]
    fid = make_fact_id(observation_id=obs_id, rule_id=RULE_RELATION,
                       subject=subject)
    # ★ 必须显式挂 subject 键：查询与裁决都读 np["subject"]
    np = dict(subject, **{
        "subject": subject,
        "resolution_id": obs_id,
        "import_fact_id": resolution.get("import_fact_id"),
        "config_observation_ids": resolution.get("config_observation_ids") or [],
        "config_blob_oids": resolution.get("config_blob_oids") or [],
        "candidate_paths": resolution.get("candidate_paths") or [],
        "importing_blob_oid": resolution.get("importing_blob_oid"),
        "importing_content_asset_id": resolution.get("importing_content_asset_id"),
        "matched_config_field": resolution.get("matched_config_field"),
        "matched_config_path": resolution.get("matched_config_path"),
        "condition_candidates": resolution.get("condition_candidates") or [],
        "resolver_version": resolution.get("resolver_version"),
        "unresolved_reason": resolution.get("unresolved_reason"),
    })
    item_key = (f"{resolution['importing_file_path']}:"
                f"{resolution['module_specifier']}:{_canon(subject)}")
    fact = FM.FactObservation(
        fact_id=fid, fact_type="static_module_resolution",
        observation=OBSERVED,
        repository_id=str(resolution["repository_id"]),
        snapshot_asset_id=source_snapshot_id or "",
        snapshot_logical_identity="SL-SNAP-src",
        commit_sha=str(resolution["commit_sha"]),
        rule_id=RULE_RELATION, rule_version=RULE_VERSION,
        normalized_parameters=np, item_key=item_key,
        observed_value=dict(subject, **{
            "config_observation_ids": resolution.get("config_observation_ids") or [],
            "config_blob_oids": resolution.get("config_blob_oids") or [],
            "resolver_version": resolution.get("resolver_version"),
            "provenance_level": resolution.get("provenance_level"),
        }),
        completeness_status="COMPLETE",
        evidence_refs=list(evidence_refs),
        input_digest=FM.make_input_digest(
            snapshot_logical_identity="SL-SNAP-src",
            snapshot_content_hash=_canon({
                "config": sorted(resolution.get("config_observation_ids") or []),
                "import": resolution.get("import_fact_id"),
                "target": resolution.get("resolved_target_path")}),
            rule_id=RULE_RELATION, rule_version=RULE_VERSION,
            normalized_parameters=np, item_key=item_key),
        content_hash=FM.make_content_hash(
            observation=OBSERVED, observed_value=subject, unknown_reason=None,
            commit_sha=str(resolution["commit_sha"]),
            completeness_status="COMPLETE"),
        extractor_version=resolution.get("resolver_version") or RULE_VERSION)
    return fact


def ingest_config_observation(store, *, observation):
    """入库配置观察产出的事实。"""
    import ingest as FI
    written, reused, skipped = [], [], []

    def _put(rule_id, subject, label="config"):
        fact = build_config_fact(observation=observation, rule_id=rule_id,
                                 subject=subject, evidence_label=label)
        prev = store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
            "AND logical_identity=?", (fact.fact_id,)).fetchone()
        if prev:
            reused.append({"fact_id": fact.fact_id, "rule_id": rule_id})
            return
        res = FI.ingest_fact(store, fact)
        if res.get("ok"):
            written.append({"fact_id": fact.fact_id, "rule_id": rule_id,
                            "asset_id": res.get("asset_id")})
        else:
            skipped.append({"rule_id": rule_id,
                            "reason": res.get("error") or res.get("detail")})

    for rule in observation.get("declared_paths") or []:
        _put(RULE_CONFIG_PATHS,
             {"pattern": rule["pattern"], "targets": list(rule["targets"])},
             f"paths:{rule['pattern']}")

    for k, v in (observation.get("declared_imports") or {}).items():
        _put(RULE_CONFIG_IMPORTS,
             {"specifier_pattern": k,
              "target_kind": type(v).__name__},
             f"imports:{k}")

    exps = observation.get("declared_exports")
    if isinstance(exps, dict):
        for k in exps:
            _put(RULE_CONFIG_EXPORTS, {"subpath": k}, f"exports:{k}")

    return {"written": written, "reused": reused, "skipped": skipped}


def ingest_resolution(store, *, resolution, evidence_refs,
                      source_snapshot_id=None, only_resolved=True):
    """入库静态关系事实。★ 只有确定状态才产权威事实。"""
    import ingest as FI
    if only_resolved:
        if resolution["resolution_state"] != "LOCAL_MODULE_RESOLVED":
            return {"written": [], "reused": [], "skipped": [{
                "reason": "NOT_RESOLVED",
                "state": resolution["resolution_state"]}]}
    if not evidence_refs:
        return {"written": [], "reused": [], "skipped": [
            {"reason": "EVIDENCE_EMPTY"}]}

    fact = build_relation_fact(resolution=resolution,
                              evidence_refs=evidence_refs,
                              source_snapshot_id=source_snapshot_id)
    prev = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
        "AND logical_identity=?", (fact.fact_id,)).fetchone()
    if prev:
        return {"written": [], "reused": [{"fact_id": fact.fact_id}],
                "skipped": []}
    res = FI.ingest_fact(store, fact)
    if res.get("ok"):
        return {"written": [{"fact_id": fact.fact_id,
                             "asset_id": res.get("asset_id")}],
                "reused": [], "skipped": []}
    return {"written": [], "reused": [], "skipped": [
        {"reason": res.get("error") or res.get("detail")}]}
