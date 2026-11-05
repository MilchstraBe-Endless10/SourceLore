#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容 Observation / Facts 入库。

★ 复用既有 Facts 框架（FactObservation + ingest_fact），不建第二套状态机。
★ A 层不可 UPDATE：所有 ID 在写入前确定。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("facts", "storage", "content", "collector"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

OBS_ASSET_TYPE = "captured_blob_content"     # Observation 挂在内容资产上
OBS_SCHEMA = "content-observation-link/1"

# 内容规则（复用 Facts 的 rule 机制）
RULE_README_HEADING = "README_HEADING_EXISTS"
RULE_MANIFEST_DEP = "MANIFEST_DEPENDENCY_DECLARED"
RULE_MANIFEST_FIELD = "MANIFEST_FIELD_PRESENT"
CONTENT_RULE_VERSION = "content-facts/1"

OBSERVED_CONTENT_PRESENT = "OBSERVED_PRESENT"   # 复用既有观察态


def make_content_fact_id(*, observation_id, rule_id, subject):
    """★ 确定性 fact_id：同观察同规则同主体 → 同 ID（幂等前提）。"""
    import hashlib
    payload = f"{observation_id}|{rule_id}|{CONTENT_RULE_VERSION}|{_canon(subject)}"
    # ★ 必须符合框架的 SAFE_FACT_ID：SL-FACT-<40 hex>
    return "SL-FACT-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def _canon(obj):
    import json
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def make_observation_id(*, repository_id, commit_sha, file_path,
                        git_blob_oid, content_sha256, parser_id, parser_version):
    import hashlib
    payload = (f"{repository_id}|{commit_sha}|{file_path}|{git_blob_oid}|"
               f"{content_sha256}|{parser_id}|{parser_version}")
    return "SL-OBS-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def build_fact(*, repository_id, commit_sha, snapshot_asset_id,
               snapshot_logical_identity, file_path, git_blob_oid,
               content_asset_id, content_sha256, parser_id, parser_version,
               rule_id, subject, byte_range, line_range, completeness_status,
               provenance_level):
    """构造一条内容事实（FactObservation 形态）。"""
    import models as FM

    obs_id = make_observation_id(
        repository_id=repository_id, commit_sha=commit_sha, file_path=file_path,
        git_blob_oid=git_blob_oid, content_sha256=content_sha256,
        parser_id=parser_id, parser_version=parser_version)
    fact_id = make_content_fact_id(observation_id=obs_id, rule_id=rule_id,
                                   subject=subject)

    fact = FM.FactObservation(
        fact_id=fact_id,
        fact_type="content_observation",
        observation=OBSERVED_CONTENT_PRESENT,
        repository_id=str(repository_id),
        snapshot_asset_id=snapshot_asset_id,
        snapshot_logical_identity=snapshot_logical_identity,
        commit_sha=str(commit_sha),
        rule_id=rule_id,
        rule_version=CONTENT_RULE_VERSION,
        normalized_parameters={
            "file_path": file_path,
            "git_blob_oid": git_blob_oid,
            "content_asset_id": content_asset_id,
            "content_sha256": content_sha256,
            "parser_id": parser_id,
            "parser_version": parser_version,
            "subject": subject,
            "observation_id": obs_id,
            "byte_range": byte_range,
            "line_range": line_range,
            "evidence_kind": rule_id,
        },
        observed_value=dict(subject, **{
            "file_path": file_path,
            "git_blob_oid": git_blob_oid,
            "content_asset_id": content_asset_id,
            "content_sha256": content_sha256,
            "parser_version": parser_version,
            "start_byte": byte_range[0], "end_byte": byte_range[1],
            "start_line": line_range[0], "end_line": line_range[1],
            "provenance_level": provenance_level,
        }),
        item_key=f"{file_path}:{rule_id}:{_canon(subject)}",
        completeness_status=completeness_status,
        evidence_refs=[f"content:{content_asset_id}@{byte_range[0]}:{byte_range[1]}"],
        input_digest=FM.make_input_digest(
            snapshot_logical_identity=snapshot_logical_identity,
            snapshot_content_hash=content_sha256,
            rule_id=rule_id, rule_version=CONTENT_RULE_VERSION,
            item_key=f"{file_path}:{rule_id}:{_canon(subject)}",
            normalized_parameters={
                "file_path": file_path, "git_blob_oid": git_blob_oid,
                "content_sha256": content_sha256,
                "parser_version": parser_version,
                "subject": subject}),
        content_hash=FM.make_content_hash(
            observation=OBSERVED_CONTENT_PRESENT,
            observed_value=dict(subject, **{
                "file_path": file_path, "git_blob_oid": git_blob_oid,
                "content_sha256": content_sha256,
                "start_byte": byte_range[0], "end_byte": byte_range[1]}),
            unknown_reason=None, commit_sha=str(commit_sha),
            completeness_status=completeness_status),
        extractor_version=parser_version,
    )
    return fact, obs_id


def ingest_content_facts(store, *, repository_id, commit_sha, snapshot_asset_id,
                         snapshot_logical_identity, extraction_result,
                         content_asset_id, content_sha256, parser_id,
                         parser_version, file_path, git_blob_oid,
                         completeness_status, provenance_level):
    """把一次抽取产出的 facts 逐条入库。★ 幂等：同 fact_id 复用。"""
    import ingest as FI

    written, reused, skipped = [], [], []
    for item in extraction_result.get("facts", []):
        rule_id = item["rule_id"]
        subject = item.get("subject") or {}
        rng = item.get("range") or {}
        try:
            fact, obs_id = build_fact(
                repository_id=repository_id, commit_sha=commit_sha,
                snapshot_asset_id=snapshot_asset_id,
                snapshot_logical_identity=snapshot_logical_identity,
                file_path=file_path, git_blob_oid=git_blob_oid,
                content_asset_id=content_asset_id,
                content_sha256=content_sha256, parser_id=parser_id,
                parser_version=parser_version,
                rule_id=rule_id, subject=subject,
                byte_range=(rng.get("start_byte", 0), rng.get("end_byte", 0)),
                line_range=(rng.get("start_line", 0), rng.get("end_line", 0)),
                completeness_status=completeness_status,
                provenance_level=provenance_level)
        except Exception as e:
            skipped.append({"rule_id": rule_id, "reason":
                            f"{type(e).__name__}: {e}"})
            continue

        prev = store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='extracted_fact' "
            "AND logical_identity=?", (fact.fact_id,)).fetchone()
        if prev:
            reused.append({"fact_id": fact.fact_id, "rule_id": rule_id})
            continue

        res = FI.ingest_fact(store, fact)
        if res.get("ok"):
            written.append({"fact_id": fact.fact_id, "rule_id": rule_id,
                            "asset_id": res.get("asset_id"),
                            "observation_id": obs_id})
        else:
            skipped.append({"rule_id": rule_id,
                            "reason": res.get("error") or res.get("detail")})
    return {"written": written, "reused": reused, "skipped": skipped}
