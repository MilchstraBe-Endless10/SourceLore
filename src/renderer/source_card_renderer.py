#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码结构卡片 HTML 渲染。★ 复用 safe_html（CSP + 转义）。"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
for _p in ("renderer",):
    _sp = str(_root / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import safe_html as SH


def _mono(v, limit=120):
    return f'<span class="mono">{SH.esc(v)}</span>'


def _kv(rows):
    out = ['<table class="kv">']
    for k, v in rows:
        out.append(f'<tr><th>{SH.esc(k)}</th><td>{v}</td></tr>')
    out.append('</table>')
    return "".join(out)


def _verdict_cell(row):
    """★ 任务书 §七：五档层级必须显式呈现，未验证的不得显示成 supported。"""
    lvl = row.get("display_level") or "OBSERVED_SOURCE_FACT"
    vd = row.get("verdict")
    cid = row.get("claim_id")
    vid = row.get("verification_id")
    label = {
        "SUPPORTED_SOURCE_CLAIM": "已验证 · 命题成立",
        "OBSERVED_SOURCE_FACT": "已观察，尚未获得命题验证",
        "INSUFFICIENT_EVIDENCE": "证据不足",
        "UNSUPPORTED_SEMANTIC_FORM": "该语义形式尚不支持解析",
        "NOT_ANALYZED": "尚未分析",
    }.get(lvl, lvl)
    ids = ""
    if cid or vid:
        ids = (f'<div class="mono">claim={SH.esc(cid) or "—"}<br>'
               f'verif={SH.esc(vid) or "—"}</div>')
    if vd:
        ids += f'<div>verdict={SH.esc(vd)}</div>'
    return (f'<strong>{SH.esc(label)}</strong>{ids}')


def render_source_card_html(card):
    if card.get("card_type") == "SOURCE_EVIDENCE_ERROR":
        return _render_error(card)

    parts = ['<h2>一 · 仓库与文件身份</h2>']
    parts.append(_kv([
        ("repository_id", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("文件路径", SH.esc_path(card.get("file_path"))),
        ("语言", SH.esc(card.get("language"))),
        ("内容可用性", SH.esc(card.get("content_availability"))),
        ("来源级别", SH.esc(card.get("provenance_level"))),
    ]))

    caps = card.get("captured") or []
    if caps:
        parts.append("<h3>内容字节</h3>")
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

    cnt = card.get("counts") or {}
    parts.append('<h2>二 · 结构概览</h2>')
    parts.append(_kv([
        ("已登记符号", SH.esc(cnt.get("symbols"))),
        ("已登记导入", SH.esc(cnt.get("imports"))),
        ("已登记导出", SH.esc(cnt.get("exports"))),
        ("事实总数", SH.esc(cnt.get("facts"))),
    ]))

    parts.append('<h2>三 · 符号声明</h2>')
    syms = card.get("symbols") or []
    if syms:
        rows = ["<table><tr><th>Fact ID</th><th>类型</th>"
                "<th>qualified_name</th><th>行号</th><th>证据</th>"
                "<th>裁决层级</th><th>Claim / Verification</th></tr>"]
        for s in syms:
            subj = s.get("subject") or {}
            rows.append(
                f'<tr><td>{_mono(s.get("fact_id"), 60)}</td>'
                f'<td>{SH.esc(subj.get("symbol_kind"))}</td>'
                f'<td>{SH.esc(subj.get("qualified_name"))}</td>'
                f'<td>L{SH.esc(s.get("start_line"))}–{SH.esc(s.get("end_line"))}</td>'
                f'<td>{SH.esc(s.get("evidence_label"))}</td>'
                f'<td>{_verdict_cell(s)}</td></tr>')
        rows.append("</table>")
        parts.append("".join(rows))
    else:
        parts.append("<p>无已登记符号。</p>")

    parts.append('<h2>四 · 静态导入声明</h2>')
    imps = card.get("imports") or []
    if imps:
        rows = ["<table><tr><th>Fact ID</th><th>语法</th><th>模块</th>"
                "<th>名称</th><th>层级</th><th>证据</th></tr>"]
        for i in imps:
            subj = i.get("subject") or {}
            rows.append(
                f'<tr><td>{_mono(i.get("fact_id"), 60)}</td>'
                f'<td>{SH.esc(subj.get("import_syntax"))}</td>'
                f'<td>{SH.esc(subj.get("module_name"))}</td>'
                f'<td>{SH.esc(subj.get("imported_name"))}</td>'
                f'<td>{SH.esc(subj.get("relative_level"))}</td>'
                f'<td>{SH.esc(i.get("evidence_label"))}</td></tr>')
        rows.append("</table>")
        parts.append("".join(rows))
    else:
        parts.append("<p>无已登记导入声明。</p>")

    parts.append('<h2>五 · 静态导出声明</h2>')
    exps = card.get("exports") or []
    if exps:
        rows = ["<table><tr><th>Fact ID</th><th>导出类型</th><th>名称</th>"
                "<th>来源</th><th>证据</th>"
                "<th>裁决层级</th><th>Claim / Verification</th></tr>"]
        for e in exps:
            subj = e.get("subject") or {}
            nm = subj.get("exported_name")
            rows.append(
                f'<tr><td>{_mono(e.get("fact_id"), 60)}</td>'
                f'<td>{SH.esc(subj.get("export_kind"))}</td>'
                f'<td>{SH.esc(nm if nm is not None else "（匿名）")}</td>'
                f'<td>{SH.esc(subj.get("source_reference"))}</td>'
                f'<td>{SH.esc(e.get("evidence_label"))}</td>'
                f'<td>{_verdict_cell(e)}</td></tr>')
        rows.append("</table>")
        parts.append("".join(rows))
    else:
        parts.append("<p>无已登记导出声明。</p>")

    parts.append('<h2>六 · 限制与免责</h2>')
    parts.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    dr = card.get("distribution_restrictions") or {}
    parts.append(_kv([
        ("distribution_allowed", SH.esc(dr.get("distribution_allowed"))),
        ("copy_permitted", SH.esc(dr.get("copy_permitted"))),
        ("网络请求数", SH.esc(card.get("network_requests"))),
    ]))

    return SH.document(title=f"源码结构卡片 · {card.get('file_path') or ''}",
                       body_html="".join(parts))


def _render_error(card):
    body = ['<div class="blocked">']
    body.append("<h2>证据链不完整 — 诊断卡片</h2>")
    body.append(f'<p>原因：{SH.esc(card.get("reason"))}</p>')
    body.append(f'<p>说明：{SH.esc(card.get("detail"))}</p>')
    body.append(_kv([
        ("repository_id", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("文件路径", SH.esc_path(card.get("file_path"))),
        ("查询状态", SH.esc(card.get("state"))),
    ]))
    body.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    body.append("</div>")
    return SH.document(title="源码证据诊断卡片", body_html="".join(body))
