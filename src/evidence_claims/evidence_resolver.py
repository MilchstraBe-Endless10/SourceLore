#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据解析：沿 evidence_refs 回查事实与来源快照。

**"不直接读 GitHub" ≠ "不能核验证据的上游来源"。**
本模块通过 Storage 授权接口回查，不联网、不重抓。

必须核验的 10 项（题面第 4 节）：
 1 fact_id 真实存在
 2 Fact 内容哈希正确
 3 Snapshot 引用真实存在
 4 Fact 与 Claim 的 repository_id 一致
 5 Commit 范围一致
 6 路径规范化语义一致
 7 来源完整性足以支持当前命题
 8 必需证据字段没有缺失
 9 引用未指向错误版本
10 证据对象存在 ≠ 支持结论（这条由 verifier 保证）
"""

import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage"), str(_HERE.parent / "facts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ec_models as M
from facts_models_proxy import FACT_ASSET_TYPE, fact_content_hash_of

FACT_ASSET_TYPE_NAME = "extracted_fact"
SNAPSHOT_ASSET_TYPE = "repository_snapshot"


class ResolvedFact:
    """一条已核验的（或核验失败的）证据事实。"""

    def __init__(self, fact_id: str):
        self.fact_id = fact_id
        self.ok = False
        self.reason: Optional[str] = None          # 核验失败的 INSUFFICIENT 原因码
        self.detail: str = ""
        self.storage_error: Optional[str] = None   # 存储层错误，与 insufficient 分开
        self.payload: dict = {}
        self.content_hash: str = ""
        self.asset_id: str = ""
        self.repository_id: Optional[str] = None
        self.commit_sha: Optional[str] = None
        self.snapshot_asset_id: Optional[str] = None
        self.snapshot_logical_identity: Optional[str] = None
        self.observation: Optional[str] = None
        self.normalized_path: Optional[str] = None
        self.completeness_status: Optional[str] = None
        self.local_coverage_only: bool = False
        self.asset_version: int = 0


def _fail(f: ResolvedFact, reason: str, detail: str = "", storage: bool = False):
    f.ok = False
    f.reason = reason
    f.detail = detail
    if storage:
        f.storage_error = detail
    return f


def resolve_fact(store, fact_id: str) -> ResolvedFact:
    """通过 Storage 公开 API 回查一条 fact 资产并校验其完整性。"""
    f = ResolvedFact(fact_id)

    # 1) fact_id 必须真实存在
    got = store.get_asset(fact_id, verify=True) if _is_asset_id(fact_id) else None
    if got is None:
        # fact_id 不是 asset_id —— 需要按 logical_identity 查
        got = _lookup_by_logical_identity(store, fact_id)

    if got is None:
        return _fail(f, M.R_FACT_NOT_FOUND, f"找不到 fact 资产: {fact_id}")

    if not got.get("ok"):
        if got.get("error") == "CHECKPOINT_CORRUPT":
            return _fail(f, M.R_FACT_INTEGRITY, got.get("detail", ""), storage=True)
        return _fail(f, M.R_FACT_NOT_FOUND, got.get("detail", ""))

    a = got["asset"]
    if a.get("asset_type") != FACT_ASSET_TYPE_NAME:
        return _fail(f, M.R_FACT_NOT_FOUND,
                     f"资产类型不是 {FACT_ASSET_TYPE_NAME}: {a.get('asset_type')}")

    p = a["payload"]

    # 8) 必需证据字段没有缺失
    required = ("fact_id", "observation", "repository_id", "commit_sha",
                "snapshot_asset_id", "snapshot_logical_identity",
                "normalized_parameters", "completeness_status", "content_hash")
    missing = [k for k in required if k not in p]
    if missing:
        return _fail(f, M.R_EVIDENCE_FIELD_MISSING, f"缺字段 {missing}")

    # 2) Fact 内容哈希正确（用 Facts 侧同一算法独立复算）
    recomputed = fact_content_hash_of(
        observation=p["observation"],
        observed_value=p.get("observed_value") or {},
        unknown_reason=p.get("unknown_reason"),
        commit_sha=p["commit_sha"],
        completeness_status=p["completeness_status"])
    if recomputed != p["content_hash"]:
        return _fail(f, M.R_FACT_INTEGRITY,
                     f"内容哈希不符: 记录 {p['content_hash'][:12]}… "
                     f"复算 {recomputed[:12]}…")

    f.ok = True
    f.payload = p
    f.content_hash = p["content_hash"]
    f.asset_id = a["asset_id"]
    f.asset_version = a.get("asset_version", 0)
    f.repository_id = str(p["repository_id"])
    f.commit_sha = p["commit_sha"]
    f.snapshot_asset_id = p["snapshot_asset_id"]
    f.snapshot_logical_identity = p["snapshot_logical_identity"]
    f.observation = p["observation"]
    f.normalized_path = (p.get("normalized_parameters") or {}).get("target_path")
    f.completeness_status = p["completeness_status"]
    f.local_coverage_only = bool((p.get("observed_value") or {})
                                 .get("local_coverage_only"))

    # 3) Snapshot 引用真实存在
    snap = store.get_asset(f.snapshot_asset_id, verify=True)
    if not snap.get("ok"):
        if snap.get("error") == "CHECKPOINT_CORRUPT":
            return _fail(f, M.R_SNAPSHOT_INTEGRITY,
                         snap.get("detail", ""), storage=True)
        return _fail(f, M.R_SNAPSHOT_NOT_FOUND, "来源快照不存在或不可读")

    sa = snap["asset"]
    if sa.get("asset_type") != SNAPSHOT_ASSET_TYPE:
        return _fail(f, M.R_SNAPSHOT_NOT_FOUND,
                     f"来源资产类型异常: {sa.get('asset_type')}")
    if sa.get("logical_identity") != f.snapshot_logical_identity:
        return _fail(f, M.R_SNAPSHOT_INTEGRITY,
                     "事实引用的快照身份与实存快照不一致")

    return f


def _is_asset_id(s: str) -> bool:
    return isinstance(s, str) and s.startswith("SL-A-")


def _lookup_by_logical_identity(store, fact_id: str):
    """fact_id 是 logical_identity（Facts 侧这么入库的）。"""
    try:
        row = store.conn.execute(
            "SELECT asset_id FROM assets WHERE logical_identity=? "
            "ORDER BY asset_version DESC LIMIT 1", (fact_id,)).fetchone()
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}
    if row is None:
        return None
    return store.get_asset(row["asset_id"], verify=True)


def resolve_all(store, fact_ids) -> list:
    """批量解析。**去重**：同一 fact 重复传入只计一次证据。"""
    seen, out = set(), []
    for fid in fact_ids:
        if fid in seen:
            continue
        seen.add(fid)
        out.append(resolve_fact(store, fid))
    return out
