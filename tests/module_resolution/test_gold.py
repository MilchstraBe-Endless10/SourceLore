#!/usr/bin/env python3
"""45 项 Gold 逐条验证。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"module_resolution"))
import sfx
import tsconfig_jsonc as JC
import tsconfig_effective_config as EC
import tsconfig_parser as TP
import package_module_map_parser as PM
import config_aware_resolver as R
import module_config_models as CM
import module_relation_adapter as MA
import module_relation_ingest as MI
import module_relation_query as MQ
from knowledge_store import KnowledgeStore
from gold.module_gold import GOLD

REPO = "990001"
COMMIT = "a"*40
COMMIT_B = "b"*40


def tc(paths, base_url=".", config_dir="", status=None):
    comp = {"paths": paths}
    if base_url is not None:
        comp["baseUrl"] = base_url
    s = TP.extract_config_surface({"compilerOptions": comp},
                                  config_dir=config_dir)
    return {"effective_config_status": status or "EFFECTIVE_CONFIG_RESOLVED",
            "config_observation_id": "C1" + config_dir,
            "declared_paths": s["paths"],
            "declared_base_url": s["base_url"],
            "_base_dir": TP.resolve_base_dir(config_dir=config_dir,
                                             base_url=s["base_url"]),
            "_config_dir": config_dir,
            "config_path": (config_dir + "/tsconfig.json").lstrip("/")}


def pkg(**kw):
    b = {"effective_config_status": "EFFECTIVE_CONFIG_RESOLVED",
         "config_observation_id": "P1", "_config_dir": "",
         "config_path": "package.json"}
    b.update(kw)
    return b


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="goldi_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestGoldCount(unittest.TestCase):
    def test_45_cases(self):
        self.assertGreaterEqual(len(GOLD), 45)
        ids = [g[0] for g in GOLD]
        self.assertEqual(len(ids), len(set(ids)))


class TestAliasGold(unittest.TestCase):
    TREE = {"src/config.ts", "src/utils.ts", "src/lib/x.ts", "generated/y.ts"}

    def test_G01_exact(self):
        r = R.resolve_with_config(specifier="@config",
                                  importing_file_path="src/app.ts",
                                  tree_paths=self.TREE,
                                  tsconfig_observation=tc({"@config":
                                                           ["./src/config.ts"]}))
        self.assertEqual(r["resolved_target_path"], "src/config.ts")

    def test_G02_wildcard(self):
        r = R.resolve_with_config(specifier="@/utils",
                                  importing_file_path="src/app.ts",
                                  tree_paths=self.TREE,
                                  tsconfig_observation=tc({"@/*": ["./src/*"]}))
        self.assertEqual(r["resolved_target_path"], "src/utils.ts")

    def test_G03_priority(self):
        r = R.resolve_with_config(
            specifier="@lib/x", importing_file_path="src/app.ts",
            tree_paths=self.TREE,
            tsconfig_observation=tc({"@/*": ["./src/*"],
                                     "@lib/*": ["./src/lib/*"]}))
        self.assertEqual(r["matched_config_rule"], "@lib/*")
        self.assertEqual(r["resolved_target_path"], "src/lib/x.ts")

    def test_G04_fallback_order(self):
        r = R.resolve_with_config(
            specifier="@lib/x", importing_file_path="src/app.ts",
            tree_paths={"src/lib/x.ts"},
            tsconfig_observation=tc({"@lib/*": ["./generated/*",
                                               "./src/lib/*"]}))
        self.assertEqual(r["resolved_target_path"], "src/lib/x.ts")


class TestBaseUrlGold(unittest.TestCase):
    def test_G05_no_baseurl_uses_config_dir(self):
        r = R.resolve_with_config(
            specifier="@/utils", importing_file_path="pkgs/a/src/app.ts",
            tree_paths={"pkgs/a/src/utils.ts"},
            tsconfig_observation=tc({"@/*": ["./src/*"]}, base_url=None,
                                    config_dir="pkgs/a"))
        self.assertEqual(r["resolved_target_path"], "pkgs/a/src/utils.ts")

    def test_G06_with_baseurl(self):
        r = R.resolve_with_config(
            specifier="@/utils", importing_file_path="src/app.ts",
            tree_paths={"src/utils.ts"},
            tsconfig_observation=tc({"@/*": ["src/*"]}, base_url="."))
        self.assertEqual(r["resolved_target_path"], "src/utils.ts")


class TestJsoncGold(unittest.TestCase):
    def test_G07_comments(self):
        d = JC.parse_jsonc('{\n// x\n/* y */\n"a": 1\n}')
        self.assertEqual(d["a"], 1)

    def test_G08_trailing(self):
        self.assertEqual(JC.parse_jsonc('{"a": [1,],}'), {"a": [1]})

    def test_G09_slashes_in_string(self):
        d = JC.parse_jsonc('{"u": "https://x//y"}')
        self.assertEqual(d["u"], "https://x//y")

    def test_G10_bad_jsonc(self):
        with self.assertRaises(JC.JsoncError):
            JC.parse_jsonc('{"a": }')


class TestExtendsGold(unittest.TestCase):
    def _read(self, files):
        # ★ resolve_extends_chain 期望的形态是 {ok, data} 或 None
        def r(path):
            v = files.get(path, "MISSING")
            if v == "MISSING":
                return None
            return {"ok": True, "data": v}
        return r

    def test_G11_inherit(self):
        files = {"tsconfig.json": {"extends": "./base.json",
                                   "compilerOptions": {}},
                 "base.json": {"compilerOptions": {"paths":
                                                   {"@/*": ["./src/*"]}}}}
        res = EC.resolve_extends_chain(config_path="tsconfig.json",
                                       read_config=self._read(files))
        self.assertTrue(res["ok"])
        merged = EC.merge_chain(res["chain"])
        self.assertEqual(merged["paths"][0]["pattern"], "@/*")

    def test_G12_cycle(self):
        files = {"tsconfig.json": {"extends": "./a.json"},
                 "a.json": {"extends": "./tsconfig.json"}}
        res = EC.resolve_extends_chain(config_path="tsconfig.json",
                                       read_config=self._read(files))
        self.assertEqual(res["error"], CM.CONFIG_INHERITANCE_CYCLE)

    def test_G13_missing(self):
        files = {"tsconfig.json": {"extends": "./nope.json"}}
        res = EC.resolve_extends_chain(config_path="tsconfig.json",
                                       read_config=self._read(files))
        self.assertEqual(res["error"], CM.CONFIG_CONTENT_NOT_CAPTURED)


class TestMonorepoGold(unittest.TestCase):
    TREE = {"a/src/utils.ts", "b/src/utils.ts"}

    def test_G14_isolated(self):
        a = R.resolve_with_config(specifier="@/utils",
                                  importing_file_path="a/src/app.ts",
                                  tree_paths=self.TREE,
                                  tsconfig_observation=tc({"@/*": ["./src/*"]},
                                                          config_dir="a"))
        b = R.resolve_with_config(specifier="@/utils",
                                  importing_file_path="b/src/app.ts",
                                  tree_paths=self.TREE,
                                  tsconfig_observation=tc({"@/*": ["./src/*"]},
                                                          config_dir="b"))
        self.assertEqual(a["resolved_target_path"], "a/src/utils.ts")
        self.assertEqual(b["resolved_target_path"], "b/src/utils.ts")

    def test_G15_ambiguous_scope(self):
        r = R.resolve_with_config(specifier="@/utils",
                                  importing_file_path="a/src/app.ts",
                                  tree_paths=self.TREE)
        self.assertEqual(r["resolution_state"], "CONFIG_NOT_CAPTURED")


class TestPackageGold(unittest.TestCase):
    def test_G16_imports(self):
        r = R.resolve_with_config(
            specifier="#internal/x", importing_file_path="src/app.ts",
            tree_paths={"src/internal/x.js"},
            package_observation=pkg(declared_imports={
                "#internal/*": "./src/internal/*.js"}))
        self.assertEqual(r["resolved_target_path"], "src/internal/x.js")

    def test_G17_self_ref_root(self):
        r = R.resolve_with_config(
            specifier="my-app", importing_file_path="src/app.ts",
            tree_paths={"src/index.js"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={".": "./src/index.js"}))
        self.assertEqual(r["resolved_target_path"], "src/index.js")

    def test_G18_subpath(self):
        r = R.resolve_with_config(
            specifier="my-app/core", importing_file_path="src/app.ts",
            tree_paths={"src/core.js"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./core": "./src/core.js"}))
        self.assertEqual(r["resolved_target_path"], "src/core.js")

    def test_G19_blocked(self):
        r = R.resolve_with_config(
            specifier="my-app/secret", importing_file_path="src/app.ts",
            tree_paths={"src/secret.js"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./secret": None}))
        self.assertEqual(r["unresolved_reason"], "EXPORT_EXPLICITLY_BLOCKED")

    def test_G20_wildcard_export(self):
        r = R.resolve_with_config(
            specifier="my-app/feat/a", importing_file_path="src/app.ts",
            tree_paths={"src/feat/a.js"},
            package_observation=pkg(declared_name="my-app",
                                    declared_exports={"./feat/*":
                                                      "./src/feat/*.js"}))
        self.assertEqual(r["resolved_target_path"], "src/feat/a.js")


class TestConditionGold(unittest.TestCase):
    C = {"import": "./e.js", "require": "./c.cjs", "default": "./d.js"}

    def test_G21_import(self):
        r = PM.expand_condition(self.C, available_conditions=["import"])
        self.assertEqual(r["target"], "./e.js")

    def test_G22_require(self):
        r = PM.expand_condition(self.C, available_conditions=["require"])
        self.assertEqual(r["target"], "./c.cjs")

    def test_G23_default(self):
        r = PM.expand_condition({"default": "./d.js"},
                                available_conditions=["import"])
        self.assertEqual(r["target"], "./d.js")

    def test_G24_types(self):
        r = PM.expand_condition({"types": "./t.d.ts"},
                                available_conditions=["types"])
        self.assertEqual(r["target"], "./t.d.ts")

    def test_G25_unknown(self):
        r = PM.expand_condition({"custom": "./x.js"},
                                available_conditions=["import"])
        self.assertEqual(r["reason"], "NO_MATCHING_CONDITION")


class TestImportGold(Base):
    def test_G26_type_only(self):
        import js_ts_parser as JP
        o = JP.parse_source(b'import type { T } from "./t";\n',
                            repository_id=REPO, commit_sha=COMMIT,
                            file_path="a.ts", git_blob_oid="b"*40,
                            content_asset_id="X", content_sha256="sha256:0")
        self.assertTrue(o["observed_imports"][0]["is_type_only"])

    def test_G27_dynamic(self):
        r = R.resolve_with_config(specifier=None,
                                  importing_file_path="src/app.ts",
                                  tree_paths={"a.js"})
        self.assertEqual(r["resolution_state"], "DYNAMIC_SPECIFIER")

    def test_G28_bare_external(self):
        r = R.resolve_with_config(specifier="react",
                                  importing_file_path="src/app.ts",
                                  tree_paths={"src/app.ts"},
                                  tsconfig_observation=tc({"@/*": ["./src/*"]}))
        self.assertEqual(r["resolution_state"], "CONFIG_MAPPING_CANDIDATE")

    def test_G29_scoped(self):
        r = R.resolve_with_config(specifier="@scope/pkg",
                                  importing_file_path="src/app.ts",
                                  tree_paths={"src/pkg.ts"},
                                  tsconfig_observation=tc({"@/*": ["./src/*"]}))
        self.assertNotEqual(r["resolution_state"], "LOCAL_MODULE_RESOLVED")


class TestEvidenceGold(Base):
    def test_G30_incomplete_tree(self):
        r = R.resolve_with_config(specifier="@/utils",
                                  importing_file_path="src/app.ts",
                                  tree_paths={"src/utils.ts"},
                                  tsconfig_observation=tc({"@/*": ["./src/*"]}),
                                  source_completeness="PARTIAL")
        self.assertEqual(r["resolution_state"], "INSUFFICIENT_TREE_COVERAGE")

    def test_G31_wrong_commit(self):
        cfg = CM.build_config_observation(
            repository_id=REPO, commit_sha=COMMIT_B, config_path="tsconfig.json",
            config_kind="tsconfig", git_blob_oid="b"*40,
            content_asset_id="X", content_digest="sha256:z",
            effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED,
            declared_paths=[{"pattern": "@/*", "targets": ["./src/*"]}])
        self.assertEqual(cfg["commit_sha"], COMMIT_B)

    def test_G32_wrong_repo(self):
        q = MQ.query_relations(repository_id="other-repo", data_root=self.tmp)
        self.assertEqual(q["relations"], [])

    def test_G33_bad_config(self):
        r = R.resolve_with_config(
            specifier="@/x", importing_file_path="src/app.ts",
            tree_paths={"src/x.ts"},
            tsconfig_observation=tc({"@/*": ["./src/*"]},
                                    status="CONFIG_INTEGRITY_FAILED"))
        self.assertEqual(r["resolution_state"], "CONFIG_NOT_CAPTURED")

    def test_G34_target_missing(self):
        r = R.resolve_with_config(specifier="@/ghost",
                                  importing_file_path="src/app.ts",
                                  tree_paths={"src/app.ts"},
                                  tsconfig_observation=tc({"@/*": ["./src/*"]}))
        self.assertEqual(r["unresolved_reason"], "TARGET_NOT_IN_TREE")

    def test_G35_traversal(self):
        r = R.resolve_with_config(specifier="@/x",
                                  importing_file_path="src/app.ts",
                                  tree_paths={"src/x.ts"},
                                  tsconfig_observation=tc({"@/*":
                                                           ["../../etc/*"]}))
        self.assertEqual(r["resolution_state"], "PATH_ESCAPES_REPOSITORY")

    def test_G36_case_diff(self):
        r = R.resolve_with_config(specifier="@/Utils",
                                  importing_file_path="src/app.ts",
                                  tree_paths={"src/utils.ts"},
                                  tsconfig_observation=tc({"@/*": ["./src/*"]}))
        self.assertNotEqual(r["resolved_target_path"], "src/utils.ts")

    def test_G37_ambiguous(self):
        r = R.resolve_with_config(specifier="@/dup",
                                  importing_file_path="src/app.ts",
                                  tree_paths={"src/dup.ts", "src/dup.tsx"},
                                  tsconfig_observation=tc({"@/*": ["./src/*"]}))
        self.assertEqual(r["resolution_state"], "AMBIGUOUS_CANDIDATES")

    def test_G38_no_runtime_state(self):
        for spec in ("@/x", "react", "./y", "#z"):
            r = R.resolve_with_config(
                specifier=spec, importing_file_path="src/app.ts",
                tree_paths={"src/x.ts"},
                tsconfig_observation=tc({"@/*": ["./src/*"]}))
            self.assertNotIn("RUNTIME", r["resolution_state"].upper())


class TestIdentityGold(Base):
    def test_G39_idempotent(self):
        cfg = CM.build_config_observation(
            repository_id=REPO, commit_sha=COMMIT, config_path="tsconfig.json",
            config_kind="tsconfig", git_blob_oid="b"*40, content_asset_id="X",
            content_digest="sha256:d",
            effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED)
        r1 = CM.build_resolution_observation(
            repository_id=REPO, commit_sha=COMMIT,
            importing_file_path="src/app.ts", importing_blob_oid="c"*40,
            importing_content_asset_id="X", import_fact_id="F1",
            module_specifier="@/u", import_kind="named_import",
            is_type_only=False,
            config_observation_ids=[cfg["config_observation_id"]],
            config_blob_oids=["b"*40], resolution_policy="p/1",
            matched_config_rule="@/*", candidate_paths=["src/u.ts"],
            resolved_target_path="src/u.ts",
            resolution_state="LOCAL_MODULE_RESOLVED", evidence_refs=["e"])
        r2 = CM.build_resolution_observation(
            repository_id=REPO, commit_sha=COMMIT,
            importing_file_path="src/app.ts", importing_blob_oid="c"*40,
            importing_content_asset_id="X", import_fact_id="F1",
            module_specifier="@/u", import_kind="named_import",
            is_type_only=False,
            config_observation_ids=[cfg["config_observation_id"]],
            config_blob_oids=["b"*40], resolution_policy="p/1",
            matched_config_rule="@/*", candidate_paths=["src/u.ts"],
            resolved_target_path="src/u.ts",
            resolution_state="LOCAL_MODULE_RESOLVED", evidence_refs=["e"])
        self.assertEqual(r1["resolution_id"], r2["resolution_id"])

    def test_G40_version_changes_id(self):
        cfg = CM.build_config_observation(
            repository_id=REPO, commit_sha=COMMIT, config_path="tsconfig.json",
            config_kind="tsconfig", git_blob_oid="b"*40, content_asset_id="X",
            content_digest="sha256:d",
            effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED)
        a = CM.build_resolution_observation(
            repository_id=REPO, commit_sha=COMMIT,
            importing_file_path="src/app.ts", importing_blob_oid="c"*40,
            importing_content_asset_id="X", import_fact_id="F1",
            module_specifier="@/u", import_kind="named_import",
            is_type_only=False,
            config_observation_ids=[cfg["config_observation_id"]],
            config_blob_oids=["b"*40], resolution_policy="p/1",
            matched_config_rule="@/*", candidate_paths=["src/u.ts"],
            resolved_target_path="src/u.ts",
            resolution_state="LOCAL_MODULE_RESOLVED", evidence_refs=["e"])
        b = CM.build_resolution_observation(
            repository_id=REPO, commit_sha=COMMIT,
            importing_file_path="src/app.ts", importing_blob_oid="c"*40,
            importing_content_asset_id="X", import_fact_id="F1",
            module_specifier="@/u", import_kind="named_import",
            is_type_only=False,
            config_observation_ids=[cfg["config_observation_id"]],
            config_blob_oids=["b"*40], resolution_policy="p/2",
            matched_config_rule="@/*", candidate_paths=["src/u.ts"],
            resolved_target_path="src/u.ts",
            resolution_state="LOCAL_MODULE_RESOLVED", evidence_refs=["e"])
        self.assertNotEqual(a["resolution_id"], b["resolution_id"])

    def test_G41_dual_commit(self):
        a = CM.build_config_observation(
            repository_id=REPO, commit_sha=COMMIT, config_path="tsconfig.json",
            config_kind="tsconfig", git_blob_oid="b"*40, content_asset_id="X",
            content_digest="sha256:a",
            effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED,
            declared_paths=[{"pattern": "@/*", "targets": ["./src/*"]}])
        b = CM.build_config_observation(
            repository_id=REPO, commit_sha=COMMIT_B, config_path="tsconfig.json",
            config_kind="tsconfig", git_blob_oid="c"*40, content_asset_id="Y",
            content_digest="sha256:b",
            effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED,
            declared_paths=[{"pattern": "@/*", "targets": ["./lib/*"]}])
        self.assertNotEqual(a["config_observation_id"],
                            b["config_observation_id"])
        self.assertNotEqual(a["declared_paths"], b["declared_paths"])

    def test_G42_dangling_evidence(self):
        rel = {"import_fact_id": None, "config_observation_ids": ["C"],
               "config_blob_oids": ["b"], "resolved_target_path": "src/x.ts",
               "importing_blob_oid": "c", "evidence_refs": []}
        ok, why = MA.evidence_complete(resolution=rel)
        self.assertFalse(ok)

    def test_G44_reason_codes(self):
        import ec_models as M
        legal = [v for k, v in vars(M).items() if k.startswith("R_")]
        for _, code in MA._STATE_REASON.items():
            self.assertIn(code, legal)


class TestGoldRegistry(unittest.TestCase):
    def test_headers_consistent(self):
        for gid, cat, desc, exp in GOLD:
            self.assertTrue(gid and cat and desc and exp, gid)
        cats = {g[1] for g in GOLD}
        self.assertGreaterEqual(len(cats), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
