#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3/D3：跨来源身份绑定回归。

纯函数在内存验证；真实写入在 kb.db 临时副本上验证（不碰真实库）。
"""
import sys, unittest, tempfile, shutil, sqlite3, json, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("trust", "storage", "runtime", "collector", "facts", "evidence_claims",
          "lifecycle", "views", "renderer", "research", "skill_interface"):
    sys.path.insert(0, str(ROOT / "src" / p))
from source_binding import (content_anchor, verify_same_content,
                            build_evidence_ref, snapshot_anchor)
from knowledge_store import KnowledgeStore

REAL_DB = Path("/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data/kb.db")
COMMIT = "8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024"
TREE = "c668da9687b98d340616ce1e4c2ede911d090ec3"


def _assets_fp(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = list(con.execute(
        "SELECT asset_id, asset_type, repository_id, asset_version, content_hash "
        "FROM assets ORDER BY asset_id"))
    con.close()
    return hashlib.sha256(json.dumps([list(r) for r in rows], ensure_ascii=False).encode()).hexdigest()


class TestAnchorPure(unittest.TestCase):
    def test_same_content_different_repo_same_anchor(self):
        left = {"commit_sha": COMMIT, "root_tree_sha": TREE, "repository_id": "1459544036"}
        right = {"commit_sha": COMMIT, "root_tree_sha": TREE, "repository_id": "local:4034d62ed2cf"}
        v = verify_same_content(left, right)
        self.assertTrue(v["ok"])
        self.assertEqual(v["subject_id"], content_anchor(COMMIT, TREE))
        self.assertFalse(v["same_repository"])
        # 完整性差异不参与身份判定
        self.assertEqual(verify_same_content(
            {**left, "completeness_status": "COMPLETE", "tree_entry_count": 9},
            {**right, "completeness_status": "COMPLETE", "tree_entry_count": 27})["ok"], True)

    def test_different_commit_rejected(self):
        v = verify_same_content(
            {"commit_sha": COMMIT, "root_tree_sha": TREE},
            {"commit_sha": "f" * 40, "root_tree_sha": TREE})
        self.assertFalse(v["ok"])
        self.assertIn("COMMIT_MISMATCH", v["reasons"])
        self.assertIsNone(v["subject_id"])

    def test_different_root_tree_rejected(self):
        v = verify_same_content(
            {"commit_sha": COMMIT, "root_tree_sha": TREE},
            {"commit_sha": COMMIT, "root_tree_sha": "a" * 40})
        self.assertFalse(v["ok"])
        self.assertIn("ROOT_TREE_MISMATCH", v["reasons"])

    def test_empty_anchor_rejected(self):
        with self.assertRaises(ValueError):
            content_anchor("", TREE)
        with self.assertRaises(ValueError):
            content_anchor(COMMIT, "")

    def test_evidence_ref_is_traceable(self):
        left = {"commit_sha": COMMIT, "root_tree_sha": TREE,
                "asset_id": "SL-A-left", "repository_id": "1459544036"}
        right = {"commit_sha": COMMIT, "root_tree_sha": TREE,
                 "asset_id": "SL-A-right", "repository_id": "local:4034d62ed2cf"}
        ref = build_evidence_ref(left, right, content_anchor(COMMIT, TREE))
        self.assertIn(COMMIT, ref)
        self.assertIn(TREE, ref)
        self.assertIn("SL-A-left", ref)
        self.assertIn("SL-A-right", ref)


@unittest.skipUnless(REAL_DB.exists(), "real KB unavailable")
class TestBindingOnCopy(unittest.TestCase):
    def test_binding_does_not_mutate_a_layer(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "kb.db"
            shutil.copy2(REAL_DB, db)
            # 读快照锚点
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            rows = list(con.execute(
                "SELECT asset_id, repository_id, payload_json FROM assets "
                "WHERE asset_type LIKE '%snapshot%'"))
            con.close()
            snaps = []
            for r in rows:
                p = json.loads(r["payload_json"] or "{}")
                snaps.append(snapshot_anchor({**p, "asset_id": r["asset_id"],
                                              "repository_id": r["repository_id"]}))
            gh = [s for s in snaps if s["repository_id"] == "1459544036"
                  and s["commit_sha"] == COMMIT]
            lo = [s for s in snaps if s["repository_id"] == "local:4034d62ed2cf"
                  and s["commit_sha"] == COMMIT]
            self.assertEqual(len(gh), 1)
            self.assertEqual(len(lo), 1)
            v = verify_same_content(gh[0], lo[0])
            self.assertTrue(v["ok"])

            fp_before = _assets_fp(db)
            store = KnowledgeStore(str(db))
            try:
                ref = build_evidence_ref(gh[0], lo[0], v["subject_id"])
                r1 = store.bind_repo(subject_id=v["subject_id"],
                                     repository_id=gh[0]["repository_id"], evidence_ref=ref)
                r2 = store.bind_repo(subject_id=v["subject_id"],
                                     repository_id=lo[0]["repository_id"], evidence_ref=ref)
                self.assertTrue(r1["ok"] and r2["ok"])
                rel = store.same_subject_across_repos(v["subject_id"])
                self.assertEqual(
                    {b["repository_id"] for b in rel["bindings"]},
                    {"1459544036", "local:4034d62ed2cf"})
                # 无证据绑定被拒绝
                bad = store.bind_repo(subject_id=v["subject_id"],
                                      repository_id="x", evidence_ref="")
                self.assertFalse(bad["ok"])
            finally:
                store.close()
            self.assertEqual(_assets_fp(db), fp_before, "A 层资产被改动")

    def test_source_has_non_destructive_binding_only(self):
        # 只检查实际代码行，不把模块文档字符串里提到的表名当作写操作
        code_lines = []
        in_doc = False
        for line in (ROOT / "src" / "trust" / "source_binding.py").read_text(
                encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith('"""'):
                in_doc = not in_doc if stripped.count('"""') == 1 else in_doc
                continue
            if in_doc or not stripped or stripped.startswith("#"):
                continue
            code_lines.append(line)
        code = "\n".join(code_lines)
        for forbidden in ("DELETE FROM assets", "UPDATE assets", "INSERT INTO assets",
                          "current_view", "index_rows", "sqlite3", "conn.execute"):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
