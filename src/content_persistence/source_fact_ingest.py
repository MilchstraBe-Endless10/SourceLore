#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码 Facts 入库。★ 复用既有 Facts 框架（FactObservation + ingest_fact）。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "source_analysis", "content_persistence"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

RULE_SYMBOL = "SOURCE_SYMBOL_DECLARED"
RULE_IMPORT = "SOURCE_IMPORT_DECLARED"
RULE_LOCAL = "SOURCE_LOCAL_MODULE_RESOLVED"
RULE_VERSION = "source-facts/1"

OBSERVED = "OBSERVED_PRESENT"


def _canon(o):
    import json
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def make_source_fact_id(*, observation_id, rule_id, subject):
    import hashlib
    payload = f"{observation_id}|{rule_id}|{RULE_VERSION}|{_canon(subject)}"
    # ★ 必须符合 SAFE_FACT_ID：^SL-FACT-[0-9a-f]{40}$
    return "SL-FACT-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def build_source_fact(*, observation, rule_id, subject, byte_range,
                      line_range, evidence_label):
    import models as FM
    obs_id = observation["observation_id"]
    fid = make_source_fact_id(observation_id=obs_id, rule_id=rule_id,
                              subject=subject)
    file_path = observation["file_path"]
    commit = observation["commit_sha"]
    np = {
        "file_path": file_path,
        "git_blob_oid": observation["git_blob_oid"],
        "content_asset_id": observation["content_asset_id"],
        "content_sha256": observation["content_sha256"],
        "parser_id": observation["parser_id"],
        "parser_version": observation["parser_version"],
        "subject": subject,
        "observation_id": obs_id,
        "byte_range": list(byte_range),
        "line_range": list(line_range),
        "evidence_label": evidence_label,
        "language": observation["language"],
    }
    observed_value = dict(subject, **{
        "file_path": file_path,
        "git_blob_oid": observation["git_blob_oid"],
        "content_asset_id": observation["content_asset_id"],
        "content_sha256": observation["content_sha256"],
        "parser_version": observation["parser_version"],
        "start_byte": byte_range[0], "end_byte": byte_range[1],
        "start_line": line_range[0], "end_line": line_range[1],
        "provenance_level": observation["provenance_level"],
    })
    item_key = f"{file_path}:{rule_id}:{_canon(subject)}"
    fact = FM.FactObservation(
        fact_id=fid,
        fact_type="source_structure_observation",
        observation=OBSERVED,
        repository_id=str(observation["repository_id"]),
        snapshot_asset_id=observation.get("source_snapshot_id") or "",
        snapshot_logical_identity=(observation.get("source_snapshot_id")
                                   or "SL-SNAP-src"),
        commit_sha=str(commit),
        rule_id=rule_id,
        rule_version=RULE_VERSION,
        normalized_parameters=np,
        item_key=item_key,
        observed_value=observed_value,
        completeness_status=observation["source_completeness"],
        evidence_refs=[f"source:{observation['content_asset_id']}@"
                       f"{byte_range[0]}:{byte_range[1]}"],
        input_digest=FM.make_input_digest(
            snapshot_logical_identity=(observation.get("source_snapshot_id")
                                       or "SL-SNAP-src"),
            snapshot_content_hash=observation["content_sha256"],
            rule_id=rule_id, rule_version=RULE_VERSION,
            normalized_parameters=np, item_key=item_key),
        content_hash=FM.make_content_hash(
            observation=OBSERVED, observed_value=observed_value,
            unknown_reason=None, commit_sha=str(commit),
            completeness_status=observation["source_completeness"]),
        extractor_version=observation["parser_version"],
    )
    return fact


def ingest_source_facts(store, *, observation, source_snapshot_id=None):
    """把一次源码观察产出的事实逐条入库。★ 幂等。"""
    import ingest as FI

    if source_snapshot_id:
        observation = dict(observation, source_snapshot_id=source_snapshot_id)

    if observation["extraction_status"] != "EXTRACTED":
        return {"written": [], "reused": [], "skipped": [],
                "note": "解析未成功，不产生事实",
                "status": observation["extraction_status"]}

    ev_by_label = {e["label"]: e for e in observation["evidence_ranges"]}
    written, reused, skipped = [], [], []

    def _put(rule_id, subject, label):
        ev = ev_by_label.get(label)
        if not ev:
            skipped.append({"rule_id": rule_id, "reason": "EVIDENCE_MISSING"})
            return
        try:
            fact = build_source_fact(
                observation=observation, rule_id=rule_id, subject=subject,
                byte_range=(ev["start_byte"], ev["end_byte"]),
                line_range=(ev["start_line"], ev["end_line"]),
                evidence_label=ev["label"])
        except Exception as e:
            skipped.append({"rule_id": rule_id,
                            "reason": f"{type(e).__name__}: {e}"})
            return
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

    for sym in observation["observed_symbols"]:
        kind = sym["symbol_kind"]
        if kind not in ("class", "function", "async_function", "method",
                        "async_method", "nested_function"):
            continue
        _put(RULE_SYMBOL,
             {"qualified_name": sym["qualified_name"],
              "symbol_kind": kind,
              "symbol_name": sym["symbol_name"]},
             sym["evidence_ref"])

    for imp in observation["observed_imports"]:
        _put(RULE_IMPORT,
             {"module_name": imp["module_name"],
              "imported_name": imp["imported_name"],
              "import_syntax": imp["import_syntax"],
              "relative_level": imp["relative_level"]},
             imp["evidence_ref"])

    return {"written": written, "reused": reused, "skipped": skipped}
