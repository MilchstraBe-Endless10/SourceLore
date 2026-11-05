#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM Adapter：可注入的叙述生成接口。

★ 本模块**不内置任何真实网络调用**。
  真实 API 由调用方注入 client；未注入时一律走离线 stub。
"""

import sys
import hashlib
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ADAPTER_SCHEMA_VERSION = "llm-adapter/1"

# 适配器状态
A_NOT_CONFIGURED = "NOT_CONFIGURED"
A_STUB = "OFFLINE_STUB"
A_OFFLINE_FIXTURE = "OFFLINE_FIXTURE_REPLAY"
A_REAL_CALLED = "REAL_CALL_ATTEMPTED"
A_REAL_VERIFIED = "REAL_CALL_VERIFIED"
A_REAL_FAILED = "REAL_CALL_FAILED"

# ★ 真实调用是否已验证：本轮保持 False
REAL_CALL_VERIFIED = False


class AdapterNotConfigured(RuntimeError):
    pass


def make_stub_client(preset=None):
    """离线 stub：返回预设文本，**不代表模型能力**。"""
    preset = preset or {}

    def _client(prompt, bank):
        return {
            "text": preset.get("text", ""),
            "statement_refs": list(preset.get("statement_refs") or []),
            "provider": "offline-stub",
            "model": "offline-stub",
        }
    return _client


def invoke(client, *, packet: dict, bank: dict, question: str = "") -> dict:
    """调用适配器。**输出必须带回 bank 与引用校验所需信息。**

    ★ client 为 None → 明确返回 NOT_CONFIGURED，不伪装。
    """
    if client is None:
        return {
            "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
            "adapter_state": A_NOT_CONFIGURED,
            "text": "",
            "statement_refs": [],
            "provider": None,
            "model": None,
            "llm_used": False,
            "real_call_verified": False,
            "note": ("未配置任何 LLM 客户端；本轮不生成叙述。"
                     "真实 DeepSeek-V4.1 Flash 调用仍待验证。"),
        }
    raw = client(_build_prompt(packet, bank, question), bank)
    if not isinstance(raw, dict):
        return {
            "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
            "adapter_state": A_REAL_FAILED,
            "text": "", "statement_refs": [],
            "error": "客户端返回非字典",
            "llm_used": False, "real_call_verified": False,
        }
    return {
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "adapter_state": raw.get("adapter_state", A_STUB),
        "text": str(raw.get("text") or ""),
        "statement_refs": list(raw.get("statement_refs") or []),
        "provider": raw.get("provider"),
        "model": raw.get("model"),
        "llm_used": raw.get("provider") not in (None, "offline-stub"),
        "real_call_verified": False,
        "note": ("offline-stub 的输出只用于验证校验通路，"
                 "不代表真实模型能力" if raw.get("provider") == "offline-stub"
                 else "真实调用未经验证"),
    }


def _build_prompt(packet: dict, bank: dict, question: str) -> str:
    """★ Prompt 只含结构化陈述与引用 ID，不含原始仓库文本。"""
    lines = [
        "你是研究材料整理器。只允许使用下列陈述，每条必须带 statement_id。",
        "禁止推断、禁止越界、禁止把 evidence_insufficient 写成否定。",
        "",
        f"研究问题：{question or packet.get('query_id', '')}",
        f"可回答性：{(packet.get('coverage_assessment') or {}).get('coverage_state')}",
        "",
        "可用陈述：",
    ]
    for s in bank.get("statements") or []:
        lines.append(f"- [{s['statement_id']}] {s['text']}")
    lines.append("")
    lines.append("输出 JSON：{text, statement_refs}。每句都要能在 statement_refs 找到依据。")
    return "\n".join(lines)


# ── 门禁：Synthesis 分级 ────────────────────────────────
SYN_STRICT = "STRICT_CITED"
SYN_DRAFT = "DRAFT_FOR_REVIEW"
SYN_REJECTED = "REJECTED_NOT_CITABLE"

SYNTHESIS_STATES = frozenset({SYN_STRICT, SYN_DRAFT, SYN_REJECTED})


def classify(validation: dict, *, has_blocking: bool) -> str:
    """按校验结果给合成产物定级。

    ★ 只有**全部句子都通过引用校验**才可能是 STRICT_CITED。
    """
    if has_blocking:
        return SYN_REJECTED
    if validation.get("is_strict_citable"):
        return SYN_STRICT
    return SYN_DRAFT
