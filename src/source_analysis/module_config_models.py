#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块解析配置模型：Config Observation + Static Module Resolution Observation。

★ 配置原文只作数据，绝不作可执行指令。
"""

import hashlib, json

CONFIG_SCHEMA = "module-resolution-config/1"
RESOLUTION_SCHEMA = "static-module-resolution/1"
RESOLVER_VERSION = "config-resolver/1"

# 配置种类
CONFIG_TSCONFIG = "tsconfig"
CONFIG_JSCONFIG = "jsconfig"
CONFIG_PACKAGE_JSON = "package_json"

# 有效配置状态
EFFECTIVE_CONFIG_RESOLVED = "EFFECTIVE_CONFIG_RESOLVED"
CONFIG_CONTENT_NOT_CAPTURED = "CONFIG_CONTENT_NOT_CAPTURED"
CONFIG_INHERITANCE_UNRESOLVED = "CONFIG_INHERITANCE_UNRESOLVED"
CONFIG_PARSE_FAILED = "CONFIG_PARSE_FAILED"
CONFIG_INHERITANCE_CYCLE = "CONFIG_INHERITANCE_CYCLE"
CONFIG_INHERITANCE_TOO_DEEP = "CONFIG_INHERITANCE_TOO_DEEP"
CONFIG_INTEGRITY_FAILED = "CONFIG_INTEGRITY_FAILED"
CONFIG_COMMIT_MISMATCH = "CONFIG_COMMIT_MISMATCH"
CONFIG_AMBIGUOUS_SCOPE = "CONFIG_AMBIGUOUS_SCOPE"

# 解析策略 / 模式
MODE_BUNDLER = "bundler"
MODE_NODE_NEXT = "nodenext"
MODE_NODE10 = "node10"
MODE_NODE16 = "node16"
MODE_CLASSIC = "classic"
MODE_UNKNOWN = "unknown"

# 静态解析状态（★ 三层，绝不出现 RUNTIME_* 成功态）
MODULE_REFERENCE_OBSERVED = "MODULE_REFERENCE_OBSERVED"
CONFIG_MAPPING_CANDIDATE = "CONFIG_MAPPING_CANDIDATE"
LOCAL_MODULE_RESOLVED = "LOCAL_MODULE_RESOLVED"
AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"
RESOLUTION_CONTEXT_INCOMPLETE = "RESOLUTION_CONTEXT_INCOMPLETE"
UNSUPPORTED_RESOLUTION_POLICY = "UNSUPPORTED_RESOLUTION_POLICY"
INSUFFICIENT_TREE_COVERAGE = "INSUFFICIENT_TREE_COVERAGE"
EXTERNAL_OR_UNRESOLVED = "EXTERNAL_OR_UNRESOLVED"
DYNAMIC_SPECIFIER = "DYNAMIC_SPECIFIER"
CONFIG_NOT_CAPTURED = "CONFIG_NOT_CAPTURED"
TARGET_BLOB_MISSING = "TARGET_BLOB_MISSING"
PATH_ESCAPES_REPOSITORY = "PATH_ESCAPES_REPOSITORY"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

LIMITATIONS_BASE = [
    "静态模块映射 ≠ 运行时模块加载成功",
    "tsconfig.paths 不自动改写输出代码的导入路径",
    "未验证构建是否成功",
]


def _canon(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def make_config_observation_id(*, repository_id, commit_sha, config_path,
                               git_blob_oid, content_digest, parser_version):
    """★ 配置身份：换 Commit 或换 Blob 必须换身份。"""
    payload = "|".join([CONFIG_SCHEMA, str(repository_id), str(commit_sha),
                        str(config_path), str(git_blob_oid),
                        str(content_digest), str(parser_version)])
    return "SL-CFG-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def make_resolution_id(*, repository_id, commit_sha, importing_file_path,
                       import_fact_id, module_specifier, import_kind,
                       is_type_only, config_observation_ids, resolution_policy,
                       resolver_version):
    """★ 关系身份：Import + 配置 + 策略版本 三者共同决定。"""
    payload = "|".join([
        RESOLUTION_SCHEMA, str(repository_id), str(commit_sha),
        str(importing_file_path), str(import_fact_id),
        str(module_specifier), str(import_kind), str(bool(is_type_only)),
        _canon(sorted(config_observation_ids or [])),
        str(resolution_policy), str(resolver_version)])
    return "SL-MREL-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def build_config_observation(*, repository_id, commit_sha, config_path,
                            config_kind, git_blob_oid, content_asset_id,
                            content_digest, effective_config_status,
                            module_resolution_mode=None,
                            declared_base_url=None, declared_paths=None,
                            declared_extends=None, declared_references=None,
                            declared_imports=None, declared_exports=None,
                            declared_name=None, declared_type=None,
                            evidence_ranges=None, limitations=None,
                            provenance_level="SYNTHETIC_FIXTURE",
                            parser_version=None, inheritance_chain=None,
                            failure_reason=None):
    pv = parser_version or RESOLVER_VERSION
    return {
        "schema": CONFIG_SCHEMA,
        "config_observation_id": make_config_observation_id(
            repository_id=repository_id, commit_sha=commit_sha,
            config_path=config_path, git_blob_oid=git_blob_oid,
            content_digest=content_digest, parser_version=pv),
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "config_path": config_path,
        "config_kind": config_kind,
        "git_blob_oid": git_blob_oid,
        "content_asset_id": content_asset_id,
        "content_digest": content_digest,
        "parser_id": "tsconfig-jsonc",
        "parser_version": pv,
        "effective_config_status": effective_config_status,
        "module_resolution_mode": module_resolution_mode,
        "declared_base_url": declared_base_url,
        "declared_paths": declared_paths or {},
        "declared_extends": declared_extends,
        "declared_references": declared_references or [],
        "declared_imports": declared_imports or {},
        "declared_exports": declared_exports,
        "declared_name": declared_name,
        "declared_type": declared_type,
        "evidence_ranges": evidence_ranges or [],
        "inheritance_chain": inheritance_chain or [],
        "failure_reason": failure_reason,
        "limitations": (limitations or []) + LIMITATIONS_BASE,
        "provenance_level": provenance_level,
        "network_requests": 0,
    }


def build_resolution_observation(*, repository_id, commit_sha,
                                 importing_file_path, importing_blob_oid,
                                 importing_content_asset_id, import_fact_id,
                                 module_specifier, import_kind, is_type_only,
                                 config_observation_ids, config_blob_oids,
                                 resolution_policy, matched_config_rule,
                                 candidate_paths, resolved_target_path=None,
                                 resolved_target_blob_oid=None,
                                 resolution_state, evidence_refs,
                                 limitations=None, provenance_level=None,
                                 matched_config_field=None,
                                 matched_config_path=None,
                                 condition_candidates=None,
                                 unresolved_reason=None):
    return {
        "schema": RESOLUTION_SCHEMA,
        "resolution_id": make_resolution_id(
            repository_id=repository_id, commit_sha=commit_sha,
            importing_file_path=importing_file_path,
            import_fact_id=import_fact_id,
            module_specifier=module_specifier, import_kind=import_kind,
            is_type_only=is_type_only,
            config_observation_ids=config_observation_ids,
            resolution_policy=resolution_policy,
            resolver_version=RESOLVER_VERSION),
        "repository_id": str(repository_id),
        "commit_sha": str(commit_sha),
        "importing_file_path": importing_file_path,
        "importing_blob_oid": importing_blob_oid,
        "importing_content_asset_id": importing_content_asset_id,
        "import_fact_id": import_fact_id,
        "module_specifier": module_specifier,
        "import_kind": import_kind,
        "is_type_only": bool(is_type_only),
        "config_observation_ids": list(config_observation_ids or []),
        "config_blob_oids": list(config_blob_oids or []),
        "resolution_policy": resolution_policy,
        "matched_config_field": matched_config_field,
        "matched_config_path": matched_config_path,
        "matched_config_rule": matched_config_rule,
        "candidate_paths": list(candidate_paths or []),
        "resolved_target_path": resolved_target_path,
        "resolved_target_blob_oid": resolved_target_blob_oid,
        "resolution_state": resolution_state,
        "condition_candidates": condition_candidates or [],
        "unresolved_reason": unresolved_reason,
        "evidence_refs": list(evidence_refs or []),
        "limitations": (limitations or []) + LIMITATIONS_BASE,
        "provenance_level": provenance_level or "SYNTHETIC_FIXTURE",
        "resolver_version": RESOLVER_VERSION,
        "network_requests": 0,
    }
