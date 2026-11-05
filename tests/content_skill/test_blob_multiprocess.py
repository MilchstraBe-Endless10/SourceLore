#!/usr/bin/env python3
"""多进程 Blob Store 可靠性。"""
import sys, unittest, tempfile, shutil, hashlib, subprocess, os, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_skill"))
import sfx
import blob_content_store as BS

WORKER = r'''
import sys, json
sys.path.insert(0, {root!r})
import blob_content_store as BS
raw = bytes.fromhex({hexdata!r})
r = BS.put_bytes(data_root={tmp!r}, raw=raw)
print(json.dumps({{"ok": r.get("ok"), "digest": r.get("digest"),
                  "reused": r.get("reused"), "path": r.get("path"),
                  "error": r.get("error")}}))
'''.replace("{", "{{").replace("}}", "}").replace("{{", "{")


class TestMultiprocess(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mproc_"))
        self.raw = b"shared-content-for-multiprocess"
        self.hexdata = self.raw.hex()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _spawn(self):
        code = (
            "import sys, json\n"
            f"sys.path.insert(0, {str(ROOT/'src'/'storage')!r})\n"
            "import blob_content_store as BS\n"
            f"r = BS.put_bytes(data_root={str(self.tmp)!r}, raw=bytes.fromhex({self.hexdata!r}))\n"
            "print(json.dumps({'ok': r.get('ok'), 'digest': r.get('digest'),"
            " 'reused': r.get('reused'), 'path': r.get('path'),"
            " 'error': r.get('error')}))\n")
        p = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr[-300:])
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_four_processes_same_blob(self):
        """★ 四个独立进程同时写同一 Blob。"""
        results = [self._spawn() for _ in range(4)]
        self.assertTrue(all(r["ok"] for r in results), results)
        digests = {r["digest"] for r in results}
        self.assertEqual(len(digests), 1, "四进程必须得到同一摘要")
        paths = {r["path"] for r in results}
        self.assertEqual(len(paths), 1, "必须只保留一个合法对象")

        got = BS.get_bytes(data_root=self.tmp,
                           content_sha256=results[0]["digest"], verify=True)
        self.assertTrue(got["ok"])
        self.assertEqual(got["raw"], self.raw)

    def test_existing_corrupt_object_detected(self):
        """★ 已存在损坏对象时一致性检查必须失败。"""
        put = BS.put_bytes(data_root=self.tmp, raw=self.raw)
        Path(put["path"]).write_bytes(b"corrupted!")
        got = BS.get_bytes(data_root=self.tmp, content_sha256=put["digest"],
                           verify=True)
        self.assertFalse(got["ok"])
        self.assertEqual(got["error"], BS.INTEGRITY_FAILED)

    def test_corrupt_not_deleted_or_overwritten(self):
        put = BS.put_bytes(data_root=self.tmp, raw=self.raw)
        Path(put["path"]).write_bytes(b"corrupted!")
        r = BS.put_bytes(data_root=self.tmp, raw=self.raw)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], BS.INTEGRITY_CONFLICT)
        self.assertEqual(Path(put["path"]).read_bytes(), b"corrupted!",
                         "损坏对象不得被删除或覆盖")

    def test_referenced_blob_not_deleted(self):
        a = BS.put_bytes(data_root=self.tmp, raw=b"referenced")
        d = a["digest"].split("sha256:")[1]
        BS.cleanup_orphans(data_root=self.tmp, referenced={d})
        self.assertTrue(Path(a["path"]).exists())

    def test_tmp_leftovers_identifiable(self):
        root = BS.store_root(self.tmp); root.mkdir(parents=True, exist_ok=True)
        (root/("orphan"+".tmp")).write_bytes(b"x")
        res = BS.cleanup_orphans(data_root=self.tmp, referenced=set())
        self.assertGreaterEqual(res["removed"], 1)

    def test_asset_committed_but_bytes_lost(self):
        """★ SQLite 资产已提交但字节丢失 → 明确完整性错误。"""
        import content_ingest_coordinator as CIC
        import captured_blob_loader as L
        from knowledge_store import KnowledgeStore
        ks = KnowledgeStore(str(self.tmp/"kb.db"))
        try:
            r = CIC.ingest_captured_blob(
                ks, data_root=self.tmp, repository_id="990001",
                commit_sha="a"*40, source_snapshot_id="S1",
                file_path="README.md", git_blob_oid="b"*40,
                git_object_format="sha1", raw=self.raw,
                source_declared_size=len(self.raw),
                acquisition_policy="ACQUISITION_ALLOWED",
                acquisition_policy_ref="T")
            self.assertTrue(r["ok"])
            pl = CIC.find_content_asset(ks, repository_id="990001",
                                        commit_sha="a"*40,
                                        file_path="README.md")
            path = BS._path_for(BS.store_root(self.tmp),
                                pl["content_sha256"].split("sha256:")[1])
            path.unlink()
            got = L.load_captured_blob(store=ks, data_root=self.tmp,
                                       repository_id="990001",
                                       commit_sha="a"*40,
                                       file_path="README.md")
            self.assertEqual(got["status"], BS.ASSET_MISSING)
            self.assertIsNone(got["raw"])
        finally:
            ks.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
