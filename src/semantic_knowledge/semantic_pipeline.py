#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技术语义知识生产链路（P2-D3）。

协作模型（关键）：
  宿主模型（注入式 client）  —— 只做「理解与表述」：读程序给的证据片段，
      提出候选技术命题，并从程序给出的证据下标里挑引用。**不能伪造证据**，
      **不能声明来源级别/裁决/支持性**（那些由确定性程序决定）。
  确定性程序（本模块）        —— 做「鉴证与落库」：按问题从 section_fts 召回
      证据 → 校验每条证据的 byte/SHA/OID 与授权字段 → 继承来源（只降不升）→
      按来源类别封顶支持性（文档自述不得冒充源码事实）→ 幂等写入 A 层。

未注入 client 时：返回 NOT_CONFIGURED，**不产生任何命题**，不用模型记忆补写。
这对齐 llm_adapter 的注入式设计，也不违反「不得伪造工具执行或证据」。

零网络：本模块只调用本地 section_index / semantic_store；不访问 GitHub。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("semantic_knowledge", "storage", "views"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import semantic_models as SM
import semantic_store as SS

NOT_CONFIGURED = "HOST_MODEL_NOT_CONFIGURED"
PRODUCED = "PRODUCED"
REUSED = "REUSED_EXISTING"

# 文档自述不得作为这些「源码事实类」知识的直接证据（Gate 4）。
_SOURCE_FACT_KINDS = frozenset({
    SM.K_DEPENDENCY, SM.K_DATA_FLOW, SM.K_CORE_MODULE,
    SM.K_ARCHITECTURE, SM.K_API_SURFACE,
})


def _evidence_packet(matches):
    """把 section_fts 命中转成宿主可读的证据包。

    每条证据带一个下标；宿主只能引用下标，不能自造 evidence ref。
    来源级别（source_category/provenance/copy/distribution）原样透传。
    """
    items = []
    for i, m in enumerate(matches):
        ref = SM.SemanticEvidenceRef.from_match(m)
        items.append({
            "index": i,
            "file_path": ref.file_path,
            "heading": ref.heading,
            "source_category": ref.source_category,
            "provenance_level": ref.provenance_level,
            "copy_permitted": ref.copy_permitted,
            "distribution_allowed": ref.distribution_allowed,
            "content_sha256": ref.content_sha256,
            "git_blob_oid": ref.git_blob_oid,
            "line_start": ref.line_start, "line_end": ref.line_end,
            "byte_start": ref.byte_start, "byte_end": ref.byte_end,
            "ref_complete": ref.ref_complete,
            "excerpt": str(m.get("body") or "")[:1200],
        })
    return items


def _cap_support_level(support_level, knowledge_kind, source_category,
                       evidence_complete):
    """确定性封顶：文档自述不得冒充源码事实；无完整证据不得直接支持。"""
    if not evidence_complete:
        return SM.S_NOT_SUPPORTED
    if (source_category == SM.SRC_DOC_SELF_REPORT
            and knowledge_kind in _SOURCE_FACT_KINDS
            and support_level == SM.S_DIRECTLY_SUPPORTED):
        # 文档自述只支持「文档声称」，对源码事实类命题降为部分支持。
        return SM.S_PARTIALLY_SUPPORTED
    return support_level


def _resolve_levels(support_level):
    """支持性 → 裁决 / 覆盖（确定性映射，复用 EC 口径）。

    ★ 只有「直接支持」才给 supported；「部分支持」给 insufficient_evidence
      + PARTIAL 覆盖，绝不冒充源码已验证事实（Gate 4）。
    """
    if support_level == SM.S_DIRECTLY_SUPPORTED:
        return SM.V_SUPPORTED, SM.C_ANSWERABLE
    if support_level == SM.S_PARTIALLY_SUPPORTED:
        return SM.V_INSUFFICIENT, SM.C_PARTIAL
    return SM.V_INSUFFICIENT, SM.C_INSUFFICIENT


def produce(store, *, repository_id, commit_sha, questions, client=None,
            limit_per_question=5, dry_run=False):
    """生产一批技术语义命题。

    questions: list[{"question": str, "knowledge_kind": str, "subject": str}]
    client: callable(packet: dict) -> dict
        返回 {"propositions":[{"proposition","knowledge_kind","subject",
        "question"(可选),"support_level","evidence_indices":[int],
        "limitations":[str]}]}。client 由宿主注入；未注入 → NOT_CONFIGURED。
    dry_run: 只生成并鉴证，不写 A 层（用于验收/预演）。

    返回 {ok, state, produced, skipped, ingested, details[], network_requests:0}
    """
    if client is None or not callable(client):
        return {"ok": False, "state": NOT_CONFIGURED, "propositions": [],
                "detail": "未注入宿主模型 client；不用模型记忆补写命题",
                "network_requests": 0}

    import section_index as SI

    details = []
    ingested = []
    skipped = []

    for q in (questions or []):
        question = str(q.get("question") or "")
        kind = str(q.get("knowledge_kind") or SM.K_ARCHITECTURE)
        subject = SM.normalize_subject(q.get("subject") or question)
        if kind not in SM.KNOWLEDGE_KINDS or not question:
            skipped.append({"reason": "INVALID_TASK", "task": q})
            continue

        # 1) 确定性召回证据（section_fts 已按 repository+commit 隔离）
        recall = SI.query_sections(
            store, repository_id=str(repository_id), commit_sha=commit_sha,
            question=question, limit=limit_per_question)
        matches = recall.get("matches") or []
        if not matches:
            skipped.append({"question": question, "reason": "NO_EVIDENCE"})
            continue

        # 2) 宿主只读证据片段，提出候选命题（只能引用证据下标）
        packet = {
            "repository_id": str(repository_id), "commit_sha": commit_sha,
            "question": question, "knowledge_kind": kind, "subject": subject,
            "evidence": _evidence_packet(matches),
        }
        try:
            out = client(packet)
        except Exception as e:
            skipped.append({"question": question,
                            "reason": "CLIENT_ERROR", "error": repr(e)})
            continue
        candidates = (out or {}).get("propositions") or []
        if not isinstance(candidates, list):
            skipped.append({"question": question,
                            "reason": "BAD_CLIENT_OUTPUT"})
            continue

        # 3) 确定性鉴证 + 落库
        for cand in candidates:
            if not isinstance(cand, dict):
                skipped.append({"question": question,
                                "reason": "BAD_CANDIDATE"})
                continue
            text = str(cand.get("proposition") or "").strip()
            if not text:
                skipped.append({"question": question,
                                "reason": "EMPTY_PROPOSITION"})
                continue

            # 宿主只能挑下标；越界/非法/不完整证据一律丢弃，不能伪造。
            idxs = cand.get("evidence_indices") or []
            picked = []
            for idx in idxs:
                if not isinstance(idx, int) or idx < 0 or idx >= len(packet["evidence"]):
                    continue
                ep = packet["evidence"][idx]
                # 找回原始 match 以构造完整 ref（含 sha/oid/byte）
                picked.append(SM.SemanticEvidenceRef.from_match(matches[idx]))

            # 授权：只接受证据链完整的引用。copy_permitted=false 是内部复制限制，
            # 不是引用禁止：命题在 content_payload 中保守继承标志（任一证据 DENY
            # 则命题 DENY），历史误标原样继承、不升级、不洗白。
            picked = [e for e in picked if e.ref_complete]
            if not picked:
                skipped.append({"question": question,
                                "reason": "NO_VALID_EVIDENCE",
                                "proposition": text[:80]})
                continue

            ck = str(cand.get("knowledge_kind") or kind)
            if ck not in SM.KNOWLEDGE_KINDS:
                ck = kind  # 不信任宿主给的分类，回落任务声明值
            csubject = SM.normalize_subject(cand.get("subject") or subject)
            proposed = str(cand.get("support_level") or SM.S_NOT_SUPPORTED)

            # 来源类别：取所有证据里最低的（只降不升）
            eff_src = SM.effective_source_category(*[e.source_category for e in picked])
            # 支持性封顶（文档自述不得冒充源码事实）
            support = _cap_support_level(
                proposed, ck, eff_src, all(e.ref_complete for e in picked))
            verdict, coverage = _resolve_levels(support)

            prop = SM.SemanticProposition(
                proposition=text,
                knowledge_kind=ck,
                repository_id=str(repository_id),
                commit_sha=commit_sha,
                subject=csubject,
                evidence=picked,
                support_level=support,
                source_category=eff_src,
                verification_status=verdict,
                coverage_state=coverage,
                limitations=[str(x) for x in (cand.get("limitations") or [])],
                question=str(cand.get("question") or question),
            )

            if dry_run:
                ingested.append({"state": "DRY_RUN", "proposition_id": prop.proposition_id,
                                 "proposition": text, "support_level": support,
                                 "source_category": eff_src})
                continue

            res = SS.ingest_proposition(store, prop)
            if not res.get("ok"):
                skipped.append({"question": question, "reason": "INGEST_FAIL",
                                "detail": res.get("detail"), "proposition": text[:80]})
                continue
            ingested.append({
                "state": res["state"], "proposition_id": res["proposition_id"],
                "proposition": text, "support_level": support,
                "source_category": eff_src, "verification_status": verdict,
                "evidence_count": len(picked),
            })

        details.append({"question": question, "evidence_count": len(matches),
                        "candidates": len(candidates)})

    return {"ok": True, "state": PRODUCED,
            "repository_id": str(repository_id), "commit_sha": commit_sha,
            "ingested": ingested, "skipped": skipped, "details": details,
            "propositions": ingested,
            "network_requests": 0}


def make_host_client(model_callable):
    """把一个宿主可调用对象包装成 client 契约（薄适配，不改语义）。"""
    if not callable(model_callable):
        return None
    def _client(packet):
        return model_callable(packet)
    return _client
