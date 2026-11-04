#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collector 适配层：给执行器一个"按 commit sha 取数"的统一协议。

**不新建第二套 Collector。** 生产适配器直接包装现有 GitHubClient；
测试适配器提供确定性响应，provenance=SYNTHETIC_FIXTURE。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "collector")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lc_models as L


class RealGhAdapter:
    """包装 GitHubClient：只按 commit sha 取数，不做 Ref 解析。

    ★ provenance = REAL_LIVE_API（真实网络）。仅在持有真实执行授权时使用。
    """
    provenance = "REAL_LIVE_API"

    def __init__(self, client, *, owner: str, name: str):
        self.client = client
        self.owner = owner
        self.name = name

    def evidence_ref(self, commit_sha: str) -> str:
        return f"github:/repos/{self.owner}/{self.name}/commits/{commit_sha}#FIXED_COMMIT"

    def fetch_commit(self, commit_sha: str) -> dict:
        resp = self.client.commit_for_ref(self.owner, self.name, commit_sha)
        if not getattr(resp, "ok", False):
            err = getattr(resp, "error", None)
            code = getattr(err, "error_code", "NETWORK_FAILED")
            # ★ 只读 API 超时视为可重试但不确定；不冒充已成功
            uncertain = code in ("NETWORK_TIMEOUT", "SERVER_ERROR",
                                 "RATE_LIMITED", "SECONDARY_RATE_LIMITED")
            return {"ok": False, "error_code": code, "uncertain": uncertain,
                    "detail": f"commit 获取失败: {code}"}
        data = resp.data or {}
        inner = data.get("commit") or {}
        tree = inner.get("tree") or {}
        return {"ok": True, "sha": data.get("sha"),
                "tree_sha": tree.get("sha")}

    def fetch_tree(self, tree_sha: str) -> dict:
        resp = self.client.tree(self.owner, self.name, tree_sha, recursive=True)
        if not getattr(resp, "ok", False):
            err = getattr(resp, "error", None)
            code = getattr(err, "error_code", "NETWORK_FAILED")
            uncertain = code in ("NETWORK_TIMEOUT", "SERVER_ERROR",
                                 "RATE_LIMITED", "SECONDARY_RATE_LIMITED")
            return {"ok": False, "error_code": code, "uncertain": uncertain,
                    "detail": f"tree 获取失败: {code}"}
        d = resp.data or {}
        return {"ok": True, "entries": d.get("tree") or [],
                "truncated": bool(d.get("truncated"))}


class FakeGhAdapter:
    """确定性测试夹具。provenance = SYNTHETIC_FIXTURE。

    ★ 明确标记，不得冒充真实观测。
    """
    provenance = "SYNTHETIC_FIXTURE"

    def __init__(self, commits: dict, trees: dict, *,
                 commit_error: str = None, tree_error: str = None,
                 uncertain: bool = False, wrong_commit_for: str = None,
                 wrong_commit_returns: str = "f" * 40):
        self.commits = dict(commits)      # {sha: tree_sha}
        self.trees = dict(trees)          # {tree_sha: {"entries":[...], "truncated":bool}}
        self.commit_error = commit_error
        self.tree_error = tree_error
        self.uncertain = uncertain
        self.wrong_commit_for = wrong_commit_for
        self.wrong_commit_returns = wrong_commit_returns
        self.calls = []

    def evidence_ref(self, commit_sha: str) -> str:
        return f"synthetic:/commit/{commit_sha}#SYNTHETIC_FIXTURE"

    def fetch_commit(self, commit_sha: str) -> dict:
        self.calls.append(("fetch_commit", commit_sha))
        if self.commit_error:
            return {"ok": False, "error_code": self.commit_error,
                    "uncertain": self.uncertain, "detail": "夹具错误"}
        if commit_sha not in self.commits:
            return {"ok": False, "error_code": "COMMIT_NOT_FOUND",
                    "uncertain": False, "detail": "夹具无此 commit"}
        if self.wrong_commit_for == commit_sha:
            # ★ 故意返回另一个 commit（测 T-13）
            return {"ok": True, "sha": self.wrong_commit_returns,
                    "tree_sha": self.commits.get(self.wrong_commit_returns,
                                                 "2" * 40)}
        return {"ok": True, "sha": commit_sha,
                "tree_sha": self.commits[commit_sha]}

    def fetch_tree(self, tree_sha: str) -> dict:
        self.calls.append(("fetch_tree", tree_sha))
        if self.tree_error:
            return {"ok": False, "error_code": self.tree_error,
                    "uncertain": self.uncertain, "detail": "夹具错误"}
        t = self.trees.get(tree_sha)
        if t is None:
            return {"ok": False, "error_code": "TREE_NOT_FOUND",
                    "uncertain": False, "detail": "夹具无此 tree"}
        return {"ok": True, "entries": t.get("entries", []),
                "truncated": bool(t.get("truncated")),
                "tree_sha_echoed": tree_sha}
