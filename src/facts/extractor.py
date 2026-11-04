#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Facts 抽取器：从已登记的 repository_snapshot 资产做确定性观察。

契约：SL-CAP-0008（分层）、0013（三字段分离）。

**输入来源唯一：Storage 里已提交的 `repository_snapshot` 资产。**
不请求 GitHub、不看当前分支、不猜缺失文件、不读模型热记忆、不绕过 Storage API。

**判定优先级（严格顺序，先否定再肯定）：**
  1. 快照资产必须能读到且完整性校验通过 → 否则 UNKNOWN
  2. 清单必须存在（v2）→ v1 快照无法判"不存在"，只能 UNKNOWN
  3. 快照完整性必须 COMPLETE 才可判"不存在"
  4. 路径标准化 → 非法即 UNKNOWN(SCOPE_NOT_COVERING 的语义变体)
  5. 找条目：命中 → PRESENT（并保留类型/mode 语义）；多条命中 → UNKNOWN(DUPLICATE)
  6. 未命中：仅当 COMPLETE + 清单完整 + 范围覆盖 → ABSENT；否则 UNKNOWN
"""

import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage"), str(_HERE.parent / "collector")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from models import (FactObservation, OBSERVED_PRESENT,
                    OBSERVED_ABSENT_IN_COVERED_SCOPE, UNKNOWN,
                    U_MANIFEST_ABSENT, U_PARTIAL_SNAPSHOT, U_SCOPE_NOT_COVERING,
                    U_TREE_TRUNCATED, U_ENTRY_REQUIRED_MISSING,
                    U_ASSET_INTEGRITY_FAILED, U_ASSET_NOT_FOUND,
                    U_MALFORMED_MANIFEST, U_DUPLICATE_ENTRY,
                    build_evidence_refs, make_content_hash, make_fact_id,
                    make_input_digest, normalize_path)
from rules import (EXTRACTOR_VERSION, RULE_FILE_PATH, RULE_FILE_PATH_V1,
                   describe_object, get_rule)

SNAPSHOT_ASSET_TYPE = "repository_snapshot"
SNAPSHOT_STATUS_COMPLETE = "COMPLETE"
SCOPE_FULL_TREE = "full_tree_enumeration"


def _load_snapshot(store, snapshot_asset_id: str) -> dict:
    """从 Storage 读快照资产。**只用公开 API。**"""
    got = store.get_asset(snapshot_asset_id, verify=True)
    if not got.get("ok"):
        code = got.get("error")
        if code == "CHECKPOINT_CORRUPT":
            return {"ok": False, "reason": U_ASSET_INTEGRITY_FAILED,
                    "detail": got.get("detail", "")}
        return {"ok": False, "reason": U_ASSET_NOT_FOUND,
                "detail": got.get("detail", "")}
    a = got["asset"]
    if a.get("asset_type") != SNAPSHOT_ASSET_TYPE:
        return {"ok": False, "reason": U_ASSET_NOT_FOUND,
                "detail": f"资产类型不是 {SNAPSHOT_ASSET_TYPE}: {a.get('asset_type')}"}
    return {"ok": True, "asset": a}


def _resolve_scope_covers(*, retrieval_scope: str, target_path: str) -> bool:
    """判断采集范围是否覆盖目标路径。

    本批只有一种范围：full_tree_enumeration（全树枚举，覆盖一切非空路径）。
    未来若出现 path-prefix 之类的范围，这里必须扩展；未知范围一律视为**不覆盖**。
    """
    if retrieval_scope == SCOPE_FULL_TREE:
        return target_path != ""
    return False


def extract_file_path_observation(store, *, snapshot_asset_id: str,
                                  target_path: str,
                                  rule_version: str = RULE_FILE_PATH_V1,
                                  observed_at: str = "") -> FactObservation:
    """规则 file_path_observation 的唯一入口。

    返回 FactObservation；调用方负责决定是否入库（UNKNOWN 不入库）。
    """
    rule = get_rule(RULE_FILE_PATH, rule_version)

    # 参数标准化（先做，失败也要能构造 UNKNOWN）
    raw_target = target_path
    try:
        norm_target = normalize_path(target_path)
        param_ok = True
    except ValueError:
        norm_target = str(target_path)
        param_ok = False

    params = {"target_path": norm_target}
    item_key = f"path:{norm_target}"

    def _unknown(reason: str, *, snap_ctx: dict, detail: str = "") -> FactObservation:
        return _build(observation=UNKNOWN,
                      observed_value={"reason_detail": detail} if detail else {},
                      snap_ctx=snap_ctx, params=params, item_key=item_key,
                      unknown_reason=reason, observed_at=observed_at,
                      completeness=snap_ctx.get("completeness_status", "UNKNOWN"),
                      manifest_version=snap_ctx.get("manifest_version"))

    # 1) 载入快照
    loaded = _load_snapshot(store, snapshot_asset_id)
    if not loaded["ok"]:
        ctx = {"repository_id": "UNKNOWN", "commit_sha": "UNKNOWN",
               "logical_identity": "UNKNOWN", "content_hash": "UNKNOWN",
               "root_tree_sha": "UNKNOWN", "tree_query_ref": "UNKNOWN",
               "completeness_status": "UNKNOWN"}
        return _unknown(loaded["reason"], snap_ctx=ctx, detail=loaded.get("detail", ""))

    a = loaded["asset"]
    p = a["payload"]
    ctx = {
        "repository_id": str(p.get("repository_id")),
        "commit_sha": p.get("commit_sha"),
        "logical_identity": a["logical_identity"],
        "content_hash": a["content_hash"],
        "root_tree_sha": p.get("root_tree_sha"),
        "tree_query_ref": p.get("tree_query_ref"),
        "completeness_status": p.get("completeness_status"),
        "manifest_version": p.get("manifest_version"),
        "retrieval_scope": p.get("retrieval_scope"),
        "asset_id": a["asset_id"],
    }

    # 参数不合法 → 无法在定义域内观察
    if not param_ok:
        return _unknown(U_SCOPE_NOT_COVERING, snap_ctx=ctx,
                        detail=f"路径非法，无法标准化: {raw_target!r}")

    # 2) 清单必须存在
    entries = p.get("tree_entries")
    mv = p.get("manifest_version")
    if mv is None or entries is None:
        # v1 快照：只有 blob_refs，无法证明"不存在"
        return _unknown(U_MANIFEST_ABSENT, snap_ctx=ctx,
                        detail="该快照是 v1 清单（只有 blob_refs），无法判定不存在")

    if not isinstance(entries, list):
        return _unknown(U_MALFORMED_MANIFEST, snap_ctx=ctx,
                        detail="tree_entries 不是列表")

    # 3) 截断事实优先（即使 status 说 COMPLETE，截断痕迹必须尊重）
    if p.get("tree_truncated_seen"):
        return _unknown(U_TREE_TRUNCATED, snap_ctx=ctx,
                        detail="采集时观察到 truncated=true")

    # 4) 范围覆盖
    if not _resolve_scope_covers(retrieval_scope=ctx.get("retrieval_scope") or "",
                                 target_path=norm_target):
        return _unknown(U_SCOPE_NOT_COVERING, snap_ctx=ctx,
                        detail=f"retrieval_scope={ctx.get('retrieval_scope')!r} "
                               f"不覆盖路径 {norm_target!r}")

    # 5) 找条目
    hits = []
    malformed = False
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("path"), str):
            malformed = True
            break
        try:
            if normalize_path(e["path"]) == norm_target:
                hits.append(e)
        except ValueError:
            continue

    if malformed:
        return _unknown(U_MALFORMED_MANIFEST, snap_ctx=ctx,
                        detail="清单含结构异常的条目")

    if len(hits) > 1:
        return _unknown(U_DUPLICATE_ENTRY, snap_ctx=ctx,
                        detail=f"清单中 {norm_target!r} 命中 {len(hits)} 条")

    status = (ctx.get("completeness_status") or "").upper()

    if hits:
        # 条目存在 → PRESENT。**即使 PARTIAL 也可以报存在**（
        # 因为有真实条目为证），但必须保留完整性限制。
        e = hits[0]
        obj = describe_object(e.get("type", "unknown"), e.get("mode", ""))
        value = {
            "path": norm_target,
            "object_type": obj["object_type"],
            "mode": obj["mode"],
            "object_kind": obj["object_kind"],
            "is_regular_file": obj["is_regular_file"],
            "blob_sha": e.get("sha") if obj["object_type"] == "blob" else None,
            "size": e.get("size"),
            "completeness_status": status,
            # PARTIAL 下的存在结论必须带这个局部覆盖标记
            "local_coverage_only": status != SNAPSHOT_STATUS_COMPLETE,
            "type_note": obj["note"],
        }
        return _build(observation=OBSERVED_PRESENT, observed_value=value,
                      snap_ctx=ctx, params=params, item_key=item_key,
                      unknown_reason=None, observed_at=observed_at,
                      completeness=status, manifest_version=mv)

    # 未命中 → 只有 COMPLETE 才能判"不存在"
    if status != SNAPSHOT_STATUS_COMPLETE:
        return _unknown(U_PARTIAL_SNAPSHOT, snap_ctx=ctx,
                        detail=(f"快照完整性为 {status!r}，未命中不能推出不存在"
                                "（可能是覆盖范围之外）"))

    return _build(observation=OBSERVED_ABSENT_IN_COVERED_SCOPE,
                  observed_value={
                      "path": norm_target,
                      "completeness_status": status,
                      # 严格限定语义，防止被读成"仓库没有这个功能"
                      "scope_statement": ("在指定 Commit 的已完整覆盖范围内"
                                          "未发现该路径"),
                      "not_a_claim": ("这不表示仓库现在不存在该文件，"
                                      "也不表示项目没有相关功能"),
                  },
                  snap_ctx=ctx, params=params, item_key=item_key,
                  unknown_reason=None, observed_at=observed_at,
                  completeness=status, manifest_version=mv)


def _build(*, observation: str, observed_value: dict, snap_ctx: dict,
           params: dict, item_key: str, unknown_reason: Optional[str],
           observed_at: str, completeness: str,
           manifest_version: Optional[int]) -> FactObservation:
    rule_id = RULE_FILE_PATH
    rule_version = RULE_FILE_PATH_V1

    fact_id = make_fact_id(
        repository_id=snap_ctx["repository_id"],
        snapshot_logical_identity=snap_ctx["logical_identity"],
        rule_id=rule_id, rule_version=rule_version,
        normalized_parameters=params, item_key=item_key)

    content_hash = make_content_hash(
        observation=observation, observed_value=observed_value,
        unknown_reason=unknown_reason, commit_sha=snap_ctx["commit_sha"],
        completeness_status=completeness)

    input_digest = make_input_digest(
        snapshot_logical_identity=snap_ctx["logical_identity"],
        snapshot_content_hash=snap_ctx["content_hash"],
        rule_id=rule_id, rule_version=rule_version,
        normalized_parameters=params, item_key=item_key)

    ev = build_evidence_refs(
        repository_id=snap_ctx["repository_id"],
        commit_sha=snap_ctx["commit_sha"],
        snapshot_asset_id=snap_ctx.get("asset_id", "UNKNOWN"),
        snapshot_logical_identity=snap_ctx["logical_identity"],
        root_tree_sha=snap_ctx.get("root_tree_sha"),
        tree_query_ref=snap_ctx.get("tree_query_ref"),
        path=params["target_path"],
        obj_type=observed_value.get("object_type", "unknown"),
        mode=observed_value.get("mode", ""),
        blob_sha=observed_value.get("blob_sha"),
        rule_id=rule_id, rule_version=rule_version,
        completeness_status=completeness,
        manifest_version=manifest_version)

    return FactObservation(
        fact_id=fact_id, fact_type=rule_id, observation=observation,
        repository_id=snap_ctx["repository_id"],
        snapshot_asset_id=snap_ctx.get("asset_id", "UNKNOWN"),
        snapshot_logical_identity=snap_ctx["logical_identity"],
        commit_sha=snap_ctx["commit_sha"],
        rule_id=rule_id, rule_version=rule_version,
        normalized_parameters=params, item_key=item_key,
        observed_value=observed_value, completeness_status=completeness,
        evidence_refs=ev, input_digest=input_digest, content_hash=content_hash,
        extractor_version=EXTRACTOR_VERSION, unknown_reason=unknown_reason,
        observed_at=observed_at, manifest_version=manifest_version)
