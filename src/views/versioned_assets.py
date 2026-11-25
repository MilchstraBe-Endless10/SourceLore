"""版本化权威资产读取（P2-B §2 固定 Commit 隔离）。

★ 为什么必须存在：
  派生/挖掘/问答三处各自读取 snapshot、正文、Claim、Verification，
  旧口径按 created_at 取"最新 snapshot"、其余资产不过滤 commit，导致
  指定历史 Commit 时混入其他版本的正文与证据（已在多版本夹具复现）。

★ 本模块是唯一的版本选择权威入口：
  - 指定 commit_sha  → 严格按该 Commit 选择 snapshot/正文/Claim/Verification；
                        缺失则如实返回缺失状态，绝不回退到别的版本填充。
  - 未指定 commit_sha → 走 B 层 current_view 当前指针（默认版本策略）；
                        current_view 缺失时回退 created_at 最新并标注来源，
                        保持对历史库的兼容。
  - 所有读取只走正式 Storage API / SQL 只读查询，不联网、不写库。

snapshot 的 commit_sha 存于 payload_json（assets.commit_sha 列在快照行为空），
故统一用 json_extract(payload_json, '$.commit_sha') 判定版本。
"""

import json
import sys
from pathlib import Path as _Path

# trust/policy.py 不在常规包路径，稳健注入（供 current_view 默认策略使用）
_TRUST_DIR = str(_Path(__file__).resolve().parents[1] / "trust")


def _trust_policy():
    if _TRUST_DIR not in sys.path:
        sys.path.insert(0, _TRUST_DIR)
    import importlib
    return importlib.import_module("policy")


# 版本选择来源标注
SELECT_PINNED = "PINNED_COMMIT"        # 调用方明确指定 Commit
SELECT_CURRENT_VIEW = "CURRENT_VIEW"   # 未指定，走当前指针
SELECT_FALLBACK_LATEST = "FALLBACK_LATEST"  # 当前指针缺失，兼容回退


def _payload(row):
    try:
        return json.loads(row["payload_json"])
    except Exception:
        return {}


def _commit_of(pl):
    return pl.get("commit_sha")


def select_snapshot(store, repository_id, commit_sha=None):
    """按 repository_id + 可选 commit_sha 选 snapshot。

    返回 (snapshot_payload, selection_meta)；无匹配返回 (None, meta)。
    """
    rid = str(repository_id)
    rows = store.conn.execute(
        "SELECT asset_id, payload_json, created_at FROM assets "
        "WHERE asset_type='repository_snapshot' AND repository_id=?",
        (rid,)).fetchall()
    if not rows:
        return None, {"selection": SELECT_PINNED if commit_sha else SELECT_CURRENT_VIEW,
                      "matched": False, "reason": "NO_SNAPSHOT"}

    parsed = [(r, _payload(r)) for r in rows]

    if commit_sha:
        for r, pl in parsed:
            if _commit_of(pl) == commit_sha:
                meta = {"selection": SELECT_PINNED, "matched": True,
                        "commit_sha": commit_sha, "snapshot_asset_id": r["asset_id"]}
                return pl, meta
        return None, {"selection": SELECT_PINNED, "matched": False,
                      "commit_sha": commit_sha, "reason": "COMMIT_NOT_FOUND"}

    # 默认策略：current_view 当前指针
    try:
        TRUST = _trust_policy()
        current = TRUST.current_asset_ids(store, repository_id=rid,
                                          asset_type="repository_snapshot")
        for _lid, aid in current.items():
            for r, pl in parsed:
                if r["asset_id"] == aid:
                    meta = {"selection": SELECT_CURRENT_VIEW, "matched": True,
                            "commit_sha": _commit_of(pl), "snapshot_asset_id": aid}
                    return pl, meta
    except Exception:
        pass

    # 兼容回退：created_at 最新（明确标注，避免被当成当前有效版本）
    r, pl = max(parsed, key=lambda x: (x[0]["created_at"] or ""))
    meta = {"selection": SELECT_FALLBACK_LATEST, "matched": True,
            "commit_sha": _commit_of(pl), "snapshot_asset_id": r["asset_id"],
            "reason": "CURRENT_VIEW_UNAVAILABLE"}
    return pl, meta


def load_versioned_assets(store, repository_id, commit_sha=None):
    """统一加载某版本的 snapshot/claims/verifications。

    返回 dict：
      ok, snapshot, claims, verifications, commit_sha, selection,
      coverage -- 如实记录各资产的版本过滤结果。
    """
    rid = str(repository_id)
    snapshot, sel = select_snapshot(store, rid, commit_sha)
    if snapshot is None:
        return {"ok": False, "reason": sel.get("reason"), "selection": sel,
                "repository_id": rid, "commit_sha": commit_sha}

    target_commit = commit_sha or _commit_of(snapshot)

    # Claims：严格按 commit 过滤（有 commit 字段）
    all_claims = [_payload(r) for r in store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type='claim_candidate' "
        "AND repository_id=?", (rid,)).fetchall()]
    if commit_sha:
        claims = [c for c in all_claims if _commit_of(c) == commit_sha]
        claims_dropped = len(all_claims) - len(claims)
    else:
        # 未指定 Commit：current_view 指向的 claim 身份
        claims = all_claims
        claims_dropped = 0

    claim_ids = {c.get("claim_id") for c in claims if c.get("claim_id")}

    # Verifications：无 commit 字段，靠 claim_id 关联到本版本 Claim；
    # 再按 current_view 当前指针过滤（P0 规则，历史裁决不混入）。
    all_verifs = [_payload(r) for r in store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type='claim_verification' "
        "AND repository_id=?", (rid,)).fetchall()]
    verifs = [v for v in all_verifs if v.get("claim_id") in claim_ids]
    verifs_dropped = len(all_verifs) - len(verifs)
    try:
        TRUST = _trust_policy()
        cur_v = set(TRUST.current_asset_ids(
            store, repository_id=rid, asset_type="claim_verification").values())
        if cur_v:
            kept = []
            for v in verifs:
                vid = v.get("verification_id") or v.get("logical_identity")
                row = store.conn.execute(
                    "SELECT asset_id FROM assets WHERE asset_type='claim_verification' "
                    "AND repository_id=? AND logical_identity=? "
                    "ORDER BY CAST(asset_version AS INTEGER) DESC LIMIT 1",
                    (rid, vid)).fetchone() if vid else None
                if row and row["asset_id"] in cur_v:
                    kept.append(v)
            verifs_dropped += len(verifs) - len(kept)
            verifs = kept
    except Exception:
        pass

    return {
        "ok": True,
        "repository_id": rid,
        "commit_sha": target_commit,
        "selection": sel,
        "snapshot": snapshot,
        "claims": claims,
        "verifications": verifs,
        "coverage": {
            "claims_total": len(all_claims),
            "claims_in_version": len(claims),
            "claims_dropped_by_version": claims_dropped,
            "verifications_total": len(all_verifs),
            "verifications_in_version": len(verifs),
            "verifications_dropped": verifs_dropped,
        },
    }


def captured_blobs(store, repository_id, commit_sha, data_root):
    """按固定 Commit 读取已捕获正文，返回 (texts, meta, coverage)。

    ★ 与 repo_miner._blob_texts 的区别：严格按 payload.commit_sha 过滤，
      同一 Commit 同一路径若有多条，按 content_sha256 确定性选取，
      绝不因写入顺序覆盖而混入别的版本正文。
    """
    import blob_content_store as BCS
    rid = str(repository_id)
    texts, meta = {}, {}
    rows = store.conn.execute(
        "SELECT asset_id, payload_json, created_at FROM assets "
        "WHERE asset_type='captured_blob_content' AND repository_id=?",
        (rid,)).fetchall()
    by_path = {}
    total = 0
    selection = SELECT_PINNED if commit_sha else SELECT_CURRENT_VIEW
    for r in rows:
        pl = _payload(r)
        total += 1
        if commit_sha and _commit_of(pl) != commit_sha:
            continue
        path = (pl.get("file_path") or pl.get("normalized_path") or pl.get("path"))
        digest = pl.get("content_sha256")
        if not path or not digest:
            continue
        # 同路径多版本：指定 Commit 时按 digest 字典序确定性选取；
        # 未指定时取 created_at 最新（同 current_view 默认口径），绝不拼接多版本正文。
        rank = ("0", digest) if commit_sha else (r["created_at"] or "", digest)
        cur = by_path.get(path)
        if cur is None or rank > cur[0]:
            by_path[path] = (rank, digest, pl)

    for path, (_rank, digest, pl) in sorted(by_path.items()):
        got = BCS.get_bytes(data_root=data_root, content_sha256=digest, verify=True)
        if not got.get("ok"):
            meta[path] = {"error": got.get("error"), "digest": digest,
                          "commit_sha": commit_sha}
            continue
        raw = got.get("raw") or b""
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        texts[path] = text
        meta[path] = {
            "digest": digest,
            "byte_length": got.get("byte_length"),
            "copy_permitted": pl.get("copy_permitted"),
            "distribution_allowed": pl.get("distribution_allowed"),
            "provenance_level": pl.get("provenance_level"),
            "git_blob_oid": pl.get("git_blob_oid"),
            "commit_sha": pl.get("commit_sha"),
            "content_asset_id": pl.get("content_asset_id"),
        }

    return texts, meta, {
        "captured_total": total,
        "captured_in_version": len(by_path),
        "captured_dropped": total - len(by_path),
        "commit_sha": commit_sha,
        "selection": selection,
    }
