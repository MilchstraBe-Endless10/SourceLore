#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容抽取编排：Blob → Observation → Facts。

★ 走既有 Facts 框架（不建第二套裁决机）。
★ 每类命题的 supported/refuted/insufficient 条件在此显式声明。
"""

import blob_reader as BR
import content_models as CM
import evidence_ranges as ER
from content_budget import Budget, DEFAULT, BatchBudget
from parsers import readme as RM
from parsers import package_json as PJ
from parsers import pyproject_toml as PT

# 命题类型
F_README_HEADING = "README_HEADING_EXISTS"
F_MANIFEST_DEP = "MANIFEST_DEPENDENCY_DECLARED"
F_MANIFEST_FIELD = "MANIFEST_FIELD_PRESENT"
F_README_LINK = "README_LINK_DECLARED"
F_CODE_MARKER = "README_CODE_LANGUAGE_MARKER"
F_FILE_META = "FILE_CONTENT_METADATA"

RULE_VERSION = "content-rules/1"

# ★ 每类命题的裁决条件（显式写出，供测试逐条核对）
CLAIM_SEMANTICS = {
    F_README_HEADING: {
        "meaning": "指定 Commit 的该 README 中存在一个标题文本与层级完全一致的标题",
        "applies_to": "readme-markdown",
        "supported": "该解析器在完整（COMPLETE）内容里找到同层级同文本标题，"
                     "且证据范围可核验",
        "refuted": "仅在内容 COMPLETE 且解析成功、确认无该标题时才可 refuted",
        "insufficient": "内容缺失/被截断/PARTIAL/解析失败 → insufficient_evidence",
    },
    F_MANIFEST_DEP: {
        "meaning": "指定 Commit 的该清单文件中显式声明了某依赖名",
        "applies_to": "package-json / pyproject-toml",
        "supported": "在依赖字段中解析到该名字",
        "refuted": "内容 COMPLETE 且清单有效解析，依赖字段中确实不存在该名字",
        "insufficient": "清单无效/缺失依赖字段/内容不完整 → insufficient_evidence",
        "warning": "声明依赖 ≠ 已安装该依赖；缺少声明 ≠ 项目未使用该库",
    },
    F_MANIFEST_FIELD: {
        "meaning": "指定 Commit 的该清单中存在某字段",
        "applies_to": "package-json / pyproject-toml",
        "supported": "字段真实存在于解析结果",
        "refuted": "内容 COMPLETE 且有效解析，字段不存在",
        "insufficient": "解析失败或内容不完整",
    },
}


def pick_parser(path):
    if RM.is_readme(path):
        return ("readme", CM.P_README, RM.PARSER_VERSION)
    base = path.rsplit("/", 1)[-1].lower()
    if base == "package.json":
        return ("package_json", CM.P_PKGJSON, PJ.PARSER_VERSION)
    if base == "pyproject.toml":
        return ("pyproject_toml", CM.P_PYPROJECT, PT.PARSER_VERSION)
    return ("source_meta", "source-meta", "1.0.0")


def extract_one(*, repository_id, commit_sha, file_path, git_blob_oid,
                content_asset_id, data, source_snapshot_id,
                budget: Budget = DEFAULT, provenance_level="SYNTHETIC_FIXTURE",
                declared_completeness="COMPLETE"):
    """单个文件 → {observation, facts, status}。

    ★ 内容不可用时返回明确状态，facts 为空 —— 绝不产生任何 "不存在" 结论。
    """
    kind, parser_id, parser_ver = pick_parser(file_path)
    status, text, meta = BR.read_text(data=data, budget=budget)

    if status != CM.C_AVAILABLE:
        return {"status": status, "observation": None, "facts": [],
                "message": meta.get("message"),
                "claim_hint": "insufficient_evidence"}

    digest = meta.get("digest")
    completeness = (declared_completeness
                    if declared_completeness != CM.COMPLETE else CM.COMPLETE)
    facts, ranges = [], []
    extraction_status = "EXTRACTED"

    if kind == "readme":
        headings, links, fences = RM.parse(text)
        for h in headings[:budget.max_facts_per_file]:
            rng = ER.build_range(text=text, start_byte=h["start_byte"],
                                 end_byte=h["end_byte"], kind=ER.E_HEADING,
                                 # ★ label 只放结构信息，不回显不可信原文
                                 label=f"heading:L{h['level']}",
                                 git_blob_oid=git_blob_oid,
                                 file_path=file_path)
            rng["content_digest"] = digest
            ranges.append(rng)
            facts.append({"rule_id": F_README_HEADING,
                          "subject": {"level": h["level"], "title": h["title"]},
                          "range": rng})
        for ln in links:
            if len(facts) >= budget.max_facts_per_file:
                break
            rng = ER.build_range(text=text, start_byte=ln["start_byte"],
                                 end_byte=ln["end_byte"], kind=ER.E_LINK,
                                 label=ln["target"], git_blob_oid=git_blob_oid,
                                 file_path=file_path)
            rng["content_digest"] = digest
            ranges.append(rng)
            facts.append({"rule_id": F_README_LINK,
                          "subject": {"target": ln["target"]}, "range": rng})
        for fe in fences:
            if len(facts) >= budget.max_facts_per_file:
                break
            rng = ER.build_range(text=text, start_byte=fe["start_byte"],
                                 end_byte=fe["end_byte"], kind=ER.E_CODE_MARKER,
                                 label=fe["language_marker"],
                                 git_blob_oid=git_blob_oid, file_path=file_path)
            rng["content_digest"] = digest
            ranges.append(rng)
            facts.append({"rule_id": F_CODE_MARKER,
                          "subject": {"language_marker": fe["language_marker"]},
                          "range": rng})

    elif kind == "package_json":
        ok, dataj, ec, em = PJ.parse(text)
        if not ok:
            extraction_status = CM.C_PARSE_FAILED
            return {"status": CM.C_PARSE_FAILED, "observation": None,
                    "facts": [], "message": f"{ec}: {em}",
                    "claim_hint": "insufficient_evidence"}
        for item in PJ.extract(dataj, text)[:budget.max_facts_per_file]:
            rng = ER.build_range(text=text, start_byte=0,
                                 end_byte=len(text), kind=ER.E_FIELD,
                                 label=f"{item['field']}:{item.get('dependency') or item.get('field')}",
                                 git_blob_oid=git_blob_oid,
                                 file_path=file_path)
            rng["content_digest"] = digest
            ranges.append(rng)
            facts.append({"rule_id": (F_MANIFEST_DEP if item["kind"] == "dependency"
                                      else F_MANIFEST_FIELD),
                          "subject": item, "range": rng})

    elif kind == "pyproject_toml":
        ok, datat, ec, em = PT.parse(text)
        if not ok:
            extraction_status = (CM.C_PARSE_FAILED if ec == "PARSER_UNAVAILABLE"
                                 else CM.C_PARSE_FAILED)
            return {"status": CM.C_PARSE_FAILED, "observation": None,
                    "facts": [], "message": f"{ec}: {em}",
                    "claim_hint": "insufficient_evidence"}
        for item in PT.extract(datat, text)[:budget.max_facts_per_file]:
            rng = ER.build_range(text=text, start_byte=0, end_byte=len(text),
                                 kind=ER.E_FIELD,
                                 label=f"{item['field']}:{item.get('dependency') or ''}",
                                 git_blob_oid=git_blob_oid,
                                 file_path=file_path)
            rng["content_digest"] = digest
            ranges.append(rng)
            facts.append({"rule_id": (F_MANIFEST_DEP if item["kind"] == "dependency"
                                      else F_MANIFEST_FIELD),
                          "subject": item, "range": rng})

    else:
        # 最小可靠能力：只有元数据，不产生语言结构断言
        rng = ER.build_range(text=text, start_byte=0, end_byte=len(text),
                             kind=ER.E_FIELD, label="file_meta",
                             git_blob_oid=git_blob_oid, file_path=file_path)
        rng["content_digest"] = digest
        ranges.append(rng)
        facts.append({"rule_id": F_FILE_META,
                      "subject": {"byte_length": meta["byte_length"],
                                  "line_count": meta["line_count"],
                                  "line_ending": meta["line_ending"]},
                      "range": rng})

    obs = CM.build_observation(
        repository_id=repository_id, commit_sha=commit_sha,
        file_path=file_path, git_blob_oid=git_blob_oid,
        content_asset_id=content_asset_id, content_digest=digest,
        byte_length=meta["byte_length"], encoding="utf-8",
        parser_id=parser_id, parser_version=parser_ver,
        completeness_status=completeness,
        evidence_ranges=[_strip_range(r) for r in ranges],
        source_snapshot_id=source_snapshot_id,
        extraction_status=extraction_status,
        provenance_level=provenance_level)
    return {"status": CM.C_AVAILABLE, "observation": obs, "facts": facts,
            "message": None, "claim_hint": "supported"}


def _strip_range(r):
    return {k: v for k, v in r.items() if k != "content_digest"}


def extract_snapshot(*, snapshot_payload, repository_id, commit_sha,
                     candidate_paths, source_snapshot_id,
                     budget: Budget = DEFAULT, provenance_level="SYNTHETIC_FIXTURE"):
    """批处理：受预算约束。★ 路径类型必须尊重真实 Tree 对象类型。"""
    entries = (snapshot_payload or {}).get("tree_entries") or []
    by_path = {e.get("path"): e for e in entries}
    bb = BatchBudget(budget)
    results, skipped = [], []

    for path in candidate_paths:
        try:
            bb.admit_path()
        except Exception as e:
            skipped.append({"file_path": path, "code": getattr(e, "code", "BUDGET")})
            continue
        entry = by_path.get(path)
        if entry is None:
            skipped.append({"file_path": path, "code": "PATH_NOT_IN_SNAPSHOT"})
            continue
        otype = entry.get("type")
        if otype in ("symlink", "submodule", "tree", "dir"):
            skipped.append({"file_path": path,
                            "code": "NON_REGULAR_CONTENT",
                            "object_type": otype,
                            "note": "符号链接/子模块/目录不做文本解析"})
            continue

        refs = [(snapshot_payload or {}).get("blob_refs") or []]
        ref = next((r for r in refs[0] if r.get("path") == path), None)
        size = (ref or {}).get("size") or entry.get("size") or 0
        try:
            bb.check_blob(size)
        except Exception as e:
            skipped.append({"file_path": path, "code": getattr(e, "code", "BUDGET")})
            continue

        inline = (snapshot_payload or {}).get("blob_contents") or {}
        data = inline.get(entry.get("sha"))
        got = extract_one(
            repository_id=repository_id, commit_sha=commit_sha,
            file_path=path, git_blob_oid=entry.get("sha"),
            content_asset_id=None,
            data=data, source_snapshot_id=source_snapshot_id,
            budget=budget, provenance_level=provenance_level,
            declared_completeness=(snapshot_payload or {}).get(
                "completeness_status") or CM.COMPLETE)
        got["file_path"] = path
        if got["status"] != CM.C_AVAILABLE:
            skipped.append({"file_path": path, "code": got["status"],
                            "message": got.get("message")})
            continue
        results.append(got)

    return {"observations": results, "skipped": skipped,
            "budget": {"used_bytes": bb.used_bytes,
                       "paths_seen": bb.paths_seen,
                       "limits": budget.__dict__}}
