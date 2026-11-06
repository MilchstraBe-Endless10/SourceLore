#!/usr/bin/env python3
"""extends 与 references 区别、monorepo 归属、上下文选择。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"ts_projects"))
import sfx
import ts_project_context as C
import ts_project_models as PM

REPO = "990001"
COMMIT = "a"*40


def _k(k):
    k = k.replace("_DOT_", "\x00").replace("__", "/").replace("\x00", ".")
    if k.endswith("_json"):
        k = k[:-5] + ".json"
    return k


def blobs(**kw):
    out = {}
    for path, src in kw.items():
        key = _k(path)
        raw = src.encode() if isinstance(src, str) else src
        out[key] = {"raw": raw, "blob_oid": "b"*40,
                    "content_asset_id": "A-" + key,
                    "content_digest": "sha256:" + key}
    return out


class TestExtendsSemantics(unittest.TestCase):
    def test_references_not_inherited(self):
        """★ 父配置 references 不随 extends 继承。"""
        tree = {"tsconfig.json", "base.json", "packages/shared/tsconfig.json"}
        b = blobs(base_json='{"include":["src/**/*.ts"],'
                            '"references":[{"path":"./packages/shared"}]}',
                  tsconfig_json='{"extends":"./base.json","include":["app/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        child = next(x for x in r["projects"]
                     if x["config_path"] == "tsconfig.json")
        self.assertEqual(child["declared_references"], [],
                         "子配置不得继承父配置的 references")

    def test_child_own_references_kept(self):
        tree = {"tsconfig.json", "base.json", "packages/x/tsconfig.json"}
        b = blobs(base_json='{"include":["src/**/*.ts"]}',
                  tsconfig_json='{"extends":"./base.json",'
                                '"references":[{"path":"./packages/x"}]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        child = next(x for x in r["projects"]
                     if x["config_path"] == "tsconfig.json")
        self.assertEqual(len(child["declared_references"]), 1)

    def test_include_overridden_by_child(self):
        """★ 子配置 include 覆盖父配置。"""
        tree = {"tsconfig.json", "base.json", "app/a.ts", "src/b.ts"}
        b = blobs(base_json='{"include":["src/**/*.ts"]}',
                  tsconfig_json='{"extends":"./base.json","include":["app/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        child = next(x for x in r["projects"]
                     if x["config_path"] == "tsconfig.json")
        self.assertEqual(child["declared_include"], ["app/**/*.ts"])
        m = C.resolve_membership(file_path="app/a.ts",
                                 projects=r["projects"], details=r["details"],
                                 tree_paths=tree)
        self.assertEqual(m["state"], PM.INPUT_MATCHED_INCLUDE)
        m2 = C.resolve_membership(file_path="src/b.ts",
                                  projects=r["projects"], details=r["details"],
                                  tree_paths=tree)
        self.assertNotEqual(m2["state"], PM.INPUT_MATCHED_INCLUDE)


class TestMonorepoMembership(unittest.TestCase):
    def test_two_projects_isolated(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json",
                "packages/a/src/x.ts", "packages/b/src/y.ts"}
        b = blobs(packages__a__tsconfig_json='{"include":["src/**/*.ts"]}',
                  packages__b__tsconfig_json='{"include":["src/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        ma = C.resolve_membership(file_path="packages/a/src/x.ts",
                                  projects=r["projects"],
                                  details=r["details"], tree_paths=tree)
        self.assertEqual(ma["candidates"][0]["config_path"],
                         "packages/a/tsconfig.json")
        mb = C.resolve_membership(file_path="packages/b/src/y.ts",
                                  projects=r["projects"],
                                  details=r["details"], tree_paths=tree)
        self.assertEqual(mb["candidates"][0]["config_path"],
                         "packages/b/tsconfig.json")

    def test_same_file_two_projects(self):
        """★ 同一文件被两个项目选中 → 多候选，不擅定唯一。"""
        tree = {"tsconfig.json", "packages/a/tsconfig.json",
                "shared/u.ts"}
        b = blobs(tsconfig_json='{"include":["shared/**/*.ts"]}',
                  packages__a__tsconfig_json='{"include":["../../shared/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        m = C.resolve_membership(file_path="shared/u.ts",
                                 projects=r["projects"], details=r["details"],
                                 tree_paths=tree)
        self.assertEqual(m["state"], PM.INPUT_MATCHED_MULTIPLE_PROJECTS)
        self.assertEqual(len(m["candidates"]), 2)


class TestSolutionStyle(unittest.TestCase):
    def test_root_does_not_own_child_files(self):
        """★ solution-style 根配置不自动获得子项目文件归属。"""
        tree = {"tsconfig.json", "packages/a/tsconfig.json",
                "packages/a/src/x.ts"}
        b = blobs(tsconfig_json='{"files":[],"references":[{"path":"./packages/a"}]}',
                  packages__a__tsconfig_json='{"include":["src/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        root = next(x for x in r["projects"]
                    if x["config_path"] == "tsconfig.json")
        self.assertTrue(root["is_solution_style"])
        m = C.resolve_membership(file_path="packages/a/src/x.ts",
                                 projects=r["projects"], details=r["details"],
                                 tree_paths=tree)
        self.assertEqual(len(m["candidates"]), 1)
        self.assertEqual(m["candidates"][0]["config_path"],
                         "packages/a/tsconfig.json")

    def test_reference_built_for_solution(self):
        tree = {"tsconfig.json", "packages/a/tsconfig.json"}
        b = blobs(tsconfig_json='{"files":[],"references":[{"path":"./packages/a"}]}',
                  packages__a__tsconfig_json='{}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        self.assertGreaterEqual(len(r["references"]), 1)
        self.assertEqual(r["references"][0]["status"],
                         PM.PROJECT_REFERENCE_TARGET_VERIFIED)


class TestContextSelection(unittest.TestCase):
    def test_single_project_selected(self):
        tree = {"tsconfig.json", "src/a.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        ctx = C.select_project_context(file_path="src/a.ts",
                                       projects=r["projects"],
                                       details=r["details"],
                                       tree_paths=tree)
        self.assertEqual(ctx["state"], PM.PROJECT_CONTEXT_SELECTED)

    def test_ambiguous_context_not_forced(self):
        """★ 归属歧义时不得强行选一个配置。"""
        tree = {"tsconfig.json", "packages/a/tsconfig.json", "shared/u.ts"}
        b = blobs(tsconfig_json='{"include":["shared/**/*.ts"]}',
                  packages__a__tsconfig_json='{"include":["../../shared/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        ctx = C.select_project_context(file_path="shared/u.ts",
                                       projects=r["projects"],
                                       details=r["details"],
                                       tree_paths=tree)
        self.assertEqual(ctx["state"], PM.PROJECT_CONTEXT_AMBIGUOUS)
        self.assertIsNone(ctx["project"])

    def test_ambiguous_multi_root_fallback_ambiguous(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json",
                "other/z.ts"}
        b = blobs(packages__a__tsconfig_json='{"include":["src/**/*.ts"]}',
                  packages__b__tsconfig_json='{"include":["src/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        ctx = C.select_project_context(file_path="other/z.ts",
                                       projects=r["projects"],
                                       details=r["details"],
                                       tree_paths=tree)
        self.assertEqual(ctx["state"], PM.PROJECT_CONTEXT_AMBIGUOUS)

    def test_no_project(self):
        tree = {"src/a.ts"}
        ctx = C.select_project_context(file_path="src/a.ts", projects=[],
                                       details={}, tree_paths=tree)
        self.assertEqual(ctx["state"], PM.PROJECT_CONTEXT_NONE)

    def test_unverified_config_not_selected(self):
        tree = {"tsconfig.json", "src/a.ts"}
        r = C.build_all_projects(tree_paths=tree, config_blobs={},
                                 repository_id=REPO, commit_sha=COMMIT)
        ctx = C.select_project_context(file_path="src/a.ts",
                                       projects=r["projects"],
                                       details=r["details"],
                                       tree_paths=tree)
        self.assertEqual(ctx["state"], PM.PROJECT_CONTEXT_NONE)


class TestTreeIncomplete(unittest.TestCase):
    def test_file_not_in_tree(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        r = C.build_all_projects(tree_paths=tree, config_blobs=b,
                                 repository_id=REPO, commit_sha=COMMIT)
        m = C.resolve_membership(file_path="src/missing.ts",
                                 projects=r["projects"], details=r["details"],
                                 tree_paths=tree)
        self.assertEqual(m["state"], PM.INPUT_MATCHED_INCLUDE,
                         "include 匹配不依赖 Tree 存在性")


if __name__ == "__main__":
    unittest.main(verbosity=2)
