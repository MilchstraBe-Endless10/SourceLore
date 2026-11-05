#!/usr/bin/env python3
"""第二层：Config Observation / Relation Fact / Claim 真正落库。"""
import sys, unittest, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"module_resolution"))
import sfx
import module_config_models as CM
import module_relation_ingest as MI
import module_relation_adapter as MA
import module_relation_query as MQ
import config_aware_resolver as R
import tsconfig_parser as TP
from knowledge_store import KnowledgeStore

REPO = "990001"
COMMIT = "a"*40
COMMIT_B = "b"*40


def cfg_obs(*, commit=COMMIT, paths=None, config_path="tsconfig.json",
            config_dir=""):
    s = TP.extract_config_surface(
        {"compilerOptions": {"paths": paths or {"@/*": ["./src/*"]}}},
        config_dir=config_dir)
    return CM.build_config_observation(
        repository_id=REPO, commit_sha=commit, config_path=config_path,
        config_kind=CM.CONFIG_TSCONFIG, git_blob_oid="b"*40,
        content_asset_id="SL-A-cfg", content_digest="sha256:cfg-" + commit[:6],
        effective_config_status=CM.EFFECTIVE_CONFIG_RESOLVED,
        declared_paths=s["paths"], provenance_level="AUTHORIZED_LOCAL_FIXTURE")


def rel_obs(*, cfg, specifier="@/utils", target="src/utils.ts",
            commit=COMMIT, state=None):
    return CM.build_resolution_observation(
        repository_id=REPO, commit_sha=commit,
        importing_file_path="src/app.ts", importing_blob_oid="c"*40,
        importing_content_asset_id="SL-A-src", import_fact_id="SL-FACT-imp",
        module_specifier=specifier, import_kind="named_import",
        is_type_only=False,
        config_observation_ids=[cfg["config_observation_id"]],
        config_blob_oids=["b"*40], resolution_policy="config-aware/1",
        matched_config_field="paths", matched_config_rule="@/*",
        matched_config_path=cfg["config_path"],
        candidate_paths=[target], resolved_target_path=target,
        resolution_state=state or CM.LOCAL_MODULE_RESOLVED,
        evidence_refs=["module_config:SL-A-cfg", "source:SL-A-src",
                       "tree:src/utils.ts"],
        provenance_level="AUTHORIZED_LOCAL_FIXTURE")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="modrel_"))
        self.ks = KnowledgeStore(str(self.tmp/"kb.db"))

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestConfigPersistence(Base):
    def test_config_facts_written(self):
        cfg = cfg_obs()
        r = MI.ingest_config_observation(self.ks, observation=cfg)
        self.assertGreaterEqual(len(r["written"]), 1)
        self.assertIn("MODULE_CONFIG_PATHS_DECLARED",
                      [w["rule_id"] for w in r["written"]])

    def test_config_idempotent(self):
        cfg = cfg_obs()
        MI.ingest_config_observation(self.ks, observation=cfg)
        r2 = MI.ingest_config_observation(self.ks, observation=cfg)
        self.assertEqual(r2["written"], [])
        self.assertGreater(len(r2["reused"]), 0)

    def test_config_identity_changes_with_commit(self):
        a = cfg_obs(commit=COMMIT)
        b = cfg_obs(commit=COMMIT_B)
        self.assertNotEqual(a["config_observation_id"],
                            b["config_observation_id"])


class TestRelationPersistence(Base):
    def test_relation_written(self):
        cfg = cfg_obs()
        MI.ingest_config_observation(self.ks, observation=cfg)
        rel = rel_obs(cfg=cfg)
        r = MI.ingest_resolution(self.ks, resolution=rel,
                                 evidence_refs=rel["evidence_refs"])
        self.assertEqual(len(r["written"]), 1)

    def test_unresolved_not_persisted(self):
        """★ 阻断级：非 LOCAL_MODULE_RESOLVED 不产权威事实。"""
        cfg = cfg_obs()
        rel = rel_obs(cfg=cfg, state=CM.AMBIGUOUS_CANDIDATES)
        r = MI.ingest_resolution(self.ks, resolution=rel,
                                 evidence_refs=rel["evidence_refs"])
        self.assertEqual(r["written"], [])
        self.assertEqual(r["skipped"][0]["reason"], "NOT_RESOLVED")

    def test_empty_evidence_not_persisted(self):
        rel = rel_obs(cfg=cfg_obs())
        r = MI.ingest_resolution(self.ks, resolution=rel, evidence_refs=[])
        self.assertEqual(r["written"], [])
        self.assertEqual(r["skipped"][0]["reason"], "EVIDENCE_EMPTY")

    def test_relation_idempotent(self):
        cfg = cfg_obs()
        rel = rel_obs(cfg=cfg)
        MI.ingest_resolution(self.ks, resolution=rel,
                             evidence_refs=rel["evidence_refs"])
        r2 = MI.ingest_resolution(self.ks, resolution=rel,
                                  evidence_refs=rel["evidence_refs"])
        self.assertEqual(r2["written"], [])
        self.assertGreater(len(r2["reused"]), 0)

    def test_resolution_id_changes_with_config(self):
        """★ 配置变 → 关系身份必须变。"""
        a = rel_obs(cfg=cfg_obs(commit=COMMIT))
        b = rel_obs(cfg=cfg_obs(commit=COMMIT_B), commit=COMMIT_B)
        self.assertNotEqual(a["resolution_id"], b["resolution_id"])

    def test_query_returns_relations(self):
        cfg = cfg_obs()
        MI.ingest_config_observation(self.ks, observation=cfg)
        rel = rel_obs(cfg=cfg)
        MI.ingest_resolution(self.ks, resolution=rel,
                             evidence_refs=rel["evidence_refs"])
        q = MQ.query_relations(repository_id=REPO, commit_sha=COMMIT,
                               importing_file_path="src/app.ts",
                               data_root=self.tmp)
        self.assertEqual(q["state"], "RELATIONS_FOUND")
        self.assertEqual(q["counts"]["relations"], 1)
        self.assertEqual(q["counts"]["resolved"], 1)
        self.assertEqual(q["network_requests"], 0)
        self.assertEqual(q["relations"][0]["matched_config_rule"], "@/*")

    def test_query_by_specifier(self):
        cfg = cfg_obs()
        MI.ingest_config_observation(self.ks, observation=cfg)
        for spec in ("@/utils", "@/other"):
            rel = rel_obs(cfg=cfg, specifier=spec)
            MI.ingest_resolution(self.ks, resolution=rel,
                                 evidence_refs=rel["evidence_refs"])
        q = MQ.query_relations(repository_id=REPO, module_specifier="@/utils",
                               data_root=self.tmp)
        self.assertEqual(len(q["relations"]), 1)

    def test_query_wrong_commit_empty(self):
        cfg = cfg_obs()
        MI.ingest_config_observation(self.ks, observation=cfg)
        rel = rel_obs(cfg=cfg)
        MI.ingest_resolution(self.ks, resolution=rel,
                             evidence_refs=rel["evidence_refs"])
        q = MQ.query_relations(repository_id=REPO, commit_sha=COMMIT_B,
                               data_root=self.tmp)
        self.assertEqual(q["relations"], [])

    def test_configs_returned(self):
        cfg = cfg_obs()
        MI.ingest_config_observation(self.ks, observation=cfg)
        rel = rel_obs(cfg=cfg)
        MI.ingest_resolution(self.ks, resolution=rel,
                             evidence_refs=rel["evidence_refs"])
        q = MQ.query_relations(repository_id=REPO, data_root=self.tmp)
        self.assertGreaterEqual(q["counts"]["configs"], 1)


class TestVerdict(Base):
    def _v(self, rel, facts):
        claim, binding = MA.build_relation_claim(
            repository_id=REPO, commit_sha=rel["commit_sha"],
            importing_file_path=rel["importing_file_path"],
            module_specifier=rel["module_specifier"],
            import_kind=rel["import_kind"], is_type_only=rel["is_type_only"],
            expected_target_path=rel["resolved_target_path"],
            expected_matched_rule=rel["matched_config_rule"])
        ok, why = MA.evidence_complete(resolution=rel)
        return MA.verify_relation_claim(
            claim=claim, facts=facts,
            resolution_state=rel["resolution_state"],
            evidence_complete=ok, subject_binding=binding)

    def test_supported(self):
        cfg = cfg_obs()
        MI.ingest_config_observation(self.ks, observation=cfg)
        rel = rel_obs(cfg=cfg)
        MI.ingest_resolution(self.ks, resolution=rel,
                             evidence_refs=rel["evidence_refs"])
        facts = MQ.query_relations(repository_id=REPO, data_root=self.tmp)["relations"]
        v = self._v(rel, facts)
        self.assertEqual(v["status"], "supported")

    def test_config_not_captured_abstains(self):
        cfg = cfg_obs()
        rel = rel_obs(cfg=cfg, state=CM.CONFIG_NOT_CAPTURED)
        v = self._v(rel, [])
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "FACT_NOT_FOUND")

    def test_ambiguous_abstains(self):
        cfg = cfg_obs()
        rel = rel_obs(cfg=cfg, state=CM.AMBIGUOUS_CANDIDATES)
        v = self._v(rel, [])
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "CONFLICTING_EVIDENCE")

    def test_incomplete_evidence_abstains(self):
        cfg = cfg_obs()
        rel = rel_obs(cfg=cfg)
        rel["config_blob_oids"] = []
        v = self._v(rel, [])
        self.assertEqual(v["status"], "insufficient_evidence")
        self.assertEqual(v["reason_code"], "EVIDENCE_FIELD_MISSING")

    def test_no_refuted_ever(self):
        """★ 阻断级：绝不产 refuted。"""
        for state in (CM.CONFIG_NOT_CAPTURED, CM.AMBIGUOUS_CANDIDATES,
                      CM.UNSUPPORTED_RESOLUTION_POLICY,
                      CM.INSUFFICIENT_TREE_COVERAGE, CM.DYNAMIC_SPECIFIER):
            v = self._v(rel_obs(cfg=cfg_obs(), state=state), [])
            self.assertNotEqual(v["status"], "refuted", state)

    def test_all_reason_codes_legal(self):
        """★ D-17 回归：映射出的码必须在 EC 封闭集内。"""
        import ec_models as M
        legal = [v for k, v in vars(M).items() if k.startswith("R_")]
        for state, code in MA._STATE_REASON.items():
            self.assertIn(code, legal, f"{state} → {code}")

    def test_evidence_complete_checks(self):
        cfg = cfg_obs()
        rel = rel_obs(cfg=cfg)
        ok, why = MA.evidence_complete(resolution=rel)
        self.assertTrue(ok)
        rel["import_fact_id"] = None
        ok2, why2 = MA.evidence_complete(resolution=rel)
        self.assertFalse(ok2)
        self.assertEqual(why2, "IMPORT_EVIDENCE_MISSING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
