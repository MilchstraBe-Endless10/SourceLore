#!/usr/bin/env python3
"""files / include / exclude 选择语义。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"ts_projects"))
import sfx
import ts_file_membership as FM
import ts_project_models as PM

REPO = "990001"
COMMIT = "a"*40


def proj(config_path="tsconfig.json"):
    return {"repository_id": REPO, "commit_sha": COMMIT,
            "project_observation_id": "PID-" + config_path,
            "config_path": config_path}


def evaluate(files=None, include=None, exclude=None, target="src/a.ts",
             cdir="", allow_js=False, tree=None):
    files_declared = files is not None
    include_declared = include is not None
    exclude_declared = exclude is not None
    inc, exc, _ = FM.prepare_rules(include=include or [], exclude=exclude or [],
                                  config_dir=cdir)
    expl, _ = FM.declared_files(files=files or [], config_dir=cdir)
    default = FM.default_inclusion_active(
        files_declared=files_declared, include_declared=include_declared,
        exclude_declared=exclude_declared, allow_js=allow_js)
    return FM.evaluate_file(
        file_path=target, tree_paths=tree or {target}, project=proj(),
        inc_specs=inc, exc_specs=exc, explicit_files=expl,
        default_rule=default)


class TestPatterns(unittest.TestCase):
    def test_recursive_ext(self):
        spec = FM.split_pattern("src/**/*.ts")
        self.assertEqual(spec["form"], "RECURSIVE_EXT")
        self.assertEqual(spec["ext"], ".ts")
        self.assertTrue(FM.match_pattern(spec, "src/sub/deep/a.ts"))

    def test_one_level(self):
        spec = FM.split_pattern("src/*.tsx")
        self.assertTrue(FM.match_pattern(spec, "src/a.tsx"))
        self.assertFalse(FM.match_pattern(spec, "src/sub/a.tsx"))

    def test_exact(self):
        spec = FM.split_pattern("src/main.ts")
        self.assertTrue(FM.match_pattern(spec, "src/main.ts"))
        self.assertFalse(FM.match_pattern(spec, "src/other.ts"))

    def test_recursive_any(self):
        spec = FM.split_pattern("src/**")
        self.assertTrue(FM.match_pattern(spec, "src/a.ts"))
        self.assertTrue(FM.match_pattern(spec, "src/x/y/z.ts"))

    def test_star_top_level(self):
        spec = FM.split_pattern("*.d.ts")
        self.assertTrue(FM.match_pattern(spec, "types.d.ts"))
        self.assertFalse(FM.match_pattern(spec, "sub/types.d.ts"))

    def test_unsupported_braces(self):
        with self.assertRaises(FM.UnsupportedPattern):
            FM.split_pattern("src/{a,b}/*.ts")

    def test_unsupported_negation(self):
        with self.assertRaises(FM.UnsupportedPattern):
            FM.split_pattern("!src/**")

    def test_unsupported_absolute(self):
        with self.assertRaises(FM.UnsupportedPattern):
            FM.split_pattern("/abs/**/*.ts")

    def test_unsupported_double_recursive(self):
        with self.assertRaises(FM.UnsupportedPattern):
            FM.split_pattern("a/**/b/**/*.ts")


class TestSelection(unittest.TestCase):
    def test_explicit_files(self):
        r = evaluate(files=["src/a.ts"], target="src/a.ts")
        self.assertEqual(r["state"], PM.INPUT_EXPLICITLY_LISTED)
        self.assertEqual(r["matched_field"], "files")

    def test_files_ignores_exclude(self):
        """★ files 显式列出不受 exclude 影响。"""
        r = evaluate(files=["src/a.ts"], exclude=["src/**"], target="src/a.ts")
        self.assertEqual(r["state"], PM.INPUT_EXPLICITLY_LISTED)

    def test_include_match(self):
        r = evaluate(include=["src/**/*.ts"], target="src/a.ts")
        self.assertEqual(r["state"], PM.INPUT_MATCHED_INCLUDE)

    def test_exclude_from_include(self):
        r = evaluate(include=["src/**/*.ts"], exclude=["src/generated/**"],
                     target="src/generated/g.ts")
        self.assertEqual(r["state"], PM.INPUT_EXCLUDED_FROM_INCLUDE)
        self.assertEqual(r["excluded_by"], "src/generated/**")

    def test_excluded_is_not_absolute_ban(self):
        """★ INPUT_EXCLUDED_FROM_INCLUDE ≠ 不可能进入 Program。"""
        r = evaluate(include=["src/**/*.ts"], exclude=["src/**"],
                     target="src/a.ts")
        self.assertEqual(r["state"], PM.INPUT_EXCLUDED_FROM_INCLUDE)
        # 状态名本身不表示绝对排除
        self.assertNotIn("NOT_IN_PROGRAM", r["state"])
        self.assertNotIn("NEVER", r["state"])

    def test_not_selected_ts_is_possible_via_import(self):
        r = evaluate(include=["src/**/*.ts"], target="other/x.ts")
        self.assertEqual(r["state"], PM.INPUT_POSSIBLE_VIA_IMPORT)

    def test_not_selected_non_ts(self):
        r = evaluate(include=["src/**/*.ts"], target="other/x.md")
        self.assertEqual(r["state"], PM.INPUT_NOT_PROVEN)


class TestDefaults(unittest.TestCase):
    def test_no_declarations_uses_default(self):
        d = FM.default_inclusion_active(files_declared=False,
                                        include_declared=False,
                                        exclude_declared=False, allow_js=False)
        self.assertTrue(d["active"])

    def test_empty_files_array_disables_default(self):
        """★ files:[] 不触发默认扫描。"""
        d = FM.default_inclusion_active(files_declared=True,
                                        include_declared=False,
                                        exclude_declared=False, allow_js=False)
        self.assertFalse(d["active"])
        self.assertEqual(d["reason"], "FILES_DECLARED")

    def test_empty_include_disables_default(self):
        d = FM.default_inclusion_active(files_declared=False,
                                        include_declared=True,
                                        exclude_declared=False, allow_js=False)
        self.assertFalse(d["active"])

    def test_default_excludes_js_when_no_allowjs(self):
        d = FM.default_inclusion_active(files_declared=False,
                                        include_declared=False,
                                        exclude_declared=False, allow_js=False)
        self.assertNotIn(".js", tuple(d["extensions"]))
        self.assertIn(".ts", tuple(d["extensions"]))

    def test_default_includes_js_when_allowjs(self):
        d = FM.default_inclusion_active(files_declared=False,
                                        include_declared=False,
                                        exclude_declared=False, allow_js=True)
        self.assertIn(".js", tuple(d["extensions"]))

    def test_default_match(self):
        r = evaluate(target="src/a.ts")
        self.assertEqual(r["state"], PM.INPUT_MATCHED_INCLUDE)
        self.assertEqual(r["matched_field"], "default_include")

    def test_empty_files_no_selection(self):
        """★ files=[] → 无输入文件，但也不等于没有依赖关系。"""
        r = evaluate(files=[], target="src/a.ts")
        self.assertEqual(r["state"], PM.INPUT_POSSIBLE_VIA_IMPORT)

    def test_solution_style_files_empty_no_include(self):
        r = evaluate(files=[], include=None, target="src/a.ts")
        self.assertNotEqual(r["state"], PM.INPUT_MATCHED_INCLUDE)


class TestEdge(unittest.TestCase):
    def test_path_traversal_pattern(self):
        _, _, probs = FM.prepare_rules(include=["../../etc/*.ts"], exclude=[],
                                       config_dir="src")
        self.assertTrue(any(p["reason"] == "PATH_ESCAPES_REPOSITORY"
                            for p in probs))

    def test_config_dir_relative(self):
        r = evaluate(include=["src/**/*.ts"], target="packages/a/src/x.ts",
                     cdir="packages/a")
        self.assertEqual(r["state"], PM.INPUT_MATCHED_INCLUDE)

    def test_case_sensitive_dir(self):
        """★ 目录大小写不同 → 不匹配（TypeScript 大小写敏感）。"""
        r = evaluate(include=["src/**/*.ts"], target="SRC/a.ts")
        self.assertEqual(r["state"], PM.INPUT_POSSIBLE_VIA_IMPORT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
