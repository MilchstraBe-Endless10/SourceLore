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
        # ★ 本批剩余 6，但只需 4 个 blob：显式降低预留到 1（短批次，非永久策略）
        request_limit=8, reserve_requests=1)
    coord = EC.Coordinator(budget=budget)

    out = {"phases": []}
    # ⓪ bootstrap：至多一次 /rate_limit，取得权威响应头（D-57）
    boot = coord.bootstrap_rate_limit()
    out["bootstrap"] = boot
    print(json.dumps({"bootstrap": boot}, ensure_ascii=False))
    can, reason = budget.can_spend(1)
    if not can:
        out["blocked"] = {"reason": reason, "bootstrap": boot}
        Path("/tmp/p6e_fetch.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"stopped": reason, **boot}, ensure_ascii=False))
        return

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
        # ★ 预算不足就停，不整批失败——已采的照常落盘
        _ok, _why = budget.can_spend(1)
        if not _ok:
            out["partial_stop"] = {"at": e["path"], "reason": _why,
                                   "remaining": budget.observed_remaining,
                                   "reserve": budget.reserve_requests}
            print(json.dumps({"partial_stop": out["partial_stop"]},
                             ensure_ascii=False))
            break
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
        # ★ D-58：每采一个立刻落盘。原本全采完才写，进程一中途退出字节全丢。
        safe = e["path"].replace("/", "__")
        Path("/tmp/p6e_blob_" + safe).write_bytes(raw)
        meta_path = Path("/tmp/p6e_blobmeta_%s.json" % safe)
        meta_path.write_text(json.dumps({
            "path": e["path"], "oid": oid, "expected": e["sha"],
            "oid_match": ok, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "repository_id": ident["repository_id"],
            "commit_sha": ident["commit_sha"]}, ensure_ascii=False), encoding="utf-8")
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
