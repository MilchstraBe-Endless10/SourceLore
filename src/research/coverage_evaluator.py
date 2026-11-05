#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""研究覆盖评估。

★ 这些状态描述"**能否回答研究问题**"，**不是** EC 的 verification_status。
  SL-CAP-0038 补充：不得另建第二套裁决状态机。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):   # noqa
    if _p not in sys.path:
        sys.path.insert(0, _p)

A_ANSWERABLE = "ANSWERABLE_FROM_EXISTING_EVIDENCE"
A_PARTIAL = "PARTIALLY_ANSWERABLE"
A_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
A_CONFLICT = "CONFLICT_REQUIRES_REVIEW"
A_ERROR = "RETRIEVAL_ERROR"
COVERAGE_STATES = frozenset({A_ANSWERABLE, A_PARTIAL, A_INSUFFICIENT,
                             A_CONFLICT, A_ERROR})

# ★ 明确的区分（题面 §6）
DISTINCTIONS = {
    "A_no_knowledge": "查询没有找到知识 → INSUFFICIENT_EVIDENCE",
    "B_found_insufficient": "找到 insufficient_evidence Claim → INSUFFICIENT_EVIDENCE",
    "C_found_refuted": "找到有效 refuted Claim → ANSWERABLE_FROM_EXISTING_EVIDENCE",
    "D_retrieval_failed": "索引或数据损坏 → RETRIEVAL_ERROR",
    "E_version_diff": "不同 Commit 的历史差异 → PARTIALLY_ANSWERABLE（不是证据冲突）",
}

MEANING = {
    A_ANSWERABLE: "现有知识资产足以回答该研究问题。",
    A_PARTIAL: "现有知识资产只覆盖了研究问题的一部分。",
    A_INSUFFICIENT: "现有知识资产不足以回答该研究问题（证据缺口已列出）。",
    A_CONFLICT: "现有证据之间存在冲突，需要人工复核，Research 不做裁决。",
    A_ERROR: "检索本身失败，无法判定可回答性。",
}


def evaluate(query: dict, retrieval: dict, findings: list,
             untrusted: list) -> dict:
    """评估可回答性。**只依据 retrieval/findings 的结构事实**。"""
    gaps = []

    RT = __import__("importlib").import_module("retriever")
    if not retrieval.get("ok"):
        return _mk(query, A_ERROR,
                   [{"gap": "RETRIEVAL_FAILED",
                     "detail": retrieval.get("detail") or retrieval.get("error")}]
                   + gaps,
                   [], extra={"retrieval_status": retrieval.get("status")})

    if retrieval.get("truncated"):
        gaps.append({"gap": "RESULT_TRUNCATED",
                     "detail": ("候选集达到上限，未出现在结果中的 Claim "
                                "不等于不存在；结论仅覆盖已检索范围")})

    if not findings and not untrusted:
        # ★ 区分「确实没有知识」与「知识存在但读不出来」
        corrupt = [e for e in (retrieval.get("excluded") or [])
                   if e.get("reason") in ("ASSET_CORRUPT",
                                          RT.E_ASSET_CORRUPT,
                                          "PAYLOAD_MALFORMED",
                                          "VERIFICATION_NOT_FOUND")]
        if corrupt:
            return _mk(query, A_ERROR,
                       gaps + [{"gap": "EVIDENCE_CORRUPT",
                                "detail": (f"{len(corrupt)} 条候选的数据无法读取"
                                           "（悬空引用或资产损坏），"
                                           "这不是'没有知识'，而是**检索通路受损**；"
                                           "不得据此判定命题为假")}],
                       [], extra={"retrieval_status": retrieval.get("status"),
                                  "distinction": "D_retrieval_failed",
                                  "corrupt_candidates": corrupt[:10]})
        # A：没有找到知识
        return _mk(query, A_INSUFFICIENT,
                   gaps + [{"gap": "NO_REGISTERED_CLAIM",
                            "detail": "现有资产中没有与该问题匹配的 Claim；"
                                      "这**不**意味着命题为假"}],
                   [], extra={"retrieval_status": retrieval.get("status"),
                              "distinction": "A_no_knowledge"})

    qtype = query.get("question_type")
    types = {f["finding_type"] for f in findings}

    if qtype == "VERSION_COMPARE":
        # E：两个 Commit 的差异 → PARTIALLY（不是冲突）
        if not findings:
            return _mk(query, A_INSUFFICIENT, gaps +
                       [{"gap": "VERSION_NO_CLAIM"}], [])
        return _mk(query, A_PARTIAL,
                   gaps + [{"gap": "VERSION_SCOPED",
                            "detail": "两个结论针对不同 Commit，各自成立于自己的"
                                      "版本；不构成同一事实的矛盾，也不推断祖先关系"}],
                   [], extra={"distinction": "E_version_diff"})

    if any(f.get("verdict_status") == "refuted" for f in findings):
        gaps.append({"gap": "HAS_REFUTED_FINDING",
                     "detail": "存在有效反证；结论为否定，仅针对该 Commit 与证据范围"})
        return _mk(query, A_ANSWERABLE, gaps, [],
                   extra={"distinction": "C_found_refuted"})

    if all(f.get("verdict_status") == "insufficient_evidence" for f in findings):
        return _mk(query, A_INSUFFICIENT,
                   gaps + [{"gap": "EVIDENCE_INSUFFICIENT",
                            "detail": "找到的 Claim 裁决为 insufficient_evidence；"
                                      "这**不**等于检索失败"}],
                   [], extra={"distinction": "B_found_insufficient"})

    if untrusted:
        gaps.append({"gap": "UNTRUSTED_FINDINGS_EXCLUDED",
                     "detail": f"{len(untrusted)} 条 Claim 缺少可定位证据，"
                               "已移出可采信集合"})

    if any(f.get("verdict_status") == "supported" for f in findings):
        has_limits = any(f.get("limitations") for f in findings)
        state = A_PARTIAL if (has_limits or untrusted) else A_ANSWERABLE
        gaps.append({"gap": "SCOPE_BOUND",
                     "detail": "结论仅适用于所记录的版本与证据范围"})
        return _mk(query, state, gaps, [])

    return _mk(query, A_INSUFFICIENT, gaps +
               [{"gap": "UNCLASSIFIED"}], [])


def _mk(query, state, gaps, unresolved, extra=None) -> dict:
    out = {
        "coverage_state": state,
        "coverage_meaning": MEANING[state],
        "not_a_verification_status": True,
        "question_type": query.get("question_type"),
        "gaps": gaps,
        "unresolved_questions": unresolved,
        "evaluated_on": "existing_knowledge_only",
        "llm_used": False,
    }
    out.update(extra or {})
    return out
