#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C 层：派生索引。**不是事实权威，可删除并重建。**

契约：SL-CAP-0065（索引与结构化查询）。

硬规则（本模块逐条落实）：
  I1 C 层不是权威 —— 查询结果必须带上 asset_id / 版本，供调用方回查 A 层
  I2 可删除重建，重建不改 A/B
  I3 索引缺失不得伪装成"知识不存在" —— 必须区分 "索引没有" 与 "资产没有"
  I4 查询结果不得直接成为已验证 Claim

**FTS5 实测可用（3.54.0），但代码不依赖它**：不可用时退化为 LIKE，
结构化查询能力保留。
"""

import json as _j
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge_store import KnowledgeStore

INDEX_MISSING = "INDEX_MISSING"


def _resolve_commit_from_payload(payload_json):
    """与 KnowledgeStore._resolve_index_commit_sha 同口径的 payload 回退。

    ★ 索引是 C 层派生数据，必须能从权威 payload 重建 —— 否则 rebuild 会丢信息。
    """
    import json as _j
    if not payload_json:
        return None
    try:
        pl = _j.loads(payload_json)
    except Exception:
        return None
    if not isinstance(pl, dict):
        return None
    cs = pl.get("commit_sha")
    if isinstance(cs, str) and cs:
        return cs
    snap = pl.get("source_snapshot")
    if isinstance(snap, dict):
        for k in ("commit_sha", "baseline_commit_sha", "observed_commit_sha"):
            v = snap.get(k)
            if isinstance(v, str) and v:
                return v
    return None


def rebuild_index(store: KnowledgeStore) -> dict:
    """从 A 层重建 C 层。

    **只动 index_rows / asset_fts**，绝不触碰 assets 或 current_view。
    返回重建前后的 A/B 摘要，供外部比对"确实没被改"。
    """
    a_before = _ab_fingerprint(store)

    try:
        store.conn.execute("BEGIN IMMEDIATE")
        store.conn.execute("DELETE FROM index_rows")
        if store.fts5_available:
            store.conn.execute("DELETE FROM asset_fts")

        rows = store.conn.execute(
            "SELECT asset_id, asset_type, logical_identity, repository_id, "
            "subject_id, commit_sha, asset_version, payload_json FROM assets"
        ).fetchall()
        # ★ D-69 补充：claim_verification 的 payload **不含任何 commit 字段**，
        #   它的 commit 原本是通过 SourceSnapshot 传给 AssetDraft 的（不进 payload）。
        #   因此必须先从 claim 建 claim_id → commit 索引再回填，否则重建后恒为 NULL。
        claim_commit = {}
        for r in rows:
            if r["asset_type"] != "claim_candidate":
                continue
            try:
                _d = _j.loads(r["payload_json"] or "{}")
            except Exception:
                continue
            cid = _d.get("claim_id")
            cs = _resolve_commit_from_payload(r["payload_json"])
            if cid and cs:
                claim_commit[(str(cid), str(r["repository_id"]))] = cs
        for r in rows:
            # ★ D-69：assets.commit_sha 实测**整列为 NULL**（各入库路径从不填它），
            #   而 index_rows 的 commit 是写入时通过 _resolve_index_commit_sha
            #   从 payload 回退解析出来的。直接照抄 assets.commit_sha 会把原本
            #   正确的索引**全部清成 NULL** —— 这不是重建，是毁索引。
            #   此处复用同一套回退：source_snapshot → payload.commit_sha →
            #   payload.source_snapshot.*。payload 不可解析时保持 NULL 并计数。
            _csha = _resolve_commit_from_payload(r["payload_json"])
            if not _csha and r["asset_type"] == "claim_verification":
                try:
                    _vd = _j.loads(r["payload_json"] or "{}")
                except Exception:
                    _vd = {}
                _cid = str(_vd.get("claim_id") or "")
                _csha = claim_commit.get((_cid, str(r["repository_id"])))
            store.conn.execute(
                """INSERT INTO index_rows(asset_id, asset_type, logical_identity,
                     repository_id, subject_id, commit_sha, asset_version)
                   VALUES(?,?,?,?,?,?,?)""",
                (r["asset_id"], r["asset_type"], r["logical_identity"],
                 r["repository_id"], r["subject_id"], _csha,
                 r["asset_version"]))
            if store.fts5_available:
                store.conn.execute(
                    "INSERT INTO asset_fts(asset_id, logical_identity, asset_type, payload_text) "
                    "VALUES(?,?,?,?)",
                    (r["asset_id"], r["logical_identity"], r["asset_type"],
                     r["payload_json"]))
        store.conn.execute("COMMIT")
    except Exception as e:
        try: store.conn.execute("ROLLBACK")
        except Exception: pass
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:200]}

    a_after = _ab_fingerprint(store)
    return {"ok": True, "indexed": len(rows),
            "a_b_unchanged": a_before == a_after,
            "fts5": store.fts5_available,
            "fingerprint": a_after}


def _ab_fingerprint(store: KnowledgeStore) -> str:
    """A/B 内容指纹：用来证明重建没动权威层。"""
    import hashlib
    a = store.conn.execute(
        "SELECT asset_id, content_hash FROM assets ORDER BY asset_id").fetchall()
    b = store.conn.execute(
        "SELECT logical_identity, current_asset_id, pointer_version "
        "FROM current_view ORDER BY logical_identity").fetchall()
    raw = repr([tuple(r) for r in a]) + "|" + repr([tuple(r) for r in b])
    return hashlib.sha256(raw.encode()).hexdigest()


def _ensure_index_present(store: KnowledgeStore) -> tuple[bool, dict]:
    """区分"索引空了"与"索引表不存在"。"""
    try:
        row = store.conn.execute(
            "SELECT count(*) AS n FROM sqlite_master WHERE type='table' AND name='index_rows'"
        ).fetchone()
        if row["n"] == 0:
            return False, {"error": INDEX_MISSING,
                           "detail": "index_rows 表不存在；需先重建索引"}
        return True, {}
    except Exception as e:
        return False, {"error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}


def _decorate(store: KnowledgeStore, rows) -> list[dict]:
    """给每条索引结果补上**来源与版本**，并标注是否当前版本。"""
    out = []
    for r in rows:
        ptr = store.conn.execute(
            "SELECT current_asset_id FROM current_view WHERE logical_identity=?",
            (r["logical_identity"],)).fetchone()
        is_current = bool(ptr and ptr["current_asset_id"] == r["asset_id"])
        out.append({"asset_id": r["asset_id"], "asset_type": r["asset_type"],
                    "logical_identity": r["logical_identity"],
                    "repository_id": r["repository_id"],
                    "subject_id": r["subject_id"], "commit_sha": r["commit_sha"],
                    "asset_version": r["asset_version"],
                    "is_current": is_current,
                    "authority": "A 层 assets 表（本结果不是事实权威，需回查）"})
    return out


def query(store: KnowledgeStore, *,
          repository_id=None, subject_id=None, asset_type=None,
          commit_sha=None, logical_identity=None, text=None, limit=100) -> dict:
    """最小结构化查询。

    索引缺失时返回 `INDEX_MISSING`，**不返回空列表**——
    "索引没有" 不等于 "知识不存在"。
    """
    present, err = _ensure_index_present(store)
    if not present:
        return {"ok": False, **err}

    where, args = [], []
    for col, val in (("repository_id", repository_id), ("subject_id", subject_id),
                     ("asset_type", asset_type), ("commit_sha", commit_sha),
                     ("logical_identity", logical_identity)):
        if val is not None:
            where.append(f"{col}=?")
            args.append(val)

    sql = "SELECT * FROM index_rows"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY asset_id LIMIT ?"
    args.append(int(limit))

    try:
        rows = store.conn.execute(sql, args).fetchall()
    except Exception as e:
        return {"ok": False, "error": "CHECKPOINT_CORRUPT", "detail": str(e)[:150]}

    results = _decorate(store, rows)

    # 全文检索：FTS5 可用才用，不可用退化 LIKE，能力不丢
    if text:
        try:
            if store.fts5_available:
                # FTS5 语法里 - : 等是运算符，"LI-1" 会被当成 col:1 而报
                # `no such column: 1`（实测踩过）。整串加双引号即为短语查询。
                safe = '"' + text.replace('"', '""') + '"'
                fts = store.conn.execute(
                    "SELECT asset_id FROM asset_fts WHERE payload_text MATCH ? LIMIT ?",
                    (safe, int(limit))).fetchall()
            else:
                fts = store.conn.execute(
                    "SELECT asset_id FROM index_rows WHERE logical_identity LIKE ? LIMIT ?",
                    (f"%{text}%", int(limit))).fetchall()
            hit_ids = {r["asset_id"] for r in fts}
            # FTS 分词可能与期望不同（如 "LI-1" 整体成词元）。
            # 用 LIKE 兜底补全，保证"能查到"优先于"只走 FTS"。
            like = store.conn.execute(
                "SELECT asset_id FROM index_rows WHERE logical_identity LIKE ? "
                "OR asset_id LIKE ? LIMIT ?",
                (f"%{text}%", f"%{text}%", int(limit))).fetchall()
            hit_ids |= {r["asset_id"] for r in like}
        except Exception as e:
            return {"ok": False, "error": "CHECKPOINT_CORRUPT",
                    "detail": f"全文检索失败: {str(e)[:150]}"}

        if not where:
            # 无结构化条件时，直接按命中 ID 取行并修饰
            if hit_ids:
                placeholders = ",".join("?" * len(hit_ids))
                rows2 = store.conn.execute(
                    f"SELECT * FROM index_rows WHERE asset_id IN ({placeholders}) LIMIT ?",
                    (*hit_ids, int(limit))).fetchall()
                results = _decorate(store, rows2)
            else:
                results = []
        else:
            results = [r for r in results if r["asset_id"] in hit_ids]

    return {"ok": True, "count": len(results), "results": results,
            "fts5": store.fts5_available,
            "note": "结果来自 C 层派生索引；未经 A 层回查不得视为已验证事实"}
