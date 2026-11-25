#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D3-dev：来源真实性严格验证 + 可信补充来源解析。

设计纪律（不可放宽）：
  - 相同 Commit + Root Tree **不足以**证明相同仓库身份：Fork / 伪造远端可复制两者。
    本模块额外要求 GitHub 数字 ID 侧存在权威 subject_record(repository_display_name)
    且 resolved_repository 明确，并要求两侧 blob_refs 的 path→blob_sha 映射一致。
  - 只做只读判定；不合并 repository_id，不写 A 层，不联网。
  - 解析结果保留双方证据身份；本地库仅作为“补充知识源”，绝不冒充 GitHub 在线采集结果。
"""
import json
import re

_GITHUB_ID_RE = re.compile(r"^\d+$")
_SNAPSHOT_TYPE = "repository_snapshot"
_DISPLAY_KIND = "repository_display_name"


def _payload(row):
    try:
        raw = row["payload_json"]
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _rows(store, sql, params=()):
    """只读查询；临时用 sqlite3.Row，结束后恢复连接原 row_factory。

    ★ 绝不能把 store.conn.row_factory 永久改为 None：会污染后续所有正式查询
      （_load_assets 等期望 Row 的按列名访问）。
    """
    import sqlite3
    original = store.conn.row_factory
    try:
        store.conn.row_factory = sqlite3.Row
        return [dict(r) for r in store.conn.execute(sql, params).fetchall()]
    finally:
        store.conn.row_factory = original


def github_identity_evidence(store, repository_id: str) -> dict:
    """核对数字 ID 是否拥有权威 GitHub 身份记录（防伪造远端的最小锚点）。

    权威来源：A 层 subject_record，record_kind=repository_display_name，
    repository_id 与传入一致，requested/resolved repository 均为明确 owner/name。
    """
    rid = str(repository_id)
    if not _GITHUB_ID_RE.match(rid):
        return {"ok": False, "reason": "NOT_GITHUB_NUMERIC_ID", "repository_id": rid}
    rows = _rows(store,
        "SELECT asset_id, payload_json FROM assets WHERE asset_type='subject_record' "
        "AND repository_id=? AND logical_identity=?",
        (rid, "SL-REPONAME-" + rid))
    for row in rows:
        pl = _payload(row)
        if str(pl.get("record_kind")) != _DISPLAY_KIND:
            continue
        res = str(pl.get("resolved_repository") or "")
        req = str(pl.get("requested_repository") or "")
        if not res or "/" not in res or res.count("/") != 1:
            continue
        if req and req != res:  # 有 requested 时必须与 resolved 一致
            continue
        return {"ok": True, "repository_id": rid,
                "resolved_repository": res, "asset_id": row["asset_id"],
                "evidence": "A_LAYER_SUBJECT_RECORD"}
    return {"ok": False, "reason": "NO_AUTHORITATIVE_IDENTITY_RECORD", "repository_id": rid}


def snapshot_by_commit(store, repository_id: str, commit_sha: str) -> dict:
    """取该仓库该 commit 的当前快照 payload（优先 current_view）。"""
    rid = str(repository_id)
    rows = _rows(store,
        "SELECT asset_id, payload_json FROM assets WHERE asset_type=? AND repository_id=?",
        (_SNAPSHOT_TYPE, rid))
    current = set()
    for r in _rows(store,
        "SELECT cv.current_asset_id FROM current_view cv JOIN assets a "
        "ON a.asset_id=cv.current_asset_id WHERE cv.repository_id=? "
        "AND a.asset_type=?", (rid, _SNAPSHOT_TYPE)):
        current.add(r["current_asset_id"])
    pool = [r for r in rows if r["asset_id"] in current] or rows
    for r in pool:
        pl = _payload(r)
        if str(pl.get("commit_sha")) == str(commit_sha):
            pl = dict(pl)
            pl["asset_id"] = r["asset_id"]
            return pl
    return {}


def _blob_map(snapshot_payload: dict) -> dict:
    out = {}
    for b in (snapshot_payload.get("blob_refs") or []):
        if isinstance(b, dict) and b.get("path") and b.get("blob_sha"):
            out[str(b["path"])] = str(b["blob_sha"])
    return out


def verify_source_binding(store, *, github_id: str, local_id: str,
                          commit_sha: str) -> dict:
    """严格验证 GitHub ID 与本地补充来源是否指向同一内容。

    ★ 返回 ok=True 需同时满足：
      1. github_id 有权威身份记录（数字 ID + owner/name subject_record）；
      2. local_id 不是数字 GitHub ID（保持独立身份，未伪造）；
      3. 两侧 commit/root_tree 一致；
      4. 两侧 blob_refs 的 path→blob_sha 映射完全一致。
    任一不满足 → ok=False，且 reasons 给出确切原因。
    """
    reasons = []
    gid, lid = str(github_id), str(local_id)
    ident = github_identity_evidence(store, gid)
    if not ident.get("ok"):
        reasons.append("GITHUB_IDENTITY_UNVERIFIED:" + str(ident.get("reason")))
    if _GITHUB_ID_RE.match(lid):
        reasons.append("LOCAL_SOURCE_CLAIMS_GITHUB_ID")
    gh = snapshot_by_commit(store, gid, commit_sha)
    lo = snapshot_by_commit(store, lid, commit_sha)
    if not gh:
        reasons.append("GITHUB_SNAPSHOT_MISSING")
    if not lo:
        reasons.append("LOCAL_SNAPSHOT_MISSING")
    if gh and lo:
        if str(gh.get("commit_sha")) != str(lo.get("commit_sha")):
            reasons.append("COMMIT_MISMATCH")
        if not gh.get("root_tree_sha") or gh.get("root_tree_sha") != lo.get("root_tree_sha"):
            reasons.append("ROOT_TREE_MISMATCH")
        gb, lb = _blob_map(gh), _blob_map(lo)
        if not gb:
            reasons.append("GITHUB_BLOB_REFS_EMPTY")
        # GitHub 根层 blob_refs 必须是本地递归 blob_map 的子集且哈希一致：
        # 同内容时根层是递归的子集；Fork/伪造会使某路径哈希对不上。
        conflict = {p: (gb[p], lb.get(p)) for p in gb if lb.get(p) != gb[p]}
        if conflict:
            reasons.append("BLOB_HASH_CONFLICT:%s" % ",".join(sorted(conflict)[:5]))
    return {
        "ok": not reasons,
        "reasons": reasons,
        "github_id": gid,
        "resolved_repository": ident.get("resolved_repository"),
        "local_id": lid,
        "commit_sha": str(commit_sha),
        "root_tree_sha": gh.get("root_tree_sha") if gh else None,
        "blob_paths_compared": len(_blob_map(gh)) if gh else 0,
        "blob_subset_verified": bool(gh and lo and all(
            _blob_map(lo).get(p) == s for p, s in _blob_map(gh).items())),
        "github_asset_id": gh.get("asset_id") if gh else None,
        "local_asset_id": lo.get("asset_id") if lo else None,
        "note": "commit+root_tree 相同不是身份证明；此处叠加权威 ID 记录与 blob 映射一致性。",
    }


def resolve_supplement(store, github_id: str, commit_sha: str = None) -> dict:
    """从 GitHub ID 解析其**经严格验证**的本地补充来源。

    仅当 repo_bindings 中存在以该 GitHub ID 为 repository_id、
    evidence_ref 标记 verified 的绑定，且通过 verify_source_binding 复核时返回。
    """
    gid = str(github_id)
    # 1) 该 GitHub ID 绑定的所有 subject（内容锚点）
    subjects = [r["subject_id"] for r in _rows(store,
        "SELECT subject_id FROM repo_bindings WHERE repository_id=?", (gid,))]
    if not subjects:
        return {"ok": False, "github_id": gid, "supplements": [],
                "note": "无绑定记录"}
    # 2) 同一 subject 下所有"非数字 GitHub ID"的 repository_id = 本地补充源
    placeholders = ",".join("?" for _ in subjects)
    rows = _rows(store,
        "SELECT subject_id, repository_id, evidence_ref FROM repo_bindings "
        "WHERE subject_id IN (%s) AND repository_id!=?" % placeholders,
        tuple(subjects) + (gid,))
    supplements = []
    for r in rows:
        ev = str(r["evidence_ref"] or "")
        if "source_verified=1" not in ev:
            continue
        local_id = str(r["repository_id"])
        if _GITHUB_ID_RE.match(local_id):
            continue  # 绝不把另一个数字 ID 当补充源
        cid = commit_sha
        if not cid:
            snap = snapshot_by_commit(store, gid, "") or {}
            # 取该 ID 快照的首个 commit
            rr = _rows(store, "SELECT commit_sha FROM assets WHERE asset_type=? "
                              "AND repository_id=? AND commit_sha IS NOT NULL LIMIT 1",
                       (_SNAPSHOT_TYPE, gid))
            cid = rr[0]["commit_sha"] if rr else None
        v = verify_source_binding(store, github_id=gid, local_id=local_id,
                                  commit_sha=cid or "")
        if v.get("ok"):
            supplements.append({"repository_id": local_id, "commit_sha": str(cid or ""),
                                "evidence_ref": ev})
    return {
        "ok": bool(supplements),
        "github_id": gid,
        "supplements": supplements,
        "note": "所有补充来源均保留原始证据身份；本地库不冒充 GitHub 在线采集。",
    }
