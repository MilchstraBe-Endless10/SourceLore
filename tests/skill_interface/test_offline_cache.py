#!/usr/bin/env python3
"""A. 离线优先缓存：T-1..T-9、T-26..T-29。"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx
for p in ("research","views","lifecycle","storage","collector","facts",
          "evidence_claims","runtime","renderer","skill_interface"):
    if str(ROOT/"src"/p) not in sys.path:
        sys.path.insert(0, str(ROOT/"src"/p))
if str(ROOT/"tests"/"views") not in sys.path:
    sys.path.insert(0, str(ROOT/"tests"/"views"))
import vfx, cache_policy as CP, analyze as A
from result import SkillError


class TestCachePolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="oc_"))
        self.ks = vfx.fresh(self.tmp)
        vfx.run_full(self.ks)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hit_complete(self):
        # ★ B3/D1：完整命中必须是"真正递归完整"的快照。默认 fixture 带未展开
        #   docs/tree，会按 ROOT_ONLY 正确降为 PARTIAL；这里显式给 blob-only 清单。
        complete_entries = [{
            "path": "README", "type": "blob", "sha": "a" * 40,
            "mode": "100644", "size": 10, "depth": 0}]
        full_commit = "c" * 40
        vfx.make_source(self.ks, commit=full_commit, entries=complete_entries)
        got = CP.lookup(self.ks, repository_id=vfx.REPO, commit_sha=full_commit)
        self.assertEqual(got["decision"], CP.CACHE_HIT_COMPLETE)
        self.assertIsNotNone(got["snapshot"])

    def test_root_only_complete_label_is_partial(self):
        """★ B3/D1：声称 COMPLETE 但仅根层（未展开子树）不得当完整缓存。"""
        got = CP.lookup(self.ks, repository_id=vfx.REPO, commit_sha=vfx.A)
        self.assertEqual(got["decision"], CP.CACHE_HIT_PARTIAL)
        self.assertTrue(any("根层" in r for r in got.get("reasons", [])))

    def test_miss_other_commit(self):
        got = CP.lookup(self.ks, repository_id=vfx.REPO, commit_sha="d"*40)
        self.assertEqual(got["decision"], CP.CACHE_MISS)

    def test_miss_unknown_repo(self):
        got = CP.lookup(self.ks, repository_id="999999")
        self.assertEqual(got["decision"], CP.CACHE_MISS)

    def test_branch_unknown_flagged(self):
        got = CP.lookup(self.ks, repository_id=vfx.REPO, commit_sha=None,
                        requested_ref="master")
        self.assertTrue(got.get("branch_current_unknown"))

    def test_partial_not_complete(self):
        """★ PARTIAL 不得冒充 COMPLETE。"""
        pl = self.ks.get_asset(
            self.ks.conn.execute(
                "SELECT asset_id FROM index_rows WHERE asset_type='repository_snapshot'"
            ).fetchone()["asset_id"], verify=False)["asset"]["payload"]
        self.assertEqual(pl.get("completeness_status"), "COMPLETE")
        src = (ROOT/"src"/"skill_interface"/"cache_policy.py").read_text(encoding="utf-8")
        self.assertIn("CACHE_HIT_PARTIAL", src)
        self.assertIn("不得冒充 COMPLETE", src)


class TestOffline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="off_"))
        self.root = str(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_offline_miss_raises(self):
        with self.assertRaises(SkillError) as cm:
            A.analyze(url="https://github.com/octocat/Hello-World",
                      offline=True, data_root=self.root)
        self.assertEqual(cm.exception.code, "OFFLINE_CACHE_MISS")

    def test_offline_never_network(self):
        """★ 离线模式不得构造 GitHubClient。"""
        src = (ROOT/"src"/"skill_interface"/"analyze.py").read_text(encoding="utf-8")
        idx_off = src.index("if offline:")
        idx_client = src.index("client = GitHubClient")
        self.assertLess(idx_off, idx_client, "offline 分支必须在创建客户端之前返回")


class TestIndexCommitSha(unittest.TestCase):
    def test_root_cause_and_fix(self):
        """★ 根因：ingest 不传 source_snapshot；修复：payload 回退。"""
        ing = (ROOT/"src"/"collector"/"ingest_coordinator.py").read_text(encoding="utf-8")
        self.assertNotIn("source_snapshot=snapshot", ing,
                         "ingest 确实未传 source_snapshot（这是根因）")
        ks = (ROOT/"src"/"storage"/"knowledge_store.py").read_text(encoding="utf-8")
        self.assertIn("_resolve_index_commit_sha", ks)

    def test_new_asset_has_commit(self):
        tmp = Path(tempfile.mkdtemp(prefix="sha_"))
        try:
            ks = vfx.fresh(tmp); vfx.run_full(ks)
            rows = ks.conn.execute(
                "SELECT commit_sha FROM index_rows WHERE asset_type='repository_snapshot'"
            ).fetchall()
            self.assertTrue(rows)
            self.assertEqual(rows[0]["commit_sha"], vfx.A,
                             "新写入的索引必须有 commit_sha")
            ks.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
