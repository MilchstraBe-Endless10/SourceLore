#!/usr/bin/env python3
"""F2-P6E 真实验收编排：预检 → 身份 → 采 Blob → 知识 → 查询 → 卡片 → 离线。

★ 全程用编排器记账，每步按真实响应头更新预算。
"""
import json, sys, hashlib, base64, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("collector", "storage", "runtime", "content", "content_persistence",
          "source_analysis", "facts", "evidence_claims", "skill_interface",
          "renderer"):
    sys.path.insert(0, str(ROOT / "src" / p))

OWNER, REPO = "sindresorhus", "is-plain-obj"
TARGETS = ("LICENSE", "readme.md", "package.json", "index.js")


def main():
    import request_budget as RB
    import acceptance_execution_coordinator as EC
    import acceptance_request_planner as A

    budget = RB.GitHubRequestBudget(
        repository_id="(pending)", commit_sha="(pending)", execution_id="p6e",
        request_limit=8, reserve_requests=6)
    coord = EC.Coordinator(budget=budget)

    out = {"phases": []}
    # ① 身份（4 次：metadata/ref/commit/tree）
    ident = EC.run_repo_identity(coord=coord, owner=OWNER, repo=REPO)
    out["identity"] = ident
    out["phases"].append({"phase": "IDENTITY_VERIFIED",
                          "requests_consumed": budget.consumed_requests})
    print(json.dumps({"identity": {k: ident[k] for k in
                                   ("repository_id", "commit_sha",
                                    "root_tree_sha", "default_branch",
                                    "license", "truncated")},
                      "entries": len(ident["tree_entries"]),
                      "requests": budget.consumed_requests}, ensure_ascii=False))

    # ② 选目标文件（大小写以真实 tree 为准）
    by_lower = {e["path"].lower(): e for e in ident["tree_entries"]}
    picked = []
    for want in TARGETS:
        e = by_lower.get(want.lower())
        if e:
            picked.append(e)
    out["picked"] = [{"path": e["path"], "sha": e["sha"],
                      "size": e.get("size")} for e in picked]
    print(json.dumps({"picked": out["picked"]}, ensure_ascii=False))

    # ③ 采 Blob（每个 1 次）
    blobs = {}
    for e in picked:
        d = coord.call(path="/repos/%s/%s/git/blobs/%s" % (OWNER, REPO, e["sha"]),
                       purpose="blob:" + e["path"], object_identity=e["sha"])
        raw = base64.b64decode(d["content"].replace("\n", ""))
        oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        ok = oid == e["sha"]
        blobs[e["path"]] = {"raw": raw, "oid": oid, "expected": e["sha"],
                            "oid_match": ok,
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "bytes": len(raw)}
        print(json.dumps({"blob": e["path"], "bytes": len(raw),
                          "oid_match": ok}, ensure_ascii=False))
        if not ok:
            out["integrity_failed"] = e["path"]
    out["blobs"] = {k: {kk: vv for kk, vv in v.items() if kk != "raw"}
                    for k, v in blobs.items()}
    out["phases"].append({"phase": "BLOBS_CAPTURED",
                          "requests_consumed": budget.consumed_requests})

    out["budget"] = coord.summary()
    Path("/tmp/p6e_fetch.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    # 字节落地，供后续离线流程使用
    for path, b in blobs.items():
        safe = path.replace("/", "__")
        Path("/tmp/p6e_blob_" + safe).write_bytes(b["raw"])
    print(json.dumps({"actual_requests": len(coord.calls),
                      "remaining_after": budget.observed_remaining,
                      "rate_limit_kind": budget.rate_limit_kind},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
