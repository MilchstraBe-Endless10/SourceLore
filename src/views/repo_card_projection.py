"""仓库知识卡片与项目文档：把 A/B 图谱与权威知识投影成可读视图。

★ 定位（对齐 F1B_RENDERER_DECISIONS 第 4 节）：
  卡片是**派生视图**，不是第二份权威。所有内容从上游资产确定性生成。
  本节不调 LLM、不联网、不重算裁决。

产出（同一批数据，两种投影）：
  card-data.json   —— Bot 卡片渲染用
  project-overview.md / file-structure.md / module-dependencies.md /
  claim-network.md / evidence-index.md  —— 项目知识文档
"""

import json
import os
import hashlib

CARD_SCHEMA_VERSION = "sourcelore-repo-card/1"

# 裁决措辞（与 F2-P4A 契约一致，不得改写）
VERDICT_TEXT = {
    "supported": "在指定范围内，现有经过验证的证据支持该命题。",
    "refuted": "现有有效反证与该命题矛盾。",
    "insufficient_evidence": "证据不足，无法作出支持或反驳裁决。",
}

STATUS_LABEL = {
    "COMPLETE": "完整枚举",
    "PARTIAL": "部分覆盖",
    "ROOT_ONLY": "仅根层",
    "INCOMPLETE": "采集不完整",
}


def _digest(obj):
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _short_sha(s, n=10):
    return (s or "")[:n]


def build_card_data(*, repository_id, repository_name, commit_sha,
                    graph, claims, verifications=None):
    """合成 Bot 卡片数据。

    卡片结构对应渲染契约的七个区域，但按「仓库」聚合而非单条 Claim：
      A 标题与范围 / B 裁决汇总 / C 新鲜度 / D 审核 / E 来源与授权
      F 证据与历史 / G 限制与门禁
    """
    vmap = {}
    for v in (verifications or []):
        cid = v.get("claim_id")
        if cid:
            vmap.setdefault(cid, []).append(v)

    claim_items = []
    for c in claims or []:
        cid = c.get("claim_id")
        if not cid:
            continue
        vs = vmap.get(cid, [])
        status = vs[0].get("status") if vs else c.get("verdict_status")
        fact_ids = []
        for v in vs:
            fact_ids.extend(v.get("fact_ids") or [])
        claim_items.append({
            "claim_id": cid,
            "claim_type": c.get("claim_type"),
            "path": c.get("normalized_path"),
            "verdict": status,
            "verdict_text": VERDICT_TEXT.get(status, "尚未裁决"),
            "review_status": c.get("review_status"),
            "verification_id": (vs[0].get("verification_id")
                                if vs and vs[0].get("verification_id") else None),
            "fact_count": len(fact_ids),
        })

    by_verdict = {}
    for it in claim_items:
        by_verdict[it["verdict"] or "unknown"] = by_verdict.get(it["verdict"] or "unknown", 0) + 1

    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    comp = graph.get("completeness") or {}

    card = {
        "card_schema_version": CARD_SCHEMA_VERSION,
        "card_id": "SL-REPOCARD-" + _digest({
            "repository_id": repository_id, "commit_sha": commit_sha,
            "graph_digest": graph.get("graph_digest"),
            "claim_ids": sorted(i["claim_id"] for i in claim_items),
        })[:32],
        # A 标题与范围
        "title": repository_name or str(repository_id),
        "repository_id": str(repository_id),
        "commit_sha": commit_sha,
        "scope_statement": (
            f"本卡片只描述 {commit_sha} 这一个固定 Commit 上的仓库知识，"
            "不代表该仓库的当前最新状态。"),
        # B 裁决汇总
        "claims": claim_items,
        "verdict_summary": by_verdict,
        # C 完整性/新鲜度（如实转述，不放大）
        "completeness": {
            "tree_status": comp.get("tree_status"),
            "tree_status_label": STATUS_LABEL.get(comp.get("tree_status"),
                                                  comp.get("tree_status")),
            "tree_max_depth": comp.get("tree_max_depth"),
            "tree_entry_count": comp.get("tree_entry_count"),
            "claim_count": comp.get("claim_count"),
        },
        # D 人工审核
        "human_review": {
            "any_reviewed": any(i.get("review_status") not in (None, "pending_review")
                                for i in claim_items),
            "note": "证据裁决不替代人工审核。",
        },
        # E 来源与授权
        "provenance": {
            "source": "GitHub 固定 Commit 快照",
            "distribution_allowed": False,
            "authorization_class": "未知授权类别",
        },
        # F 证据与图谱
        "graph": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_types": _count_by(nodes, "node_type"),
            "edge_types": _count_by(edges, "edge_type"),
            "graph_digest": graph.get("graph_digest"),
        },
        # G 限制与门禁
        "limitations": list(graph.get("limitations") or []),
        "distribution": {
            "distribution_allowed": False,
            "freeze_state": "FROZEN_INTERNAL_RESTRICTED",
            "scope": "LOCAL_INTERNAL_TEST_ONLY",
        },
        "note": "本地内部预览产物，不是对外发布的正式知识。",
    }
    return card


def _count_by(items, key):
    out = {}
    for it in items:
        k = it.get(key) or "unknown"
        out[k] = out.get(k, 0) + 1
    return out


# ── 项目知识文档 ────────────────────────────────────────────────

def _md_overview(card, graph):
    lines = [f"# {card['title']}", ""]
    lines.append(f"- 仓库 ID：`{card['repository_id']}`")
    lines.append(f"- 固定 Commit：`{card['commit_sha']}`")
    lines.append(f"- 树完整度：{card['completeness']['tree_status_label']}"
                 f"（{card['completeness']['tree_entry_count']} 条目，"
                 f"最大深度 {card['completeness']['tree_max_depth']}）")
    lines.append("")
    lines.append(f"> {card['scope_statement']}")
    lines.append("")
    lines.append("## 裁决汇总")
    lines.append("")
    if card["verdict_summary"]:
        for k, v in sorted(card["verdict_summary"].items()):
            lines.append(f"- `{k}`：{v} 条 —— {VERDICT_TEXT.get(k, '尚未裁决')}")
    else:
        lines.append("- 本仓库暂无裁决。")
    lines.append("")
    if card["limitations"]:
        lines.append("## 已知限制")
        lines.append("")
        for l in card["limitations"]:
            lines.append(f"- {l}")
        lines.append("")
    lines.append("> 本文件为派生视图，内容全部来自已登记知识资产，不是第二份权威。")
    return "\n".join(lines)


def _md_file_structure(card, graph):
    nodes = [n for n in (graph.get("nodes") or [])
             if n.get("node_type") in ("file", "directory")]
    nodes.sort(key=lambda n: ("/" + n.get("path", "")))
    lines = [f"# 文件结构 · {card['title']}", ""]
    lines.append(f"固定 Commit `{card['commit_sha']}` · "
                 f"完整度 {card['completeness']['tree_status_label']}")
    lines.append("")
    if not nodes:
        lines.append("树中无可列举条目。")
    else:
        lines.append("| 路径 | 类型 | 大小 |")
        lines.append("|---|---|---|")
        for n in nodes:
            w = "目录" if n["node_type"] == "directory" else "文件"
            size = n.get("size")
            lines.append(f"| `{n.get('path')}` | {w} | "
                         f"{size if size is not None else '-'} |")
    lines.append("")
    if card["completeness"]["tree_max_depth"] == 0:
        lines.append("> △ 树快照仅含根层条目；子目录内容未采集，"
                     "不得据此推断深层路径不存在。")
    return "\n".join(lines)


def _md_dependencies(card, graph):
    edges = [e for e in (graph.get("edges") or [])
             if e.get("edge_type") in ("IMPORTS", "DECLARES")]
    lines = [f"# 模块与声明 · {card['title']}", ""]
    lines.append(f"固定 Commit `{card['commit_sha']}`")
    lines.append("")
    if not edges:
        lines.append("无源码导入/声明观察。")
        lines.append("")
        lines.append("> △ 缺少模块关系不代表没有依赖，只代表本 Commit 尚未做源码结构分析。")
    else:
        ids = {n["id"]: n for n in (graph.get("nodes") or [])}
        lines.append("| 关系 | 源 | 目标 | 解析状态 |")
        lines.append("|---|---|---|---|")
        for e in edges:
            a = ids.get(e.get("from"), {}).get("label", "-")
            b = ids.get(e.get("to"), {}).get("label", "-")
            lines.append(f"| {e['edge_type']} | `{a}` | `{b}` | "
                         f"{e.get('resolution_state')} |")
    return "\n".join(lines)


def _md_claims(card, graph):
    lines = [f"# 知识主张 · {card['title']}", ""]
    lines.append(f"固定 Commit `{card['commit_sha']}`")
    lines.append("")
    if not card["claims"]:
        lines.append("本仓库暂无已登记命题。")
        return "\n".join(lines)

    lines.append("| Claim | 类型 | 文件 | 裁决 | 证据数 |")
    lines.append("|---|---|---|---|---|")
    for c in card["claims"]:
        cid = c["claim_id"]
        short = cid.split("-")[-1][:10] if cid else "-"
        lines.append(f"| `{short}` | {c.get('claim_type') or '-'} | "
                     f"`{c.get('path') or '-'}` | {c.get('verdict') or '未裁决'} | "
                     f"{c.get('fact_count', 0)} |")
    lines.append("")

    shares = [e for e in (graph.get("edges") or [])
              if e.get("edge_type") == "SHARES_FACT"]
    if shares:
        ids = {n["id"]: n for n in (graph.get("nodes") or [])}
        lines.append("## 共享证据关联")
        lines.append("")
        lines.append("以下 Claim 共享同一 Fact。★ 共享证据**不构成互相证明**。")
        lines.append("")
        for e in shares[:20]:
            a = ids.get(e.get("from"), {}).get("claim_id", "-")
            b = ids.get(e.get("to"), {}).get("claim_id", "-")
            fa = (a or "").split("-")[-1][:8]
            fb = (b or "").split("-")[-1][:8]
            lines.append(f"- `{fa}` ↔ `{fb}` · 共享 `{(e.get('fact_id') or '')[:20]}`")
    return "\n".join(lines)


def _md_evidence(card, graph):
    lines = [f"# 证据索引 · {card['title']}", ""]
    lines.append(f"固定 Commit `{card['commit_sha']}`")
    lines.append("")
    total = sum(c.get("fact_count", 0) for c in card["claims"])
    lines.append(f"- Claim 数：{len(card['claims'])}")
    lines.append(f"- 关联 Fact 引用总数：{total}")
    lines.append(f"- 图谱节点：{card['graph']['node_count']}，"
                 f"边：{card['graph']['edge_count']}")
    lines.append("")
    lines.append("## 限制")
    lines.append("")
    for l in card["limitations"] or ["无"]:
        lines.append(f"- {l}")
    lines.append("")
    lines.append("## 分发门禁")
    lines.append("")
    d = card["distribution"]
    lines.append(f"- 允许分发：{'是' if d['distribution_allowed'] else '否'}")
    lines.append(f"- 冻结状态：`{d['freeze_state']}`")
    lines.append(f"- 适用范围：`{d['scope']}`")
    return "\n".join(lines)


DOCS = {
    "project-overview.md": _md_overview,
    "file-structure.md": _md_file_structure,
    "module-dependencies.md": _md_dependencies,
    "claim-network.md": _md_claims,
    "evidence-index.md": _md_evidence,
}


def write_derived_views(*, data_root, repository_id, commit_sha, card, graph):
    """把卡片数据与文档写入派生视图目录。返回写出的文件清单。"""
    out = os.path.join(str(data_root), "派生视图", str(repository_id), str(commit_sha))
    os.makedirs(out, exist_ok=True)

    written = []
    for name, fn in DOCS.items():
        p = os.path.join(out, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(fn(card, graph))
        written.append(p)

    p = os.path.join(out, "card-data.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=1)
    written.append(p)

    p = os.path.join(out, "code-graph.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=1)
    written.append(p)

    return written
