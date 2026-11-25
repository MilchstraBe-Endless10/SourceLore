"""把派生视图生成固化为可复现命令（替代一次性脚本）。

★ 为什么必须存在：
  2026-11-10 的派生视图是用临时 `python3 - <<PY` 脚本生成的，
  不在源码里、无入口、无测试、不可复现。本模块把它变成 `sourcelore derive <rid>`。

★ 数据来源全部是已登记的权威资产，不重新采集、不联网：
  - repository_snapshot.payload.tree_entries  → 文件树
  - claim_candidate                           → 命题
  - claim_verification.payload.fact_ids       → 真实证据（★ 证据不在这 claim 上）
  - query --type code 的结果                   → 符号与导入（code_rows）
"""

import json
import os

DOC_NAMES = (
    "project-overview.md",
    "file-structure.md",
    "module-dependencies.md",
    "claim-network.md",
    "evidence-index.md",
)

# 源码事实有界读取上限：不靠固定 500 冒充完整图谱，超限如实标注。
SOURCE_FACT_PAGE_SIZE = 1000


def _load_assets(store, repository_id, commit_sha=None):
    """读某仓库**指定 Commit**的权威资产（P2-B §2 固定 Commit 隔离）。

    兼容旧调用：仍返回 (snapshot, claims, verifs) 三元组；
    版本选择/过滤结果挂在返回的第一个元素之外的旁路属性不可能（tuple），
    因此额外提供 `_load_assets_ex()` 返回完整 meta。
    """
    ex = _load_assets_ex(store, repository_id, commit_sha)
    if not ex.get("ok"):
        return None
    return ex["snapshot"], ex["claims"], ex["verifications"]


def _load_assets_ex(store, repository_id, commit_sha=None):
    """完整版：带版本选择/覆盖 meta，供 derive/answer 精确使用。"""
    import versioned_assets as VA
    ex = VA.load_versioned_assets(store, repository_id, commit_sha)
    if ex.get("ok"):
        ex["snapshot"]["_selection"] = ex["selection"]
        ex["snapshot"]["_coverage"] = ex["coverage"]
    return ex


def _code_rows(repository_id, commit_sha, data_root, *, max_results=SOURCE_FACT_PAGE_SIZE):
    """取源码结构观察（符号声明 / import / export）。

    ★ P2-B §4 修复：旧实现调用 `query.run_query(qtype="code")`，而 run_query
      的 VALID_TYPES 只有 path/claims/version —— 该调用永远抛异常被 except 吞掉，
      code_rows 恒为空，图谱符号/导入边因此为空。改用正式源码知识入口
      `source_knowledge.query_code()`，它读取已登记的 AST/source_facts。

    返回 (rows, meta)。rows 元素带 `kind` 兼容下游 claim_rows 结构；
    meta 如实记录读取上限、总数与是否被截断。
    """
    meta = {"source": "source_knowledge.query_code", "commit_sha": commit_sha,
            "requested_limit": max_results, "truncated": False}
    try:
        import source_knowledge as SK
        r = SK.query_code(repository_id=str(repository_id), commit_sha=commit_sha,
                          data_root=data_root)
        facts = r.get("facts") or []
        meta["facts_total"] = len(facts)
        if len(facts) > max_results:
            facts = facts[:max_results]
            meta["truncated"] = True
        # 保留完整 source_fact 字段，补 kind/subject 兼容下游 old claim_rows 口径
        rows = []
        for f in facts:
            row = dict(f)
            subj = f.get("subject") or {}
            rule = f.get("rule_id") or ""
            # 统一符号读取契约：导入用 module_specifier，导出用 source_reference
            ref = subj.get("source_reference") or subj.get("module_specifier")
            if ref:
                subj = dict(subj)
                subj["source_reference"] = ref
            if "IMPORT" in rule:
                row["kind"] = "import"
            elif "EXPORT" in rule:
                row["kind"] = "export"
            elif "SYMBOL" in rule:
                row["kind"] = "symbol"
            else:
                row["kind"] = "symbol"
            row["subject"] = subj
            rows.append(row)
        meta["facts_returned"] = len(rows)
        meta["state"] = r.get("state")
        meta["coverage_status"] = r.get("coverage_status")
        return rows, meta
    except Exception as e:
        meta["error"] = f"{type(e).__name__}: {e}"
        return [], meta


def _relations_rows(repository_id, commit_sha, data_root):
    """P2-B §5：读取 P2-A 已登记的静态模块关系（只读、零网络）。"""
    meta = {"source": "source_knowledge.query_module_relations",
            "commit_sha": commit_sha}
    try:
        import source_knowledge as SK
        q = SK.query_module_relations(repository_id=str(repository_id),
                                      commit_sha=commit_sha, data_root=data_root,
                                      include_supplements=False)
        meta.update({"state": q.get("state"), "status": q.get("status"),
                     "status_counts": q.get("status_counts") or {},
                     "counts": q.get("counts") or {}})
        return q.get("relations") or [], meta
    except Exception as e:
        meta["error"] = f"{type(e).__name__}: {e}"
        return [], meta


def derive_one(*, repository_id, data_root, store=None, logger=None,
               commit_sha=None):
    """为单仓库生成派生视图 + 项目文档。返回结果摘要。

    commit_sha 给定则严格派生该固定版本（P2-B §2）；未给则走 current_view。
    """
    from knowledge_store import KnowledgeStore
    from paths import db_path
    import os as _os
    # ★ 源码/关系读取入口在 src/skill_interface，运行时注入模块路径
    for _sub in ("skill_interface", "trust"):
        _p = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), _sub)
        if _p not in __import__("sys").path:
            __import__("sys").path.insert(0, _p)
    import repo_graph_derivation as RG
    import repo_card_projection as CP
    import repo_miner as RM          # 真实项目知识的挖掘层

    own_store = False
    if store is None:
        store = KnowledgeStore(str(db_path(data_root)), create=False)
        own_store = True

    try:
        ex = _load_assets_ex(store, repository_id, commit_sha)
        if not ex.get("ok"):
            return {"ok": False, "error": ex.get("reason", "NO_SNAPSHOT"),
                    "selection": ex.get("selection"),
                    "repository_id": str(repository_id)}
        snapshot, claims, verifs = ex["snapshot"], ex["claims"], ex["verifications"]
        commit_sha = ex["commit_sha"]

        tree_entries = snapshot.get("tree_entries") or []
        tree_coverage = [{
            "commit_sha": commit_sha,
            "completeness_status": snapshot.get("completeness_status"),
            "tree_entry_count": snapshot.get("tree_entry_count"),
            "snapshot_asset_id": snapshot.get("snapshot_asset_id"),
        }]

        # ★ 代码观察必须真的取到并喂给图谱（P2-B §4 正式入口 + 有界读取）
        code_rows, symbol_meta = _code_rows(repository_id, commit_sha, data_root)

        # ★ P2-B §5：读取 P2-A 已登记静态关系（只读、零网络）
        relations, relation_meta = _relations_rows(repository_id, commit_sha, data_root)

        graph = RG.derive_repo_graph(
            repository_id=str(repository_id), commit_sha=commit_sha,
            tree_entries=tree_entries, claim_rows=claims,
            tree_coverage=tree_coverage, code_rows=code_rows,
            verifications=verifs, relations=relations,
            symbol_meta=symbol_meta, relation_meta=relation_meta)

        # 项目知识挖掘（README / Manifest / 符号 → 可读文档）
        mined = RM.mine_project_knowledge(
            store=store, repository_id=str(repository_id),
            commit_sha=commit_sha, tree_entries=tree_entries,
            code_rows=code_rows, claims=claims, verifications=verifs,
            data_root=data_root)

        repo_name = None
        try:
            import bot_card as BCARD
            repo_name = BCARD.lookup_repo_name(store, str(repository_id))
        except Exception:
            repo_name = None

        card = CP.build_card_data(
            repository_id=str(repository_id), repository_name=repo_name,
            commit_sha=commit_sha, graph=graph, claims=claims, verifications=verifs)
        # ★ 把挖掘出的项目知识正文挂进卡片数据（卡片据此渲染全文）
        card["documents"] = mined.get("documents") or []
        card["project"] = mined.get("project") or {}

        written = CP.write_derived_views(
            data_root=data_root, repository_id=str(repository_id),
            commit_sha=commit_sha, card=card, graph=graph,
            documents=mined.get("documents") or [])

        return {
            "ok": True,
            "repository_id": str(repository_id),
            "commit_sha": commit_sha,
            "selection": ex["selection"],
            "code_rows": len(code_rows),
            "symbol_meta": symbol_meta,
            "relation_meta": relation_meta,
            "documents": len(card["documents"]),
            "nodes": len(graph.get("nodes") or []),
            "edges": len(graph.get("edges") or []),
            "graph_digest": graph.get("graph_digest"),
            "written": written,
            "tree_status": (graph.get("completeness") or {}).get("tree_status"),
        }

    finally:
        if own_store:
            try:
                store.close()
            except Exception:
                pass


def derive_all(*, data_root, logger=None):
    """对库里所有仓库生成派生视图。"""
    from knowledge_store import KnowledgeStore
    from paths import db_path

    store = KnowledgeStore(str(db_path(data_root)), create=False)
    try:
        rows = store.conn.execute(
            "SELECT DISTINCT repository_id FROM assets "
            "WHERE asset_type='repository_snapshot'").fetchall()
        rids = [r["repository_id"] for r in rows]
    finally:
        store.close()

    results = []
    for rid in rids:
        try:
            results.append(derive_one(repository_id=rid, data_root=data_root))
        except Exception as e:
            results.append({"ok": False, "repository_id": str(rid),
                            "error": f"{type(e).__name__}: {e}"})
    return results
