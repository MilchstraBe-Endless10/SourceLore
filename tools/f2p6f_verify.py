#!/usr/bin/env python3
"""F2-P6F 验收器：逐 Blob 契约 + CLI 集成 + 预算 + 许可 + 隔离。全离线。"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))


def main():
    import acceptance_request_planner as A
    import semantic_coverage as SC
    checks = []

    def add(cid, ok, detail=""):
        checks.append({"id": cid, "ok": bool(ok), "detail": detail})

    cli = (ROOT / "src/skill_interface/cli.py").read_text(encoding="utf-8")
    cc = (ROOT / "src/skill_interface/content_capture.py").read_text(encoding="utf-8")
    bf = (ROOT / "src/collector/blob_fetcher.py").read_text(encoding="utf-8")

    # ① 逐 Blob 即时提交
    add("PER_BLOB_IN_LOOP",
        cc.index("ingest_captured_blob") > cc.index("fetch_blob"),
        "入库点必须在 fetch 之后、同一循环内")
    add("NO_BATCH_FINAL_WRITE", "pending_writes" not in cc,
        "不得有攒批再写的结构")

    # ② CLI 集成
    add("CLI_HAS_PREFLIGHT", "_preflight_budget" in cli)
    add("CLI_PASSES_BUDGET", "budget=_budget" in cli)
    add("CLI_OFFLINE_BLOCK", "OFFLINE_NO_REQUESTS" in cli)
    add("BLOB_FETCHER_HEADERS", 'got["headers"]' in bf,
        "响应头必须透传，否则预算拿不到真实剩余")

    # ③ 授权前置
    add("PERSIST_BEFORE_WRITE", "PERSIST_BLOCKED" in cc)
    add("NO_UNLICENSED_WRITE",
        cc.index("PERSIST_BLOCKED") < cc.index("ingest_captured_blob"),
        "持久化判定必须在写入之前")

    # ④ 预算
    p = A.build_repo_acceptance_plan(
        repository_id="r", commit_sha="c" * 40, target_paths=("a",),
        license_path=None, have_metadata=True, have_tree=True, have_blobs=("a",))
    add("REUSE_ZERO_REQUESTS", p.counts()["maximum_planned_requests"] == 0)
    add("D59_NO_HEADER_OK_WHEN_ZERO",
        A.preflight(plan=p, observed_remaining=None)["can_begin"],
        "无需联网时不应要求配额")
    q = A.build_repo_acceptance_plan(
        repository_id="r", commit_sha="c" * 40, target_paths=("a",),
        license_path=None, have_metadata=True)
    add("D59_BLOCK_WHEN_GAP",
        not A.preflight(plan=q, observed_remaining=None)["can_begin"])

    # ⑤ 语义
    add("CJS_UNSUPPORTED",
        SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                    facts_persisted=0, observed_nodes=0,
                    unsupported_forms=["commonjs_module_exports"])["analysis_coverage"]
        == SC.UNSUPPORTED_SEMANTIC_FORM)
    add("VALID_EMPTY",
        SC.classify(parse_status="PARSE_COMPLETE", language="javascript",
                    facts_persisted=0, observed_nodes=0,
                    unsupported_forms=[])["analysis_coverage"]
        == SC.VALID_EMPTY_RESULT)

    # ⑥ 真实库资产（若已采）
    e2e = Path("/tmp/p6f_e2e.json")
    if e2e.exists():
        d = json.loads(e2e.read_text(encoding="utf-8"))
        i = d.get("identity") or {}
        blobs = d.get("blobs") or {}
        done = [k for k, v in blobs.items()
                if v.get("status") in ("PERSISTED_VERIFIED", "ALREADY_CAPTURED")]
        add("REAL_IDENTITY", i.get("repository_id") == 38923193, str(i.get("repository_id")))
        add("REAL_COMMIT",
            i.get("commit_sha") == "666df7c10035f7e26f27ec214fe5ae3173435f34")
        add("REAL_OID_MATCH",
            all(v.get("oid_match", True) for v in blobs.values()))
        add("REAL_BLOBS_PERSISTED", len(done) >= 1, "%d 个" % len(done))
    else:
        add("REAL_IDENTITY", False, "未采集")
        add("REAL_COMMIT", False, "未采集")
        add("REAL_OID_MATCH", False, "未采集")
        add("REAL_BLOBS_PERSISTED", False, "未采集")

    bad = [c for c in checks if not c["ok"]]
    print(json.dumps({"ok": not bad, "checks": checks, "total": len(checks),
                      "failed": len(bad)}, ensure_ascii=False, indent=2))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
