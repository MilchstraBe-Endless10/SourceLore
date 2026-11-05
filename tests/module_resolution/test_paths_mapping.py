#!/usr/bin/env python3
"""tsconfig paths 匹配规则与优先级。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"module_resolution"))
import sfx
import tsconfig_effective_config as EC
import tsconfig_parser as TP
import config_aware_resolver as R


def surf(paths, base_url=".", config_dir=""):
    comp = {"paths": paths}
    if base_url is not None:
        comp["baseUrl"] = base_url
    return TP.extract_config_surface({"compilerOptions": comp},
                                     config_dir=config_dir)


def tc(paths, base_url=".", config_dir="", status=None):
    s = surf(paths, base_url, config_dir)
    return {
        "effective_config_status": status or "EFFECTIVE_CONFIG_RESOLVED",
        "config_observation_id": "CFG-X",
        "declared_paths": s["paths"],
        "declared_base_url": s["base_url"],
        "_base_dir": TP.resolve_base_dir(config_dir=config_dir,
                                         base_url=s["base_url"]),
        "config_path": (config_dir + "/tsconfig.json").lstrip("/"),
    }


class TestMatching(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(EC.match_pattern("@config", "@config"), "")
        self.assertIsNone(EC.match_pattern("@config", "@other"))

    def test_wildcard(self):
        self.assertEqual(EC.match_pattern("@/*", "@/utils"), "utils")

    def test_wildcard_suffix(self):
        self.assertEqual(EC.match_pattern("@/*.ts", "@/a.ts"), "a")

    def test_star_alone(self):
        self.assertEqual(EC.match_pattern("*", "anything"), "anything")

    def test_prefix_longer_wins(self):
        rules = [{"pattern": "*", "targets": ["a"]},
                 {"pattern": "@/*", "targets": ["b"]},
                 {"pattern": "@lib/*", "targets": ["c"]}]
        hits = EC.select_rules(rules, "@lib/x")
        self.assertEqual(hits[0]["pattern"], "@lib/*")

    def test_exact_beats_wildcard(self):
        rules = [{"pattern": "@/*", "targets": ["b"]},
                 {"pattern": "@config", "targets": ["c"]}]
        hits = EC.select_rules(rules, "@config")
        self.assertEqual(hits[0]["pattern"], "@config")

    def test_star_last(self):
        rules = [{"pattern": "*", "targets": ["a"]},
                 {"pattern": "@/*", "targets": ["b"]}]
        hits = EC.select_rules(rules, "@/x")
        self.assertEqual([h["pattern"] for h in hits], ["@/*", "*"])

    def test_no_match(self):
        rules = [{"pattern": "@/*", "targets": ["b"]}]
        self.assertEqual(EC.select_rules(rules, "other"), [])


class TestTargets(unittest.TestCase):
    def test_multi_target_order_preserved(self):
        rule = {"pattern": "@lib/*", "targets": ["./generated/*", "./src/lib/*"],
                "capture": "x"}
        exp = EC.expand_targets(rule, base_dir="")
        self.assertEqual([e["path"] for e in exp], ["generated/x", "src/lib/x"])

    def test_path_traversal_rejected(self):
        rule = {"pattern": "@/*", "targets": ["../../etc/*"], "capture": "x"}
        exp = EC.expand_targets(rule, base_dir="src")
        self.assertEqual(exp[0]["path"], None)
        self.assertEqual(exp[0]["rejected"], "PATH_ESCAPES_REPOSITORY")

    def test_absolute_rejected(self):
        rule = {"pattern": "@/*", "targets": ["/etc/*"], "capture": "x"}
        exp = EC.expand_targets(rule, base_dir="")
        self.assertEqual(exp[0]["path"], None)

    def test_base_url_none_uses_config_dir(self):
        self.assertEqual(TP.resolve_base_dir(config_dir="packages/a",
                                             base_url=None), "packages/a")

    def test_base_url_relative_to_config_dir(self):
        self.assertEqual(TP.resolve_base_dir(config_dir="packages/a",
                                             base_url=".."), "packages")

    def test_base_url_traversal_rejected(self):
        self.assertIsNone(TP.resolve_base_dir(config_dir="", base_url=".."))


class TestResolve(unittest.TestCase):
    TREE = {"src/utils.ts", "src/components/Button.tsx",
            "generated/y.ts", "src/lib/x.ts", "src/index.ts"}

    def _r(self, spec, pathses, tree=None, **kw):
        return R.resolve_with_config(
            specifier=spec, importing_file_path="src/app.ts",
            tree_paths=tree or self.TREE,
            tsconfig_observation=tc(pathses, **kw))

    def test_simple_alias(self):
        r = self._r("@/utils", {"@/*": ["./src/*"]})
        self.assertEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertEqual(r["resolved_target_path"], "src/utils.ts")

    def test_multi_target_fallback_first_missing(self):
        """★ 第一个目标不存在 → 用第二个。"""
        r = self._r("@lib/x", {"@lib/*": ["./generated/*", "./src/lib/*"]},
                    tree={"src/lib/x.ts"})
        self.assertEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")
        self.assertEqual(r["resolved_target_path"], "src/lib/x.ts")
        self.assertEqual(r["candidate_paths"], ["generated/x", "src/lib/x"])

    def test_multi_target_first_wins(self):
        r = self._r("@lib/x", {"@lib/*": ["./generated/*", "./src/lib/*"]},
                    tree={"generated/x.ts", "src/lib/x.ts"})
        self.assertEqual(r["resolved_target_path"], "generated/x.ts")

    def test_no_candidate(self):
        r = self._r("@/nope", {"@/*": ["./src/*"]})
        self.assertEqual(r["resolution_state"], "CONFIG_MAPPING_CANDIDATE")
        self.assertEqual(r["unresolved_reason"], "TARGET_NOT_IN_TREE")

    def test_no_matching_rule(self):
        r = self._r("react", {"@/*": ["./src/*"]})
        self.assertEqual(r["resolution_state"], "CONFIG_MAPPING_CANDIDATE")
        self.assertEqual(r["unresolved_reason"], "NO_MATCHING_PATH_RULE")

    def test_ambiguous(self):
        r = self._r("@/dup", {"@/*": ["./src/*"]},
                    tree={"src/dup.ts", "src/dup.tsx"})
        self.assertEqual(r["resolution_state"], "AMBIGUOUS_CANDIDATES")

    def test_incomplete_tree(self):
        r = R.resolve_with_config(
            specifier="@/utils", importing_file_path="src/app.ts",
            tree_paths=self.TREE, tsconfig_observation=tc({"@/*": ["./src/*"]}),
            source_completeness="PARTIAL")
        self.assertEqual(r["resolution_state"], "INSUFFICIENT_TREE_COVERAGE")

    def test_config_not_captured(self):
        r = R.resolve_with_config(
            specifier="@/utils", importing_file_path="src/app.ts",
            tree_paths=self.TREE,
            tsconfig_observation=tc({"@/*": ["./src/*"]},
                                    status="CONFIG_CONTENT_NOT_CAPTURED"))
        self.assertEqual(r["resolution_state"], "CONFIG_NOT_CAPTURED")

    def test_config_dir_scoped(self):
        """★ 子目录 tsconfig：映射基准是该目录，不是仓库根。"""
        r = R.resolve_with_config(
            specifier="@/utils", importing_file_path="packages/a/src/app.ts",
            tree_paths={"packages/a/src/utils.ts"},
            tsconfig_observation=tc({"@/*": ["./src/*"]},
                                    base_url=None, config_dir="packages/a"))
        self.assertEqual(r["resolved_target_path"], "packages/a/src/utils.ts")

    def test_path_traversal_target(self):
        r = self._r("@/x", {"@/*": ["../../etc/*"]})
        self.assertEqual(r["resolution_state"], "PATH_ESCAPES_REPOSITORY")

    def test_no_runtime_state_ever(self):
        """★ 阻断级：不得出现 RUNTIME_* 成功态。"""
        states = set()
        for spec in ("@/utils", "react", "./x", "#h"):
            states.add(R.resolve_with_config(
                specifier=spec, importing_file_path="src/app.ts",
                tree_paths=self.TREE,
                tsconfig_observation=tc({"@/*": ["./src/*"]}))["resolution_state"])
        for s in states:
            self.assertNotIn("RUNTIME", s.upper())


if __name__ == "__main__":
    unittest.main(verbosity=2)
