#!/usr/bin/env python3
"""第二层：项目/引用/归属事实真正落库 + 裁决 + 查询。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"ts_projects"))
import sfx
import ts_project_context as C
import ts_project_models as PM
import ts_project_ingest as TI
import ts_project_adapter as TA
import ts_project_query as TQ
from knowledge_store import KnowledgeStore

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
        self.tmp = Path(tempfile.mkdtemp(prefix="tsp_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, tree, b, commit=COMMIT):
        return C.build_all_projects(tree_paths=tree, config_blobs=b,
                                    repository_id=REPO, commit_sha=commit,
                                    provenance_level="AUTHORIZED_LOCAL_FIXTURE")


class TestPersistence(Base):
    def test_project_fact_written(self):
        tree = {"tsconfig.json", "src/a.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        bundle = self._build(tree, b)
        r = TI.ingest_project_bundle(store=self.ks, bundle=bundle)
        self.assertGreaterEqual(len(r["written"]), 1)
        rows = self.ks.conn.execute(
            "SELECT count(*) c FROM index_rows WHERE asset_type='extracted_fact'"
        ).fetchone()
        self.assertGreater(rows["c"], 0)

    def test_reference_fact_written(self):
        tree = {"tsconfig.json", "packages/a/tsconfig.json"}
        b = blobs(tsconfig_json='{"files":[],"references":[{"path":"./packages/a"}]}',
                  packages__a__tsconfig_json='{}')
        bundle = self._build(tree, b)
        r = TI.ingest_project_bundle(store=self.ks, bundle=bundle)
        kinds = {w["kind"] for w in r["written"]}
        self.assertIn("reference", kinds)

    def test_membership_fact_written(self):
        tree = {"tsconfig.json", "src/a.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        bundle = self._build(tree, b)
        p = next(x for x in bundle["projects"]
                 if x["config_path"] == "tsconfig.json")
        ms = C.build_memberships(project=p,
                                 details=bundle["details"],
                                 tree_paths=tree, target_files=["src/a.ts"])
        r = TI.ingest_project_bundle(store=self.ks, bundle=bundle, memberships=ms)
        kinds = {w["kind"] for w in r["written"]}
        self.assertIn("membership", kinds)

    def test_idempotent(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"include":["src/*.ts"]}')
        bundle = self._build(tree, b)
        TI.ingest_project_bundle(store=self.ks, bundle=bundle)
        r2 = TI.ingest_project_bundle(store=self.ks, bundle=bundle)
        self.assertEqual(r2["written"], [])
        self.assertGreater(len(r2["reused"]), 0)

    def test_identity_differs_by_commit(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"include":["src/*.ts"]}')
        a = self._build(tree, b, COMMIT)
        c = self._build(tree, b, COMMIT_B)
        self.assertNotEqual(a["projects"][0]["project_observation_id"],
                            c["projects"][0]["project_observation_id"])


class TestVerdict(Base):
    def _facts(self, tree, b):
        bundle = self._build(tree, b)
        p = next(x for x in bundle["projects"]
                 if x["config_path"] == "tsconfig.json")
        ms = C.build_memberships(project=p, details=bundle["details"],
                                 tree_paths=tree, target_files=["src/a.ts"])
        TI.ingest_project_bundle(store=self.ks, bundle=bundle, memberships=ms)
        return bundle, ms

    def test_project_supported(self):
        tree = {"tsconfig.json", "src/a.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        self._facts(tree, b)
        q = TQ.query_projects(repository_id=REPO, commit_sha=COMMIT,
                              data_root=self.tmp)
        p = q["projects"][0]
        claim, binding = TA.build_project_claim(
            repository_id=REPO, commit_sha=COMMIT,
            config_path=p["config_path"])
        facts = TQ.query_projects(repository_id=REPO, data_root=self.tmp)["projects"]
        v = TA.verify_ts_claim(claim=claim, facts=facts,
                               status=p["discovery_status"],
                               subject_binding=binding)
        self.assertEqual(v["status"], "supported")

    def test_membership_supported_when_selected(self):
        tree = {"tsconfig.json", "src/a.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        bundle, ms = self._facts(tree, b)
        m = ms[0]
        claim, binding = TA.build_membership_claim(
            repository_id=REPO, commit_sha=COMMIT,
            config_path=m["config_path"],
            source_file_path=m["source_file_path"],
            expected_state=m["state"])
        facts = TQ.query_projects(repository_id=REPO, data_root=self.tmp)["memberships"]
        v = TA.verify_ts_claim(claim=claim, facts=facts, status=m["state"],
                               subject_binding=binding)
        self.assertEqual(v["status"], "supported")

    def test_excluded_abstains(self):
        tree = {"tsconfig.json", "src/generated/g.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"],'
                                '"exclude":["src/generated/**"]}')
        bundle = self._build(tree, b)
        p = next(x for x in bundle["projects"]
                 if x["config_path"] == "tsconfig.json")
        ms = C.build_memberships(project=p, details=bundle["details"],
                                 tree_paths=tree,
                                 target_files=["src/generated/g.ts"])
        m = ms[0]
        self.assertEqual(m["state"], PM.INPUT_EXCLUDED_FROM_INCLUDE)
        claim, binding = TA.build_membership_claim(
            repository_id=REPO, commit_sha=COMMIT,
            config_path=m["config_path"],
            source_file_path=m["source_file_path"])
        v = TA.verify_ts_claim(claim=claim, facts=[], status=m["state"],
                               subject_binding=binding)
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertNotEqual(v["status"], "refuted")

    def test_not_captured_abstains(self):
        claim, binding = TA.build_project_claim(
            repository_id=REPO, commit_sha=COMMIT, config_path="tsconfig.json")
        v = TA.verify_ts_claim(
            claim=claim, facts=[], status=PM.PROJECT_CONFIG_NOT_CAPTURED,
            subject_binding=binding)
        self.assertEqual(v["status"], "insufficient_evidence")

    def test_all_reason_codes_legal(self):
        import ec_models as M
        legal = [v for k, v in vars(M).items() if k.startswith("R_")]
        for state, code in TA._STATUS_REASON.items():
            self.assertIn(code, legal, f"{state} → {code}")

    def test_no_refuted_anywhere(self):
        for state in (PM.PROJECT_CONFIG_INVALID, PM.PROJECT_CONFIG_AMBIGUOUS,
                      PM.INPUT_NOT_PROVEN, PM.INPUT_MATCHED_MULTIPLE_PROJECTS,
                      PM.UNSUPPORTED_SELECTION_RULE):
            claim, binding = TA.build_project_claim(
                repository_id=REPO, commit_sha=COMMIT,
                config_path="tsconfig.json")
            v = TA.verify_ts_claim(claim=claim, facts=[], status=state,
                                   subject_binding=binding)
            self.assertNotEqual(v["status"], "refuted", state)


class TestQuery(Base):
    def test_query_projects(self):
        tree = {"tsconfig.json", "src/a.ts"}
        b = blobs(tsconfig_json='{"include":["src/**/*.ts"]}')
        bundle = self._build(tree, b)
        p = bundle["projects"][0]
        ms = C.build_memberships(project=p, details=bundle["details"],
                                 tree_paths=tree, target_files=["src/a.ts"])
        TI.ingest_project_bundle(store=self.ks, bundle=bundle, memberships=ms)
        q = TQ.query_projects(repository_id=REPO, commit_sha=COMMIT,
                              data_root=self.tmp)
        self.assertEqual(q["state"], "PROJECTS_FOUND")
        self.assertEqual(q["counts"]["projects"], 1)
        self.assertEqual(q["network_requests"], 0)

    def test_query_by_config(self):
        tree = {"tsconfig.json", "packages/a/tsconfig.json"}
        b = blobs(tsconfig_json='{"include":["src/*.ts"]}',
                  packages__a__tsconfig_json='{"include":["src/*.ts"]}')
        bundle = self._build(tree, b)
        TI.ingest_project_bundle(store=self.ks, bundle=bundle)
        q = TQ.query_projects(repository_id=REPO,
                              config_path="packages/a/tsconfig.json",
                              data_root=self.tmp)
        self.assertEqual(len(q["projects"]), 1)

    def test_query_membership_lists_all(self):
        tree = {"tsconfig.json", "packages/a/tsconfig.json", "shared/u.ts"}
        b = blobs(tsconfig_json='{"include":["shared/**/*.ts"]}',
                  packages__a__tsconfig_json='{"include":["../../shared/**/*.ts"]}')
        bundle = self._build(tree, b)
        all_ms, q_ms = [], []
        for p in bundle["projects"]:
            ms = C.build_memberships(project=p, details=bundle["details"],
                                     tree_paths=tree,
                                     target_files=["shared/u.ts"])
            all_ms.extend(ms)
        TI.ingest_project_bundle(store=self.ks, bundle=bundle,
                                 memberships=all_ms)
        q = TQ.resolve_file_membership(repository_id=REPO,
                                       file_path="shared/u.ts",
                                       data_root=self.tmp)
        self.assertEqual(len(q["candidates"]), 2, "多候选必须全列")

    def test_query_wrong_commit_empty(self):
        tree = {"tsconfig.json"}
        b = blobs(tsconfig_json='{"include":["src/*.ts"]}')
        bundle = self._build(tree, b)
        TI.ingest_project_bundle(store=self.ks, bundle=bundle)
        q = TQ.query_projects(repository_id=REPO, commit_sha=COMMIT_B,
                              data_root=self.tmp)
        self.assertEqual(q["projects"], [])

    def test_query_unregistered_repo(self):
        q = TQ.query_projects(repository_id="other", data_root=self.tmp)
        self.assertEqual(q["state"], "REPOSITORY_NOT_REGISTERED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
