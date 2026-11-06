#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收级请求编排：把整条 E2E 需要的 GitHub 请求算清，再决定是否动手。

★ P6D 的教训：预算只在采集内部生效，不管验收编排。
  结果连续三轮在 60/小时配额上反复折损。
"""

import hashlib

# 阶段
PREFLIGHT = "PREFLIGHT"
IDENTITY_VERIFIED = "IDENTITY_VERIFIED"
AUTHORIZATION_VERIFIED = "AUTHORIZATION_VERIFIED"
TREE_AVAILABLE = "TREE_AVAILABLE"
BLOBS_CAPTURED = "BLOBS_CAPTURED"
KNOWLEDGE_PERSISTED = "KNOWLEDGE_PERSISTED"
KNOWLEDGE_VERIFIED = "KNOWLEDGE_VERIFIED"
INSTALLED_SKILL_QUERY_PASSED = "INSTALLED_SKILL_QUERY_PASSED"
CARD_RENDERED = "CARD_RENDERED"
OFFLINE_REUSE_VERIFIED = "OFFLINE_REUSE_VERIFIED"

STAGE_ORDER = (PREFLIGHT, IDENTITY_VERIFIED, AUTHORIZATION_VERIFIED,
               TREE_AVAILABLE, BLOBS_CAPTURED, KNOWLEDGE_PERSISTED,
               KNOWLEDGE_VERIFIED, INSTALLED_SKILL_QUERY_PASSED,
               CARD_RENDERED, OFFLINE_REUSE_VERIFIED)

# 暂停/终止状态
PREFLIGHT_BUDGET_BLOCKED = "PREFLIGHT_BUDGET_BLOCKED"
REMOTE_RATE_LIMITED = "REMOTE_RATE_LIMITED"
AUTHORIZATION_BLOCKED = "AUTHORIZATION_BLOCKED"
BLOB_CAPTURE_INCOMPLETE = "BLOB_CAPTURE_INCOMPLETE"
FACTS_INCOMPLETE = "FACTS_INCOMPLETE"
VERIFICATION_INCOMPLETE = "VERIFICATION_INCOMPLETE"
INSTALLED_SKILL_FAILED = "INSTALLED_SKILL_FAILED"
E2E_COMPLETE = "E2E_COMPLETE"

# 节点状态
NODE_PLANNED = "PLANNED"
NODE_LOCAL_REUSE = "LOCAL_REUSE"
NODE_DONE = "DONE"
NODE_FAILED = "FAILED"
NODE_SKIPPED = "SKIPPED"

DEFAULT_LOCAL_MAX = 8
DEFAULT_RESERVE = 6
BOOTSTRAP_ENDPOINT = "GET /rate_limit"


def _nid(*parts):
    return "RN-" + hashlib.sha256(
        "|".join(str(p) for p in parts).encode()).hexdigest()[:16]


class AcceptanceRequestPlan:
    """一次验收的请求 DAG。

    ★ 关键：区分 已确定 / 依赖前序 / 可能额外 三类，
      不把未解析依赖伪造成确定值。
    """

    def __init__(self, *, repository_id, commit_sha=None,
                 local_max_requests=DEFAULT_LOCAL_MAX,
                 reserve_requests=DEFAULT_RESERVE):
        self.repository_id = str(repository_id)
        self.commit_sha = commit_sha
        self.local_max_requests = int(local_max_requests)
        self.reserve_requests = int(reserve_requests)
        self.nodes = []

    # ── 建图 ─────────────────────────────────────
    def add(self, *, operation, endpoint, source_object_identity=None,
            depends_on=(), required=True, cache_state="UNKNOWN",
            cost=1, resolved=False):
        node = {
            "request_node_id": _nid(self.repository_id, operation, endpoint,
                                    source_object_identity),
            "operation": operation,
            "endpoint": endpoint,
            "source_object_identity": source_object_identity,
            "depends_on": list(depends_on),
            "required": bool(required),
            "cache_state": cache_state,          # UNKNOWN/LOCAL_COMPLETE/ABSENT
            "estimated_primary_cost": int(cost),
            "estimated_secondary_cost_if_known": None,
            "execution_status": NODE_PLANNED,
            "actual_response_headers": None,
            "error_code": None,
            "local_reuse_reference": None,
            "dependency_resolved": bool(resolved),
        }
        self.nodes.append(node)
        return node

    def mark_reuse(self, node_id, reference):
        for n in self.nodes:
            if n["request_node_id"] == node_id:
                n["execution_status"] = NODE_LOCAL_REUSE
                n["local_reuse_reference"] = reference
                n["cache_state"] = "LOCAL_COMPLETE"
                return True
        return False

    # ── 计数 ─────────────────────────────────────
    def counts(self):
        """★ 三类分开：确定 / 条件 / 可能额外。绝不合并成一个数。

        ★ D-56：复用节点**不算请求**。此前 counts 把它算进 certain，
          而 by_operation 又排除它 → 两个函数口径不一致，
          导致"已全在本地"仍报 need=5。
        """
        certain, conditional, optional = [], [], []
        reused = [n for n in self.nodes
                  if n["execution_status"] == NODE_LOCAL_REUSE]
        for n in self.nodes:
            if n["execution_status"] == NODE_LOCAL_REUSE:
                continue          # 本地复用不发请求
            if not n["required"]:
                optional.append(n)
            elif n["dependency_resolved"]:
                certain.append(n)
            else:
                conditional.append(n)
        return {
            "certain_requests": len(certain),
            "conditional_requests": len(conditional),
            "optional_requests": len(optional),
            "local_reuse_nodes": len(reused),
            "minimum_required_requests": len(certain),
            "maximum_planned_requests": len(certain) + len(conditional),
        }

    def by_operation(self):
        out = {}
        for n in self.nodes:
            out.setdefault(n["operation"], 0)
            if n["execution_status"] != NODE_LOCAL_REUSE:
                out[n["operation"]] += 1
        return out

    def dedup_key(self, node):
        """★ 去重键：方法 + 端点 + 不可变目标身份。

        同一 Commit 的同一 Blob 只发一次；不同 Commit/仓库绝不合并。
        """
        return (node["operation"].split(" ")[0],
                node["endpoint"],
                str(node["source_object_identity"]),
                self.repository_id,
                str(self.commit_sha or ""))


def build_repo_acceptance_plan(*, repository_id=None, commit_sha=None,
                               known_tree_sha=None, target_paths=(),
                               license_path="LICENSE",
                               local_max_requests=DEFAULT_LOCAL_MAX,
                               reserve_requests=DEFAULT_RESERVE,
                               have_metadata=False, have_tree=False,
                               have_blobs=()):
    """为一次仓库验收建请求 DAG。

    ★ 已确定能省的不写进 certain；依赖前序的标 conditional。
    """
    p = AcceptanceRequestPlan(repository_id=repository_id or "UNKNOWN",
                              commit_sha=commit_sha,
                              local_max_requests=local_max_requests,
                              reserve_requests=reserve_requests)

    # ① 仓库元数据：有就不请求
    if have_metadata:
        p.add(operation="GET repo metadata", endpoint="/repos/{owner}/{repo}",
              cache_state="LOCAL_COMPLETE", resolved=True)
        p.mark_reuse(p.nodes[-1]["request_node_id"], "local:repo_metadata")
    else:
        p.add(operation="GET repo metadata", endpoint="/repos/{owner}/{repo}",
              resolved=True)

    # ② Commit：已知固定 SHA 就不请求 commit 详情（tree 可从 tree_sha 直取）
    if commit_sha:
        p.add(operation="GET commit", endpoint="/repos/{o}/{r}/commits/{sha}",
              source_object_identity=commit_sha, cache_state="LOCAL_COMPLETE",
              resolved=True, required=False)   # 有 SHA 即可，非必需
    else:
        p.add(operation="GET ref", endpoint="/repos/{o}/{r}/git/ref/heads/{b}",
              resolved=True)

    # ③ Tree：已知 root_tree_sha 就不依赖 commit 响应
    if have_tree:
        p.add(operation="GET tree", endpoint="/repos/{o}/{r}/git/trees/{t}",
              source_object_identity=known_tree_sha,
              cache_state="LOCAL_COMPLETE", resolved=True)
        p.mark_reuse(p.nodes[-1]["request_node_id"], "local:tree")
    elif known_tree_sha:
        p.add(operation="GET tree", endpoint="/repos/{o}/{r}/git/trees/{t}",
              source_object_identity=known_tree_sha, resolved=True)
    else:
        # ★ 依赖 commit 响应才能知道 tree sha
        p.add(operation="GET tree", endpoint="/repos/{o}/{r}/git/trees/{t}",
              depends_on=[n["request_node_id"] for n in p.nodes],
              resolved=False)

    # ④ Blob：OID 依赖 tree；已捕获的直接标复用
    # ★ 去重：license_path 若已在 target_paths 里，不得重复成两个节点
    _paths = list(dict.fromkeys(
        list(target_paths) + ([license_path] if license_path else [])))
    for path in _paths:
        oid_known = path in have_blobs
        if oid_known:
            p.add(operation="GET blob", endpoint="/repos/{o}/{r}/git/blobs/{oid}",
                  source_object_identity=path, cache_state="LOCAL_COMPLETE",
                  resolved=True)
            p.mark_reuse(p.nodes[-1]["request_node_id"], "local:blob:" + path)
        else:
            # OID 由 tree 提供 → 依赖 tree
            tree_nodes = [n["request_node_id"] for n in p.nodes
                          if n["operation"] == "GET tree"]
            p.add(operation="GET blob", endpoint="/repos/{o}/{r}/git/blobs/{oid}",
                  source_object_identity=path, depends_on=tree_nodes,
                  resolved=False)
    return p


def preflight(*, plan, observed_remaining, observed_reset_at=None,
              observed_resource=None, header_age_seconds=None,
              rate_limit_status=None, bootstrap_used=False):
    """全局预算预检。★ 三条件同时满足才放行。"""
    c = plan.counts()
    need = c["maximum_planned_requests"]
    reserve = plan.reserve_requests
    exec_budget = plan.local_max_requests
    reasons = []

    # 条件 1：本地整批上限
    if need > exec_budget:
        reasons.append("LOCAL_MAX_EXCEEDED")
    # 条件 3：限流态
    if rate_limit_status in ("PRIMARY", "SECONDARY"):
        reasons.append("RATE_LIMITED:" + str(rate_limit_status))
    # 条件 2：权威剩余
    # ★ D-59：need==0（全部本地复用）时不需要任何配额，也不该要求响应头。
    #   此前仍去看 remaining，导致"无需联网"的运行被误判为预算不足。
    if need > 0:
        if observed_remaining is None:
            reasons.append("NO_AUTHORITATIVE_REMAINING")
        elif int(observed_remaining) < need + reserve:
            reasons.append("INSUFFICIENT_REMAINING")
    # need==0 → 不检查剩余配额（本地即可完成）

    can_begin = not reasons
    out = {
        "planned_primary_requests": need,
        "required_minimum": c["minimum_required_requests"],
        "planned_upper_bound": c["maximum_planned_requests"],
        "local_max_requests": exec_budget,
        "observed_remaining": observed_remaining,
        "observed_reset_at": observed_reset_at,
        "observed_resource": observed_resource,
        "response_header_age": header_age_seconds,
        "reserve_requests": reserve,
        "execution_budget": exec_budget,
        "rate_limit_status": rate_limit_status,
        "can_begin": can_begin,
        "block_reason": None if can_begin else ",".join(reasons),
        "bootstrap_used": bool(bootstrap_used),
        "note": ("预检通过不等于配额已预留；匿名配额按 IP 共享，"
                 "每次请求后须按真实响应头更新"),
        "counts": c,
    }
    if not can_begin and "NO_AUTHORITATIVE_REMAINING" in reasons:
        out["next_action"] = ("允许至多一次 %s 诊断；仍为 0 则整批停止"
                              % BOOTSTRAP_ENDPOINT)
    return out


def plan_state(*, preflight_result, stage_states=None):
    if not preflight_result.get("can_begin"):
        return {"state": PREFLIGHT_BUDGET_BLOCKED,
                "stage": PREFLIGHT,
                "block_reason": preflight_result.get("block_reason")}
    last = None
    for s in STAGE_ORDER:
        if (stage_states or {}).get(s) == NODE_DONE:
            last = s
    if last == OFFLINE_REUSE_VERIFIED:
        return {"state": E2E_COMPLETE, "stage": last}
    return {"state": "IN_PROGRESS", "stage": last or PREFLIGHT,
            "completed_stages": list((stage_states or {}).keys())}
