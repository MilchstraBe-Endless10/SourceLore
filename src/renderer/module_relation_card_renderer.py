#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态模块关系卡片 HTML。★ 复用 safe_html（CSP + 转义）。"""

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


def render_relation_card_html(card):
    if card.get("card_type") == "SOURCE_MODULE_RELATION_ERROR":
        return _render_error(card)

    parts = ['<h2>一 · Import 来源</h2>']
    imp = card.get("import") or {}
    parts.append(_kv([
        ("仓库", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("源文件", SH.esc_path(imp.get("file_path"))),
        ("Import 说明符", SH.esc(imp.get("module_specifier"))),
        ("Import 类型", SH.esc(imp.get("import_kind"))),
        ("仅类型导入", SH.esc(imp.get("is_type_only"))),
        ("Import Fact", _mono(imp.get("import_fact_id"), 60)),
    ]))

    parts.append('<h2>二 · 解析配置</h2>')
    cfg = card.get("config") or {}
    parts.append(_kv([
        ("配置文件", SH.esc_path(cfg.get("config_path"))),
        ("匹配字段", SH.esc(cfg.get("matched_field"))),
        ("映射规则", SH.esc(cfg.get("matched_rule"))),
        ("解析策略", SH.esc(cfg.get("resolution_policy"))),
        ("配置观察", _mono("；".join(
            str(x) for x in (cfg.get("observation_ids") or [])), 80)),
        ("配置 Blob", _mono("；".join(
            str(x) for x in (cfg.get("blob_oids") or [])), 80)),
    ]))

    parts.append('<h2>三 · 目标</h2>')
    tgt = card.get("target") or {}
    parts.append(_kv([
        ("目标路径", SH.esc_path(tgt.get("resolved_target_path"))),
        ("候选数量", SH.esc(len(tgt.get("candidate_paths") or []))),
        ("唯一", SH.esc(tgt.get("unique"))),
        ("静态解析状态", SH.esc(tgt.get("resolution_state"))),
    ]))
    cands = tgt.get("candidate_paths") or []
    if cands:
        parts.append("<p>候选顺序：</p><ol>")
        for c in cands:
            parts.append(f'<li>{SH.esc_path(c)}</li>')
        parts.append("</ol>")

    cond = card.get("condition_candidates") or []
    if cond:
        parts.append('<h2>四 · 条件候选</h2>')
        rows = ["<table><tr><th>条件</th><th>目标</th></tr>"]
        for c in cond:
            rows.append(f'<tr><td>{SH.esc(c.get("condition"))}</td>'
                        f'<td>{SH.esc(c.get("target"))}</td></tr>')
        rows.append("</table>")
        parts.append("".join(rows))

    parts.append('<h2>五 · 证据</h2>')
    evs = card.get("evidence_refs") or []
    if evs:
        parts.append("<ul>" + "".join(
            f"<li>{_mono(e, 100)}</li>" for e in evs) + "</ul>")
    else:
        parts.append("<p>无证据引用。</p>")

    parts.append('<h2>六 · 限制</h2>')
    parts.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    dr = card.get("distribution_restrictions") or {}
    parts.append(_kv([
        ("distribution_allowed", SH.esc(dr.get("distribution_allowed"))),
        ("copy_permitted", SH.esc(dr.get("copy_permitted"))),
        ("网络请求数", SH.esc(card.get("network_requests"))),
    ]))

    return SH.document(
        title=f"静态模块关系 · {card.get('import', {}).get('module_specifier') or ''}",
        body_html="".join(parts))


def _render_error(card):
    body = ['<div class="blocked">']
    body.append("<h2>静态模块关系 — 诊断卡片</h2>")
    body.append(f'<p>原因：{SH.esc(card.get("reason"))}</p>')
    body.append(f'<p>说明：{SH.esc(card.get("detail"))}</p>')
    body.append(_kv([
        ("仓库", SH.esc(card.get("repository_id"))),
        ("Commit", _mono(card.get("commit_sha"))),
        ("源文件", SH.esc_path(card.get("importing_file_path"))),
        ("说明符", SH.esc(card.get("module_specifier"))),
        ("解析状态", SH.esc(card.get("resolution_state"))),
    ]))
    body.append("<ul>" + "".join(
        f"<li>{SH.esc(x)}</li>" for x in (card.get("limitations") or [])) + "</ul>")
    body.append("</div>")
    return SH.document(title="静态模块关系诊断卡片", body_body="") if False else \
        SH.document(title="静态模块关系诊断卡片", body_html="".join(body))
