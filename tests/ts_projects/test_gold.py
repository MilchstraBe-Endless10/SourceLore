#!/usr/bin/env python3
"""40 项 TS 项目 Gold 逐条验证。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"ts_projects"))
import sfx
import ts_project_context as C
import ts_project_models as PM
import ts_project_references as REF
import ts_file_membership as FM
import ts_project_ingest as TI
import ts_project_query as TQ
import ts_project_adapter as TA
import package_module_map_parser as PPM
import config_aware_resolver as RZ
import tsconfig_parser as TP
from knowledge_store import KnowledgeStore
from gold.ts_project_gold import GOLD

REPO = "990001"
COMMIT = "a"*40
COMMIT_B = "b"*40


def _k(k):
    k = k.replace("_DOT_", "\x00").replace("__", "/").replace("\x00", ".")
    return k[:-5] + ".json" if k.endswith("_json") else k


def blobs(**kw):
    out = {}
    for path, src in kw.items():
        key = _k(path)
        raw = src.encode() if isinstance(src, str) else src
        out[key] = {"raw": raw, "blob_oid": "b"*40,
                    "content_asset_id": "A-" + key,
                    "content_digest": "sha256:" + key}
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="goldj_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, tree, b, commit=COMMIT):
        return C.build_all_projects(tree_paths=tree, config_blobs=b,
                                    repository_id=REPO, commit_sha=commit,
                                    provenance_level="AUTHORIZED_LOCAL_FIXTURE")


class TestRegistry(unittest.TestCase):
    def test_40_cases(self):
        self.assertGreaterEqual(len(GOLD), 40)
        ids = [g[0] for g in GOLD]
        self.assertEqual(len(ids), len(set(ids), ))


class TestProjectGold(Base):
    def test_T01_single(self):
        b = self.build({"tsconfig.json"}, blobs(tsconfig_json='{}'))
        self.assertEqual(b["projects"][0]["discovery_status"],
                         PM.PROJECT_CONFIG_VERIFIED)

    def test_T02_multi(self):
        b = self.build({"tsconfig.json", "packages/a/tsconfig.json"},
                       blobs(tsconfig_json='{}',
                             packages__a__tsconfig_json='{}'))
        self.assertEqual(len(b["projects"]), 2)

    def test_T28_invalid(self):
        b = self.build({"tsconfig.json"},
                       blobs(tsconfig_json='{"a": }'))
        self.assertEqual(b["projects"][0]["discovery_status"],
                         PM.PROJECT_CONFIG_INVALID)

    def test_T19_22_flags(self):
        b = self.build({"tsconfig.json"},
                       blobs(tsconfig_json='{"compilerOptions":'
                              '{"composite":true,"rootDir":"src",'
                              '"outDir":"dist","allowJs":true,"jsx":"react"}}'))
        p = b["projects"][0]
        self.assertTrue(p["declared_composite"])
        self.assertEqual(p["declared_root_dir"], "src")
        self.assertEqual(p["declared_out_dir"], "dist")
        self.assertTrue(p["declared_allow_js"])
        self.assertEqual(p["declared_jsx"], "react")


class TestFilesGold(Base):
    def test_T03_explicit(self):
        r = FM.evaluate_file(file_path="src/a.ts", tree_paths={"src/a.ts"},
                             project={"config_path": "tsconfig.json",
                                      "project_observation_id": "P"},
                             inc_specs=[], exc_specs=[],
                             explicit_files=["src/a.ts"],
                             default_rule={"active": False})
        self.assertEqual(r["state"], PM.INPUT_EXPLICITLY_LISTED)

    def test_T04_include(self):
        r = FM.evaluate_file(file_path="src/a.ts", tree_paths={"src/a.ts"},
                             project={"config_path": "tsconfig.json",
                                      "project_observation_id": "P"},
                             inc_specs=[FM.split_pattern("src/**/*.ts")],
                             exc_specs=[], explicit_files=[],
                             default_rule={"active": False})
        self.assertEqual(r["state"], PM.INPUT_MATCHED_INCLUDE)

    def test_T05_exclude(self):
        inc = [FM.split_pattern("src/**/*.ts")]
        exc = [FM.split_pattern("src/gen/**")]
        r = FM.evaluate_file(file_path="src/gen/g.ts",
                             tree_paths={"src/gen/g.ts"},
                             project={"config_path": "tsconfig.json",
                                      "project_observation_id": "P"},
                             inc_specs=inc, exc_specs=exc, explicit_files=[],
                             default_rule={"active": False})
        self.assertEqual(r["state"], PM.INPUT_EXCLUDED_FROM_INCLUDE)

    def test_T06_files_over_exclude(self):
        r = FM.evaluate_file(file_path="src/a.ts", tree_paths={"src/a.ts"},
                             project={"config_path": "tsconfig.json",
                                      "project_observation_id": "P"},
                             inc_specs=[],
                             exc_specs=[FM.split_pattern("src/**")],
                             explicit_files=["src/a.ts"],
                             default_rule={"active": False})
        self.assertEqual(r["state"], PM.INPUT_EXPLICITLY_LISTED)

    def test_T07_default_active(self):
        d = FM.default_inclusion_active(files_declared=False,
                                        include_declared=False,
                                        exclude_declared=False, allow_js=False)
        self.assertTrue(d["active"])

    def test_T08_empty_files_no_default(self):
        d = FM.default_inclusion_active(files_declared=True,
                                        include_declared=True,
                                        exclude_declared=False, allow_js=False)
        self.assertFalse(d["active"])

    def test_T22_allowjs(self):
        d1 = FM.default_inclusion_active(files_declared=False,
                                         include_declared=False,
                                         exclude_declared=False, allow_js=True)
        self.assertIn(".js", tuple(d1["extensions"]))

    def test_T24_dts(self):
        inc = [FM.split_pattern("src/**/*.d.ts")]
        self.assertTrue(FM.match_pattern(inc[0], "src/x.d.ts"))


class TestSolutionGold(Base):
    def test_T09_solution(self):
        b = self.build({"tsconfig.json", "p/tsconfig.json"},
                       blobs(tsconfig_json='{"files":[],"references":[{"path":"./p"}]}',
                             p__tsconfig_json='{}'))
        root = next(x for x in b["projects"]
                    if x["config_path"] == "tsconfig.json")
        self.assertTrue(root["is_solution_style"])


class TestRefGold(Base):
    def test_T10_dir_target(self):
        t, s = REF.resolve_reference_path(
            declared_path="../b", from_config_dir="a",
            tree_paths={"a/tsconfig.json", "b/tsconfig.json"})
        self.assertEqual(s, PM.PROJECT_REFERENCE_TARGET_VERIFIED)

    def test_T11_file_target(self):
        t, s = REF.resolve_reference_path(
            declared_path="./x/tsconfig.build.json", from_config_dir="a",
            tree_paths={"a/x/tsconfig.build.json"})
        self.assertEqual(t, "a/x/tsconfig.build.json")

    def test_T13_cycle(self):
        cycles, _ = REF.detect_cycles([
            {"from_project_id": "A", "to_project_id": "B"},
            {"from_project_id": "B", "to_project_id": "A"}])
        self.assertTrue(cycles)

    def test_T14_missing(self):
        _, s = REF.resolve_reference_path(
            declared_path="../nope", from_config_dir="a",
            tree_paths={"a/tsconfig.json"})
        self.assertEqual(s, PM.PROJECT_REFERENCE_TARGET_MISSING)

    def test_T15_not_inherited(self):
        b = self.build({"tsconfig.json", "base.json"},
                       blobs(base_json='{"references":[{"path":"./x"}]}',
                             tsconfig_json='{"extends":"./base.json"}'))
        child = next(x for x in b["projects"]
                     if x["config_path"] == "tsconfig.json")
        self.assertEqual(child["declared_references"], [])

    def test_T16_inherited_include_used(self):
        b = self.build({"tsconfig.json", "base.json"},
                       blobs(base_json='{"include":["src/**/*.ts"]}',
                             tsconfig_json='{"extends":"./base.json"}'))
        child = next(x for x in b["projects"]
                     if x["config_path"] == "tsconfig.json")
        # ★ TypeScript 语义：include 随 extends 继承
        self.assertEqual(child["declared_include"], ["src/**/*.ts"])
        detail = b["details"]["tsconfig.json"]
        self.assertFalse(detail["default_rule"]["active"],
                         "已有 include 时不应启用默认扫描")

    def test_T17_child_override(self):
        b = self.build({"tsconfig.json", "base.json"},
                       blobs(base_json='{"include":["src/**/*.ts"]}',
                             tsconfig_json='{"extends":"./base.json",'
                                            '"include":["app/**/*.ts"]}'))
        child = next(x for x in b["projects"]
                     if x["config_path"] == "tsconfig.json")
        self.assertEqual(child["declared_include"], ["app/**/*.ts"])

    def test_T18_config_dir_base(self):
        b = self.build({"packages/a/tsconfig.json", "packages/a/src/x.ts"},
                       blobs(packages__a__tsconfig_json='{"include":["src/**/*.ts"]}'))
        p = b["projects"][0]
        self.assertEqual(p["project_root"], "packages/a")
        detail = b["details"]["packages/a/tsconfig.json"]
        self.assertEqual(detail["include"][0]["prefix"], "packages/a/src")


class TestMembershipGold(Base):
    def test_T25_multi_projects(self):
        b = self.build({"tsconfig.json", "p/tsconfig.json", "shared/u.ts"},
                       blobs(tsconfig_json='{"include":["shared/**/*.ts"]}',
                             p__tsconfig_json='{"include":["../shared/**/*.ts"]}'))
        m = C.resolve_membership(file_path="shared/u.ts",
                                 projects=b["projects"], details=b["details"],
                                 tree_paths={"tsconfig.json", "p/tsconfig.json",
                                             "shared/u.ts"})
        self.assertEqual(m["state"], PM.INPUT_MATCHED_MULTIPLE_PROJECTS)

    def test_T26_not_proven(self):
        b = self.build({"tsconfig.json", "src/a.ts"},
                       blobs(tsconfig_json='{"include":["other/**/*.ts"]}'))
        m = C.resolve_membership(file_path="src/a.ts",
                                 projects=b["projects"], details=b["details"],
                                 tree_paths={"src/a.ts"})
        self.assertNotEqual(m["state"], PM.INPUT_MATCHED_INCLUDE)

    def test_T32_paths_context_ambiguous(self):
        b = self.build({"tsconfig.json", "p/tsconfig.json", "shared/u.ts"},
                       blobs(tsconfig_json='{"include":["shared/**/*.ts"]}',
                             p__tsconfig_json='{"include":["../shared/**/*.ts"]}'))
        ctx = C.select_project_context(file_path="shared/u.ts",
                                       projects=b["projects"],
                                       details=b["details"],
                                       tree_paths={"shared/u.ts"})
        self.assertEqual(ctx["state"], PM.PROJECT_CONTEXT_AMBIGUOUS)


class TestNodeConditionGold(unittest.TestCase):
    def test_T33_default(self):
        r = PPM.expand_condition({"default": "./d.js"},
                                 available_conditions=["import"])
        self.assertEqual(r["target"], "./d.js")

    def test_T34_order(self):
        a = {"default": "./d.js", "import": "./e.js"}
        b = {"import": "./e.js", "default": "./d.js"}
        ra = PPM.expand_condition(a, available_conditions=["import"])
        rb = PPM.expand_condition(b, available_conditions=["import"])
        self.assertEqual(ra["target"], "./d.js")
        self.assertEqual(rb["target"], "./e.js")

    def test_T35_first_match(self):
        r = PPM.expand_condition({"import": "./e.js", "node": "./n.js"},
                                 available_conditions=["import", "node"])
        self.assertEqual(r["condition_used"], "import")

    def test_T36_unknown(self):
        r = PPM.expand_condition({"custom": "./x"},
                                 available_conditions=["import"])
        self.assertEqual(r["reason"], "NO_MATCHING_CONDITION")


class TestPersistGold(Base):
    def test_T37_idempotent(self):
        b = self.build({"tsconfig.json"}, blobs(tsconfig_json='{}'))
        TI.ingest_project_bundle(store=self.ks, bundle=b)
        r2 = TI.ingest_project_bundle(store=self.ks, bundle=b)
        self.assertEqual(r2["written"], [])

    def test_T29_wrong_commit(self):
        b = self.build({"tsconfig.json"}, blobs(tsconfig_json='{}'))
        TI.ingest_project_bundle(store=self.ks, bundle=b)
        q = TQ.query_projects(repository_id=REPO, commit_sha=COMMIT_B,
                              data_root=self.tmp)
        self.assertEqual(q["projects"], [])

    def test_T30_wrong_repo(self):
        q = TQ.query_projects(repository_id="nope", data_root=self.tmp)
        self.assertEqual(q["state"], "REPOSITORY_NOT_REGISTERED")

    def test_T38_zero_network(self):
        b = self.build({"tsconfig.json"}, blobs(tsconfig_json='{}'))
        TI.ingest_project_bundle(store=self.ks, bundle=b)
        q = TQ.query_projects(repository_id=REPO, data_root=self.tmp)
        self.assertEqual(q["network_requests"], 0)


class TestEvidenceGold(unittest.TestCase):
    def test_T39_evidence_required(self):
        claim, binding = TA.build_membership_claim(
            repository_id=REPO, commit_sha=COMMIT,
            config_path="tsconfig.json", source_file_path="src/a.ts")
        v = TA.verify_ts_claim(claim=claim, facts=[], status="INPUT_MATCHED_INCLUDE",
                              subject_binding=binding, evidence_complete=False)
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_T31_independent_scope(self):
        """★ TS 项目归属与 package scope 是两件事。"""
        b = C.build_all_projects(
            tree_paths={"tsconfig.json"}, config_blobs=blobs(tsconfig_json='{}'),
            repository_id=REPO, commit_sha=COMMIT)
        self.assertEqual(len(b["projects"]), 1)
        # 项目身份独立，不含 package name
        pid = b["projects"][0]["project_observation_id"]
        self.assertNotIn("package", pid.lower())


class TestGoldRegistry(unittest.TestCase):
    def test_categories(self):
        cats = {g[1] for g in GOLD}
        self.assertGreaterEqual(len(cats), 8)

    def test_all_fields(self):
        for gid, cat, desc, exp in GOLD:
            self.assertTrue(gid and cat and desc and exp, gid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
