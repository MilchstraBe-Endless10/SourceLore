#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-C §3-§8：统一确定性深度问答（纯本地、零网络、只读）。

复用现有 knowledge_answer.answer() 的意图分类与正文/证据能力，
叠加 graph_query 的实体定位与图谱检索，输出统一结构化契约。

铁律：
  - 不接 LLM；确定性检索，宿主 Agent 负责组织自然语言。
  - 不写任何资产；只读派生图谱 code-graph.json 与已登记知识。
  - 不用 ok=true 代替知识成功；用 query_status + coverage 诚实表达。
  - 主来源身份保持用户指定 GitHub ID；补充来源单列，不合并身份。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

# 深层意图（在现有 6 类之上按关键词细分，未命中则沿用原 answer 意图）
_DEEP_PATTERNS = (
    ("reverse_dependency", re.compile(
        r"反向|被.*依赖|谁.*依赖|谁.*导入|导入并解析到|哪些文件.*(?:导入|依赖)|依赖.*我的|reverse depend|depended by|imported by", re.I)),
    ("multi_hop", re.compile(
        r"多跳|路径|几跳|经过|可达|reach|path.*between|how.*reach", re.I)),
    ("forward_dependency", re.compile(
        r"依赖|导入|import|module.*depend|静态依赖|正向", re.I)),
    ("symbol_lookup", re.compile(
        r"函数|类|符号|定义在哪|在哪定义|的位置|定义|定位|symbol|function|class", re.I)),
    ("supplement", re.compile(
        r"补充|附加来源|其他来源|supplement|另外的仓库", re.I)),
)


def detect_deep_intent(question: str) -> str:
    q = question or ""
    for intent, pat in _DEEP_PATTERNS:
        if pat.search(q):
            return intent
    return "general"


def _load_graph(data_root, repository_id, commit_sha):
    gp = (Path(data_root) / "派生视图" / str(repository_id) /
          str(commit_sha) / "code-graph.json")
    if not gp.exists():
        return None, str(gp)
    try:
        return json.loads(gp.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _entity_from_question(question):
    """从问句中保守抽取候选实体（路径 / specifier / 符号名）。"""
    q = (question or "").strip()
    candidates = []
    # 引号或反引号包裹
    for m in re.findall(r"[`\"']([^`\"']+)[`\"']", q):
        candidates.append(m.strip())
    # 明确路径 src/xxx 或 ./xxx
    for m in re.findall(r"[\w./-]+\.(?:py|js|jsx|ts|tsx|json)\b", q):
        candidates.append(m)
    for m in re.findall(r"\./[\w./-]+", q):
        candidates.append(m)
    # 限定/下划线标识符：renderComponent.parentDom、COMPONENT_DIRTY
    for m in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b", q):
        candidates.append(m)
    for m in re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", q):
        candidates.append(m)
    # 标识符候选：CamelCase 类型/类、snake_case 函数；作为保守符号查询候选
    for m in re.findall(r"\b[A-Z][A-Za-z0-9]{2,}\b", q):
        candidates.append(m)
    for m in re.findall(r"\b[a-z_][a-z0-9_]{2,}\b", q):
        candidates.append(m)
    # 去重的非空候选
    seen = []
    for c in candidates:
        if c and c not in seen:
            seen.append(c)
    return seen


def deep_answer(*, repository_id, question, data_root, commit_sha=None,
                store=None, max_hops=4, max_visited=5000, max_paths=50):
    """统一深度问答：正文 + 图谱实体/依赖/路径 + 证据联合。

    返回契约（复用现有 answer 字段，不另建数据模型）：
      ok / repository_id / commit_sha / intent / blocks /
      resolved_entities / graph_results / evidence_refs / graph_paths /
      supplement_sources / coverage / limitations / query_status /
      truncation / network_requests / wrote_assets
    """
    t0 = time.monotonic()
    import knowledge_answer as KA

    base = KA.answer(repository_id=repository_id, question=question,
                     data_root=data_root, store=store, commit_sha=commit_sha)
    result = dict(base)  # 保留全部原有字段，向后兼容
    result["ok"] = bool(base.get("ok"))
    result["intent"] = detect_deep_intent(question)
    result["base_intent"] = base.get("intent")
    result["resolved_entities"] = []
    result["graph_results"] = {}
    result["graph_paths"] = []
    result["evidence_refs"] = []
    result["limitations"] = []
    result["supplement_sources"] = list(base.get("supplement_sources") or [])
    result["supplement_relations"] = []
    result["network_requests"] = 0
    result["wrote_assets"] = 0

    if not result["ok"]:
        result["query_status"] = base.get("state") or "VERSION_NOT_FOUND"
        result["coverage"] = "NONE"
        result["truncation"] = {"applied": False}
        return result

    commit = base.get("commit_sha")
    graph, err = _load_graph(data_root, repository_id, commit)
    if graph is None:
        result["query_status"] = "GRAPH_NOT_AVAILABLE"
        result["coverage"] = "TEXT_ONLY"
        result["limitations"].append("图谱未生成或读取失败: " + (err or ""))
        result["truncation"] = {"applied": False}
        return result

    try:
        # graph_query 位于 views/，安装态与源码树 sys.path 不一定含该目录
        import sys as _sys
        _views = str(Path(__file__).resolve().parents[1] / "views")
        if _views not in _sys.path:
            _sys.path.insert(0, _views)
        import graph_query as GQ
        idx = GQ.build_index(graph)

        # §7：补充来源关系单列、保留 source_identity，不并入主图谱
        try:
            import sys as _s2
            _views2 = str(Path(__file__).resolve().parents[1] / "views")
            if _views2 not in _s2.path:
                _s2.path.insert(0, _views2)
            import repo_derive_runner as _DR
            _rels, _sups, _rmeta = _DR._relations_rows(
                repository_id, commit, data_root)
            result["supplement_relations"] = [
                {"source_identity": s.get("source_identity") or
                 s.get("repository_id"),
                 "relation_id": s.get("resolution_id") or s.get("fact_id"),
                 "source_ref": s.get("source_ref"),
                 "source_role": "verified_local_supplement"}
                for s in _sups]
        except Exception:
            pass  # 补充关系查询失败不影响主来源答案

        intent = result["intent"]
        entities = _entity_from_question(question)
        resolved = []
        for e in entities:
            r = GQ.resolve_entity(idx, e)
            if r["status"] != "NOT_FOUND_IN_GRAPH":
                resolved.append(r)
        result["resolved_entities"] = resolved

        if intent == "symbol_lookup":
            for r in resolved:
                for c in r["candidates"][:3]:
                    nid = c.get("node_id")
                    if nid:
                        result["graph_results"][nid] = GQ.node_query(idx, nid)
        elif intent == "forward_dependency":
            for r in resolved:
                for c in r["candidates"][:3]:
                    p = c.get("path")
                    if p:
                        result["graph_results"][p] = GQ.forward_dependencies(idx, p)
        elif intent == "reverse_dependency":
            for r in resolved:
                for c in r["candidates"][:3]:
                    p = c.get("path")
                    if p:
                        result["graph_results"][p] = GQ.reverse_dependencies(idx, p)
        elif intent == "multi_hop" and len(resolved) >= 2:
            src = next((c.get("path") for r in resolved
                        for c in r["candidates"] if c.get("path")), None)
            dst = next((c.get("path") for r in resolved[1:]
                        for c in r["candidates"] if c.get("path")), None)
            if src and dst and src != dst:
                hp = GQ.multi_hop(idx, src, dst, max_hops=max_hops,
                                  max_visited=max_visited, max_paths=max_paths)
                result["graph_results"]["multi_hop"] = hp
                result["graph_paths"] = hp.get("paths") or []
                result["truncation"] = hp.get("meta") or {}

        # 证据联合：收集正文 referenced + 图谱边 source_ref
        refs = []
        for b in base.get("blocks") or []:
            for ref in b.get("refs") or []:
                refs.append({"kind": "text", "ref": ref,
                             "source_role": b.get("source_role", "primary")})
        for gr in result["graph_results"].values():
            for d in (gr.get("dependencies") or gr.get("dependents") or []):
                for ev in (d.get("evidence") or [])[:3]:
                    for sr in ev.get("source_refs") or []:
                        if sr:
                            refs.append({"kind": "graph", "ref": sr,
                                         "source_role": "primary"})
        for hp in result["graph_paths"][:5]:
            for e in hp.get("edges") or []:
                for ev in (e.get("evidence") or []):
                    for sr in ev.get("source_refs") or []:
                        if sr:
                            refs.append({"kind": "graph_path", "ref": sr,
                                         "source_role": "primary"})
        # 去重
        seen, uniq = set(), []
        for r in refs:
            key = json.dumps(r, sort_keys=True, ensure_ascii=False, default=str)
            if key not in seen:
                seen.add(key); uniq.append(r)
        result["evidence_refs"] = uniq

        # query_status / coverage 诚实表达
        if any(r["status"] == "AMBIGUOUS" for r in resolved):
            result["query_status"] = "ENTITY_AMBIGUOUS"
        elif not resolved and intent != "general":
            result["query_status"] = "ENTITY_NOT_LOCATED"
        elif result["graph_paths"]:
            result["query_status"] = "ANSWERED_WITH_GRAPH_PATHS"
        elif result["graph_results"]:
            result["query_status"] = "ANSWERED_WITH_GRAPH"
        else:
            result["query_status"] = "ANSWERED_TEXT_ONLY"
        result["coverage"] = ("GRAPH+TEXT" if result["graph_results"]
                              else "TEXT_ONLY")
        result["truncation"] = result.get("truncation") or {"applied": False}
        result.setdefault("limitations", []).append(
            "静态关系不代表函数运行时调用；未发现路径不等于证实无依赖")
        result["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        return result
    except Exception as e:
        result["query_status"] = "QUERY_ERROR"
        result["coverage"] = "TEXT_ONLY"
        result["limitations"].append("图谱查询失败: " + f"{type(e).__name__}: {e}")
        result["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
        return result


def answer_deep(*args, **kwargs):
    """供 CLI 调用的别名。"""
    return deep_answer(*args, **kwargs)
