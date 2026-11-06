#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TS 项目卡片渲染。"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
for _p in ("renderer",):
    _sp = str(_root / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import safe_html as SH


def _mono(v, limit=80):
    return f'<span class="mono">{SH.esc(v)}</span>'


def _kv(rows):
    out = ['<table class="kv">']
    for k, v in rows:
        out.append(f'<tr><th>{SH.esc(k)}</th><td>{v}</td></tr>')
    out.append('</table>')
    return "".join(out)


def render_ts_card_html(card):
    ct = card.get("card_type")
    if ct == "TYPESCRIPT_PROJECT_ERROR":
        return _render_error(card)
    if ct == "PROJECT_REFERENCE_CARD":
        return _render_reference(card)
    if ct == "PROJECT_FILE_MEMBERSHIP_CARD":
        return _render_membership(card)
    return _render_project(card)


def _render_project(card):
    parts = ['<h2>一 · 项目身份</h2>']
    parts.append(_kv([
        ("仓库", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("配置", SH.esc_path(card.get("config_path"))),
        ("配置 Blob", _mono(card.get("config_blob_oid"))),
        ("Project ID", _mono(card.get("project_id"), 60)),
        ("发现状态", SH.esc(card.get("discovery_status"))),
        ("配置完整性", SH.esc(card.get("config_completeness"))),
        ("solution-style", SH.esc(card.get("is_solution_style"))),
    ]))

    parts.append('<h2>二 · 输入选择</h2>')
    for label, key in (("files", "declared_files"),
                       ("include", "declared_include"),
                       ("exclude", "declared_exclude")):
        vals = card.get(key) or []
        parts.append(f"<h3>{SH.esc(label)}</h3>")
        if vals:
            parts.append("<ul>" + "".join(
                f"<li>{_mono(v)}</li>" for v in vals) + "</ul>")
        else:
            parts.append("<p>未声明</p>")

    parts.append('<h2>三 · 编译相关标记（仅记录，不代表已构建）</h2>')
    parts.append(_kv([
        ("composite", SH.esc(card.get("declared_composite"))),
        ("rootDir", SH.esc(card.get("declared_root_dir"))),
        ("outDir", SH.esc(card.get("declared_out_dir"))),
    ]))

    parts.append('<h2>四 · 证据</h2>')
    evs = card.get("evidence_refs") or []
    parts.append("<ul>" + "".join(
        f"<li>{_mono(e, 100)}</li>" for e in evs) + "</ul>" if evs
        else "<p>无证据引用。</p>")

    parts.append('<h2>五 · 限制</h2>')
    parts.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    dr = card.get("distribution_restrictions") or {}
    parts.append(_kv([
        ("distribution_allowed", SH.esc(dr.get("distribution_allowed"))),
        ("copy_permitted", SH.esc(dr.get("copy_permitted"))),
        ("网络请求数", SH.esc(card.get("network_requests"))),
    ]))
    return SH.document(
        title=f"TypeScript 项目 · {card.get('config_path') or ''}",
        body_html="".join(parts))


def _render_reference(card):
    parts = ['<h2>一 · 引用关系</h2>']
    parts.append(_kv([
        ("仓库", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("源配置", SH.esc_path(card.get("from_config_path"))),
        ("声明路径", SH.esc(card.get("declared_path"))),
        ("目标配置", SH.esc_path(card.get("to_config_path"))),
        ("目标 Project", _mono(card.get("to_project_id"), 60)),
        ("状态", SH.esc(card.get("status"))),
    ]))
    parts.append('<h2>二 · 证据</h2>')
    evs = card.get("evidence_refs") or []
    parts.append("<ul>" + "".join(
        f"<li>{_mono(e, 100)}</li>" for e in evs) + "</ul>")
    parts.append('<h2>三 · 限制</h2>')
    parts.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    return SH.document(title="Project Reference", body_html="".join(parts))


def _render_membership(card):
    parts = ['<h2>一 · 文件归属</h2>']
    parts.append(_kv([
        ("仓库", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("文件", SH.esc_path(card.get("file_path"))),
        ("多候选歧义", SH.esc(card.get("ambiguous"))),
    ]))
    parts.append('<h2>二 · 候选项目</h2>')
    cands = card.get("candidates") or []
    rows = ["<table><tr><th>配置</th><th>状态</th><th>规则</th>"
            "<th>被 exclude</th></tr>"]
    for c in cands:
        rows.append(
            f'<tr><td>{SH.esc_path(c.get("config_path"))}</td>'
            f'<td>{SH.esc(c.get("state"))}</td>'
            f'<td>{SH.esc(c.get("matched_rule"))}</td>'
            f'<td>{SH.esc(c.get("excluded_by"))}</td></tr>')
    rows.append("</table>")
    parts.append("".join(rows))

    parts.append('<h2>三 · 限制</h2>')
    parts.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    return SH.document(title="Project File Membership",
                       body_html="".join(parts))


def _render_error(card):
    body = ['<div class="blocked">']
    body.append("<h2>TypeScript 项目 — 诊断卡片</h2>")
    body.append(f'<p>原因：{SH.esc(card.get("reason"))}</p>')
    body.append(f'<p>说明：{SH.esc(card.get("detail"))}</p>')
    body.append(_kv([
        ("仓库", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("配置", SH.esc_path(card.get("config_path"))),
    ]))
    body.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    body.append("</div>")
    return SH.document(title="TypeScript 项目诊断卡片", body_html="".join(body))
