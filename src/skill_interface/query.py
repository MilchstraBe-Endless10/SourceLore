#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识查询：复用 F2-P4B Research Core，不重采集。"""

from paths import ensure_import_path
from result import SkillError
from knowledge import open_store

ensure_import_path()

VALID_TYPES = ("path", "claims", "version")


def run_query(*, repository_id, commit_sha, qtype="path",
              path=None, compare_commit=None, max_results=50,
              data_root=None):
    import query_models as QM
    import research_engine as RE

    if qtype == "path":
        if not path:
            raise SkillError("path 查询需要 --path", code="MISSING_PATH")
        q = QM.build_query(question_type=QM.Q_PATH_CLAIM,
                           repository_id=repository_id,
                           commit_sha=commit_sha, path=path,
                           max_results=max_results)
    elif qtype == "claims":
        q = QM.build_query(question_type=QM.Q_KNOWN_CLAIMS,
                           repository_id=repository_id,
                           commit_sha=commit_sha, max_results=max_results)
    elif qtype == "version":
        if not compare_commit:
            raise SkillError("version 查询需要 --compare-commit",
                             code="MISSING_COMPARE_COMMIT")
        q = QM.build_query(question_type=QM.Q_VERSION_COMPARE,
                           repository_id=repository_id,
                           commit_sha=commit_sha,
                           compare_commit_sha=compare_commit,
                           path=path)
    else:
        raise SkillError(f"未知查询类型：{qtype}（可选 {VALID_TYPES}）",
                         code="UNKNOWN_QUERY_TYPE")

    store = open_store(data_root)
    try:
        pkt = RE.run_research(store, q)
    finally:
        store.close()

    findings = []
    for f in pkt["findings"]:
        findings.append({
            "finding_id": f["finding_id"],
            "claim_id": f["claim_id"],
            "verification_id": f["verification_id"],
            "commit_sha": f["claim_commit_sha"],
            "verdict_status": f["verdict_status"],
            "meaning": f["meaning"],
            "evidence_refs": f["evidence_refs"][:5],
            "evidence_integrity": f.get("evidence_integrity"),
            "review_status": f["review_status"],
            "limitations": f["limitations"],
        })

    cov = pkt["coverage_assessment"]
    return {
        "query_id": pkt["query_id"],
        "research_id": pkt["research_id"],
        "repository_id": repository_id,
        "commit_sha": commit_sha,
        "coverage_state": cov["coverage_state"],
        "coverage_meaning": cov["coverage_meaning"],
        "answerable": cov["coverage_state"] == "ANSWERABLE_FROM_EXISTING_EVIDENCE",
        "findings": findings,
        "untrusted_findings": pkt["untrusted_findings"],
        "gaps": cov.get("gaps") or [],
        "limitations": pkt["limitations"],
        "distribution_restrictions": pkt["distribution_restrictions"],
        "is_knowledge_authority": False,
        "note": ("本结果是知识库检索结果，不是模型推断；"
                 "证据不足时不得据此得出肯定或否定结论"),
    }
