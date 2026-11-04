#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SL-CAP-0075 离线评测：Gold 集 + 混淆矩阵 + 高风险错误门禁。

**Gold 是手工构造的，不由裁决器生成。** 每条 gold 都写明预期与构造依据。

高风险门禁（题面第 10 节）：
  - 把缺失证据判成 refuted → **阻断级**
  - 把不充分证据判成 supported → **阻断级**
"""

import json, sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# 本模块只需要 EC 自己的 models —— 不引入 facts 路径，
# 否则 `import models` 会命中 src/facts/models.py（同名模块冲突，实测踩过）。
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import ec_models as M

STATUSES = (M.SUPPORTED, M.REFUTED, M.INSUFFICIENT)


def confusion_matrix(results: list) -> dict:
    """results: [{expected, actual, case_id}]"""
    used = sorted({r["actual"] for r in results} | {r["expected"] for r in results})
    m = {e: {a: 0 for a in used} for e in used}
    for r in results:
        m[r["expected"]][r["actual"]] += 1
    return m


def score(results: list) -> dict:
    """计算题面要求的各项指标 + 高风险门禁。"""
    n = len(results)
    if n == 0:
        return {"error": "EMPTY_GOLD_SET", "total": 0}

    per_status = Counter(r["expected"] for r in results)
    correct = sum(1 for r in results if r["expected"] == r["actual"])
    matrix = confusion_matrix(results)

    # 错误 supported：预期不是 supported 却判 supported
    false_supported = [r for r in results
                       if r["expected"] != M.SUPPORTED and r["actual"] == M.SUPPORTED]
    # 错误 refuted：预期不是 refuted 却判 refuted
    false_refuted = [r for r in results
                     if r["expected"] != M.REFUTED and r["actual"] == M.REFUTED]

    # 正确 abstention：预期 insufficient 且实际 insufficient
    correct_abstention = sum(1 for r in results
                             if r["expected"] == M.INSUFFICIENT
                             and r["actual"] == M.INSUFFICIENT)
    wrong_abstention = [r for r in results
                        if r["expected"] in (M.SUPPORTED, M.REFUTED)
                        and r["actual"] == M.INSUFFICIENT]

    # 证据引用完整性
    ev_ok = sum(1 for r in results if r.get("evidence_refs_ok"))

    # ★ 阻断级判定
    blocking = []
    for r in false_supported:
        # 缺失证据被误判 supported / 不充分被误判 supported —— 两者都是阻断
        if r["expected"] == M.INSUFFICIENT:
            blocking.append({"case_id": r["case_id"],
                             "kind": "INSUFFICIENT_JUDGED_SUPPORTED",
                             "severity": "BLOCKER"})
    for r in false_refuted:
        # 缺失证据被误判 refuted
        if r["expected"] == M.INSUFFICIENT:
            blocking.append({"case_id": r["case_id"],
                             "kind": "MISSING_JUDGED_REFUTED",
                             "severity": "BLOCKER"})

    return {
        "total": n,
        "per_expected_status": dict(per_status),
        "correct": correct,
        "accuracy": round(correct / n, 4),
        "confusion_matrix": matrix,
        "false_supported": len(false_supported),
        "false_refuted": len(false_refuted),
        "correct_abstention": correct_abstention,
        "wrong_abstention": len(wrong_abstention),
        "evidence_refs_ok": ev_ok,
        "blocking_errors": blocking,
        "gate": "BLOCKED" if blocking else ("PASS" if correct == n else "IMPERFECT"),
        "note": ("不得仅凭 accuracy 宣布合格；必须看 false_supported/false_refuted 与阻断项"
                 "（SL-CAP-0075）"),
        "failures": [{"case_id": r["case_id"], "expected": r["expected"],
                      "actual": r["actual"], "detail": r.get("detail", "")}
                     for r in results if r["expected"] != r["actual"]],
    }


def assert_no_blocking(results: list):
    """高风险门禁：有任何阻断项就抛。"""
    s = score(results)
    if s["blocking_errors"]:
        raise AssertionError(f"阻断级错误: {s['blocking_errors']}")
    return s


def load_gold(path) -> list:
    return json.loads(Path(path).read_text(encoding="utf-8"))
