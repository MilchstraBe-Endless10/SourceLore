#!/usr/bin/env python3
"""Monorepo：不同子项目不同 tsconfig，必须隔离。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"module_resolution"))
import sfx
import tsconfig_parser as TP
import config_aware_resolver as R


def tc(paths, config_dir, base_url=None):
    s = TP.extract_config_surface(
        {"compilerOptions": {"paths": paths,
                            **({"baseUrl": base_url} if base_url else {})}},
        config_dir=config_dir)
    return {"effective_config_status": "EFFECTIVE_CONFIG_RESOLVED",
            "config_observation_id": "CFG-" + config_dir,
            "declared_paths": s["paths"],
            "declared_base_url": s["base_url"],
            "_base_dir": TP.resolve_base_dir(config_dir=config_dir,
                                             base_url=s["base_url"]),
            "config_path": (config_dir + "/tsconfig.json").lstrip("/")}


class TestMonorepo(unittest.TestCase):
    TREE = {"packages/a/src/utils.ts", "packages/b/src/utils.ts"}

    def test_same_alias_different_projects(self):
        """★ 同一 alias 在两个子项目指向不同文件。"""
        a = R.resolve_with_config(
            specifier="@/utils", importing_file_path="packages/a/src/app.ts",
            tree_paths=self.TREE,
            tsconfig_observation=tc({"@/*": ["./src/*"]}, "packages/a"))
        b = R.resolve_with_config(
            specifier="@/utils", importing_file_path="packages/b/src/app.ts",
            tree_paths=self.TREE,
            tsconfig_observation=tc({"@/*": ["./src/*"]}, "packages/b"))
        self.assertEqual(a["resolved_target_path"], "packages/a/src/utils.ts")
        self.assertEqual(b["resolved_target_path"], "packages/b/src/utils.ts")

    def test_config_bound_to_import(self):
        r = R.resolve_with_config(
            specifier="@/utils", importing_file_path="packages/a/src/app.ts",
            tree_paths=self.TREE,
            tsconfig_observation=tc({"@/*": ["./src/*"]}, "packages/a"))
        self.assertEqual(r["config_observation_ids"], ["CFG-packages/a"])
        self.assertEqual(r["matched_config_path"], "packages/a/tsconfig.json")

    def test_no_config_means_not_captured(self):
        """★ 归属不确定时不得套用仓库根配置。"""
        r = R.resolve_with_config(
            specifier="@/utils", importing_file_path="packages/a/src/app.ts",
            tree_paths=self.TREE)
        self.assertEqual(r["resolution_state"], "CONFIG_NOT_CAPTURED")

    def test_wrong_project_config_gives_wrong_target(self):
        """★ 用错的配置会得到错误目标——证明必须绑定 importing file。"""
        wrong = R.resolve_with_config(
            specifier="@/utils", importing_file_path="packages/a/src/app.ts",
            tree_paths=self.TREE,
            tsconfig_observation=tc({"@/*": ["./src/*"]}, "packages/b"))
        self.assertEqual(wrong["resolved_target_path"],
                         "packages/b/src/utils.ts")

    def test_relative_uses_importing_file_dir(self):
        r = R.resolve_with_config(
            specifier="./helper", importing_file_path="packages/a/src/app.ts",
            tree_paths={"packages/a/src/helper.ts"})
        self.assertEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertEqual(r["resolved_target_path"],
                         "packages/a/src/helper.ts")


if __name__ == "__main__":
    unittest.main(verbosity=2)
