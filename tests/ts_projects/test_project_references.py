#!/usr/bin/env python3
"""Project references 解析与图。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"ts_projects"))
import sfx
import ts_project_references as REF
import ts_project_models as PM

REPO = "990001"
COMMIT = "a"*40


def proj(config_path, refs=None):
    return {
        "repository_id": REPO, "commit_sha": COMMIT,
        "project_observation_id": "PID-" + config_path,
        "config_path": config_path,
        "config_blob_oid": "b"*40,
        "config_content_asset_id": "A-" + config_path,
        "declared_references": [{"path": r} for r in (refs or [])],
    }


class TestResolvePath(unittest.TestCase):
    def test_directory_target(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json"}
        t, s = REF.resolve_reference_path(
            declared_path="../b", from_config_dir="packages/a",
            tree_paths=tree)
        self.assertEqual(t, "packages/b/tsconfig.json")
        self.assertEqual(s, PM.PROJECT_REFERENCE_TARGET_VERIFIED)

    def test_file_target(self):
        tree = {"packages/a/tsconfig.json",
                "packages/core/tsconfig.build.json"}
        t, s = REF.resolve_reference_path(
            declared_path="./core/tsconfig.build.json",
            from_config_dir="packages/a", tree_paths=tree)
        self.assertEqual(t, "packages/a/core/tsconfig.build.json")
        self.assertEqual(s, PM.PROJECT_REFERENCE_TARGET_MISSING)

    def test_missing_target(self):
        tree = {"packages/a/tsconfig.json"}
        t, s = REF.resolve_reference_path(
            declared_path="../nope", from_config_dir="packages/a",
            tree_paths=tree)
        self.assertEqual(s, PM.PROJECT_REFERENCE_TARGET_MISSING)

    def test_outside_repository(self):
        tree = {"tsconfig.json"}
        t, s = REF.resolve_reference_path(
            declared_path="../../../etc", from_config_dir="a/b",
            tree_paths=tree)
        self.assertEqual(s, PM.PROJECT_REFERENCE_OUTSIDE_REPOSITORY)
        self.assertIsNone(t)


class TestBuildReferences(unittest.TestCase):
    def test_reference_verified(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json"}
        a = proj("packages/a/tsconfig.json", ["../b"])
        b = proj("packages/b/tsconfig.json")
        refs = REF.build_references_for_project(
            project=a, tree_paths=tree,
            config_lookup=lambda p: {b["config_path"]: b}.get(p),
            captured_configs={"packages/b/tsconfig.json"})
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["status"],
                         PM.PROJECT_REFERENCE_TARGET_VERIFIED)
        self.assertEqual(refs[0]["to_project_id"],
                         b["project_observation_id"])

    def test_reference_target_not_captured(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json"}
        a = proj("packages/a/tsconfig.json", ["../b"])
        refs = REF.build_references_for_project(
            project=a, tree_paths=tree, config_lookup=lambda p: None,
            captured_configs=set())
        self.assertEqual(refs[0]["status"],
                         PM.PROJECT_REFERENCE_TARGET_NOT_CAPTURED)
        self.assertIsNone(refs[0]["to_project_id"])

    def test_multiple_references(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json",
                "packages/c/tsconfig.json"}
        a = proj("packages/a/tsconfig.json", ["../b", "../c"])
        refs = REF.build_references_for_project(
            project=a, tree_paths=tree, config_lookup=lambda p: None,
            captured_configs=set())
        self.assertEqual(len(refs), 2)

    def test_duplicate_references_both_present(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json"}
        a = proj("packages/a/tsconfig.json", ["../b", "../b"])
        refs = REF.build_references_for_project(
            project=a, tree_paths=tree, config_lookup=lambda p: None,
            captured_configs=set())
        self.assertEqual(len(refs), 2, "重复引用应各留一条")

    def test_reference_id_includes_target(self):
        tree = {"packages/a/tsconfig.json", "packages/b/tsconfig.json",
                "packages/c/tsconfig.json"}
        a = proj("packages/a/tsconfig.json", ["../b"])
        a2 = proj("packages/a/tsconfig.json", ["../c"])
        r1 = REF.build_references_for_project(
            project=a, tree_paths=tree, config_lookup=lambda p: None)[0]
        r2 = REF.build_references_for_project(
            project=a2, tree_paths=tree, config_lookup=lambda p: None)[0]
        self.assertNotEqual(r1["reference_id"], r2["reference_id"])


class TestCycles(unittest.TestCase):
    def test_cycle_detected(self):
        refs = [
            {"from_project_id": "A", "to_project_id": "B"},
            {"from_project_id": "B", "to_project_id": "A"},
        ]
        cycles, deepest = REF.detect_cycles(refs)
        self.assertTrue(cycles)
        self.assertEqual(len(cycles[0]), 3)

    def test_self_cycle(self):
        refs = [{"from_project_id": "A", "to_project_id": "A"}]
        cycles, _ = REF.detect_cycles(refs)
        self.assertTrue(cycles)

    def test_no_cycle(self):
        refs = [{"from_project_id": "A", "to_project_id": "B"},
                {"from_project_id": "B", "to_project_id": "C"}]
        cycles, deepest = REF.detect_cycles(refs)
        self.assertEqual(cycles, [])
        self.assertGreaterEqual(deepest, 2)

    def test_depth_exceeded(self):
        refs = [{"from_project_id": f"A{i}", "to_project_id": f"A{i+1}"}
                for i in range(15)]
        cycles, deepest = REF.detect_cycles(refs, max_depth=5)
        self.assertLessEqual(deepest, 6)


class TestGraph(unittest.TestCase):
    def test_graph_nodes_and_edges(self):
        projects = [proj("a/tsconfig.json"), proj("b/tsconfig.json")]
        refs = [{"from_project_id": "PID-a/tsconfig.json",
                 "to_project_id": "PID-b/tsconfig.json",
                 "to_config_path": "b/tsconfig.json",
                 "status": PM.PROJECT_REFERENCE_TARGET_VERIFIED,
                 "from_config_path": "a/tsconfig.json",
                 "declared_path": "../b"}]
        g = REF.build_project_graph(projects=projects, references=refs)
        self.assertEqual(len(g["nodes"]), 2)
        self.assertEqual(len(g["edges"]), 1)

    def test_graph_has_limitations(self):
        g = REF.build_project_graph(projects=[], references=[])
        self.assertTrue(g["limitations"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
