#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore 统一身份与证据准入（P0 trust contract）。

唯一一套可信性判定，供 Asset Ingest / Index Rebuild / Current View /
Knowledge Query / Evidence Resolver / Claim Verifier / Derived Views 共用。
只读 A 层；结论作用于 C 索引、B 指针解释与查询结果，不创造新 reason_code。
"""

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage"), str(_HERE.parent / "research"),
           str(_HERE.parent / "evidence_claims")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Commit 真实性封闭码表 ──────────────────────────────────
COMMIT_FORMAT_VALID = "COMMIT_FORMAT_VALID"
COMMIT_BOUND_TO_REPOSITORY = "COMMIT_BOUND_TO_REPOSITORY"
COMMIT_SNAPSHOT_VERIFIED = "COMMIT_SNAPSHOT_VERIFIED"
COMMIT_UNKNOWN = "COMMIT_UNKNOWN"
COMMIT_IDENTITY_CONFLICT = "COMMIT_IDENTITY_CONFLICT"

# 复用现有封闭 reason_code（ec_models），不引入新码
R_FACT_NOT_FOUND = "FACT_NOT_FOUND"
R_FACT_INTEGRITY = "FACT_INTEGRITY_FAILED"
R_REPO_MISMATCH = "REPOSITORY_MISMATCH"
R_COMMIT_MISMATCH = "COMMIT_MISMATCH"
R_PATH_MISMATCH = "PATH_MISMATCH"
R_SNAPSHOT_NOT_FOUND = "SNAPSHOT_NOT_FOUND"
R_NOT_COVERING = "SCOPE_NOT_COVERING"
R_PARTIAL_INSUFFICIENT = "PARTIAL_EVIDENCE_INSUFFICIENT"
R_PARTIAL_CANNOT_REFUTE = "PARTIAL_CANNOT_REFUTE"
R_EVIDENCE_FIELD_MISSING = "EVIDENCE_FIELD_MISSING"

EV_FULL = "FULLY_LOCATABLE"
EV_PARTIAL = "PARTIALLY_LOCATABLE"
EV_UNRESOLVED = "UNRESOLVED_NO_INTEGRITY"
EV_NONE = "NO_EVIDENCE"

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
# 占位/非真实 Commit 的已知形态（aaaa…）。格式合法但未认证，不得当真实版本。
_PLACEHOLDER_COMMITS = {"a" * 40, "0" * 40, "f" * 40}


def commit_status(commit_sha, *, snapshot_commits, snapshot_payloads=None):
    """Commit 真实性分级。格式合法 ≠ 真实有效。

    snapshot_commits: 该仓库已登记 repository_snapshot 的 commit 集合（可信绑定）。
    snapshot_payloads: 可选，同 commit 的快照 payload 列表，用于检测身份冲突。
    """
    if not isinstance(commit_sha, str) or not _HEX40.match(commit_sha):
        return COMMIT_UNKNOWN
    if commit_sha in _PLACEHOLDER_COMMITS:
        # 合法十六进制但为已知占位身份 —— 只到 FORMAT_VALID，绝不认证
        return COMMIT_FORMAT_VALID
    payloads = snapshot_payloads or []
    if len(payloads) > 1:
        roots = {str(p.get("root_tree_sha")) for p in payloads if isinstance(p, dict)}
        if len(roots) > 1:
            return COMMIT_IDENTITY_CONFLICT
    if commit_sha in set(snapshot_commits or []):
        return COMMIT_SNAPSHOT_VERIFIED if payloads else COMMIT_BOUND_TO_REPOSITORY
    # 格式合法，但未绑定本仓库任何快照 —— 不能作为可信版本
    return COMMIT_FORMAT_VALID


def is_authenticated_commit(status):
    """只有绑定到仓库快照的 Commit 才能作为当前可信版本身份。"""
    return status in (COMMIT_BOUND_TO_REPOSITORY, COMMIT_SNAPSHOT_VERIFIED)


def identity_check(payload, *, repository_id, snapshot_commits,
                   expected_commit=None, fact_payload=None,
                   require_authenticated_commit=False):
    """仓库级事实/命题的身份一致性核对。禁止按文件名或 symbol_name 合并。

    返回 {ok, reasons[], commit_status}。
    """
    payload = payload if isinstance(payload, dict) else {}
    reasons = []
    pl_repo = str(payload.get("repository_id") or "")
    if pl_repo and pl_repo != str(repository_id):
        reasons.append(R_REPO_MISMATCH)
    cs = expected_commit if expected_commit is not None else payload.get("commit_sha")
    st = commit_status(cs, snapshot_commits=snapshot_commits)
    # ★ P0/D1：仓库级命题/Fact 引用的 commit 必须绑定到本仓库快照。
    #   跨仓库 Commit（如 is-number 的 Claim 挂 is-plain-obj 的 666df7c）
    #   和占位 Commit（aaaa…）都必须在此阻断——即使 payload.repository_id 伪装正确。
    if cs and st == COMMIT_FORMAT_VALID:
        # 格式合法但未绑定本仓库任何快照：不可作为可信身份
        reasons.append(R_COMMIT_MISMATCH)
    if require_authenticated_commit and cs and not is_authenticated_commit(st):
        reasons.append(R_COMMIT_MISMATCH)
    if cs and st == COMMIT_IDENTITY_CONFLICT:
        reasons.append(R_COMMIT_MISMATCH)
    if isinstance(fact_payload, dict):
        frepo = str(fact_payload.get("repository_id") or "")
        if frepo and frepo != str(repository_id):
            reasons.append(R_REPO_MISMATCH)
        fcs = fact_payload.get("commit_sha")
        if fcs and str(fcs) != str(cs):
            reasons.append(R_COMMIT_MISMATCH)
    return {"ok": not reasons, "reasons": reasons, "commit_status": st}


def current_asset_ids(store, *, repository_id, asset_type=None, logical_identity=None):
    """唯一允许的“当前有效资产”来源：B 层 current_view 且资产实存、身份匹配。"""
    sql = ("SELECT cv.logical_identity, cv.current_asset_id, a.asset_type, a.repository_id "
           "FROM current_view cv JOIN assets a ON a.asset_id=cv.current_asset_id "
           "WHERE cv.repository_id=?")
    params = [repository_id]
    if asset_type is not None:
        sql += " AND a.asset_type=?"
        params.append(asset_type)
    if logical_identity is not None:
        sql += " AND cv.logical_identity=?"
        params.append(logical_identity)
    out = {}
    for r in store.conn.execute(sql, params).fetchall():
        if str(r["repository_id"]) != str(repository_id):
            continue
        out[r["logical_identity"]] = r["current_asset_id"]
    return out


def _payload_of(store, asset_id):
    got = store.get_asset(asset_id, verify=True)
    if not got.get("ok"):
        return None
    return (got["asset"] or {}).get("payload") or {}


def resolve_verification_for_claim(store, claim_id, repository_id):
    """B 层解析 Claim 的当前 Verification。历史裁决不得混入当前结果。"""
    claim_current = current_asset_ids(store, repository_id=repository_id,
                                      asset_type="claim_candidate")
    verif_current = current_asset_ids(store, repository_id=repository_id,
                                      asset_type="claim_verification")
    claim_lid = None
    for lid, aid in claim_current.items():
        pl = _payload_of(store, aid) or {}
        if str(pl.get("claim_id")) == str(claim_id):
            claim_lid = lid
            break
    # 当前语义只认：当前 verification 中 claim_id 命中，且属于当前 claim 集合
    for lid, aid in verif_current.items():
        pl = _payload_of(store, aid) or {}
        if str(pl.get("claim_id")) == str(claim_id):
            if claim_lid is not None and lid != claim_lid and not _verif_lid_matches(pl, claim_lid):
                continue
            return {"ok": True, "source": "current", "verification_id": pl.get("verification_id"),
                    "asset_id": aid, "status": pl.get("status")}
    return {"ok": False, "source": "none", "reason": R_NOT_COVERING,
            "detail": "当前视图中没有该 Claim 的 Verification"}


def _verif_lid_matches(pl, claim_lid):
    return str((pl or {}).get("claim_id") or "") == str(claim_lid)


def list_historical_verifications(store, claim_id, repository_id):
    """合法的历史查询通道：列出 A 层所有版本（含未被 B 采用的）。"""
    out = []
    for r in store.conn.execute(
            "SELECT asset_id, asset_version FROM assets WHERE asset_type='claim_verification' "
            "AND repository_id=? AND payload_json LIKE ? ORDER BY asset_version DESC, asset_id",
            (repository_id, '%"claim_id":"' + str(claim_id) + '"%')).fetchall():
        pl = _payload_of(store, r["asset_id"]) or {}
        if str(pl.get("claim_id")) == str(claim_id):
            out.append({"asset_id": r["asset_id"], "asset_version": r["asset_version"],
                        "verification_id": pl.get("verification_id"),
                        "status": pl.get("status")})
    return out


def evidence_admission(verification, *, current, integrity):
    """证据准入：原始 verdict ≠ 当前可采信 finding。不修改历史裁决。"""
    verification = verification if isinstance(verification, dict) else {}
    integrity = integrity if isinstance(integrity, dict) else {}
    level = integrity.get("level", EV_NONE)
    raw = verification.get("status")
    note_parts = []
    if not current:
        return {"admitted": False, "verdict_status": "insufficient_evidence",
                "reason_code": R_NOT_COVERING,
                "note": "非当前视图裁决，不作为当前结论"}
    if level == EV_FULL:
        return {"admitted": True, "verdict_status": raw or "insufficient_evidence",
                "reason_code": None, "note": "证据全部可定位"}
    # 证据链不完整：supported / refuted 均不得作为当前可信结论
    note_parts.append(f"证据完整性={level}：" + "、".join(integrity.get("reasons") or []))
    if level == EV_PARTIAL:
        reason = R_EVIDENCE_FIELD_MISSING
    elif level == EV_UNRESOLVED:
        reason = R_FACT_NOT_FOUND
    else:
        reason = R_PARTIAL_INSUFFICIENT
    return {"admitted": False, "verdict_status": "insufficient_evidence",
            "reason_code": reason, "note": "；".join(note_parts)}


def refutation_soundness(counter_fact_payload, snapshot_payload=None, *, claim_path=None):
    """反证准入：root 级精确缺路径判断与全仓递归搜索区分处理。

    不允许用 object_type=unknown / blob_sha=null / mode="" / observed_at="" 的
    “缺失观察”形成确定 refuted。目录子树未展开导致的缺路径也不构成反证。
    """
    f = counter_fact_payload if isinstance(counter_fact_payload, dict) else {}
    reasons = []
    obs = str(f.get("observation") or "")
    is_absent = obs == "OBSERVED_ABSENT_IN_COVERED_SCOPE"
    is_present = obs == "OBSERVED_PRESENT_IN_COVERED_SCOPE" or bool(
        (f.get("observed_value") or {}).get("object_type") in ("blob", "tree", "commit"))
    if not (is_absent or is_present):
        reasons.append(R_EVIDENCE_FIELD_MISSING)
    ev = [e for e in (f.get("evidence_refs") or []) if isinstance(e, dict) and e.get("kind") == "tree_entry"]
    # ★ ABSENT 反证靠 source_snapshot 的 COMPLETE 覆盖声明，其占位 tree_entry
    #   （object_type=unknown / blob_sha=null / mode=""）是"文件不存在"的正常表达。
    #   PRESENT 反证靠真实 tree_entry 字段，不要求快照覆盖声明。
    if is_present and not is_absent:
        good_entry = any(
            e.get("object_type") in ("blob", "tree", "commit") and e.get("sha")
            and str(e.get("mode") or "") != "" for e in ev)
        ov_obj = (f.get("observed_value") or {}).get("object_type")
        if not good_entry and ov_obj not in ("blob", "tree", "commit"):
            reasons.append(R_PARTIAL_CANNOT_REFUTE)
    if not str(f.get("observed_at") or "") and not is_absent:
        # observed_at 空由覆盖声明/真实条目补足，不单独否决
        pass
    # 路径必须精确匹配（README ≠ README.md；Git 路径大小写敏感）
    ov = f.get("observed_value") or {}
    if claim_path is not None and str(ov.get("path") or "") != str(claim_path):
        reasons.append(R_PATH_MISMATCH)
    sp = snapshot_payload if isinstance(snapshot_payload, dict) else {}
    # 反证要求反证事实本身声明了 COMPLETE 覆盖。
    # ★ 有快照时：额外核对快照真实覆盖度（未展开子树 + 非根级路径 → 不可反证）。
    #   仅对 ABSENT 反证适用：PRESENT 靠真实条目反驳，与目录覆盖度无关。
    # ★ 无快照时：不凭空否决；反证 fact 自带 completeness_status 即可判定。
    fact_complete = str(f.get("completeness_status") or "").upper() == "COMPLETE"
    ov_complete = str(ov.get("completeness_status") or "").upper() == "COMPLETE"
    if sp and is_absent:
        target = str(claim_path if claim_path is not None else ov.get("path") or "")
        root_level = "/" not in target
        if str(sp.get("completeness_status") or "").upper() != "COMPLETE":
            # ROOT_ONLY 对根级精确路径仍可判定；对子目录路径不可
            if not (root_level and str(sp.get("completeness_status")).upper() == "ROOT_ONLY"):
                reasons.append(R_PARTIAL_CANNOT_REFUTE)
        has_subtrees = any(
            isinstance(e, dict) and e.get("type") == "tree"
            for e in (sp.get("tree_entries") or []))
        if has_subtrees and not sp.get("deep_walk_used"):
            if not root_level:
                reasons.append(R_PARTIAL_CANNOT_REFUTE)
    elif is_absent and not (fact_complete or ov_complete):
        # 无任何覆盖度声明 → ABSENT 反证证据不足，不可反证
        reasons.append(R_NOT_COVERING)
    reasons = sorted(set(r for r in reasons if r))
    return {"sound": not reasons, "reason_code": reasons[0] if reasons else None,
            "reasons": reasons}
