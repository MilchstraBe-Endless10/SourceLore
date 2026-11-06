#!/usr/bin/env python3
"""F2-P6E 验收器：编排器行为 + 多仓库隔离 + 覆盖度。全离线。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))


def main():
    import acceptance_request_planner as A
    import capture_plan_consistency as CPC
    import semantic_coverage as SC

    checks = []

    # ① 冷启动估算
    p = A.build_repo_acceptance_plan(
        repository_id="(pending)", commit_sha=None,
        target_paths=("LICENSE", "readme.md", "package.json", "index.js"),
        license_path="LICENSE")
    c = p.counts()
    checks.append({"id": "MIN_MAX_SPLIT",
                   "ok": c["minimum_required_requests"] < c["maximum_planned_requests"],
                   "detail": "%s ~ %s" % (c["minimum_required_requests"],
                                          c["maximum_planned_requests"])})
    checks.append({"id": "BLOB_COUNT_4",
                   "ok": p.by_operation().get("GET blob") == 4,
                   "detail": p.by_operation()})

    # ② 全复用 → 0 请求（D-56）
    q = A.build_repo_acceptance_plan(
        repository_id="r", commit_sha="c" * 40, known_tree_sha="t" * 40,
        target_paths=("README.md", "package.json", "index.js"),
        license_path=None, have_tree=True,
        have_blobs=("README.md", "package.json", "index.js"),
        have_metadata=True)
    checks.append({"id": "REUSE_ZERO_REQUESTS",
                   "ok": q.counts()["maximum_planned_requests"] == 0,
                   "detail": q.counts()})

    # ③ 预检三条件
    blk = A.preflight(plan=p, observed_remaining=None)
    checks.append({"id": "NO_HEADER_BLOCKS", "ok": not blk["can_begin"],
                   "detail": blk["block_reason"]})
    ok = A.preflight(plan=p, observed_remaining=60)
    checks.append({"id": "BUDGET_OK_PASSES", "ok": ok["can_begin"],
                   "detail": ok["planned_primary_requests"]})
    rl = A.preflight(plan=p, observed_remaining=60, rate_limit_status="PRIMARY")
    checks.append({"id": "RATE_LIMIT_BLOCKS", "ok": not rl["can_begin"],
                   "detail": rl["block_reason"]})

    # ④ 计划失效
    ctx = CPC.build_plan_context(repository_id="r", commit_sha="c",
                                 data_root="/tmp/x", source_snapshot_id="s",
                                 selected_scope=["a"])
    pl = CPC.finalize_plan(context=ctx, inventory={
        "objects": [{"file_path": "a", "state": "CONTENT_NOT_CAPTURED",
                     "planned_requests": 1}], "planned_requests_total": 1})
    same = CPC.revalidate(pl, {"objects": [{"file_path": "a",
                                           "state": "CONTENT_NOT_CAPTURED",
                                           "planned_requests": 1}]},
                          data_root="/tmp/x", repository_id="r", commit_sha="c")
    checks.append({"id": "PLAN_FRESH", "ok": same["state"] == CPC.FRESH,
                   "detail": same["state"]})
    stale = CPC.revalidate(pl, {"objects": [{"file_path": "a",
                                            "state": "CLAIMS_VERIFIED",
                                            "planned_requests": 0}]},
                           data_root="/tmp/x", repository_id="r", commit_sha="c")
    checks.append({"id": "PLAN_STALE_REVALIDATED",
                   "ok": stale["state"] == CPC.REVALIDATED,
                   "detail": stale["state"]})
    other = CPC.revalidate(pl, {"objects": []}, data_root="/tmp/y",
                           repository_id="r", commit_sha="c")
    checks.append({"id": "PLAN_CONTEXT_MISMATCH",
                   "ok": other["state"] == CPC.ABORTED,
                   "detail": other["mismatches"]})

    # ⑤ CommonJS 覆盖
    cov = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                      facts_persisted=0, observed_nodes=0,
                      unsupported_forms=SC.detect_unsupported_forms(
                          "module.exports = function(x){};"))
    checks.append({"id": "CJS_UNSUPPORTED",
                   "ok": cov["analysis_coverage"] == SC.UNSUPPORTED_SEMANTIC_FORM,
                   "detail": cov["analysis_coverage"]})
    empty = SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                        facts_persisted=0, observed_nodes=0,
                        unsupported_forms=[])
    checks.append({"id": "VALID_EMPTY",
                   "ok": empty["analysis_coverage"] == SC.VALID_EMPTY_RESULT,
                   "detail": empty["analysis_coverage"]})

    # ⑥ 多仓库隔离（真实库，只读）
    from knowledge_store import KnowledgeStore
    from paths import db_path
    ks = KnowledgeStore(str(db_path("/tmp/p6b_real")), create=False)
    repos = [r["repository_id"] for r in ks.conn.execute(
        "SELECT DISTINCT repository_id FROM index_rows "
        "WHERE asset_type='repository_snapshot'")]
    ks.close()
    checks.append({"id": "ISOLATION_ROW", "ok": "24313173" in repos,
                   "detail": repos})

    bad = [c for c in checks if not c["ok"]]
    out = {"ok": not bad, "checks": checks,
           "total": len(checks), "failed": len(bad)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
