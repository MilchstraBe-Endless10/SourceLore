#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可重建的正文片段派生层（P2-D2 / D2-A）。

★ 边界（务必遵守）：
  1. 这是**读取层派生**，不是新的权威知识来源。正文原始字节始终在 CAS
     （<data_root>/blobs/<裸sha256>.bin），本模块只把已授权正文按内容类型
     切成可检索片段，供 C 层 FTS 索引与 answer 召回使用。
  2. 完全可从 A 层授权资产离线重建；删除本层派生结果不触碰 CAS / Facts /
     Claims / Verifications，也不改 current_view。
  3. 不把文档自述升级为源码已验证事实：每个片段带 source_category，
     明确区分 documentation_self_report / config_declaration / source_literal /
     license_text / plain_text。
  4. 授权边界随片段传递：copy_permitted / distribution_allowed 原样保留，
     禁止借 FTS 绕过分发 DENY 门禁。

内容类型区分（D2-A §4.2）：
  - Markdown 按标题层级切分；代码块内的 `#` 不当标题；保留列表/表格/代码。
  - Cargo.toml / package.json / *.yaml 等按配置清单处理，绝不按 Markdown 切。
  - 普通文本按空行段落切；源码按整文件有界切（不假装 AST 解析）。
  - 不支持的二进制/编码显式记录原因，绝不伪造解析结果。
"""

from __future__ import annotations

import hashlib
import re

# 标题：ATX（# .. ######）；要求 # 后是空格或行尾，避免 `#hashtag` 误判
_ATX = re.compile(r"^(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
# 代码围栏：``` 或 ~~~，可带语言标记
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")

MAX_SECTION_CHARS = 4000          # 单片段正文上限（超长章节再切）
MAX_SECTIONS_PER_FILE = 120       # 单文件片段数上限（防失控，超出如实标注）

KIND_MARKDOWN = "markdown"
KIND_TEXT = "plain_text"
KIND_CONFIG = "config_declaration"
KIND_SOURCE = "source_literal"
KIND_SKILL_DOC = "skill_document"
KIND_LICENSE = "license_text"
KIND_UNSUPPORTED = "unsupported"

_SOURCE_CATEGORY = {
    KIND_MARKDOWN: "documentation_self_report",
    KIND_TEXT: "documentation_self_report",
    KIND_SKILL_DOC: "documentation_self_report",
    KIND_CONFIG: "config_declaration",
    KIND_SOURCE: "source_literal",
    KIND_LICENSE: "license_text",
}


def classify_content(path: str) -> str:
    """按路径判定内容类型。只按扩展名/文件名，不读内容、不猜用途。"""
    low = (path or "").lower()
    base = low.rsplit("/", 1)[-1]
    if base in ("license", "license.md", "license.txt", "copying", "notice"):
        return KIND_LICENSE
    # Skill 文档（含子目录 skills/*/SKILL.md），仍按 Markdown 结构切
    if base == "skill.md" or "/skills/" in low:
        return KIND_SKILL_DOC
    if low.endswith((".md", ".markdown", ".mdx")):
        return KIND_MARKDOWN
    if low.endswith((".toml", ".json", ".jsonc", ".yaml", ".yml",
                    ".ini", ".cfg", ".conf", ".lock", ".env.example")):
        return KIND_CONFIG
    if low.endswith((".txt", ".rst", ".adoc", ".text")):
        return KIND_TEXT
    if low.endswith((".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
                    ".py", ".rs", ".go", ".java", ".c", ".h", ".cpp",
                    ".cc", ".rb", ".php", ".swift", ".kt", ".sh", ".sql")):
        return KIND_SOURCE
    # 无扩展名但可读的普通文件（README 等已在上面覆盖）
    if not base or "." not in base:
        return KIND_TEXT
    return KIND_UNSUPPORTED


def _stable_id(repository_id, commit_sha, path, heading, line_start, digest):
    raw = "|".join([str(repository_id), str(commit_sha), path,
                    heading or "", str(line_start), digest or ""])
    return "SL-SEC-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _byte_offsets(lines):
    """返回每行（含换行）起始字节偏移列表，长度 len(lines)+1。"""
    offs = [0]
    total = 0
    for ln in lines:
        total += len(ln.encode("utf-8")) + 1  # +1 for splitlines 丢掉的 \n
        offs.append(total)
    return offs


def _split_long(body, *, limit=MAX_SECTION_CHARS):
    """超长正文按行边界切成 <=limit 的片段，尽量不切断行。"""
    if len(body) <= limit:
        return [body]
    chunks, cur = [], []
    size = 0
    for ln in body.split("\n"):
        add = len(ln) + 1
        if cur and size + add > limit:
            chunks.append("\n".join(cur))
            cur, size = [], 0
        cur.append(ln)
        size += add
    if cur:
        chunks.append("\n".join(cur))
    # 单行本身就超过 limit（如超长 base64/压缩 JSON）时按字符硬切，
    # 如实标注 boundary=char（行边界不可用时才用）。
    final = []
    for ch in chunks:
        if len(ch) <= limit:
            final.append(ch)
            continue
        for i in range(0, len(ch), limit):
            final.append(ch[i:i + limit])
    return final or [body]


def _base_section(*, repository_id, commit_sha, path, meta, kind, heading,
                  heading_level, line_start, line_end, byte_start, byte_end,
                  body, seq):
    return {
        "section_id": _stable_id(repository_id, commit_sha, path,
                                 heading, line_start,
                                 (meta or {}).get("digest")),
        "sequence": seq,
        "repository_id": str(repository_id),
        "commit_sha": commit_sha,
        "file_path": path,
        "content_asset_id": (meta or {}).get("content_asset_id"),
        "content_sha256": (meta or {}).get("digest"),
        "git_blob_oid": (meta or {}).get("git_blob_oid"),
        "content_kind": kind,
        "source_category": _SOURCE_CATEGORY.get(kind, "documentation_self_report"),
        "heading": heading or "",
        "heading_level": int(heading_level or 0),
        "line_start": int(line_start),
        "line_end": int(line_end),
        "byte_start": int(byte_start),
        "byte_end": int(byte_end),
        "body": body,
        "provenance_level": (meta or {}).get("provenance_level"),
        "copy_permitted": bool((meta or {}).get("copy_permitted")),
        "distribution_allowed": bool((meta or {}).get("distribution_allowed")),
    }


def derive_markdown_sections(*, repository_id, commit_sha, path, text, meta,
                             kind=KIND_MARKDOWN):
    """按 Markdown 标题层级切分。

    ★ 代码块内的 `#` 不触发新章节（_FENCE 状态机）。
    ★ 无标题正文、列表、表格、多级标题、重复标题都原样保留。
    ★ 每段带精确行号 + UTF-8 字节范围。
    """
    lines = text.split("\n")
    offs = _byte_offsets(lines)
    sections = []
    cur_heading, cur_level = None, 0
    cur_start = 0          # 0-based 行索引
    in_code = False
    fence_mark = ""

    def flush(end_idx):
        # end_idx 为 exclusive；把 [cur_start, end_idx) 切成一个或多个片段
        if end_idx <= cur_start:
            return
        raw_lines = lines[cur_start:end_idx]
        body = "\n".join(raw_lines).strip("\n")
        if not body.strip():
            return
        bs = offs[cur_start]
        be = offs[end_idx] - 1 if end_idx < len(offs) else offs[-1]
        for part in _split_long(body):
            sections.append(_base_section(
                repository_id=repository_id, commit_sha=commit_sha, path=path,
                meta=meta, kind=kind, heading=cur_heading,
                heading_level=cur_level, line_start=cur_start + 1,
                line_end=end_idx, byte_start=bs, byte_end=be, body=part,
                seq=len(sections)))

    for i, raw in enumerate(lines):
        line = raw.rstrip()
        fm = _FENCE.match(line)
        if fm:
            mark = fm.group(1)[0]
            if not in_code:
                in_code, fence_mark = True, mark
            elif mark == fence_mark:
                in_code, fence_mark = False, ""
            continue
        if not in_code:
            hm = _ATX.match(line)
            if hm:
                flush(i)
                cur_heading = (hm.group(2) or "").strip()
                cur_level = len(hm.group(1))
                cur_start = i + 1
                continue
    flush(len(lines))
    return sections[:MAX_SECTIONS_PER_FILE]


def derive_plain_sections(*, repository_id, commit_sha, path, text, meta, kind):
    """普通文本 / 配置清单 / 源码 / 许可：按空行段落切，有界。

    ★ 不按 Markdown 标题切（Cargo.toml 绝不当 Markdown）。
    ★ 源码只做 literal 片段，不冒充 AST 解析。
    """
    lines = text.split("\n")
    offs = _byte_offsets(lines)
    blocks = []
    start = 0
    for i in range(1, len(lines) + 1):
        if i == len(lines) or not lines[i].strip():
            if i > start:
                body = "\n".join(lines[start:i]).strip("\n")
                if body.strip():
                    blocks.append((start, i, body))
            start = i + 1
    if not blocks:
        body = "\n".join(lines).strip("\n")
        if body.strip():
            blocks.append((0, len(lines), body))

    sections = []
    for start, end, body in blocks:
        bs, be = offs[start], (offs[end] - 1 if end < len(offs) else offs[-1])
        for part in _split_long(body):
            sections.append(_base_section(
                repository_id=repository_id, commit_sha=commit_sha, path=path,
                meta=meta, kind=kind, heading=None, heading_level=0,
                line_start=start + 1, line_end=end, byte_start=bs, byte_end=be,
                body=part, seq=len(sections)))
        if len(sections) >= MAX_SECTIONS_PER_FILE:
            break
    return sections[:MAX_SECTIONS_PER_FILE]


def derive_sections_for_blob(*, repository_id, commit_sha, path, text, meta):
    """单文件派生入口：按类型分派，返回 (sections, note)。"""
    if not text:
        return [], {"status": "EMPTY_TEXT", "path": path}
    kind = classify_content(path)
    if kind == KIND_UNSUPPORTED:
        return [], {"status": "UNSUPPORTED_CONTENT_TYPE", "path": path,
                    "reason": "extension not recognized as text"}
    if kind in (KIND_MARKDOWN, KIND_SKILL_DOC):
        secs = derive_markdown_sections(
            repository_id=repository_id, commit_sha=commit_sha, path=path,
            text=text, meta=meta, kind=kind)
    else:
        secs = derive_plain_sections(
            repository_id=repository_id, commit_sha=commit_sha, path=path,
            text=text, meta=meta, kind=kind)
    if not secs:
        return [], {"status": "NO_SECTIONS", "path": path,
                    "reason": "no non-empty text block"}
    return secs, {"status": "DERIVED", "path": path, "kind": kind,
                  "section_count": len(secs)}


def derive_sections_from_texts(*, texts, meta, repository_id, commit_sha):
    """对已加载的正文派生（避免重复读 CAS）。返回 (sections, notes, coverage)。

    `texts` / `meta` 形状与 versioned_assets.captured_blobs 返回一致。
    """
    all_sections, notes = [], []
    kind_counts = {}
    for path, text in sorted((texts or {}).items()):
        secs, note = derive_sections_for_blob(
            repository_id=repository_id, commit_sha=commit_sha,
            path=path, text=text, meta=(meta or {}).get(path))
        notes.append(note)
        if secs:
            kind = secs[0]["content_kind"]
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        all_sections.extend(secs)
    return all_sections, notes, {
        "captured_in_version": len(texts or {}),
        "derived_files": sum(1 for n in notes if n["status"] == "DERIVED"),
        "derived_sections": len(all_sections),
        "kind_counts": kind_counts,
        "per_file_notes": notes,
    }


def derive_all_sections(store, repository_id, commit_sha, data_root):
    """从 CAS 读全部已授权正文并逐个派生。

    返回 (sections, per_file_notes, coverage)。严格按固定 Commit 隔离，
    复用 versioned_assets.captured_blobs（同路径多版本确定性选取）。
    """
    import versioned_assets as VA
    texts, meta, coverage = VA.captured_blobs(
        store, repository_id, commit_sha, data_root)
    all_sections, notes, cov = derive_sections_from_texts(
        texts=texts, meta=meta, repository_id=repository_id,
        commit_sha=commit_sha)
    return all_sections, notes, {**coverage, **cov}
