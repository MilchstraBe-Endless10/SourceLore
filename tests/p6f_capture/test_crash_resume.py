#!/usr/bin/env python3
"""T2/T3/T13 跨进程崩溃恢复（真子进程，不是同进程模拟）。"""
import json, os, subprocess, sys, tempfile, shutil, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(tempfile.mkdtemp(prefix="p6f_cr_"))

WORKER = r'''
import sys, json
sys.path.insert(0, r"%s")
for p in ("collector","storage","runtime","content","content_persistence",
          "source_analysis","facts","evidence_claims","skill_interface"):
    sys.path.insert(0, r"%s" + "/src/" + p)
import content_ingest_coordinator as CIC
from knowledge_store import KnowledgeStore
from source_snapshot import build_snapshot
from ingest_coordinator import ingest_snapshot
from paths import db_path

root = r"%s"
ks = KnowledgeStore(str(db_path(root)))
te = [{"path": "a.js", "sha": "ab"*20, "size": 20, "type": "blob", "mode": "100644"}]
if %s:
    snap = build_snapshot(repository_id="r1", requested_repository="o/r",
                          resolved_repository="o/r", requested_ref="main",
                          commit_sha="c"*40, root_tree_sha="t"*40,
                          tree_query_ref="t"*40, completeness_status="COMPLETE",
                          tree_entries=te, collected_at="", evidence_refs=["e"])
    ingest_snapshot(ks, snap)
r = CIC.ingest_captured_blob(
    ks, data_root=root, repository_id="r1", commit_sha="c"*40,
    source_snapshot_id="s", file_path="a.js", git_blob_oid="ab"*20,
    git_object_format="sha1", raw=b"export const a = 1;\n",
    source_declared_size=20, acquisition_policy="ACQUISITION_ALLOWED",
    acquisition_policy_ref="ORIGINAL_TEST_FIXTURE",
    provenance_level="SYNTHETIC_FIXTURE")
print(json.dumps({"ok": r.get("ok"), "asset": r.get("content_asset_id"),
                  "reused": r.get("reused")}))
ks.close()
'''


def run_worker(seed, data=DATA):
    code = WORKER % (str(ROOT), str(ROOT), str(data), "True" if seed else "False")
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=90)
    return r.returncode, r.stdout, r.stderr


class TestCrashResume(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DATA.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(DATA, ignore_errors=True)

    def test_T2_written_in_child_survives_process_exit(self):
        """T2：子进程写完就退出；父进程重开库必须读回。"""
        rc, out, err = run_worker(seed=True)
        self.assertEqual(rc, 0, err[-500:])
        d = json.loads(out.strip().splitlines()[-1])
        self.assertTrue(d["ok"], d)

        # 父进程独立重开
        for _p in ("storage", "content", "content_persistence", "runtime",
                   "skill_interface", "collector", "facts", "evidence_claims",
                   "source_analysis"):
            sys.path.insert(0, str(ROOT / "src" / _p))
        import content_ingest_coordinator as CIC
        from knowledge_store import KnowledgeStore
        from paths import db_path
        ks = KnowledgeStore(str(db_path(str(DATA)), ), create=False)
        try:
            m = CIC.find_content_asset(ks, repository_id="r1",
                                       commit_sha="c" * 40, file_path="a.js")
            self.assertIsNotNone(m, "跨进程必须能读回")
            self.assertEqual((m.get("completeness_status") or "").upper(),
                             "COMPLETE")
        finally:
            ks.close()

    def test_T3_second_run_reuses_not_redownloads(self):
        """T3/T4：第二次运行必须复用，不重复写。"""
        rc, out, err = run_worker(seed=False)
        self.assertEqual(rc, 0, err[-500:])
        d = json.loads(out.strip().splitlines()[-1])
        self.assertTrue(d["reused"], "第二次必须是复用：%s" % d)

    def test_T15_repeat_no_asset_drift(self):
        """T15：重复执行，资产身份不变。"""
        rc1, out1, _ = run_worker(seed=False)
        rc2, out2, _ = run_worker(seed=False)
        a1 = json.loads(out1.strip().splitlines()[-1])["asset"]
        a2 = json.loads(out2.strip().splitlines()[-1])["asset"]
        self.assertEqual(a1, a2, "重复执行不得改资产身份")


if __name__ == "__main__":
    unittest.main(verbosity=2)
