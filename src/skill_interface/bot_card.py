#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bot 内呈现：把源码知识渲染成 **Bot 消息流里的文本块**。

★ 设计约束（用户明确要求）：
  1. 不生成 HTML、不写文件、不要求用户开浏览器。
  2. 不复用 Bot 的 `card` 组件 —— 那是**工具授权卡**
     （allowed-once / allowed-always-* / rejected，生命周期 decided/answered/
     cancelled/expired），语义是权限确认，不是知识展示。挪用即改别人排版。
  3. 只用**点阵符号 + 表格**表达，天然适配 Tobs 的点阵视觉语言，
     且不改动 Tobs 任何既有排版。

点阵五档（与 botui-core 的「格子亮度」语义对齐）：
  ▣  满格实心 —— 已验证，命题成立
  ▤  半格       —— 已观察，尚未获得命题验证
  □  空心       —— 证据不足
  △  异形       —— 该语义形式尚不支持解析
  ·  空位       —— 尚未分析
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("content_persistence", "evidence_claims", "storage", "skill_interface"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

GLYPH = {
    "SUPPORTED_SOURCE_CLAIM": "▣",
    "OBSERVED_SOURCE_FACT": "▤",
    "INSUFFICIENT_EVIDENCE": "□",
    "UNSUPPORTED_SEMANTIC_FORM": "△",
    "NOT_ANALYZED": "·",
}

LABEL = {
    "SUPPORTED_SOURCE_CLAIM": "已验证·命题成立",
    "OBSERVED_SOURCE_FACT": "已观察·尚未验证",
    "INSUFFICIENT_EVIDENCE": "证据不足",
    "UNSUPPORTED_SEMANTIC_FORM": "该语义形式不支持",
    "NOT_ANALYZED": "尚未分析",
}

# 点阵图例固定行，放在块首，读者一眼能对照
LEGEND = "▣ 已验证   ▤ 已观察未验证   □ 证据不足   △ 语义不支持   · 尚未分析"


def _subject_name(v):
    s = v.get("subject") or {}
    return (s.get("qualified_name") or s.get("exported_name")
            or s.get("module_name") or "?")


def render_bot_block(*, query_result, repo_name=None):
    """把一个 source_query 结果渲染成 Bot 可直出的 Markdown 块。

    ★ 纯函数：不写盘、不联网、不读模型。
    """
    q = query_result or {}
    state = q.get("state")
    lines = []

    rid = q.get("repository_id") or "?"
    commit = (q.get("commit_sha") or "")[:12]
    fpath = q.get("file_path") or "-"
    head = f"{repo_name}（{rid}）" if repo_name else f"仓库 {rid}"
    lines.append(f"**源码知识** · {head}")
    lines.append(f"固定 Commit `{commit}` · 文件 `{fpath}`")
    lines.append("")

    if state != "FOUND":
        why = {
            "CONTENT_NOT_CAPTURED": "原始字节尚未采集，无法分析",
            "SOURCE_NOT_ANALYZED": "已采集但尚未做源码结构分析",
            "REPOSITORY_NOT_REGISTERED": "该仓库尚未建立知识库",
            "COMMIT_NOT_REGISTERED": "该 Commit 未登记",
        }.get(state, f"状态 {state}")
        lines.append(f"△ {why}")
        lines.append("")
        lines.append("· 未产出一事一议的结论 —— 知识库回答不了这个问题。")
        return "\n".join(lines)

    counts = q.get("counts") or {}
    lines.append(
        f"符号 {counts.get('symbols', 0)} · 导出 {counts.get('exports', 0)}"
        f" · 导入 {counts.get('imports', 0)} · 事实 {counts.get('facts', 0)}")
    lines.append("")
    lines.append(LEGEND)
    lines.append("")

    claims = q.get("claims") or []
    if not claims:
        lines.append("· 有事实但无命题裁决 —— 只能算观察，不算结论。")
        return "\n".join(lines)

    lines.append("|  | 对象 | 类型 | 行 | 裁决 | 证据 ID |")
    lines.append("|---|---|---|---|---|---|")
    for c in claims:
        lv = c.get("display_level") or "OBSERVED_SOURCE_FACT"
        g = GLYPH.get(lv, "·")
        kind = c.get("kind") or ""
        name = _subject_name(c)
        ln = c.get("line") or c.get("start_line") or ""
        lbl = LABEL.get(lv, lv)
        fid = (c.get("claim_id") or c.get("fact_id") or "")
        lines.append(
            f"| {g} | `{name}` | {kind} | {ln} | {lbl} | `{fid[-8:]}` |")

    lines.append("")
    n_sup = sum(1 for c in claims
                if c.get("display_level") == "SUPPORTED_SOURCE_CLAIM")
    n_obs = sum(1 for c in claims
                if c.get("display_level") == "OBSERVED_SOURCE_FACT")
    if n_sup:
        lines.append(f"▣ {n_sup} 项已获命题验证，可当结论引用。")
    if n_obs:
        lines.append(f"▤ {n_obs} 项只是观察到的结构，**不代表已验证**。")

    lim = q.get("limitations") or []
    if lim:
        lines.append("")
        lines.append("限制：")
        for x in lim[:3]:
            lines.append(f"- {x}")
    return "\n".join(lines)


def lookup_repo_name(store, repository_id):
    """从 subject_record 读仓库显示名；读不到返回 None（**不猜**）。"""
    try:
        rows = store.conn.execute(
            "SELECT asset_id FROM index_rows WHERE asset_type='subject_record' "
            "AND repository_id=? LIMIT 20", (str(repository_id),)).fetchall()
        for r in rows:
            got = store.get_asset(r["asset_id"], verify=True)
            if not got.get("ok"):
                continue
            pl = ((got.get("asset") or {}).get("payload") or {})
            if pl.get("record_kind") != "repository_display_name":
                continue
            nm = pl.get("resolved_repository")
            if nm:
                return nm
    except Exception:
        return None
    return None
