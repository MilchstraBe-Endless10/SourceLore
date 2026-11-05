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


def select_findings(store, pairs: list, query: dict) -> dict:
    """从 (claim, verification) 对生成 findings。

    ★ 只读投影：不改裁决、不补造证据、不把缺失当否证。
    ★ 证据必须**可核对**，不能只凭非空 evidence_refs 就采信。
    """
    findings, untrusted = [], []
    known = _known_fact_ids(store, query.get("repository_id"))
    for pr in pairs:
        c, v = pr["claim"], pr["verification"]
        status = v.get("status")
        ftype, verdict = _map_status(status)
        refs = _evidence_refs(v, c)
        limited = []

        integrity = assess_evidence_integrity(store, refs, known)
        if integrity["level"] in (EV_NONE, EV_UNRESOLVED):
            # ★ 没有可核对证据 → 不可采信
            untrusted.append({
                "claim_id": c["claim_id"],
                "verification_id": v.get("verification_id"),
                "reason": ("NO_LOCATABLE_EVIDENCE"
                           if integrity["level"] == EV_NONE
                           else "EVIDENCE_NOT_RESOLVABLE"),
                "evidence_integrity": integrity["level"],
                "integrity_reasons": integrity["reasons"],
                "note": MEANING[F_EVIDENCE_MISSING]})
            continue

        # ★ 覆盖范围要**同时**看两处：
        #   1) EC 的 local_coverage_only 标记
        #   2) 证据链里 snapshot manifest 的真实 completeness_status
        #   （只信 EC 标记会漏判 —— EC 在某些 insufficient 路径下不设该标记）
        coverage = _snapshot_completeness(refs)
        if integrity["level"] == EV_PARTIAL:
            limited.append("证据只能部分核对：部分引用无法解析，"
                           "该结论的证据链不完整")
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
            "evidence_integrity": integrity["level"],
            "evidence_integrity_detail": {
                "total": integrity["total"],
                "resolved": integrity["resolved"],
                "reasons": integrity["reasons"]},
            "limitations": limited,
            "verification_content_hash": v.get("content_hash"),
            "claim_content_hash": c.get("content_hash"),
        })

    findings = sorted(findings, key=lambda f: (f["claim_commit_sha"] or "",
                                               f["claim_id"], f["finding_id"]))
    levels = {}
    for f in findings:
        levels[f["evidence_integrity"]] = levels.get(f["evidence_integrity"], 0) + 1
    return {"ok": True, "findings": findings, "untrusted": untrusted,
            "evidence_cap": EVIDENCE_CAP,
            "evidence_integrity_summary": {
                "levels": levels,
                "unresolvable_count": len(untrusted),
                "known_fact_count": len(known),
                "note": ("证据可信度按**可核对性**判定，"
                         "不以是否非空为准")}}


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


FACT_TYPE = "extracted_fact"

# 证据完整性等级
EV_FULL = "FULLY_LOCATABLE"
EV_PARTIAL = "PARTIALLY_LOCATABLE"
EV_UNRESOLVED = "UNRESOLVED_NO_INTEGRITY"
EV_NONE = "NO_EVIDENCE"

# ★ 必须能解析出身份的引用种类；解析不出即不可采信
_JSON_REQUIRED = {
    "tree_entry": ("kind", "path", "object_type"),
    "source_snapshot": ("kind", "commit_sha", "snapshot_asset_id",
                        "completeness_status"),
}


def _known_fact_ids(store, repository_id, cap: int = 500) -> set:
    """★ 从 Storage 收集真实存在的 fact_id。

    A 层不可篡改，但引用**可以**指向不存在的 fact ——
    非空 evidence_refs 并不等于证据可信。
    """
    ids = set()
    try:
        rows = store.conn.execute(
            "SELECT payload_json FROM assets WHERE asset_type=? "
            "AND repository_id=? LIMIT ?",
            (FACT_TYPE, repository_id, cap)).fetchall()
    except Exception:
        return ids
    for r in rows:
        try:
            pj = json.loads(r["payload_json"])
        except Exception:
            continue
        for k in ("fact_id",):
            if pj.get(k):
                ids.add(str(pj[k]))
    return ids


def assess_evidence_integrity(store, refs: list, known_facts: set) -> dict:
    """★ 逐条解析引用，给出完整性等级。

    只"非空"不算可信：必须能解析出可核对的身份，且 fact 引用真实存在。
    """
    if not refs:
        return {"level": EV_NONE, "total": 0, "resolved": 0,
                "reasons": ["无证据引用"]}

    resolved, reasons = 0, []
    for r in refs:
        if not isinstance(r, str):
            reasons.append("引用不是字符串")
            continue
        if r.startswith("fact:"):
            fid = r.split(":", 1)[1]
            if fid in known_facts:
                resolved += 1
            else:
                reasons.append(f"fact 引用不存在：{fid}")
            continue
        if r.startswith("{"):
            try:
                o = json.loads(r)
            except Exception:
                reasons.append("证据引用不是合法 JSON")
                continue
            kind = o.get("kind")
            need = _JSON_REQUIRED.get(kind)
            if not need:
                reasons.append(f"未知引用种类：{kind}")
                continue
            missing = [k for k in need if not o.get(k)]
            if missing:
                reasons.append(f"{kind} 缺少必需字段：{missing}")
                continue
            resolved += 1
            continue
        reasons.append(f"无法识别的引用形态：{r[:40]}")

    total = len(refs)
    if resolved == total:
        level = EV_FULL
    elif resolved > 0:
        level = EV_PARTIAL
    else:
        level = EV_UNRESOLVED
    return {"level": level, "total": total, "resolved": resolved,
            "reasons": sorted(set(reasons))[:10]}


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
