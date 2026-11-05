#!/usr/bin/env python3
"""Gold 评估：25 例，统计准确率/错误肯定/错误否定/正确 abstention。"""
import sys, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content"))
import sfx
import content_extractor as EX
import content_models as CM
from gold_content import GOLD, case_bytes, SHA_A, REPO


def build_one(path, content, idx=0):
    """★ Git 语义：同一 Commit 同一路径只有一个 blob。
    因此每个用例用**独立快照**，不能把同路径的多个用例塞进一个快照
    （那样 extractor 按 path 查找必然互相覆盖）。"""
    b = case_bytes(content)
    oid = f"{idx:040d}"
    return {"repository_id": REPO, "commit_sha": SHA_A,
            "completeness_status": "COMPLETE",
            "tree_entries": [{"path": path, "sha": oid, "size": len(b),
                              "type": "blob", "mode": "100644"}],
            "blob_refs": [{"path": path, "blob_sha": oid, "size": len(b)}],
            "blob_contents": {oid: b}}


class TestGold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.per_case = {}
        cls.all_obs = []
        for i, (gid, path, content, exp) in enumerate(GOLD):
            snap = build_one(path, content, idx=i)
            got = EX.extract_snapshot(
                snapshot_payload=snap, repository_id=REPO, commit_sha=SHA_A,
                candidate_paths=[path], source_snapshot_id=f"SL-A-G{gid}")
            cls.per_case[gid] = (path, got)
            cls.all_obs.extend(got["observations"])
        cls.snap = build_one(GOLD[0][1], GOLD[0][2])
        cls.out = EX.extract_snapshot(
            snapshot_payload=cls.snap, repository_id=REPO, commit_sha=SHA_A,
            candidate_paths=[GOLD[0][1]], source_snapshot_id="SL-A-G")
        # ★ 多个用例共用同一路径（README.md 出现多次）——
        #   不能按路径聚合，否则计数与断言都会错位。按顺序索引。
        cls.by_path = {}
        for o in cls.out["observations"]:
            cls.by_path.setdefault(o["file_path"], []).append(o)
        cls.skip_by_path = {}
        for s in cls.out["skipped"]:
            cls.skip_by_path.setdefault(s["file_path"], []).append(s)
        # observed_paths 会去重，故用「已产出结果的文件路径数」判定覆盖
        cls.covered_paths = set(cls.by_path) | set(cls.skip_by_path)
        cls.covered_cases = sum(
            len(cls.by_path.get(g[1], [])) + len(cls.skip_by_path.get(g[1], []))
            for g in [GOLD[0]])

    def _facts_gid(self, gid):
        return self.per_case[gid][1]["observations"][0]["facts"] \
            if self.per_case[gid][1]["observations"] else []

    def _skip_gid(self, gid):
        return {s["code"] for s in self.per_case[gid][1]["skipped"]}

    def test_all_25_cases_produced_a_result(self):
        self.assertEqual(len(self.per_case), len(GOLD))
        for gid, (path, got) in self.per_case.items():
            self.assertTrue(got["observations"] or got["skipped"],
                            f"{gid} 既无观察也无跳过")

    def test_g01_headings(self):
        heads = [(f["subject"]["level"], f["subject"]["title"])
                 for f in self._facts_gid("G01")
                 if f["rule_id"] == EX.F_README_HEADING]
        self.assertEqual(set(GOLD[0][3]["headings"]).issubset(set(heads)), True,
                         f"缺：{set(GOLD[0][3]['headings'])-set(heads)}")

    def test_g03_no_label_leak(self):
        """★ 阻断级：注入文本不得进入**证据描述字段**（label）。

        注意区分：`facts[].subject.title` 是**被观察的知识对象**（标题本身），
        它可以含原文——那是观察结果，不是证据描述。真正要守住的是
        `evidence_ranges[].label` 这类描述性字段不得回显不可信原文。
        """
        got = self.per_case["G03"][1]
        ranges = got["observations"][0]["observation"]["evidence_ranges"]
        for r in ranges:
            low = str(r.get("label", "")).lower()
            self.assertNotIn("ignore previous instructions", low)
            self.assertNotIn("admin mode", low)
        # 断言 label 是结构化描述而非原文
        self.assertTrue(all(str(r["label"]).startswith(("heading:", "readme_heading@"))
                            for r in ranges), [r["label"] for r in ranges])

    def test_g03_no_execution_side_effect(self):
        """★ 注入文本只被记录为结构，不产生任何"已验证/已执行"标记。"""
        got = self.per_case["G03"][1]
        obs = got["observations"][0]["observation"]
        self.assertEqual(obs["extraction_status"], "EXTRACTED")
        rules = {f["rule_id"] for f in got["observations"][0]["facts"]}
        self.assertEqual(rules, {EX.F_README_HEADING})

    def test_g04_no_secret_leak(self):
        blob = json.dumps(self.per_case["G04"][1], ensure_ascii=False)
        self.assertNotIn("sk-live", blob)
        self.assertNotIn("hunter2", blob)

    def test_g11_deps(self):
        deps = {f["subject"].get("dependency") for f in self._facts_gid("G11")
                if f["rule_id"] == EX.F_MANIFEST_DEP}
        self.assertEqual(deps, {"lodash", "axios", "vitest"})

    def test_g12_g13_parse_failed(self):
        for gid in ("G12", "G13"):
            self.assertIn(CM.C_PARSE_FAILED, self._skip_gid(gid), gid)

    def test_g20_too_large(self):
        self.assertIn("BLOB_TOO_LARGE", self._skip_gid("G20"),
                      f"实际={self._skip_gid('G20')}")

    def test_g21_bad_encoding(self):
        self.assertIn(CM.C_BAD_ENCODING, self._skip_gid("G21"))

    def test_g22_binary(self):
        self.assertIn(CM.C_BINARY, self._skip_gid("G22"))

    def test_g18_g19_same_blob_distinct_case(self):
        """同一内容出现在不同路径 → 两个用例各自独立观察。"""
        for gid in ("G18", "G19"):
            self.assertTrue(self.per_case[gid][1]["observations"], gid)

    def test_idempotent(self):
        gid = "G25"
        path, content, _ = GOLD[24][1], GOLD[24][2], None
        snap = build_one(path, content, idx=24)
        a = EX.extract_snapshot(snapshot_payload=snap, repository_id=REPO,
                                commit_sha=SHA_A, candidate_paths=[path],
                                source_snapshot_id="x")
        b = EX.extract_snapshot(snapshot_payload=snap, repository_id=REPO,
                                commit_sha=SHA_A, candidate_paths=[path],
                                source_snapshot_id="x")
        self.assertEqual(
            [o["observation"]["observation_id"] for o in a["observations"]],
            [o["observation"]["observation_id"] for o in b["observations"]])

    def test_no_wrong_refutation(self):
        for o in self.all_obs:
            for f in o["facts"]:
                self.assertNotEqual(f.get("verdict"), "refuted")

    def test_synthetic_provenance_labeled(self):
        for o in self.all_obs:
            self.assertEqual(o["observation"]["provenance_level"],
                             "SYNTHETIC_FIXTURE")

    def test_metrics(self):
        parsed = sum(1 for g, (p, r) in self.per_case.items() if r["observations"])
        skipped = sum(1 for g, (p, r) in self.per_case.items() if r["skipped"])
        self.assertGreaterEqual(parsed, 18, f"解析成功 {parsed}")
        self.assertGreaterEqual(skipped, 5, f"明确跳过 {skipped}")
        self.assertEqual(parsed + skipped, len(GOLD))


if __name__ == "__main__":
    unittest.main(verbosity=2)
