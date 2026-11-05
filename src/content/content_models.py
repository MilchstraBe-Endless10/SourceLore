#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容级数据模型。

★ Git Blob OID 与 SourceLore 内容摘要是**两个不同概念**，不混用。
★ Observation 身份确定性、可复算；同输入同解析器版本必须幂等。
"""

import hashlib
import json

OBSERVATION_SCHEMA = "file-content-observation/1"
SUPPORTED_SCHEMA = "content-support/1"

# 内容可用性（不是裁决状态）
C_AVAILABLE = "CONTENT_AVAILABLE"
C_NOT_CAPTURED = "CONTENT_NOT_CAPTURED"
C_TOO_LARGE = "BLOB_TOO_LARGE"
C_BINARY = "BINARY_CONTENT"
C_BAD_ENCODING = "UNSUPPORTED_ENCODING"
C_HASH_MISMATCH = "CONTENT_HASH_MISMATCH"
C_PARTIAL = "CONTENT_PARTIAL"
C_PARSE_FAILED = "CONTENT_PARSE_FAILED"

# 资产级完整性
COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"

# 解析器标识
P_README = "readme-markdown"
P_PKGJSON = "package-json"
P_PYPROJECT = "pyproject-toml"


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def make_observation_id(*, repository_id, commit_sha, file_path, git_blob_oid,
                        content_digest, parser_id, parser_version) -> str:
    """★ 确定性：相同七元组 → 相同 ID。

    故意不含 collected_at / 时间戳，否则重复抽取不幂等。
    """
    payload = {
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "file_path": str(file_path),
        "git_blob_oid": str(git_blob_oid),
        "content_digest": str(content_digest),
        "parser_id": str(parser_id),
        "parser_version": str(parser_version),
        "schema": OBSERVATION_SCHEMA,
    }
    return "SL-COBS-" + sha256_of(payload)


def make_content_fact_id(*, observation_id, rule_id, rule_version, subject):
    payload = {"observation_id": observation_id, "rule_id": rule_id,
               "rule_version": rule_version, "subject": subject}
    return "SL-CFACT-" + sha256_of(payload)


def build_observation(*, repository_id, commit_sha, file_path, git_blob_oid,
                      content_asset_id, content_digest, byte_length,
                      encoding, parser_id, parser_version,
                      completeness_status, evidence_ranges,
                      source_snapshot_id, extraction_status,
                      provenance_level="SYNTHETIC_FIXTURE"):
    """构造 Observation。★ provenance_level 必须显式，默认不冒充真实。"""
    oid = make_observation_id(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, git_blob_oid=git_blob_oid,
        content_digest=content_digest, parser_id=parser_id,
        parser_version=parser_version)
    return {
        "observation_schema": OBSERVATION_SCHEMA,
        "observation_id": oid,
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "file_path": str(file_path),
        "git_blob_oid": str(git_blob_oid),
        "content_asset_id": content_asset_id,
        "content_digest": content_digest,
        "byte_length": int(byte_length),
        "encoding": encoding,
        "parser_id": parser_id,
        "parser_version": parser_version,
        "completeness_status": completeness_status,
        "evidence_ranges": evidence_ranges,
        "provenance_level": provenance_level,
        "source_snapshot_id": source_snapshot_id,
        "extraction_status": extraction_status,
    }


def is_synthetic(obs) -> bool:
    return (obs or {}).get("provenance_level") == "SYNTHETIC_FIXTURE"
