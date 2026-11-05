#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐句引用校验：把候选叙述切成句子，逐句核对是否绑定真实陈述。

★ SL-CAP-0039 的可判定实现：
  - 无引用的句子 → INFERENCE
  - 引用不存在的 statement_id → 无效引用，句子降级
  - 含放大措辞（无证据的肯定）→ 违规
"""

import sys
import re
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

VALIDATOR_SCHEMA_VERSION = "citation-validator/1"
MAX_SENTENCE = 2000
GROUNDING_MIN = 0.20   # 接地度下限（低于此视为"引用了但没支撑"）

# 句子切分：中英文句末
_SPLIT = re.compile(r"(?<=[。．.！!？?\n])\s*")

# ★ 放大 / 越界措辞：命中即违规（保持与 P4A 同一口径 + 研究特有）
AMPLIFY = (
    "完全正确", "整个项目存在问题", "该软件正确", "肯定不存在",
    "已证明错误", "必然无效", "当前最新", "当前有效", "已发布",
    "该软件存在漏洞", "具备完善文档", "功能完备", "项目质量高",
    "因此该项目", "由此可见该项目",
)
# ★ 把 insufficient 写成否定
NEGATE_INSUFFICIENT = (
    "该命题错误", "该命题为假", "不存在该文件", "可以确认不存在",
    "已证实不存在",
)

C_OK = "CITED_OK"
C_NO_CITATION = "NO_CITATION"
C_BAD_CITATION = "INVALID_STATEMENT_REF"
C_AMPLIFIED = "AMPLIFIED_BEYOND_EVIDENCE"
C_NEGATED_INSUFFICIENT = "INSUFFICIENT_AS_NEGATION"
C_EMPTY = "EMPTY_SENTENCE"
C_TOO_LONG = "SENTENCE_TOO_LONG"
C_NOT_GROUNDED = "NOT_GROUNDED_IN_CITED_STATEMENT"

BLOCKING = frozenset({C_BAD_CITATION, C_AMPLIFIED,
                      C_NEGATED_INSUFFICIENT})
# ★ 非阻断但**也不得 STRICT** 的代码
DOWNGRADE_ONLY = frozenset({C_NOT_GROUNDED, C_NO_CITATION})


def split_sentences(text: str) -> list:
    out = [s.strip() for s in _SPLIT.split(text or "") if s.strip()]
    return [s[:MAX_SENTENCE] for s in out]


def validate(claim: dict, bank: dict) -> dict:
    """校验一条候选叙述。

    claim: {"text": str, "statement_refs": [sid, ...]}
    返回逐条判定 + 是否可用于 STRICT_CITED。
    """
    statements = {s["statement_id"]: s for s in bank.get("statements") or []}
    text = claim.get("text") or ""
    refs = list(claim.get("statement_refs") or [])

    verdicts = []
    for sent in split_sentences(text):
        v = _judge(sent, refs, statements)
        verdicts.append(v)

    bad = [v for v in verdicts if v["code"] in BLOCKING]
    uncited = [v for v in verdicts if v["code"] in
               (C_NO_CITATION, C_EMPTY)]
    ungrounded = [v for v in verdicts if v["code"] == C_NOT_GROUNDED]

    # ★ 整条叙述的可引用性：全部句子都 CITED_OK 才算合格
    overall = (C_OK if verdicts and not bad and not uncited and not ungrounded
               else (bad[0]["code"] if bad
                     else (C_NOT_GROUNDED if ungrounded
                           else (C_NO_CITATION if uncited else C_EMPTY))))

    return {
        "validator_schema_version": VALIDATOR_SCHEMA_VERSION,
        "sentence_count": len(verdicts),
        "verdicts": verdicts,
        "blocking_failures": [v["code"] for v in bad],
        "uncited_count": len(uncited),
        "ungrounded_count": len(ungrounded),
        "overall": overall,
        "is_strict_citable": overall == C_OK,
        "unbound_references": [r for r in refs if r not in statements],
    }


_CJK = re.compile(r"[\u4e00-\u9fff]")
_WORD = re.compile(r"[A-Za-z0-9_]{2,}")
_STOP = frozenset({
    "the", "and", "for", "with", "that", "this", "are", "was", "were",
    "from", "into", "have", "has", "not", "all", "any", "can", "will",
    "该", "这", "那", "的", "了", "在", "是", "与", "和", "为", "已",
    "上", "中", "对", "并", "其", "或", "有", "不", "等", "个", "条",
})


def _tokens(text: str) -> set:
    out = set()
    for w in _WORD.findall(text or ""):
        lw = w.lower()
        if lw not in _STOP:
            out.add(lw)
    for ch in _CJK.findall(text or ""):
        if ch not in _STOP:
            out.add(ch)
    return out


def grounding_ratio(sentence: str, refs: list, statements: dict) -> float:
    """句子与所引陈述的词汇重合度（0..1）。"""
    toks = _tokens(sentence)
    if not toks:
        return 0.0
    cited = set()
    for r in refs:
        s = statements.get(r)
        if s:
            cited |= _tokens(s.get("text") or "")
    if not cited:
        return 0.0
    return len(toks & cited) / len(toks)


def _judge(sent: str, refs: list, statements: dict) -> dict:
    reasons = []
    code = C_OK

    if len(sent) > MAX_SENTENCE:
        code, reasons = C_TOO_LONG, ["句子超长"]

    for phrase in AMPLIFY:
        if phrase in sent:
            code = C_AMPLIFIED
            reasons.append(f"越界措辞：{phrase}")
            break
    else:
        for phrase in NEGATE_INSUFFICIENT:
            if phrase in sent:
                code = C_NEGATED_INSUFFICIENT
                reasons.append(f"把证据不足写成否定：{phrase}")
                break

    bad_refs = [r for r in refs if r not in statements]
    if bad_refs and code == C_OK:
        code = C_BAD_CITATION
        reasons.append(f"引用了不存在的陈述：{bad_refs[:3]}")

    if not refs and code == C_OK:
        code = C_NO_CITATION
        reasons.append("无引用——只能作为 INFERENCE，不得以肯定事实语气出现")

    # ★ 引用了真实陈述但内容与它无关 → 不得 STRICT
    ratio = grounding_ratio(sent, refs, statements) if refs else 0.0
    if code == C_OK and ratio < GROUNDING_MIN:
        code = C_NOT_GROUNDED
        reasons.append(f"引用与句意几乎无关（接地度 {ratio:.2f} < "
                       f"{GROUNDING_MIN}）——引用不构成支撑")

    return {"sentence": sent, "code": code,
            "tier": "CITED" if code == C_OK else "INFERENCE",
            "reasons": reasons,
            "grounding": round(ratio, 3),
            "statement_refs": refs}
