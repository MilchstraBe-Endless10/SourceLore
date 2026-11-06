#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收执行协调：把 DAG 节点实际跑起来，边跑边按真实响应头更新预算。

★「事务式」指可恢复的工作流编排，不声称网络/文件系统/SQLite 有全局 ACID。
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in ("collector", "storage", "runtime", "content", "content_persistence",
           "source_analysis", "facts", "evidence_claims", "skill_interface"):
    _sp = str(_ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

API = "https://api.github.com"
UA = {"User-Agent": "SourceLore-P6E", "Accept": "application/vnd.github+json"}
HDR_KEYS = ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset",
            "X-RateLimit-Resource", "X-RateLimit-Used", "Retry-After")


class BudgetExhausted(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class Coordinator:
    def __init__(self, *, budget, dry_run=False):
        self.budget = budget          # GitHubRequestBudget
        self.dry_run = dry_run
        self.calls = []
        self.reused = []
        self.bootstrap_used = False

    # ── 单次请求 ────────────────────────────────
    def call(self, *, path, purpose, object_identity=None, optional=False):
        ok, reason = self.budget.can_spend(1)
        if not ok:
            if optional:
                return None
            raise BudgetExhausted(reason)
        if self.dry_run:
            return None
        url = API + path
        req = urllib.request.Request(url, headers=UA)
        status, headers, body = None, {}, ""
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                status = r.status
                headers = dict(r.headers)
                body = r.read()
        except urllib.error.HTTPError as e:
            status = e.code
            headers = dict(e.headers)
            body = (e.read() or b"")
        except Exception as e:
            self.budget.consume(headers={}, status=None,
                                result="TRANSPORT_ERROR",
                                at=time.time(), message=str(e))
            raise
        obs = self.budget.consume(headers=headers, status=status,
                                  result="SUCCESS" if status == 200 else "HTTP_ERROR",
                                  at=time.time())
        self.calls.append({
            "endpoint": path, "purpose": purpose,
            "object_identity": object_identity, "status": status,
            "rate_limit": {k: obs.get(v) for k, v in
                           (("limit", "observed_limit"),
                            ("remaining", "observed_remaining"),
                            ("reset", "reset_at")) if obs.get(v) is not None},
            "resource": obs.get("observed_resource"),
            "success": status == 200,
        })
        if status != 200:
            from request_budget import classify_rate_limit
            kind = classify_rate_limit(status=status, headers=headers)
            if kind:
                self.budget.rate_limit_kind = kind
                raise BudgetExhausted("RATE_LIMITED:" + kind)
            raise RuntimeError("HTTP %s on %s" % (status, path))
        return json.loads(body.decode()) if body else {}

    def bootstrap_rate_limit(self):
        """★ D-57：计划器允许至多一次 /rate_limit 诊断，
        但执行器原本没有这个动作 → 首次 can_spend 恒 False，永远不发第一个请求。

        只发一次，不循环。仍为 0 就交回调用方整批停止。
        """
        if self.bootstrap_used:
            raise BudgetExhausted("BOOTSTRAP_ALREADY_USED")
        # ★ 这一发不受 can_spend 约束（正是为了取得权威响应头）
        self.bootstrap_used = True
        url = API + "/rate_limit"
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                status, headers = r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            status, headers = e.code, dict(e.headers)
        self.budget.consume(headers=headers, status=status, result="BOOTSTRAP",
                            at=time.time())
        self.calls.append({"endpoint": "/rate_limit", "purpose": "bootstrap",
                           "object_identity": None, "status": status,
                           "success": status == 200, "is_bootstrap": True})
        return {"status": status,
                "observed_remaining": self.budget.observed_remaining,
                "reset_at": self.budget.reset_at,
                "resource": self.budget.observed_resource}

    def summary(self):
        d = self.budget.to_dict()
        d["actual_requests"] = len(self.calls)
        d["calls"] = self.calls
        d["reused_local_assets"] = len(self.reused)
        d["duplicate_remote_requests"] = self._duplicates()
        return d

    def _duplicates(self):
        seen, dup = set(), 0
        for c in self.calls:
            k = (c["endpoint"], str(c["object_identity"]))
            if k in seen:
                dup += 1
            seen.add(k)
        return dup


def run_repo_identity(*, coord, owner, repo, ref=None):
    """最小身份请求：metadata（含 default_branch）→ ref → commit → tree。

    ★ 若已知固定 commit，跳过 ref。
    """
    meta = coord.call(path="/repos/%s/%s" % (owner, repo),
                      purpose="repository_metadata")
    out = {"repository_id": meta.get("id"), "full_name": meta.get("full_name"),
           "default_branch": meta.get("default_branch"),
           "license": (meta.get("license") or {}).get("spdx_id")}
    branch = ref or meta.get("default_branch") or "HEAD"
    refobj = coord.call(path="/repos/%s/%s/git/ref/heads/%s" % (owner, repo, branch),
                        purpose="resolve_ref")
    commit_sha = (refobj.get("object") or {}).get("sha")
    out["commit_sha"] = commit_sha
    c = coord.call(path="/repos/%s/%s/commits/%s" % (owner, repo, commit_sha),
                   purpose="commit_detail")
    out["root_tree_sha"] = ((c.get("commit") or {}).get("tree") or {}).get("sha")
    out["commit_date"] = ((c.get("commit") or {}).get("committer") or {}).get("date")
    t = coord.call(path="/repos/%s/%s/git/trees/%s"
                   % (owner, repo, out["root_tree_sha"]), purpose="root_tree")
    out["tree_entries"] = [{"path": e["path"], "sha": e["sha"],
                            "size": e.get("size"), "type": e["type"],
                            "mode": e.get("mode")}
                           for e in (t.get("tree") or [])]
    out["truncated"] = bool(t.get("truncated"))
    return out
