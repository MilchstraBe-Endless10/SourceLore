#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识卡片渲染：JSON 与 HTML。

★ 结构由**可信模板**生成；来自视图的一切文字只能经 safe_html.esc 进入。
"""

import sys, json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import card_models as CM
from safe_html import esc, esc_sha, esc_path, document, link_or_text

# 诊断阻塞：这些情况下不得生成"看似正常"的卡片
BLOCKING_DIAGNOSTICS = frozenset({
    "VIEW_INTEGRITY_FAILED", "DANGLING_REFERENCE", "SOURCE_MISSING",
    "VERSION_MISMATCH", "CLAIM_NOT_FOUND", "VERIFICATION_NOT_FOUND",
    "CLAIM_VERIFICATION_MISMATCH", "REPOSITORY_MISMATCH", "COMMIT_MISMATCH",
    "EVIDENCE_CORRUPT",
})


def render_json(card: dict) -> str:
    """确定性 JSON：键排序、无时间戳、缩进固定。"""
    return json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_card_html(card: dict, *, assembled_at: str = "") -> str:
    """渲染单张知识卡片。

    ★ assembled_at 只进诊断页脚，**不参与**任何确定性身份。
    """
    if card.get("blocked"):
        return _render_blocked(card, assembled_at=assembled_at)

    violations = CM.check_wording(card)
    if violations:
        raise ValueError(f"措辞放大裁决：{violations}")

    v = card["verification"]
    f = card["freshness"]
    r = card["review"]
    p = card["provenance"]
    a = card["authorization"]
    e = card["evidence"]
    h = card["history"]
    d = card["distribution"]

    parts = []
    parts.append(f"<h1>{esc(card['title'])}</h1>")
    parts.append(
        f'<p class="meta">仓库 <span class="sha">{esc(card["repository_id"])}</span>'
        f' ・ 固定 Commit <span class="sha">{esc_sha(card["commit_sha"])}</span>'
        f' ・ 命题类型 <code>{esc(card["claim_type"])}</code></p>')

    # ── 范围声明：固定 Commit 不等于当前最新 ─────────────
    parts.append(
        '<div class="panel">'
        f'<p><strong>范围</strong>：本卡片只描述 <span class="sha">'
        f'{esc_sha(card["commit_sha"])}</span> 这一个固定 Commit 上的命题，'
        '不代表该仓库的当前最新状态。</p>'
        f'</div>')

    # ── B. 证据裁决 ─────────────────────────────────
    parts.append("<h2>证据裁决</h2>")
    parts.append(
        '<div class="panel">'
        f'<p>{_verdict_badge(v["status"])} '
        f'<strong>{esc(v["label"])}</strong></p>'
        f'<p>{esc(v["meaning"])}</p>'
        '</div>')
    parts.append("<dl>")
    parts.append(f"<dt>裁决规则版本</dt><dd><code>{esc(v['rule_version'])}"
                 "</code></dd>")
    parts.append(f"<dt>Verification</dt><dd><span class=\"sha\">"
                 f"{esc(v['verification_id'])}</span></dd>")
    parts.append("</dl>")

    # ── C. 新鲜度 ───────────────────────────────────
    parts.append("<h2>新鲜度与适用性</h2>")
    parts.append("<dl>")
    parts.append(f"<dt>新鲜度</dt><dd>{esc(f['label'])}</dd>")
    parts.append(f"<dt>含义</dt><dd>{esc(f['meaning'])}</dd>")
    parts.append(f"<dt>当前适用性</dt><dd>"
                 f"{esc(f['current_applicability_label'])}</dd>")
    if f.get("observed_commit_sha"):
        parts.append(f"<dt>观测到的 Commit</dt><dd><span class=\"sha\">"
                     f"{esc_sha(f['observed_commit_sha'])}</span></dd>")
    if f.get("last_observed_at"):
        parts.append(f"<dt>观测时间</dt><dd>{esc(f['last_observed_at'])}</dd>")
    parts.append("</dl>")

    # ── D. 人工审核 ─────────────────────────────────
    parts.append("<h2>人工审核</h2>")
    parts.append("<dl>")
    parts.append(f"<dt>状态</dt><dd>{_review_badge(r['status'])} "
                 f"{esc(r['label'])}</dd>")
    parts.append(f"<dt>人工撰写</dt><dd>"
                 f"{'是' if r.get('human_authored') else '否'}</dd>")
    parts.append("</dl>")
    if r["status"] != "approved":
        parts.append('<p class="meta">该结论尚未经过人工批准；'
                     '证据裁决不替代人工审核。</p>')

    # ── E. 来源与授权 ────────────────────────────────
    parts.append("<h2>来源与授权</h2>")
    parts.append("<dl>")
    parts.append(f"<dt>来源等级</dt><dd>{esc(p['label'])} "
                 f"<code>{esc(p['level'] or '未知')}</code></dd>")
    if p.get("mixed_provenance"):
        parts.append("<dt>混合来源</dt><dd>是（各层不一致，按最弱者展示）</dd>")
    if p.get("basis"):
        parts.append(f"<dt>判定依据</dt><dd>"
                     f"{esc('、'.join(p['basis']))}</dd>")
    parts.append(f"<dt>授权类别</dt><dd>{esc(a['label'])}</dd>")
    parts.append("</dl>")
    if a["test_only"]:
        parts.append('<div class="panel"><p><strong>隔离测试结果</strong>：'
                     '本卡片由隔离测试授权（TEST_ONLY）产生，'
                     '<strong>未通过真实平台授权验收</strong>，'
                     '不代表生产环境结论。</p></div>')

    # ── F. 证据与历史 ────────────────────────────────
    parts.append("<h2>证据与历史</h2>")
    parts.append("<dl>")
    parts.append(f"<dt>Fact 引用</dt><dd>{_ref_list(e['fact_refs'])}</dd>")
    parts.append(f"<dt>Snapshot 引用</dt><dd>"
                 f"{_ref_list(e['snapshot_refs'])}</dd>")
    if e.get("local_coverage_only"):
        parts.append("<dt>覆盖范围</dt><dd>仅局部覆盖"
                     f"（<code>{esc(e.get('coverage_scope') or 'PARTIAL')}"
                     "</code>）</dd>")
    parts.append("</dl>")
    if e["refs"]:
        parts.append("<h3>证据引用明细</h3><ul>")
        for ref in e["refs"]:
            parts.append(f"<li><code>{esc(ref)}</code></li>")
        parts.append("</ul>")
    if h["refs"]:
        parts.append("<h3>历史版本关联</h3><dl>")
        for k, label in (("source_claim_id", "原 Claim"),
                         ("source_verification_id", "原 Verification"),
                         ("candidate_id", "重新验证候选"),
                         ("relation", "关系")):
            if h["refs"].get(k):
                parts.append(f"<dt>{esc(label)}</dt>"
                             f"<dd><span class=\"sha\">"
                             f"{esc(h['refs'][k])}</span></dd>")
        parts.append("</dl>")

    # ── G. 限制 ─────────────────────────────────────
    parts.append("<h2>限制与使用边界</h2>")
    if card["limitations"]:
        parts.append("<ul>")
        for lim in card["limitations"]:
            parts.append(f"<li>{esc(lim)}</li>")
        parts.append("</ul>")
    else:
        parts.append('<p class="meta">（无额外限制记录）</p>')

    # ── 分发门禁 ────────────────────────────────────
    parts.append("<h2>分发门禁</h2>")
    parts.append("<dl>")
    parts.append(f"<dt>允许分发</dt><dd>"
                 f"{'是' if d.get('distribution_allowed') else '否'}</dd>")
    parts.append(f"<dt>冻结状态</dt><dd><code>"
                 f"{esc(d.get('freeze_state'))}</code></dd>")
    parts.append(f"<dt>适用范围</dt><dd><code>"
                 f"{esc(d.get('scope'))}</code></dd>")
    parts.append("</dl>")
    blockers = d.get("blockers") or []
    if blockers:
        parts.append("<table><thead><tr><th>门禁</th><th>状态</th>"
                     "<th>说明</th></tr></thead><tbody>")
        for b in blockers:
            parts.append(f"<tr><td><code>{esc(b.get('id'))}</code></td>"
                         f"<td>{esc(b.get('status'))}</td>"
                         f"<td>{esc(b.get('title'))}</td></tr>")
        parts.append("</tbody></table>")

    parts.append(_footer(card, assembled_at))
    return document(title=card["title"], body_html="\n".join(parts))


def render_blocked_html(diagnostic: dict, *, assembled_at: str = "") -> str:
    """★ 损坏/缺失来源：明确输出"无法生成可信知识卡片"。"""
    return _render_blocked({"blocked": True, "diagnostic": diagnostic,
                            "card_id": ""}, assembled_at=assembled_at)


# ── 内部渲染片段 ─────────────────────────────────────────
def _verdict_badge(status) -> str:
    cls = {"supported": "ok", "refuted": "bad"}.get(status, "unk")
    label = CM.VERDICT_LABEL.get(status, "未知裁决")
    return f'<span class="badge {cls}">{esc(status)}</span>'


def _review_badge(status) -> str:
    cls = "ok" if status == "approved" else "unk"
    return f'<span class="badge {cls}">{esc(status)}</span>'


def _ref_list(items) -> str:
    if not items:
        return '<span class="meta">（无）</span>'
    return "".join(f'<span class="sha">{esc(x)}</span><br>' for x in items)


def _footer(card, assembled_at) -> str:
    return ('<div class="foot">'
            f'<p>卡片身份 <span class="sha">{esc(card["card_id"])}</span></p>'
            f'<p>视图身份 <span class="sha">{esc(card["view_id"])}</span></p>'
            f'<p>渲染器版本 <code>{esc(card["renderer_version"])}</code> ・ '
            f'卡片 Schema <code>{esc(card["card_schema_version"])}</code></p>'
            f'<p>本文件为本地内部预览产物，不是对外发布的正式知识。</p>'
            + (f'<p>渲染时刻（诊断用，不参与确定性身份）：'
               f'{esc(assembled_at)}</p>' if assembled_at else '')
            + '</div>')


def _render_blocked(card, assembled_at) -> str:
    diag = card.get("diagnostic") or {}
    code = diag.get("error_code") or "VIEW_INTEGRITY_FAILED"
    detail = diag.get("detail") or "来源或证据链存在问题，无法安全地展示裁决结论。"
    body = [
        "<h1>无法生成可信知识卡片</h1>",
        '<div class="panel">',
        f'<p><span class="badge bad">阻断</span> '
        f'<strong>{esc(code)}</strong></p>',
        f'<p>{esc(detail)}</p>',
        "</div>",
        "<h2>为什么不显示结论</h2>",
        "<ul>",
        "<li>证据链损坏或悬空引用时，任何 supported/refuted 展示都不可信。</li>",
        "<li>缺少 Snapshot 或内容摘要不一致时，无法证明结论针对该 Commit。</li>",
        "<li>此时宁可不显示，也不生成看似完整、实际缺失证据的卡片。</li>",
        "</ul>",
    ]
    if assembled_at:
        body.append(f'<div class="foot"><p>渲染时刻：{esc(assembled_at)}</p>'
                    '</div>')
    return document(title="无法生成可信知识卡片",
                    body_html="\n".join(body))
