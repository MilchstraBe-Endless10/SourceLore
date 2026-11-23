#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确定性证据评估（三态裁决）。

契约：SL-CAP-0020～0028。

**铁律：**
  V1 缺少证明 ≠ 具有反证 —— 无证据一律 insufficient_evidence
  V2 证据对象存在 ≠ 证据足以支持结论
  V3 PARTIAL 未命中：既不能 support 不存在，也不能 refute 存在
  V4 不同 Commit 的观察互不证伪
  V5 同范围冲突不强行裁决，保留 conflict 诊断
  V6 绝不默认 supported
"""

import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "storage"), str(_HERE.parent / "facts"),
           str(_HERE.parent / "trust")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ec_models as M
from evidence_resolver import resolve_all
from facts_models_proxy import fact_content_hash_of
import policy as TRUST

VERIFIER_RULE_VERSION = "path-exists-verifier/v1"

# Facts 侧观察态（与 facts/models.py 一致）
OBS_PRESENT = "OBSERVED_PRESENT"
OBS_ABSENT = "OBSERVED_ABSENT_IN_COVERED_SCOPE"
OBS_UNKNOWN = "UNKNOWN"

STATUS_COMPLETE = "COMPLETE"


def verify_path_claim(store, claim, fact_ids,
                      rule_version: str = VERIFIER_RULE_VERSION,
                      verified_at: str = "",
                      snapshot_payload: Optional[dict] = None) -> M.Verification:
    """对 repository_path_exists 命题做确定性评估。

    ★ P0/D4：counter 判 refuted 前必须过反证准入（object_type/sha/mode/observed_at
      与快照真实覆盖度）。缺可靠反证时降级 insufficient，不产生确定否定。
    """
    if claim.claim_type != M.CLAIM_PATH_EXISTS:
        return _insufficient(
            claim=claim, fact_ids=[], hashes=[], status_reason=M.R_UNSUPPORTED_TYPE,
            rule_version=rule_version, verified_at=verified_at,
            detail=f"不支持的命题类型: {claim.claim_type}")

    # 证据去重 + 排序（顺序不影响身份与结论）
    resolved = resolve_all(store, list(fact_ids or []))
    fids = sorted(f.fact_id for f in resolved)
    hashes = sorted(f.content_hash for f in resolved if f.ok)

    # 任何存储层错误都必须显式保留，不能只用 insufficient 掩盖
    storage_errors = [f for f in resolved if f.storage_error]
    if storage_errors:
        return _insufficient(
            claim=claim, fact_ids=fids, hashes=hashes,
            status_reason=M.R_STORAGE_ERROR, rule_version=rule_version,
            verified_at=verified_at,
            detail=f"存储错误: {storage_errors[0].storage_error}",
            storage_error=storage_errors[0].storage_error)

    # V1：没有事实 → insufficient
    if not resolved:
        return _insufficient(claim=claim, fact_ids=[], hashes=[],
                             status_reason=M.R_NO_FACTS,
                             rule_version=rule_version, verified_at=verified_at)

    # 核验失败的证据不能参与裁决
    bad = [f for f in resolved if not f.ok]
    if bad:
        return _insufficient(
            claim=claim, fact_ids=fids, hashes=hashes,
            status_reason=bad[0].reason, rule_version=rule_version,
            verified_at=verified_at, detail=bad[0].detail)

    # 逐条检查归属一致性
    usable, diagnostics = [], []
    for f in resolved:
        if f.repository_id != claim.repository_id:
            return _insufficient(
                claim=claim, fact_ids=fids, hashes=hashes,
                status_reason=M.R_REPO_MISMATCH, rule_version=rule_version,
                verified_at=verified_at,
                detail=f"证据仓库 {f.repository_id} ≠ 命题仓库 {claim.repository_id}")

    for f in resolved:
        if f.commit_sha != claim.commit_sha:
            # V4：不同 Commit 不互相证伪 —— 排除该证据，不是 refute
            diagnostics.append((f, M.R_COMMIT_MISMATCH))
            continue
        if f.normalized_path != claim.normalized_path:
            diagnostics.append((f, M.R_PATH_MISMATCH))
            continue
        if f.observation == OBS_UNKNOWN:
            diagnostics.append((f, M.R_FACT_UNKNOWN))
            continue
        usable.append(f)

    if not usable:
        reason = diagnostics[0][1] if diagnostics else M.R_EVIDENCE_FIELD_MISSING
        return _insufficient(claim=claim, fact_ids=fids, hashes=hashes,
                             status_reason=reason, rule_version=rule_version,
                             verified_at=verified_at,
                             detail="没有可用的匹配证据")

    # 分类：支持性 / 反证性
    support, counter, partial_limited = [], [], []
    for f in usable:
        is_complete = (f.completeness_status or "").upper() == STATUS_COMPLETE
        if f.observation == OBS_PRESENT:
            if claim.expected_exists:
                support.append(f)
            else:
                # 存在观察反驳"不存在"命题。PARTIAL 下也可反驳（有真实条目为证）
                counter.append(f)
        elif f.observation == OBS_ABSENT:
            if claim.expected_exists:
                # 不存在观察反驳"存在"命题 —— 但要求 COMPLETE
                if is_complete:
                    counter.append(f)
                else:
                    partial_limited.append(f)
            else:
                if is_complete:
                    support.append(f)
                else:
                    partial_limited.append(f)

    # V5：同范围冲突
    if support and counter:
        return _insufficient(
            claim=claim, fact_ids=fids, hashes=hashes,
            status_reason=M.R_CONFLICT, rule_version=rule_version,
            verified_at=verified_at, conflict=True,
            conflict_ids=sorted([f.fact_id for f in support + counter]),
            support_ids=sorted(f.fact_id for f in support),
            counter_ids=sorted(f.fact_id for f in counter),
            detail="同范围证据互相矛盾，不强行裁决")

    if support:
        # V3：若断言"存在"而证据是 PARTIAL 的 present，必须保留局部限制
        local_only = any(f.local_coverage_only for f in support)
        return _verified(
            claim=claim, status=M.SUPPORTED, fact_ids=fids, hashes=hashes,
            rule_version=rule_version, verified_at=verified_at,
            support_ids=sorted(f.fact_id for f in support),
            refs=[r for f in support for r in (f.payload.get("evidence_refs") or [])],
            local_only=local_only,
            detail=("局部覆盖限制下的支持" if local_only else "完整覆盖下的支持"))

    if counter:
        # ★ P0/D4：逐条反证过准入；任一反证不可靠即不得产生确定 refuted。
        bad_reasons = []
        for f in counter:
            cfp = (getattr(f, "payload", None) or {})
            if not cfp:
                cfp = {"observation": getattr(f, "observation", None),
                       "completeness_status": getattr(f, "completeness_status", None),
                       "observed_value": {"path": getattr(f, "normalized_path", None)},
                       "observed_at": getattr(f, "observed_at", ""),
                       "evidence_refs": getattr(f, "evidence_refs", [])}
            # ★ 从反证 fact 的 source_snapshot 引用取真实快照覆盖度，
            #   用派生视图识别 ROOT_ONLY 误标 COMPLETE（审计 D4+D5）。
            snap_pl = snapshot_payload
            if snap_pl is None:
                try:
                    import json as _j
                    for ref in (cfp.get("evidence_refs") or []):
                        if isinstance(ref, dict) and ref.get("kind") == "source_snapshot":
                            sa = ref.get("snapshot_asset_id")
                            if sa:
                                g = store.get_asset(sa, verify=False)
                                if g.get("ok"):
                                    ap = g["asset"]
                                    snap_pl = ap.get("payload")
                                    if snap_pl is None:
                                        snap_pl = _j.loads(ap.get("payload_json") or "{}")
                            break
                except Exception:
                    snap_pl = None
            # 用派生覆盖度替换历史误标的 COMPLETE
            if snap_pl:
                try:
                    import tree_scope as _TS
                    derived = _TS.derive_tree_scope(snap_pl)
                    if not derived["complete"]:
                        snap_pl = dict(snap_pl)
                        snap_pl["completeness_status"] = derived["scope"]
                except Exception:
                    pass
            sound = TRUST.refutation_soundness(
                cfp, snap_pl, claim_path=getattr(claim, "normalized_path", None))
            if not sound["sound"]:
                bad_reasons.append((f, sound["reason_code"]))
        if bad_reasons:
            f, reason = bad_reasons[0]
            return _insufficient(
                claim=claim, fact_ids=fids, hashes=hashes,
                status_reason=reason or M.R_PARTIAL_CANNOT_REFUTE,
                rule_version=rule_version, verified_at=verified_at,
                detail="反证不满足准入条件，不得产生确定否定")
        return _verified(
            claim=claim, status=M.REFUTED, fact_ids=fids, hashes=hashes,
            rule_version=rule_version, verified_at=verified_at,
            counter_ids=sorted(f.fact_id for f in counter),
            refs=[r for f in counter for r in (f.payload.get("evidence_refs") or [])],
            detail="存在充分反证")

    # 只剩 partial_limited：既不能 support 也不能 refute
    if partial_limited:
        return _insufficient(
            claim=claim, fact_ids=fids, hashes=hashes,
            status_reason=M.R_PARTIAL_INSUFFICIENT,
            rule_version=rule_version, verified_at=verified_at,
            detail="仅有不完整覆盖下的不存在观察，无法支持或反驳")

    return _insufficient(claim=claim, fact_ids=fids, hashes=hashes,
                         status_reason=M.R_EVIDENCE_FIELD_MISSING,
                         rule_version=rule_version, verified_at=verified_at)


def _verified(*, claim, status, fact_ids, hashes, rule_version, verified_at,
              support_ids=(), counter_ids=(), refs=(), local_only=False, detail=""):
    params = {"claim_type": claim.claim_type,
              "expected_exists": claim.expected_exists}
    vid = M.make_verification_id(
        claim_id=claim.claim_id, fact_ids_sorted=fact_ids,
        fact_content_hashes_sorted=hashes, rule_version=rule_version,
        normalized_verification_params=params)
    return M.Verification(
        verification_id=vid, claim_id=claim.claim_id, status=status,
        reason_code=None, fact_ids=fact_ids, fact_content_hashes=hashes,
        rule_version=rule_version,
        normalized_verification_params=params,
        evidence_refs=list(refs), supporting_fact_ids=sorted(support_ids),
        counter_fact_ids=sorted(counter_ids),
        local_coverage_only=local_only, verified_at=verified_at)


def _insufficient(*, claim, fact_ids, hashes, status_reason, rule_version,
                  verified_at, detail="", conflict=False, conflict_ids=(),
                  support_ids=(), counter_ids=(), storage_error=None):
    params = {"claim_type": claim.claim_type,
              "expected_exists": claim.expected_exists}
    vid = M.make_verification_id(
        claim_id=claim.claim_id, fact_ids_sorted=fact_ids,
        fact_content_hashes_sorted=hashes, rule_version=rule_version,
        normalized_verification_params=params)
    return M.Verification(
        verification_id=vid, claim_id=claim.claim_id,
        status=M.INSUFFICIENT, reason_code=status_reason,
        fact_ids=fact_ids, fact_content_hashes=hashes,
        rule_version=rule_version,
        normalized_verification_params=params, evidence_refs=[],
        conflict_detected=conflict, conflict_fact_ids=sorted(conflict_ids),
        supporting_fact_ids=sorted(support_ids),
        counter_fact_ids=sorted(counter_ids),
        storage_error=storage_error, verified_at=verified_at)
