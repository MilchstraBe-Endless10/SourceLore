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

    i = sub.add_parser("inspect", help="查看单仓库知识摘要")
    i.add_argument("repository_id")

    h = sub.add_parser("history", help="查看已登记历史版本")
    h.add_argument("repository_id")

    q = sub.add_parser("query", help="查询已有知识（不重采集）")
    q.add_argument("repository_id")
    q.add_argument("--commit", required=True)
    q.add_argument("--type", default="path", choices=["path", "claims", "version"])
    q.add_argument("--path", default=None)
    q.add_argument("--compare-commit", default=None)
    q.add_argument("--max-results", type=int, default=50)

    c = sub.add_parser("card", help="生成知识卡片（本地 HTML）")
    c.add_argument("--repository-id", required=True)
    c.add_argument("--claim-id", default=None)
    c.add_argument("--verification-id", default=None)

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
            return emit_ok(K.inspect_repository(store, args.repository_id))
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
        return emit_ok(out)

    if cmd == "query":
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
        import render as R
        out = R.render_card(claim_id=args.claim_id,
                            verification_id=args.verification_id,
                            repository_id=args.repository_id, data_root=root)
        return emit_ok(out)

    raise SkillError(f"未知命令：{cmd}", code="UNKNOWN_COMMAND",
                     exit_code=EXIT_USAGE)


if __name__ == "__main__":
    sys.exit(main())
