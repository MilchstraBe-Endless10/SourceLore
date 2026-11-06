#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TypeScript 项目观察模型。

★ 只描述配置与静态选择，绝不表示编译成功或运行时可用。
"""

import hashlib, json

PROJECT_SCHEMA = "ts-project-observation/1"
REFERENCE_SCHEMA = "ts-project-reference/1"
MEMBERSHIP_SCHEMA = "ts-file-membership/1"
PARSER_ID = "ts-project"
PARSER_VERSION = "ts-project/1"

# 项目发现状态
PROJECT_CONFIG_VERIFIED = "PROJECT_CONFIG_VERIFIED"
PROJECT_CONFIG_NOT_CAPTURED = "PROJECT_CONFIG_NOT_CAPTURED"
PROJECT_CONFIG_INVALID = "PROJECT_CONFIG_INVALID"
PROJECT_CONFIG_INHERITANCE_UNRESOLVED = "PROJECT_CONFIG_INHERITANCE_UNRESOLVED"
PROJECT_CONFIG_AMBIGUOUS = "PROJECT_CONFIG_AMBIGUOUS"

# 引用解析状态
PROJECT_REFERENCE_DECLARED = "PROJECT_REFERENCE_DECLARED"
PROJECT_REFERENCE_TARGET_VERIFIED = "PROJECT_REFERENCE_TARGET_VERIFIED"
PROJECT_REFERENCE_TARGET_NOT_CAPTURED = "PROJECT_REFERENCE_TARGET_NOT_CAPTURED"
PROJECT_REFERENCE_TARGET_MISSING = "PROJECT_REFERENCE_TARGET_MISSING"
PROJECT_REFERENCE_OUTSIDE_REPOSITORY = "PROJECT_REFERENCE_OUTSIDE_REPOSITORY"
PROJECT_REFERENCE_CYCLE = "PROJECT_REFERENCE_CYCLE"
PROJECT_REFERENCE_DEPTH_EXCEEDED = "PROJECT_REFERENCE_DEPTH_EXCEEDED"

# 文件归属状态（★ 每态语义独立，绝不可互换）
INPUT_EXPLICITLY_LISTED = "INPUT_EXPLICITLY_LISTED"
INPUT_MATCHED_INCLUDE = "INPUT_MATCHED_INCLUDE"
INPUT_EXCLUDED_FROM_INCLUDE = "INPUT_EXCLUDED_FROM_INCLUDE"
INPUT_POSSIBLE_VIA_IMPORT = "INPUT_POSSIBLE_VIA_IMPORT"
INPUT_MATCHED_MULTIPLE_PROJECTS = "INPUT_MATCHED_MULTIPLE_PROJECTS"
INPUT_NOT_PROVEN = "INPUT_NOT_PROVEN"
CONFIG_INCOMPLETE = "CONFIG_INCOMPLETE"
UNSUPPORTED_SELECTION_RULE = "UNSUPPORTED_SELECTION_RULE"

# 项目上下文解析
PROJECT_CONTEXT_SELECTED = "PROJECT_CONTEXT_SELECTED"
PROJECT_CONTEXT_AMBIGUOUS = "PROJECT_CONTEXT_AMBIGUOUS"
PROJECT_CONTEXT_NONE = "PROJECT_CONTEXT_NONE"

LIMITATIONS = [
    "项目配置关系不代表项目已成功构建",
    "exclude 只影响 include 扫描，不等于文件永不进入 TypeScript Program",
    "files/include 匹配 ≠ 类型检查通过",
    "resolveJsonModule / allowJs 等未完整模拟",
]


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def make_project_id(*, repository_id, commit_sha, config_path,
                    config_blob_oid, config_content_digest, parser_version):
    """★ 项目身份由固定 Commit + 配置身份决定，不用目录名。"""
    payload = "|".join([PROJECT_SCHEMA, str(repository_id), str(commit_sha),
                        str(config_path), str(config_blob_oid),
                        str(config_content_digest), str(parser_version)])
    return "SL-TSPROJ-" + hashlib.sha256(
        payload.encode("utf-8")).hexdigest()[:40]


def make_reference_id(*, repository_id, commit_sha, from_project_id,
                      declared_path, to_config_path, resolver_version):
    payload = "|".join([REFERENCE_SCHEMA, str(repository_id),
                        str(commit_sha), str(from_project_id),
                        str(declared_path), str(to_config_path),
                        str(resolver_version)])
    return "SL-TSREF-" + hashlib.sha256(
        payload.encode("utf-8")).hexdigest()[:40]


def make_membership_id(*, repository_id, commit_sha, project_id,
                       source_file_path, resolution_version):
    payload = "|".join([MEMBERSHIP_SCHEMA, str(repository_id),
                        str(commit_sha), str(project_id),
                        str(source_file_path), str(resolution_version)])
    return "SL-TSMEM-" + hashlib.sha256(
        payload.encode("utf-8")).hexdigest()[:40]


def build_project_observation(*, repository_id, commit_sha, config_path,
                             config_blob_oid, config_content_asset_id,
                             config_content_digest, discovery_status,
                             project_root=None, declared_files=None,
                             declared_include=None, declared_exclude=None,
                             declared_references=None, declared_composite=None,
                             declared_root_dir=None, declared_out_dir=None,
                             declared_declaration=None,
                             declared_allow_js=None, declared_jsx=None,
                             config_completeness="COMPLETE",
                             inheritance_chain=None,
                             effective_fields=None,
                             is_solution_style=False,
                             evidence_refs=None,
                             provenance_level="SYNTHETIC_FIXTURE",
                             failure_reason=None, limitations=None):
    pid = make_project_id(
        repository_id=repository_id, commit_sha=commit_sha,
        config_path=config_path, config_blob_oid=config_blob_oid,
        config_content_digest=config_content_digest,
        parser_version=PARSER_VERSION)
    return {
        "schema": PROJECT_SCHEMA,
        "project_observation_id": pid,
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "config_path": config_path,
        "config_blob_oid": config_blob_oid,
        "config_content_asset_id": config_content_asset_id,
        "config_content_digest": config_content_digest,
        "parser_id": PARSER_ID,
        "parser_version": PARSER_VERSION,
        "effective_config_id": pid,
        "project_root": project_root,
        "discovery_status": discovery_status,
        "declared_files": list(declared_files or []),
        "declared_include": list(declared_include or []),
        "declared_exclude": list(declared_exclude or []),
        "declared_references": list(declared_references or []),
        "declared_composite": declared_composite,
        "declared_root_dir": declared_root_dir,
        "declared_out_dir": declared_out_dir,
        "declared_declaration": declared_declaration,
        "declared_allow_js": declared_allow_js,
        "declared_jsx": declared_jsx,
        "config_completeness": config_completeness,
        "inheritance_chain": list(inheritance_chain or []),
        "effective_fields": effective_fields or {},
        "is_solution_style": bool(is_solution_style),
        "evidence_refs": list(evidence_refs or []),
        "failure_reason": failure_reason,
        "limitations": (limitations or []) + LIMITATIONS,
        "provenance_level": provenance_level,
        "network_requests": 0,
    }


def build_reference(*, repository_id, commit_sha, from_project_id,
                    from_config_path, declared_path, to_config_path=None,
                    to_project_id=None, to_config_blob_oid=None,
                    to_config_content_asset_id=None,
                    status=None, evidence_refs=None,
                    limitations=None):
    rid = make_reference_id(
        repository_id=repository_id, commit_sha=commit_sha,
        from_project_id=from_project_id, declared_path=declared_path,
        to_config_path=to_config_path or "", resolver_version=PARSER_VERSION)
    return {
        "schema": REFERENCE_SCHEMA,
        "reference_id": rid,
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "from_project_id": from_project_id,
        "from_config_path": from_config_path,
        "declared_path": declared_path,
        "to_config_path": to_config_path,
        "to_project_id": to_project_id,
        "to_config_blob_oid": to_config_blob_oid,
        "to_config_content_asset_id": to_config_content_asset_id,
        "status": status or PROJECT_REFERENCE_DECLARED,
        "evidence_refs": list(evidence_refs or []),
        "limitations": (limitations or []) + LIMITATIONS,
        "resolver_version": PARSER_VERSION,
        "network_requests": 0,
    }


def build_membership(*, repository_id, commit_sha, project_id,
                     config_path, source_file_path, state, matched_rule=None,
                     matched_field=None, excluded_by=None,
                     other_project_ids=None, evidence_refs=None,
                     limitations=None, selection_mode=None):
    mid = make_membership_id(
        repository_id=repository_id, commit_sha=commit_sha,
        project_id=project_id, source_file_path=source_file_path,
        resolution_version=PARSER_VERSION)
    return {
        "schema": MEMBERSHIP_SCHEMA,
        "membership_id": mid,
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "project_id": project_id,
        "config_path": config_path,
        "source_file_path": source_file_path,
        "state": state,
        "matched_rule": matched_rule,
        "matched_field": matched_field,
        "excluded_by": excluded_by,
        "selection_mode": selection_mode,
        "other_project_ids": list(other_project_ids or []),
        "evidence_refs": list(evidence_refs or []),
        "limitations": (limitations or []) + LIMITATIONS,
        "resolution_version": PARSER_VERSION,
        "network_requests": 0,
    }
