#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Facts 数据模型。

契约：SL-CAP-0001～0010（Facts）、SL-CAP-0008（观察与推断分层）。

**四条不可混淆的东西：**
  fact_id        —— 事实身份（由规则 + 参数 + 快照身份派生）
  content_hash   —— 事实内容哈希（观测值变了就变）
  snapshot_identity —— 输入快照身份（Facts 不能改它）
  asset_id       —— Storage 层的物理资产 ID（由 Storage 生成）

**三条观察态（不是布尔）：**
  OBSERVED_PRESENT                 在快照中确实存在
  OBSERVED_ABSENT_IN_COVERED_SCOPE 在**已完整覆盖范围内**确实不存在
  UNKNOWN                          无法确定（必须带原因）

`UNKNOWN` 绝不用 `[]` / `False` / `NOT_FOUND` 冒充。
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Optional

# ── 观察态 ──────────────────────────────────────────────────
OBSERVED_PRESENT = "OBSERVED_PRESENT"
OBSERVED_ABSENT_IN_COVERED_SCOPE = "OBSERVED_ABSENT_IN_COVERED_SCOPE"
UNKNOWN = "UNKNOWN"

OBSERVATION_STATES = frozenset({OBSERVED_PRESENT,
                                OBSERVED_ABSENT_IN_COVERED_SCOPE,
                                UNKNOWN})

# UNKNOWN 的原因（必须用这些码，不允许自由文本充当原因）
U_MANIFEST_ABSENT = "MANIFEST_ABSENT"            # v1 快照没有清单，无法判不存在
U_PARTIAL_SNAPSHOT = "PARTIAL_SNAPSHOT"          # 快照不完整
U_SCOPE_NOT_COVERING = "SCOPE_NOT_COVERING"      # 采集范围未覆盖目标路径
U_TREE_TRUNCATED = "TREE_TRUNCATED"              # 树被截断
U_ENTRY_REQUIRED_MISSING = "ENTRY_REQUIRED_MISSING"  # 必需条目缺失
U_BLOB_VERIFY_FAILED = "BLOB_VERIFY_FAILED"      # blob 校验失败
U_ASSET_INTEGRITY_FAILED = "ASSET_INTEGRITY_FAILED"  # 资产完整性校验失败
U_ASSET_NOT_FOUND = "ASSET_NOT_FOUND"            # 找不到来源快照
U_MALFORMED_MANIFEST = "MALFORMED_MANIFEST"      # 清单结构异常
U_DUPLICATE_ENTRY = "DUPLICATE_ENTRY"            # 路径条目重复

UNKNOWN_REASONS = frozenset({
    U_MANIFEST_ABSENT, U_PARTIAL_SNAPSHOT, U_SCOPE_NOT_COVERING, U_TREE_TRUNCATED,
    U_ENTRY_REQUIRED_MISSING, U_BLOB_VERIFY_FAILED, U_ASSET_INTEGRITY_FAILED,
    U_ASSET_NOT_FOUND, U_MALFORMED_MANIFEST, U_DUPLICATE_ENTRY})

# 合法的 Tree 对象类型
OBJ_BLOB = "blob"
OBJ_TREE = "tree"
OBJ_COMMIT = "commit"       # submodule
OBJ_UNKNOWN = "unknown"

# 每个对象类型对应的"它到底是不是普通文件"
TYPE_IS_REGULAR_FILE = {OBJ_BLOB: True, OBJ_TREE: False,
                        OBJ_COMMIT: False, OBJ_UNKNOWN: False}

# mode → 语义
MODE_SYMLINK = "120000"
MODE_SUBMODULE = "160000"
MODE_DIR = "040000"

SAFE_FACT_ID = re.compile(r"^SL-FACT-[0-9a-f]{40}$")


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_of(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def normalize_path(p: str) -> str:
    """路径标准化。

    规则（明确、可测）：
      - 必须是非空字符串
      - 不允许绝对路径（以 / 开头）
      - 统一分隔符为 /
      - 拒绝 ..（父目录穿越）、空段、反斜杠、空字节
      - 不做大小写折叠（Git 路径大小写敏感）
    """
    if not isinstance(p, str) or not p:
        raise ValueError("路径必须是非空字符串")
    if p.startswith("/"):
        raise ValueError(f"路径不得为绝对路径: {p!r}")
    if "\\" in p:
        raise ValueError(f"路径不得含反斜杠: {p!r}")
    if "\x00" in p:
        raise ValueError("路径不得含空字节")
    if p.endswith("/"):
        p = p[:-1]
    segs = p.split("/")
    if any(s == "" for s in segs):
        raise ValueError(f"路径不得含空段: {p!r}")
    if any(s == ".." for s in segs):
        raise ValueError(f"路径不得含父目录穿越: {p!r}")
    return "/".join(segs)


@dataclass
class FactObservation:
    """一条确定性观察。

    `observed_at` **不参与身份**，也不参与 content_hash —— 抽取时间不是事实身份。
    """
    fact_id: str
    fact_type: str                      # 固定 "file_path_observation"
    observation: str                    # OBSERVED_PRESENT / ...ABSENT... / UNKNOWN
    repository_id: str
    snapshot_asset_id: str
    snapshot_logical_identity: str
    commit_sha: str
    rule_id: str
    rule_version: str
    normalized_parameters: dict
    item_key: str
    observed_value: dict
    completeness_status: str
    evidence_refs: list
    input_digest: str
    content_hash: str
    extractor_version: str
    unknown_reason: Optional[str] = None
    observed_at: str = ""
    manifest_version: Optional[int] = None

    def __post_init__(self):
        if self.observation not in OBSERVATION_STATES:
            raise ValueError(f"非法观察态: {self.observation!r}")
        if not SAFE_FACT_ID.match(self.fact_id):
            raise ValueError(f"非法 fact_id 形态: {self.fact_id!r}")
        if self.observation == UNKNOWN:
            if self.unknown_reason is None:
                raise ValueError("UNKNOWN 必须带 unknown_reason")
            if self.unknown_reason not in UNKNOWN_REASONS:
                raise ValueError(f"非法 unknown_reason: {self.unknown_reason!r}")
        else:
            if self.unknown_reason is not None:
                raise ValueError("非 UNKNOWN 的观察不得带 unknown_reason")

    def to_dict(self) -> dict:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "observation": self.observation,
            "repository_id": self.repository_id,
            "snapshot_asset_id": self.snapshot_asset_id,
            "snapshot_logical_identity": self.snapshot_logical_identity,
            "commit_sha": self.commit_sha,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "normalized_parameters": self.normalized_parameters,
            "item_key": self.item_key,
            "observed_value": self.observed_value,
            "completeness_status": self.completeness_status,
            "evidence_refs": self.evidence_refs,
            "input_digest": self.input_digest,
            "content_hash": self.content_hash,
            "extractor_version": self.extractor_version,
            "unknown_reason": self.unknown_reason,
            "observed_at": self.observed_at,
            "manifest_version": self.manifest_version,
        }

    def is_deterministic(self) -> bool:
        """只有非 UNKNOWN 的观察才是可入库的确定性事实。"""
        return self.observation != UNKNOWN


def make_fact_id(*, repository_id: str, snapshot_logical_identity: str,
                 rule_id: str, rule_version: str,
                 normalized_parameters: dict, item_key: str) -> str:
    """事实身份。

    输入顺序无关（canonical_json 排序），不含时间。
    多结果规则靠 item_key 区分（不用数组下标）。
    """
    payload = {
        "repository_id": str(repository_id),
        "snapshot_logical_identity": snapshot_logical_identity,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "normalized_parameters": normalized_parameters,
        "item_key": item_key,
    }
    return "SL-FACT-" + sha256_of(payload)[:40]


def make_content_hash(*, observation: str, observed_value: dict,
                      unknown_reason: Optional[str],
                      commit_sha: str, completeness_status: str) -> str:
    """内容哈希：不含 observed_at，但包含观测结论本身。

    同输入同规则 → 同哈希；观测值变了 → 哈希变。
    """
    payload = {
        "observation": observation,
        "observed_value": observed_value,
        "unknown_reason": unknown_reason,
        "commit_sha": commit_sha,
        "completeness_status": completeness_status,
    }
    return sha256_of(payload)


def make_input_digest(*, snapshot_logical_identity: str,
                      snapshot_content_hash: str, rule_id: str,
                      rule_version: str, normalized_parameters: dict,
                      item_key: str) -> str:
    """输入摘要：标识"这次抽取吃的是什么输入"。

    与 content_hash 不同：前者固定输入，后者固定输出。
    """
    return sha256_of({
        "snapshot_logical_identity": snapshot_logical_identity,
        "snapshot_content_hash": snapshot_content_hash,
        "rule_id": rule_id,
        "rule_version": rule_version,
        "normalized_parameters": normalized_parameters,
        "item_key": item_key,
    })


def build_evidence_refs(*, repository_id: str, commit_sha: str,
                        snapshot_asset_id: str, snapshot_logical_identity: str,
                        root_tree_sha: str, tree_query_ref: str,
                        path: str, obj_type: str, mode: str,
                        blob_sha: Optional[str], rule_id: str, rule_version: str,
                        completeness_status: str,
                        manifest_version: Optional[int]) -> list:
    """结构化证据引用。**不是一段自然语言**。

    刻意区分：证据对象存在 ≠ 证据足以支持任意结论。
    """
    return [{
        "kind": "source_snapshot",
        "repository_id": repository_id,
        "commit_sha": commit_sha,
        "snapshot_asset_id": snapshot_asset_id,
        "snapshot_logical_identity": snapshot_logical_identity,
        "root_tree_sha": root_tree_sha,
        "tree_query_ref": tree_query_ref,
        "completeness_status": completeness_status,
        "manifest_version": manifest_version,
        "rule_id": rule_id,
        "rule_version": rule_version,
    }, {
        "kind": "tree_entry",
        "path": path,
        "object_type": obj_type,
        "mode": mode,
        "blob_sha": blob_sha,
    }]
