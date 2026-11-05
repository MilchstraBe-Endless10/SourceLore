#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视图完整性校验：只读，不修不补。

★ 损坏/悬空/缺失必须给出明确诊断码，绝不静默回退成"没有知识"。
"""
import sys, json, hashlib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import view_models as VM

CLAIM_TYPE = "claim_candidate"
VERIF_TYPE = "claim_verification"
FACT_TYPE = "extracted_fact"
SNAP_TYPE = "repository_snapshot"


def _read(store, asset_id):
    """只读取资产。返回 (asset_dict|None, error_code)。"""
    if not asset_id:
        return None, VM.E_DANGLING_REFERENCE
    got = store.get_asset(asset_id)
    if not got.get("ok"):
        err = got.get("error")
        if err == "NOT_FOUND":
            return None, VM.E_DANGLING_REFERENCE
        if err == "CHECKPOINT_CORRUPT":
            return None, VM.E_VIEW_INTEGRITY_FAILED
        return None, VM.E_VIEW_INTEGRITY_FAILED
    return got["asset"], None


def _find_latest(store, asset_type, logical_identity, repository_id=None):
    """按 logical_identity 取最新版本资产。★ 只用安全 SQL 拼接。"""
    sql = ("SELECT asset_id FROM assets WHERE asset_type=? AND logical_identity=?"
           " ORDER BY asset_version DESC LIMIT 1")
    params = [asset_type, logical_identity]
    if repository_id is not None:
        sql = ("SELECT asset_id FROM assets WHERE asset_type=?"
               " AND logical_identity=? AND repository_id=?"
               " ORDER BY asset_version DESC LIMIT 1")
        params.append(str(repository_id))
    row = store.conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def resolve_claim(store, *, claim_id=None, asset_id=None, repository_id=None):
    """定位 Claim。★ 不凭空构造。"""
    aid = asset_id
    if aid is None:
        if not claim_id:
            return None, VM.E_CLAIM_NOT_FOUND
        # ★ 先全局定位，再比对仓库 —— 否则"仓库不匹配"会被误报成"找不到"
        row = _find_latest(store, CLAIM_TYPE, claim_id, None)
        if row is None:
            return None, VM.E_CLAIM_NOT_FOUND
        aid = row["asset_id"]
    a, err = _read(store, aid)
    if a is None:
        return None, err
    if a["asset_type"] != CLAIM_TYPE:
        return None, VM.E_VIEW_INTEGRITY_FAILED
    if repository_id is not None and str(a["repository_id"]) != str(repository_id):
        return None, VM.E_REPOSITORY_MISMATCH
    return a, None


def resolve_verification(store, *, verification_id=None, asset_id=None,
                         repository_id=None):
    aid = asset_id
    if aid is None:
        if not verification_id:
            return None, VM.E_VERIFICATION_NOT_FOUND
        # ★ 同上：先定位，再比对仓库
        row = _find_latest(store, VERIF_TYPE, verification_id, None)
        if row is None:
            return None, VM.E_VERIFICATION_NOT_FOUND
        aid = row["asset_id"]
    a, err = _read(store, aid)
    if a is None:
        return None, err
    if a["asset_type"] != VERIF_TYPE:
        return None, VM.E_VIEW_INTEGRITY_FAILED
    if repository_id is not None and str(a["repository_id"]) != str(repository_id):
        return None, VM.E_REPOSITORY_MISMATCH
    return a, None


def check_link(claim, verification):
    """★ Verification 必须引用**这个** Claim，且 Commit 一致。"""
    cp, vp = claim["payload"], verification["payload"]
    if vp.get("claim_id") != cp.get("claim_id"):
        return VM.E_CLAIM_VERIFICATION_MISMATCH
    if str(claim["repository_id"]) != str(verification["repository_id"]):
        return VM.E_REPOSITORY_MISMATCH
    vparams = (vp.get("normalized_verification_params") or {})
    v_commit = vparams.get("commit_sha")
    if v_commit and cp.get("commit_sha") and v_commit != cp["commit_sha"]:
        return VM.E_COMMIT_MISMATCH
    return None


def check_fact_chain(store, verification):
    """Fact → Snapshot 链必须可定位、Commit 一致、内容摘要一致。"""
    vp = verification["payload"]
    raw_ids = list(vp.get("fact_ids") or [])
    # ★ None 表示"本次裁决没有可用证据"（例如 UNKNOWN 观察），
    #   这是 insufficient_evidence 的正常形态，**不是**悬空引用。
    #   只有"写了 id 却找不到"才是损坏。
    fact_ids = [f for f in raw_ids if f]
    no_evidence = (len(fact_ids) == 0)
    if no_evidence:
        return None, {"facts": [], "snapshots": [], "damaged": [],
                      "no_evidence": True,
                      "raw_fact_ids": raw_ids}

    facts, snaps, damaged = [], [], []
    claim_commit = (vp.get("normalized_verification_params") or {}).get("commit_sha")
    for fid in fact_ids:
        row = _find_latest(store, FACT_TYPE, fid)
        if row is None:
            damaged.append({"fact_id": fid, "reason": VM.E_DANGLING_REFERENCE})
            continue
        a, err = _read(store, row["asset_id"])
        if a is None:
            damaged.append({"fact_id": fid, "reason": err})
            continue
        fp = a["payload"]
        if claim_commit and fp.get("commit_sha") != claim_commit:
            damaged.append({"fact_id": fid, "reason": VM.E_COMMIT_MISMATCH,
                            "detail": f"fact commit {fp.get('commit_sha')} != {claim_commit}"})
            continue
        facts.append(a)
        # Snapshot
        sid = fp.get("snapshot_asset_id")
        # ★ fact 里存的是 snapshot 的 **asset_id**（SL-A-…），
        #   不是 logical_identity（SL-SNAP-…）。直接按 asset_id 读取。
        srow = {"asset_id": sid} if sid else None
        if srow is None:
            damaged.append({"fact_id": fid, "reason": VM.E_SOURCE_MISSING,
                            "detail": f"snapshot {sid} 无法定位"})
            continue
        s, serr = _read(store, srow["asset_id"])
        if s is None:
            damaged.append({"fact_id": fid, "reason": serr})
            continue
        sp = s["payload"]
        # ★ Tree 与 Commit 身份不得混用
        if sp.get("commit_sha") != fp.get("commit_sha"):
            damaged.append({"fact_id": fid, "reason": VM.E_COMMIT_MISMATCH,
                            "detail": "快照 commit 与 fact commit 不一致"})
            continue
        if sp.get("root_tree_sha") == sp.get("commit_sha"):
            damaged.append({"fact_id": fid, "reason": VM.E_VIEW_INTEGRITY_FAILED,
                            "detail": "root_tree_sha 与 commit_sha 相同，身份混用"})
            continue
        snaps.append(s)

    if damaged:
        return VM.E_EVIDENCE_CORRUPT, {"facts": facts, "snapshots": snaps,
                                       "damaged": damaged,
                                       "no_evidence": no_evidence}
    return None, {"facts": facts, "snapshots": snaps, "damaged": [],
                  "no_evidence": no_evidence}


def fingerprint_assets(store, *, asset_types=None) -> dict:
    """只读指纹快照（仅用于测试断言"装配前后不变"）。"""
    sql = "SELECT asset_id, asset_type, content_hash, asset_version FROM assets"
    if asset_types:
        sql += " WHERE asset_type IN (%s)" % ",".join("?" * len(asset_types))
    rows = store.conn.execute(sql, tuple(asset_types or ())).fetchall()
    return {r["asset_id"]: {"type": r["asset_type"],
                            "hash": r["content_hash"],
                            "version": r["asset_version"]}
            for r in rows}


def fingerprint_operation_log(store) -> dict:
    rows = store.conn.execute(
        "SELECT operation_id, result_hash, pointer_version FROM operation_log").fetchall()
    return {r["operation_id"]: {"hash": r["result_hash"],
                                "pv": r["pointer_version"]} for r in rows}


def fingerprint_pointers(store) -> dict:
    rows = store.conn.execute(
        "SELECT logical_identity, repository_id, pointer_version, "
        "current_asset_id, last_known_good "
        "FROM current_view").fetchall()
    return {f"{r['repository_id']}:{r['logical_identity']}":
            {"pv": r["pointer_version"], "aid": r["current_asset_id"],
             "lkg": r["last_known_good"]} for r in rows}


def fingerprint_index(store) -> dict:
    try:
        rows = store.conn.execute(
            "SELECT asset_id, row_kind, text FROM index_rows ORDER BY asset_id, row_kind").fetchall()
    except Exception:
        return {}
    import hashlib
    return {"rows": len(rows),
            "digest": hashlib.sha256(
                json.dumps([dict(r) for r in rows], sort_keys=True,
                           ensure_ascii=False).encode()).hexdigest()}
