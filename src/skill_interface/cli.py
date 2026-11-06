#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore Skill 统一 CLI。

★ stdout=结构化 JSON；stderr=错误；退出码真实。
"""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paths  # noqa: E402
paths.ensure_import_path()

from result import (emit_ok, emit_error, SkillError,  # noqa: E402
                    EXIT_USAGE, EXIT_OK)


def build_parser():
    p = argparse.ArgumentParser(
        prog="sourcelore",
        description="SourceLore GitHub 知识库 Skill（只读知识，不做模型推断）")
    p.add_argument("--data-root", default=None,
                   help="知识库数据根目录（默认 $SOURCELORE_DATA_ROOT 或 ~/.sourcelore）")
    p.add_argument("--version", action="store_true", help="显示 Skill 版本")
    sub = p.add_subparsers(dest="cmd", required=False)

    sub.add_parser("status", help="运行状态")
    sub.add_parser("repositories", help="列出已登记仓库")
    sub.add_parser("help", help="显示帮助")

    a = sub.add_parser("analyze", help="分析 GitHub 仓库并建立/复用知识资产")
    a.add_argument("url", help="https://github.com/<owner>/<repo>")
    a.add_argument("--ref", default=None, help="分支/标签/Commit（默认 HEAD）")
    a.add_argument("--path", default="README", help="要观察的路径")
    a.add_argument("--max-requests", type=int, default=40, help="GitHub 请求上限")
    a.add_argument("--commit", default=None, help="固定 Commit SHA（优先复用本地缓存）")
    a.add_argument("--offline", action="store_true", help="禁用一切 GitHub 请求")
    a.add_argument("--refresh", action="store_true", help="显式要求重新获取远程版本")
    a.add_argument("--no-token", action="store_true",
                   help="本次不使用 GITHUB_TOKEN（即便环境里有）")
    a.add_argument("--license-known", action="store_true",
                   help="声明该仓库有明确授权依据（内部采集用）；默认不声明")
    a.add_argument("--include-content", action="store_true",
                   help="对已保存快照做内容级抽取（读 Blob；无字节则明确报告）")
    a.add_argument("--content-status", action="store_true",
                   help="只报内容可用性，不采集、不联网")
    a.add_argument("--plan", action="store_true",
                   help="只读计划：盘点缺口并估算请求，不联网、不写资产")
    a.add_argument("--resume", action="store_true",
                   help="续跑：只补齐缺失内容，已完成的直接复用")
    a.add_argument("--request-limit", type=int, default=None,
                   help="本次采集最多发出的 GitHub 请求数（默认 8）")
    a.add_argument("--reserve-requests", type=int, default=None,
                   help="优先保留的主配额（默认 5）")
    a.add_argument("--content-path", action="append", default=None,
                   help="限定内容抽取的路径（可重复）")

    i = sub.add_parser("inspect", help="查看单仓库知识摘要")
    i.add_argument("repository_id")
    i.add_argument("--content-summary", action="store_true",
                   help="附带内容级知识概览（Blob 数/可解析数/事实数）")

    h = sub.add_parser("history", help="查看已登记历史版本")
    h.add_argument("repository_id")

    q = sub.add_parser("query", help="查询已有知识（不重采集）")
    q.add_argument("repository_id")
    q.add_argument("--commit", default=None,
                   help="固定 Commit（content 类型必需）")
    q.add_argument("--type", default="path",
                   choices=["path", "claims", "version", "content", "code",
                            "relation", "project"])
    q.add_argument("--path", default=None)
    q.add_argument("--compare-commit", default=None)
    q.add_argument("--max-results", type=int, default=50)
    q.add_argument("--symbol", default=None, help="按符号 qualified_name 或 name 查")
    q.add_argument("--symbol-kind", default=None, help="按符号类型过滤")
    q.add_argument("--module", default=None, help="按静态导入模块名过滤")
    q.add_argument("--language", default=None,
                   help="按源码语言过滤（python/javascript/typescript/jsx/tsx）")
    q.add_argument("--relation", default=None,
                   help="关系查询：imports（配合 --type relation）")
    q.add_argument("--show-resolution", action="store_true",
                   help="显示解析状态与配置细节")
    q.add_argument("--config", default=None, help="按 tsconfig 路径过滤")
    q.add_argument("--file", default=None, help="按源码文件路径过滤归属")

    c = sub.add_parser("card", help="生成知识卡片（本地 HTML）")
    c.add_argument("--repository-id", required=True)
    c.add_argument("--claim-id", default=None)
    c.add_argument("--verification-id", default=None)
    # F2-P5F：内容知识卡片
    c.add_argument("--content-fact-id", default=None)
    c.add_argument("--content-claim-id", default=None)
    c.add_argument("--commit", default=None)
    c.add_argument("--path", default=None)
    c.add_argument("--code", action="store_true",
                   help="生成源码结构卡片")

    return p


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        if e.code == 0:
            return EXIT_OK
        return EXIT_USAGE

    if args.version:
        return emit_ok({"ok": True, "skill_version": paths.SKILL_VERSION})

    cmd = getattr(args, "cmd", None)
    if cmd in (None, "help"):
        parser.print_help(sys.stderr)
        return emit_ok({"ok": True, "usage": parser.format_usage().strip()})

    try:
        return _dispatch(cmd, args)
    except SkillError as e:
        return emit_error(e)
    except Exception as e:                       # ★ 不吞底层错误
        tb = traceback.format_exc()
        return emit_error(SkillError(
            f"{type(e).__name__}: {e}", code="INTERNAL_ERROR",
            detail={"traceback_tail": tb.strip().splitlines()[-3:]}))


def _dispatch(cmd, args):
    root = args.data_root

    if cmd == "status":
        import status as S
        return emit_ok(S.status(root))

    if cmd == "repositories":
        import knowledge as K
        store = K.open_store(root)
        try:
            return emit_ok(K.list_repositories(store))
        finally:
            store.close()

    if cmd == "inspect":
        import knowledge as K
        store = K.open_store(root)
        try:
            res = K.inspect_repository(store, args.repository_id)
            if getattr(args, "content_summary", False):
                # ★ F2-P5F：改用持久化内容知识概览（计数口径分离）
                import content_knowledge_query as CKQ
                res["content_summary"] = CKQ.content_knowledge_summary(
                    repository_id=args.repository_id,
                    commit_sha=(res.get("commits") or [None])[0],
                    data_root=root)
            return emit_ok(res)
        finally:
            store.close()

    if cmd == "history":
        import knowledge as K
        store = K.open_store(root)
        try:
            return emit_ok(K.history(store, args.repository_id))
        finally:
            store.close()

    if cmd == "analyze":
        # ★ D-60：--resume 原本只在 argparse 里定义了，函数体零引用
        #   （和 D-46 同一类"声明式空参数"）。现在接到真实恢复盘点。
        if getattr(args, "resume", False):
            import capture_resume_report as CRR
            return emit_ok(CRR.inventory(
                data_root=root,
                repository_id=getattr(args, "repository_id", None),
                commit=getattr(args, "commit", None),
                url=args.url,
                content_paths=getattr(args, "content_path", None)))

        # --plan 只读：不采集、不写资产、不改 A/B 层
        if getattr(args, "plan", False):
            return emit_ok(_run_capture_plan(
                data_root=root,
                repository_id=getattr(args, "repository_id", None),
                commit=getattr(args, "commit", None),
                content_paths=getattr(args, "content_path", None),
                request_limit=getattr(args, "request_limit", None),
                reserve=getattr(args, "reserve_requests", None)))

        import analyze as A
        import status as S
        out = A.analyze(url=args.url, ref=args.ref, data_root=root,
                        target_path=args.path,
                        max_requests=args.max_requests,
                        commit=getattr(args, "commit", None),
                        offline=getattr(args, "offline", False),
                        refresh=getattr(args, "refresh", False),
                        use_token=not getattr(args, "no_token", False))
        S.record_operation("analyze", out)
        if (getattr(args, "include_content", False)
                or getattr(args, "content_status", False)):
            import content_capture as CC
            status_only = (getattr(args, "content_status", False)
                           and not getattr(args, "include_content", False))
            src_url = args.url
            parts = src_url.rstrip("/").split("/")
            owner = parts[-2] if len(parts) >= 2 else None
            repo = parts[-1] if parts else None
            # ★ F2-P6F：正式 CLI 必须走全局预算预检 + 编排器，
            #   不允许绕过预检直接采集（此前 cap 只在采集内部生效）。
            _budget = _preflight_budget(
                root=root,
                repository_id=out["repository_id"],
                commit_sha=out["commit_sha"],
                content_paths=args.content_path,
                request_limit=getattr(args, "request_limit", None),
                reserve=getattr(args, "reserve_requests", None),
                offline=bool(getattr(args, "offline", False)) or status_only,
                dry_run=status_only)
            out["budget_preflight"] = _budget["preflight"]
            if not _budget["preflight"].get("can_begin") and not status_only:
                # 预检不过 → 不采集，但已完成资产仍可查询
                out["content"] = {
                    "results": [], "network_requests": 0,
                    "blocked_by_preflight": True,
                    "reason": _budget["preflight"].get("block_reason")}
            else:
                out["content"] = CC.capture(
                    repository_id=out["repository_id"],
                    commit_sha=out["commit_sha"], data_root=root,
                    paths=args.content_path, owner=owner, repo=repo,
                    license_known=getattr(args, "license_known", False),
                    offline=bool(getattr(args, "offline", False)) or status_only,
                    dry_run=status_only,
                    budget=_budget["budget"])
        # ★ D-51：GitHub 路径原本只捕获字节、不抽取知识。
        #   把已捕获字节交给同一条抽取链路（不新增解析器、不联网）。
        # status_only 只在 include-content 分支内定义；此处用安全取值
        _status_only = bool(getattr(args, "content_status", False)
                            and not getattr(args, "include_content", False))
        if not _status_only:
            try:
                import github_knowledge_extract as GKE
                from knowledge_store import KnowledgeStore as _KS
                from paths import db_path as _db_path
                _ks = _KS(str(_db_path(root)), create=False)
                try:
                    out["knowledge_extraction"] = GKE.extract_captured(
                        store=_ks, data_root=root,
                        repository_id=out["repository_id"],
                        commit_sha=out["commit_sha"],
                        content_report=out.get("content") or {},
                        paths=args.content_path)
                finally:
                    _ks.close()
            except Exception as e:
                out["knowledge_extraction"] = {
                    "ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        return emit_ok(out)

    if cmd == "query":
        if getattr(args, "type", None) == "project":
            import ts_project_knowledge as TK
            if getattr(args, "file", None) and not getattr(args, "config", None):
                return emit_ok(TK.query_membership(
                    repository_id=args.repository_id,
                    file_path=args.file, commit_sha=args.commit,
                    data_root=root))
            return emit_ok(TK.query_projects(
                repository_id=args.repository_id, commit_sha=args.commit,
                config_path=getattr(args, "config", None),
                show_references=bool(getattr(args, "show_resolution", False)),
                data_root=root))
        if getattr(args, "type", None) == "relation":
            import source_knowledge as SK
            return emit_ok(SK.query_module_relations(
                repository_id=args.repository_id, commit_sha=args.commit,
                importing_file_path=args.path,
                module_specifier=getattr(args, "module", None), data_root=root))
        if getattr(args, "type", None) == "code":
            import source_knowledge as SK
            return emit_ok(SK.query_code(
                repository_id=args.repository_id, commit_sha=args.commit,
                file_path=args.path,
                symbol_name=getattr(args, "symbol", None),
                symbol_kind=getattr(args, "symbol_kind", None),
                module_name=getattr(args, "module", None),
                data_root=root))
        if getattr(args, "type", None) == "content":
            # ★ 必须用专属名：content_query 已被 P5C 的同名模块占用
            import content_knowledge_query as CQ
            if not args.commit:
                raise SkillError("content 查询需要 --commit",
                                 code="MISSING_COMMIT", exit_code=EXIT_USAGE)
            return emit_ok(CQ.content_query(
                repository_id=args.repository_id, commit_sha=args.commit,
                file_path=args.path, data_root=root))
        import query as Q
        import status as S
        out = Q.run_query(repository_id=args.repository_id,
                          commit_sha=args.commit, qtype=args.type,
                          path=args.path,
                          compare_commit=args.compare_commit,
                          max_results=args.max_results, data_root=root)
        S.record_operation("query", out)
        return emit_ok(out)

    if cmd == "card":
        has_content = any(getattr(args, k, None) for k in
                          ("content_fact_id", "content_claim_id"))
        if getattr(args, "code", False):
            import source_knowledge as SK
            return emit_ok(SK.render_source_card(
                repository_id=args.repository_id,
                commit_sha=getattr(args, "commit", None),
                file_path=getattr(args, "path", None), data_root=root))
        if has_content or (getattr(args, "path", None)
                           and getattr(args, "commit", None)):
            import content_card as CCARD
            return emit_ok(CCARD.render_content_card(
                repository_id=args.repository_id,
                commit_sha=args.commit, file_path=args.path,
                content_fact_id=getattr(args, "content_fact_id", None),
                content_claim_id=getattr(args, "content_claim_id", None),
                data_root=root))
        import render as R
        out = R.render_card(claim_id=args.claim_id,
                            verification_id=args.verification_id,
                            repository_id=args.repository_id, data_root=root)
        return emit_ok(out)

    raise SkillError(f"未知命令：{cmd}", code="UNKNOWN_COMMAND",
                     exit_code=EXIT_USAGE)


if __name__ == "__main__":
    sys.exit(main())



def _preflight_budget(*, root, repository_id, commit_sha, content_paths,
                      request_limit, reserve, offline, dry_run):
    """★ F2-P6F：统一预算预检。

    正式 CLI 的远程采集必须经过这里：
    先建请求 DAG → 盘点本地已有资产（标 LOCAL_REUSE）→ 取权威响应头 → 三条件判定。
    """
    import acceptance_request_planner as ARP
    import request_budget as RB

    limit = int(request_limit or ARP.DEFAULT_LOCAL_MAX)
    reserve_val = int(reserve if reserve is not None else ARP.DEFAULT_RESERVE)

    budget = RB.GitHubRequestBudget(
        repository_id=str(repository_id), commit_sha=str(commit_sha),
        execution_id="cli-%s" % str(commit_sha)[:8],
        request_limit=limit, reserve_requests=reserve_val)

    if offline or dry_run:
        return {"budget": budget,
                "preflight": {"can_begin": not dry_run and not offline,
                              "block_reason": "OFFLINE_NO_REQUESTS" if offline
                              else "DRY_RUN",
                              "planned_primary_requests": 0,
                              "note": "不发起网络请求"}}

    # 盘点本地已完整资产 → 标 LOCAL_REUSE
    have = []
    try:
        from knowledge_store import KnowledgeStore
        import content_ingest_coordinator as CIC
        from paths import db_path as _dbp
        ks = KnowledgeStore(str(_dbp(root)), create=False)
        try:
            for fp in (content_paths or []):
                m = CIC.find_content_asset(ks, repository_id=str(repository_id),
                                           commit_sha=str(commit_sha),
                                           file_path=fp)
                if m and (m.get("completeness_status") or "").upper() == "COMPLETE":
                    have.append(fp)
        finally:
            ks.close()
    except Exception:
        pass

    plan = ARP.build_repo_acceptance_plan(
        repository_id=repository_id, commit_sha=commit_sha,
        target_paths=tuple(content_paths or ()), license_path=None,
        local_max_requests=limit, reserve_requests=reserve_val,
        have_metadata=True, have_tree=True, have_blobs=tuple(have))

    # 取权威响应头：至多一次 bootstrap
    observed = None
    try:
        import acceptance_execution_coordinator as EC
        coord = EC.Coordinator(budget=budget)
        boot = coord.bootstrap_rate_limit()
        observed = boot.get("observed_remaining")
        pre = ARP.preflight(plan=plan, observed_remaining=observed,
                            observed_reset_at=boot.get("reset_at"),
                            observed_resource=boot.get("resource"),
                            rate_limit_status=budget.rate_limit_kind,
                            bootstrap_used=True)
        pre["reused_paths"] = list(have)
        return {"budget": budget, "preflight": pre}
    except Exception as e:
        pre = ARP.preflight(plan=plan, observed_remaining=None, bootstrap_used=True)
        pre["error"] = "%s: %s" % (type(e).__name__, e)
        return {"budget": budget, "preflight": pre}


def _run_capture_plan(*, data_root, repository_id, commit, content_paths,
                      request_limit=None, reserve=None):
    """只读缺口盘点。绝不联网、绝不写库。"""
    import capture_request_plan as PLAN
    import request_budget as RB
    from knowledge_store import KnowledgeStore
    from paths import db_path, guard_inside_project_db

    p = db_path(data_root)
    guard_inside_project_db(p)
    if not p.exists():
        raise SkillError("知识库未建立", code="KNOWLEDGE_DB_MISSING", exit_code=3)

    store = KnowledgeStore(str(p), create=False)
    try:
        if repository_id is None:
            rows = store.conn.execute(
                "SELECT DISTINCT repository_id FROM index_rows "
                "WHERE asset_type='repository_snapshot'").fetchall()
            if len(rows) != 1:
                raise SkillError(
                    "存在多个仓库，请显式指定 --repository-id",
                    code="AMBIGUOUS_REPOSITORY", exit_code=3,
                    detail={"candidates": [r["repository_id"] for r in rows]})
            repository_id = rows[0]["repository_id"]

        commit_sha = commit or _latest_commit(store, repository_id)
        inv = PLAN.build_gap_inventory(
            store=store, repository_id=repository_id, commit_sha=commit_sha,
            content_scope=content_paths or PLAN.DEFAULT_CONTENT_SCOPE)
        if not inv.get("ok"):
            raise SkillError("快照不存在：%s" % inv.get("error"),
                             code=inv.get("error"), exit_code=3)

        budget = RB.GitHubRequestBudget(
            repository_id=repository_id, commit_sha=inv["commit_sha"],
            execution_id="plan",
            request_limit=(request_limit if request_limit is not None
                           else RB.DEFAULT_REQUEST_LIMIT),
            reserve_requests=(reserve if reserve is not None
                              else RB.DEFAULT_RESERVE))
        plan = PLAN.build_request_plan(inventory=inv, budget=budget)
        plan["network_requests"] = 0
        plan["wrote_assets"] = 0
        plan["inventory"] = inv
        return plan
    finally:
        store.close()


def _latest_commit(store, repository_id):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='repository_snapshot' "
        "AND repository_id=?", (str(repository_id),)).fetchall()
    best = None
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if not got.get("ok"):
            continue
        c = ((got["asset"] or {}).get("payload") or {}).get("commit_sha")
        if c and (best is None or str(c) > str(best)):
            best = c
    if best is None:
        raise SkillError("该仓库没有快照", code="SNAPSHOT_NOT_FOUND", exit_code=3)
    return best
