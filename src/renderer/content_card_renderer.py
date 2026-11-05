#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容知识卡片 HTML 渲染。★ 复用 safe_html（CSP + 转义），不自建渲染引擎。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("renderer",):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import safe_html as SH


def _mono(value, limit=120):
    """长 SHA / 路径：等宽 + 可换行，不破坏布局。"""
    return (f'<span class="mono">{SH.esc(value)}</span>')


def _section(title):
    return f'<h2>{SH.esc(title)}</h2>'


def _kv(rows):
    out = ['<table class="kv">']
    for k, v in rows:
        out.append(f'<tr><th>{SH.esc(k)}</th><td>{v}</td></tr>')
    out.append('</table>')
    return "".join(out)


def render_content_card_html(card, *, generated_at=""):
    """渲染内容卡片。★ 只读投影，不修改任何权威数据。"""
    ct = card.get("card_type")

    if ct == "CONTENT_EVIDENCE_ERROR":
        return _render_error(card, generated_at)

    parts = []

    # 一、仓库与文件身份
    parts.append(_section("一 · 仓库与文件身份"))
    parts.append(_kv([
        ("repository_id", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("文件路径", SH.esc_path(card.get("file_path"))),
        ("来源快照", SH.esc(card.get("source_snapshot_id"))),
        ("来源级别", SH.esc(card.get("provenance_level"))),
        ("内容可用性", SH.esc(card.get("content_availability"))),
        ("审核状态", SH.esc(card.get("review_status"))),
        ("时效状态", SH.esc(card.get("freshness_state"))),
    ]))

    caps = card.get("captured") or []
    if caps:
        parts.append('<h3>内容字节</h3>')
        rows = ["<table><tr><th>路径</th><th>Git Blob OID</th>"
                "<th>字节</th><th>校验</th></tr>"]
        for c in caps:
            rows.append(
                f'<tr><td>{SH.esc_path(c.get("file_path"))}</td>'
                f'<td>{_mono(c.get("git_blob_oid"))}</td>'
                f'<td>{SH.esc(c.get("byte_length"))}</td>'
                f'<td>{SH.esc(c.get("verify_status"))}</td></tr>')
        rows.append("</table>")
        parts.append("".join(rows))

    # 二、内容知识概览
    parts.append(_section("二 · 内容知识概览"))
    cnt = card.get("counts") or {}
    parts.append(_kv([
        ("事实总数", SH.esc(cnt.get("facts_total"))),
        ("已登记标题", SH.esc(cnt.get("headings"))),
        ("已登记依赖", SH.esc(cnt.get("dependencies"))),
        ("已登记字段", SH.esc(cnt.get("fields"))),
    ]))

    # 三、结构化事实
    parts.append(_section("三 · 已登记的结构化事实"))
    facts = card.get("facts") or []
    if facts:
        rows = ["<table><tr><th>Fact ID</th><th>规则</th><th>主体</th>"
                "<th>位置</th><th>证据标签</th></tr>"]
        for f in facts:
            subj = f.get("subject") or {}
            subj_txt = " / ".join(f"{k}={v}" for k, v in sorted(subj.items())
                                  if k != "kind")
            rows.append(
                f'<tr><td>{_mono(f.get("fact_id"), 60)}</td>'
                f'<td>{SH.esc(f.get("rule_id"))}</td>'
                f'<td>{SH.esc(subj_txt)}</td>'
                f'<td>L{SH.esc(f.get("start_line"))}–{SH.esc(f.get("end_line"))}'
                f' / b{SH.esc(f.get("start_byte"))}–{SH.esc(f.get("end_byte"))}</td>'
                f'<td>{SH.esc(f.get("evidence_label"))}</td></tr>')
        rows.append("</table>")
        parts.append("".join(rows))
    else:
        parts.append("<p>无已登记事实。</p>")

    # 四、命题与裁决
    parts.append(_section("四 · 经过核验的命题"))
    verifs = card.get("verifications") or []
    if verifs:
        rows = ["<table><tr><th>Verification</th><th>裁决</th>"
                "<th>理由</th></tr>"]
        for v in verifs:
            st = v.get("status")
            cls = {"supported": "ok", "refuted": "bad"}.get(st, "warn")
            rows.append(
                f'<tr><td>{_mono(v.get("verification_id"), 60)}</td>'
                f'<td><span class="badge {cls}">{SH.esc(st)}</span></td>'
                f'<td>{SH.esc(v.get("status_reason"))}</td></tr>')
        rows.append("</table>")
        parts.append("".join(rows))
    else:
        parts.append("<p>尚无 Verification。事实已登记，但命题未被裁决。</p>")

    # 五、证据定位
    parts.append(_section("五 · 证据定位"))
    parts.append('<p>每条事实的字节与行号范围均指向固定 Commit 上的 Git Blob；'
                 '可用 Fact ID 在 Storage 中回查。</p>')

    # 六、限制
    parts.append(_section("六 · 限制与免责"))
    lims = card.get("limitations") or []
    parts.append("<ul>" + "".join(f"<li>{SH.esc(x)}</li>" for x in lims) + "</ul>")
    dr = card.get("distribution_restrictions") or {}
    parts.append(_kv([
        ("distribution_allowed", SH.esc(dr.get("distribution_allowed"))),
        ("copy_permitted", SH.esc(dr.get("copy_permitted"))),
        ("网络请求数", SH.esc(card.get("network_requests"))),
    ]))

    title = f"内容知识卡片 · {card.get('file_path') or ''}"
    return SH.document(title=title, body_html="".join(parts))


def _render_error(card, generated_at):
    body = []
    body.append('<div class="blocked">')
    body.append("<h2>证据链不完整 — 诊断卡片</h2>")
    body.append(f'<p>原因：{SH.esc(card.get("reason"))}</p>')
    body.append(f'<p>说明：{SH.esc(card.get("detail"))}</p>')
    body.append(_kv([
        ("repository_id", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("文件路径", SH.esc_path(card.get("file_path"))),
        ("查询状态", SH.esc(card.get("state"))),
        ("内容可用性", SH.esc(card.get("content_availability"))),
    ]))
    body.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    body.append("</div>")
    return SH.document(title="内容证据诊断卡片", body_html="".join(body))
