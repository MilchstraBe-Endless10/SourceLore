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
