#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trusted Statement Bank：从 Research Packet 抽出**可被引用**的陈述池。

★ 关键约束（SL-CAP-0039）：
  - 只有 finding 能成为陈述来源；没有 finding 就没有陈述
  - 每条陈述都绑定 finding_id，永不脱离证据
  - 陈述是**模板生成**的，不是 LLM 生成的
"""

import sys
import hashlib
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BANK_SCHEMA_VERSION = "statement-bank/1"

# 陈述种类（全部是**事实转录**，不含推断）
S_SUPPORTED = "FACT_SUPPORTED"
S_REFUTED = "FACT_REFUTED"
S_INSUFFICIENT = "FACT_INSUFFICIENT"
S_SCOPE = "SCOPE_BOUND"
S_LIMITATION = "LIMITATION"
S_COVERAGE = "COVERAGE_STATE"

# ★ 陈述强度：CITED 可直接引用；INFERENCE/UNKNOWN 不得以肯定语气出现
TIER_CITED = "CITED"
TIER_INFERENCE = "INFERENCE"
TIER_UNKNOWN = "UNKNOWN"


def _h(d) -> str:
    return hashlib.sha256(
        json.dumps(d, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()


def build_bank(packet: dict) -> dict:
    """从研究包生成陈述池。**只转录，不推断。**"""
    statements, by_id = [], {}

    def add(kind, text, refs, *, tier=TIER_CITED, extra=None):
        sid = "SL-ST-" + _h({"kind": kind, "text": text,
                             "refs": sorted(refs), "tier": tier})[:24]
        if sid in by_id:
            return by_id[sid]["statement_id"]
        s = {"statement_id": sid, "kind": kind, "tier": tier,
             "text": text, "finding_refs": sorted(refs),
             "citation_required": tier == TIER_CITED,
             "rendered_as": ("可引用" if tier == TIER_CITED
                             else "推断/未知，不得以肯定语气出现")}
        if extra:
            s.update(extra)
        statements.append(s)
        by_id[sid] = s
        return sid

    # 1) 逐 finding 的事实转录
    for f in packet.get("findings") or []:
        st = f["verdict_status"]
        commit = f.get("claim_commit_sha") or ""
        if st == "supported":
            text = (f"在固定 Commit {commit} 上，该路径存在命题的裁决为 "
                    f"supported（支持）。")
        elif st == "refuted":
            text = (f"在固定 Commit {commit} 上，现有有效反证与该命题矛盾，"
                    f"裁决为 refuted（反驳）。")
        else:
            text = (f"在固定 Commit {commit} 上，现有证据不足以支持或反驳"
                    f"该命题，裁决为 insufficient_evidence（证据不足）。")
        add({"supported": S_SUPPORTED,
             "refuted": S_REFUTED}.get(st, S_INSUFFICIENT),
            text, [f["finding_id"]],
            extra={"commit_sha": commit, "claim_id": f.get("claim_id"),
                   "verification_id": f.get("verification_id"),
                   "evidence_integrity": f.get("evidence_integrity")})

    # 2) 覆盖状态（本身不是 finding，绑定 coverage 的 gap 即可）
    cov = packet.get("coverage_assessment") or {}
    cstate = cov.get("coverage_state")
    if cstate:
        add(S_COVERAGE,
            f"该研究问题的可回答性状态为 {cstate}；"
            "这不是证据裁决（verification_status）。",
            [g.get("gap", "") for g in (cov.get("gaps") or []) if g.get("gap")] or
            ["coverage"],
            extra={"coverage_state": cstate})

    # 3) 限制：逐条转录
    for lim in packet.get("limitations") or []:
        add(S_LIMITATION, str(lim), ["limitations"],
            extra={"limitation": str(lim)})

    # 4) 范围声明（固定模板）
    rt = (packet.get("distribution_restrictions") or {})
    add(S_SCOPE,
        "本产物是内部研究材料，不是知识权威，不得作为 Claim 裁决或发布依据；"
        f"分发门禁为 {rt.get('freeze_state', 'UNKNOWN')}，"
        f"distribution_allowed={rt.get('distribution_allowed')}。",
        ["distribution_restrictions"])

    ids = [s["statement_id"] for s in statements]
    return {
        "bank_schema_version": BANK_SCHEMA_VERSION,
        "statement_count": len(statements),
        "statements": statements,
        "statement_ids": sorted(ids),
        "citation_map": {s["statement_id"]: s["finding_refs"]
                         for s in statements},
        "bank_digest": _h(sorted(ids)),
        "note": ("陈述由模板转录生成，非 LLM 生成；"
                 "每条都绑定证据引用，脱离引用的陈述不在此池内"),
    }


def find(statements: list, sid: str):
    for s in statements:
        if s["statement_id"] == sid:
            return s
    return None
