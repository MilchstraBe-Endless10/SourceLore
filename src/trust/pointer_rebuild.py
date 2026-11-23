#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段D：当前视图（B 层）指针重建。

只写 current_view，不碰 A 层 assets、不改 C 层索引内容。
为每个通过身份准入的 logical_identity 选择最高版本的合法资产作为当前指针；
污染/占位资产永不入选。幂等：重复运行不产生新版本。
"""
import sys, json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import policy as TRUST


def _trusted_snapshot_commits(conn):
    trusted = {}
    for r in conn.execute(
            "SELECT repository_id, payload_json FROM assets "
            "WHERE asset_type='repository_snapshot'").fetchall():
        try:
            pl = json.loads(r["payload_json"] or "{}")
        except Exception:
            continue
        cs = pl.get("commit_sha")
        if cs:
            trusted.setdefault(str(r["repository_id"]), set()).add(cs)
    return trusted


def _now():
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def rebuild_current_pointers(store, *, dry_run=False):
    """重建 B 层当前指针。返回报告。只 INSERT/UPDATE current_view。"""
    conn = store.conn
    trusted = _trusted_snapshot_commits(conn)
    added, repointed, kept, rejected = [], [], [], []

    rows = conn.execute(
        "SELECT asset_id, asset_type, logical_identity, repository_id, asset_version, payload_json "
        "FROM assets ORDER BY repository_id, logical_identity, CAST(asset_version AS INTEGER) DESC, asset_id ASC"
    ).fetchall()

    # 按 (repo, logical_identity) 分组，取第一个通过身份准入的（已按版本降序）
    best = {}
    for r in rows:
        key = (str(r["repository_id"]), str(r["logical_identity"]))
        if key in best:
            continue
        try:
            pl = json.loads(r["payload_json"] or "{}") if r["payload_json"] else {}
        except Exception:
            rejected.append({"asset_id": r["asset_id"], "reason": "PAYLOAD_MALFORMED"})
            continue
        chk = TRUST.identity_check(
            pl, repository_id=str(r["repository_id"]),
            snapshot_commits=trusted.get(str(r["repository_id"]), set()))
        if not chk["ok"]:
            rejected.append({"asset_id": r["asset_id"],
                             "logical_identity": r["logical_identity"],
                             "reasons": chk["reasons"]})
            continue
        best[key] = r

    for (repo, lid), r in best.items():
        cur = conn.execute(
            "SELECT current_asset_id, pointer_version FROM current_view "
            "WHERE repository_id=? AND logical_identity=?", (repo, lid)).fetchone()
        if cur is None:
            if not dry_run:
                conn.execute(
                    "INSERT INTO current_view(logical_identity, repository_id, current_asset_id, "
                    "pointer_version, last_known_good, updated_at) VALUES(?,?,?,1,?,?)",
                    (lid, repo, r["asset_id"], r["asset_id"], _now()))
            added.append({"repository_id": repo, "logical_identity": lid,
                          "asset_id": r["asset_id"], "asset_type": r["asset_type"]})
        elif cur["current_asset_id"] == r["asset_id"]:
            kept.append(lid)
        else:
            # 当前指针指向非最高合法资产：推进到合法版本（不改 A）
            if not dry_run:
                conn.execute(
                    "UPDATE current_view SET current_asset_id=?, pointer_version=?, "
                    "last_known_good=current_asset_id, updated_at=? "
                    "WHERE repository_id=? AND logical_identity=?",
                    (r["asset_id"], int(cur["pointer_version"]) + 1, _now(), repo, lid))
            repointed.append({"repository_id": repo, "logical_identity": lid,
                              "from": cur["current_asset_id"], "to": r["asset_id"]})

    if not dry_run:
        conn.commit()
    return {"ok": True, "dry_run": bool(dry_run),
            "added_count": len(added), "repointed_count": len(repointed),
            "kept_count": len(kept), "rejected_count": len(rejected),
            "added": added, "repointed": repointed, "rejected": rejected[:50]}
