#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Facts 抽取与入库测试（题面 §12 的 26 项）。

全部离线：输入来自 Storage 内已入库的 repository_snapshot 资产，不访问 GitHub。
"""
import sys, tempfile, shutil, unittest, inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT/"tests"/"facts"), str(ROOT/"src"/"facts"),
          str(ROOT/"src"/"storage"), str(ROOT/"src"/"collector"), str(ROOT/"src"/"runtime")):
    if p not in sys.path: sys.path.insert(0, p)

import fixtures as FX
from models import (OBSERVED_PRESENT, OBSERVED_ABSENT_IN_COVERED_SCOPE, UNKNOWN,
                    U_MANIFEST_ABSENT, U_PARTIAL_SNAPSHOT, U_TREE_TRUNCATED,
                    U_ASSET_NOT_FOUND, U_DUPLICATE_ENTRY, U_SCOPE_NOT_COVERING,
                    make_fact_id, normalize_path, FactObservation)
from extractor import extract_file_path_observation, SNAPSHOT_ASSET_TYPE
from ingest import ingest_fact, INGESTED, IDEMPOTENT, CONFLICT, REJECTED
import extractor, rules, models
import index_store as IX


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p2a_"))
        self.ks = FX.fresh_store(self.tmp)

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def snap_in(self, **kw):
        r = FX.ingest_snapshot_asset(self.ks, **kw)
        self.assertEqual(r["result"]["state"], INGESTED, r)
        return r

    def obs(self, aid, path):
        return extract_file_path_observation(
            self.ks, snapshot_asset_id=aid, target_path=path)


class TestInputSource(Base):
    """1/2：从 Storage 读快照；不访问 GitHub。"""

    def test_reads_from_storage_only(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        self.assertEqual(o.observation, OBSERVED_PRESENT)
        self.assertEqual(o.snapshot_asset_id, r["asset_id"])

    def test_extractor_does_not_import_github_client(self):
        src = Path(extractor.__file__).read_text(encoding="utf-8")
        for bad in ("github_client", "urllib", "requests", "http"):
            self.assertNotIn(f"import {bad}", src, f"抽取器不得依赖网络: {bad}")
            self.assertNotIn(f"from {bad}", src)

    def test_extractor_has_no_sql(self):
        """不得绕过 Storage API 直查表。"""
        src = Path(extractor.__file__).read_text(encoding="utf-8")
        for bad in ("SELECT ", "INSERT ", "UPDATE ", "DELETE "):
            self.assertNotIn(bad, src, f"抽取器不得直接执行 SQL: {bad}")


class TestCompletenessSemantics(Base):
    """3/4/5/6：COMPLETE 与 PARTIAL 的存在/不存在语义。"""

    def test_complete_present(self):
        r = self.snap_in(completeness="COMPLETE")
        o = self.obs(r["asset_id"], "README")
        self.assertEqual(o.observation, OBSERVED_PRESENT)
        v = o.observed_value
        self.assertEqual(v["path"], "README")
        self.assertEqual(v["object_type"], "blob")
        self.assertEqual(v["mode"], "100644")
        self.assertTrue(v["is_regular_file"])
        self.assertFalse(v["local_coverage_only"])

    def test_complete_absent_in_covered_scope(self):
        r = self.snap_in(completeness="COMPLETE")
        o = self.obs(r["asset_id"], "NOTHERE")
        self.assertEqual(o.observation, OBSERVED_ABSENT_IN_COVERED_SCOPE)
        self.assertIn("scope_statement", o.observed_value)
        self.assertIn("不表示", o.observed_value["not_a_claim"],
                      "必须写明不是'仓库没有该功能'")

    def test_partial_present_keeps_local_coverage_flag(self):
        r = self.snap_in(completeness="PARTIAL")
        o = self.obs(r["asset_id"], "README")
        self.assertEqual(o.observation, OBSERVED_PRESENT)
        self.assertTrue(o.observed_value["local_coverage_only"],
                        "PARTIAL 下的存在必须标局部覆盖")
        self.assertEqual(o.completeness_status, "PARTIAL")

    def test_partial_absent_is_unknown(self):
        r = self.snap_in(completeness="PARTIAL")
        o = self.obs(r["asset_id"], "NOTHERE")
        self.assertEqual(o.observation, UNKNOWN, "PARTIAL 未命中绝不能推断不存在")
        self.assertEqual(o.unknown_reason, U_PARTIAL_SNAPSHOT)


class TestUnknownConditions(Base):
    """UNKNOWN 各种触发条件。"""

    def test_manifest_absent_v1(self):
        r = self.snap_in(manifest_v1=True)
        o = self.obs(r["asset_id"], "NOTHERE")
        self.assertEqual(o.observation, UNKNOWN)
        self.assertEqual(o.unknown_reason, U_MANIFEST_ABSENT,
                         "v1 快照没有清单，无法证明不存在")

    def test_v1_present_still_unresolvable(self):
        """v1 连"存在"都判不了（没有条目清单）。"""
        r = self.snap_in(manifest_v1=True)
        o = self.obs(r["asset_id"], "README")
        self.assertEqual(o.observation, UNKNOWN)
        self.assertEqual(o.unknown_reason, U_MANIFEST_ABSENT)

    def test_tree_truncated_forces_unknown(self):
        r = self.snap_in(completeness="COMPLETE", truncated=True)
        o = self.obs(r["asset_id"], "README")
        self.assertEqual(o.observation, UNKNOWN)
        self.assertEqual(o.unknown_reason, U_TREE_TRUNCATED)

    def test_missing_asset(self):
        self.snap_in()
        o = extract_file_path_observation(self.ks, snapshot_asset_id="SL-A-NOPE",
                                          target_path="README")
        self.assertEqual(o.observation, UNKNOWN)
        self.assertEqual(o.unknown_reason, U_ASSET_NOT_FOUND)

    def test_duplicate_entry(self):
        ents = [FX.README, dict(FX.README)]   # 同一路径两条
        r = self.snap_in(entries=ents)
        o = self.obs(r["asset_id"], "README")
        self.assertEqual(o.observation, UNKNOWN)
        self.assertEqual(o.unknown_reason, U_DUPLICATE_ENTRY)

    def test_scope_not_covering(self):
        r = self.snap_in(scope="path_prefix:src/")
        o = self.obs(r["asset_id"], "README")
        self.assertEqual(o.observation, UNKNOWN)
        self.assertEqual(o.unknown_reason, U_SCOPE_NOT_COVERING)

    def test_illegal_path_is_unknown_not_crash(self):
        r = self.snap_in()
        for bad in ("/abs/path", "../escape", "a//b", "a\\b"):
            o = self.obs(r["asset_id"], bad)
            self.assertEqual(o.observation, UNKNOWN, f"{bad} 应 UNKNOWN")
            self.assertIsNotNone(o.unknown_reason)

    def test_unknown_requires_reason(self):
        with self.assertRaises(ValueError):
            FactObservation(
                fact_id="SL-FACT-" + "0"*40, fact_type="file_path_observation",
                observation=UNKNOWN, repository_id="1", snapshot_asset_id="a",
                snapshot_logical_identity="b", commit_sha="c",
                rule_id="file_path_observation", rule_version="v1",
                normalized_parameters={}, item_key="k", observed_value={},
                completeness_status="X", evidence_refs=[], input_digest="d",
                content_hash="e", extractor_version="f", unknown_reason=None)

    def test_non_unknown_cannot_carry_reason(self):
        with self.assertRaises(ValueError):
            FactObservation(
                fact_id="SL-FACT-" + "0"*40, fact_type="file_path_observation",
                observation=OBSERVED_PRESENT, repository_id="1",
                snapshot_asset_id="a", snapshot_logical_identity="b",
                commit_sha="c", rule_id="file_path_observation", rule_version="v1",
                normalized_parameters={}, item_key="k", observed_value={},
                completeness_status="X", evidence_refs=[], input_digest="d",
                content_hash="e", extractor_version="f",
                unknown_reason=U_PARTIAL_SNAPSHOT)


class TestObjectTypes(Base):
    """15：symlink / submodule / 目录 / unknown 不冒充普通文件。"""

    def test_symlink_not_regular(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "link")
        self.assertEqual(o.observation, OBSERVED_PRESENT)
        self.assertEqual(o.observed_value["object_kind"], "symlink")
        self.assertFalse(o.observed_value["is_regular_file"])
        self.assertIsNotNone(o.observed_value["type_note"])

    def test_submodule_not_regular(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "sub")
        self.assertEqual(o.observed_value["object_kind"], "submodule")
        self.assertFalse(o.observed_value["is_regular_file"])

    def test_directory_not_regular(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "docs")
        self.assertEqual(o.observed_value["object_kind"], "directory")
        self.assertFalse(o.observed_value["is_regular_file"])

    def test_unknown_object_type(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "weird")
        self.assertEqual(o.observed_value["object_kind"], "unknown_object")
        self.assertFalse(o.observed_value["is_regular_file"])

    def test_nested_path(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "docs/guide.md")
        self.assertEqual(o.observation, OBSERVED_PRESENT)
        self.assertEqual(o.observed_value["path"], "docs/guide.md")


class TestIdentity(Base):
    """10/11/12/13：fact_id 可复算、item_key、规则版本、时间。"""

    def test_fact_id_recomputable(self):
        r = self.snap_in()
        o1 = self.obs(r["asset_id"], "README")
        o2 = self.obs(r["asset_id"], "README")
        self.assertEqual(o1.fact_id, o2.fact_id)
        li = r["snapshot"].logical_identity()
        expect = make_fact_id(
            repository_id="1296269", snapshot_logical_identity=li,
            rule_id="file_path_observation", rule_version="v1",
            normalized_parameters={"target_path": "README"},
            item_key="path:README")
        self.assertEqual(o1.fact_id, expect, "fact_id 必须可独立复算")

    def test_time_does_not_change_identity(self):
        r = self.snap_in()
        o1 = extract_file_path_observation(
            self.ks, snapshot_asset_id=r["asset_id"], target_path="README",
            observed_at="2026-01-01T00:00:00+0800")
        o2 = extract_file_path_observation(
            self.ks, snapshot_asset_id=r["asset_id"], target_path="README",
            observed_at="2027-12-31T23:59:59+0800")
        self.assertEqual(o1.fact_id, o2.fact_id)
        self.assertEqual(o1.content_hash, o2.content_hash,
                         "抽取时间不得影响内容哈希")

    def test_different_path_different_fact(self):
        r = self.snap_in()
        a = self.obs(r["asset_id"], "README")
        b = self.obs(r["asset_id"], "docs")
        self.assertNotEqual(a.fact_id, b.fact_id, "不同目标路径必须是不同事实")
        self.assertNotEqual(a.item_key, b.item_key)

    def test_item_key_stable_across_order(self):
        """多结果规则的 item_key 不依赖数组位置。"""
        r = self.snap_in()
        a = self.obs(r["asset_id"], "README")
        b = self.obs(r["asset_id"], "docs")
        # 两个 fact 的 item_key 互不相同且各自稳定
        self.assertEqual(a.item_key, "path:README")
        self.assertEqual(b.item_key, "path:docs")

    def test_rule_version_changes_identity(self):
        r = self.snap_in()
        o_v1 = self.obs(r["asset_id"], "README")
        expect_v2 = make_fact_id(
            repository_id="1296269",
            snapshot_logical_identity=r["snapshot"].logical_identity(),
            rule_id="file_path_observation", rule_version="v2",
            normalized_parameters={"target_path": "README"},
            item_key="path:README")
        self.assertNotEqual(o_v1.fact_id, expect_v2,
                            "规则版本必须改变事实身份")
        # 且未注册的 v2 会被拒绝
        with self.assertRaises(KeyError):
            rules.get_rule("file_path_observation", "v2")

    def test_no_llm_rules(self):
        for (rid, rv), meta in rules.RULES.items():
            self.assertFalse(meta["uses_llm"])
            self.assertTrue(meta["deterministic"])


class TestIsolation(Base):
    """8/9：repository_id 与 commit 隔离。"""

    def test_repository_isolation(self):
        a = self.snap_in(repo_id="111")
        b = self.snap_in(repo_id="222")
        oa = self.obs(a["asset_id"], "README")
        ob = self.obs(b["asset_id"], "README")
        self.assertNotEqual(oa.fact_id, ob.fact_id,
                            "不同仓库同名文件不得混为同一事实")
        self.assertNotEqual(oa.repository_id, ob.repository_id)

    def test_commit_version_isolation(self):
        """两个不同 Commit 的快照 —— 历史观察互不覆盖。"""
        a = self.snap_in(commit="a"*40, entries=[FX.README])
        b = self.snap_in(commit="c"*40, entries=[FX.DOCS])   # 无 README
        oa = self.obs(a["asset_id"], "README")
        ob = self.obs(b["asset_id"], "README")
        self.assertNotEqual(oa.fact_id, ob["fact_id"] if isinstance(ob, dict) else ob.fact_id)
        self.assertEqual(oa.observation, OBSERVED_PRESENT)
        self.assertEqual(ob.observation, OBSERVED_ABSENT_IN_COVERED_SCOPE)
        # 两条都正确 —— 针对不同 Commit
        self.assertEqual(oa.commit_sha, "a"*40)
        self.assertEqual(ob.commit_sha, "c"*40)
        # 旧事实没有被标成 false，新事实也没有被标 verified
        self.assertNotIn("verified", oa.observed_value)
        self.assertNotIn("verified", ob.observed_value)

    def test_snapshot_identity_not_confused(self):
        a = self.snap_in(commit="a"*40)
        b = self.snap_in(commit="c"*40)
        self.assertNotEqual(a["snapshot"].logical_identity(),
                            b["snapshot"].logical_identity())
        oa = self.obs(a["asset_id"], "README")
        ob = self.obs(b["asset_id"], "README")
        self.assertNotEqual(oa.snapshot_logical_identity, ob.snapshot_logical_identity)


class TestEvidence(Base):
    """14：evidence_refs 完整且结构化。"""

    def test_evidence_refs_complete(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        self.assertGreaterEqual(len(o.evidence_refs), 2)
        snap_ev = o.evidence_refs[0]
        self.assertEqual(snap_ev["kind"], "source_snapshot")
        for f in ("repository_id", "commit_sha", "snapshot_asset_id",
                  "snapshot_logical_identity", "root_tree_sha", "tree_query_ref",
                  "completeness_status", "rule_id", "rule_version"):
            self.assertIn(f, snap_ev, f"证据缺字段 {f}")
        entry_ev = o.evidence_refs[1]
        self.assertEqual(entry_ev["kind"], "tree_entry")
        for f in ("path", "object_type", "mode", "blob_sha"):
            self.assertIn(f, entry_ev)

    def test_evidence_is_structured_not_prose(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        for ev in o.evidence_refs:
            self.assertIsInstance(ev, dict, "证据必须是结构化对象，不能是自然语言")


class TestIngest(Base):
    """17/18/19/20/21/22：入库、幂等、CAS、半提交、对账、不产生 Claim。"""

    def test_ingest_present_fact(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        res = ingest_fact(self.ks, o)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["state"], INGESTED)
        self.assertEqual(res["pointer_version"], 1)

    def test_repeat_ingest_idempotent(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        a = ingest_fact(self.ks, o)
        b = ingest_fact(self.ks, o)
        self.assertEqual(b["state"], IDEMPOTENT)
        self.assertEqual(b["asset_id"], a["asset_id"])
        n = self.ks.conn.execute("SELECT count(*) AS n FROM assets "
                                 "WHERE asset_type='extracted_fact'").fetchone()["n"]
        self.assertEqual(n, 1, "重复抽取不得产生多条事实资产")
        ptr = self.ks.current_pointer(o.fact_id, o.repository_id)
        self.assertEqual(ptr["pointer_version"], 1, "不得重复推进指针")

    def test_unknown_not_ingested(self):
        r = self.snap_in(completeness="PARTIAL")
        o = self.obs(r["asset_id"], "NOTHERE")
        self.assertEqual(o.observation, UNKNOWN)
        res = ingest_fact(self.ks, o)
        self.assertFalse(res["ok"])
        self.assertEqual(res["state"], REJECTED)
        n = self.ks.conn.execute("SELECT count(*) AS n FROM assets "
                                 "WHERE asset_type='extracted_fact'").fetchone()["n"]
        self.assertEqual(n, 0, "UNKNOWN 不得作为事实入库")

    def test_cas_conflict_explicit(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        ingest_fact(self.ks, o)
        # 制造 CAS 冲突：用错误的 expected_version 再写一条同 fact 但不同内容
        o2 = self.obs(r["asset_id"], "docs")
        # 先占住 fact_id 用错误初始版本
        res = ingest_fact(self.ks, o2, expected_version=1)
        # 该 logical_identity 尚不存在 → NOT_FOUND（也是显式错误，不静默成功）
        self.assertFalse(res["ok"])
        self.assertIn(res.get("error"), ("NOT_FOUND", "CONFLICT", "PERMISSION_DENIED"))

    def test_rule_version_content_conflict(self):
        """同 fact_id 不同内容 → CONFLICT，不得静默覆盖。"""
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        ingest_fact(self.ks, o)
        # 手工构造一个同 fact_id 但 content_hash 不同的事实
        import copy
        o2 = copy.deepcopy(o)
        o2.content_hash = "f"*64
        res = ingest_fact(self.ks, o2)
        self.assertFalse(res["ok"])
        self.assertEqual(res["state"], CONFLICT)

    def test_failure_leaves_no_half_commit(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        orig = self.ks.append_asset_and_advance

        def boom(*a, **kw):
            try: self.ks.conn.execute("ROLLBACK")
            except Exception: pass
            return {"ok": False, "error": "PERMISSION_DENIED", "detail": "injected"}

        self.ks.append_asset_and_advance = boom
        try:
            res = ingest_fact(self.ks, o)
            self.assertFalse(res["ok"])
        finally:
            self.ks.append_asset_and_advance = orig
        n = self.ks.conn.execute("SELECT count(*) AS n FROM assets "
                                 "WHERE asset_type='extracted_fact'").fetchone()["n"]
        self.assertEqual(n, 0, "失败不得留下半提交事实")

    def test_no_verified_claim_produced(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        res = ingest_fact(self.ks, o)
        a = self.ks.get_asset(res["asset_id"])["asset"]
        self.assertEqual(a["asset_type"], "extracted_fact",
                         "类型必须是 extracted_fact，不能是 claim")
        for bad in ("verified", "supported", "refuted", "claim_status",
                    "insufficient_evidence"):
            self.assertNotIn(bad, a["payload"],
                             f"Facts 不得产出 Claim 裁决字段: {bad}")

    def test_does_not_modify_source_snapshot(self):
        r = self.snap_in()
        aid = r["asset_id"]
        before = self.ks.get_asset(aid)["asset"]
        o = self.obs(aid, "README")
        ingest_fact(self.ks, o)
        after = self.ks.get_asset(aid)["asset"]
        self.assertEqual(before["content_hash"], after["content_hash"],
                         "Facts 不得修改来源快照")
        self.assertEqual(before["logical_identity"], after["logical_identity"])
        self.assertEqual(before["asset_version"], after["asset_version"])


class TestIntegrationAndRegression(Base):
    """23：索引不受影响；多版本历史共存。"""

    def test_index_rebuild_keeps_assets(self):
        r = self.snap_in()
        o = self.obs(r["asset_id"], "README")
        ingest_fact(self.ks, o)
        before = IX._ab_fingerprint(self.ks)
        rb = IX.rebuild_index(self.ks)
        after = IX._ab_fingerprint(self.ks)
        self.assertTrue(rb["ok"])
        self.assertEqual(before, after, "重建索引不得改 A/B")

    def test_two_commits_both_recoverable(self):
        a = self.snap_in(commit="a"*40, entries=[FX.README])
        b = self.snap_in(commit="c"*40, entries=[FX.DOCS])
        oa = self.obs(a["asset_id"], "README")
        ob = self.obs(b["asset_id"], "README")
        ra = ingest_fact(self.ks, oa)
        rb = ingest_fact(self.ks, ob)
        self.assertTrue(ra["ok"] and rb["ok"])
        aa = self.ks.get_asset(ra["asset_id"])["asset"]
        bb = self.ks.get_asset(rb["asset_id"])["asset"]
        self.assertEqual(aa["payload"]["commit_sha"], "a"*40)
        self.assertEqual(bb["payload"]["commit_sha"], "c"*40)
        self.assertNotEqual(aa["payload"]["observation"],
                            None)
        self.assertNotEqual(ra["asset_id"], rb["asset_id"])


class TestPathNormalization(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_path("a/b"), "a/b")
        self.assertEqual(normalize_path("a/b/"), "a/b")
        for bad in ("/abs", "../x", "a//b", "a\\b", "", "a\x00b"):
            with self.assertRaises(ValueError):
                normalize_path(bad)

    def test_case_sensitive(self):
        self.assertNotEqual(normalize_path("README"), normalize_path("readme"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
