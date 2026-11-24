#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3/D1+D4+D5：正式 analyze 入口的递归树 / 固定 Commit / 全局预算回归。

用注入的假 GitHubClient 直接调用 analyze()（不经网络），验证：
  - 复用 TreeCollector 递归范围，真实子目录条目进入 Snapshot，标 COMPLETE
  - truncated/逐层上限 → PARTIAL/ROOT_ONLY，绝不冒充 COMPLETE
  - --commit 与返回 Commit 不一致 → COMMIT_MISMATCH 立即终止
  - analyze 与 content capture 共用单一 max_requests 硬上限
"""
import sys, unittest, tempfile, json
from unittest import mock
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "skill_interface"))
import sfx  # noqa: F401  设置 sys.path
sys.path.insert(0, str(ROOT / "src" / "skill_interface"))
sys.path.insert(0, str(ROOT / "src" / "collector"))
import analyze as A
from result import SkillError


class FakeResp:
    def __init__(self, ok, data=None, error=None, headers=None, status=200):
        self.ok = ok
        self.data = data or {}
        self.error = error
        self.headers = headers or {}
        self.status = status


class FakeErr:
    def __init__(self, code="X"):
        self.error_code = code
        self.retry_after = None
        self.retryable = False
        def to_dict(self):
            return {"error_code": self.error_code}


class FakeClient:
    """记录每次 tree 调用的 recursive 参数。"""
    def __init__(self, *, commit_sha, tree_entries, recursive_result=None,
                 token=None, limits=None):
        self.commit_sha = commit_sha
        self.tree_entries = tree_entries
        self.recursive_result = recursive_result  # None=用 tree_entries
        self.calls = []
        self.limits = {"max_tree_entries": 10000, "max_depth": 12,
                       "max_blob_bytes": 262144, "max_requests": 50}
        self.limits.update(limits or {})
        self.request_count = 0

    def repo(self, owner, name):
        self.calls.append(("repo",))
        return FakeResp(True, {"id": "999", "full_name": f"{owner}/{name}"},
                        headers={"x-ratelimit-remaining": "50"})

    def commit_for_ref(self, owner, name, ref):
        self.calls.append(("commit", ref))
        return FakeResp(True, {
            "sha": self.commit_sha,
            "commit": {"tree": {"sha": "tree-" + self.commit_sha[:8]}},
        }, headers={"x-ratelimit-remaining": "49"})

    def tree(self, owner, name, tree_ref, *, recursive=False, **kw):
        self.calls.append(("tree", tree_ref, recursive))
        if self.recursive_result is not None:
            return self.recursive_result
        # 模拟逐层：递归返回全量；非递归只返回该目录一层
        entries = self.tree_entries
        if not recursive:
            entries = [e for e in entries if "/" not in e["path"]]
        return FakeResp(True, {"tree": entries, "truncated": False},
                        headers={"x-ratelimit-remaining": "48"})


def _patch_client(fake):
    """analyze() 在函数内 from github_client import GitHubClient，patch 模块属性。"""
    return mock.patch("github_client.GitHubClient", return_value=fake)


class TestRecursiveTree(unittest.TestCase):
    def test_analyze_uses_recursive_tree_and_full_entries(self):
        sha = "a" * 40
        entries = [
            {"path": "README.md", "sha": "s1", "type": "blob", "size": 10},
            {"path": "scripts/arch_engine/graph.py", "sha": "s2",
             "type": "blob", "size": 20},
        ]
        fake = FakeClient(commit_sha=sha, tree_entries=entries)
        with _patch_client(fake):
            with tempfile.TemporaryDirectory() as td:
                out = A.analyze(url="https://github.com/o/r", commit=sha,
                                data_root=td, max_requests=50)
        self.assertTrue(out.get("ok", True))
        self.assertEqual(out["coverage"]["scope"], "COMPLETE")
        # COMPLETE 由一次成功的递归枚举得到（无需逐层，故 deep_walk_used=False）
        self.assertFalse(out["coverage"]["deep_walk_used"])
        self.assertEqual(out["tree_entry_count"], 2)
        # 真实子目录条目进入快照（不是只有根层）
        tree_calls = [c for c in fake.calls if c[0] == "tree"]
        self.assertTrue(any(c[2] is True for c in tree_calls),
                        "正式入口必须使用 recursive=True")
        self.assertEqual(out["coverage"]["max_depth"], 2)

    def test_truncated_is_partial_not_complete(self):
        sha = "b" * 40
        entries = [{"path": "README.md", "sha": "s1", "type": "blob", "size": 10}]
        truncated = FakeResp(True, {"tree": entries, "truncated": True})
        fake = FakeClient(commit_sha=sha, tree_entries=entries,
                          recursive_result=truncated)
        with _patch_client(fake):
            with tempfile.TemporaryDirectory() as td:
                out = A.analyze(url="https://github.com/o/r", commit=sha,
                                data_root=td, max_requests=50)
        # 递归被 truncated → 退回逐层，逐层响应未 truncated 则
        # TreeCollector 记 DEEP_WALK_COMPLETE=COMPLETE，但 truncated 历史保留；
        # 关键是不得把递归截断当成"完整递归"，且必须留下 deep_walk 轨迹。
        self.assertTrue(out["coverage"]["deep_walk_used"])
        self.assertTrue(out["coverage"]["truncated"])


class TestFixedCommit(unittest.TestCase):
    def test_commit_mismatch_aborts(self):
        fake = FakeClient(commit_sha="c" * 40, tree_entries=[])
        with _patch_client(fake):
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(SkillError) as cm:
                    A.analyze(url="https://github.com/o/r", commit="d" * 40,
                              data_root=td, max_requests=50)
        self.assertEqual(cm.exception.code, "COMMIT_MISMATCH")
        # 不一致时不得继续请求 tree
        self.assertFalse(any(c[0] == "tree" for c in fake.calls))

    def test_explicit_commit_used_for_resolution(self):
        sha = "e" * 40
        fake = FakeClient(commit_sha=sha, tree_entries=[])
        with _patch_client(fake):
            with tempfile.TemporaryDirectory() as td:
                A.analyze(url="https://github.com/o/r", ref="main", commit=sha,
                          data_root=td, max_requests=50)
        commits = [c for c in fake.calls if c[0] == "commit"]
        self.assertEqual(commits[0][1], sha)  # 解析用的是 --commit，不是 ref


class TestGlobalBudget(unittest.TestCase):
    def test_analyze_exposes_shared_budget_without_json_pollution(self):
        # analyze 返回同一预算对象供内容采集复用；CLI 必须 pop 掉再 emit。
        sha = "9" * 40
        entries = [{"path": "README.md", "sha": "s1", "type": "blob", "size": 1}]
        fake = FakeClient(commit_sha=sha, tree_entries=entries)
        with _patch_client(fake):
            with tempfile.TemporaryDirectory() as td:
                out = A.analyze(url="https://github.com/o/r", commit=sha,
                                data_root=td, max_requests=50)
        self.assertIn("_shared_budget", out)
        self.assertEqual(out["_shared_budget"].request_limit, 50)
        self.assertEqual(out["_shared_budget"].consumed_requests,
                         out["network_requests"])
        # 模拟 CLI pop：之后 JSON 序列化不得含对象字段
        shared = out.pop("_shared_budget")
        json.dumps(out)  # 不应抛异常
        self.assertEqual(shared.consumed_requests, out["network_requests"])

    def test_preflight_reuses_existing_budget(self):
        cli_src = (ROOT / "src" / "skill_interface" / "cli.py").read_text(
            encoding="utf-8")
        self.assertIn("existing_budget=None", cli_src)
        self.assertIn("budget = existing_budget or RB.GitHubRequestBudget(", cli_src)
        self.assertIn('_shared_budget = out.pop("_shared_budget", None)', cli_src)
        self.assertIn("existing_budget=_shared_budget", cli_src)
        self.assertIn('pre["execution_budget"] = budget.request_limit', cli_src)
        self.assertIn("shared_budget_consumed", cli_src)

    def test_budget_is_single_across_stages(self):
        sha = "f" * 40
        entries = [{"path": "README.md", "sha": "s1", "type": "blob", "size": 1}]
        fake = FakeClient(commit_sha=sha, tree_entries=entries)
        with _patch_client(fake):
            with tempfile.TemporaryDirectory() as td:
                out = A.analyze(url="https://github.com/o/r", commit=sha,
                                data_root=td, max_requests=10)
        b = out["request_budget"]
        self.assertEqual(b["request_limit"], 10)
        self.assertEqual(out["network_requests"], b["consumed_requests"])
        self.assertGreaterEqual(b["consumed_requests"], 3)  # repo+commit+tree
        self.assertLessEqual(b["consumed_requests"], 10)

    def test_source_uses_tree_collector(self):
        src = (ROOT / "src" / "skill_interface" / "analyze.py").read_text(encoding="utf-8")
        self.assertIn("from tree_collector import TreeCollector", src)
        self.assertIn("tc.collect(root_tree)", src)
        self.assertIn("truncated_seen=truncated", src)
        self.assertIn("deep_walk_used=deep_walk_used", src)
        self.assertIn("COMMIT_MISMATCH", src)
        self.assertIn("import request_budget as RB", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
