#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分发前检查。

★ **预览许可 ≠ 分发许可。**
   preview_allowed 表示"可以本地打开看"，
   distribution_allowed 表示"可以对外发布"——两者独立。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 当前冻结状态与三个未关闭门禁
FREEZE_STATE = "FROZEN_INTERNAL_RESTRICTED"
BLOCKERS = (
    ("B-1", "第三方声明措辞"),
    ("B-2", "UPSTREAM-06 法律审查（copy_permitted=false）"),
    ("B-3", "CC BY 4.0 署名"),
)

# 检查项代码
C_TEST_ONLY = "ARTIFACT_IS_TEST_ONLY"
C_SYNTHETIC = "SYNTHETIC_PROVENANCE"
C_EVIDENCE_CORRUPT = "EVIDENCE_CORRUPT"
C_MISSING_LIMITS = "UNDISPLAYED_LIMITATIONS"
C_GATE_OPEN = "DISTRIBUTION_GATE_OPEN"
C_EXTERNAL_RESOURCE = "UNTRUSTED_EXTERNAL_RESOURCE"
C_CLAIMS_CURRENT = "FALSE_CURRENT_CLAIM"
C_THIRD_PARTY = "THIRD_PARTY_EXPRESSION"


def pre_publish_check(rendered_artifact, source_view, restrictions) -> dict:
    """返回检查结论。**本轮所有对外分发都必须被拒绝。**

    rendered_artifact: {"html": str, "json": dict} 或其中任一
    source_view:        KnowledgeView dict
    restrictions:       分发限制 dict（distribution_restrictions）
    """
    html = ""
    doc = {}
    if isinstance(rendered_artifact, dict):
        html = rendered_artifact.get("html") or ""
        doc = rendered_artifact.get("json") or {}
    elif isinstance(rendered_artifact, str):
        html = rendered_artifact

    view = source_view or {}
    restr = restrictions or {}
    findings = []
    html_low = html.lower()

    # 1) TEST_ONLY
    is_test_only = bool(view.get("authorization_is_test_only")) or \
        (doc.get("authorization") or {}).get("test_only") is True
    if is_test_only:
        findings.append({"code": C_TEST_ONLY, "severity": "blocker",
                         "detail": "该产物由隔离测试授权产生，不得对外分发"})

    # 2) 合成来源
    prov = view.get("provenance_level") or \
        (doc.get("provenance") or {}).get("level")
    if prov == "SYNTHETIC_FIXTURE":
        findings.append({"code": C_SYNTHETIC, "severity": "blocker",
                         "detail": "来源为合成夹具，不代表真实仓库"})

    # 3) 证据损坏
    if view.get("no_usable_evidence") is False and \
            (view.get("conflict_indicators") or {}).get("evidence_conflict_detected"):
        findings.append({"code": C_EVIDENCE_CORRUPT, "severity": "blocker",
                         "detail": "证据存在冲突，结论不可直接外发"})

    # 4) 限制信息是否展示
    limits = list(view.get("limitations") or [])
    hidden = []
    for lim in limits:
        head = lim[:10]
        if head and head not in html:
            hidden.append(lim[:40])
    if hidden:
        findings.append({"code": C_MISSING_LIMITS, "severity": "blocker",
                         "detail": f"有 {len(hidden)} 条限制未在产物中展示"})

    # 5) 分发门禁
    if restr.get("freeze_state") == FREEZE_STATE:
        open_blockers = [b["id"] for b in (restr.get("blockers") or [])
                         if b.get("status") == "OPEN"]
        if not open_blockers:
            open_blockers = [b[0] for b in BLOCKERS]
        findings.append({"code": C_GATE_OPEN, "severity": "blocker",
                         "detail": f"分发门禁仍 OPEN：{open_blockers}"})
    if restr.get("distribution_allowed") is not True:
        if not any(f["code"] == C_GATE_OPEN for f in findings):
            findings.append({"code": C_GATE_OPEN, "severity": "blocker",
                             "detail": "distribution_allowed 不为 true"})

    # 6) 外部资源
    for bad in ("<script", "<iframe", "<object", "<embed", "src=\"http",
                "href=\"http://", "@import url(http", "<link rel=\"stylesheet"):
        if bad in html_low:
            findings.append({"code": C_EXTERNAL_RESOURCE, "severity": "blocker",
                             "detail": f"产物含可疑外部资源写法：{bad}"})
            break

    # 7) 错误宣称当前有效
    for phrase in ("当前最新", "当前有效", "已发布为正式知识", "当前 master 的权威"):
        if phrase in html or phrase in str(doc):
            findings.append({"code": C_CLAIMS_CURRENT, "severity": "blocker",
                             "detail": f"出现未经证明的时效宣称：{phrase}"})
            break

    # 8) 第三方受保护表达（UPSTREAM-06）
    for protected in ("Unsupported claims MUST NOT be presented as facts",):
        if protected in html:
            findings.append({"code": C_THIRD_PARTY, "severity": "blocker",
                             "detail": "产物复制了受保护的第三方表达"})

    blockers = [f for f in findings if f["severity"] == "blocker"]
    return {
        "preview_allowed": True,          # 本地内部预览允许
        "distribution_allowed": False,    # ★ 本轮恒为 False
        "publish_blocked": True,
        "findings": findings,
        "blocker_count": len(blockers),
        "statement": ("内部预览：允许本地打开。"
                      "对外分发：拒绝。预览许可不等于分发许可。"),
    }
