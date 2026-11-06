#!/usr/bin/env python3
"""F2-P6F 真实 E2E：身份 → 逐 Blob 落盘 → 知识。★ 每采一个立刻入库，中途停不丢。"""
import json, sys, base64, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface",
          "renderer"):
    sys.path.insert(0, str(ROOT / "src" / p))

OWNER, REPO = "sindresorhus", "is-plain-obj"
DATA_ROOT = "/tmp/p6f_real"
TARGETS = ("license", "readme.md", "package.json", "index.js")
KNOWN_COMMIT = "666df7c10035f7e26f27ec214fe5ae3173435f34"
KNOWN_TREE = "5d176b98189da7878396a2cffe7590ff35461332"


def main():
    import request_budget as RB
    import acceptance_execution_coordinator as EC
    from knowledge_store import KnowledgeStore
    from paths import db_path
    import source_snapshot as SS
    import ingest_coordinator as IC
    import content_ingest_coordinator as CIC

    Path(DATA_ROOT).mkdir(parents=True, exist_ok=True)
    ks = KnowledgeStore(str(db_path(DATA_ROOT)))

    budget = RB.GitHubRequestBudget(
        repository_id="38923193", commit_sha=KNOWN_COMMIT,
        execution_id="p6f", request_limit=8, reserve_requests=1)
    coord = EC.Coordinator(budget=budget)

    out = {"data_root": DATA_ROOT, "steps": []}
    boot = coord.bootstrap_rate_limit()
    out["bootstrap"] = boot
    print(json.dumps({"bootstrap": boot}, ensure_ascii=False))
    if not budget.can_spend(1)[0]:
        print(json.dumps({"stopped": budget.can_spend(1)[1]}, ensure_ascii=False))
        Path("/tmp/p6f_e2e.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        return

    ident = EC.run_repo_identity(coord=coord, owner=OWNER, repo=REPO)
    out["identity"] = ident
    print(json.dumps({"identity": {k: ident[k] for k in
        ("repository_id", "commit_sha", "root_tree_sha", "license", "truncated")},
        "entries": len(ident["tree_entries"]),
        "requests": budget.consumed_requests}, ensure_ascii=False))

    # 快照落库（身份 + tree）
    snap = SS.build_snapshot(
        repository_id=str(ident["repository_id"]),
        requested_repository="%s/%s" % (OWNER, REPO),
        resolved_repository=ident["full_name"],
        requested_ref="main", commit_sha=ident["commit_sha"],
        root_tree_sha=ident["root_tree_sha"],
        tree_query_ref=ident["root_tree_sha"],
        completeness_status="COMPLETE",
        tree_entries=ident["tree_entries"],
        collected_at=ident.get("commit_date") or "",
        evidence_refs=["github:trees"])
    snap_id = IC.ingest_snapshot(ks, snap)["asset_id"]
    out["snapshot_asset_id"] = snap_id
    print(json.dumps({"snapshot": snap_id}, ensure_ascii=False))

    # 逐 Blob：采 → 验 → 存 → 标记完成
    by_lower = {e["path"].lower(): e for e in ident["tree_entries"]}
    out["blobs"] = {}
    for want in TARGETS:
        e = by_lower.get(want)
        if not e:
            out["blobs"][want] = {"status": "PATH_NOT_IN_TREE"}
            continue
        fp = e["path"]
        # ★ 已完整 → 直接复用，绝不重下
        have = CIC.find_content_asset(ks, repository_id=str(ident["repository_id"]),
                                      commit_sha=ident["commit_sha"], file_path=fp)
        if have and (have.get("completeness_status") or "").upper() == "COMPLETE":
            out["blobs"][fp] = {"status": "ALREADY_CAPTURED",
                                "asset": have.get("content_asset_id")}
            print(json.dumps({"blob": fp, "status": "ALREADY_CAPTURED"}, ensure_ascii=False))
            continue
        ok, why = budget.can_spend(1)
        if not ok:
            out["blobs"][fp] = {"status": "BUDGET_BLOCKED", "reason": why}
            print(json.dumps({"blob": fp, "status": "BUDGET_BLOCKED",
                              "reason": why}, ensure_ascii=False))
            break
        d = coord.call(path="/repos/%s/%s/git/blobs/%s" % (OWNER, REPO, e["sha"]),
                       purpose="blob:" + fp, object_identity=e["sha"])
        raw = base64.b64decode(d["content"].replace("\n", ""))
        oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        if oid != e["sha"]:
            out["blobs"][fp] = {"status": "OID_MISMATCH",
                                "got": oid, "expected": e["sha"]}
            print(json.dumps({"blob": fp, "status": "OID_MISMATCH"}, ensure_ascii=False))
            continue
        ing = CIC.ingest_captured_blob(
            ks, data_root=DATA_ROOT, repository_id=str(ident["repository_id"]),
            commit_sha=ident["commit_sha"], source_snapshot_id=snap_id,
            file_path=fp, git_blob_oid=oid, git_object_format="sha1",
            raw=raw, source_declared_size=e.get("size") or len(raw),
            acquisition_policy="ACQUISITION_ALLOWED",
            acquisition_policy_ref="LICENSE_OBSERVED_AND_APPLICABLE",
            provenance_level="AUTHORIZED_REMOTE_SOURCE")
        out["blobs"][fp] = {
            "status": "PERSISTED_VERIFIED" if ing.get("ok") else "PERSIST_FAILED",
            "asset": ing.get("content_asset_id"), "bytes": len(raw),
            "oid": oid, "oid_match": True, "reused": ing.get("reused"),
            "sha256": hashlib.sha256(raw).hexdigest()}
        print(json.dumps({"blob": fp, "status": out["blobs"][fp]["status"],
                          "bytes": len(raw), "oid_match": True}, ensure_ascii=False))

    out["budget"] = coord.summary()
    ks.close()
    Path("/tmp/p6f_e2e.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    print(json.dumps({"actual_requests": len(coord.calls),
                      "remaining": budget.observed_remaining}, ensure_ascii=False))


if __name__ == "__main__":
    main()
