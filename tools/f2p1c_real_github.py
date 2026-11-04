#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-P1C 真实 GitHub 取数（T-20）。

**真实网络**，非模拟。结果落 docs/implementation/F2_P1C_REAL_GITHUB.json。
若限流/网络失败，如实记录，门禁保持 OPEN。

不要求凭据：只用公开只读 API。
"""
import json, os, sys, tempfile, shutil, datetime, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT/"src"/"collector"), str(ROOT/"src"/"storage"), str(ROOT/"src"/"runtime")):
    if p not in sys.path: sys.path.insert(0, p)

import github_client as G
from tree_collector import TreeCollector, COMPLETE, PARTIAL, read_blob
from source_snapshot import build_snapshot, COLLECTOR_VERSION
from ingest_coordinator import ingest_snapshot, stable_operation_id, INGESTED, IDEMPOTENT
from knowledge_store import KnowledgeStore

TZ = datetime.timezone(datetime.timedelta(hours=8))
OUT = ROOT/"docs"/"implementation"/"F2_P1C_REAL_GITHUB.json"

OWNER, REPO = "octocat", "Hello-World"
REF = "master"


def now():
    return datetime.datetime.now(TZ).isoformat(timespec="seconds")


def main():
    rec = {"artifact": "F2_P1C_REAL_GITHUB", "attempted_at": now(),
           "target": f"{OWNER}/{REPO}", "requested_ref": REF,
           "credential_used": bool(os.environ.get("GITHUB_TOKEN")),
           "stages": []}

    client = G.GitHubClient(max_retries=2)
    client._sleep = lambda s: __import__("time").sleep(min(s, 10))

    def stage(name, fn):
        r = fn()
        e = {"stage": name, "ok": r.ok, "http_status": r.status or None,
             "request_count": client.request_count,
             "error": r.error.to_dict() if r.error else None}
        rec["stages"].append(e)
        return r

    # 1) 仓库身份
    repo_resp = stage("repo_identity", lambda: client.repo(OWNER, REPO))
    if not repo_resp.ok:
        rec["result"] = "BLOCKED_AT_REPO_IDENTITY"
        rec["blocking_error"] = repo_resp.error.to_dict() if repo_resp.error else None
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({"result": rec["result"], "error": rec["blocking_error"]},
                         ensure_ascii=False, indent=2))
        return 2

    repository_id = str(repo_resp.data["id"])
    rec["repository_id"] = repository_id
    rec["resolved_repository"] = repo_resp.data.get("full_name")

    # 2) 解析 ref → commit
    commit_resp = stage("resolve_ref", lambda: client.commit_for_ref(OWNER, REPO, REF))
    if not commit_resp.ok:
        rec["result"] = "BLOCKED_AT_RESOLVE_REF"
        rec["blocking_error"] = commit_resp.error.to_dict() if commit_resp.error else None
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({"result": rec["result"], "error": rec["blocking_error"]},
                         ensure_ascii=False, indent=2))
        return 2

    commit_sha = commit_resp.data["sha"]
    # ★ root_tree_sha 只从 Commit 对象取，绝不用 Trees 响应的 sha
    root_tree_sha = commit_resp.data["commit"]["tree"]["sha"]
    rec["commit_sha"] = commit_sha
    rec["root_tree_sha"] = root_tree_sha
    rec["root_tree_sha_source"] = "commit.commit.tree.sha（非 Trees API 响应）"

    # 3) 抓 tree（用明确的 root_tree_sha）
    tc = TreeCollector(client, OWNER, REPO, repository_id=repository_id,
                       commit_sha=commit_sha)
    tree_res = tc.collect(root_tree_sha)
    rec["tree"] = {"completeness_status": tree_res["completeness_status"],
                   "entry_count": tree_res["entry_count"],
                   "truncated_seen": tree_res["truncated_seen"],
                   "deep_walk_used": tree_res["deep_walk_used"],
                   "tree_query_refs": tree_res["tree_query_refs"][:5],
                   "sample_paths": [e["path"] for e in tree_res["entries"][:10]]}
    rec["tree_query_ref"] = tree_res["tree_query_refs"][0] if tree_res["tree_query_refs"] else None

    if tree_res["completeness_status"] != COMPLETE:
        rec["result"] = "TREE_INCOMPLETE"
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({"result": "TREE_INCOMPLETE",
                          "status": tree_res["completeness_status"]}, ensure_ascii=False))
        return 3

    # 4) 读一个最小 blob（不得执行其内容）
    blobs = [e for e in tree_res["entries"] if e["type"] == "blob" and e["size"] and e["size"] < 4096]
    blob_info = {"attempted": False}
    if blobs:
        target = blobs[0]
        br = read_blob(client, OWNER, REPO, target["sha"], repository_id=repository_id,
                       commit_sha=commit_sha)
        blob_info = {"attempted": True, "path": target["path"], "blob_sha": target["sha"],
                     "ok": br.get("ok"), "verified": br.get("verified"),
                     "size": br.get("size"), "is_binary": br.get("is_binary"),
                     "sha256": br.get("sha256"),
                     "error_code": br.get("error_code")}
        rec["stages"].append({"stage": "blob_fetch", "ok": br.get("ok"),
                              "blob_sha": target["sha"]})
    rec["blob"] = blob_info

    # 5) 构造快照并入库（临时库）
    snap = build_snapshot(
        repository_id=repository_id, requested_repository=f"{OWNER}/{REPO}",
        resolved_repository=repo_resp.data.get("full_name", f"{OWNER}/{REPO}"),
        requested_ref=REF, commit_sha=commit_sha, root_tree_sha=root_tree_sha,
        tree_query_ref=root_tree_sha, completeness_status=tree_res["completeness_status"],
        tree_entries=tree_res["entries"], collected_at=now(),
        evidence_refs=[f"github:repos/{OWNER}/{REPO}@{commit_sha}"],
        truncated_seen=tree_res["truncated_seen"],
        deep_walk_used=tree_res["deep_walk_used"])

    rec["snapshot"] = {
        "logical_identity": snap.logical_identity(),
        "content_hash": snap.content_hash(),
        "tree_entry_count": snap.tree_entry_count,
        "blob_refs_count": len(snap.blob_refs),
        "commit_sha": snap.commit_sha,
        "root_tree_sha": snap.root_tree_sha,
        "tree_query_ref": snap.tree_query_ref,
    }

    tmp = Path(tempfile.mkdtemp(prefix="p1c_real_"))
    try:
        db = str(tmp/"kb.db")
        op = stable_operation_id(repository_id=repository_id, commit_sha=commit_sha,
                                 retrieval_scope=snap.retrieval_scope,
                                 collector_version=COLLECTOR_VERSION)
        with KnowledgeStore(db) as ks:
            r1 = ingest_snapshot(ks, snap, operation_id=op)
            r2 = ingest_snapshot(ks, snap, operation_id=op)   # 幂等复跑
            n = ks.conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"]
            nops = ks.conn.execute("SELECT count(*) AS n FROM operation_log").fetchone()["n"]
            ptr = ks.current_pointer(snap.logical_identity(), repository_id)
            rec["ingest"] = {"first": r1["state"], "second": r2["state"],
                             "operation_id": op, "assets_count": n,
                             "operation_log_count": nops,
                             "pointer_version": ptr.get("pointer_version"),
                             "asset_id": r1.get("asset_id")}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    rec["request_count_total"] = client.request_count
    rec["total_bytes"] = client.total_bytes
    ok_real = (rec["ingest"]["first"] == INGESTED
               and rec["ingest"]["second"] == IDEMPOTENT
               and rec["ingest"]["assets_count"] == 1)
    rec["result"] = "REAL_GITHUB_OK" if ok_real else "REAL_GITHUB_PARTIAL"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"result": rec["result"], "repository_id": repository_id,
                      "commit_sha": commit_sha, "root_tree_sha": root_tree_sha,
                      "entries": tree_res["entry_count"],
                      "ingest": rec["ingest"]["first"]},
                     ensure_ascii=False, indent=2))
    return 0 if ok_real else 1


if __name__ == "__main__":
    sys.exit(main())
