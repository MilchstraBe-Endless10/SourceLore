#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内容采集前置授权判定（Preflight）。

★ 五个权限层次严格分开：
  可访问公开仓库 / 可读取内容 / 可为内部持久化 / 可复制到卡片 / 可对外再分发
  公开可见 ≠ 允许永久复制原文。

★ 不修改既有 copy_permitted / distribution_allowed 语义；
  本模块只新增「内部内容采集」这一独立判定。
"""

ACQ_ALLOWED = "ACQUISITION_ALLOWED"
ACQ_METADATA_ONLY = "METADATA_ONLY"
ACQ_BLOCKED = "ACQUISITION_BLOCKED"
ACQ_UNKNOWN = "AUTHORIZATION_UNKNOWN"

# 默认候选路径（仅仓库根；子目录须显式 --content-path）
DEFAULT_CANDIDATES = (
    "readme.md", "readme.markdown", "readme.txt",
    "package.json", "pyproject.toml", "cargo.toml", "go.mod",
)

# 明确不采的敏感/危险名（即使匹配白名单也拒绝）
_DENY_NAMES = frozenset({
    ".env", ".env.local", "id_rsa", "id_ed25519", ".npmrc", ".netrc",
    "credentials", "secrets.json", "secrets.yaml", "secrets.yml",
})

MAX_PATH_LEN = 255


def normalize_candidate(path: str) -> str:
    """大小写规范化，但**保留实际 Git 路径**。"""
    return path.lower()


def is_default_candidate(path: str) -> bool:
    if "/" in path:            # 只认仓库根
        return False
    base = path.lower()
    return base in DEFAULT_CANDIDATES or base in ("readme", "readme.md",
                                                   "readme.markdown",
                                                   "readme.txt")


def path_is_safe(path: str) -> bool:
    if not path or len(path) > MAX_PATH_LEN:
        return False
    if path.startswith("/") or "\\" in path:
        return False
    if ".." in path.split("/"):
        return False
    base = path.rsplit("/", 1)[-1].lower()
    if base in _DENY_NAMES:
        return False
    return True


def preflight(*, repository_id, commit_sha, file_path, object_type,
              repository_owner=None, repo_looks_third_party=True,
              copy_permitted=False, license_known=False,
              distribution_allowed=False, purpose="internal_analysis"):
    """返回 (状态, 原因码, 说明)。保守默认：未知即拒绝写入。

    ★ 关键：copy_permitted 只影响**再分发**，不决定内部采集；
      但内部采集本身也需要明确依据（license_known 或项目自有仓库）。
    """
    if not path_is_safe(file_path):
        return ACQ_BLOCKED, "PATH_UNSAFE", "路径含穿越/敏感名/超长"

    if object_type not in ("blob",):
        return ACQ_BLOCKED, "OBJECT_TYPE_NOT_ALLOWED", \
            f"仅普通 blob 可采集，收到 {object_type}"

    if not repository_id or not commit_sha:
        return ACQ_BLOCKED, "IDENTITY_INCOMPLETE", "缺少 repository_id 或 commit_sha"

    if purpose != "internal_analysis":
        return ACQ_BLOCKED, "PURPOSE_NOT_ALLOWED", \
            f"只允许 internal_analysis，收到 {purpose}"

    # 项目自有/用户明确授权的仓库：允许
    if not repo_looks_third_party:
        return ACQ_ALLOWED, "PROJECT_OWNED_REPO", \
            "项目自有或用户明确授权的仓库，允许内部采集"

    # 第三方仓库：必须有明确的许可证依据
    if not license_known:
        return ACQ_UNKNOWN, "LICENSE_UNKNOWN", \
            ("许可证或授权依据不足；不得写入原始字节，"
             "只保留路径元数据与阻断原因")

    # 有许可依据 → 允许内部采集（但分发仍受独立门禁约束）
    note = "有许可证依据，允许内部采集"
    if not copy_permitted:
        note += "；但 copy_permitted=false，不得复制原文到对外材料"
    if not distribution_allowed:
        note += "；distribution_allowed=false 保持不变"
    return ACQ_ALLOWED, "LICENSE_OBSERVED_INTERNAL_ONLY", note


def candidate_paths(tree_entries, explicit=None):
    """选出候选路径。显式指定优先；否则仅根目录白名单。

    ★ 返回 (eligible, blocked)，每个带原因。
    """
    by_path = {e.get("path"): e for e in (tree_entries or [])}
    eligible, blocked = [], []

    if explicit:
        for p in explicit:
            if not path_is_safe(p):
                blocked.append({"file_path": p, "reason": "PATH_UNSAFE"})
                continue
            e = by_path.get(p)
            if e is None:
                blocked.append({"file_path": p, "reason": "PATH_NOT_IN_SNAPSHOT"})
                continue
            eligible.append({"file_path": p, "entry": e})
        return eligible, blocked

    for e in (tree_entries or []):
        p = e.get("path")
        if not is_default_candidate(p):
            continue
        if not path_is_safe(p):
            blocked.append({"file_path": p, "reason": "PATH_UNSAFE"})
            continue
        eligible.append({"file_path": p, "entry": e})
    return eligible, blocked


# ═══════════════════════════════════════════════════════════════
# F2-P5E：五维权限分离 + 结构化授权引用
# ═══════════════════════════════════════════════════════════════

POLICY_VERSION = "content-authz/2"

# 五种动作，分别判
OP_FETCH = "fetch"
OP_PERSIST = "persist_bytes"
OP_DERIVE = "derive_facts"
OP_PREVIEW = "internal_preview"
OP_DISTRIBUTE = "external_distribution"

ALLOW = "ALLOW"
DENY = "DENY"
UNKNOWN = "UNKNOWN"

# 依据类型（结构化，不接受裸布尔）
AUTH_PROJECT_OWNED = "PROJECT_OWNED_WORK"
AUTH_ORIGINAL_FIXTURE = "ORIGINAL_TEST_FIXTURE"
AUTH_LICENSE_OBSERVED = "LICENSE_OBSERVED_AND_APPLICABLE"
AUTH_USER_GRANT = "USER_EXPLICIT_GRANT"

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"

# 每类依据允许哪些动作
_EVIDENCE_CAPS = {
    # 自有作品：全链内部动作都允许；分发永远不允许
    AUTH_PROJECT_OWNED: {OP_FETCH, OP_PERSIST, OP_DERIVE, OP_PREVIEW},
    AUTH_ORIGINAL_FIXTURE: {OP_FETCH, OP_PERSIST, OP_DERIVE, OP_PREVIEW},
    # 观测到的许可证：允许内部链路，但分发仍需独立门禁
    AUTH_LICENSE_OBSERVED: {OP_FETCH, OP_PERSIST, OP_DERIVE, OP_PREVIEW},
    AUTH_USER_GRANT: {OP_FETCH, OP_PERSIST, OP_DERIVE, OP_PREVIEW},
}


def build_authorization_ref(*, authorization_kind, repository_id, scope,
                            source, verification_status, policy_version=POLICY_VERSION,
                            authorization_ref=None):
    """构造可审计授权引用。★ 裸布尔不得直接当授权。"""
    if authorization_kind not in _EVIDENCE_CAPS:
        raise ValueError(f"未知授权类型：{authorization_kind}")
    if verification_status not in (VERIFIED, UNVERIFIED):
        raise ValueError(f"未知核验状态：{verification_status}")
    if not repository_id or not scope or not source:
        raise ValueError("授权引用必须含 repository_id / scope / source")
    return {
        "authorization_ref": authorization_ref or (
            f"SL-AUTHZ-{authorization_kind}-{repository_id}"),
        "authorization_kind": authorization_kind,
        "repository_id": str(repository_id),
        "scope": scope,
        "source": source,
        "verification_status": verification_status,
        "policy_version": policy_version,
    }


def _decision(decision, reason, *, evidence_ref=None, op=None,
              repository_id=None, commit_sha=None, file_path=None,
              limitations=None):
    return {
        "decision": decision,
        "reason_code": reason,
        "evidence_reference": evidence_ref,
        "policy_version": POLICY_VERSION,
        "repository_identity": repository_id,
        "commit_sha": commit_sha,
        "file_path": file_path,
        "permitted_operation": op,
        "limitations": limitations or [],
    }


def evaluate_operation(*, operation, repository_id, commit_sha, file_path,
                       authorization=None, object_type="blob",
                       distribution_gate_open=False):
    """★ 每维独立判定。返回一维 result dict。

    正确顺序：确定来源 → 确定对象 → 确定拟执行操作 → 权限预检。
    """
    limitations = []

    if not repository_id or not commit_sha:
        return _decision(DENY, "IDENTITY_INCOMPLETE", op=operation,
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path)
    if not path_is_safe(file_path):
        return _decision(DENY, "PATH_UNSAFE", op=operation,
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path)
    if object_type != "blob":
        return _decision(DENY, "OBJECT_TYPE_NOT_ALLOWED", op=operation,
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path,
                         limitations=[f"object_type={object_type}"])

    # 分发：恒被现有门禁阻断（B-1/B-2/B-3），除非未来独立关闭
    if operation == OP_DISTRIBUTE:
        if not distribution_gate_open:
            return _decision(DENY, "DISTRIBUTION_GATE_OPEN_BLOCKED",
                             op=operation,
                             repository_id=repository_id,
                             commit_sha=commit_sha, file_path=file_path,
                             limitations=["B-1/B-2/B-3 OPEN",
                                          "copy_permitted=false"])
        return _decision(ALLOW, "DISTRIBUTION_GATE_OPEN", op=operation,
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path)

    if authorization is None:
        return _decision(UNKNOWN, "NO_AUTHORIZATION_REF", op=operation,
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path,
                         limitations=["缺少结构化授权引用"])

    # 绑定校验：错仓库 / 错范围 → 拒绝
    if str(authorization.get("repository_id")) != str(repository_id):
        return _decision(DENY, "AUTHORIZATION_REPO_MISMATCH", op=operation,
                         evidence_ref=authorization.get("authorization_ref"),
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path)
    kind = authorization.get("authorization_kind")
    if kind not in _EVIDENCE_CAPS:
        return _decision(DENY, "AUTHORIZATION_KIND_UNKNOWN", op=operation,
                         evidence_ref=authorization.get("authorization_ref"),
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path)
    if authorization.get("verification_status") != VERIFIED:
        return _decision(UNKNOWN, "AUTHORIZATION_UNVERIFIED", op=operation,
                         evidence_ref=authorization.get("authorization_ref"),
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path,
                         limitations=["授权引用未核验"])

    allowed_ops = _EVIDENCE_CAPS[kind]
    if operation not in allowed_ops:
        return _decision(DENY, "OPERATION_NOT_COVERED", op=operation,
                         evidence_ref=authorization.get("authorization_ref"),
                         repository_id=repository_id,
                         commit_sha=commit_sha, file_path=file_path,
                         limitations=[f"{kind} 不覆盖 {operation}"])

    limitations = ["copy_permitted=false", "distribution_allowed=false"]
    if kind == AUTH_LICENSE_OBSERVED:
        limitations.append("许可证依据仅覆盖内部链路")
    return _decision(ALLOW, "AUTHORIZED_INTERNAL_ONLY", op=operation,
                     evidence_ref=authorization.get("authorization_ref"),
                     repository_id=repository_id,
                     commit_sha=commit_sha, file_path=file_path,
                     limitations=limitations)


def evaluate_all(*, repository_id, commit_sha, file_path, authorization=None,
                 object_type="blob", distribution_gate_open=False):
    """一次出五维结果。调用方必须逐维看待，不能合并。"""
    return {
        "FETCH_DECISION": evaluate_operation(
            operation=OP_FETCH, repository_id=repository_id,
            commit_sha=commit_sha, file_path=file_path,
            authorization=authorization, object_type=object_type),
        "PERSIST_DECISION": evaluate_operation(
            operation=OP_PERSIST, repository_id=repository_id,
            commit_sha=commit_sha, file_path=file_path,
            authorization=authorization, object_type=object_type),
        "DERIVE_FACTS_DECISION": evaluate_operation(
            operation=OP_DERIVE, repository_id=repository_id,
            commit_sha=commit_sha, file_path=file_path,
            authorization=authorization, object_type=object_type),
        "PREVIEW_DECISION": evaluate_operation(
            operation=OP_PREVIEW, repository_id=repository_id,
            commit_sha=commit_sha, file_path=file_path,
            authorization=authorization, object_type=object_type),
        "DISTRIBUTION_DECISION": evaluate_operation(
            operation=OP_DISTRIBUTE, repository_id=repository_id,
            commit_sha=commit_sha, file_path=file_path,
            authorization=authorization, object_type=object_type,
            distribution_gate_open=distribution_gate_open),
    }
