#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引用解析 + Tree 采集 + Blob 读取。

契约：SL-CAP-0013（Commit / Root Tree / Tree Query 三者分离）。

**核心防错（F0 勘误 E-01..E-06 的直接防线）：**
  GitHub Trees API 以 commit-ish 为 ref 时，响应里的 `sha` **回显的是请求标识**，
  而不是它真正展开的 tree 的 sha。
  所以：
    - `root_tree_sha` 只能来自 **Commit 对象的 `commit.tree.sha`**，绝不能从 Trees API 响应里取。
    - `tree_query_ref` 记录**这次实际请求用的 ref**，它可能等于 commit_sha，也可能等于 root_tree_sha。
    - 三者即使字面相同，语义也不同，**必须分开存**。
"""

import base64
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from github_client import (GhError, GitHubClient, GhResponse,
                           TRUNCATED, BLOB_MISSING, BUDGET_EXCEEDED, MALFORMED)

# 完整性状态（三种，绝不混用）
COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"
INCOMPLETE = "INCOMPLETE"

# Tree 条目类型
ENTRY_BLOB = "blob"
ENTRY_TREE = "tree"
ENTRY_COMMIT = "commit"      # submodule
ENTRY_UNKNOWN = "unknown"


@dataclass
class TreeCollector:
    """Tree 采集器。

    优先递归；`truncated=true` 时**不得**标记完整，退回逐层遍历（有上限）。
    """
    client: GitHubClient
    owner: str
    repo: str
    repository_id: Optional[str] = None
    commit_sha: Optional[str] = None

    entries: list = field(default_factory=list)
    tree_query_refs: list = field(default_factory=list)
    truncated_seen: bool = False
    deep_walk_used: bool = False
    error: Optional[GhError] = None

    def collect(self, root_tree_sha: str) -> dict:
        """采集 tree。root_tree_sha 必须来自 Commit 对象，不接受其他来源。"""
        self.entries.clear(); self.tree_query_refs.clear()
        self.truncated_seen = False; self.deep_walk_used = False
        self.error = None

        # 第一次：用明确的 tree sha 做递归
        resp = self.client.tree(self.owner, self.repo, root_tree_sha,
                                recursive=True, repository_id=self.repository_id,
                                commit_sha=self.commit_sha)
        self.tree_query_refs.append(root_tree_sha)

        if not resp.ok:
            self.error = resp.error
            return self._result(INCOMPLETE, reason=resp.error.error_code if resp.error else "UNKNOWN")

        data = resp.data or {}
        truncated = bool(data.get("truncated"))
        self.truncated_seen = truncated

        if truncated:
            # 递归被截断 → 逐层遍历；**不得**直接标 COMPLETE
            return self._deep_walk(root_tree_sha)

        limit = self.client.limits["max_tree_entries"]
        for e in data.get("tree", []):
            if len(self.entries) >= limit:
                return self._result(PARTIAL, reason="TREE_ENTRY_LIMIT_EXCEEDED")
            self.entries.append(self._norm_entry(e, depth=0))

        return self._result(COMPLETE)

    def _deep_walk(self, root_tree_sha: str) -> dict:
        """逐层遍历（受深度/条目/请求数上限）。逐层结果本身也不保证完整。"""
        self.deep_walk_used = True
        queue = [(root_tree_sha, 0, "")]
        seen_dirs = set()

        while queue:
            sha, depth, prefix = queue.pop(0)
            if depth > self.client.limits["max_depth"]:
                return self._result(PARTIAL, reason="MAX_DEPTH_EXCEEDED")
            if sha in seen_dirs:
                continue
            seen_dirs.add(sha)

            resp = self.client.tree(self.owner, self.repo, sha, recursive=False,
                                    repository_id=self.repository_id,
                                    commit_sha=self.commit_sha)
            self.tree_query_refs.append(sha)
            if not resp.ok:
                self.error = resp.error
                return self._result(INCOMPLETE,
                                    reason=resp.error.error_code if resp.error else "UNKNOWN")

            data = resp.data or {}
            if data.get("truncated"):
                # 逐层仍被截断 → 只能 PARTIAL
                self.truncated_seen = True
                return self._result(PARTIAL, reason="TRUNCATED_EVEN_NON_RECURSIVE")

            limit = self.client.limits["max_tree_entries"]
            for e in data.get("tree", []):
                if len(self.entries) >= limit:
                    return self._result(PARTIAL, reason="TREE_ENTRY_LIMIT_EXCEEDED")
                norm = self._norm_entry(e, depth=depth, prefix=prefix)
                self.entries.append(norm)
                if norm["type"] == ENTRY_TREE:
                    queue.append((norm["sha"], depth + 1, norm["path"] + "/"))

        # 逐层走完且没有任何截断 → 可标 COMPLETE，但记下用过逐层路径
        return self._result(COMPLETE, reason="DEEP_WALK_COMPLETE")

    def _norm_entry(self, e: dict, *, depth: int, prefix: str = "") -> dict:
        t = e.get("type")
        path = (prefix + e.get("path", "")) if prefix else e.get("path", "")
        if t not in (ENTRY_BLOB, ENTRY_TREE, ENTRY_COMMIT):
            t = ENTRY_UNKNOWN
        mode = e.get("mode", "")
        mode_kind = ("symlink" if mode == "120000" else
                     "submodule" if mode == "160000" else "file")
        return {"path": path, "sha": e.get("sha"), "type": t,
                "mode": mode, "mode_kind": mode_kind, "size": e.get("size"),
                "depth": depth}

    def _result(self, status: str, *, reason: str = "") -> dict:
        return {"ok": status == COMPLETE or (status == PARTIAL and not self.error),
                "completeness_status": status,
                "reason": reason,
                "entry_count": len(self.entries),
                "entries": list(self.entries),
                "tree_query_refs": list(self.tree_query_refs),
                "truncated_seen": self.truncated_seen,
                "deep_walk_used": self.deep_walk_used,
                "error": self.error.to_dict() if self.error else None}


# ── Blob 读取 ───────────────────────────────────────────────
def git_blob_sha1(content: bytes) -> str:
    """按 **Git 对象编码规则**算 blob sha：
    sha1("blob <len>\\0" + content)

    这与直接对文件内容算 sha1 **不同**。题面明确要求用真实规则。
    """
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def read_blob(client: GitHubClient, owner: str, repo: str, blob_sha: str, *,
              max_bytes: Optional[int] = None,
              repository_id=None, commit_sha=None) -> dict:
    """读取并校验一个 Git Blob。

    校验两点：
      1) 返回对象的类型必须是 blob
      2) 解码后的原始字节按 Git 规则重算 sha1 必须等于请求的 blob_sha
    """
    limit = max_bytes if max_bytes is not None else client.limits["max_blob_bytes"]
    resp = client.blob(owner, repo, blob_sha, repository_id=repository_id,
                       commit_sha=commit_sha)
    if not resp.ok:
        err = resp.error
        code = BLOB_MISSING if (err and err.error_code == "REPO_NOT_FOUND") else \
               (err.error_code if err else "UNKNOWN")
        return {"ok": False, "error_code": code,
                "error": err.to_dict() if err else None}

    d = resp.data or {}
    if d.get("encoding") != "base64":
        return {"ok": False, "error_code": MALFORMED,
                "detail": f"意外编码 {d.get('encoding')!r}（只支持 base64）"}

    try:
        raw = base64.b64decode(d.get("content", ""), validate=False)
    except Exception as e:
        return {"ok": False, "error_code": MALFORMED, "detail": f"base64 解码失败: {e}"}

    if len(raw) > limit:
        return {"ok": False, "error_code": BUDGET_EXCEEDED,
                "detail": f"blob 大小 {len(raw)} 超过上限 {limit}"}

    computed = git_blob_sha1(raw)
    verified = (computed == blob_sha)

    # 文本解码失败**不改变原始字节**
    text = None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None

    return {"ok": True, "blob_sha": blob_sha, "git_blob_sha1": computed,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw), "verified": verified,
            "is_binary": text is None,
            "content_bytes": raw,
            "content_text": text}
