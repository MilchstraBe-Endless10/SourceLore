#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README 解析器。★ 只做机械可验证的结构观察。

不推断：安装流程完整、功能已实现、文档完善。
"""

import re

from content_models import P_README
PARSER_VERSION = "1.0.0"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^```([A-Za-z0-9_+-]*)")


def parse(text, *, max_headings=64, max_links=64, max_fences=64):
    """返回 (headings, links, fences)。全部带字节偏移。"""
    headings, links, fences = [], [], []
    offset = 0
    in_fence = False

    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        stripped = line.rstrip("\r\n")

        m = FENCE_RE.match(stripped)
        if m:
            if len(fences) < max_fences:
                lang = m.group(1) or None
                fences.append({"language_marker": lang, "line": lineno,
                               "start_byte": offset,
                               "end_byte": offset + len(stripped)})
            in_fence = not in_fence
        elif not in_fence:
            h = HEADING_RE.match(stripped)
            if h and len(headings) < max_headings:
                level = len(h.group(1))
                title = h.group(2).strip()
                headings.append({"level": level, "title": title,
                                 "line": lineno, "start_byte": offset,
                                 "end_byte": offset + len(stripped)})
            if len(links) < max_links:
                for lm in LINK_RE.finditer(stripped):
                    links.append({
                        "text": lm.group(1), "target": lm.group(2),
                        "line": lineno,
                        "start_byte": offset + lm.start(),
                        "end_byte": offset + lm.end(),
                    })
        offset += len(line)

    return headings, links, fences


def document_format(path):
    low = path.lower()
    if low.endswith(".md"):
        return "markdown"
    if low.endswith(".markdown"):
        return "markdown"
    if low.endswith(".txt"):
        return "text"
    return None


def is_readme(path):
    base = path.rsplit("/", 1)[-1].lower()
    return base in ("readme.md", "readme.markdown", "readme.txt", "readme")
