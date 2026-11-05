#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research Packet：只读研究包。

★ **不是新的 Claim 裁决状态机**（SL-CAP-0038 补充：结论状态只有 SL-CAP-0028）。
"""

import sys
import hashlib
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PACKET_SCHEMA_VERSION = "research-packet/1"
RETRIEVAL_RULE_VERSION = "retrieval-rule/1"

# 包状态（★ 与 coverage/verification 都正交）
P_OK = "PACKET_OK"
P_PARTIAL = "PACKET_PARTIAL"
P_INSUFFICIENT = "PACKET_INSUFFICIENT"
P_ERROR = "PACKET_ERROR"
PACKET_STATES = frozenset({P_OK, P_PARTIAL, P_INSUFFICIENT, P_ERROR})


def make_research_id(*, query_id, finding_ids, packet_schema=PACKET_SCHEMA_VERSION,
                     rule=RETRIEVAL_RULE_VERSION) -> str:
    """★ 只由 query_id + 排序后的 finding 身份决定；不含时间戳。"""
    core = {"query_id": query_id, "finding_ids": sorted(finding_ids),
            "packet_schema_version": packet_schema,
            "retrieval_rule_version": rule}
    raw = json.dumps(core, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return "SL-R-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def build_packet(*, query, retrieval, coverage, findings, untrusted,
                 limitations, distribution, freshness_summary=None,
                 review_summary=None, provenance_summary=None,
                 conflicts=None, evidence_integrity=None) -> dict:
    finding_ids = [f["finding_id"] for f in findings]
    rid = make_research_id(query_id=query["query_id"],
                           finding_ids=finding_ids)

    status = _packet_status(coverage["coverage_state"])

    pkt = {
        "research_id": rid,
        "research_schema_version": PACKET_SCHEMA_VERSION,
        "retrieval_rule_version": RETRIEVAL_RULE_VERSION,
        "query_id": query["query_id"],
        "query": {k: query.get(k) for k in
                  ("question_type", "repository_id", "subject_id",
                   "commit_sha", "compare_commit_sha", "path",
                   "claim_type", "max_results", "retrieval_scope",
                   "evidence_policy", "provenance_policy",
                   "query_schema_version", "query_rule_version")},
        "canonical_refs": list(query.get("canonical_refs") or []),
        "selected_view_ids": sorted({f["claim_id"] for f in findings}),
        "claim_refs": sorted({f["claim_id"] for f in findings}),
        "verification_refs": sorted({f["verification_id"] for f in findings}),
        "fact_refs": sorted({x for f in findings for x in f["fact_refs"]}),
        "evidence_refs": sorted({x for f in findings for x in f["evidence_refs"]}),
        "source_snapshot_refs": sorted(
            {r for f in findings for r in f["source_view_refs"]}),
        "findings": findings,
        "excluded_candidates": list(retrieval.get("excluded") or []) +
                              list(untrusted or []),
        "untrusted_findings": list(untrusted or []),
        # ★ 证据完整性是可信度组成部分，必须进摘要
        "evidence_integrity_summary": dict(evidence_integrity or {}),
        "coverage_assessment": coverage,
        "unresolved_questions": list(coverage.get("unresolved_questions") or []),
        "limitations": sorted(set(limitations or [])),
        "conflicts": list(conflicts or []),
        "provenance_summary": provenance_summary or {},
        "review_summary": review_summary or {},
        "freshness_summary": freshness_summary or {},
        "distribution_restrictions": distribution or {},
        "retrieval": {
            "status": retrieval.get("status"),
            "truncated": bool(retrieval.get("truncated")),
            "candidate_count": retrieval.get("candidate_count"),
            "limit": retrieval.get("cap"),
            "note": retrieval.get("note") or "",
        },
        "packet_status": status,
        "llm_used": False,
        "external_network_used": False,
        "is_claim_authority": False,
        "publishable_as_knowledge": False,
    }
    pkt["content_digest"] = content_digest(pkt)
    return pkt


def content_digest(pkt: dict) -> str:
    """★ 内容摘要：排除一切运行期/诊断元数据，保证可复算。"""
    core = {k: v for k, v in pkt.items()
            if k not in ("content_digest", "assembled_at", "elapsed_ms",
                         "run_diagnostics")}
    raw = json.dumps(core, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _packet_status(coverage_state) -> str:
    return {
        "ANSWERABLE_FROM_EXISTING_EVIDENCE": P_OK,
        "PARTIALLY_ANSWERABLE": P_PARTIAL,
        "INSUFFICIENT_EVIDENCE": P_INSUFFICIENT,
        "CONFLICT_REQUIRES_REVIEW": P_PARTIAL,
        "RETRIEVAL_ERROR": P_ERROR,
    }.get(coverage_state, P_ERROR)
