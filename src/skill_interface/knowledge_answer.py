#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""面向用户的知识问答层（P1）：把已登记的项目内容知识按意图组织成答案。

★ 铁律：
  1. 只读、零网络、不写任何资产；只用已登记/已派生的本地知识。
  2. 内容优先：默认回答用途/能力/使用/结构/代码；审计字段（Fact/Claim/
     Verification/覆盖统计）只在用户问「为什么可信 / 检查完整性」时给出。
  3. 不编造：没有来源支持的一律写「未分析 / 证据不足」，绝不从文件名猜功能，
     不把「发现脚本」说成「运行通过」。
  4. 不接 LLM：本模块只做确定性检索与组装，复用 repo_miner 的挖掘结果。

数据源（全部本地、已验证）：
  - repo_miner.mine_project_knowledge() → documents（项目总览 / README 原文 /
    文件结构 / 模块与依赖 / 知识主张与证据）+ project（覆盖说明）。
  - 该挖掘器通过正式 Storage API 读 <data_root>/blobs/*.bin 已验证字节。
"""
from __future__ import annotations

import re

# 意图 → 需要展示的 document_id + section_id（None 表示整篇）
_INTENT_PLAN = {
    "introduce": {
        "docs": {"project-overview": ["purpose", "stack", "entrypoints",
                                      "core_impl"]},
        "fallback": "project-overview",
    },
    "usage": {
        "docs": {
            "readme": None,          # 用标题关键词命中 Install/Usage/true/False 等
            "project-overview": ["stack"],
        },
        "match_heading": True,
        "fallback": "readme",
    },
    "architecture": {
        "docs": {"project-overview": ["entrypoints", "coverage"],
                 "file-structure": None, "dependencies": None},
        "fallback": "project-overview",
    },
    "code": {
        "docs": {"project-overview": ["entrypoints", "core_impl"],
                 "dependencies": None},
        "fallback": "project-overview",
    },
    "evidence": {
        "docs": {"claims": None, "project-overview": ["coverage"]},
        "fallback": "claims",
    },
    "completeness": {
        "docs": {"project-overview": ["coverage"], "file-structure": None},
        "fallback": "project-overview",
    },
}

# 意图识别关键词（中文为主，兼容英文）。顺序即优先级；默认 introduce。
_PATTERNS = (
    ("usage", re.compile(
        r"怎么(使用|用|安装)|如何使用|安装|使用方法|用法|API|示例|例子|"
        r"how to (use|install)|usage|install", re.I)),
    ("evidence", re.compile(
        r"为什么.*(可信|证据)|证据|依据|verification|evidence|"
        r"怎么.*(证实|验证)|可信度", re.I)),
    ("completeness", re.compile(
        r"完整性|覆盖|检查知识库|未分析|缺什么|coverage|completeness", re.I)),
    ("architecture", re.compile(
        r"架构|结构|模块|依赖|入口|architecture|structure|module", re.I)),
    ("code", re.compile(
        r"源码|代码|函数|类|导出|符号|实现|code|symbol|function", re.I)),
    ("introduce", re.compile(
        r"介绍|用途|功能|能力|作用|简介|概览|什么|introduce|overview|purpose", re.I)),
)


def detect_intent(question: str) -> str:
    """把自然语言问题映射为封闭意图码；无法识别回退 introduce。"""
    q = question or ""
    for intent, pat in _PATTERNS:
        if pat.search(q):
            return intent
    return "introduce"


def _index_documents(documents):
    return {d.get("document_id"): d for d in (documents or [])}


def _pick_sections(doc, wanted_ids, match_heading=False, keywords=None):
    """按 section_id 或标题关键词挑段落；wanted_ids=None 且无关键词时取全部。"""
    secs = doc.get("sections") or []
    # 无 id 约束但有关键词 → 只按标题关键词过滤
    if wanted_ids is None and match_heading and keywords:
        picked = []
        for s in secs:
            hay = (str(s.get("heading") or "") + " " +
                   str(s.get("section_id") or "")).lower()
            if any(kw and kw in hay for kw in keywords):
                picked.append(s)
        return picked
    if wanted_ids is None:
        return list(secs)
    picked = []
    for s in secs:
        sid = str(s.get("section_id") or "")
        head = str(s.get("heading") or "")
        if sid in wanted_ids:
            picked.append(s)
            continue
        if match_heading and keywords:
            hay = (head + " " + sid).lower()
            if any(kw and kw in hay for kw in keywords):
                picked.append(s)
    return picked


def _heading_keywords(question):
    """把问题里的实词抽成标题匹配关键词（只读、确定性）。

    ★ 中英映射：README 标题多为英文（Install/Usage/Benchmarks），
      中文问题必须能命中；同时保留英文原词与中文标题。
    """
    q = (question or "").lower()
    direct = ("install", "usage", "api", "example", "true", "false", "why",
              "benchmark", "test", "build", "license", "contributing",
              "安装", "使用", "示例", "测试", "构建", "许可", "基准", "性能")
    kws = [s for s in direct if s in q]
    # 中文意图 → 英文标题词（反之亦然）
    if any(w in q for w in ("怎么使用", "如何使用", "用法", "使用", "安装", "怎么安装")):
        kws += ["install", "usage"]
    if any(w in q for w in ("示例", "例子", "api")):
        kws += ["usage", "true", "false"]
    if any(w in q for w in ("性能", "基准", "benchmark")):
        kws += ["benchmark"]
    if any(w in q for w in ("测试", "test")):
        kws += ["test", "running-tests"]
    if any(w in q for w in ("许可", "license")):
        kws += ["license"]
    # 去重保序
    seen, out = set(), []
    for k in kws:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def answer(*, repository_id, question, data_root, store=None, commit_sha=None):
    """按意图检索已登记项目知识，返回面向用户的答案结构。

    只读：复用 repo_miner（经正式 Storage API 读已验证字节），不联网、不写库。
    """
    from knowledge_store import KnowledgeStore
    from paths import db_path, DEFAULT_DATA_ROOT

    # ★ dispatch 传来的 data_root 可能是 None（走 config/环境变量默认根）。
    #   mine/_blob_texts 必须拿到真实根才能定位 blobs/*.bin，与 derive 一致。
    data_root = data_root or DEFAULT_DATA_ROOT

    own = False
    if store is None:
        store = KnowledgeStore(str(db_path(data_root)), create=False)
        own = True
    try:
        import repo_miner as RM
        import repo_derive_runner as DR

        loaded = DR._load_assets(store, str(repository_id))
        if not loaded:
            return _not_found(repository_id)
        snapshot, claims, verifs = loaded
        commit = commit_sha or snapshot.get("commit_sha")
        tree_entries = snapshot.get("tree_entries") or []

        # 源码观察（与 derive 同一路径，纯本地）
        code_rows = DR._code_rows(repository_id, commit, data_root)

        mined = RM.mine_project_knowledge(
            store=store, repository_id=str(repository_id), commit_sha=commit,
            tree_entries=tree_entries, code_rows=code_rows,
            claims=claims, verifications=verifs, data_root=data_root)
        docs = _index_documents(mined.get("documents"))
        project = mined.get("project") or {}

        intent = detect_intent(question)
        plan = _INTENT_PLAN[intent]
        blocks = []
        for doc_id, wanted in (plan.get("docs") or {}).items():
            doc = docs.get(doc_id)
            if not doc:
                continue
            kws = _heading_keywords(question) if plan.get("match_heading") else None
            for sec in _pick_sections(doc, wanted,
                                      match_heading=bool(plan.get("match_heading")),
                                      keywords=kws):
                body = (sec.get("body") or "").strip()
                if not body:
                    continue
                blocks.append({
                    "document_id": doc_id,
                    "title": doc.get("title") or doc_id,
                    "heading": sec.get("heading") or "",
                    "body": body,
                    "refs": sec.get("refs") or [],
                })

        if not blocks and plan.get("fallback"):
            doc = docs.get(plan["fallback"])
            if doc:
                for sec in _pick_sections(doc, None):
                    if (sec.get("body") or "").strip():
                        blocks.append({
                            "document_id": plan["fallback"],
                            "title": doc.get("title") or plan["fallback"],
                            "heading": sec.get("heading") or "",
                            "body": sec["body"].strip(),
                            "refs": sec.get("refs") or [],
                        })

        # 审计字段仅按需附加（不淹没普通答案）
        audit = None
        if intent in ("evidence", "completeness"):
            from collections import Counter
            import sys as _sys
            from pathlib import Path as _Path
            _trust_dir = str(_Path(__file__).resolve().parents[1] / "trust")
            if _trust_dir not in _sys.path:
                _sys.path.insert(0, _trust_dir)
            import policy as TRUST

            # ★ P0 规则：verification 必须按 current_view 当前指针过滤，
            #   未被当前指针采纳的历史 Verification 不得混入审计统计。
            current_ids = set(TRUST.current_asset_ids(
                store, repository_id=str(repository_id),
                asset_type="claim_verification").values())
            verdict = Counter()
            for v in verifs:
                # 从 A 层 payload 反查该 verification 的 asset_id，
                # 只统计被当前指针采纳的那些
                vid = (v.get("verification_id") or
                       v.get("logical_identity"))
                if not vid:
                    continue
                row = store.conn.execute(
                    "SELECT asset_id FROM assets WHERE asset_type='claim_verification' "
                    "AND repository_id=? AND logical_identity=? "
                    "ORDER BY CAST(asset_version AS INTEGER) DESC LIMIT 1",
                    (str(repository_id), vid)).fetchone()
                if row and row["asset_id"] in current_ids and v.get("status"):
                    verdict[v["status"]] += 1
            audit = {
                "claim_count": len(claims or []),
                "verification_count": len(verifs or []),
                "current_verification_count": sum(verdict.values()),
                "verdict_distribution": dict(verdict),
                "coverage_note": project.get("coverage_note"),
                "blobs_read": project.get("blobs_read"),
                "readme_captured": project.get("readme_captured"),
                "manifest_parsed": project.get("manifest_parsed"),
            }

        return {
            "ok": True,
            "repository_id": str(repository_id),
            "commit_sha": commit,
            "intent": intent,
            "blocks": blocks,
            "audit": audit,
            "coverage_note": project.get("coverage_note"),
            "distribution_allowed": False,
            "freeze_state": "FROZEN_INTERNAL_RESTRICTED",
            "network_requests": 0,
            "wrote_assets": 0,
            "note": ("内容来自已登记、已验证的本地字节；"
                     "未分析部分如实标注，不从文件名推断。"),
        }
    finally:
        if own:
            try:
                store.close()
            except Exception:
                pass


def _not_found(repository_id):
    return {
        "ok": False, "error": "REPOSITORY_NOT_REGISTERED",
        "repository_id": str(repository_id), "blocks": [], "audit": None,
        "network_requests": 0, "wrote_assets": 0,
    }
