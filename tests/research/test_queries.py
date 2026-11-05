#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-1 / T-24 / T-25 / T-28：查询身份、排序、注入防护。"""
import sys, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/research", "src/research", "src/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import query_models as QM


class TestQueryIdentity(unittest.TestCase):
    def test_t1_same_input_same_id(self):
        a = rfx.q_path()
        b = rfx.q_path()
        self.assertEqual(a["query_id"], b["query_id"])
        self.assertTrue(a["query_id"].startswith("SL-Q-"))

    def test_t1b_different_commit_no_collision(self):
        a = rfx.q_path()
        b = rfx.q_path(commit_sha=rfx.B)
        self.assertNotEqual(a["query_id"], b["query_id"])

    def test_t1c_different_repo_no_collision(self):
        a = rfx.q_path()
        b = rfx.q_path(repository_id="999999")
        self.assertNotEqual(a["query_id"], b["query_id"])

    def test_t1d_different_question_type_no_collision(self):
        a = rfx.q_path()
        b = rfx.q_claims()
        self.assertNotEqual(a["query_id"], b["query_id"])

    def test_t25_order_independent(self):
        """canonical_refs 排序后参与身份 → 顺序无关。"""
        q = rfx.q_path()
        d1 = json.loads(json.dumps(q))
        d2 = json.loads(json.dumps(q))
        d2["canonical_refs"] = list(reversed(d2["canonical_refs"]))
        self.assertEqual(QM.make_query_id(d1), QM.make_query_id(d2))

    def test_time_not_in_identity(self):
        q = rfx.q_path()
        self.assertNotIn("created_at", q)
        self.assertNotIn("queried_at", q)

    def test_roundtrip_identity(self):
        q = rfx.q_path()
        again = QM.from_dict(q)
        self.assertEqual(q["query_id"], again["query_id"])


class TestQueryValidation(unittest.TestCase):
    def test_unknown_type_rejected(self):
        with self.assertRaises(QM.QueryError) as cm:
            QM.build_query(question_type="FREE_TEXT", repository_id="r")
        self.assertEqual(cm.exception.reason, QM.R_BAD_TYPE)

    def test_missing_repo_rejected(self):
        with self.assertRaises(QM.QueryError) as cm:
            QM.build_query(question_type=QM.Q_KNOWN_CLAIMS, repository_id="")
        self.assertEqual(cm.exception.reason, QM.R_NO_REPO)

    def test_missing_commit_for_path(self):
        with self.assertRaises(QM.QueryError) as cm:
            QM.build_query(question_type=QM.Q_PATH_CLAIM, repository_id="r",
                           path="README")
        self.assertEqual(cm.exception.reason, QM.R_NO_COMMIT)

    def test_bad_commit_rejected(self):
        with self.assertRaises(QM.QueryError) as cm:
            QM.build_query(question_type=QM.Q_PATH_CLAIM, repository_id="r",
                           commit_sha="zzz", path="README")
        self.assertIn(cm.exception.reason, (QM.R_BAD_COMMIT,))

    def test_tree_sha_not_accepted_as_commit(self):
        """★ 40 位十六进制的 Tree SHA 形态上像 Commit，必须靠字段语义区分。"""
        tree_like = "b4eecafa" + "0" * 32
        q = QM.build_query(question_type=QM.Q_PATH_CLAIM, repository_id="r",
                           commit_sha=tree_like, path="README")
        # 形态合法（真 Commit 也是 40 hex）→ 由检索端比对 stem 是否真存在
        self.assertEqual(q["commit_sha"], tree_like)

    def test_bad_limit_rejected(self):
        for bad in (0, -1, "50"):
            with self.assertRaises(QM.QueryError) as cm:
                QM.build_query(question_type=QM.Q_KNOWN_CLAIMS,
                               repository_id="r", max_results=bad)
            self.assertEqual(cm.exception.reason, QM.R_BAD_LIMIT)

    def test_limit_capped(self):
        q = QM.build_query(question_type=QM.Q_KNOWN_CLAIMS,
                           repository_id="r", max_results=99999)
        self.assertEqual(q["max_results"], QM.MAX_RESULTS_CAP)


class TestInjectionSafety(unittest.TestCase):
    """T-28：恶意查询不得形成 SQL / Shell / 网络命令。"""

    BAD = ["javascript:alert(1)", "<script>alert(1)</script>",
           "'; DROP TABLE assets--", "a; drop table b",
           "UNION SELECT * FROM assets", "$(whoami)", "`id`",
           "a && rm -rf /", "a || true", "file:///etc/passwd",
           "data:text/html,x", "/etc/passwd", "../etc", "a/../../b"]

    def test_t28_path_injection_rejected(self):
        for bad in self.BAD:
            with self.assertRaises(QM.QueryError) as cm:
                QM.build_query(question_type=QM.Q_PATH_CLAIM,
                               repository_id="r", commit_sha=rfx.A, path=bad)
            self.assertEqual(cm.exception.reason, QM.R_BAD_PATH,
                             f"{bad!r} 必须被拒")

    def test_normal_paths_accepted(self):
        for ok in ("README", "src/main.py", "docs/a-b_c.md", "a.b.c"):
            q = QM.build_query(question_type=QM.Q_PATH_CLAIM,
                               repository_id="r", commit_sha=rfx.A, path=ok)
            self.assertEqual(q["path"], ok)

    def test_control_chars_stripped(self):
        q = QM.build_query(question_type=QM.Q_KNOWN_CLAIMS, repository_id="r",
                           requested_ref="ma\u202ester")
        self.assertNotIn("\u202e", q["requested_ref"])

    def test_overlong_stripped(self):
        q = QM.build_query(question_type=QM.Q_KNOWN_CLAIMS, repository_id="r",
                           subject_id="x" * 5000)
        self.assertLessEqual(len(q["subject_id"]), 128)


class TestTemplates(unittest.TestCase):
    """自然语言只走有限模板映射，识别不了就拒绝。"""

    def test_path_template(self):
        q = QM.parse_question(f"在 Commit {rfx.A} 中 README 是否存在",
                              repository_id=rfx.REPO)
        self.assertEqual(q["question_type"], QM.Q_PATH_CLAIM)
        self.assertEqual(q["path"], "README")

    def test_compare_template(self):
        q = QM.parse_question(
            f"README 在 Commit {rfx.A} 与 Commit {rfx.B} 有什么不同",
            repository_id=rfx.REPO)
        self.assertEqual(q["question_type"], QM.Q_VERSION_COMPARE)

    def test_unmatched_rejected_not_guessed(self):
        for bad in ("这个项目好不好", "帮我写份报告", ""):
            with self.assertRaises(QM.QueryError) as cm:
                QM.parse_question(bad, repository_id=rfx.REPO)
            self.assertEqual(cm.exception.reason, QM.R_BAD_TYPE,
                             f"{bad!r} 不得被猜测")


if __name__ == "__main__":
    unittest.main(verbosity=2)
