#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub REST 客户端：受限、受限流感知、错误分类。

契约：SL-CAP-0011～0019（Collector）。

**铁律：**
  G1 只访问**经验证**的 api.github.com 端点，绝不把用户输入当 URL 交给通用下载器
  G2 401/403/404/429/5xx **不得**全部折成"空仓库"，必须按响应头与响应体分类
  G3 限流判定要看 `x-ratelimit-remaining` / `retry-after` / 响应体 message，不只看状态码
  G4 有限次重试 + 退避；**禁止无界重试**，**禁止绕过**限流
  G5 Token 绝不进日志 / checkpoint / snapshot / 提交

**次级限流（secondary rate limit）与主限流要分开：**
  - 主限流：403 且 `x-ratelimit-remaining: 0`
  - 次级限流：403/429 但 remaining > 0，或响应体含 "secondary rate limit"
"""

import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

# ── 只允许这一个主机（G1）────────────────────────────────
ALLOWED_HOST = "api.github.com"
ALLOWED_SCHEME = "https"

# ── 默认资源上限（全部可配置，且都有测试）──────────────
DEFAULT_LIMITS = {
    "request_timeout": 20,          # 单次请求超时（秒）
    "max_requests": 40,             # 单次采集最大请求数
    "max_retries": 3,               # 单次请求最大重试次数
    "max_retry_after": 120,         # 服务端建议等待的上限（秒）
    "max_tree_entries": 2000,       # 最大 Tree 条目数
    "max_blob_bytes": 1_000_000,    # 单 Blob 字节上限
    "max_total_bytes": 4_000_000,   # 采集总字节上限
    "max_depth": 12,                # 递归遍历深度上限
}

# ── 错误码（与执行状态正交）──────────────────────────────
OK = "OK"
NOT_FOUND = "REPO_NOT_FOUND"
FORBIDDEN = "PERMISSION_DENIED"
UNAUTHORIZED = "AUTH_FAILED"
RATE_LIMITED = "RATE_LIMITED"
SECONDARY_RATE_LIMITED = "SECONDARY_RATE_LIMITED"
TIMEOUT = "NETWORK_TIMEOUT"
NETWORK_ERROR = "NETWORK_ERROR"
SERVER_ERROR = "SERVER_ERROR"
MALFORMED = "MALFORMED_RESPONSE"
TRUNCATED = "TREE_TRUNCATED"
BLOB_MISSING = "BLOB_MISSING"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

RETRYABLE = frozenset({RATE_LIMITED, SECONDARY_RATE_LIMITED, TIMEOUT,
                       NETWORK_ERROR, SERVER_ERROR})

# 仅限非生产用的默认 UA；不含任何凭据
USER_AGENT = "SourceLore-Collector/1.0 (+local-probe)"


@dataclass
class GhError:
    error_code: str
    request_stage: str
    repository_id: Optional[str] = None
    commit_sha: Optional[str] = None
    retryable: bool = False
    retry_after: Optional[int] = None
    evidence_ref: Optional[str] = None
    http_status: Optional[int] = None
    detail: str = ""

    def to_dict(self) -> dict:
        return {"error_code": self.error_code, "request_stage": self.request_stage,
                "repository_id": self.repository_id, "commit_sha": self.commit_sha,
                "retryable": self.retryable, "retry_after": self.retry_after,
                "evidence_ref": self.evidence_ref, "http_status": self.http_status,
                "detail": self.detail}


@dataclass
class GhResponse:
    ok: bool
    status: int = 0
    data: Optional[dict] = None
    error: Optional[GhError] = None
    headers: dict = field(default_factory=dict)
    body_bytes: int = 0


class GitHubClient:
    """受限 GitHub 客户端。

    只认识 api.github.com；token 从环境读，**绝不写日志**。
    """

    def __init__(self, *, token: Optional[str] = None, limits: Optional[dict] = None,
                 max_retries: Optional[int] = None):
        self.limits = dict(DEFAULT_LIMITS)
        if limits:
            self.limits.update(limits)
        if max_retries is not None:
            self.limits["max_retries"] = max_retries
        # token 只放内存，且不提供任何 getter 输出其值
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self.request_count = 0
        self.total_bytes = 0
        self._sleep = time.sleep     # 测试可替换，避免真等待

    # ── 安全 URL 构造（G1）───────────────────────────────────
    def _build_url(self, path: str, params: Optional[dict] = None) -> str:
        if not path.startswith("/"):
            raise PermissionError(f"路径必须以 / 开头: {path!r}")
        # 协议相对路径 //host 会把主机替换掉 —— 必须在拼 URL 前拒绝
        if path.startswith("//"):
            raise PermissionError(f"拒绝协议相对路径（可替换主机）: {path!r}")
        if ".." in path.split("/"):
            raise PermissionError(f"路径含父目录穿越: {path!r}")
        if "//" in path:
            raise PermissionError(f"路径含空段: {path!r}")
        url = f"{ALLOWED_SCHEME}://{ALLOWED_HOST}{path}"
        if params:
            q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
            url += "?" + q
        # 再次确认主机未被参数污染
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if parts.hostname != ALLOWED_HOST or parts.scheme != ALLOWED_SCHEME:
            raise PermissionError(f"拒绝非 GitHub API 目标: {url}")
        return url

    # ── 单次请求（含有限重试）───────────────────────────────
    def get(self, path: str, *, params: Optional[dict] = None,
            stage: str = "generic",
            repository_id: Optional[str] = None,
            commit_sha: Optional[str] = None,
            accept: str = "application/vnd.github+json") -> GhResponse:
        if self.request_count >= self.limits["max_requests"]:
            return GhResponse(ok=False, error=GhError(
                error_code=BUDGET_EXCEEDED, request_stage=stage,
                repository_id=repository_id, commit_sha=commit_sha,
                detail=f"已用请求数 {self.request_count} 达到上限 "
                       f"{self.limits['max_requests']}"))

        url = self._build_url(path, params)
        attempts = 0
        last: Optional[GhResponse] = None

        while attempts <= self.limits["max_retries"]:
            attempts += 1
            self.request_count += 1
            resp = self._do_request(url, stage, repository_id, commit_sha, accept)
            last = resp
            if resp.ok:
                return resp
            err = resp.error
            if err is None or not err.retryable:
                return resp
            # 有界退避：服务端 retry_after 优先，但不超过上限
            if attempts > self.limits["max_retries"]:
                break
            wait = err.retry_after
            if wait is None:
                wait = min(2 ** (attempts - 1), 8)
            wait = min(wait, self.limits["max_retry_after"])
            self._sleep(wait)
        return last

    def _do_request(self, url, stage, repository_id, commit_sha, accept) -> GhResponse:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", accept)
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if self._token:
            # 只在内存中组装，不落任何日志
            req.add_header("Authorization", f"Bearer {self._token}")

        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=self.limits["request_timeout"],
                                        context=ctx) as r:
                raw = r.read()
                self.total_bytes += len(raw)
                if self.total_bytes > self.limits["max_total_bytes"]:
                    return GhResponse(ok=False, status=r.status, error=GhError(
                        error_code=BUDGET_EXCEEDED, request_stage=stage,
                        repository_id=repository_id, commit_sha=commit_sha,
                        detail=f"累计字节 {self.total_bytes} 超过上限 "
                               f"{self.limits['max_total_bytes']}"))
                hdrs = {k.lower(): v for k, v in r.headers.items()}
                try:
                    data = json.loads(raw.decode("utf-8"))
                except Exception as e:
                    return GhResponse(ok=False, status=r.status, headers=hdrs,
                                      body_bytes=len(raw), error=GhError(
                        error_code=MALFORMED, request_stage=stage,
                        repository_id=repository_id, commit_sha=commit_sha,
                        http_status=r.status, detail=f"JSON 解析失败: {e}"))
                return GhResponse(ok=True, status=r.status, data=data,
                                  headers=hdrs, body_bytes=len(raw))

        except urllib.error.HTTPError as e:
            hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
            body = b""
            try:
                body = e.read()
            except Exception:
                pass
            self.total_bytes += len(body)
            code, retry_after, detail = self._classify_http(e.code, hdrs, body, stage)
            return GhResponse(ok=False, status=e.code, headers=hdrs,
                              body_bytes=len(body),
                              error=GhError(error_code=code, request_stage=stage,
                                            repository_id=repository_id,
                                            commit_sha=commit_sha,
                                            retryable=(code in RETRYABLE),
                                            retry_after=retry_after,
                                            http_status=e.code, detail=detail))

        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            is_timeout = isinstance(reason, (TimeoutError, OSError)) and \
                ("timed out" in str(reason).lower() or "timeout" in str(reason).lower())
            code = TIMEOUT if is_timeout else NETWORK_ERROR
            return GhResponse(ok=False, error=GhError(
                error_code=code, request_stage=stage,
                repository_id=repository_id, commit_sha=commit_sha,
                retryable=True, detail=str(reason)[:200]))

        except (TimeoutError, OSError) as e:
            msg = str(e).lower()
            code = TIMEOUT if "timeout" in msg or "timed out" in msg else NETWORK_ERROR
            return GhResponse(ok=False, error=GhError(
                error_code=code, request_stage=stage, repository_id=repository_id,
                commit_sha=commit_sha, retryable=True, detail=str(e)[:200]))

    # ── 错误分类（G2/G3）────────────────────────────────────
    def _classify_http(self, status: int, hdrs: dict, body: bytes, stage: str) -> tuple:
        """返回 (error_code, retry_after, detail)。"""
        msg = ""
        try:
            j = json.loads(body.decode("utf-8"))
            msg = str(j.get("message", ""))
        except Exception:
            msg = body[:200].decode("utf-8", "replace")

        remaining = hdrs.get("x-ratelimit-remaining")
        reset = hdrs.get("x-ratelimit-reset")
        retry_after_h = hdrs.get("retry-after")

        def _ra():
            if retry_after_h:
                try: return int(retry_after_h)
                except Exception: return None
            if reset:
                try:
                    return max(0, int(reset) - int(time.time()))
                except Exception: return None
            return None

        low = msg.lower()

        if status == 401:
            return UNAUTHORIZED, None, f"认证失败: {msg[:120]}"
        if status == 404:
            return NOT_FOUND, None, f"资源不存在: {msg[:120]}"
        if status == 403:
            # 主限流：remaining 为 0
            if remaining is not None and remaining.isdigit() and int(remaining) == 0:
                return RATE_LIMITED, _ra(), f"主限流已耗尽: {msg[:120]}"
            # 次级限流：403 + 响应体提及 secondary / abuse
            if "secondary rate limit" in low or "abuse" in low:
                return SECONDARY_RATE_LIMITED, _ra(), f"次级限流: {msg[:120]}"
            return FORBIDDEN, None, f"权限不足: {msg[:120]}"
        if status == 429:
            return SECONDARY_RATE_LIMITED, _ra(), f"429 限流: {msg[:120]}"
        if 500 <= status < 600:
            return SERVER_ERROR, _ra(), f"服务端错误 {status}: {msg[:120]}"
        return MALFORMED, None, f"意外状态 {status}: {msg[:120]}"

    # ── 便捷方法 ────────────────────────────────────────────
    def repo(self, owner: str, name: str) -> GhResponse:
        return self.get(f"/repos/{owner}/{name}", stage="repo_identity")

    def commit_for_ref(self, owner: str, name: str, ref: str) -> GhResponse:
        return self.get(f"/repos/{owner}/{name}/commits/{ref}", stage="resolve_ref")

    def tree(self, owner: str, name: str, tree_ref: str, *,
             recursive: bool = False, repository_id=None, commit_sha=None) -> GhResponse:
        params = {"recursive": "1"} if recursive else None
        return self.get(f"/repos/{owner}/{name}/git/trees/{tree_ref}",
                        params=params, stage="tree_fetch",
                        repository_id=repository_id, commit_sha=commit_sha)

    def blob(self, owner: str, name: str, blob_sha: str, *,
             repository_id=None, commit_sha=None) -> GhResponse:
        return self.get(f"/repos/{owner}/{name}/git/blobs/{blob_sha}",
                        stage="blob_fetch", repository_id=repository_id,
                        commit_sha=commit_sha)
