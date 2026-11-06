#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 请求预算：本地计划上限 + 最近响应头 + 每次请求后重新评估。

★ 核心约束：本地记录**不等于**网络侧真实剩余配额。
  匿名配额按来源 IP 计算，其他进程也在消耗。
  所以绝不使用 `60 - 自己记录的请求数` 推断剩余。
"""

DEFAULT_REQUEST_LIMIT = 8      # 单次真实采集最多 8 个请求
DEFAULT_RESERVE = 5            # 优先保留至少 5 次主配额

BUDGET_OK = "BUDGET_OK"
BUDGET_INSUFFICIENT = "REQUEST_BUDGET_INSUFFICIENT"
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
BUDGET_RATE_LIMITED = "BUDGET_RATE_LIMITED"

PRIMARY = "PRIMARY"
SECONDARY = "SECONDARY"
UNKNOWN_KIND = "UNKNOWN"

# 计划项结果
RESULT_NOT_RUN = "NOT_RUN"
RESULT_SUCCESS = "SUCCESS"
RESULT_CACHE_HIT = "CACHE_HIT"
RESULT_RATE_LIMITED = "RATE_LIMITED"
RESULT_HTTP_ERROR = "HTTP_ERROR"
RESULT_SKIPPED_BUDGET = "SKIPPED_BUDGET_INSUFFICIENT"


def classify_rate_limit(*, status, headers=None, message=""):
    """主限流 vs 次级限流 —— 不能只看 403。

    ★ 主限流：remaining=0 且 used=limit（或 remaining=0 且 reset 存在）
    ★ 次级限流：有 Retry-After，且 remaining 通常非 0
    两者都缺 → UNKNOWN（不要猜）
    """
    h = {str(k).lower(): v for k, v in (headers or {}).items()}
    remaining = h.get("x-ratelimit-remaining")
    used = h.get("x-ratelimit-used")
    limit = h.get("x-ratelimit-limit")
    retry_after = h.get("retry-after")
    msg = (message or "").lower()

    if retry_after is not None and str(retry_after).strip() != "":
        return SECONDARY
    if remaining is not None and str(remaining).strip().isdigit() \
            and int(remaining) == 0:
        return PRIMARY
    if used is not None and limit is not None \
            and str(used).strip().isdigit() and str(limit).strip().isdigit() \
            and int(used) >= int(limit):
        return PRIMARY
    if "secondary rate limit" in msg or "abuse detection" in msg:
        return SECONDARY
    if "rate limit" in msg or "rate_limit" in msg:
        return UNKNOWN_KIND
    if status == 403 or status == 429:
        return UNKNOWN_KIND
    return None


def parse_headers(headers):
    """从响应头提取权威计数。★ 只取 GitHub 明确给出的字段。"""
    h = {str(k).lower(): v for k, v in (headers or {}).items()}
    out = {}
    for src, dst in (("x-ratelimit-limit", "observed_limit"),
                     ("x-ratelimit-remaining", "observed_remaining"),
                     ("x-ratelimit-reset", "reset_at"),
                     ("x-ratelimit-resource", "observed_resource"),
                     ("x-ratelimit-used", "observed_used"),
                     ("retry-after", "retry_after")):
        v = h.get(src)
        if v is None:
            continue
        s = str(v).strip()
        out[dst] = int(s) if s.isdigit() else s
    return out


class GitHubRequestBudget:
    """一次采集执行单元的预算状态。

    ★ 三类"剩余"必须分开，绝不合并：
      - request_limit      本地单次上限
      - consumed_requests  本次实际发出
      - observed_remaining 最近响应头给的真实剩余（可能被其他进程改变）
    """

    def __init__(self, *, repository_id, commit_sha, execution_id,
                 request_limit=DEFAULT_REQUEST_LIMIT,
                 reserve_requests=DEFAULT_RESERVE):
        self.repository_id = str(repository_id)
        self.commit_sha = str(commit_sha)
        self.execution_id = execution_id
        self.request_limit = int(request_limit)
        self.reserve_requests = int(reserve_requests)
        self.consumed_requests = 0
        self.planned_requests = 0
        self.observed_limit = None
        self.observed_remaining = None
        self.observed_resource = None
        self.reset_at = None
        self.last_response_at = None
        self.rate_limit_kind = None
        self.plan = []
        self.blocked_reason = None

    # ── 计划 ─────────────────────────────────────
    def add_plan_item(self, *, endpoint, intended_object, purpose,
                      required=True, dependency=None,
                      cache_hit=False,
                      estimated_primary_cost=1):
        item = {
            "endpoint": endpoint,
            "intended_object": intended_object,
            "purpose": purpose,
            "required_or_optional": "required" if required else "optional",
            "dependency": dependency,
            "estimated_primary_cost": int(estimated_primary_cost),
            "cache_hit": bool(cache_hit),
            "result": RESULT_NOT_RUN,
            "actual_rate_limit_headers": None,
        }
        self.plan.append(item)
        if not cache_hit and required:
            self.planned_requests += int(estimated_primary_cost)
        return item

    # ── 观察 ─────────────────────────────────────
    def observe(self, *, headers=None, status=None, at=None,
                message="", result=None):
        """每次请求后调用。★ 用响应头覆盖本地推断。"""
        obs = parse_headers(headers)
        for k in ("observed_limit", "observed_remaining",
                  "observed_resource", "reset_at", "observed_used"):
            if k in obs:
                setattr(self, k, obs[k])
        if "retry_after" in obs:
            self.rate_limit_kind = SECONDARY
        elif status in (403, 429):
            kind = classify_rate_limit(status=status, headers=headers,
                                       message=message)
            if kind:
                self.rate_limit_kind = kind
        self.last_response_at = at
        return obs

    def consume(self, item=None, *, headers=None, status=None,
                result=RESULT_SUCCESS, at=None, message=""):
        """记一次实际请求。"""
        self.consumed_requests += 1
        obs = self.observe(headers=headers, status=status, at=at,
                           message=message)
        if item is not None:
            item["result"] = result
            item["actual_rate_limit_headers"] = obs
        return obs

    # ── 判定 ─────────────────────────────────────
    def effective_remaining(self):
        """可用的真实剩余。

        ★ 优先用响应头；没有响应头时**不下结论**，返回 None。
        """
        if self.observed_remaining is not None:
            return int(self.observed_remaining)
        return None

    def can_spend(self, cost=1):
        """能否再花 cost 次主配额。

        ★ 三重闸门：
          1) 本次执行没超本地上限
          2) 真实剩余 ≥ cost + reserve
          3) 未处于限流态
        没有权威响应头时 → 视为不足（宁可不发）。
        """
        if self.rate_limit_kind in (PRIMARY, SECONDARY):
            return False, BUDGET_RATE_LIMITED
        if self.consumed_requests + cost > self.request_limit:
            return False, BUDGET_EXHAUSTED
        real = self.effective_remaining()
        if real is None:
            return False, BUDGET_INSUFFICIENT
        if real < cost + self.reserve_requests:
            return False, BUDGET_INSUFFICIENT
        return True, BUDGET_OK

    def to_dict(self):
        real = self.effective_remaining()
        return {
            "repository_id": self.repository_id,
            "commit_sha": self.commit_sha,
            "execution_id": self.execution_id,
            "request_limit": self.request_limit,
            "consumed_requests": self.consumed_requests,
            "planned_requests": self.planned_requests,
            # ★ 明确标注：这是估计，不是 GitHub 官方剩余
            "estimated_remaining": (None if real is None
                                    else max(0, real - self.consumed_requests)),
            "reserve_requests": self.reserve_requests,
            "reset_at": self.reset_at,
            "observed_limit": self.observed_limit,
            "observed_remaining": self.observed_remaining,
            "observed_resource": self.observed_resource,
            "last_response_at": self.last_response_at,
            "rate_limit_kind": self.rate_limit_kind,
            "budget_state": self._state(),
            "authoritative_remaining_is_from_headers":
                self.observed_remaining is not None,
            "note": "本地记录不等于网络侧真实配额；剩余以最近响应头为准",
            "plan": self.plan,
        }

    def _state(self):
        if self.rate_limit_kind in (PRIMARY, SECONDARY):
            return BUDGET_RATE_LIMITED
        if self.consumed_requests >= self.request_limit:
            return BUDGET_EXHAUSTED
        real = self.effective_remaining()
        if real is None:
            return BUDGET_INSUFFICIENT
        if real < self.planned_requests + self.reserve_requests:
            return BUDGET_INSUFFICIENT
        return BUDGET_OK
