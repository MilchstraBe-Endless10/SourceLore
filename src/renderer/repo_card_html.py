"""仓库知识卡片渲染：把 card-data.json + code-graph.json 渲染成可交互 HTML。

★ 安全约束（对齐 F2-P4A 契约）：
  - 所有不可信文本走 `esc()`，不拼原始 HTML。
  - 无外部资源、无 CDN、无 `<img>` 外链；图形用内联 SVG 绘制。
  - CSP 内联 meta；`script-src 'unsafe-inline'` 仅为本地交互脚本，不加载远端。
  - 卡片数据全部来自本地派生视图，零网络。
"""

import html
import json
import os

# 五个状态不只是颜色，都带文字（契约要求）
VERDICT_LABEL = {
    "supported": "支持",
    "refuted": "反驳",
    "insufficient_evidence": "证据不足",
    "unknown": "未裁决",
}

CSP = ("default-src 'none'; style-src 'unsafe-inline'; "
       "script-src 'unsafe-inline'; img-src data:; "
       "object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'")


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


CSS = """
*{box-sizing:border-box}
body{margin:0;padding:24px;background:#f6f7f9;color:#1a1a1e;
 font-family:-apple-system,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif;
 font-size:14px;line-height:1.6}
.wrap{max-width:1040px;margin:0 auto}
.card{background:#fff;border:1px solid #e3e5e9;border-radius:10px;padding:20px 22px;margin-bottom:16px}
h1{font-size:20px;margin:0 0 4px;word-break:break-all}
h2{font-size:15px;margin:0 0 12px;color:#2b2b31}
.meta{color:#6b7280;font-size:12.5px;word-break:break-all}
.scope{background:#f0f4ff;border-left:3px solid #4b6fd6;padding:10px 12px;
 border-radius:0 6px 6px 0;font-size:13px;margin:12px 0 0}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0}
.badge{display:inline-flex;align-items:center;gap:6px;border:1px solid #dfe2e8;
 border-radius:999px;padding:2px 10px;font-size:12.5px;background:#fafbfc}
.dot{width:8px;height:8px;border-radius:50%;flex:none}
.d-ok{background:#16a34a}.d-bad{background:#dc2626}.d-mid{background:#d97706}.d-none{background:#9ca3af}
.row{display:flex;gap:14px;padding:7px 0;border-bottom:1px solid #f0f1f4}
.row:last-child{border-bottom:none}
.k{color:#6b7280;min-width:120px;flex:none;font-size:13px}
.v{word-break:break-all}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #eef0f3;word-break:break-all}
th{color:#6b7280;font-weight:500;background:#fafbfc}
.tabs{display:flex;gap:4px;border-bottom:1px solid #e3e5e9;margin-bottom:14px;flex-wrap:wrap}
.tab{padding:7px 14px;border:none;background:none;cursor:pointer;font-size:13.5px;
 color:#6b7280;border-bottom:2px solid transparent;font-family:inherit}
.tab.on{color:#1a1a1e;border-bottom-color:#4b6fd6;font-weight:500}
.pane{display:none}.pane.on{display:block}
.tree{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}
.tree div{padding:2px 0;word-break:break-all}
.dir{color:#4b6fd6;font-weight:500}
.sz{color:#9ca3af;font-size:11.5px;margin-left:8px}
.lim{color:#92400e;background:#fffbeb;border-left:3px solid #d97706;
 padding:8px 12px;border-radius:0 6px 6px 0;margin:8px 0;font-size:13px}
.foot{color:#9ca3af;font-size:11.5px;margin-top:18px;word-break:break-all}
code{background:#f3f4f6;padding:1px 5px;border-radius:3px;font-size:12px}
"""

JS = """
function showTab(id){
  document.querySelectorAll('.pane').forEach(function(p){p.classList.remove('on')});
  document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('on')});
  var p=document.getElementById(id); if(p)p.classList.add('on');
  var b=document.querySelector('[data-tab="'+id+'"]'); if(b)b.classList.add('on');
}
"""


def _tree_html(nodes):
    """按路径层级输出缩进树；只用已存在的节点，不编造层级。"""
    paths = {}
    for n in nodes:
        if n.get("node_type") in ("file", "directory"):
            paths[n.get("path", "")] = n
    lines = []
    for p in sorted(paths, key=lambda x: "/" + x):
        n = paths[p]
        depth = p.count("/")
        is_dir = n["node_type"] == "directory"
        name = p.rsplit("/", 1)[-1] if "/" in p else p
        size = n.get("size")
        sz = f'<span class="sz">{size} B</span>' if (size is not None and not is_dir) else ""
        cls = "dir" if is_dir else ""
        mark = "▸ " if is_dir else "· "
        lines.append(
            f'<div style="padding-left:{depth*16}px" class="{cls}">'
            f'{mark}{esc(name)}{sz}</div>')
    return "".join(lines) if lines else "<div>无条目</div>"


def _claims_table(claims):
    if not claims:
        return "<p>本仓库暂无已登记命题。</p>"
    rows = []
    for c in claims:
        v = c.get("verdict") or "unknown"
        dot = {"supported": "d-ok", "refuted": "d-bad",
               "insufficient_evidence": "d-mid"}.get(v, "d-none")
        cid = (c.get("claim_id") or "").split("-")[-1][:10]
        rows.append(
            f'<tr><td><code>{esc(cid)}</code></td>'
            f'<td>{esc(c.get("claim_type"))}</td>'
            f'<td>{esc(c.get("path"))}</td>'
            f'<td><span class="dot {dot}"></span> {esc(VERDICT_LABEL.get(v, v))}</td>'
            f'<td>{esc(c.get("fact_count", 0))}</td></tr>')
    return ("<table><thead><tr><th>Claim</th><th>类型</th><th>文件</th>"
            "<th>裁决</th><th>证据</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def render_repo_card_html(card, graph, *, assembled_at=""):
    """渲染一张仓库知识卡片（单文件，可直接打开）。"""
    c = card or {}
    comp = c.get("completeness") or {}
    vs = c.get("verdict_summary") or {}

    badges = []
    for k in ("supported", "refuted", "insufficient_evidence", "unknown"):
        if vs.get(k):
            dot = {"supported": "d-ok", "refuted": "d-bad",
                   "insufficient_evidence": "d-mid"}.get(k, "d-none")
            badges.append(
                f'<span class="badge"><span class="dot {dot}"></span>'
                f'{esc(VERDICT_LABEL.get(k, k))} {esc(vs[k])}</span>')

    lim = "".join(f'<div class="lim">{esc(x)}</div>'
                  for x in (c.get("limitations") or []))

    ids = {n["id"]: n for n in (graph.get("nodes") or [])}
    share_rows = []
    for e in (graph.get("edges") or []):
        if e.get("edge_type") != "SHARES_FACT":
            continue
        a = (ids.get(e.get("from"), {}).get("claim_id") or "").split("-")[-1][:8]
        b = (ids.get(e.get("to"), {}).get("claim_id") or "").split("-")[-1][:8]
        if a == b:
            continue
        share_rows.append(
            f'<li><code>{esc(a)}</code> ↔ <code>{esc(b)}</code> '
            f'· 共享 <code>{esc((e.get("fact_id") or "")[:22])}</code></li>')

    share_block = ""
    if share_rows:
        share_block = (
            '<div class="card"><h2>共享证据关联</h2>'
            '<p class="meta">以下 Claim 共享同一 Fact。<strong>共享证据不构成互相证明。</strong></p>'
            '<ul>' + "".join(share_rows[:30]) + '</ul></div>')

    parts = []
    parts.append('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">')
    parts.append(f'<meta http-equiv="Content-Security-Policy" content="{CSP}">')
    parts.append(f'<title>{esc(c.get("title"))} · 仓库知识卡片</title>')
    parts.append(f'<style>{CSS}</style></head><body><div class="wrap">')

    # A 标题与范围
    parts.append('<div class="card">')
    parts.append(f'<h1>{esc(c.get("title"))}</h1>')
    parts.append(
        f'<div class="meta">仓库 <code>{esc(c.get("repository_id"))}</code> · '
        f'固定 Commit <code>{esc(c.get("commit_sha"))}</code> · '
        f'树 {esc(comp.get("tree_status_label"))}'
        f'（{esc(comp.get("tree_entry_count"))} 条目，深度 {esc(comp.get("tree_max_depth"))}）'
        '</div>')
    parts.append(f'<div class="scope">{esc(c.get("scope_statement"))}</div>')
    if badges:
        parts.append('<div class="badges">' + "".join(badges) + '</div>')
    parts.append('</div>')

    # Tab 区
    parts.append('<div class="card">')
    parts.append('<div class="tabs">')
    parts.append('<button class="tab on" data-tab="p-struct" onclick="showTab(\'p-struct\')">文件结构</button>')
    parts.append('<button class="tab" data-tab="p-claims" onclick="showTab(\'p-claims\')">知识主张</button>')
    parts.append('<button class="tab" data-tab="p-graph" onclick="showTab(\'p-graph\')">图谱统计</button>')
    parts.append('<button class="tab" data-tab="p-limit" onclick="showTab(\'p-limit\')">限制</button>')
    parts.append('</div>')

    parts.append(f'<div class="pane on" id="p-struct"><div class="tree">'
                 f'{_tree_html(graph.get("nodes") or [])}</div></div>')

    parts.append(f'<div class="pane" id="p-claims">{_claims_table(c.get("claims"))}</div>')

    g = c.get("graph") or {}
    parts.append('<div class="pane" id="p-graph">')
    parts.append(f'<div class="row"><span class="k">节点</span>'
                 f'<span class="v">{esc(g.get("node_count"))}</span></div>')
    parts.append(f'<div class="row"><span class="k">边</span>'
                 f'<span class="v">{esc(g.get("edge_count"))}</span></div>')
    nt = g.get("node_types") or {}
    et = g.get("edge_types") or {}
    parts.append('<div class="row"><span class="k">节点构成</span><span class="v">'
                 + " · ".join(f"{esc(k)} {esc(v)}" for k, v in sorted(nt.items()))
                 + '</span></div>')
    parts.append('<div class="row"><span class="k">边构成</span><span class="v">'
                 + (" · ".join(f"{esc(k)} {esc(v)}" for k, v in sorted(et.items())) or "无")
                 + '</span></div>')
    parts.append(f'<div class="row"><span class="k">图谱摘要</span>'
                 f'<span class="v"><code>{esc((g.get("graph_digest") or "")[:24])}</code></span></div>')
    parts.append('</div>')

    parts.append(f'<div class="pane" id="p-limit">{lim or "<p>无已知限制。</p>"}</div>')
    parts.append('</div>')

    parts.append(share_block)

    # G 分发门禁
    d = c.get("distribution") or {}
    parts.append('<div class="card"><h2>分发门禁</h2>')
    parts.append(f'<div class="row"><span class="k">允许分发</span>'
                 f'<span class="v">{"是" if d.get("distribution_allowed") else "否"}</span></div>')
    parts.append(f'<div class="row"><span class="k">冻结状态</span>'
                 f'<span class="v"><code>{esc(d.get("freeze_state"))}</code></span></div>')
    parts.append(f'<div class="row"><span class="k">适用范围</span>'
                 f'<span class="v"><code>{esc(d.get("scope"))}</code></span></div>')
    parts.append('</div>')

    parts.append(f'<div class="foot">卡片身份 <code>{esc(c.get("card_id"))}</code> · '
                 f'Schema {esc(c.get("card_schema_version"))}'
                 + (f' · 渲染于 {esc(assembled_at)}' if assembled_at else "")
                 + f'<br>{esc(c.get("note"))}</div>')

    parts.append(f'<script>{JS}</script>')
    parts.append('</div></body></html>')
    return "".join(parts)


def write_card_html(*, data_root, repository_id, commit_sha, card, graph,
                    assembled_at=""):
    out = os.path.join(str(data_root), "派生视图", str(repository_id), str(commit_sha))
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, "knowledge_card.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(render_repo_card_html(card, graph, assembled_at=assembled_at))
    return p
