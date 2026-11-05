#!/usr/bin/env python3
"""Blob Store 不可变性：不覆盖、并发、崩溃恢复。"""
import sys, unittest, tempfile, shutil, hashlib, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content_persistence"))
import sfx
import blob_content_store as BS


class TestNoOverwrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="imm_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_new_content_exclusive_create(self):
        r = BS.put_bytes(data_root=self.tmp, raw=b"abc")
        self.assertTrue(r["ok"])
        self.assertTrue(r.get("created_exclusive"))

    def test_existing_same_content_reused(self):
        raw = b"abc"
        a = BS.put_bytes(data_root=self.tmp, raw=raw)
        b = BS.put_bytes(data_root=self.tmp, raw=raw)
        self.assertTrue(a["ok"] and b["ok"])
        self.assertTrue(b["reused"])
        self.assertEqual(a["path"], b["path"])

    def test_existing_corrupt_refused_not_overwritten(self):
        """★ 阻断级：已有错误内容必须拒绝，绝不覆盖。"""
        raw = b"ORIGINAL"
        a = BS.put_bytes(data_root=self.tmp, raw=raw)
        Path(a["path"]).write_bytes(b"TAMPERED")
        b = BS.put_bytes(data_root=self.tmp, raw=raw)
        self.assertFalse(b["ok"])
        self.assertEqual(b["error"], BS.INTEGRITY_CONFLICT)
        self.assertEqual(Path(a["path"]).read_bytes(), b"TAMPERED",
                         "已被篡改的文件不得被覆盖回原内容")

    def test_existing_not_regular_file(self):
        raw = b"x"
        d = BS.store_root(self.tmp)
        d.mkdir(parents=True, exist_ok=True)
        target = BS._path_for(d, hashlib.sha256(raw).hexdigest())
        target.mkdir()
        r = BS.put_bytes(data_root=self.tmp, raw=raw)
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], BS.INTEGRITY_CONFLICT)

    def test_expected_sha_mismatch_refused(self):
        r = BS.put_bytes(data_root=self.tmp, raw=b"abc",
                         expected_sha256="sha256:"+"0"*64)
        self.assertFalse(r["ok"])

    def test_orphan_cleanup_keeps_referenced(self):
        a = BS.put_bytes(data_root=self.tmp, raw=b"keep")
        b = BS.put_bytes(data_root=self.tmp, raw=b"drop")
        d = a["digest"].split("sha256:")[1]
        res = BS.cleanup_orphans(data_root=self.tmp, referenced={d})
        self.assertEqual(res["kept"], 1)
        self.assertEqual(res["removed"], 1)
        self.assertTrue(Path(a["path"]).exists(), "被引用 Blob 不得删除")
        self.assertFalse(Path(b["path"]).exists())

    def test_concurrent_same_content(self):
        """两进程并发写同内容 → 一份字节，无损坏。"""
        raw = b"concurrent-bytes"
        import threading
        results = []
        def w():
            results.append(BS.put_bytes(data_root=self.tmp, raw=raw))
        ts = [threading.Thread(target=w) for _ in range(4)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertTrue(all(r["ok"] for r in results), results)
        self.assertTrue(all(r["digest"] == results[0]["digest"] for r in results))
        got = BS.get_bytes(data_root=self.tmp,
                           content_sha256=results[0]["digest"], verify=True)
        self.assertTrue(got["ok"])
        self.assertEqual(got["raw"], raw)

    def test_tmp_files_cleaned(self):
        d = BS.store_root(self.tmp); d.mkdir(parents=True, exist_ok=True)
        (d/("dead"+".tmp")).write_bytes(b"junk")
        res = BS.cleanup_orphans(data_root=self.tmp, referenced=set())
        self.assertGreaterEqual(res["removed"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
