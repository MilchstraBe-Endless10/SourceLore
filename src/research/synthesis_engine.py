#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合成引擎：packet → statement bank → LLM adapter → 逐句校验 → 分级产物。

★ 铁律：
  - 无 LLM 客户端 → 明确 NOT_CONFIGURED，不产出任何叙述
  - 有任何阻断级违规 → REJECTED_NOT_CITABLE
  - 全部句子通过校验 → 才可能是 STRICT_CITED
  - 否则一律 DRAFT_FOR_REVIEW（留人工复核，不得发布）
"""

import sys
import hashlib
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import statement_bank as SB
import citation_validator as CV
import llm_adapter as LA

SYNTHESIS_SCHEMA_VERSION = "research-synthesis/1"

S_NONE = "NO_SYNTHESIS"


def make_synthesis_id(*, packet_digest, bank_digest, adapter_state,
                      text_digest, verdict) -> str:
    return "SL-SYN-" + hashlib.sha256(json.dumps({
        "packet_digest": packet_digest, "bank_digest": bank_digest,
        "adapter_state": adapter_state, "text_digest": text_digest,
        "verdict": verdict,
        "synthesis_schema_version": SYNTHESIS_SCHEMA_VERSION},
        ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()[:32]


def synthesize(packet: dict, *, client=None, question: str = "") -> dict:
    """执行合成。返回结构化结果（不写任何文件）。"""
    bank = SB.build_bank(packet)
    out = LA.invoke(client, packet=packet, bank=bank, question=question)

    adapter_state = out["adapter_state"]
    if adapter_state == LA.A_NOT_CONFIGURED:
        return {
            "synthesis_schema_version": SYNTHESIS_SCHEMA_VERSION,
            "synthesis_state": S_NONE,
            "adapter_state": adapter_state,
            "bank": bank,
            "text": "",
            "validations": [],
            "verdict": "NOT_SYNTHESIZED",
            "llm_used": False,
            "real_call_verified": False,
            "note": ("未配置 LLM；本轮不生成任何研究叙述。"
                     "陈述池本身可用，但叙述留空。"),
        }

    v = CV.validate({"text": out["text"],
                     "statement_refs": out["statement_refs"]}, bank)
    has_blocking = bool(v["blocking_failures"])
    verdict = LA.classify(v, has_blocking=has_blocking)

    text_digest = hashlib.sha256(out["text"].encode()).hexdigest()
    sid = make_synthesis_id(
        packet_digest=packet.get("content_digest") or "",
        bank_digest=bank["bank_digest"],
        adapter_state=adapter_state,
        text_digest=text_digest,
        verdict=verdict)

    return {
        "synthesis_id": sid,
        "synthesis_schema_version": SYNTHESIS_SCHEMA_VERSION,
        "synthesis_state": verdict,
        "adapter_state": adapter_state,
        "provider": out.get("provider"),
        "model": out.get("model"),
        "bank": bank,
        "text": out["text"],
        "statement_refs": out["statement_refs"],
        "validation": v,
        "verdict": verdict,
        "llm_used": bool(out.get("llm_used")),
        "real_call_verified": False,
        "is_knowledge_authority": False,
        "publishable": False,
        "review_required": verdict != LA.SYN_STRICT,
        "limitations": list(packet.get("limitations") or []),
        "distribution_restrictions": dict(
            packet.get("distribution_restrictions") or {}),
        "note": _note(verdict, adapter_state),
    }


def _note(verdict, adapter_state) -> str:
    if adapter_state == LA.A_STUB:
        base = ("本产物由离线 stub 生成，**只验证引用校验通路**，"
                "不代表任何真实模型能力。")
    else:
        base = "本产物由注入的 LLM 客户端生成。"
    tail = {
        LA.SYN_STRICT: "全部句子通过引用校验，可用于内部严格引用场景。",
        LA.SYN_DRAFT: "存在无引用句子，只能作为待审草稿，不得以肯定事实语气使用。",
        LA.SYN_REJECTED: "存在阻断级违规（越界措辞/无效引用/把证据不足写成否定），"
                         "整条被拒绝。",
    }.get(verdict, "")
    return base + tail + " 真实 DeepSeek-V4.1 Flash 调用仍待验证。"
