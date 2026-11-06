#!/usr/bin/env python3
"""TS 项目配置发现与解析。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"ts_projects"))
import sfx
import ts_project_context as C
import ts_project_models as PM

REPO = "990001"
COMMIT = "a"*40


def _decode_key(k):
    """把 python 标识符还原成路径：__ → / ，_DOT_ → . ，末尾 _json → .json"""
    k = k.replace("_DOT_", "\x00").replace("__", "/")
    k = k.replace("\x00", ".")
    if k.endswith("_json"):
        k = k[:-5] + ".json"
    return k


def blobs(**kw):
    out = {}
    for path, src in kw.items():
        key = _decode_key(path)
        raw = src.encode() if isinstance(src, str) else src
        out[key] = {"raw": raw, "blob_oid": "b"*40,
                    "content_asset_id": "A-" + key,
                    "content_digest": "sha256:" + key}
    return out


class TestDiscovery(unittest.TestCase):
    def test_finds_tsconfig(self):
        tree = {"tsconfig.json", "src/a.ts"}
        got = C.discover_config_paths(tree_paths=tree)
        self.assertEqual(got, ["tsconfig.json"])

    def test_finds_multiple(self):
        tree = {"tsconfig.json", "packages/a/tsconfig.json",
                "packages/b/jsconfig.json", "src/a.ts"}
        got = C.discover_config_paths(tree_paths=tree)
        self.assertEqual(len(got), 3)
        self.assertIn("packages/b/jsconfig.json", got)

    def test_not_captured(self):
        tree = {"tsconfig.json", "src/a.ts"}
        r = C.build_all_projects(tree_paths=tree, config_blobs={},
                                 repository_id=REPO, commit_sha=COMMIT)
        p = r["projects"][0]
        self.assertEqual(p["discovery_status"],
                         PM.PROJECT_CONFIG_NOT_CAPTURED)

    def test_invalid_config(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"compilerOptions": }')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        self.assertEqual(r["projects"][0]["discovery_status"],
                         PM.PROJECT_CONFIG_INVALID)

    def test_valid_config(self):
        tree = {"tsconfig.json", "src/a.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        p = r["projects"][0]
        self.assertEqual(p["discovery_status"], PM.PROJECT_CONFIG_VERIFIED)
        self.assertEqual(p["declared_include"], ["src/**/*.ts"])

    def test_identity_includes_commit(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"include":["src/*.ts"]}')
        a = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        c = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha="c"*40)
        self.assertNotEqual(
            a["projects"][0]["project_observation_id"],
            c["projects"][0]["project_observation_id"])

    def test_project_root_is_config_dir(self):
        tree = {"packages/a/tsconfig.json"}
        b = blobs(packages__a__tsconfig_json='{"include":["src/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        self.assertEqual(r["projects"][0]["project_root"], "packages/a")

    def test_composite_recorded(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"compilerOptions":{"composite":true,'
                                '"rootDir":"src","outDir":"dist"}}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        p = r["projects"][0]
        self.assertTrue(p["declared_composite"])
        self.assertEqual(p["declared_root_dir"], "src")
        self.assertEqual(p["declared_out_dir"], "dist")

    def test_extends_unresolved_when_no_reader(self):
        tree = {"tsconfig.json", "base.json"}
        b = blobs(tsconfig_json='{"extends":"./base.json"}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        p = next(x for x in r["projects"]
                 if x["config_path"] == "tsconfig.json")
        self.assertEqual(p["discovery_status"],
                         PM.PROJECT_CONFIG_INHERITANCE_UNRESOLVED)

    def test_extends_resolved_with_reader(self):
        tree = {"tsconfig.json", "base.json"}
        b = blobs(tsconfig_json='{"extends":"./base.json"}',
                  base_json='{"include":["src/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        p = next(x for x in r["projects"]
                 if x["config_path"] == "tsconfig.json")
        self.assertEqual(p["discovery_status"], PM.PROJECT_CONFIG_VERIFIED)
        self.assertGreaterEqual(len(p["inheritance_chain"]), 1)

    def test_jsonc_comments_accepted(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{\n// comment\n"include":["src/*.ts"]\n}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        self.assertEqual(r["projects"][0]["discovery_status"],
                         PM.PROJECT_CONFIG_VERIFIED)

    def test_solution_style_detected(self):
        tree = {"tsconfig.json", "packages/a/tsconfig.json"}
        b = blobs(tsconfig_json='{"files":[],"references":[{"path":"./packages/a"}]}',
                  packages__a__tsconfig_json='{"include":["src/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        root = next(x for x in r["projects"]
                    if x["config_path"] == "tsconfig.json")
        self.assertTrue(root["is_solution_style"])

    def test_empty_files_is_not_solution_without_refs(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"files":[]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        self.assertFalse(r["projects"][0]["is_solution_style"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
