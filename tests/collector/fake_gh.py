#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确定性 GitHub 假响应夹具（不联网）。

用于覆盖错误分类、树截断、blob 校验等**无法稳定靠真实网络复现**的场景。
真实网络测试单独在 test_real_github.py 里，两者分开报告。
"""
import base64, hashlib, json

def blob_sha1(content: bytes) -> str:
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()

COMMIT_SHA = "a" * 40
ROOT_TREE_SHA = "b" * 40
OTHER_TREE_SHA = "c" * 40
BLOB_SHA = None
BLOB_CONTENT = b"hello world\n"
BLOB_SHA = blob_sha1(BLOB_CONTENT)

REPO_JSON = {"id": 1296269, "full_name": "octocat/Hello-World",
             "name": "Hello-World", "owner": {"login": "octocat"},
             "default_branch": "master", "private": False}

COMMIT_JSON = {
    "sha": COMMIT_SHA,
    "commit": {"tree": {"sha": ROOT_TREE_SHA}, "message": "init"},
    "files": [],
}

# 关键：递归 tree 的 sha 回显请求 ref（模拟 GitHub 行为）
def tree_json(ref: str, entries: list, truncated: bool = False) -> dict:
    return {"sha": ref, "truncated": truncated, "tree": entries}

FLAT_ENTRIES = [
    {"path": "README", "mode": "100644", "type": "blob", "sha": BLOB_SHA, "size": 12},
    {"path": "docs", "mode": "040000", "type": "tree", "sha": "d" * 40, "size": None},
]

NESTED_ROOT = [
    {"path": "README", "mode": "100644", "type": "blob", "sha": BLOB_SHA, "size": 12},
    {"path": "docs", "mode": "040000", "type": "tree", "sha": "d" * 40, "size": None},
    {"path": "link", "mode": "120000", "type": "blob", "sha": "e" * 40, "size": 4},
    {"path": "sub", "mode": "160000", "type": "commit", "sha": "f" * 40, "size": None},
    {"path": "weird", "mode": "100644", "type": "unknown", "sha": "g" * 40, "size": 3},
]

SUBTREE_ENTRIES = [
    {"path": "docs/guide.md", "mode": "100644", "type": "blob", "sha": "h" * 40, "size": 7},
]

BLOB_JSON = {"sha": BLOB_SHA, "size": len(BLOB_CONTENT), "encoding": "base64",
             "content": base64.b64encode(BLOB_CONTENT).decode()}

def make_router(*, truncated_recursive=False, tree_entries=None,
                commit_sha=COMMIT_SHA, root_tree_sha=ROOT_TREE_SHA):
    """返回一个 path→(status, json, headers) 的路由函数。"""
    entries = tree_entries if tree_entries is not None else FLAT_ENTRIES

    def route(path: str, params: dict) -> tuple:
        hdr = {}
        if path.startswith("/repos/") and "/git/trees/" in path:
            ref = path.rsplit("/", 1)[1]
            if ref == root_tree_sha:
                if params.get("recursive") and truncated_recursive:
                    return 200, tree_json(ref, entries, truncated=True), hdr
                if params.get("recursive"):
                    # 模拟 GitHub：回显请求 ref
                    return 200, tree_json(ref, entries, truncated=False), hdr
                return 200, tree_json(ref, entries, truncated=False), hdr
            if ref == "d" * 40:      # 子目录
                return 200, tree_json(ref, SUBTREE_ENTRIES, truncated=False), hdr
            if ref == commit_sha:
                # ★ 真实 GitHub 行为：以 commit-ish 为 ref 请求 trees 时，
                # 响应里的 sha **回显请求标识**，而不是真实展开的 tree sha。
                # 这正是 F0 勘误 E-01..E-06 的核心，必须在夹具里复现。
                return 200, tree_json(ref, entries, truncated=truncated_recursive), hdr
            return 404, {"message": "Not Found"}, hdr
        if "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[1]
            if sha == BLOB_SHA:
                return 200, BLOB_JSON, hdr
            return 404, {"message": "Not Found"}, hdr
        if "/commits/" in path:
            return 200, dict(COMMIT_JSON, sha=commit_sha), hdr
        if path.startswith("/repos/") and path.count("/") == 3:
            return 200, REPO_JSON, hdr
        return 404, {"message": "Not Found"}, hdr
    return route


def install_fake(client, router):
    """把 client 的底层请求替换为路由器（仍走同一错误分类代码路径）。"""
    import github_client as G

    def _fake_do_request(url, stage, repository_id, commit_sha, accept):
        from urllib.parse import urlsplit, parse_qs
        parts = urlsplit(url)
        params = {k: v[0] for k, v in parse_qs(parts.query).items()}
        status, body, hdrs = router(parts.path, params)
        client.request_count += 1
        if status == 200:
            return G.GhResponse(ok=True, status=200, data=body, headers=hdrs,
                                body_bytes=len(json.dumps(body)))
        import json as _j
        raw = _j.dumps(body).encode()
        code, ra, detail = client._classify_http(status, hdrs, raw, stage)
        return G.GhResponse(ok=False, status=status, headers=hdrs,
                            body_bytes=len(raw),
                            error=G.GhError(error_code=code, request_stage=stage,
                                            repository_id=repository_id,
                                            commit_sha=commit_sha,
                                            retryable=(code in G.RETRYABLE),
                                            retry_after=ra, http_status=status,
                                            detail=detail))
    client._do_request = _fake_do_request
    # 默认不真等待；但**不要**覆盖调用方已设置的 _sleep ——
    # 曾因此让"退避时间被上限截断"的断言变成空跑假通过（本批实测发现）。
    if not getattr(client, "_sleep_override_set", False):
        client._sleep = lambda s: None
    return client
