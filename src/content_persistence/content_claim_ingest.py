#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容命题入库：Claim + Verification 真实落库。

★ 复用既有 EC 存储（verification_store.ingest_claim / ingest_verification）。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("evidence_claims", "facts", "storage", "content"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

VERIF_RULE_VERSION = "content-verifier/1"

# ★ EC 框架的 reason_code 是封闭码表，不能自造。内容裁决码 → 框架码映射。
_REASON_MAP = {
    "CONTENT_FACT_FOUND": "FACT_NOT_FOUND",          # supported 时框架不用此码
    "CONTENT_FACT_CONTRADICTS": "CONFLICTING_EVIDENCE",
    "ABSENCE_CONFIRMED_IN_COMPLETE_SCOPE": "NO_FACTS",
    "NO_MATCHING_FACT": "FACT_NOT_FOUND",
    "CONTENT_UNAVAILABLE": "FACT_NOT_FOUND",
    "CONTENT_PARTIAL": "PARTIAL_EVIDENCE_INSUFFICIENT",
    "PARSER_FAILED": "FACT_INTEGRITY_FAILED",
    "UNSUPPORTED_CLAIM_TYPE": "UNSUPPORTED_CLAIM_TYPE",
}


def _ec_reason(status, reason):
    """映射到框架合法码。supported 不携带 reason。"""
    if status == "supported":
        return None
    return _REASON_MAP.get(reason, "EVIDENCE_FIELD_MISSING")

_STATUS = {"supported": "supported", "refuted": "refuted",
           "insufficient_evidence": "insufficient_evidence"}


def ingest_content_claim(store, *, claim, verdict, facts_payload,
                         repository_id, evidence_refs=None):
    """写入 Claim 候选 + Verification。返回 {ok, claim_result, verification_result}。

    ★ 幂等：同 claim_id → 同 Claim 身份；同证据同规则 → 同 verification_id。
    """
    import ec_models as M
    import verification_store as VS

    cres = VS.ingest_claim(store, claim)
    if not cres.get("ok"):
        return {"ok": False, "stage": "claim",
                "error": cres.get("error") or cres.get("error_code"),
                "detail": cres.get("detail")}

    status = _STATUS.get(verdict.get("status"))
    if status is None:
        return {"ok": False, "stage": "verdict",
                "error": f"未知裁决 {verdict.get('status')}"}

    fid = sorted(verdict.get("supported_fact_ids") or [])
    hashes = sorted(f.get("content_hash") for f in facts_payload
                    if f.get("content_hash"))
    params = {"claim_type": claim.claim_type,
              "expected_present": claim.expected_exists}

    vid = M.make_verification_id(
        claim_id=claim.claim_id, fact_ids_sorted=fid,
        fact_content_hashes_sorted=hashes, rule_version=VERIF_RULE_VERSION,
        normalized_verification_params=params)

    verif = M.Verification(
        verification_id=vid,
        claim_id=claim.claim_id,
        status=status,
        reason_code=_ec_reason(status, verdict.get("reason_code")),
        fact_ids=fid,
        fact_content_hashes=hashes,
        rule_version=VERIF_RULE_VERSION,
        normalized_verification_params=params,
        evidence_refs=evidence_refs or [],
        supporting_fact_ids=fid if status == "supported" else [],
        counter_fact_ids=fid if status == "refuted" else [],
        local_coverage_only=True,
    )
    vres = VS.ingest_verification(store, verif,
                                  repository_id=str(repository_id))
    if not vres.get("ok"):
        return {"ok": False, "stage": "verification",
                "error": vres.get("error") or vres.get("error_code"),
                "detail": vres.get("detail")}

    return {"ok": True, "claim_id": claim.claim_id,
            "verification_id": vid, "status": status,
            "claim_result": cres, "verification_result": vres}
