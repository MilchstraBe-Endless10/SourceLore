#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ResearchQuery：确定性研究问题。

★ 只支持**显式结构化查询**。自然语言问题只走有限的模板映射，
  不假装实现了通用语义理解。
"""

import sys
import hashlib
import json
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "views"), str(_HERE.parent / "lifecycle")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

QUERY_SCHEMA_VERSION = "research-query/1"
QUERY_RULE_VERSION = "query-rule/1"

# ── 三类问题（题面 §4）──────────────────────────────────────
Q_PATH_CLAIM = "PATH_EXISTENCE"        # Q-A：路径命题研究
Q_KNOWN_CLAIMS = "KNOWN_CLAIMS"        # Q-B：已验证知识检索
Q_VERSION_COMPARE = "VERSION_COMPARE"  # Q-C：历史版本对照
QUESTION_TYPES = frozenset({Q_PATH_CLAIM, Q_KNOWN_CLAIMS, Q_VERSION_COMPARE})

# 冻结 canonical 对应
CANONICAL_MAP = {
    Q_PATH_CLAIM: ["SL-CAP-0039"],
    Q_KNOWN_CLAIMS: ["SL-CAP-0037", "SL-CAP-0039"],
    Q_VERSION_COMPARE: ["SL-CAP-0037", "SL-CAP-0038"],
}

# ── 拒绝原因码 ────────────────────────────────────────────
R_BAD_TYPE = "UNKNOWN_QUESTION_TYPE"
R_NO_REPO = "MISSING_REPOSITORY_ID"
R_NO_COMMIT = "MISSING_COMMIT_SHA"
R_BAD_COMMIT = "INVALID_COMMIT_SHA"
R_NO_PATH = "MISSING_PATH"
R_BAD_PATH = "INVALID_PATH"
R_TOO_LONG = "FIELD_TOO_LONG"
R_BAD_LIMIT = "INVALID_MAX_RESULTS"
R_UNCLEAN = "UNSAFE_CHARACTERS"
R_NEED_TWO_COMMITS = "VERSION_COMPARE_NEEDS_TWO_COMMITS"

MAX_TEXT = 4000
MAX_PATH = 240
MAX_RESULTS_CAP = 200

# ★ 控制字符与双向文本符（与 renderer 同口径）
_CTRL = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f"
    "\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")
# 路径只允许相对路径字符；拒绝绝对路径、..、空字节
_SAFE_PATH = re.compile(r"^[^/\\\x00][^\\\x00]*$")

# ★ 显式拒绝的可疑形态（题面 §3：不可信查询不得变成 SQL/Shell/网络命令）
_DANGEROUS = re.compile(
    r"(^\s*(javascript|data|vbscript|file|about)\s*:)"   # URL scheme
    r"|([<>])"                                            # HTML 尖括号
    r"|(;\s*(drop|delete|insert|update|select)\b)"       # SQL 语句
    r"|(\b(union\s+select|or\s+1\s*=\s*1)\b)"
    r"|([`$]\()"                                          # Shell $() 替换
    r"|(`)"                                               # Shell 反引号
    r"|(&&|\|\|)",                                      # Shell 串联
    re.I)


def clean(value, *, limit: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return _CTRL.sub("", value)[:limit]


def normalize_path(value) -> str:
    """路径规范化。★ 不接受的形态直接抛 ValueError，不猜测。"""
    raw = clean(value, limit=MAX_PATH).strip()
    if not raw:
        raise ValueError(R_NO_PATH)
    if raw.startswith("/") or raw.startswith("\\"):
        raise ValueError(R_BAD_PATH)          # 绝对路径
    if ".." in raw.split("/"):
        raise ValueError(R_BAD_PATH)          # 路径穿越
    if not _SAFE_PATH.match(raw):
        raise ValueError(R_BAD_PATH)
    # ★ 即使形态"像"相对路径，可疑内容一律拒绝（不做启发式放行）
    if _DANGEROUS.search(raw):
        raise ValueError(R_BAD_PATH)
    return raw


def is_commit_sha(value) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value))


class QueryError(ValueError):
    def __init__(self, reason, detail=""):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def build_query(*, question_type, repository_id, commit_sha=None,
                subject_id=None, requested_ref=None, path=None,
                compare_commit_sha=None, claim_type=None,
                verification_status=None, max_results=50,
                evidence_policy="REQUIRE_REFS",
                provenance_policy="PRESERVE_ALL",
                retrieval_scope="REPOSITORY_COMMIT") -> dict:
    """构造 ResearchQuery。**规范化确定性**：同输入同 query_id。"""
    qt = clean(question_type, limit=64)
    if qt not in QUESTION_TYPES:
        raise QueryError(R_BAD_TYPE, qt)

    repo = clean(repository_id, limit=128).strip()
    if not repo:
        raise QueryError(R_NO_REPO)

    commit = clean(commit_sha, limit=64).strip() if commit_sha else None
    if commit is not None and not is_commit_sha(commit):
        raise QueryError(R_BAD_COMMIT, commit)

    cmp_commit = (clean(compare_commit_sha, limit=64).strip()
                  if compare_commit_sha else None)
    if cmp_commit is not None and not is_commit_sha(cmp_commit):
        raise QueryError(R_BAD_COMMIT, cmp_commit)

    if qt == Q_PATH_CLAIM:
        if commit is None:
            raise QueryError(R_NO_COMMIT, "PATH_EXISTENCE 需要 commit_sha")
    if qt == Q_VERSION_COMPARE:
        if not (commit and cmp_commit):
            raise QueryError(R_NEED_TWO_COMMITS,
                             "VERSION_COMPARE 需要两个 Commit")

    norm_path = None
    if path is not None:
        try:
            norm_path = normalize_path(path)
        except ValueError as e:
            raise QueryError(getattr(e, "args", ["INVALID_PATH"])[0],
                             str(path))

    if not isinstance(max_results, int) or max_results < 1:
        raise QueryError(R_BAD_LIMIT, str(max_results))
    max_results = min(max_results, MAX_RESULTS_CAP)

    q = {
        "query_schema_version": QUERY_SCHEMA_VERSION,
        "query_rule_version": QUERY_RULE_VERSION,
        "question_type": qt,
        "canonical_refs": list(CANONICAL_MAP[qt]),
        "repository_id": repo,
        "subject_id": clean(subject_id, limit=128) if subject_id else None,
        "commit_sha": commit,
        "compare_commit_sha": cmp_commit,
        "requested_ref": clean(requested_ref, limit=128) if requested_ref else None,
        "path": norm_path,
        "claim_type": clean(claim_type, limit=64) if claim_type else None,
        "verification_status": (clean(verification_status, limit=32)
                                if verification_status else None),
        "retrieval_scope": clean(retrieval_scope, limit=64),
        "max_results": max_results,
        "evidence_policy": clean(evidence_policy, limit=64),
        "provenance_policy": clean(provenance_policy, limit=64),
    }
    q["query_id"] = make_query_id(q)
    return q


def make_query_id(q: dict) -> str:
    """★ 身份只由规范化字段决定：不含时间戳、顺序无关。"""
    core = {k: v for k, v in q.items() if k not in ("query_id",)}
    if "canonical_refs" in core:
        core["canonical_refs"] = sorted(core["canonical_refs"])
    raw = json.dumps(core, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return "SL-Q-" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def from_dict(d: dict) -> dict:
    """重建并校验（用于回放/回归：身份必须复算一致）。"""
    return build_query(
        question_type=d.get("question_type"),
        repository_id=d.get("repository_id"),
        commit_sha=d.get("commit_sha"),
        subject_id=d.get("subject_id"),
        requested_ref=d.get("requested_ref"),
        path=d.get("path"),
        compare_commit_sha=d.get("compare_commit_sha"),
        claim_type=d.get("claim_type"),
        verification_status=d.get("verification_status"),
        max_results=d.get("max_results", 50),
        evidence_policy=d.get("evidence_policy", "REQUIRE_REFS"),
        provenance_policy=d.get("provenance_policy", "PRESERVE_ALL"),
        retrieval_scope=d.get("retrieval_scope", "REPOSITORY_COMMIT"))


# ── 自然语言模板映射（有限、显式）─────────────────────────
# ★ 只识别少数固定句式；识别不了就明确拒绝，不做模糊猜测。
_TEMPLATES = (
    (Q_PATH_CLAIM,
     re.compile(r"(?:在|对于)?\s*Commit\s*(?P<commit>[0-9a-f]{40})\s*中"
                r"[，,]?\s*(?P<path>[^\s，,。?？]+)\s*是否存在")),
    (Q_KNOWN_CLAIMS,
     re.compile(r"(?:仓库\s*(?P<repo>[^\s，,]+)\s*在\s*)?Commit\s*"
                r"(?P<commit>[0-9a-f]{40})\s*(?:有哪些|有什么)已登记(?:的)?Claim")),
    (Q_VERSION_COMPARE,
     re.compile(r"(?P<path>[^\s，,。]+)\s*在\s*Commit\s*(?P<c1>[0-9a-f]{40})"
                r"\s*与\s*Commit\s*(?P<c2>[0-9a-f]{40})\s*(?:有什么不同|对比)")),
)


def parse_question(text: str, **overrides) -> dict:
    """★ 有限模板映射。匹配失败即抛错，不猜。

    返回 build_query 的结果。overrides 可补 repository_id 等必需字段。
    """
    s = clean(text, limit=MAX_TEXT).strip()
    for qt, pat in _TEMPLATES:
        m = pat.search(s)
        if not m:
            continue
        g = m.groupdict()
        kw = dict(overrides)
        kw["question_type"] = qt
        if qt == Q_PATH_CLAIM:
            kw.update(commit_sha=g.get("commit"), path=g.get("path"))
        elif qt == Q_KNOWN_CLAIMS:
            kw.update(commit_sha=g.get("commit"))
            if g.get("repo") and "repository_id" not in kw:
                kw["repository_id"] = g["repo"]
        else:
            kw.update(commit_sha=g.get("c1"),
                      compare_commit_sha=g.get("c2"), path=g.get("path"))
        return build_query(**kw)
    raise QueryError(R_BAD_TYPE,
                     "无法匹配任何已知模板；不猜语义，请改用结构化查询")
