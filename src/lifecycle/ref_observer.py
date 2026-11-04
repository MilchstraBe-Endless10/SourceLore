#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可信 Ref 版本观测。

契约：SL-CAP-0043（更新触发）、SL-CAP-0045（外部可变来源与时效）。

**Lifecycle 不直接抓取 GitHub。** 复用 Collector 已有的受控获取与 Commit 解析
（`GitHubClient.commit_for_ref`）—— 它是唯一合法的"把 Ref 解析成 Commit"的地方。

铁律：
  O1 Commit 必须经真实解析或可信持久化记录证明
  O2 保留原始请求 Ref
  O3 不把 Branch 名当 Commit
  O4 不把 Tree SHA 当 Commit SHA
  O5 不凭时间戳宣布版本更新
  O6 失败的 Ref 解析不得生成虚假新 HEAD
  O7 观测记录与知识验证历史分离
"""

import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "collector")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lc_models as L

COLLECTOR_VERSION_DEFAULT = "sourcelore-collector/1.0.0"

PROV_REAL_LIVE_API = "REAL_LIVE_API"
PROV_HISTORICAL = "HISTORICAL_REAL_DATA"
PROV_SYNTHETIC = "SYNTHETIC_FIXTURE"
PROVENANCE_LEVELS = frozenset({PROV_REAL_LIVE_API, PROV_HISTORICAL, PROV_SYNTHETIC})


def observe_ref_via_collector(client, *, owner: str, name: str,
                              repository_id: str, requested_ref: str,
                              ref_kind: str = L.REF_KIND_BRANCH,
                              retrieval_scope: str = "full_tree_enumeration",
                              observed_at: str = "",
                              collector_version: str = COLLECTOR_VERSION_DEFAULT
                              ) -> L.RefObservation:
    """用 Collector 的受控客户端真实解析 Ref → Commit。

    这是**唯一**允许产生 REAL_LIVE_API 级别观测的路径。
    """
    resp = client.commit_for_ref(owner, name, requested_ref)

    if not getattr(resp, "ok", False):
        err = getattr(resp, "error", None)
        code = getattr(err, "error_code", "OBSERVATION_FAILED")
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=retrieval_scope,
            observed_at=observed_at, collector_version=collector_version,
            failure_reason=_map_failure(code),
            provenance=PROV_REAL_LIVE_API,
            evidence_ref=_evidence_ref(owner, name, requested_ref, code))

    data = resp.data or {}
    sha = data.get("sha")

    if not L.is_commit_sha(sha):
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=retrieval_scope,
            observed_at=observed_at, collector_version=collector_version,
            failure_reason=L.U_COMMIT_MALFORMED,
            provenance=PROV_REAL_LIVE_API,
            evidence_ref=_evidence_ref(owner, name, requested_ref,
                                       "MALFORMED_SHA"))

    # ★ O4 加强：40 位十六进制还不足以证明它是 **commit**。
    # GitHub 的 Tree SHA 同样是 40 位十六进制（本项目在 P1C 实测过
    # root_tree_sha=b4eecafa…）。/commits/{ref} 的响应是 Commit 对象，
    # 必带 "commit" 子对象（含 tree/author）。缺它就不是 commit 形状。
    if not _looks_like_commit_object(data):
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=retrieval_scope,
            observed_at=observed_at, collector_version=collector_version,
            failure_reason=L.U_NOT_A_COMMIT_OBJECT,
            provenance=PROV_REAL_LIVE_API,
            evidence_ref=_evidence_ref(owner, name, requested_ref,
                                       "NOT_A_COMMIT_OBJECT"))

    return _ok_observation(
        repository_id=repository_id, requested_ref=requested_ref,
        ref_kind=ref_kind, retrieval_scope=retrieval_scope,
        resolved_commit_sha=sha, observed_at=observed_at,
        collector_version=collector_version, provenance=PROV_REAL_LIVE_API,
        evidence_ref=_evidence_ref(owner, name, requested_ref, "RESOLVED"),
        source_snapshot_ref=None)


def observe_ref_from_snapshot(*, snapshot_asset: dict, repository_id: str,
                              requested_ref: str,
                              ref_kind: str = L.REF_KIND_BRANCH,
                              observed_at: str = "",
                              provenance_level: str = PROV_HISTORICAL
                              ) -> L.RefObservation:
    """从**已持久化的快照资产**构造观测（历史真实数据回放）。

    ★ 关键约束（见 F2_P3A_REF_OBSERVATION_AUDIT）：
    snapshot 的 identity **不含 requested_ref**，所以不能仅凭快照存在
    就宣称"该 Ref 当时指向该 Commit"。必须满足：
      快照的内容载荷记录了 requested_ref，且它与本次观测的 requested_ref 一致。
    否则返回 UNKNOWN（REF_MISMATCH），不产生假观测。
    """
    if provenance_level not in PROVENANCE_LEVELS:
        raise ValueError(f"非法 provenance_level: {provenance_level!r}")

    p = (snapshot_asset or {}).get("payload") or {}
    scoped_ref = p.get("requested_ref")
    commit = p.get("commit_sha")
    scope = p.get("retrieval_scope") or "full_tree_enumeration"
    cver = p.get("collector_version") or COLLECTOR_VERSION_DEFAULT

    if str(p.get("repository_id")) != str(repository_id):
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=scope,
            observed_at=observed_at, collector_version=cver,
            failure_reason=L.U_REPO_MISMATCH, provenance=provenance_level,
            evidence_ref="snapshot:repo_mismatch")

    if scoped_ref != requested_ref:
        # ★ 快照没记录这个 Ref → 不能说该 Ref 解析成了这个 Commit
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=scope,
            observed_at=observed_at, collector_version=cver,
            failure_reason=L.U_REF_MISMATCH, provenance=provenance_level,
            evidence_ref="snapshot:ref_mismatch")

    if not L.is_commit_sha(commit):
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=scope,
            observed_at=observed_at, collector_version=cver,
            failure_reason=L.U_COMMIT_MALFORMED, provenance=provenance_level,
            evidence_ref="snapshot:malformed_commit")

    return _ok_observation(
        repository_id=repository_id, requested_ref=requested_ref,
        ref_kind=ref_kind, retrieval_scope=scope, resolved_commit_sha=commit,
        observed_at=observed_at, collector_version=cver,
        provenance=provenance_level, evidence_ref="snapshot:resolved",
        source_snapshot_ref=(snapshot_asset or {}).get("asset_id"))


def observe_ref_from_record(*, record: dict, repository_id: str,
                            requested_ref: str,
                            ref_kind: str = L.REF_KIND_BRANCH,
                            retrieval_scope: str = "full_tree_enumeration",
                            observed_at: str = "",
                            collector_version: str = COLLECTOR_VERSION_DEFAULT
                            ) -> L.RefObservation:
    """从**真实采集执行记录**构造可信观测（HISTORICAL_REAL_DATA）。

    ★ 为什么不能用快照：快照的 identity 与 payload 都**不含 requested_ref**
    （见 F2_P3A_REF_OBSERVATION_AUDIT），无法证明"该 Ref 指向该 Commit"。

    而采集执行记录（如 F2_P1C_REAL_GITHUB.json）同时保存了
    `requested_ref` 与 `commit_sha`，且该 commit 来自 /commits/{ref} 的真实响应，
    因此它是合法的 Ref→Commit 对位证据。
    """
    rid = record.get("repository_id")
    ref = record.get("requested_ref")
    commit = record.get("commit_sha")

    if str(rid) != str(repository_id):
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=retrieval_scope,
            observed_at=observed_at, collector_version=collector_version,
            failure_reason=L.U_REPO_MISMATCH, provenance=PROV_HISTORICAL,
            evidence_ref="record:repo_mismatch")

    if ref != requested_ref:
        # ★ 执行记录对应的是别的 Ref → 不能说它证明了本次 Ref
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=retrieval_scope,
            observed_at=observed_at, collector_version=collector_version,
            failure_reason=L.U_REF_MISMATCH, provenance=PROV_HISTORICAL,
            evidence_ref="record:ref_mismatch")

    if not L.is_commit_sha(commit):
        return _failed_observation(
            repository_id=repository_id, requested_ref=requested_ref,
            ref_kind=ref_kind, retrieval_scope=retrieval_scope,
            observed_at=observed_at, collector_version=collector_version,
            failure_reason=L.U_COMMIT_MALFORMED, provenance=PROV_HISTORICAL,
            evidence_ref="record:malformed_commit")

    return _ok_observation(
        repository_id=repository_id, requested_ref=requested_ref,
        ref_kind=ref_kind, retrieval_scope=retrieval_scope,
        resolved_commit_sha=commit, observed_at=observed_at,
        collector_version=collector_version, provenance=PROV_HISTORICAL,
        evidence_ref="record:resolved", source_snapshot_ref=None)


def _ok_observation(*, repository_id, requested_ref, ref_kind, retrieval_scope,
                    resolved_commit_sha, observed_at, collector_version,
                    provenance, evidence_ref, source_snapshot_ref):
    oid = L.make_observation_id(
        repository_id=repository_id, requested_ref=requested_ref,
        ref_kind=ref_kind, resolved_commit_sha=resolved_commit_sha,
        observation_status=L.OBS_OK, collector_version=collector_version)
    digest = L.sha256_of({"kind": "ref_observation", "id": oid,
                          "payload": {"repo": str(repository_id), "ref": requested_ref,
                                      "commit": resolved_commit_sha}})
    return L.RefObservation(
        observation_id=oid, repository_id=str(repository_id),
        requested_ref=requested_ref, ref_kind=ref_kind,
        resolved_commit_sha=resolved_commit_sha,
        source_snapshot_ref=source_snapshot_ref,
        retrieval_scope=retrieval_scope, observation_status=L.OBS_OK,
        evidence_refs=[{"kind": "ref_resolution", "ref": evidence_ref,
                        "requested_ref": requested_ref,
                        "resolved_commit_sha": resolved_commit_sha, "at": observed_at}],
        collector_version=collector_version, input_digest=digest,
        observed_at=observed_at, provenance_level=provenance)


def _failed_observation(*, repository_id, requested_ref, ref_kind,
                        retrieval_scope, observed_at, collector_version,
                        failure_reason, provenance, evidence_ref):
    # ★ O6：失败观测 resolved_commit_sha 恒为 None —— 绝不伪造新 HEAD
    oid = L.make_observation_id(
        repository_id=repository_id, requested_ref=requested_ref,
        ref_kind=ref_kind, resolved_commit_sha=None,
        observation_status=L.OBS_FAILED, collector_version=collector_version)
    digest = L.sha256_of({"kind": "ref_observation_failed", "id": oid,
                          "reason": failure_reason})
    return L.RefObservation(
        observation_id=oid, repository_id=str(repository_id),
        requested_ref=requested_ref, ref_kind=ref_kind,
        resolved_commit_sha=None, source_snapshot_ref=None,
        retrieval_scope=retrieval_scope,
        observation_status=L.OBS_FAILED,
        evidence_refs=[{"kind": "ref_resolution_failed", "ref": evidence_ref,
                        "failure_reason": failure_reason, "at": observed_at}],
        collector_version=collector_version, input_digest=digest,
        observed_at=observed_at, provenance_level=provenance,
        failure_reason=failure_reason)


def _looks_like_commit_object(data: dict) -> bool:
    """判断响应是否是 Commit 对象（而非 Tree/Blob 对象）。

    Tree 对象形如 {"sha":..., "tree":[...], "truncated":...}
    Blob 对象形如 {"sha":..., "content":..., "encoding":...}
    Commit 对象必须有 "commit" 子对象（内含 tree.sha）。

    只靠"40 位十六进制"无法区分 —— 这正是 P1C 踩过的坑。
    """
    if not isinstance(data, dict):
        return False
    inner = data.get("commit")
    if not isinstance(inner, dict):
        return False
    tree = inner.get("tree")
    if not isinstance(tree, dict):
        return False
    return L.is_commit_sha(tree.get("sha"))


def _map_failure(code: str) -> str:
    """把 Collector 的错误码映射为 Lifecycle 的失败原因。

    ★ 题面情况 G：404/403/网络失败/限流**不得统一解释成"已删除"**。
    """
    return {
        "RATE_LIMITED": L.U_RATE_LIMITED,
        "SECONDARY_RATE_LIMITED": L.U_RATE_LIMITED,
        "PERMISSION_DENIED": L.U_PERMISSION_DENIED,
        "AUTH_FAILED": L.U_PERMISSION_DENIED,
        "REPO_NOT_FOUND": L.U_REF_UNAVAILABLE,
        "NETWORK_TIMEOUT": L.U_OBSERVATION_FAILED,
        "SERVER_ERROR": L.U_OBSERVATION_FAILED,
        "MALFORMED_RESPONSE": L.U_OBSERVATION_FAILED,
        "BUDGET_EXCEEDED": L.U_OBSERVATION_FAILED,
    }.get(code, L.U_OBSERVATION_FAILED)


def _evidence_ref(owner, name, ref, outcome):
    return f"github:/repos/{owner}/{name}/commits/{ref}#{outcome}"
