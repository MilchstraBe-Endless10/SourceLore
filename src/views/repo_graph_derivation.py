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
    "IMPORTS",            # 文件 → 模块（来自 source_reference 观察，绝不叫 CALLS）
    "RESOLVES_TO",        # 模块引用 → 已验证本地目标（来自 P2-A 静态关系）
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

def build_symbol_and_import_graph(claim_rows, *, repository_id, commit_sha=None,
                                  relations=None, tree_paths=None):
    """从源码观察建符号节点、导入节点与边。

    ★ P2-B §3/§6 统一身份：
      - 符号 ID 含 repository_id / commit_sha / 路径 / 限定名 / 作用域；
      - module_ref ID 含导入方路径（同一 specifier 跨文件不再错误归并）；
      - 节点携带完整来源身份（fact/parser/blob/content/provenance/status）；
      - 仅在有已验证的 LOCAL_MODULE_RESOLVED 关系时建 RESOLVES_TO 边；
        未解析关系只留观察节点，不冒充已验证目标。
    """
    nodes, edges = [], []
    symbols, imports = {}, {}
    rel_index = {}
    for rel in (relations or []):
        key = (_norm_path(rel.get("importing_file_path")), rel.get("module_specifier"))
        rel_index.setdefault(key, []).append(rel)
    tree_path_set = set(tree_paths or [])
    implicit_files = {}   # 源码/关系证据支撑、但不在 tree 快照中的文件节点

    def file_nid(path):
        return _stable_id("node:path:", repository_id, commit_sha, path)

    def ensure_file(path, source_ref, origin):
        if path in tree_path_set or not path:
            return
        if path not in implicit_files:
            implicit_files[path] = {
                "id": file_nid(path),
                "node_type": "file",
                "label": path,
                "path": path,
                "in_tree": False,
                "node_origin": origin,
                "source_ref": source_ref,
            }

    for c in claim_rows or []:
        subj = c.get("subject") or {}
        path = _norm_path(c.get("file_path") or subj.get("file_path")
                          or c.get("normalized_path"))
        if not path:
            continue

        name = (subj.get("qualified_name") or subj.get("symbol_name")
                or subj.get("name") or subj.get("exported_name")
                or subj.get("imported_name"))
        ref = subj.get("source_reference")
        # ★ P2-C：c["kind"] 是分类(symbol/import/export)，不是符号类型(function/class)；
        #   展示用 symbol_kind 只取 subject.symbol_kind。
        kind = subj.get("symbol_kind") or subj.get("export_kind")
        scope = subj.get("scope") or subj.get("qualname_prefix") or ""
        provenance = subj.get("provenance_level") or c.get("provenance_level") or "OBSERVED"

        def evidence():
            return {
                "kind": "source_fact",
                "repository_id": repository_id,
                "commit_sha": c.get("commit_sha") or commit_sha,
                "fact_id": c.get("fact_id"),
                "source_fact_id": c.get("fact_id") or c.get("source_fact_id"),
                "path": path,
                "parser_id": subj.get("parser_id") or c.get("parser_id"),
                "parser_version": subj.get("parser_version") or c.get("parser_version"),
                "git_blob_oid": subj.get("git_blob_oid") or c.get("git_blob_oid"),
                "content_asset_id": subj.get("content_asset_id") or c.get("content_asset_id"),
                "provenance_level": provenance,
                "extraction_status": subj.get("extraction_status") or c.get("extraction_status"),
            }

        # ★ P2-C §2：按统一契约的 kind 精确分派，不再用 "name+kind+not ref"
        #   模糊判断（那会把 Python from_import 误判成符号声明）。
        s_kind = c.get("kind") or subj.get("kind") or ""
        # ★ P2-C：兼容历史/夹具里用 function/class 等表示符号的 kind；
        #   统一契约输出的是 "symbol"。二者都归到符号分支。
        if s_kind in ("function", "js_function", "class", "method",
                      "variable", "const", "interface", "type", "enum"):
            s_kind = "symbol"
        if s_kind == "symbol" and name:
            key = (path, name, scope)
            if key in symbols:
                continue
            symbols[key] = 1
            ensure_file(path, evidence(), "SOURCE_SYMBOL_FACT")
            sid = _stable_id("node:symbol:", repository_id, commit_sha, path,
                             name, scope)
            nodes.append({
                "id": sid,
                "node_type": "symbol",
                "label": name,
                "symbol_name": name,
                "qualified_name": subj.get("qualified_name") or name,
                "scope": scope,
                "path": path,
                "symbol_kind": kind,
                "start_line": subj.get("start_line") or c.get("start_line"),
                "line_range": subj.get("line_range") or c.get("line_range"),
                "byte_range": subj.get("byte_range") or c.get("byte_range"),
                "parser_id": subj.get("parser_id") or c.get("parser_id"),
                "parser_version": subj.get("parser_version") or c.get("parser_version"),
                "git_blob_oid": subj.get("git_blob_oid") or c.get("git_blob_oid"),
                "content_asset_id": subj.get("content_asset_id") or c.get("content_asset_id"),
                "provenance_level": provenance,
                "extraction_status": subj.get("extraction_status") or c.get("extraction_status"),
                "source_fact_id": c.get("fact_id") or c.get("source_fact_id"),
                "source_ref": evidence(),
            })
            edges.append({
                "id": _stable_id("edge:declares:", repository_id, commit_sha,
                                 path, name, scope),
                "edge_type": "DECLARES",
                "from": file_nid(path),
                "to": sid,
                "resolution_state": provenance,
                "source_ref": evidence(),
            })

        if s_kind in ("import", "export") and ref:
            # ★ P2-C §2：IMPORT 与 EXPORT(re_export) 分别成边，不混为一类
            edge_type = "IMPORTS" if s_kind == "import" else "RE_EXPORTS"
            key = (path, ref, name, s_kind)
            if key in imports:
                continue
            imports[key] = 1
            ensure_file(path, evidence(), "SOURCE_IMPORT_FACT")
            # module_ref 身份含导入方路径：同名 specifier 跨文件不归并
            mid = _stable_id("node:module:", repository_id, commit_sha, path, ref)
            rels = rel_index.get((path, ref), [])
            verified = [r for r in rels
                        if r.get("resolution_state") == "LOCAL_MODULE_RESOLVED"
                        and r.get("status") == "RESOLVED"
                        and r.get("resolved_target_path")]
            # ★ P2-C §2：多候选/多配置上下文不得无条件取 verified[0]。
            #   按 resolved_target_path + fact_id + resolution_id 确定性排序；
            #   多候选时只落一条主边，但把所有候选/歧义如实写进节点，
            #   不凭第一条冒充唯一解析。
            def _rel_key(r):
                return (str(r.get("resolved_target_path") or ""),
                        str(r.get("fact_id") or ""),
                        str(r.get("resolution_id") or ""))
            verified = sorted(verified, key=_rel_key)
            primary = verified[0] if verified else None
            cand_targets = sorted({str(r.get("resolved_target_path"))
                                   for r in verified if r.get("resolved_target_path")})
            ambiguous = len(cand_targets) > 1
            node = {
                "id": mid,
                "node_type": "module_ref",
                "label": ref,
                # ★ P2-C §2：IMPORT/EXPORT 按真实 rule_id 分别标注，不合并身份
                "fact_kind": s_kind,
                "module_specifier": ref,
                "importing_file_path": path,
                "resolution_state": (primary["resolution_state"] if primary
                                     else (rels[0].get("resolution_state")
                                           if rels else "SPECIFIER_OBSERVED")),
                "import_fact_id": c.get("fact_id"),
                "relation_fact_ids": [r.get("fact_id") for r in rels if r.get("fact_id")],
                "relation_ids": [r.get("resolution_id") for r in rels if r.get("resolution_id")],
                "candidate_paths": sorted({json.dumps(p, sort_keys=True, ensure_ascii=False)
                                           if isinstance(p, (dict, list)) else str(p)
                                           for r in verified
                                           for p in (r.get("candidate_paths") or [])}),
                "candidate_target_paths": cand_targets,
                "ambiguous_resolution": ambiguous,
                "matched_config_rule": (primary.get("matched_config_rule")
                                        if primary else None),
                "matched_config_field": (primary.get("matched_config_field")
                                         if primary else None),
                "config_blob_oids": (primary.get("config_blob_oids")
                                     if primary else []),
                "resolver_version": (primary.get("resolver_version")
                                     if primary else None),
                "evidence_refs": [r for rel in verified
                                  for r in (rel.get("evidence_refs") or [])],
                "source_identity": primary.get("repository_id") if primary else None,
                "source_ref": evidence(),
            }
            nodes.append(node)
            edges.append({
                "id": _stable_id("edge:imports:", edge_type, repository_id,
                                 commit_sha, path, ref, name),
                "edge_type": edge_type,
                "from": file_nid(path),
                "to": mid,
                "imported_name": name,
                "resolution_state": "SPECIFIER_OBSERVED",
                "import_fact_id": c.get("fact_id"),
                "relation_fact_ids": node["relation_fact_ids"],
                "evidence_refs": node["evidence_refs"],
                "source_ref": evidence(),
            })
            # 仅已验证解析建 RESOLVES_TO，目标必须实际存在于树，避免悬空边
            # ★ P2-C §2：多候选目标时按确定性顺序取主目标建边，歧义写入边，
            #   并在节点 candidate_target_paths 保留全部候选；不冒充唯一解析。
            if primary:
                target = _norm_path(primary["resolved_target_path"])
                if target:
                    rel_src = {
                        "kind": "module_relation_fact",
                        "fact_id": primary.get("fact_id"),
                        "resolution_id": primary.get("resolution_id"),
                        "repository_id": primary.get("repository_id"),
                        "commit_sha": primary.get("commit_sha"),
                    }
                    ensure_file(target, rel_src, "VERIFIED_LOCAL_RELATION")
                    edges.append({
                        "id": _stable_id("edge:resolves:", repository_id, commit_sha,
                                         path, ref, target),
                        "edge_type": "RESOLVES_TO",
                        "from": mid,
                        "to": file_nid(target),
                        "resolution_state": "LOCAL_MODULE_RESOLVED",
                        "relation_fact_id": primary.get("fact_id"),
                        "resolution_policy": primary.get("resolution_policy"),
                        "ambiguous_resolution": ambiguous,
                        "candidate_target_paths": cand_targets,
                        "evidence_refs": node["evidence_refs"],
                        "source_ref": {
                            "kind": "module_relation_fact",
                            "fact_id": primary.get("fact_id"),
                            "resolution_id": primary.get("resolution_id"),
                            "repository_id": primary.get("repository_id"),
                            "commit_sha": primary.get("commit_sha"),
                        },
                    })
                    node["resolved_target_path"] = target
                    node["target_in_tree"] = target in tree_path_set

    nodes.extend(implicit_files.values())
    return nodes, edges


# ── 3. 知识主张网络 ─────────────────────────────────────────────

def build_claim_network(claim_rows, *, repository_id, commit_sha=None,
                        verifications=None):
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
            "id": _stable_id("node:claim:", repository_id, commit_sha, cid),
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
                    "id": _stable_id("edge:shares:", repository_id, commit_sha, a, b, fact_id),
                    "edge_type": "SHARES_FACT",
                    "from": _stable_id("node:claim:", repository_id, commit_sha, a),
                    "to": _stable_id("node:claim:", repository_id, commit_sha, b),
                    "fact_id": fact_id,
                    "resolution_state": "SHARED_EVIDENCE_ONLY",
                    "semantics": "共享同一证据来源，不构成互相证明",
                    "not_a_proof": True,
                })

    return nodes, edges


# ── 4. 装配 ────────────────────────────────────────────────────

def derive_repo_graph(*, repository_id, commit_sha, tree_entries,
                      claim_rows, tree_coverage=None, code_rows=None,
                      verifications=None, relations=None,
                      symbol_meta=None, relation_meta=None):
    """装配一张完整的 A 层图谱。

    返回值是**确定性**的：同样输入必然同样输出（含 graph_digest）。
    节点/边身份含 repository_id + commit_sha；RESOLVES_TO 仅来自已验证关系。
    """
    tree_nodes, tree_edges = build_tree_nodes(
        tree_entries, repository_id=repository_id, commit_sha=commit_sha)
    tree_paths = [n["path"] for n in tree_nodes]

    sym_nodes, sym_edges = build_symbol_and_import_graph(
        code_rows or [], repository_id=repository_id, commit_sha=commit_sha,
        relations=relations, tree_paths=tree_paths)

    claim_nodes, claim_edges = build_claim_network(
        claim_rows or [], repository_id=repository_id, commit_sha=commit_sha,
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

    # ★ P2-B §6：丢弃悬空边（起点/终点必须实际存在），并如实记录数量。
    #   TREE_CONTAINS 根层 from=None 是合法的（无虚拟根节点），跳过校验。
    node_ids = {n["id"] for n in uniq_nodes}
    dangling = []
    kept_edges = []
    for e in uniq_edges:
        endpoints = [e.get("from"), e.get("to")]
        if any(x is not None and x not in node_ids for x in endpoints):
            dangling.append(e["id"])
            continue
        kept_edges.append(e)
    uniq_edges = kept_edges

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
    if dangling:
        limitations.append(
            f"派生过程中发现 {len(dangling)} 条悬空边（端点节点不存在），已剔除。")
    rel_meta = relation_meta or {}
    status_counts = rel_meta.get("status_counts") or {}
    if status_counts:
        unresolved = sum(v for k, v in status_counts.items()
                         if k and k != "RESOLVED")
        if unresolved:
            limitations.append(
                f"P2-A 关系中有 {unresolved} 条未解析/部分解析，未建立已验证目标边。")

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
        "edge_type_counts": {
            t: len([e for e in uniq_edges if e["edge_type"] == t])
            for t in EDGE_TYPES
        },
        "coverage": {
            "symbol": symbol_meta or {},
            "relation": rel_meta,
            "relation_status_counts": status_counts,
            "dangling_edges_dropped": len(dangling),
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
