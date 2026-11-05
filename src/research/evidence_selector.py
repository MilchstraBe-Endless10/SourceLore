#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据筛选：把 Claim+Verification 组装成**可定位的** finding。

★ 硬规则（SL-CAP-0039）：没有来源引用的 finding **不得**进入可采信结论集合。
"""

import sys
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views"), str(_HERE.parent / "storage")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EVIDENCE_CAP = 50
MAX_TEXT = 4000

# finding 类型
F_SUPPORTED = "SUPPORTED"
F_REFUTED = "REFUTED"
F_INSUFFICIENT = "INSUFFICIENT"
F_NO_CLAIM = "NO_CLAIM"
F_EVIDENCE_MISSING = "EVIDENCE_MISSING"
F_RETRIEVAL_ERROR = "RETRIEVAL_ERROR"

# ★ 措辞（严格忠实，不放大）
MEANING = {
    F_SUPPORTED: "在指定范围内，现有经过验证的证据支持该命题。",
    F_REFUTED: "现有有效反证与该命题矛盾。",
    F_INSUFFICIENT: "现有证据不足以支持或反驳该命题。",
    F_NO_CLAIM: "该项研究问题在现有知识资产中没有对应的已登记 Claim。",
    F_EVIDENCE_MISSING: "该 Claim 缺少可定位的证据引用，不能作为可采信结论。",
    F_RETRIEVAL_ERROR: "检索本身失败，无法判定该问题是否可答。",
}

_w = __import__("importlib").import_module("view_models")


def select_findings(pairs: list, query: dict) -> dict:
    """从 (claim, verification) 对生成 findings。

    ★ 只读投影：不改裁决、不补造证据、不把缺失当否证。
    """
    findings, untrusted = [], []
    for pr in pairs:
        c, v = pr["claim"], pr["verification"]
        status = v.get("status")
        ftype, verdict = _map_status(status)
        refs = _evidence_refs(v, c)
        limited = []

        if not refs:
            # ★ 没有可定位证据 → 不可采信
            untrusted.append({
                "claim_id": c["claim_id"],
                "verification_id": v.get("verification_id"),
                "reason": "NO_LOCATABLE_EVIDENCE",
                "note": MEANING[F_EVIDENCE_MISSING]})
            continue

        # ★ 覆盖范围要**同时**看两处：
        #   1) EC 的 local_coverage_only 标记
        #   2) 证据链里 snapshot manifest 的真实 completeness_status
        #   （只信 EC 标记会漏判 —— EC 在某些 insufficient 路径下不设该标记）
        coverage = _snapshot_completeness(refs)
        if v.get("local_coverage_only") or coverage == "PARTIAL":
            limited.append("仅局部覆盖（局部覆盖标记或快照 completeness=PARTIAL）："
                           "未覆盖部分不得判为不存在")
        if status == "insufficient_evidence":
            limited.append("证据不足，不得转写为否定结论")
        if v.get("conflict_detected"):
            limited.append("证据存在冲突，不得强行裁决")

        findings.append({
            "finding_id": "SL-F-" + _h({
                "claim_id": c["claim_id"],
                "verification_id": v.get("verification_id"),
                "status": status})[:24],
            "finding_type": ftype,
            "verdict_status": verdict,
            "label": _label(status),
            "meaning": MEANING[ftype],
            "claim_id": c["claim_id"],
            "claim_type": c.get("claim_type"),
            "claim_commit_sha": c.get("commit_sha"),
            "claim_payload": {k: c["payload"].get(k) for k in
                              ("claim_type", "normalized_path",
                               "expected_exists", "claim_scope")},
            "verification_id": v.get("verification_id"),
            "verification_rule_version": v.get("rule_version"),
            "repository_id": str(query["repository_id"]),
            "review_status": c.get("review_status", "pending_review"),
            "evidence_refs": refs[:EVIDENCE_CAP],
            "fact_refs": (v.get("fact_ids") or [])[:EVIDENCE_CAP],
            "source_view_refs": [
                f"claim:{c['asset_id']}", f"verification:{v['asset_id']}"],
            "limitations": limited,
            "verification_content_hash": v.get("content_hash"),
            "claim_content_hash": c.get("content_hash"),
        })

    findings = sorted(findings, key=lambda f: (f["claim_commit_sha"] or "",
                                               f["claim_id"], f["finding_id"]))
    return {"ok": True, "findings": findings, "untrusted": untrusted,
            "evidence_cap": EVIDENCE_CAP,
            "note": ("无来源引用的条目已移出可采信集合，单独列入 untrusted"
                     )}


def _map_status(status: str):
    if status == "supported":
        return F_SUPPORTED, "supported"
    if status == "refuted":
        return F_REFUTED, "refuted"
    if status == "insufficient_evidence":
        return F_INSUFFICIENT, "insufficient_evidence"
    return F_INSUFFICIENT, "insufficient_evidence"


def _label(status) -> str:
    return {"supported": "支持", "refuted": "反驳",
            "insufficient_evidence": "证据不足"}.get(status, "未知裁决")


def _snapshot_completeness(refs: list) -> str:
    """从证据引用里的 snapshot manifest 读取真实 completeness_status。

    ★ 只看声明式标记不够；快照本身没覆盖全树时，结论范围必须收窄。
    """
    seen = set()
    for r in refs:
        if not isinstance(r, str) or not r.startswith("{"):
            continue
        try:
            o = json.loads(r)
        except Exception:
            continue
        if o.get("kind") == "source_snapshot" and o.get("completeness_status"):
            seen.add(o["completeness_status"])
    if "PARTIAL" in seen:
        return "PARTIAL"
    return seen.pop() if len(seen) == 1 else ("UNKNOWN" if seen else "")


def _evidence_refs(v: dict, c: dict) -> list:
    """★ 可定位证据 = Verification 的 evidence_refs 或 fact_ids 非空。"""
    refs = []
    for r in (v.get("evidence_refs") or []):
        refs.append(r if isinstance(r, str) else _canon(r))
    for fid in (v.get("fact_ids") or []):
        if fid:
            refs.append(f"fact:{fid}")
    return sorted(set(refs))


def _canon(o) -> str:
    import json
    return json.dumps(o, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _h(d) -> str:
    import hashlib, json
    return hashlib.sha256(
        json.dumps(d, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()
