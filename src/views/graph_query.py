#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-C §3-§5：确定性图谱查询引擎（纯本地、只读、零网络）。

消费 P2-B 派生图谱 code-graph.json 的内存字典，不重新派生、不写任何资产。
全部结论可回查到图谱节点/边的 source_ref（Fact / relation / tree 身份）。

能力：
  - 实体定位（路径/模块 specifier/符号名/限定名/节点 ID），同名多候选如实返回；
  - 单节点检索（文件声明的符号、符号所属文件、源码证据位置）；
  - 正向静态依赖（IMPORTS + RESOLVES_TO）、反向依赖（谁指向目标模块）；
  - 有界多跳路径（默认 4 跳文件依赖，环检测、多候选、访问上限、截断状态）。

铁律：
  - 未发现路径 != 证实无依赖；反向导入 != 具体函数被调用；
  - 只沿已验证静态关系建边，不做模糊名称匹配、不合并来源身份；
  - 不修改传入的图谱对象。
"""
from __future__ import annotations

from collections import defaultdict, deque

# 静态依赖边：文件 --IMPORTS/RE_EXPORTS--> module_ref --RESOLVES_TO--> file
_DEP_FORWARD_EDGES = ("IMPORTS", "RE_EXPORTS")
_RESOLVE_EDGE = "RESOLVES_TO"
DEFAULT_MAX_HOPS = 4
DEFAULT_MAX_VISITED = 5000
DEFAULT_MAX_PATHS = 50


def _nodes(graph):
    return graph.get("nodes") or []


def _edges(graph):
    return graph.get("edges") or []


def _by_id(graph):
    return {n.get("id"): n for n in _nodes(graph)}


def build_index(graph):
    """构建只读查询索引（每次查询可复用）。"""
    nodes = _nodes(graph)
    nid = _by_id(graph)
    by_path = defaultdict(list)
    by_symbol = defaultdict(list)
    by_specifier = defaultdict(list)
    out_edges = defaultdict(list)
    in_edges = defaultdict(list)
    for n in nodes:
        nt = n.get("node_type")
        if nt in ("file", "directory") and n.get("path"):
            by_path[n["path"]].append(n)
        if nt == "symbol":
            if n.get("qualified_name"):
                by_symbol[n["qualified_name"]].append(n)
            if n.get("symbol_name"):
                by_symbol[n["symbol_name"]].append(n)
        if nt == "module_ref" and n.get("module_specifier"):
            by_specifier[n["module_specifier"]].append(n)
    for e in _edges(graph):
        if e.get("from"):
            out_edges[e["from"]].append(e)
        if e.get("to"):
            in_edges[e["to"]].append(e)
    # 文件级静态依赖邻接：file -> {target_file: [edge证据]}
    # 一条文件依赖 = file --IMPORTS/RE_EXPORTS--> module_ref --RESOLVES_TO--> file
    fwd = defaultdict(lambda: defaultdict(list))
    rev = defaultdict(lambda: defaultdict(list))
    for imp in _edges(graph):
        if imp.get("edge_type") not in _DEP_FORWARD_EDGES:
            continue
        src_file = nid.get(imp.get("from"))
        mod = nid.get(imp.get("to"))
        if not src_file or not mod or src_file.get("node_type") != "file":
            continue
        for res in out_edges.get(mod.get("id"), []):
            if res.get("edge_type") != _RESOLVE_EDGE:
                continue
            target = nid.get(res.get("to"))
            if not target or target.get("node_type") != "file":
                continue
            evidence = {
                "import_edge_id": imp.get("id"),
                "resolve_edge_id": res.get("id"),
                "module_specifier": mod.get("module_specifier"),
                "resolution_state": res.get("resolution_state"),
                "ambiguous_resolution": bool(res.get("ambiguous_resolution")),
                "import_fact_id": imp.get("import_fact_id"),
                "relation_fact_id": res.get("relation_fact_id"),
                "source_refs": [imp.get("source_ref"), res.get("source_ref")],
            }
            fwd[src_file["path"]][target["path"]].append(evidence)
            rev[target["path"]][src_file["path"]].append(evidence)
    return {
        "nodes_by_id": nid,
        "by_path": dict(by_path),
        "by_symbol": dict(by_symbol),
        "by_specifier": dict(by_specifier),
        "out_edges": dict(out_edges),
        "in_edges": dict(in_edges),
        "forward": {k: dict(v) for k, v in fwd.items()},
        "reverse": {k: dict(v) for k, v in rev.items()},
    }


def _candidate(nodes, kind):
    return [{"node_id": n.get("id"), "path": n.get("path"),
             "qualified_name": n.get("qualified_name"),
             "module_specifier": n.get("module_specifier"),
             "source_ref": n.get("source_ref")} for n in nodes]


def resolve_entity(index, entity, *, node_id=None):
    """§4 实体定位：区分『已定位/有歧义/未找到/图谱无此实体』。"""
    if node_id:
        n = index["nodes_by_id"].get(node_id)
        if not n:
            return {"status": "NOT_FOUND", "node_id": node_id, "candidates": []}
        return {"status": "RESOLVED", "strategy": "node_id", "unique": True,
                "node": n, "candidates": _candidate([n], n.get("node_type"))}
    e = (entity or "").strip()
    if not e:
        return {"status": "NOT_FOUND", "candidates": [], "reason": "EMPTY_ENTITY"}
    hits = []
    strategies = []
    if e in index["by_path"]:
        hits.extend(index["by_path"][e]); strategies.append("path")
    if e in index["by_specifier"]:
        hits.extend(index["by_specifier"][e]); strategies.append("module_specifier")
    if e in index["by_symbol"]:
        hits.extend(index["by_symbol"][e]); strategies.append("symbol_name")
    # 节点 ID 直接命中
    if e in index["nodes_by_id"]:
        hits.append(index["nodes_by_id"][e]); strategies.append("node_id")
    # 限定名/符号名子串仅在精确未命中时做保守候选，不建立关系
    if not hits:
        for name, ns in index["by_symbol"].items():
            if e and (e == name.split(".")[-1]):
                hits.extend(ns); strategies.append("unqualified_symbol")
    # 路径 basename 兜底：仅返回候选，不建立关系；同名文件如实标歧义
    if not hits and ("/" not in e) and e:
        for p, ns in index["by_path"].items():
            if p.rsplit("/", 1)[-1] == e:
                hits.extend(ns); strategies.append("path_basename")
    # 去重
    seen, uniq = set(), []
    for n in hits:
        if n.get("id") not in seen:
            seen.add(n.get("id")); uniq.append(n)
    if not uniq:
        return {"status": "NOT_FOUND_IN_GRAPH", "entity": e, "candidates": [],
                "note": "未定位到实体；不等于实体不存在或依赖不存在"}
    return {
        "status": "RESOLVED" if len(uniq) == 1 else "AMBIGUOUS",
        "entity": e, "strategy": "+".join(dict.fromkeys(strategies)),
        "unique": len(uniq) == 1, "candidates": _candidate(uniq, "mixed"),
    }


def node_query(index, node_id):
    """单节点检索：声明符号/所属文件/源码证据位置。"""
    n = index["nodes_by_id"].get(node_id)
    if not n:
        return {"status": "NOT_FOUND", "node_id": node_id}
    result = {"status": "FOUND", "node": n}
    if n.get("node_type") == "file":
        syms = []
        for e in index["out_edges"].get(node_id, []):
            if e.get("edge_type") == "DECLARES":
                sn = index["nodes_by_id"].get(e.get("to"))
                if sn:
                    syms.append({"id": sn.get("id"), "name": sn.get("symbol_name"),
                                 "qualified_name": sn.get("qualified_name"),
                                 "kind": sn.get("symbol_kind"),
                                 "start_line": sn.get("start_line"),
                                 "source_fact_id": sn.get("source_fact_id")})
        result["declared_symbols"] = syms
    if n.get("node_type") == "symbol":
        result["source_location"] = {
            "path": n.get("path"), "start_line": n.get("start_line"),
            "git_blob_oid": n.get("git_blob_oid"),
            "content_asset_id": n.get("content_asset_id"),
            "source_fact_id": n.get("source_fact_id"),
            "source_ref": n.get("source_ref"),
        }
        owner = []
        for e in index["in_edges"].get(node_id, []):
            if e.get("edge_type") == "DECLARES":
                owner.append(index["nodes_by_id"].get(e.get("from")))
        result["declared_in_files"] = [
            {"id": f.get("id"), "path": f.get("path")} for f in owner if f]
    return result


def forward_dependencies(index, path, *, include_reexport=True):
    """正向直接静态依赖（目标文件 + 证据）。"""
    deps = index["forward"].get(path, {})
    out = [{"path": target, "evidence": evid}
           for target, evid in sorted(deps.items())]
    return {"query_path": path, "dependencies": out,
            "note": "仅已验证静态解析关系；不代表函数运行时调用"}


def reverse_dependencies(index, path):
    """反向依赖：哪些文件导入并解析到目标模块。"""
    refs = index["reverse"].get(path, {})
    return {
        "query_path": path,
        "dependents": [{"path": src, "evidence": ev}
                       for src, ev in sorted(refs.items())],
        "note": "反向导入依赖不代表具体函数被调用",
    }


def multi_hop(index, src_path, dst_path, *, max_hops=DEFAULT_MAX_HOPS,
              max_visited=DEFAULT_MAX_VISITED, max_paths=DEFAULT_MAX_PATHS):
    """§5 有界多跳：BFS 文件级静态依赖路径，环检测 + 多候选 + 截断状态。"""
    meta = {"src": src_path, "dst": dst_path, "max_hops": max_hops,
            "max_visited": max_visited, "max_paths": max_paths,
            "visited": 0, "truncated": False}
    paths = []
    if src_path not in index["forward"] and src_path != dst_path:
        return {"status": "NOT_FOUND_IN_GRAPH", "paths": [], "meta": meta,
                "note": "起点无已验证静态依赖边；未发现路径不等于证实无依赖"}
    queue = deque([(src_path, [src_path], [])])
    seen_states = set()
    while queue and len(paths) < max_paths and meta["visited"] < max_visited:
        node, hops, edges = queue.popleft()
        meta["visited"] += 1
        if len(hops) - 1 >= max_hops:
            meta["truncated"] = True
            continue
        for target, evid in sorted(index["forward"].get(node, {}).items()):
            if target in hops:  # 环检测
                continue
            nhops = hops + [target]
            nedges = edges + [{"from": node, "to": target, "evidence": evid}]
            state = (target, tuple(nhops))
            if state in seen_states:
                continue
            seen_states.add(state)
            if target == dst_path:
                paths.append({"nodes": nhops, "edges": nedges,
                              "hops": len(nhops) - 1})
                if len(paths) >= max_paths:
                    meta["truncated"] = True
                continue
            queue.append((target, nhops, nedges))
    if queue:
        meta["truncated"] = True
    if paths:
        return {"status": "PATHS_FOUND", "paths": paths, "meta": meta}
    return {"status": "NO_PATH_FOUND", "paths": [], "meta": meta,
            "note": "在有界深度与已验证静态关系内未发现路径；不等于证实无依赖"}
