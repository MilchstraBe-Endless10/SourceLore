#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 仓库分析：复用现有 Collector / Facts / Evidence-Claims。

★ 只读采集公开仓库；绝不把部分覆盖标成 COMPLETE。
"""

import re
from urllib.parse import urlparse

from paths import ensure_import_path, db_path, guard_inside_project_db
from result import SkillError

ensure_import_path()

ALLOWED_HOSTS = frozenset({"github.com", "www.github.com"})
_REPO_PATH = re.compile(r"^/(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)"
                        r"(?:\.git)?/?(?:tree/(?P<ref>[^/]+))?/?$")


def parse_github_url(url: str) -> dict:
    """★ 严格校验：只接受 github.com 的仓库地址。"""
    if not isinstance(url, str) or not url.strip():
        raise SkillError("空 URL", code="INVALID_URL")
    u = url.strip()
    if not re.match(r"^https?://", u, re.I):
        raise SkillError(f"必须是 http(s) URL：{u}", code="INVALID_URL")
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        raise SkillError(f"不支持的协议：{p.scheme}", code="INVALID_URL")
    host = (p.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise SkillError(
            f"只允许 github.com（收到 {host}）；拒绝内网或未知主机",
            code="HOST_NOT_ALLOWED", detail={"host": host})
    if p.port not in (None, 80, 443):
        raise SkillError(f"不支持端口：{p.port}", code="INVALID_URL")
    m = _REPO_PATH.match(p.path or "")
    if not m:
        raise SkillError(f"无法解析仓库路径：{p.path}",
                         code="INVALID_REPO_PATH",
                         detail={"path": p.path})
    return {"owner": m.group("owner"), "name": m.group("name"),
            "ref": m.group("ref"), "canonical": f"{m.group('owner')}/{m.group('name')}"}


def analyze(*, url, ref=None, data_root=None, max_requests=40,
            target_path="README", facts_limit=20,
            budget_seconds=30.0) -> dict:
    """采集 → 快照 → Facts → Claim/Verification → 可查询资产。

    ★ 真实走 GitHub API；不复制另一套实现。
    """
    from knowledge_store import KnowledgeStore
    from github_client import GitHubClient
    from source_snapshot import build_snapshot
    from ingest_coordinator import ingest_snapshot
    import extractor
    import ingest as FI
    import ec_models as EM
    import verifier as V
    import verification_store as VS

    parsed = parse_github_url(url)
    owner, name = parsed["owner"], parsed["name"]
    want_ref = ref or parsed["ref"] or "HEAD"

    p = db_path(data_root)
    guard_inside_project_db(p)
    p.parent.mkdir(parents=True, exist_ok=True)

    # ★ Collector 默认允许 retry_after 截到 120s 并重试 4 次（约 8 分钟）。
    # Skill 场景必须限流即快失败，故收紧 max_retry_after / max_retries。
    # 不改 Collector 本身：那是 P1C 的既有契约，这里只调实例上限。
    client = GitHubClient(limits={
        "max_requests": max_requests,
        # ★ 不重试：限流的 retry_after 通常以千秒计，重试只会多烧一次配额
        #    并让用户干等。限流信息由上层如实回报，由用户决定何时重试。
        "max_retries": 0,
        "max_retry_after": 0,
        "request_timeout": min(20, int(budget_seconds)),
    })
    repo_resp = client.repo(owner, name)
    if not getattr(repo_resp, "ok", False):
        err = getattr(repo_resp, "error", None)
        code = getattr(err, "error_code", "UNKNOWN")
        detail = {"error_code": code,
                  "status": getattr(repo_resp, "status", 0),
                  "retry_after": getattr(err, "retry_after", None)}
        if code in ("RATE_LIMITED", "SECONDARY_RATE_LIMITED"):
            detail["hint"] = ("GitHub 已限流（未认证配额 60/h）。"
                              "本 Skill 不会绕过限流，也不会长时间等待；"
                              "请稍后重试或提供 GITHUB_TOKEN 环境变量。")
            raise SkillError(
                f"GitHub 限流：{code}，重试等待 {detail['retry_after']} 秒",
                code=code, detail=detail)
        raise SkillError(f"GitHub 仓库请求失败：{code}",
                         code="GITHUB_FAILED", detail=detail)
    repo_payload = getattr(repo_resp, "data", None) or {}

    repo_id = str(repo_payload.get("id") or "")
    if not repo_id:
        raise SkillError("GitHub 未返回仓库 id", code="MISSING_REPOSITORY_ID")

    commit_resp = client.commit_for_ref(owner, name, want_ref)
    if not getattr(commit_resp, "ok", False):
        raise SkillError("无法解析该 ref 的 Commit",
                         code="COMMIT_RESOLVE_FAILED",
                         detail={"error": getattr(getattr(commit_resp, "error", None), "code", None)})
    commit_sha = (getattr(commit_resp, "data", None) or {}).get("sha") or ""
    root_tree = ((getattr(commit_resp, "data", None) or {}).get("commit") or {}).get("tree", {}).get("sha") or ""
    if not (commit_sha and root_tree):
        raise SkillError("Commit/Tree 字段缺失", code="COMMIT_RESOLVE_FAILED")

    tree_resp = client.tree(owner, name, root_tree)
    if not getattr(tree_resp, "ok", False):
        raise SkillError("Tree 获取失败", code="TREE_FAILED")
    tp = getattr(tree_resp, "data", None) or {}
    entries = tp.get("tree") or []
    truncated = bool(tp.get("truncated"))

    # ★ 截断即 PARTIAL —— 绝不标 COMPLETE
    completeness = "PARTIAL" if truncated else "COMPLETE"

    store = KnowledgeStore(str(p))
    try:
        snap = build_snapshot(
            repository_id=repo_id,
            requested_repository=parsed["canonical"],
            resolved_repository=str(repo_payload.get("full_name") or parsed["canonical"]),
            requested_ref=want_ref, commit_sha=commit_sha,
            root_tree_sha=root_tree, tree_query_ref=root_tree,
            completeness_status=completeness, tree_entries=entries,
            collected_at=_now_iso(), evidence_refs=[
                f"github:repos/{owner}/{name}@{commit_sha}"])
        ing = ingest_snapshot(store, snap)
        snap_asset = ing.get("asset_id")

        facts, claims, verifs = [], [], []
        existing = _existing_claims(store, repo_id)
        if target_path and target_path not in existing:
            f = extractor.extract_file_path_observation(
                store, snapshot_asset_id=snap_asset, target_path=target_path)
            FI.ingest_fact(store, f)
            claim = EM.build_path_claim(
                repository_id=repo_id, commit_sha=commit_sha,
                target_path=target_path, expected_exists=True,
                claim_origin="skill_analyze")
            ver = V.verify_path_claim(store, claim, [f.fact_id])
            VS.ingest_claim(store, claim)
            VS.ingest_verification(store, ver, repository_id=repo_id)
            facts.append(f.fact_id)
            claims.append(claim.claim_id)
            verifs.append({"verification_id": ver.verification_id,
                           "status": ver.status})
    finally:
        store.close()

    return {
        "repository_id": repo_id,
        "repository": str(repo_payload.get("full_name") or parsed["canonical"]),
        "requested_ref": want_ref,
        "commit_sha": commit_sha,
        "root_tree_sha": root_tree,
        "tree_entry_count": len(entries),
        "completeness_status": completeness,
        "snapshot_asset_id": snap_asset,
        "facts": facts, "claims": claims, "verifications": verifs,
        "reused": bool(existing),
        "limitations": ([
            "Tree 被 GitHub 截断，覆盖不完整；未覆盖部分不得判为不存在"] if truncated else []) + [
            "本知识库只记录路径观察事实，不含功能实现或测试结论",
            "commit 为本次固定采集的 Commit，非仓库当前最新状态",
        ],
    }


def _existing_claims(store, repo_id):
    rows = store.conn.execute(
        "SELECT asset_id FROM index_rows WHERE asset_type='claim_candidate' "
        "AND repository_id=?", (repo_id,)).fetchall()
    out = set()
    for r in rows:
        got = store.get_asset(r["asset_id"], verify=True)
        if got.get("ok"):
            pl = got["asset"]["payload"] or {}
            if pl.get("normalized_path"):
                out.add(pl["normalized_path"])
    return out


def _now_iso():
    import datetime
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).isoformat(timespec="seconds")
