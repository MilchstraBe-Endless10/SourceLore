#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TS 项目 / 引用 / 归属 事实入库。★ 复用既有 Facts 框架。"""

import hashlib, json, sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "source_analysis", "content_persistence"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

RULE_PROJECT = "TSCONFIG_PROJECT_DECLARED"
RULE_REFERENCE = "TSCONFIG_PROJECT_REFERENCE_DECLARED"
RULE_MEMBERSHIP = "TSCONFIG_FILE_SELECTION_OBSERVED"
RULE_VERSION = "ts-project/1"

OBSERVED = "OBSERVED_PRESENT"


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def make_fact_id(*, observation_id, rule_id, subject):
    payload = f"{observation_id}|{rule_id}|{RULE_VERSION}|{_canon(subject)}"
    return "SL-FACT-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def _put(store, *, fact_id, fact_type, obs, rule_id, subject, np,
         evidence_refs, snapshot_identity="SL-SNAP-src"):
    import models as FM
    import ingest as FI
    prev = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
        "AND logical_identity=?", (fact_id,)).fetchone()
    if prev:
        return {"written": False, "reused": True, "fact_id": fact_id}
    item_key = f"{obs['repository_id']}:{obs['commit_sha']}:{_canon(subject)}"
    np = dict(np, subject=subject)
    fact = FM.FactObservation(
        fact_id=fact_id, fact_type=fact_type, observation=OBSERVED,
        repository_id=str(obs["repository_id"]),
        snapshot_asset_id="", snapshot_logical_identity=snapshot_identity,
        commit_sha=str(obs["commit_sha"]),
        rule_id=rule_id, rule_version=RULE_VERSION,
        normalized_parameters=np, item_key=item_key,
        observed_value=dict(subject),
        completeness_status="COMPLETE",
        evidence_refs=list(evidence_refs),
        input_digest=FM.make_input_digest(
            snapshot_logical_identity=snapshot_identity,
            snapshot_content_hash=_canon(subject),
            rule_id=rule_id, rule_version=RULE_VERSION,
            normalized_parameters=np, item_key=item_key),
        content_hash=FM.make_content_hash(
            observation=OBSERVED, observed_value=dict(subject),
            unknown_reason=None, commit_sha=str(obs["commit_sha"]),
            completeness_status="COMPLETE"),
        extractor_version=RULE_VERSION)
    res = FI.ingest_fact(store, fact)
    return {"written": bool(res.get("ok")), "reused": False,
            "fact_id": fact_id,
            "error": None if res.get("ok")
                     else (res.get("error") or res.get("detail"))}


def ingest_project(store, *, project):
    subject = {
        "config_path": project["config_path"],
        "config_blob_oid": project["config_blob_oid"],
        "discovery_status": project["discovery_status"],
        "is_solution_style": project["is_solution_style"],
        "declared_composite": project["declared_composite"],
        "declared_root_dir": project["declared_root_dir"],
        "declared_out_dir": project["declared_out_dir"],
        "declared_files": project["declared_files"],
        "declared_include": project["declared_include"],
        "declared_exclude": project["declared_exclude"],
    }
    fid = make_fact_id(
        observation_id=project["project_observation_id"],
        rule_id=RULE_PROJECT, subject=subject)
    return _put(store, fact_id=fid, fact_type="ts_project_declaration",
                obs=project, rule_id=RULE_PROJECT, subject=subject,
                np={"project_observation_id":
                        project["project_observation_id"],
                    "config_content_digest": project["config_content_digest"],
                    "parser_version": project["parser_version"],
                    "config_completeness": project["config_completeness"],
                    "provenance_level": project["provenance_level"]},
                evidence_refs=project.get("evidence_refs") or [])


def ingest_reference(store, *, reference):
    subject = {
        "from_project_id": reference["from_project_id"],
        "from_config_path": reference["from_config_path"],
        "declared_path": reference["declared_path"],
        "to_config_path": reference.get("to_config_path"),
        "to_project_id": reference.get("to_project_id"),
        "status": reference["status"],
    }
    fid = make_fact_id(observation_id=reference["reference_id"],
                       rule_id=RULE_REFERENCE, subject=subject)
    return _put(store, fact_id=fid,
                fact_type="ts_project_reference",
                obs=reference, rule_id=RULE_REFERENCE, subject=subject,
                np={"reference_id": reference["reference_id"],
                    "to_config_blob_oid": reference.get("to_config_blob_oid"),
                    "resolver_version": reference["resolver_version"]},
                evidence_refs=reference.get("evidence_refs") or [])


def ingest_membership(store, *, membership):
    subject = {
        "project_id": membership["project_id"],
        "config_path": membership["config_path"],
        "source_file_path": membership["source_file_path"],
        "state": membership["state"],
        "matched_rule": membership.get("matched_rule"),
        "matched_field": membership.get("matched_field"),
        "excluded_by": membership.get("excluded_by"),
    }
    fid = make_fact_id(observation_id=membership["membership_id"],
                       rule_id=RULE_MEMBERSHIP, subject=subject)
    return _put(store, fact_id=fid, fact_type="ts_file_membership",
                obs=membership, rule_id=RULE_MEMBERSHIP, subject=subject,
                np={"membership_id": membership["membership_id"],
                    "selection_mode": membership.get("selection_mode"),
                    "resolution_version": membership["resolution_version"]},
                evidence_refs=membership.get("evidence_refs") or [])


def ingest_project_bundle(store, *, bundle, memberships=None):
    written, reused, failed = [], [], []
    for p in bundle.get("projects") or []:
        r = ingest_project(store, project=p)
        (written if r["written"] else reused if r["reused"] else failed).append(
            {"kind": "project", "fact_id": r["fact_id"]})
    for ref in bundle.get("references") or []:
        r = ingest_reference(store, reference=ref)
        (written if r["written"] else reused if r["reused"] else failed).append(
            {"kind": "reference", "fact_id": r["fact_id"]})
    for m in (memberships or []):
        r = ingest_membership(store, membership=m)
        (written if r["written"] else reused if r["reused"] else failed).append(
            {"kind": "membership", "fact_id": r["fact_id"]})
    return {"written": written, "reused": reused, "failed": failed}
