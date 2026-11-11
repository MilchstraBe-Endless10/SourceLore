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


def _load_assets(store, repository_id):
    """读某仓库的权威资产。"""
    snap_row = store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type='repository_snapshot' "
        "AND repository_id=? ORDER BY created_at DESC LIMIT 1",
        (str(repository_id),)).fetchone()
    if not snap_row:
        return None
    snapshot = json.loads(snap_row["payload_json"])

    claims = [json.loads(r["payload_json"]) for r in store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type='claim_candidate' "
        "AND repository_id=?", (str(repository_id),)).fetchall()]

    verifs = [json.loads(r["payload_json"]) for r in store.conn.execute(
        "SELECT payload_json FROM assets WHERE asset_type='claim_verification' "
        "AND repository_id=?", (str(repository_id),)).fetchall()]

    return snapshot, claims, verifs


def _code_rows(repository_id, commit_sha, data_root):
    """取源码结构观察（符号声明 / import / export）。

    ★ 这是 2026-11-11 审计发现的缺口：derive 时必须真的把代码观察喂给图谱，
      否则 IMPORTS/DECLARES 边永远为空，模块文档会写成「无源码观察」——
      而库里明明有 13 条 re-export 观察。
    """
    try:
        import query as Q
        r = Q.run_query(repository_id=str(repository_id), commit_sha=commit_sha,
                        qtype="code", max_results=500, data_root=data_root)
        return r.get("claims") or []
    except Exception:
        return []


def derive_one(*, repository_id, data_root, store=None, logger=None):
    """为单仓库生成派生视图 + 项目文档。返回结果摘要。"""
    from knowledge_store import KnowledgeStore
    from paths import db_path
    import repo_graph_derivation as RG
    import repo_card_projection as CP
    import repo_miner as RM          # 真实项目知识的挖掘层

    own_store = False
    if store is None:
        store = KnowledgeStore(str(db_path(data_root)), create=False)
        own_store = True

    try:
        loaded = _load_assets(store, repository_id)
        if not loaded:
            return {"ok": False, "error": "NO_SNAPSHOT",
                    "repository_id": str(repository_id)}
        snapshot, claims, verifs = loaded
        commit_sha = snapshot.get("commit_sha")

        tree_entries = snapshot.get("tree_entries") or []
        tree_coverage = [{
            "commit_sha": commit_sha,
            "completeness_status": snapshot.get("completeness_status"),
            "tree_entry_count": snapshot.get("tree_entry_count"),
            "snapshot_asset_id": snapshot.get("snapshot_asset_id"),
        }]

        # ★ 代码观察必须真的取到并喂给图谱
        code_rows = _code_rows(repository_id, commit_sha, data_root)

        graph = RG.derive_repo_graph(
            repository_id=str(repository_id), commit_sha=commit_sha,
            tree_entries=tree_entries, claim_rows=claims,
            tree_coverage=tree_coverage, code_rows=code_rows,
            verifications=verifs)

        # 项目知识挖掘（README / Manifest / 符号 → 可读文档）
        mined = RM.mine_project_knowledge(
            store=store, repository_id=str(repository_id),
            commit_sha=commit_sha, tree_entries=tree_entries,
            code_rows=code_rows, claims=claims, verifications=verifs)

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
            "code_rows": len(code_rows),
            "documents": len(card["documents"]),
            "nodes": len(graph.get("nodes") or []),
            "edges": len(graph.get("edges") or []),
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
