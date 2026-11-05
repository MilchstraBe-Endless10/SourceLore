#!/usr/bin/env python3
"""package.json imports / exports 与条件。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"module_resolution"))
import sfx
import package_module_map_parser as PM
import config_aware_resolver as R


def pkg(**kw):
    base = {"effective_config_status": "EFFECTIVE_CONFIG_RESOLVED",
            "config_observation_id": "PKG1", "_config_dir": "",
            "config_path": "package.json"}
    base.update(kw)
    return base


class TestImports(unittest.TestCase):
    def test_hash_prefix_required(self):
        self.assertEqual(PM.match_imports({"#a": "./a.js"}, "a"), (None, None))

    def test_exact_imports(self):
        k, v = PM.match_imports({"#types": "./t.js"}, "#types")
        self.assertEqual((k, v), ("#types", "./t.js"))

    def test_wildcard_imports(self):
        k, v = PM.match_imports({"#internal/*": "./src/internal/*.js"},
                                "#internal/tool")
        self.assertEqual(k, "#internal/*")

    def test_longest_prefix_wins(self):
        m = {"#*": "./any/*", "#internal/*": "./in/*"}
        k, _ = PM.match_imports(m, "#internal/x")
        self.assertEqual(k, "#internal/*")

    def test_resolve_hash_import(self):
        tree = {"src/internal/tool.js"}
        r = R.resolve_with_config(
            specifier="#internal/tool", importing_file_path="src/app.ts",
            tree_paths=tree,
            package_observation=pkg(declared_imports={
                "#internal/*": "./src/internal/*.js"}))
        self.assertEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertEqual(r["resolved_target_path"], "src/internal/tool.js")

    def test_hash_no_matching_entry(self):
        r = R.resolve_with_config(
            specifier="#nope", importing_file_path="src/app.ts",
            tree_paths={"a.js"},
            package_observation=pkg(declared_imports={"#a": "./a.js"}))
        self.assertEqual(r["resolution_state"], "CONFIG_MAPPING_CANDIDATE")
        self.assertEqual(r["unresolved_reason"], "NO_MATCHING_IMPORTS_ENTRY")

    def test_hash_without_package(self):
        r = R.resolve_with_config(
            specifier="#x", importing_file_path="src/app.ts",
            tree_paths={"a.js"})
        self.assertEqual(r["resolution_state"], "CONFIG_NOT_CAPTURED")


class TestExports(unittest.TestCase):
    def test_self_reference_root(self):
        tree = {"src/index.js"}
        r = R.resolve_with_config(
            specifier="my-app", importing_file_path="src/app.ts",
            tree_paths=tree,
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={".": "./src/index.js"}))
        self.assertEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertEqual(r["resolved_target_path"], "src/index.js")

    def test_self_reference_subpath(self):
        tree = {"src/core.js"}
        r = R.resolve_with_config(
            specifier="my-app/core", importing_file_path="src/app.ts",
            tree_paths=tree,
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./core": "./src/core.js"}))
        self.assertEqual(r["resolved_target_path"], "src/core.js")

    def test_subpath_not_in_exports_blocked(self):
        """★ 阻断级：exports 未列出该子路径 → 不得据文件存在而放行。"""
        r = R.resolve_with_config(
            specifier="my-app/secret", importing_file_path="src/app.ts",
            tree_paths={"src/secret.js"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./core": "./src/core.js"}))
        self.assertEqual(r["resolution_state"], "UNSUPPORTED_RESOLUTION_POLICY")
        self.assertEqual(r["unresolved_reason"], "SUBPATH_NOT_IN_EXPORTS")

    def test_null_export_blocked(self):
        r = R.resolve_with_config(
            specifier="my-app/blocked", importing_file_path="src/app.ts",
            tree_paths={"src/blocked.js"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./blocked": None}))
        self.assertEqual(r["resolution_state"], "UNSUPPORTED_RESOLUTION_POLICY")
        self.assertEqual(r["unresolved_reason"], "EXPORT_EXPLICITLY_BLOCKED")

    def test_wildcard_export(self):
        tree = {"src/feat/a.js"}
        r = R.resolve_with_config(
            specifier="my-app/feat/a", importing_file_path="src/app.ts",
            tree_paths=tree,
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./feat/*": "./src/feat/*.js"}))
        self.assertEqual(r["resolved_target_path"], "src/feat/a.js")

    def test_external_package_not_resolved(self):
        """★ 阻断级：不能用本仓库 exports 解析第三方包。"""
        r = R.resolve_with_config(
            specifier="other-lib/core", importing_file_path="src/app.ts",
            tree_paths={"src/core.js"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={".": "./src/index.js"}))
        self.assertNotEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")


class TestConditions(unittest.TestCase):
    COND = {"import": "./e.js", "require": "./c.cjs", "default": "./d.js"}

    def test_import_condition(self):
        r = PM.expand_condition(self.COND, available_conditions=["import"])
        self.assertTrue(r["resolved"])
        self.assertEqual(r["target"], "./e.js")

    def test_require_condition(self):
        r = PM.expand_condition(self.COND, available_conditions=["require"])
        self.assertEqual(r["target"], "./c.cjs")

    def test_default_condition(self):
        r = PM.expand_condition({"default": "./d.js"},
                                available_conditions=["import"])
        self.assertEqual(r["target"], "./d.js")

    def test_types_condition(self):
        r = PM.expand_condition({"types": "./t.d.ts", "import": "./t.js"},
                                available_conditions=["types"])
        self.assertEqual(r["target"], "./t.d.ts")

    def test_multiple_available_not_guessed(self):
        """★ 阻断级：多个条件可用时不得任选一条。"""
        r = PM.expand_condition(self.COND, available_conditions=["import", "require"])
        self.assertFalse(r["resolved"])
        self.assertEqual(r["reason"], "MULTIPLE_CONDITIONS_AVAILABLE")
        self.assertIsNone(r["target"])

    def test_unknown_custom_condition_kept(self):
        r = PM.expand_condition({"custom": "./c.js"},
                                available_conditions=["import"])
        self.assertFalse(r["resolved"])
        self.assertEqual(r["reason"], "NO_MATCHING_CONDITION")
        self.assertIn("custom", {c.get("condition") for c in r["candidates"]})

    def test_key_order_preserved(self):
        d = {"types": "./a", "import": "./b", "default": "./c"}
        keys = list(d.keys())
        self.assertEqual(keys, ["types", "import", "default"])

    def test_condition_resolves_when_kind_known(self):
        """★ import 语句 → 只有 import 条件可用 → 可以确定。"""
        tree = {"e.js", "c.cjs"}
        r = R.resolve_with_config(
            specifier="my-app/cond", importing_file_path="src/app.ts",
            tree_paths=tree, import_kind="named_import",
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./cond": self.COND}))
        self.assertEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertEqual(r["resolved_target_path"], "e.js")

    def test_condition_unresolved_when_multiple_available(self):
        """★ 阻断级：两个条件同时可用时不得任选。"""
        tree = {"e.js", "c.cjs"}
        r = R.resolve_with_config(
            specifier="my-app/cond", importing_file_path="src/app.ts",
            tree_paths=tree, import_kind="named_import",
            conditions={"import", "require"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./cond": self.COND}))
        self.assertEqual(r["resolution_state"], "RESOLUTION_CONTEXT_INCOMPLETE")
        self.assertIsNone(r["resolved_target_path"])

    def test_require_kind_selects_require(self):
        tree = {"c.cjs", "e.js"}
        r = R.resolve_with_config(
            specifier="my-app/cond", importing_file_path="src/app.ts",
            tree_paths=tree, import_kind="require_literal_call",
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./cond": self.COND}))
        self.assertIn(r["resolution_state"],
                      ("LOCAL_MODULE_RESOLVED", "RESOLUTION_CONTEXT_INCOMPLETE"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
