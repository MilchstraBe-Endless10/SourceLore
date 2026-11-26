#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 面向用户问答层测试：意图分流 + 内容优先 + 只读零网络 + 审计后置。"""
import os
import sys
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "src" / "skill_interface"
sys.path.insert(0, str(SKILL_DIR))
for _p in ("views", "storage", "skill_interface"):
    _sp = str(ROOT / "src" / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

import paths  # noqa: E402
paths.ensure_import_path()

LAUNCHER = Path.home() / ".agents" / "skills" / "sourcelore" / "scripts" / "sourcelore.py"
RIDS = {
    "is-number": "24313173",
    "is-plain-obj": "38923193",
    "preact": "42283287",
}


def _run_answer(rid, question):
    env = dict(os.environ)
    r = subprocess.run(
        [sys.executable, str(LAUNCHER), "answer", rid, question],
        capture_output=True, text=True, env=env, timeout=120)
    try:
        return r.returncode, json.loads(r.stdout)
    except Exception:
        return r.returncode, {"_raw": r.stdout[:300], "_err": r.stderr[:300]}


class TestDetectIntent(unittest.TestCase):
    def test_intents(self):
        import knowledge_answer as KA
        cases = {
            "介绍这个项目": "introduce",
            "这个项目是做什么的": "introduce",
            "怎么使用": "usage",
            "安装方法": "usage",
            "API 示例": "usage",
            "分析架构": "architecture",
            "模块依赖": "architecture",
            "核心函数源码": "code",
            "为什么可信": "evidence",
            "证据链": "evidence",
            "检查知识库完整性": "completeness",
            "随便一句话": "introduce",
        }
        for q, want in cases.items():
            self.assertEqual(KA.detect_intent(q), want, q)


class TestAnswerContent(unittest.TestCase):
    def _assert_common(self, d):
        self.assertTrue(d.get("ok"), d)
        self.assertEqual(d.get("network_requests"), 0)
        self.assertEqual(d.get("wrote_assets"), 0)
        self.assertFalse(d.get("distribution_allowed", True))
        self.assertTrue(isinstance(d.get("blocks"), list) and d["blocks"], d)

    def test_introduce_has_purpose(self):
        rc, d = _run_answer(RIDS["is-number"], "介绍这个项目")
        self.assertEqual(rc, 0, d)
        self._assert_common(d)
        self.assertEqual(d.get("base_intent"), "introduce")
        heads = [b["heading"] for b in d["blocks"]]
        self.assertIn("项目用途", heads)
        purpose = [b for b in d["blocks"] if b["heading"] == "项目用途"][0]
        self.assertIn("finite number", purpose["body"])
        self.assertTrue(purpose.get("refs"))

    def test_introduce_core_function_with_source(self):
        rc, d = _run_answer(RIDS["is-number"], "介绍这个项目")
        self.assertEqual(rc, 0, d)
        core = [b for b in d["blocks"] if "核心实现" in b["heading"]]
        self.assertTrue(core, "核心实现段落应存在")
        body = core[0]["body"]
        self.assertIn("module.exports = function", body)
        self.assertIn("index.js", body)
        self.assertTrue(core[0].get("refs"))

    def test_usage_has_install_and_example(self):
        for name in ("is-number", "is-plain-obj"):
            with self.subTest(repo=name):
                rc, d = _run_answer(RIDS[name], "怎么使用")
                self.assertEqual(rc, 0, d)
                self._assert_common(d)
                self.assertEqual(d.get("base_intent"), "usage")
                heads = " ".join(b["heading"] for b in d["blocks"])
                self.assertIn("Install", heads)
                joined = " ".join(b["body"] for b in d["blocks"])
                self.assertIn("npm", joined)
                self.assertTrue(
                    ("require" in joined) or ("import" in joined),
                    "使用示例应含 require 或 import")

    def test_audit_only_on_evidence(self):
        rc, intro = _run_answer(RIDS["is-number"], "介绍这个项目")
        self.assertIsNone(intro.get("audit"))
        rc, ev = _run_answer(RIDS["is-number"], "为什么这个结论可信")
        self.assertEqual(rc, 0, ev)
        self.assertEqual(ev.get("base_intent"), "evidence")
        self.assertTrue(isinstance(ev.get("audit"), dict))
        self.assertIn("verdict_distribution", ev["audit"])

    def test_audit_uses_current_view_only(self):
        """审计统计必须只含当前视图采纳的 verification（P0 规则18）。"""
        for name, rid in RIDS.items():
            with self.subTest(repo=name):
                rc, d = _run_answer(rid, "为什么这个结论可信")
                self.assertEqual(rc, 0, d)
                a = d["audit"]
                self.assertIn("current_verification_count", a)
                self.assertLessEqual(a["current_verification_count"],
                                     a["verification_count"])
                self.assertEqual(a["current_verification_count"],
                                 sum(a["verdict_distribution"].values()))

    def test_all_three_repos_answer(self):
        for name, rid in RIDS.items():
            with self.subTest(repo=name):
                rc, d = _run_answer(rid, "介绍这个项目")
                self.assertEqual(rc, 0, d)
                self._assert_common(d)
                self.assertIn("项目用途", [b["heading"] for b in d["blocks"]])

    def test_unknown_repo(self):
        rc, d = _run_answer("00000000", "介绍这个项目")
        self.assertFalse(d.get("ok"))
        self.assertEqual(d.get("error"), "REPOSITORY_NOT_REGISTERED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
