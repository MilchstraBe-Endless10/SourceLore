#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research 引擎：query → retrieval → findings → coverage → packet。

★ 只读。不调 LLM、不联网、不重新裁决、不写权威库。
"""

import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views"), str(_HERE.parent / "storage"),
           str(_HERE.parent / "lifecycle"), str(_HERE.parent / "renderer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import query_models as QM
import retriever as RT
import evidence_selector as ES
import coverage_evaluator as CE
import research_packet as RP
import view_models as VM


def run_research(store, query: dict, *,
                 include_diagnostics: bool = False) -> dict:
    """执行一次确定性研究。返回 packet（可选带诊断元数据）。"""
    t0 = time.time()

    # ── 1. 检索 ──────────────────────────────────────────
    qtype = query["question_type"]
    if qtype == QM.Q_VERSION_COMPARE:
        ret = RT.retrieve_version_pair(store, query)
        pairs, excluded, truncated = [], [], False
        if not ret.get("ok"):
            retrieval = {"ok": False, "status": RT.RETRIEVAL_ERROR,
                         "error": RT.E_INDEX_CORRUPT,
                         "detail": ret.get("detail", "")}
            pairs = []
        else:
            for side in ("commit_a", "commit_b"):
                r = ret[side]
                vr = RT.retrieve_verifications(store, r["kept"], query)
                pairs.extend(vr.get("pairs") or [])
                excluded.extend(r.get("excluded") or [])
                excluded.extend(vr.get("excluded") or [])
                truncated = truncated or bool(r.get("truncated"))
            retrieval = {"ok": True,
                         "status": RT.TRUNCATED if truncated else RT.OK,
                         "truncated": truncated,
                         "candidate_count": sum(
                             ret[s]["candidate_count"] for s in
                             ("commit_a", "commit_b")),
                         "excluded": excluded,
                         "cap": query.get("max_results"),
                         "note": ("结果集已截断：未出现的 Claim 不等于不存在"
                                  if truncated else "")}
    else:
        retrieval = RT.retrieve_claims(store, query)
        pairs = []
        if retrieval.get("ok"):
            vr = RT.retrieve_verifications(store, retrieval["kept"], query)
            pairs = vr.get("pairs") or []
            retrieval["excluded"] = (retrieval.get("excluded") or []) + \
                                    list(vr.get("excluded") or [])

    # ── 2. 证据筛选 ─────────────────────────────────────
    sel = ES.select_findings(store, pairs, query)

    # ── 3. 覆盖评估 ─────────────────────────────────────
    cov = CE.evaluate(query, retrieval, sel["findings"], sel["untrusted"])

    # ── 4. 限制继承（原样保留，不降级）────────────────────
    cov["snapshot_completeness"] = _snapshot_coverage(store, query)
    # ★ 证据链完整性无法确认时不得声称"完全可答"
    _downgrade_for_unverifiable_chain(cov, cov["snapshot_completeness"])
    limits = _collect_limitations(sel["findings"], retrieval, cov, pairs,
                                  cov["snapshot_completeness"])
    dist = VM.distribution_restrictions()
    prov = _provenance_summary(sel["findings"])
    review = _review_summary(sel["findings"])
    conflicts = _conflicts(sel["findings"])

    pkt = RP.build_packet(
        query=query, retrieval=retrieval, coverage=cov,
        findings=sel["findings"], untrusted=sel["untrusted"],
        evidence_integrity=sel.get("evidence_integrity_summary"),
        limitations=limits, distribution=dist,
        provenance_summary=prov, review_summary=review,
        freshness_summary={"note": ("Research 不重评估新鲜度；"
                                    "新鲜度以 View/Assessment 原值为准")},
        conflicts=conflicts)

    if include_diagnostics:
        pkt["run_diagnostics"] = {
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
            "note": "诊断元数据，不参与 content_digest"}
    return pkt


def _downgrade_for_unverifiable_chain(cov, snapshots) -> None:
    """★ 快照完整性无法确认（索引丢失/无快照资产）→ 不得声称 ANSWERABLE。

    这与"证据不足"不同：EC 裁决仍是它自己记录的值，Research 不改裁决；
    但**研究结论的适用范围**必须收窄，并显式说明证据链不完整。
    """
    unknown = sorted(c for c, v in (snapshots or {}).items()
                     if (v or {}).get("completeness") in ("", "UNKNOWN"))
    if not unknown:
        return
    if cov.get("coverage_state") == "ANSWERABLE_FROM_EXISTING_EVIDENCE":
        cov["coverage_state"] = "PARTIALLY_ANSWERABLE"
        cov["coverage_meaning"] = (
            "现有知识资产覆盖了该研究问题，但**证据链完整性无法确认**"
            "（快照索引缺失或状态未知），因此不能给出完全可答的判定。")
    cov.setdefault("gaps", []).append({
        "gap": "EVIDENCE_CHAIN_UNVERIFIABLE",
        "detail": (f"以下 Commit 的快照完整性无法确认：{unknown}；"
                   "这不改变 EC 已记录的裁决，但限制研究结论的适用范围")})


def _snapshot_coverage(store, query) -> dict:
    """★ 从 Storage 读快照真实完整性（不只信 EC 标记）。"""
    out = {}
    for c in (query.get("commit_sha"), query.get("compare_commit_sha")):
        if not c:
            continue
        r = RT.snapshot_completeness(store, query["repository_id"], c)
        out[c] = {"completeness": r.get("completeness") or "UNKNOWN"}
    return out


def _collect_limitations(findings, retrieval, cov, pairs=None,
                         snapshots=None) -> list:
    """★ 限制原样继承；不因"影响可读性"而丢弃。

    包括那些**被移出可采信集合**的 Claim —— 它们的覆盖范围限制
    仍然约束整个研究结论。
    """
    out = []
    for f in findings:
        out.extend(f.get("limitations") or [])
    # ★ 从检索原始 refs 汇总快照真实覆盖范围（即使 finding 已被剔除）
    import json as _json
    partial = False
    for pr in (pairs or []):
        v = pr.get("verification") or {}
        refs = v.get("evidence_refs_raw") or v.get("evidence_refs") or []
        if v.get("local_coverage_only"):
            partial = True
        for r in refs:
            if isinstance(r, str) and r.startswith("{"):
                try:
                    o = _json.loads(r)
                except Exception:
                    continue
                if o.get("kind") == "source_snapshot" and \
                        o.get("completeness_status") == "PARTIAL":
                    partial = True
    # ★ Storage 侧真实完整性
    unverifiable = []
    for c, info in (snapshots or {}).items():
        cs = (info or {}).get("completeness")
        if cs == "PARTIAL":
            partial = True
        elif cs in ("", "UNKNOWN"):
            unverifiable.append(c)
    if unverifiable:
        out.append("证据链完整性无法确认（快照索引缺失或状态未知）："
                   "结论仅覆盖已声明的证据范围，不得据此扩展适用范围")
    if partial:
        out.append("仅局部覆盖（快照 completeness=PARTIAL）："
                   "未覆盖部分不得判为不存在")
    if retrieval.get("truncated"):
        out.append("结果集已截断：结论仅覆盖已检索范围")
    for g in cov.get("gaps") or []:
        d = g.get("detail")
        if d:
            out.append(str(d))
    if cov.get("coverage_state") == CE.A_INSUFFICIENT:
        out.append("证据不足，不得据此得出肯定或否定结论")
    out.append("Research 产物不是知识权威，不得。")
    out = [x for x in out if x]
    # 去掉结尾那条占位
    out = [x for x in out if "不得。" not in x]
    out.append("Research 产物不是知识权威，不得作为 Claim 裁决或发布依据")
    out.append("分发门禁仍为 FROZEN_INTERNAL_RESTRICTED，仅限本地内部消费")
    return sorted(set(out))


def _provenance_summary(findings) -> dict:
    """★ 来源原样继承，不做"最强来源"升级。"""
    return {
        "note": ("来源等级以 KnowledgeView 原值为准；Research 不做升级或混合取强"),
        "finding_levels": sorted({
            (f.get("claim_payload") or {}).get("provenance_hint") or "unknown"
            for f in findings}),
        "mixed_provenance": False,
    }


def _review_summary(findings) -> dict:
    statuses = sorted({f.get("review_status") or "pending_review"
                       for f in findings})
    return {"review_statuses": statuses,
            "any_approved": "approved" in statuses,
            "note": "Research 不修改 review_status"}


def _conflicts(findings) -> list:
    """★ 只做分辨与分流，不裁决（SL-CAP-0038 补充）。"""
    out = []
    commits = {}
    for f in findings:
        commits.setdefault(f.get("claim_commit_sha"), []).append(f)
    if len(commits) > 1:
        out.append({
            "kind": "MULTI_COMMIT_DIFFERENCE",
            "note": ("不同 Commit 下的结论各自成立，**不是**同一事实的证据冲突；"
                     "不推断祖先关系"),
            "commits": sorted(k for k in commits if k)})
    statuses = {f.get("verdict_status") for f in findings}
    if len(statuses) > 1:
        out.append({
            "kind": "VERDICT_DIVERGENCE_ACROSS_COMMITS",
            "note": ("同一路径在不同 Commit 上裁决不同；属版本差异，"
                     "**不是**同一范围内的证据冲突；"
                     "不得据此推断两个 Commit 的祖先或先后关系"),
            "verdicts": sorted(s for s in statuses if s)})
    return out
