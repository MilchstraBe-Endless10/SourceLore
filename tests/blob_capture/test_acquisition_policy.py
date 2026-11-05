#!/usr/bin/env python3
"""授权门禁：五档权限分离、白名单、路径安全。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"blob_capture"))
import sfx
import content_acquisition_policy as POL


class TestPreflight(unittest.TestCase):
    base = dict(repository_id="1", commit_sha="a"*40, file_path="README.md",
                object_type="blob", purpose="internal_analysis")

    def test_license_unknown_blocks_write(self):
        st, code, note = POL.preflight(**self.base, license_known=False)
        self.assertEqual(st, POL.ACQ_UNKNOWN)
        self.assertEqual(code, "LICENSE_UNKNOWN")
        self.assertIn("不得写入原始字节", note)

    def test_license_known_allows_internal_only(self):
        """★ 有许可 → 允许内部采集，但分发仍 false。"""
        st, code, note = POL.preflight(**self.base, license_known=True,
                                       copy_permitted=False,
                                       distribution_allowed=False)
        self.assertEqual(st, POL.ACQ_ALLOWED)
        self.assertIn("copy_permitted=false", note)
        self.assertIn("distribution_allowed=false", note)

    def test_project_owned_allowed(self):
        st, code, _ = POL.preflight(**self.base, repo_looks_third_party=False)
        self.assertEqual(st, POL.ACQ_ALLOWED)
        self.assertEqual(code, "PROJECT_OWNED_REPO")

    def test_symlink_blocked(self):
        st, code, _ = POL.preflight(**{**self.base, "object_type": "symlink"},
                                    license_known=True)
        self.assertEqual(st, POL.ACQ_BLOCKED)
        self.assertEqual(code, "OBJECT_TYPE_NOT_ALLOWED")

    def test_submodule_blocked(self):
        st, code, _ = POL.preflight(**{**self.base, "object_type": "submodule"},
                                    license_known=True)
        self.assertEqual(st, POL.ACQ_BLOCKED)

    def test_purpose_restricted(self):
        st, code, _ = POL.preflight(**{**self.base, "purpose": "redistribution"},
                                    license_known=True)
        self.assertEqual(st, POL.ACQ_BLOCKED)
        self.assertEqual(code, "PURPOSE_NOT_ALLOWED")

    def test_missing_identity(self):
        st, code, _ = POL.preflight(**{**self.base, "commit_sha": ""},
                                    license_known=True)
        self.assertEqual(st, POL.ACQ_BLOCKED)
        self.assertEqual(code, "IDENTITY_INCOMPLETE")


class TestPathSafety(unittest.TestCase):
    def test_traversal_rejected(self):
        for bad in ("../etc/passwd", "a/../../b", "/abs/path"):
            self.assertFalse(POL.path_is_safe(bad), bad)

    def test_sensitive_names_rejected(self):
        for bad in (".env", ".npmrc", "id_rsa", "credentials",
                    "secrets.json", ".netrc"):
            self.assertFalse(POL.path_is_safe(bad), bad)

    def test_normal_paths_ok(self):
        for ok in ("README.md", "package.json", "docs/README.md"):
            self.assertTrue(POL.path_is_safe(ok), ok)

    def test_overlong_rejected(self):
        self.assertFalse(POL.path_is_safe("a" * 300))


class TestCandidates(unittest.TestCase):
    def test_root_whitelist_only(self):
        tree = [
            {"path": "README.md", "type": "blob"},
            {"path": "package.json", "type": "blob"},
            {"path": "src/main.py", "type": "blob"},
            {"path": "docs/README.md", "type": "blob"},
        ]
        eligible, blocked = POL.candidate_paths(tree)
        paths = {e["file_path"] for e in eligible}
        self.assertEqual(paths, {"README.md", "package.json"},
                         "子目录不在默认白名单内")

    def test_case_insensitive_match(self):
        tree = [{"path": "ReadMe.MD", "type": "blob"}]
        eligible, _ = POL.candidate_paths(tree)
        self.assertEqual(eligible[0]["file_path"], "ReadMe.MD",
                         "保留实际 Git 路径，不改写大小写")

    def test_explicit_subdir_allowed(self):
        tree = [{"path": "docs/README.md", "type": "blob"}]
        eligible, _ = POL.candidate_paths(tree, explicit=["docs/README.md"])
        self.assertEqual(len(eligible), 1)

    def test_explicit_missing_path(self):
        tree = []
        eligible, blocked = POL.candidate_paths(tree, explicit=["x.md"])
        self.assertEqual(blocked[0]["reason"], "PATH_NOT_IN_SNAPSHOT")

    def test_no_match(self):
        tree = [{"path": "src/a.py", "type": "blob"}]
        eligible, blocked = POL.candidate_paths(tree)
        self.assertEqual(eligible, [])
        self.assertEqual(blocked, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
