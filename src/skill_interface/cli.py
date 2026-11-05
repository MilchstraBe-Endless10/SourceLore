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
                   choices=["path", "claims", "version", "content", "code"])
    q.add_argument("--path", default=None)
    q.add_argument("--compare-commit", default=None)
    q.add_argument("--max-results", type=int, default=50)
    q.add_argument("--symbol", default=None, help="按符号 qualified_name 或 name 查")
    q.add_argument("--symbol-kind", default=None, help="按符号类型过滤")
    q.add_argument("--module", default=None, help="按静态导入模块名过滤")

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
            out["content"] = CC.capture(
                repository_id=out["repository_id"],
                commit_sha=out["commit_sha"], data_root=root,
                paths=args.content_path, owner=owner, repo=repo,
                license_known=getattr(args, "license_known", False),
                offline=bool(getattr(args, "offline", False)) or status_only,
                dry_run=status_only)
        return emit_ok(out)

    if cmd == "query":
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
