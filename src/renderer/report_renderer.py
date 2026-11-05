#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多版本报告渲染：A/B 历史对照。

★ 铁律：两个结论针对**不同 Commit**，并列展示，不合并、不推断祖先关系。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import card_models as CM
from safe_html import esc, esc_sha, document


def render_report_html(cards: list, *, title: str = "多版本知识对照报告",
                       assembled_at: str = "") -> str:
    """把多张卡片渲染成一份内部对照报告。

    ★ 卡片顺序按 commit_sha 排序（确定性），不用传入顺序。
    """
    if not cards:
        raise ValueError("报告至少需要一张卡片")

    ordered = sorted(cards, key=lambda c: (str(c.get("commit_sha") or ""),
                                           str(c.get("card_id") or "")))

    parts = [f"<h1>{esc(title)}</h1>"]
    parts.append(
        '<div class="panel">'
        '<p>本报告并列展示<strong>不同 Commit</strong> 上的独立结论。'
        '它们各自成立于自己的版本，<strong>不构成同一事实的矛盾</strong>。</p>'
        '<p>报告不推断这些 Commit 之间的祖先/先后关系——'
        '除非有真实 Git 图证据，本报告不做任何版本先后假设。</p>'
        '</div>')

    # ── 总览表 ───────────────────────────────────────
    parts.append("<h2>版本总览</h2>")
    parts.append("<table><thead><tr>"
                 "<th>#</th><th>Commit</th><th>命题</th>"
                 "<th>证据裁决</th><th>新鲜度</th><th>人工审核</th>"
                 "<th>来源</th><th>授权</th>"
                 "</tr></thead><tbody>")
    for i, c in enumerate(ordered, 1):
        v, f, r, p, a = (c["verification"], c["freshness"],
                         c["review"], c["provenance"], c["authorization"])
        parts.append(
            f"<tr><td>{i}</td>"
            f'<td><span class="sha">{esc_sha(c["commit_sha"])}</span></td>'
            f"<td>{esc(c['title'])}</td>"
            f"<td>{esc(v['status'])}<br><span class=\"meta\">"
            f"{esc(v['label'])}</span></td>"
            f"<td>{esc(f['label'])}</td>"
            f"<td>{esc(r['label'])}</td>"
            f"<td>{esc(p['label'])}</td>"
            f"<td>{esc(a['label'])}</td></tr>")
    parts.append("</tbody></table>")

    # ── 分版本详情 ──────────────────────────────────
    for i, c in enumerate(ordered, 1):
        v, f, r, p, a = (c["verification"], c["freshness"],
                         c["review"], c["provenance"], c["authorization"])
        parts.append(f"<h2>版本 {i}：<span class=\"sha\">"
                     f"{esc_sha(c['commit_sha'])}</span></h2>")
        parts.append("<dl>")
        parts.append(f"<dt>命题</dt><dd>{esc(c['title'])}</dd>")
        parts.append(f"<dt>Claim</dt><dd><span class=\"sha\">"
                     f"{esc(c['claim_id'])}</span></dd>")
        parts.append(f"<dt>Verification</dt><dd><span class=\"sha\">"
                     f"{esc(v['verification_id'])}</span></dd>")
        parts.append(f"<dt>裁决</dt><dd><span class=\"badge "
                     f"{_cls(v['status'])}\">{esc(v['status'])}</span> "
                     f"{esc(v['meaning'])}</dd>")
        parts.append(f"<dt>新鲜度</dt><dd>{esc(f['meaning'])}</dd>")
        parts.append(f"<dt>审核</dt><dd>{esc(r['label'])}</dd>")
        parts.append(f"<dt>来源</dt><dd>{esc(p['label'])}</dd>")
        parts.append(f"<dt>执行来源</dt><dd>"
                     f"<code>{esc(p.get('execution_source_level') or '未知')}"
                     "</code></dd>")
        parts.append(f"<dt>授权</dt><dd>{esc(a['label'])}</dd>")
        h = c.get("history") or {}
        if (h.get("refs") or {}).get("relation"):
            parts.append(f"<dt>历史关系</dt><dd><code>"
                         f"{esc(h['refs']['relation'])}</code> ・ 原 Claim "
                         f"<span class=\"sha\">"
                         f"{esc(h['refs'].get('source_claim_id'))}</span></dd>")
        parts.append("</dl>")
        if c["limitations"]:
            parts.append('<p class="meta">限制：</p><ul>')
            for lim in c["limitations"]:
                parts.append(f"<li>{esc(lim)}</li>")
            parts.append("</ul>")

    # ── 分发门禁 ────────────────────────────────────
    d = ordered[0]["distribution"]
    parts.append("<h2>分发门禁</h2>")
    parts.append("<dl>")
    parts.append(f"<dt>允许分发</dt><dd>"
                 f"{'是' if d.get('distribution_allowed') else '否'}</dd>")
    parts.append(f"<dt>冻结状态</dt><dd><code>"
                 f"{esc(d.get('freeze_state'))}</code></dd>")
    parts.append("</dl>")
    parts.append(
        '<div class="panel"><p>本报告是<strong>本地内部预览</strong>，'
        '不是对外发布的正式知识产品。</p></div>')

    parts.append('<div class="foot">')
    parts.append("<p>卡片身份：")
    for c in ordered:
        parts.append(f'<span class="sha">{esc(c["card_id"])}</span><br>')
    parts.append("</p>")
    parts.append(f"<p>渲染器版本 <code>{esc(ordered[0]['renderer_version'])}"
                 "</code></p>")
    parts.append("<p>本文件为本地内部预览产物，不是对外发布的正式知识。</p>")
    if assembled_at:
        parts.append(f"<p>渲染时刻（诊断用，不参与确定性身份）："
                     f"{esc(assembled_at)}</p>")
    parts.append("</div>")

    return document(title=title, body_html="\n".join(parts))


def _cls(status) -> str:
    return {"supported": "ok", "refuted": "bad"}.get(status, "unk")
