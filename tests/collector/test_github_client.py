#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collector 确定性测试（T-1..T-19，不含真实网络）。

**全部离线**：使用 fake_gh 夹具。真实网络测试在 test_real_github.py 分开跑。
"""
import base64, hashlib, json, os, sys, tempfile, shutil, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLL = ROOT / "src" / "collector"
STORAGE = ROOT / "src" / "storage"
RUNTIME = ROOT / "src" / "runtime"
for p in (str(COLL), str(STORAGE), str(RUNTIME), str(ROOT / "tests" / "collector")):
    if p not in sys.path:
        sys.path.insert(0, p)

import fake_gh as F
import github_client as G
from tree_collector import (TreeCollector, COMPLETE, PARTIAL, INCOMPLETE,
                            read_blob, git_blob_sha1, ENTRY_TREE, ENTRY_COMMIT,
                            ENTRY_UNKNOWN)
from source_snapshot import build_snapshot, SourceSnapshot, COLLECTOR_VERSION
from ingest_coordinator import (ingest_snapshot, stable_operation_id, verify_ingest,
                                INGESTED, IDEMPOTENT, CONFLICT, REJECTED)
from knowledge_store import KnowledgeStore
import index_store as IX


def fake_client(**kw):
    c = G.GitHubClient(max_retries=0, token=None)
    F.install_fake(c, F.make_router(**kw))
    return c


class TestIdentityAndResolution(unittest.TestCase):
    """T-1 / T-2 / T-3 / T-4。"""

    def test_t1_repo_identity(self):
        c = fake_client()
        r = c.repo("octocat", "Hello-World")
        self.assertTrue(r.ok)
        self.assertEqual(r.data["id"], 1296269)
        self.assertEqual(r.data["full_name"], "octocat/Hello-World")

    def test_t2_resolve_ref_to_commit(self):
        c = fake_client()
        r = c.commit_for_ref("octocat", "Hello-World", "master")
        self.assertTrue(r.ok)
        self.assertEqual(r.data["sha"], F.COMMIT_SHA)

    def test_t3_commit_and_root_tree_are_separate(self):
        """commit_sha 与 root_tree_sha 是两个不同的值，必须分字段取。"""
        c = fake_client()
        commit = c.commit_for_ref("octocat", "Hello-World", "master")
        commit_sha = commit.data["sha"]
        root_tree_sha = commit.data["commit"]["tree"]["sha"]
        self.assertNotEqual(commit_sha, root_tree_sha,
                            "本夹具刻意让二者不同，以暴露混用")
        # Trees API 以 commit_sha 为 ref 时，响应 sha 回显的是请求 ref
        t = c.tree("octocat", "Hello-World", commit_sha, recursive=True)
        self.assertTrue(t.ok)
        self.assertEqual(t.data["sha"], commit_sha,
                         "GitHub 行为：Trees API 回显请求 ref")
        self.assertNotEqual(t.data["sha"], root_tree_sha,
                            "★ 绝不能把 Trees 响应的 sha 当成 root_tree_sha")

    def test_t3_build_snapshot_keeps_three_fields_distinct(self):
        snap = build_snapshot(
            repository_id="1296269", requested_repository="octocat/Hello-World",
            resolved_repository="octocat/Hello-World", requested_ref="master",
            commit_sha=F.COMMIT_SHA,
            root_tree_sha=F.ROOT_TREE_SHA,
            tree_query_ref=F.ROOT_TREE_SHA,
            completeness_status=COMPLETE, tree_entries=F.FLAT_ENTRIES,
            collected_at="2026-11-04T20:00:00+0800", evidence_refs=["ev1"])
        d = snap.to_dict()
        self.assertEqual(d["commit_sha"], F.COMMIT_SHA)
        self.assertEqual(d["root_tree_sha"], F.ROOT_TREE_SHA)
        self.assertEqual(d["tree_query_ref"], F.ROOT_TREE_SHA)
        self.assertNotEqual(d["commit_sha"], d["root_tree_sha"])

    def test_t4_tree_query_ref_recorded_accurately(self):
        """记录的是**实际请求的 ref**，即使是 commit_sha。"""
        c = fake_client()
        tc = TreeCollector(c, "octocat", "Hello-World")
        res = tc.collect(F.ROOT_TREE_SHA)
        self.assertEqual(res["tree_query_refs"][0], F.ROOT_TREE_SHA,
                         "必须记录实际使用的 ref")


class TestTreeCollection(unittest.TestCase):
    """T-5 / T-6 / T-7。"""

    def test_t5_flat_tree_enumeration(self):
        c = fake_client()
        tc = TreeCollector(c, "octocat", "Hello-World")
        res = tc.collect(F.ROOT_TREE_SHA)
        self.assertEqual(res["completeness_status"], COMPLETE)
        self.assertEqual(res["entry_count"], 2)
        paths = {e["path"] for e in res["entries"]}
        self.assertEqual(paths, {"README", "docs"})

    def test_t6_nested_tree_with_symlink_and_submodule(self):
        c = fake_client(tree_entries=F.NESTED_ROOT)
        tc = TreeCollector(c, "octocat", "Hello-World")
        res = tc.collect(F.ROOT_TREE_SHA)
        kinds = {e["path"]: e["mode_kind"] for e in res["entries"]}
        self.assertEqual(kinds["link"], "symlink")
        self.assertEqual(kinds["sub"], "submodule")
        types = {e["path"]: e["type"] for e in res["entries"]}
        self.assertEqual(types["sub"], ENTRY_COMMIT)
        self.assertEqual(types["weird"], ENTRY_UNKNOWN,
                         "不可解析的 type 必须标 unknown，不得猜成 blob/tree")

    def test_t7_truncated_never_reported_complete(self):
        """truncated=true 时，即使逐层遍历成功也不能冒充原始递归完整。"""
        c = fake_client(truncated_recursive=True)
        tc = TreeCollector(c, "octocat", "Hello-World")
        res = tc.collect(F.ROOT_TREE_SHA)
        self.assertTrue(res["truncated_seen"])
        self.assertTrue(res["deep_walk_used"], "必须退回逐层遍历")
        # 逐层走完（本夹具子目录存在）→ 可标 COMPLETE，但必须留下 truncated_seen 记录
        self.assertIn(res["completeness_status"], (COMPLETE, PARTIAL))
        self.assertTrue(res["truncated_seen"],
                        "无论最终状态如何，截断事实必须留痕")

    def test_t7_partial_when_deep_walk_also_truncated(self):
        c = fake_client(truncated_recursive=True)
        # 让非递归也返回 truncated
        router = F.make_router(truncated_recursive=True)
        def r2(path, params):
            st, body, h = router(path, params)
            if "/git/trees/" in path and not params.get("recursive") and st == 200:
                body = dict(body, truncated=True)
            return st, body, h
        c = G.GitHubClient(max_retries=0)
        F.install_fake(c, r2)
        tc = TreeCollector(c, "octocat", "Hello-World")
        res = tc.collect(F.ROOT_TREE_SHA)
        self.assertEqual(res["completeness_status"], PARTIAL,
                         "逐层也截断 → 只能 PARTIAL，绝不能 COMPLETE")

    def test_entry_limit_forces_partial(self):
        many = [{"path": f"f{i}", "mode": "100644", "type": "blob",
                 "sha": "x" * 40, "size": 1} for i in range(50)]
        c = fake_client(tree_entries=many)
        c.limits["max_tree_entries"] = 10
        tc = TreeCollector(c, "octocat", "Hello-World")
        res = tc.collect(F.ROOT_TREE_SHA)
        self.assertEqual(res["completeness_status"], PARTIAL)
        self.assertLessEqual(res["entry_count"], 10)


class TestBlobReading(unittest.TestCase):
    """T-8 / T-9。"""

    def test_t8_blob_bytes_and_verification(self):
        c = fake_client()
        r = read_blob(c, "octocat", "Hello-World", F.BLOB_SHA)
        self.assertTrue(r["ok"])
        self.assertTrue(r["verified"], "Git blob sha1 必须校验通过")
        self.assertEqual(r["content_bytes"], F.BLOB_CONTENT)
        self.assertEqual(r["content_text"], "hello world\n")
        self.assertFalse(r["is_binary"])

    def test_git_blob_sha_differs_from_plain_content_sha1(self):
        """Git 对象编码 ≠ 裸内容 sha1 —— 题面明确要求。"""
        import hashlib as H
        plain = H.sha1(F.BLOB_CONTENT).hexdigest()
        git = git_blob_sha1(F.BLOB_CONTENT)
        self.assertNotEqual(plain, git, "两者必须不同，证明用了 Git 规则")
        self.assertEqual(git, F.BLOB_SHA)

    def test_binary_content_keeps_raw_bytes(self):
        raw = b"\x00\x01\xff\xfe"
        sha = git_blob_sha1(raw)
        c = G.GitHubClient(max_retries=0)
        def route(path, params):
            if path.endswith(sha):
                return 200, {"sha": sha, "size": len(raw), "encoding": "base64",
                             "content": base64.b64encode(raw).decode()}, {}
            return 404, {"message": "Not Found"}, {}
        F.install_fake(c, route)
        r = read_blob(c, "o", "r", sha)
        self.assertTrue(r["ok"])
        self.assertTrue(r["is_binary"], "文本解码失败必须标 binary")
        self.assertEqual(r["content_bytes"], raw, "原始字节不得因解码失败而改变")

    def test_t9_unknown_encoding_rejected(self):
        c = G.GitHubClient(max_retries=0)
        def route(path, params):
            return 200, {"encoding": "utf-8", "content": "x"}, {}
        F.install_fake(c, route)
        r = read_blob(c, "o", "r", "z" * 40)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error_code"], G.MALFORMED)

    def test_blob_too_large_rejected(self):
        raw = b"x" * 5000
        sha = git_blob_sha1(raw)
        c = G.GitHubClient(max_retries=0)
        c.limits["max_blob_bytes"] = 100
        def route(path, params):
            return 200, {"sha": sha, "size": len(raw), "encoding": "base64",
                         "content": base64.b64encode(raw).decode()}, {}
        F.install_fake(c, route)
        r = read_blob(c, "o", "r", sha, max_bytes=100)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error_code"], G.BUDGET_EXCEEDED)


class TestErrorClassification(unittest.TestCase):
    """T-14 / T-15：错误与限流分类。"""

    def _client_with_status(self, status, body=None, headers=None):
        c = G.GitHubClient(max_retries=0)
        body = body if body is not None else {"message": "err"}
        hdrs = headers or {}
        def route(path, params):
            return status, body, hdrs
        F.install_fake(c, route)
        return c

    def test_t14_401(self):
        r = self._client_with_status(401).repo("o", "r")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.error_code, G.UNAUTHORIZED)
        self.assertFalse(r.error.retryable)

    def test_t14_403_primary_rate_limit(self):
        r = self._client_with_status(403, headers={"x-ratelimit-remaining": "0"}).repo("o", "r")
        self.assertEqual(r.error.error_code, G.RATE_LIMITED)
        self.assertTrue(r.error.retryable, "限流可重试")

    def test_t14_403_secondary_rate_limit(self):
        r = self._client_with_status(
            403, body={"message": "You have exceeded a secondary rate limit"},
            headers={"x-ratelimit-remaining": "10"}).repo("o", "r")
        self.assertEqual(r.error.error_code, G.SECONDARY_RATE_LIMITED,
                         "次级限流必须与主限流分开")
        self.assertNotEqual(r.error.error_code, G.RATE_LIMITED)

    def test_t14_403_plain_forbidden(self):
        r = self._client_with_status(403, headers={"x-ratelimit-remaining": "42"}).repo("o", "r")
        self.assertEqual(r.error.error_code, G.FORBIDDEN, "非限流的 403 是权限问题")

    def test_t14_404(self):
        r = self._client_with_status(404).repo("o", "r")
        self.assertEqual(r.error.error_code, G.NOT_FOUND)
        self.assertFalse(r.error.retryable)

    def test_t14_429(self):
        r = self._client_with_status(429, headers={"retry-after": "5"}).repo("o", "r")
        self.assertEqual(r.error.error_code, G.SECONDARY_RATE_LIMITED)
        self.assertEqual(r.error.retry_after, 5)

    def test_t14_5xx(self):
        for st in (500, 502, 503):
            r = self._client_with_status(st).repo("o", "r")
            self.assertEqual(r.error.error_code, G.SERVER_ERROR)
            self.assertTrue(r.error.retryable)

    def test_404_never_becomes_empty_repo(self):
        """★ 铁律：404 不得折成"空仓库"。"""
        r = self._client_with_status(404).repo("o", "r")
        self.assertFalse(r.ok)
        self.assertIsNone(r.data, "404 不得返回空 data 冒充成功")

    def test_t15_bounded_retry(self):
        calls = {"n": 0}
        c = G.GitHubClient(max_retries=2)
        c._sleep = lambda s: None
        def route(path, params):
            calls["n"] += 1
            return 503, {"message": "boom"}, {}
        F.install_fake(c, route)
        r = c.repo("o", "r")
        self.assertFalse(r.ok)
        self.assertEqual(calls["n"], 3, "1 次首试 + 2 次重试 = 3，不得无界")
        self.assertEqual(r.error.error_code, G.SERVER_ERROR)

    def test_t15_non_retryable_not_retried(self):
        calls = {"n": 0}
        c = G.GitHubClient(max_retries=3)
        c._sleep = lambda s: None
        def route(path, params):
            calls["n"] += 1
            return 401, {"message": "bad creds"}, {}
        F.install_fake(c, route)
        r = c.repo("o", "r")
        self.assertEqual(calls["n"], 1, "401 不该重试")

    def test_retry_after_capped(self):
        slept = []
        c = G.GitHubClient(max_retries=2)
        c._sleep = lambda s: slept.append(s)
        c.limits["max_retry_after"] = 5
        def route(path, params):
            return 429, {"message": "slow"}, {"retry-after": "9999"}
        F.install_fake(c, route)
        c.repo("o", "r")
        self.assertTrue(all(s <= 5 for s in slept), f"等待必须被上限约束: {slept}")

    def test_max_requests_budget(self):
        c = G.GitHubClient(max_retries=0)
        c.limits["max_requests"] = 2
        F.install_fake(c, lambda p, q: (200, F.REPO_JSON, {}))
        c.repo("o", "r"); c.repo("o", "r")
        r = c.repo("o", "r")
        self.assertFalse(r.ok)
        self.assertEqual(r.error.error_code, G.BUDGET_EXCEEDED)


class TestSnapshotIdentity(unittest.TestCase):
    """快照身份确定性。"""

    def _snap(self, *, repo_id="1296269", commit="a" * 40, tree="b" * 40,
              collected="2026-11-04T20:00:00+0800"):
        return build_snapshot(
            repository_id=repo_id, requested_repository="o/r",
            resolved_repository="o/r", requested_ref="master",
            commit_sha=commit, root_tree_sha=tree, tree_query_ref=tree,
            completeness_status=COMPLETE, tree_entries=F.FLAT_ENTRIES,
            collected_at=collected, evidence_refs=["ev"])

    def test_collected_at_not_in_identity(self):
        a = self._snap(collected="2026-11-04T20:00:00+0800")
        b = self._snap(collected="2026-11-05T09:00:00+0800")
        self.assertEqual(a.logical_identity(), b.logical_identity(),
                         "collected_at 不得影响身份")
        self.assertEqual(a.content_hash(), b.content_hash(),
                         "collected_at 不得影响内容哈希")

    def test_different_repo_same_content_different_identity(self):
        a = self._snap(repo_id="1296269")
        b = self._snap(repo_id="999999")
        self.assertNotEqual(a.logical_identity(), b.logical_identity(),
                            "不同仓库即使内容一致也不得同身份")
        self.assertNotEqual(a.content_hash(), b.content_hash())

    def test_different_commit_different_identity(self):
        a = self._snap(commit="a" * 40)
        b = self._snap(commit="c" * 40)
        self.assertNotEqual(a.logical_identity(), b.logical_identity())

    def test_requested_ref_does_not_change_identity(self):
        """requested_ref 是定位手段，不是身份 —— 解析到同一 commit 即同一身份。"""
        a = build_snapshot(repository_id="1", requested_repository="o/r",
                           resolved_repository="o/r", requested_ref="master",
                           commit_sha="a" * 40, root_tree_sha="b" * 40,
                           tree_query_ref="b" * 40, completeness_status=COMPLETE,
                           tree_entries=F.FLAT_ENTRIES,
                           collected_at="t1", evidence_refs=[])
        b = build_snapshot(repository_id="1", requested_repository="o/r",
                           resolved_repository="o/r", requested_ref="v1.0",
                           commit_sha="a" * 40, root_tree_sha="b" * 40,
                           tree_query_ref="b" * 40, completeness_status=COMPLETE,
                           tree_entries=F.FLAT_ENTRIES,
                           collected_at="t2", evidence_refs=[])
        self.assertEqual(a.logical_identity(), b.logical_identity(),
                         "同一 commit 不同 ref 名 → 同一身份")

    def test_incomplete_status_changes_content_hash(self):
        a = self._snap()
        b = build_snapshot(repository_id="1296269", requested_repository="o/r",
                           resolved_repository="o/r", requested_ref="master",
                           commit_sha="a" * 40, root_tree_sha="b" * 40,
                           tree_query_ref="b" * 40, completeness_status=PARTIAL,
                           tree_entries=F.FLAT_ENTRIES,
                           collected_at="t", evidence_refs=[])
        self.assertNotEqual(a.content_hash(), b.content_hash(),
                            "完整性状态必须影响内容哈希")


class TestIngest(unittest.TestCase):
    """T-11 / T-12 / T-18。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p1c_ing_"))
        self.db = str(self.tmp / "kb.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snap(self, *, repo_id="1296269", commit="a" * 40):
        return build_snapshot(
            repository_id=repo_id, requested_repository="o/r",
            resolved_repository="o/r", requested_ref="master",
            commit_sha=commit, root_tree_sha="b" * 40, tree_query_ref="b" * 40,
            completeness_status=COMPLETE, tree_entries=F.FLAT_ENTRIES,
            collected_at="2026-11-04T20:00:00+0800", evidence_refs=["ev"])

    def test_ingest_creates_asset(self):
        with KnowledgeStore(self.db) as ks:
            r = ingest_snapshot(ks, self._snap())
            self.assertTrue(r["ok"])
            self.assertEqual(r["state"], INGESTED)
            self.assertEqual(r["pointer_version"], 1)
            v = verify_ingest(ks, self._snap(), asset_id=r["asset_id"])
            self.assertTrue(v["ok"], "读回哈希必须一致")

    def test_t12_repeat_same_snapshot_is_idempotent(self):
        with KnowledgeStore(self.db) as ks:
            r1 = ingest_snapshot(ks, self._snap())
            r2 = ingest_snapshot(ks, self._snap())
            self.assertEqual(r2["state"], IDEMPOTENT)
            self.assertEqual(r2["asset_id"], r1["asset_id"])
            n = ks.conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"]
            self.assertEqual(n, 1, "重复采集不得产生第二条资产")
            p = ks.current_pointer(self._snap().logical_identity(), "1296269")
            self.assertEqual(p["pointer_version"], 1, "不得重复推进指针")

    def test_t11_different_repos_no_collision(self):
        with KnowledgeStore(self.db) as ks:
            a = ingest_snapshot(ks, self._snap(repo_id="111"))
            b = ingest_snapshot(ks, self._snap(repo_id="222"))
            self.assertTrue(a["ok"] and b["ok"])
            self.assertNotEqual(a["asset_id"], b["asset_id"],
                                "不同仓库同内容不得碰撞")
            n = ks.conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"]
            self.assertEqual(n, 2)

    def test_t18_same_operation_id_different_input_conflicts(self):
        with KnowledgeStore(self.db) as ks:
            s1 = self._snap(commit="a" * 40)
            op = stable_operation_id(repository_id="1296269",
                                     commit_sha="a" * 40,
                                     retrieval_scope=s1.retrieval_scope,
                                     collector_version=COLLECTOR_VERSION)
            ingest_snapshot(ks, s1, operation_id=op)
            s2 = self._snap(commit="c" * 40)   # 不同内容
            r = ingest_snapshot(ks, s2, operation_id=op)
            self.assertEqual(r["state"], CONFLICT,
                             "同 operation_id 不同摘要必须 CONFLICT")

    def test_stable_operation_id_is_deterministic(self):
        a = stable_operation_id(repository_id="1", commit_sha="a" * 40,
                                retrieval_scope="full_tree_enumeration",
                                collector_version=COLLECTOR_VERSION)
        b = stable_operation_id(repository_id="1", commit_sha="a" * 40,
                                retrieval_scope="full_tree_enumeration",
                                collector_version=COLLECTOR_VERSION)
        self.assertEqual(a, b, "重试不得改变 operation_id")

    def test_ingest_does_not_upgrade_to_claim(self):
        """★ 采集资产 ≠ 已验证 Claim。"""
        with KnowledgeStore(self.db) as ks:
            r = ingest_snapshot(ks, self._snap())
            a = ks.get_asset(r["asset_id"])["asset"]
            self.assertEqual(a["asset_type"], "repository_snapshot",
                             "类型必须是原始采集，不能是 claim_record")
            self.assertNotIn("verified", a["payload"])
            self.assertNotIn("claim_status", a["payload"])


class TestIndexRebuild(unittest.TestCase):
    """T-19。"""

    def test_rebuild_after_ingest_keeps_a_b(self):
        tmp = Path(tempfile.mkdtemp(prefix="p1c_ix_"))
        try:
            with KnowledgeStore(str(tmp / "kb.db")) as ks:
                snap = build_snapshot(
                    repository_id="1296269", requested_repository="o/r",
                    resolved_repository="o/r", requested_ref="master",
                    commit_sha="a" * 40, root_tree_sha="b" * 40,
                    tree_query_ref="b" * 40, completeness_status=COMPLETE,
                    tree_entries=F.FLAT_ENTRIES,
                    collected_at="t", evidence_refs=["ev"])
                ingest_snapshot(ks, snap)
                before = IX._ab_fingerprint(ks)
                cnt = IX.query(ks, repository_id="1296269")["count"]
                rb = IX.rebuild_index(ks)
                after = IX._ab_fingerprint(ks)
                self.assertTrue(rb["ok"])
                self.assertTrue(rb["a_b_unchanged"])
                self.assertEqual(before, after, "重建不得改 A/B")
                self.assertEqual(IX.query(ks, repository_id="1296269")["count"], cnt)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestPathSafety(unittest.TestCase):
    """T-16：恶意路径不逃逸。"""

    def test_rejects_absolute_url(self):
        c = G.GitHubClient(max_retries=0)
        with self.assertRaises(PermissionError):
            c._build_url("https://evil.example/steal")

    def test_rejects_traversal(self):
        c = G.GitHubClient(max_retries=0)
        with self.assertRaises(PermissionError):
            c._build_url("/repos/../../secret")

    def test_rejects_non_github_host_via_params(self):
        c = G.GitHubClient(max_retries=0)
        with self.assertRaises(PermissionError):
            c._build_url("//evil.example/x")

    def test_token_never_in_error_detail(self):
        c = G.GitHubClient(max_retries=0, token="ghp_SUPERSECRETTOKEN")
        c._do_request = lambda *a, **k: G.GhResponse(
            ok=False, error=G.GhError(error_code=G.NETWORK_ERROR,
                                      request_stage="x",
                                      detail="connection refused"))
        r = c.repo("o", "r")
        dumped = json.dumps(r.error.to_dict())
        self.assertNotIn("ghp_SUPERSECRETTOKEN", dumped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
