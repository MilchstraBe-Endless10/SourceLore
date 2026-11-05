#!/usr/bin/env python3
"""E2E：原创夹具 → 存储 → 读回 → 解析 → Facts → Claim → 裁决。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_persistence"))
import sfx
import fixtures as FX
import pipeline as PL
import blob_content_store as BS
import captured_blob_loader as L
import content_acquisition_policy as POL
import content_claim_adapter as CA
from knowledge_store import KnowledgeStore

FILES = [("README.md", FX.README_A), ("package.json", FX.PKG)]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="e2e_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestE2E1Readme(Base):
    def test_full_chain(self):
        snap_id, snap_li = PL.make_snapshot(self.ks, FX.COMMIT_A, FILES)
        content = PL.capture(self.ks, self.tmp, snap_id, FX.COMMIT_A, FILES)
        self.assertTrue(content["README.md"]["ok"])

        # 离线读回
        back = L.load_captured_blob(store=self.ks, data_root=self.tmp,
                                    repository_id=FX.REPO,
                                    commit_sha=FX.COMMIT_A,
                                    file_path="README.md")
        self.assertEqual(back["status"], BS.AVAILABLE_VERIFIED)
        self.assertEqual(back["raw"], FX.README_A)

        # 解析 + Facts
        res = PL.extract_and_ingest(self.ks, snap_id, snap_li, FX.COMMIT_A,
                                    content, paths=["README.md"])
        facts = res["README.md"]["facts"]
        self.assertGreater(len(facts), 0, "README 应产生事实")

        # Claim 裁决：Installation 存在
        c, b = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=FX.REPO,
            commit_sha=FX.COMMIT_A, file_path="README.md",
            subject={"level": 2, "title": "Installation"})
        v = CA.verify_content_claim(claim=c, facts=facts,
                                    content_available=True,
                                    completeness_status="COMPLETE",
                                    subject_binding=b)
        self.assertEqual(v["status"], "supported")
        self.assertTrue(v["supported_fact_ids"], "supported 必须挂事实")

    def test_distribution_still_denied(self):
        snap_id, _ = PL.make_snapshot(self.ks, FX.COMMIT_A, FILES)
        content = PL.capture(self.ks, self.tmp, snap_id, FX.COMMIT_A, FILES)
        dec = content["README.md"]["decisions"]
        self.assertEqual(dec["DISTRIBUTION_DECISION"]["decision"], POL.DENY)
        self.assertEqual(dec["PERSIST_DECISION"]["decision"], POL.ALLOW)

    def test_idempotent(self):
        snap_id, snap_li = PL.make_snapshot(self.ks, FX.COMMIT_A, FILES)
        c1 = PL.capture(self.ks, self.tmp, snap_id, FX.COMMIT_A, FILES)
        c2 = PL.capture(self.ks, self.tmp, snap_id, FX.COMMIT_A, FILES)
        self.assertEqual(c1["README.md"]["asset_id"], c2["README.md"]["asset_id"],
                         "同内容重复采集必须复用同一资产")

        # ★ 抽取两次再比：第一次抽取会新增事实，不能拿它做基线
        PL.extract_and_ingest(self.ks, snap_id, snap_li, FX.COMMIT_A, c1,
                              paths=["README.md"])
        n1 = self.ks.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE asset_type=?",
            ("extracted_fact",)).fetchone()["c"]
        r2 = PL.extract_and_ingest(self.ks, snap_id, snap_li, FX.COMMIT_A, c2,
                                   paths=["README.md"])
        n2 = self.ks.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE asset_type=?",
            ("extracted_fact",)).fetchone()["c"]
        self.assertEqual(n1, n2, "重复抽取不得新增事实")
        self.assertGreater(len(r2["README.md"]["ingest"]["reused"]), 0,
                           "第二次应命中复用而非重写")


class TestE2E2Manifest(Base):
    def test_manifest_facts(self):
        snap_id, snap_li = PL.make_snapshot(self.ks, FX.COMMIT_A, FILES)
        content = PL.capture(self.ks, self.tmp, snap_id, FX.COMMIT_A, FILES)
        res = PL.extract_and_ingest(self.ks, snap_id, snap_li, FX.COMMIT_A,
                                    content, paths=["package.json"])
        facts = res["package.json"]["facts"]
        self.assertGreater(len(facts), 0)
        rules = {f["rule_id"] for f in facts}
        self.assertTrue(any("MANIFEST" in r for r in rules), rules)


class TestE2E3TwoCommits(Base):
    def test_commit_isolation(self):
        """两 Commit 内容共存，Fact 不覆盖，Claim 不混用。"""
        fa = [("README.md", FX.README_A)]
        fb = [("README.md", FX.README_B)]
        sa, la = PL.make_snapshot(self.ks, FX.COMMIT_A, fa)
        sb, lb = PL.make_snapshot(self.ks, FX.COMMIT_B, fb)
        ca = PL.capture(self.ks, self.tmp, sa, FX.COMMIT_A, fa)
        cb = PL.capture(self.ks, self.tmp, sb, FX.COMMIT_B, fb)

        self.assertNotEqual(ca["README.md"]["asset_id"],
                            cb["README.md"]["asset_id"],
                            "不同 Commit 必须是不同内容资产")

        ra = PL.extract_and_ingest(self.ks, sa, la, FX.COMMIT_A, ca)
        rb = PL.extract_and_ingest(self.ks, sb, lb, FX.COMMIT_B, cb)

        # Commit A 有 Installation，Commit B 没有
        cA, bA = CA.build_content_claim(
            claim_type="readme_heading_exists", repository_id=FX.REPO,
            commit_sha=FX.COMMIT_A, file_path="README.md",
            subject={"level": 2, "title": "Installation"})
        vA = CA.verify_content_claim(claim=cA, facts=ra["README.md"]["facts"],
                                     content_available=True,
                                     completeness_status="COMPLETE",
                                     subject_binding=bA)
        self.assertEqual(vA["status"], "supported")

        # 用 Commit B 的 facts 验 Commit A 的命题 → 必须不 supported
        vX = CA.verify_content_claim(claim=cA, facts=rb["README.md"]["facts"],
                                     content_available=True,
                                     completeness_status="COMPLETE",
                                     subject_binding=bA)
        self.assertNotEqual(vX["status"], "supported",
                            "★ 跨 Commit 证据不得确认命题")

    def test_read_by_commit(self):
        fa = [("README.md", FX.README_A)]
        fb = [("README.md", FX.README_B)]
        for commit, files in ((FX.COMMIT_A, fa), (FX.COMMIT_B, fb)):
            sid, _ = PL.make_snapshot(self.ks, commit, files)
            PL.capture(self.ks, self.tmp, sid, commit, files)
        got_a = L.load_captured_blob(store=self.ks, data_root=self.tmp,
                                     repository_id=FX.REPO,
                                     commit_sha=FX.COMMIT_A,
                                     file_path="README.md")
        got_b = L.load_captured_blob(store=self.ks, data_root=self.tmp,
                                     repository_id=FX.REPO,
                                     commit_sha=FX.COMMIT_B,
                                     file_path="README.md")
        self.assertEqual(got_a["raw"], FX.README_A)
        self.assertEqual(got_b["raw"], FX.README_B)


if __name__ == "__main__":
    unittest.main(verbosity=2)
