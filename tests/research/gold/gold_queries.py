#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线 Gold Query 集（人工定义，**不由 Research 输出反推**）。

每项含 gold_expectation：人工给定的期望。评测器比对实际结果与它。
"""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
for p in ("src/research", "tests/research", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))

A = "a" * 40
B = "b" * 40
WRONG_COMMIT = "c" * 40
REPO = "1296269"
WRONG_REPO = "99999999"

# 覆盖状态
ANS = "ANSWERABLE_FROM_EXISTING_EVIDENCE"
PART = "PARTIALLY_ANSWERABLE"
INSUF = "INSUFFICIENT_EVIDENCE"
ERR = "RETRIEVAL_ERROR"
CONF = "CONFLICT_REQUIRES_REVIEW"

# ★ gold 由人写明：期望 coverage + 期望 finding 裁决集合（可为空）
GOLD = [
  # 1 有充分支持证据
  {"id": "G01_supported", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": ANS, "verdicts": ["supported"],
            "must_have_evidence": True}},
  # 2 有有效反证（B 上 README 缺失 → EC 判 refuted）
  {"id": "G02_refuted", "scenario": "complete_ab",
   "query": {"question_type": "PATH_EXISTENCE", "repository_id": REPO,
             "commit_sha": B, "path": "README"},
   "gold": {"coverage": ANS, "verdicts": ["refuted"]}},
  # 3 证据不足
  {"id": "G03_insufficient", "scenario": "partial",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": INSUF,
            "verdicts": ["insufficient_evidence"],
            "must_have_partial_limit": True}},
  # 4 没有任何已登记 Claim
  {"id": "G04_no_claim", "scenario": "complete_ab",
   "query": {"question_type": "PATH_EXISTENCE", "repository_id": REPO,
             "commit_sha": A, "path": "no-such-file.md"},
   "gold": {"coverage": INSUF, "verdicts": [],
            "must_not_be": ["refuted"]}},
  # 5 PARTIAL 来源
  {"id": "G05_partial", "scenario": "partial",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": INSUF, "must_have_partial_limit": True}},
  # 6 错误 Commit
  {"id": "G06_wrong_commit", "scenario": "complete_ab",
   "query": {"question_type": "PATH_EXISTENCE", "repository_id": REPO,
             "commit_sha": WRONG_COMMIT, "path": "README"},
   "gold": {"coverage": INSUF, "verdicts": [],
            "must_not_be": ["supported"]}},
  # 7 错误 repository_id
  {"id": "G07_wrong_repo", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": WRONG_REPO,
             "commit_sha": A},
   "gold": {"coverage": INSUF, "verdicts": []}},
  # 8 不同 Commit 的历史对照
  {"id": "G08_version_compare", "scenario": "complete_ab",
   "query": {"question_type": "VERSION_COMPARE", "repository_id": REPO,
             "commit_sha": A, "compare_commit_sha": B, "path": "README"},
   "gold": {"coverage": PART, "two_commits": True,
            "must_not_be_conflict": True}},
  # 9 冲突证据
  {"id": "G09_conflict", "scenario": "complete_ab",
   "query": {"question_type": "VERSION_COMPARE", "repository_id": REPO,
             "commit_sha": A, "compare_commit_sha": B, "path": "README"},
   "gold": {"verdict_divergence": True, "must_not_be_conflict": True}},
  # 10 TEST_ONLY 来源
  {"id": "G10_test_only", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": ANS, "verdicts": ["supported"],
            "must_not_publish": True}},
  # 11 混合来源
  {"id": "G11_mixed_prov", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"must_not_upgrade_provenance": True,
            "must_not_publish": True}},
  # 12 当前 Ref 适用性未知
  {"id": "G12_applicability", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"must_not_claim_current": True}},
  # 13 缺失 Snapshot（索引丢失）→ 证据链不可确认，不得声称完全可答
  {"id": "G13_missing_snapshot", "scenario": "no_snapshot",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": PART,
            "must_flag_chain_unverifiable": True}},
  # 14 悬空引用 → 检索通路受损（**不是**"没有知识"）
  {"id": "G14_corrupt_evidence", "scenario": "corrupt",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": ERR, "no_trusted_finding": True,
            "must_not_be": ["supported", "refuted"]}},
  # 15 索引缺失
  {"id": "G15_index_missing", "scenario": "empty",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": INSUF, "verdicts": []}},
  # 16 结果超过 LIMIT
  {"id": "G16_truncated", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A, "max_results": 1},
   "gold": {"limit": 1, "must_mark_truncation_if_truncated": True}},
  # 17 恶意提示注入文本
  {"id": "G17_injection", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": ANS, "verdicts": ["supported"],
            "must_ignore_injection": True}},
  # 18 查询输入顺序变化
  {"id": "G18_order", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"stable_id": True}},
  # 19 重复 Claim
  {"id": "G19_duplicate", "scenario": "duplicate",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"coverage": ANS, "stable_dedup": True}},
  # 20 人工审核未完成
  {"id": "G20_pending_review", "scenario": "complete_ab",
   "query": {"question_type": "KNOWN_CLAIMS", "repository_id": REPO,
             "commit_sha": A},
   "gold": {"review_not_approved": True,
            "verdicts": ["supported"]}},
]


def by_id(gid):
    for g in GOLD:
        if g["id"] == gid:
            return g
    raise KeyError(gid)
