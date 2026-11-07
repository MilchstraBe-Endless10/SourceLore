#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把源码知识写成 Obsidian 笔记：一条知识 = 一张卡片 = 一个带双向链接的 .md。

★ 设计依据（已查证，非自造）：
  1. Zettelkasten（卢曼卡片盒，见 sspai.com/post/60802）的核心不是分类，
     是**建立连接**：每条永久笔记（Permanent Note）只讲一件事，
     并用 [[双向链接]] 挂到已有笔记上。因此这里**一条事实一个文件**，
     不按仓库/文件做层级目录 —— 目录是僵硬结构，会杀死联想。
  2. 命名必须**稳定且可预测**，否则链接会碎。用固定前缀 + 语义键，
     不用序号、不用时间戳。

★ 三类笔记（对应 Zettelkasten 的三个层次）：
  - 主体笔记  `SL-<repo>/<file>/<symbol>`   一个符号/导出
  - 文件笔记  `SL-<repo>/<file>`            该文件的入口，链到所有符号
  - 仓库笔记  `SL-<repo>`                   仓库入口，链到所有文件
  双向链接是 Obsidian 自动建立的：只要 A 的正文里出现 [[B]]，
  B 的 Backlinks 面板就会显示 A，无需另写反向链接。
"""

import re
from pathlib import Path


def _slug(s):
    """Obsidian 文件名安全化。保留 `/` 作为子目录分隔，其余非法字符转 `-`。"""
    s = str(s or "").strip()
    s = re.sub(r'[\\:*?"<>|#^\[\]]', "-", s)
    s = re.sub(r"\s+", "-", s)
    return s or "untitled"


STATE_ZH = {
    "SUPPORTED_SOURCE_CLAIM": "已验证·命题成立",
    "OBSERVED_SOURCE_FACT": "已观察·尚未验证",
    "INSUFFICIENT_EVIDENCE": "证据不足",
    "UNSUPPORTED_SEMANTIC_FORM": "该语义形式不支持",
    "NOT_ANALYZED": "尚未分析",
}


def repo_note_name(repo_name, repo_id):
    """仓库笔记名。用 owner/repo 优先（人认得出），无名字时才退到 id。"""
    return _slug(repo_name or ("repo-%s" % repo_id))


def file_note_name(repo_name, repo_id, file_path):
    head = repo_note_name(repo_name, repo_id)
    return _slug(f"{head}/{file_path}")


def symbol_note_name(repo_name, repo_id, file_path, symbol):
    return _slug(f"{file_note_name(repo_name, repo_id, file_path)}/{symbol}")


def _fm(pairs):
    """YAML frontmatter。★ 字段名用 Dataview 认可的写法，便于 Obsidian 里查询。"""
    out = ["---"]
    for k, v in pairs:
        if v is None or v == "":
            continue
        if isinstance(v, (list, tuple)):
            out.append("%s:" % k)
            for x in v:
                out.append("  - %s" % x)
        else:
            out.append("%s: %s" % (k, v))
    out.append("---")
    return "\n".join(out)


def note_repository(*, repo_name, repo_id, commit_sha, files, facts_count):
    title = repo_note_name(repo_name, repo_id)
    fm = _fm([("source", "SourceLore"), ("type", "repository"),
              ("repository_id", repo_id), ("commit", commit_sha),
              ("facts", facts_count)])
    body = [fm, "", "# %s" % (repo_name or repo_id), "",
            "固定 Commit `%s`" % commit_sha, "", "## 文件", ""]
    for f in files:
        body.append(f"- [[{file_note_name(repo_name, repo_id, f)}]]")
    body += ["", "## 回溯", "",
             "- 知识库：SourceLore（repo_id `%s`）" % repo_id,
             "- Commit：`%s`" % commit_sha]
    return title, "\n".join(body) + "\n"


def note_file(*, repo_name, repo_id, commit_sha, file_path, rows):
    title = file_note_name(repo_name, repo_id, file_path)
    fm = _fm([("source", "SourceLore"), ("type", "file"),
              ("repository_id", repo_id), ("commit", commit_sha),
              ("path", file_path), ("items", len(rows))])
    body = [fm, "", "# `%s`" % file_path, "",
            f"属于 [[{repo_note_name(repo_name, repo_id)}]] · 固定 Commit `{commit_sha[:12]}`",
            "", "## 导出 / 符号", ""]
    for r in rows:
        nm = symbol_note_name(repo_name, repo_id, file_path, r["name"])
        state = STATE_ZH.get(r.get("state"), r.get("state") or "")
        body.append(f"- [[{nm}]] · {r.get('kind') or ''} · {state}")
    return title, "\n".join(body) + "\n"


def note_symbol(*, repo_name, repo_id, commit_sha, file_path, row):
    title = symbol_note_name(repo_name, repo_id, file_path, row["name"])
    st = row.get("state") or "OBSERVED_SOURCE_FACT"
    fm = _fm([("source", "SourceLore"), ("type", "symbol"),
              ("repository_id", repo_id), ("commit", commit_sha),
              ("path", file_path), ("symbol", row["name"]),
              ("kind", row.get("kind")), ("verification", st),
              ("line", row.get("line")),
              ("claim_id", row.get("claim_id"))])
    state_zh = STATE_ZH.get(st, st)
    body = [fm, "", "# `%s`" % row["name"], "",
            "> %s" % state_zh, "",
            "| 项 | 值 |", "|---|---|",
            f"| 类型 | {row.get('kind') or '-'} |",
            f"| 行 | {row.get('line') or '-'} |",
            f"| 仓库 | [[{repo_note_name(repo_name, repo_id)}]] |",
            f"| 文件 | [[{file_note_name(repo_name, repo_id, file_path)}]] |",
            "", "## 证据", "",
            f"- claim: `{row.get('claim_id') or '-'}`",
            f"- commit: `{commit_sha}`",
            "", "## 边界", "",
            "- 静态声明 ≠ 运行时行为",
            "- 只覆盖已抽取的源码文件"]
    return title, "\n".join(body) + "\n"


def export_query_to_vault(*, query_result, repo_name, vault_root):
    """把一次 source_query 结果写成一组互相链接的 Obsidian 笔记。零网络。"""
    q = query_result or {}
    if q.get("state") != "FOUND":
        return {"ok": False, "state": q.get("state"),
                "reason": "该查询没有可导出的知识", "written": []}
    rid = str(q.get("repository_id") or "")
    csha = q.get("commit_sha") or ""
    fpath = q.get("file_path") or ""
    root = Path(vault_root)
    written = []

    rows = []
    for c in (q.get("claims") or []):
        s = c.get("subject") or {}
        nm = (s.get("qualified_name") or s.get("exported_name")
              or s.get("module_name") or "")
        if not nm:
            continue
        rows.append({"name": nm, "kind": c.get("kind"),
                     "state": c.get("display_level"),
                     "line": c.get("start_line"),
                     "claim_id": c.get("claim_id")})

    # 符号笔记
    for r in rows:
        t, txt = note_symbol(repo_name=repo_name, repo_id=rid, commit_sha=csha,
                             file_path=fpath, row=r)
        p = root / (t + ".md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")
        written.append(str(p))

    # 文件笔记
    if fpath:
        t, txt = note_file(repo_name=repo_name, repo_id=rid, commit_sha=csha,
                           file_path=fpath, rows=rows)
        p = root / (t + ".md"); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8"); written.append(str(p))

    # 仓库笔记
    t, txt = note_repository(repo_name=repo_name, repo_id=rid, commit_sha=csha,
                             files=[fpath] if fpath else [],
                             facts_count=(q.get("counts") or {}).get("facts", 0))
    p = root / (t + ".md"); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8"); written.append(str(p))

    return {"ok": True, "vault_root": str(root),
            "notes_written": len(written),
            "files": written, "network_requests": 0}
