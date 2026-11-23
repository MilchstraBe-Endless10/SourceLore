#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读检索器：在 index_rows 上做元数据过滤，再读资产 payload 做结构化过滤。

★ 明确不宣称有全文检索或语义检索 —— index_rows **没有 text 列**。
★ SQL 固定为常量模板 + 参数绑定；**不接受**任何外部拼接的 SQL 字符串。
"""

import sys
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views"), str(_HERE.parent / "storage"),
           str(_HERE.parent / "lifecycle"), str(_HERE.parent / "trust")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import query_models as QM
import policy as TRUST

CLAIM_TYPE = "claim_candidate"
VERIF_TYPE = "claim_verification"
SNAPSHOT_TYPE = "repository_snapshot"   # ★ 实际资产名（不是 source_snapshot）

# 预算（题面 §12：不得无界遍历）
CANDIDATE_CAP = 200
EVIDENCE_CAP = 50

# 检索状态
OK = "OK"
TRUNCATED = "TRUNCATED"
EMPTY = "EMPTY"
RETRIEVAL_ERROR = "RETRIEVAL_ERROR"

E_INDEX_CORRUPT = "INDEX_CORRUPT"
E_ASSET_CORRUPT = "ASSET_CORRUPT"
E_PAYLOAD_MALFORMED = "PAYLOAD_MALFORMED"

# ★ 固定 SQL：只按元数据列过滤，绝不拼接外部字符串
_SQL_CLAIMS = (
    "SELECT asset_id, logical_identity, repository_id, commit_sha, asset_version "
    "FROM index_rows WHERE asset_type=? AND repository_id=? "
    "ORDER BY asset_version DESC, asset_id ASC LIMIT ?")


def _rows(store, sql, params) -> dict:
    try:
        return {"ok": True,
                "rows": [dict(r) for r in store.conn.execute(sql, params).fetchall()]}
    except Exception as e:
        return {"ok": False, "error": E_INDEX_CORRUPT,
                "detail": f"{type(e).__name__}: {e}"}


def _read_payload(store, asset_id) -> dict:
    got = store.get_asset(asset_id, verify=True)
    if not got.get("ok"):
        return {"ok": False, "error": E_ASSET_CORRUPT,
                "detail": got.get("error", "")}
    return {"ok": True, "payload": got["asset"].get("payload") or {},
            "asset_type": got["asset"].get("asset_type"),
            "repository_id": got["asset"].get("repository_id"),
            "content_hash": got["asset"].get("content_hash")}


def retrieve_claims(store, query: dict) -> dict:
    """按结构化条件检索 Claim 候选。

    ★ 只在 repository_id 上做索引级过滤；commit/path/claim_type 需读 payload。
    """
    cap = min(query.get("max_results") or 50, CANDIDATE_CAP)
    got = _rows(store, _SQL_CLAIMS,
                (CLAIM_TYPE, query["repository_id"], cap + 1))
    if not got["ok"]:
        return {"ok": False, "status": RETRIEVAL_ERROR,
                "error": got["error"], "detail": got["detail"],
                "candidates": [], "truncated": False}

    rows = got["rows"]
    truncated = len(rows) > cap
    rows = rows[:cap]

    kept, excluded = [], []
    for r in rows:
        p = _read_payload(store, r["asset_id"])
        if not p["ok"]:
            excluded.append({"asset_id": r["asset_id"], "reason": p["error"],
                             "detail": p["detail"]})
            continue
        pl = p["payload"]
        # 结构化过滤（不靠索引，读后判定）
        if query.get("commit_sha") and pl.get("commit_sha") != query["commit_sha"]:
            excluded.append({"asset_id": r["asset_id"],
                             "reason": "COMMIT_NOT_MATCH",
                             "detail": f"{pl.get('commit_sha')}"})
            continue
        if query.get("path") and pl.get("normalized_path") != query["path"]:
            excluded.append({"asset_id": r["asset_id"],
                             "reason": "PATH_NOT_MATCH",
                             "detail": pl.get("normalized_path")})
            continue
        if query.get("claim_type") and pl.get("claim_type") != query["claim_type"]:
            excluded.append({"asset_id": r["asset_id"],
                             "reason": "CLAIM_TYPE_NOT_MATCH",
                             "detail": pl.get("claim_type")})
            continue
        if str(p["repository_id"]) != str(query["repository_id"]):
            excluded.append({"asset_id": r["asset_id"],
                             "reason": "REPOSITORY_NOT_MATCH",
                             "detail": p["repository_id"]})
            continue
        kept.append({"asset_id": r["asset_id"],
                     "claim_id": pl.get("claim_id"),
                     "commit_sha": pl.get("commit_sha"),
                     "claim_type": pl.get("claim_type"),
                     "normalized_path": pl.get("normalized_path"),
                     "expected_exists": pl.get("expected_exists"),
                     "review_status": pl.get("review_status", "pending_review"),
                     "content_hash": p["content_hash"],
                     "payload": pl})

    # ★ 确定性排序（题面 §7 优先级链）
    kept = _rank(kept, query)
    status = TRUNCATED if truncated else (OK if kept else EMPTY)
    return {"ok": True, "status": status, "truncated": truncated,
            "candidate_count": len(rows), "kept": kept,
            "excluded": excluded, "cap": cap,
            "examined_boundary": cap,
            "note": ("结果集已截断：未出现在结果中的 Claim 不等于不存在"
                     if truncated else "")}


def _rank(kept: list, query: dict) -> list:
    """确定性排序：范围 > 仓库 > Commit > 类型 > 证据 > 稳定 ID。"""
    def key(c):
        return (
            0 if c.get("normalized_path") == query.get("path") else 1,
            0 if str(c.get("repository_id", query["repository_id"]))
                 == str(query["repository_id"]) else 1,
            0 if c.get("commit_sha") == query.get("commit_sha") else 1,
            0 if c.get("claim_type") == query.get("claim_type") else 1,
            0 if c.get("review_status") == "approved" else 1,
            str(c.get("claim_id") or ""),
            str(c.get("asset_id") or ""),
        )
    return sorted(kept, key=key)


def retrieve_verifications(store, claims: list, query: dict) -> dict:
    """为已选 Claim 取 Verification。

    ★ P0/D3：默认只读 B 层 current_view 采纳的裁决；历史版本不得混入当前 findings。
      当前视图没有裁决时明确排除（RETRIEVAL_EXCLUDED_NOT_CURRENT），不回退旧版本。
      历史裁决请走 policy.list_historical_verifications 的显式历史通道。
    """
    out, excluded = [], []
    current_verifs = TRUST.current_asset_ids(store, repository_id=query["repository_id"],
                                             asset_type=VERIF_TYPE)
    current_by_claim = {}
    for _lid, aid in current_verifs.items():
        p = _read_payload(store, aid)
        if not p["ok"]:
            continue
        cid = str(p["payload"].get("claim_id") or "")
        if cid:
            current_by_claim.setdefault(cid, (aid, p["payload"]))
    for c in claims:
        cid = str(c["claim_id"])
        hit = current_by_claim.get(cid)
        if hit is None:
            excluded.append({"claim_id": cid,
                             "reason": "RETRIEVAL_EXCLUDED_NOT_CURRENT",
                             "detail": "当前视图中没有该 Claim 的 Verification；历史裁决不作为当前结论"})
            continue
        aid, pl = hit
        found = {"asset_id": aid,
                 "verification_id": pl.get("verification_id"),
                 "status": pl.get("status"),
                 "reason_code": pl.get("reason_code"),
                 "fact_ids": [f for f in (pl.get("fact_ids") or []) if f],
                 "evidence_refs": list(pl.get("evidence_refs") or []),
                 "local_coverage_only": bool(pl.get("local_coverage_only")),
                 "evidence_refs_raw": list(pl.get("evidence_refs") or []),
                 "conflict_detected": bool(pl.get("conflict_detected")),
                 "rule_version": pl.get("rule_version"),
                 "content_hash": pl.get("content_hash"),
                 "source": "current",
                 "payload": pl}
        out.append({"claim": c, "verification": found})
    return {"ok": True, "status": OK, "pairs": out, "excluded": excluded}


_SQL_SNAPSHOTS = (
    "SELECT asset_id FROM index_rows WHERE asset_type=? AND repository_id=? "
    "ORDER BY asset_version DESC, asset_id ASC LIMIT ?")


def snapshot_completeness(store, repository_id, commit_sha,
                          cap: int = 20) -> dict:
    """★ 读该 Commit 的快照**真实** completeness_status。

    只信 EC 的 local_coverage_only 会漏判：EC 在 insufficient 路径下
    并不设该标记，但快照本身可能只是 PARTIAL。
    """
    got = _rows(store, _SQL_SNAPSHOTS, (SNAPSHOT_TYPE, repository_id, cap))
    if not got["ok"]:
        return {"ok": False, "error": got["error"], "detail": got["detail"]}
    statuses = {}
    for r in got["rows"]:
        p = _read_payload(store, r["asset_id"])
        if not p["ok"]:
            continue
        pl = p["payload"]
        if commit_sha and pl.get("commit_sha") != commit_sha:
            continue
        cs = pl.get("completeness_status")
        if cs:
            statuses[cs] = statuses.get(cs, 0) + 1
    worst = ("PARTIAL" if "PARTIAL" in statuses
             else (next(iter(statuses)) if len(statuses) == 1
                   else ("UNKNOWN" if statuses else "")))
    return {"ok": True, "completeness": worst, "by_status": statuses,
            "examined": len(got["rows"]), "cap": cap}


def retrieve_version_pair(store, query: dict) -> dict:
    """Q-C：两个 Commit 的 Claim/Verification 对照。"""
    a = dict(query); a["commit_sha"] = query["commit_sha"]
    b = dict(query); b["commit_sha"] = query["compare_commit_sha"]
    ra = retrieve_claims(store, a)
    rb = retrieve_claims(store, b)
    if not (ra["ok"] and rb["ok"]):
        return {"ok": False, "status": RETRIEVAL_ERROR,
                "detail": "任一 Commit 检索失败"}
    return {"ok": True, "status": OK, "commit_a": ra, "commit_b": rb}
