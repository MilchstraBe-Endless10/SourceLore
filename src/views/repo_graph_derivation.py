"""A 层图谱派生：从已有权威资产确定性生成仓库代码结构图谱。

★ 铁律（对齐 F1B_RENDERER_DECISIONS 第 4/5 节）：
  - 本模块**不读 GitHub**、不重新采集、不猜结构。
  - 所有节点与边必须能指回上游资产（tree_entry / Fact / Claim / Evidence）。
  - 无来源的边不得出现。未解析的关系保持 `UNRESOLVED`，不伪装成确定关系。

数据来源（全部来自已登记 Storage）：
  1. repository_snapshot.payload.tree_entries  → 文件树节点
  2. extracted_fact（rule_id 前缀 SOURCE_/MODULE_）→ 符号声明与导入观察
  3. claim_candidate                          → 命题节点

产出 graph JSON：
  {
    "repository_id", "commit_sha", "derivation_version",
    "completeness": {...},            # 树完整性如实转述，不放大
    "nodes": [...],                   # id 稳定、带 source_ref
    "edges": [...],                   # type + source_ref + resolution_state
    "limitations": [...]              # 缺什么就说什么
  }
"""

import json
import hashlib

DERIVATION_VERSION = "repo-graph/1"

# 边类型：只允许这几种，新增须同时补证据来源
EDGE_TYPES = (
    "TREE_CONTAINS",      # 目录 → 子项（来自 tree_entries.path 的层级关系）
    "IMPORTS",            # 文件 → 模块（来自 source_reference 观察）
    "DECLARES",           # 文件 → 符号（来自 symbol 声明观察）
    "CLAIM_ABOUT",        # Claim → 文件/符号
    "SHARES_FACT",        # Claim ↔ Claim（共享同一 Fact）—— 注意：不是互相证明
)


def _stable_id(prefix, *parts):
    """稳定 ID：同样输入永远同样输出，便于跨次比对。"""
    raw = "\x1f".join(str(p) for p in parts)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _norm_path(p):
    """归一化路径：只剥 "./" 前缀。

    ★ 绝不能用 lstrip("./") —— 它会把 `.editorconfig` 吃成 `editorconfig`，
      那是字符集剥离，不是前缀剥离（实测踩过）。
    """
    v = (p or "").strip()
    while v.startswith("./"):
        v = v[2:]
    return v


# ── 1. 文件树 ────────────────────────────────────────────────────

def build_tree_nodes(tree_entries, *, repository_id, commit_sha):
    """从 tree_entries 建文件树节点与包含边。

    只陈述「该 Commit 的树里有这个条目」；不推断用途。
    """
    nodes, edges, seen = [], [], set()

    for e in tree_entries or []:
        path = _norm_path(e.get("path"))
        if not path or path in seen:
            continue
        seen.add(path)

        kind = e.get("type") or "blob"
        nodes.append({
            "id": _stable_id("node:path:", repository_id, commit_sha, path),
            "node_type": "directory" if kind == "tree" else ("file" if kind == "blob" else kind),
            "label": path,
            "path": path,
            "depth": path.count("/"),
            "size": e.get("size"),
            "git_object_sha": e.get("sha"),
            "source_ref": {
                "kind": "tree_entry",
                "repository_id": repository_id,
                "commit_sha": commit_sha,
                "path": path,
            },
        })

    # 包含边：按路径层级直接由路径推导，来源仍是 tree_entry
    path_set = seen
    for path in sorted(path_set):
        parent = path.rsplit("/", 1)[0] if "/" in path else None
        frm = None
        if parent and parent in path_set:
            frm = _stable_id("node:path:", repository_id, commit_sha, parent)
        edges.append({
            "id": _stable_id("edge:contains:", repository_id, commit_sha, path),
            "edge_type": "TREE_CONTAINS",
            "from": frm,                     # None = 根层，不编造虚拟根节点
            "to": _stable_id("node:path:", repository_id, commit_sha, path),
            "resolution_state": "DERIVED_FROM_PATH",
            "source_ref": {
                "kind": "tree_entry",
                "commit_sha": commit_sha,
                "path": path,
            },
        })

    return nodes, edges


# ── 2. 符号与导入 ───────────────────────────────────────────────

def build_symbol_and_import_graph(claim_rows, *, repository_id):
    """从已登记 code 类 Claim 建符号节点与导入边。

    ★ 只认来源代码里确实存在的观察；`source_reference` 缺失 → 不进边。
    """
    nodes, edges = [], []
    symbols, imports = {}, {}

    for c in claim_rows or []:
        subj = c.get("subject") or {}
        path = _norm_path(c.get("file_path") or subj.get("file_path")
                          or c.get("normalized_path"))
        if not path:
            continue

        name = (subj.get("qualified_name") or subj.get("exported_name")
                or subj.get("imported_name") or subj.get("name"))
        ref = subj.get("source_reference")
        kind = c.get("kind") or subj.get("symbol_kind")
        start_line = c.get("start_line")

        if name and kind and not ref:
            key = (path, name)
            if key in symbols:
                continue
            symbols[key] = 1
            sid = _stable_id("node:symbol:", repository_id, path, name)
            nodes.append({
                "id": sid,
                "node_type": "symbol",
                "label": name,
                "path": path,
                "symbol_kind": kind,
                "start_line": start_line,
                "fact_id": c.get("fact_id"),
                "source_ref": {"kind": "source_fact",
                               "fact_id": c.get("fact_id"), "path": path},
            })
            edges.append({
                "id": _stable_id("edge:declares:", repository_id, path, name),
                "edge_type": "DECLARES",
                "from": _stable_id("node:path:", repository_id,
                                   c.get("commit_sha"), path),
                "to": sid,
                "resolution_state": "OBSERVED_IN_SOURCE",
                "source_ref": {"kind": "source_fact", "fact_id": c.get("fact_id")},
            })

        if ref:
            key = (path, ref, name)
            if key in imports:
                continue
            imports[key] = 1
            mid = _stable_id("node:module:", repository_id, ref)
            nodes.append({
                "id": mid,
                "node_type": "module_ref",
                "label": ref,
                "module_specifier": ref,
                # ★ 模块是否真实存在由树证据决定，此处不作断言
                "resolved_in_tree": None,
                "source_ref": {"kind": "source_fact",
                               "fact_id": c.get("fact_id"), "path": path},
            })
            edges.append({
                "id": _stable_id("edge:imports:", repository_id, path, ref, name),
                "edge_type": "IMPORTS",
                "from": _stable_id("node:path:", repository_id,
                                   c.get("commit_sha"), path),
                "to": mid,
                "imported_name": name,
                "resolution_state": "SPECIFIER_OBSERVED",
                "source_ref": {"kind": "source_fact", "fact_id": c.get("fact_id")},
            })

    return nodes, edges


# ── 3. 知识主张网络 ─────────────────────────────────────────────

def build_claim_network(claim_rows, *, repository_id, verifications=None):
    """建 Claim 节点与「共享 Fact」关联。

    ★ 共享 Fact ≠ 互相证明。边的语义必须写死为 SHARES_FACT，
      并附 not_a_proof 说明，避免被读成推导关系。

    ★ 证据位置实测（2026-11-09）：
      claim_candidate.payload **没有** evidence_refs（0/39）；
      真正的证据在 claim_verification.payload.fact_ids（30/33 有值）。
      因此证据必须由 verifications 传入，不能从 claim 上硬取。
    """
    vmap = {}
    for v in (verifications or []):
        cid = v.get("claim_id")
        if cid:
            vmap.setdefault(cid, []).append(v)

    # ★ 同一 claim_id 可能在库里有多条资产记录（不同 asset_version）。
    #   按 claim_id 去重，保留 asset_version 最大的那条，否则会画出自环。
    dedup = {}
    for c in (claim_rows or []):
        cid = c.get("claim_id") or c.get("finding_id")
        if not cid:
            continue
        ver = c.get("asset_version")
        cur = dedup.get(cid)
        if cur is None:
            dedup[cid] = c
        else:
            try:
                if ver is not None and (cur.get("asset_version") is None
                                        or ver > cur.get("asset_version")):
                    dedup[cid] = c
            except TypeError:
                pass

    nodes, edges = [], []
    fact_to_claims = {}

    for c in dedup.values():
        cid = c.get("claim_id") or c.get("finding_id")
        if not cid:
            continue
        # 证据优先取 verification 的 fact_ids；回退到 claim 自带 evidence_refs
        facts = []
        for v in vmap.get(cid, []):
            facts.extend(v.get("fact_ids") or [])
        if not facts:
            facts = [f for f in (c.get("evidence_refs") or [])
                     if isinstance(f, str) and f.startswith("fact:")]
        nodes.append({
            "id": _stable_id("node:claim:", repository_id, cid),
            "node_type": "claim",
            "label": c.get("claim_type") or "claim",
            "claim_id": cid,
            "claim_type": c.get("claim_type"),
            "verdict_status": (vmap.get(cid, [{}])[0].get("status")
                               if vmap.get(cid) else c.get("verdict_status")),
            "review_status": c.get("review_status"),
            "verification_id": c.get("verification_id"),
            "path": _norm_path(c.get("normalized_path") or c.get("file_path")),
            "fact_count": len(facts),
            "source_ref": {"kind": "claim", "claim_id": cid},
        })
        for f in facts:
            fact_to_claims.setdefault(f, []).append(cid)

    for fact_id, claims in fact_to_claims.items():
        if len(claims) < 2:
            continue
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                a, b = sorted((claims[i], claims[j]))
                if a == b:
                    continue  # 去重后不应再出现，防御性跳过
                edges.append({
                    "id": _stable_id("edge:shares:", repository_id, a, b, fact_id),
                    "edge_type": "SHARES_FACT",
                    "from": _stable_id("node:claim:", repository_id, a),
                    "to": _stable_id("node:claim:", repository_id, b),
                    "fact_id": fact_id,
                    "resolution_state": "SHARED_EVIDENCE_ONLY",
                    "semantics": "共享同一证据来源，不构成互相证明",
                    "not_a_proof": True,
                })

    return nodes, edges


# ── 4. 装配 ────────────────────────────────────────────────────

def derive_repo_graph(*, repository_id, commit_sha, tree_entries,
                      claim_rows, tree_coverage=None, code_rows=None,
                      verifications=None):
    """装配一张完整的 A 层图谱。

    返回值是**确定性**的：同样输入必然同样输出（含 graph_digest）。
    """
    tree_nodes, tree_edges = build_tree_nodes(
        tree_entries, repository_id=repository_id, commit_sha=commit_sha)

    sym_nodes, sym_edges = build_symbol_and_import_graph(
        code_rows or [], repository_id=repository_id)

    claim_nodes, claim_edges = build_claim_network(
        claim_rows or [], repository_id=repository_id,
        verifications=verifications)

    nodes = tree_nodes + sym_nodes + claim_nodes
    edges = tree_edges + sym_edges + claim_edges

    # 去重（同一 ID 只保留一条）
    seen_n, uniq_nodes = set(), []
    for n in nodes:
        if n["id"] in seen_n:
            continue
        seen_n.add(n["id"])
        uniq_nodes.append(n)
    seen_e, uniq_edges = set(), []
    for e in edges:
        if e["id"] in seen_e:
            continue
        seen_e.add(e["id"])
        uniq_edges.append(e)

    limitations = []
    cov = (tree_coverage or [{}])[0] if tree_coverage else {}
    completeness = cov.get("completeness_status")
    if completeness == "COMPLETE":
        max_depth = max((n.get("depth", 0) for n in tree_nodes), default=0)
        if max_depth == 0 and len(tree_nodes) > 0:
            # ★ 如实报告：COMPLETE 但只有根层，说明子树未展开
            completeness = "ROOT_ONLY"
            limitations.append(
                "树快照标记 COMPLETE，但最大深度为 0（仅根层条目）；"
                "子目录内容未采集，不得据此推断深层路径不存在。")
    if not sym_edges:
        limitations.append("无源码符号/导入观察，模块关系为空不代表没有依赖。")

    graph = {
        "derivation_version": DERIVATION_VERSION,
        "repository_id": str(repository_id),
        "commit_sha": commit_sha,
        "completeness": {
            "tree_status": completeness,
            "tree_entry_count": len(tree_nodes),
            "tree_max_depth": max((n.get("depth", 0) for n in tree_nodes), default=0),
            "symbol_count": len([n for n in uniq_nodes if n["node_type"] == "symbol"]),
            "module_ref_count": len([n for n in uniq_nodes if n["node_type"] == "module_ref"]),
            "claim_count": len([n for n in uniq_nodes if n["node_type"] == "claim"]),
        },
        "nodes": sorted(uniq_nodes, key=lambda x: x["id"]),
        "edges": sorted(uniq_edges, key=lambda x: x["id"]),
        "limitations": limitations,
        "distribution_allowed": False,
        "note": "A 层代码结构图谱为本地内部派生视图，不是对外发布的正式知识。",
    }
    graph["graph_digest"] = hashlib.sha256(
        json.dumps({"nodes": graph["nodes"], "edges": graph["edges"]},
                   ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return graph
