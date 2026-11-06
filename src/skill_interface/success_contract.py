#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-42 成功契约：区分"命令跑完"与"知识真的建立了"。

★ 核心教训：`ok=True` 只表示 COMMAND_EXECUTED。
  SNAPSHOT_SAVED / FACTS_PERSISTED / CLAIMS_VERIFIED / KNOWLEDGE_QUERYABLE
  每一档都要独立判定，不能因为前一档成功就宣布后一档成功。
"""

STATUS_LEVELS = (
    "COMMAND_EXECUTED",
    "SNAPSHOT_SAVED",
    "CONTENT_CAPTURED",
    "PARSING_COMPLETED",
    "FACTS_PERSISTED",
    "CLAIMS_VERIFIED",
    "KNOWLEDGE_QUERYABLE",
    "CARD_RENDERED",
)


def build_contract(*, executed=False, snapshot=False, content_captured=False,
                   parsing=False, facts=0, claims=0, verifications=0,
                   queryable=False, card=False, coverage=None):
    """构造成功契约。

    ★ 每一档独立，不自动向上传递。
    ★ facts=0 且预期有事实时，由调用方给出 coverage 说明原因。
    """
    levels = {
        "COMMAND_EXECUTED": bool(executed),
        "SNAPSHOT_SAVED": bool(snapshot),
        "CONTENT_CAPTURED": bool(content_captured),
        "PARSING_COMPLETED": bool(parsing),
        "FACTS_PERSISTED": int(facts) > 0,
        "CLAIMS_VERIFIED": int(claims) > 0 and int(verifications) > 0,
        "KNOWLEDGE_QUERYABLE": bool(queryable),
        "CARD_RENDERED": bool(card),
    }
    counts = {"facts": int(facts), "claims": int(claims),
              "verifications": int(verifications)}
    # ★ 最高已达档位
    reached = [k for k in STATUS_LEVELS if levels[k]]
    highest = reached[-1] if reached else "NONE"
    return {
        "levels": levels,
        "counts": counts,
        "highest_reached": highest,
        # ★ 只有到 KNOWLEDGE_QUERYABLE 才算"知识可用"
        "knowledge_available": levels["KNOWLEDGE_QUERYABLE"],
        # ★ COMMAND_EXECUTED 单独绝不足以宣称分析成功
        "command_ok_is_success": False,
        "coverage": coverage or {},
    }


def assert_expected_facts(contract, *, expected, actual, empty_reason=None):
    """预期有事实但实际为 0 → 必须失败（除非给出合法空原因）。

    ★ 不设"所有文件至少一条"规则；只对调用方明确预期的输入断言。
    """
    if expected and actual == 0:
        if empty_reason:
            return {"ok": True, "state": "LEGITIMATE_EMPTY",
                    "reason": empty_reason}
        return {"ok": False, "state": "SILENT_ZERO_FACTS",
                "reason": "预期存在可提取知识，实际 0 条事实且无覆盖说明"}
    return {"ok": True, "state": "AS_EXPECTED"}
