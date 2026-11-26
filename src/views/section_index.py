#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C 层可重建正文片段检索索引（P2-D2 / D2-B）。

★ 边界（务必遵守）：
  1. 索引是 **C 层派生数据**，可删除重建；正文权威始终在 CAS，片段由 derive
     阶段从 CAS 派生（见 content_section_derivation）。重建只动 section_fts 表，
     绝不触碰 assets / current_view / blobs（Gate 7）。
  2. 严格按 repository_id + commit_sha 身份隔离；不同仓库、不同 Commit 的片段
     不串用，保留 P2-C 的 Commit 指定与歧义契约（Gate 6）。
  3. 授权边界随片段落库：copy_permitted / distribution_allowed 原样保留，
     召回逐条回传，禁止借索引绕过分发 DENY（Gate 9）。
  4. 每条命中都带可回查的 byte 偏移 / content_sha256 / git_blob_oid /
     content_asset_id / 行号（Gate 5）；仅"命中"不等于"语义正确"，调用方
     必须按 source_category 区分文档自述与源码已验证事实（Gate 4）。

★ 不用 FTS5 中文分词（unicode61 对连续中文按整 token 处理，技术词召回不稳）。
  这里用 Python 端确定性大小写不敏感子串匹配，中英文通吃，且授权过滤精确可控。
"""
from __future__ import annotations

import json
import re

TABLE = "section_fts"
SCHEMA_VERSION = "section-index/1"

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    section_id           TEXT NOT NULL,
    repository_id        TEXT NOT NULL,
    commit_sha           TEXT NOT NULL,
    file_path            TEXT NOT NULL,
    heading              TEXT,
    body                 TEXT,
    content_kind         TEXT,
    source_category      TEXT,
    content_asset_id     TEXT,
    content_sha256       TEXT,
    git_blob_oid         TEXT,
    line_start           INTEGER,
    line_end             INTEGER,
    byte_start           INTEGER,
    byte_end             INTEGER,
    copy_permitted       INTEGER NOT NULL DEFAULT 0,
    distribution_allowed INTEGER NOT NULL DEFAULT 0,
    evidence_json        TEXT,
    PRIMARY KEY (section_id, repository_id, commit_sha)
);
CREATE INDEX IF NOT EXISTS idx_section_identity
    ON {TABLE}(repository_id, commit_sha);
CREATE INDEX IF NOT EXISTS idx_section_path
    ON {TABLE}(repository_id, commit_sha, file_path);
"""

# 提问里的通用词，不作为检索词（避免命中 noise 淹没技术词）
_STOPWORDS = frozenset({
    "架构", "结构", "模块", "依赖", "入口", "介绍", "用途", "功能", "能力", "作用",
    "简介", "概览", "什么", "如何", "怎么", "使用", "安装", "实现", "源码", "代码",
    "函数", "类", "导出", "符号", "证据", "依据", "为什么", "可信", "覆盖", "完整",
    "检查", "知识库", "未分析", "缺什么", "是否", "可以", "哪些", "这个", "那个",
    "the", "and", "for", "with", "from", "this", "that", "what", "how", "why",
    "architecture", "structure", "module", "overview", "introduce", "purpose",
    "source", "code", "function", "class", "symbol", "evidence", "coverage",
})

_ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.+#-]{2,}")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")

# 通用中英技术概念映射：只做"问题词→检索词"的确定性翻译，不产出事实结论。
# 目的是让中文问题能命中英文技术文档正文（Gate 8 通用性：不限某一仓库）。
_ZH_EN = {
    "架构": ["architecture"], "结构": ["structure"], "模块": ["module", "crate"],
    "依赖": ["depend", "dependency"], "入口": ["entrypoint", "entry"],
    "用途": ["purpose"], "功能": ["feature"], "能力": ["capability"],
    "源码": ["source"], "实现": ["implementation", "impl"],
    "渲染": ["renderer", "render"], "请求": ["request"],
    "数据流": ["flow", "request"], "接管": ["intercept"],
    "拦截": ["intercept", "proxy"], "修改": ["modify", "intercept"],
    "代理": ["proxy"], "配置": ["configure", "config"],
    "构建": ["build"], "安装": ["install", "installation"],
    "使用": ["usage", "use"], "测试": ["test"], "性能": ["benchmark"],
    "许可": ["license"], "浏览器": ["browser", "webdriver", "chromium"],
    "服务": ["server"], "服务器": ["server"], "隐藏": ["stealth"],
    "指纹": ["fingerprint"], "抓取": ["fetch", "scrape"],
    "提取": ["extract"], "数据": ["data"],
}


def ensure_table(store) -> bool:
    """确保表存在。返回是否新建（供诊断，不影响行为）。"""
    row = store.conn.execute(
        "SELECT count(*) AS n FROM sqlite_master WHERE type='table' AND name=?",
        (TABLE,)).fetchone()
    existed = bool(row and row["n"])
    store.conn.executescript(DDL)
    return not existed


def _flags(section: dict) -> tuple[int, int]:
    cp = 1 if (section.get("copy_permitted") is True or
               section.get("copy_permitted") == 1) else 0
    da = 1 if (section.get("distribution_allowed") is True or
               section.get("distribution_allowed") == 1) else 0
    return cp, da


def rebuild_section_index(store, *, repository_id, commit_sha, sections) -> dict:
    """从派生片段重建某仓库某 Commit 的索引。只动 section_fts 表。

    ★ 可重复、幂等；先删后写同一身份的旧片段，不碰其他身份。
    """
    ensure_table(store)
    rid, cs = str(repository_id), str(commit_sha)
    old = store.conn.execute(
        f"SELECT count(*) FROM {TABLE} WHERE repository_id=? AND commit_sha=?",
        (rid, cs)).fetchone()[0]

    written = 0
    errors = []
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        store.conn.execute(
            f"DELETE FROM {TABLE} WHERE repository_id=? AND commit_sha=?", (rid, cs))
        for s in sections or []:
            cp, da = _flags(s)
            refs = s.get("refs") or []
            try:
                store.conn.execute(
                    f"""INSERT OR REPLACE INTO {TABLE}(
                        section_id, repository_id, commit_sha, file_path, heading,
                        body, content_kind, source_category, content_asset_id,
                        content_sha256, git_blob_oid, line_start, line_end,
                        byte_start, byte_end, copy_permitted, distribution_allowed,
                        evidence_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (str(s.get("section_id") or ""), rid, cs,
                     str(s.get("file_path") or ""), str(s.get("heading") or ""),
                     str(s.get("body") or ""), str(s.get("content_kind") or ""),
                     str(s.get("source_category") or "documentation_self_report"),
                     str(s.get("content_asset_id") or ""),
                     str(s.get("content_sha256") or ""),
                     str(s.get("git_blob_oid") or ""),
                     int(s.get("line_start") or 0), int(s.get("line_end") or 0),
                     int(s.get("byte_start") or 0), int(s.get("byte_end") or 0),
                     cp, da,
                     json.dumps(refs, ensure_ascii=False, sort_keys=True)))
                written += 1
            except Exception as e:
                errors.append(f"{s.get('section_id')}: {type(e).__name__}: {e}")
        store.conn.execute("COMMIT")
    except Exception as e:
        try:
            store.conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    now = store.conn.execute(
        f"SELECT count(*) FROM {TABLE} WHERE repository_id=? AND commit_sha=?",
        (rid, cs)).fetchone()[0]
    return {
        "ok": True, "table": TABLE, "schema": SCHEMA_VERSION,
        "repository_id": rid, "commit_sha": cs,
        "removed": old, "indexed": written, "present": now,
        "errors": errors[:20], "error_count": len(errors),
        "note": "C 层可重建索引；只动 section_fts，不动 A/B/CAS",
    }


def extract_terms(question: str, *, max_terms: int = 18) -> list[str]:
    """确定性检索词：ASCII 技术词 + 中文概念英译优先，CJK bigram 兜底。"""
    q = (question or "").lower()
    terms = []
    for w in _ASCII_WORD.findall(q):
        if w not in _STOPWORDS and w not in terms:
            terms.append(w)
    for run in _CJK_RUN.findall(q):
        # 中文技术概念 → 英文检索词（英文文档正文可用）
        for zh, ens in _ZH_EN.items():
            if zh in run:
                for en in ens:
                    if en not in terms:
                        terms.append(en)
        # 长中文串切成 2 字窗口，避免整句匹配不到；保留原串
        if run not in _STOPWORDS and run not in terms:
            terms.append(run)
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in _STOPWORDS and bg not in terms:
                terms.append(bg)
    return terms[:max_terms]


def query_sections(store, *, repository_id, commit_sha, question=None,
                   terms=None, limit=5, min_score=1) -> dict:
    """按身份隔离 + 确定性子串匹配召回正文片段。只读、零网络、零写入。

    ★ 授权：所有命中原样回传 copy_permitted / distribution_allowed，调用方
      不得把它们升级；本函数本身不产出任何"已验证"结论。
    """
    rid, cs = str(repository_id), str(commit_sha)
    try:
        row = store.conn.execute(
            "SELECT count(*) AS n FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE,)).fetchone()
        if not row or not row["n"]:
            return {"ok": False, "error": "SECTION_INDEX_MISSING", "matches": [],
                    "note": "索引未构建；请用正式 CLI derive 重建（C 层，不动 A/B）"}
        rows = store.conn.execute(
            f"""SELECT * FROM {TABLE}
                WHERE repository_id=? AND commit_sha=?""", (rid, cs)).fetchall()
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "matches": []}

    kws = [k.lower() for k in (terms or extract_terms(question or "")) if k]
    matches = []
    for r in rows:
        if not kws:
            break
        body = (r["body"] or "").lower()
        head = (r["heading"] or "").lower()
        path = (r["file_path"] or "").lower()
        score = 0
        hit = []
        for k in kws:
            if k in head:
                score += 5
                hit.append(k)
            elif k in path:
                score += 2
                hit.append(k)
            elif k in body:
                score += 1
                hit.append(k)
        if score < min_score:
            continue
        refs = []
        try:
            refs = json.loads(r["evidence_json"] or "[]")
        except Exception:
            pass
        matches.append({
            "section_id": r["section_id"],
            "file_path": r["file_path"],
            "heading": r["heading"],
            "body": r["body"],
            "content_kind": r["content_kind"],
            "source_category": r["source_category"],
            "content_asset_id": r["content_asset_id"],
            "content_sha256": r["content_sha256"],
            "git_blob_oid": r["git_blob_oid"],
            "line_start": r["line_start"], "line_end": r["line_end"],
            "byte_start": r["byte_start"], "byte_end": r["byte_end"],
            "copy_permitted": bool(r["copy_permitted"]),
            "distribution_allowed": bool(r["distribution_allowed"]),
            "refs": refs,
            "score": score,
            "matched_terms": hit,
        })

    matches.sort(key=lambda m: (-m["score"], m["file_path"],
                                m["line_start"], m["section_id"]))
    return {
        "ok": True, "repository_id": rid, "commit_sha": cs,
        "terms": kws, "scanned": len(rows),
        "matches": matches[:max(1, int(limit))],
        "note": ("片段命中仅表示正文含检索词；技术结论须按 source_category "
                 "区分文档自述/配置声明/源码字面，不等于已验证事实"),
    }


def index_stats(store) -> dict:
    """诊断：按身份列出索引规模，用于验证跨仓库/Commit 隔离。"""
    try:
        row = store.conn.execute(
            "SELECT count(*) AS n FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE,)).fetchone()
        if not row or not row["n"]:
            return {"ok": False, "error": "SECTION_INDEX_MISSING"}
        rows = store.conn.execute(
            f"""SELECT repository_id, commit_sha, count(*) AS n
                FROM {TABLE} GROUP BY repository_id, commit_sha
                ORDER BY repository_id, commit_sha""").fetchall()
        return {"ok": True, "table": TABLE, "schema": SCHEMA_VERSION,
                "identities": [dict(r) for r in rows],
                "total": sum(r["n"] for r in rows)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
