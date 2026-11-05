#!/usr/bin/env python3
"""E. Harness 实际调用：记录真实子进程调用证据。

★ 这里是"CLI 可被外部进程真实调用"的证据；
  Agent(LLM) 是否真的在对话中调用了它，由 f2p5a_e2e.py 另行记录。
"""
import sys, unittest, subprocess, json, tempfile, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx

INSTALLED = Path.home()/".agents"/"skills"/"sourcelore"/"scripts"/"sourcelore.py"


def run_cli(*args, root=None, cwd="/tmp"):
    cmd = [sys.executable, str(INSTALLED)]
    if root: cmd += ["--data-root", root]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=90, cwd=cwd)


class TestInvocation(unittest.TestCase):
    def test_install_path_used(self):
        self.assertTrue(INSTALLED.exists(), "未安装")

    def test_status_structured(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_cli("status", root=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertTrue(out["ok"])
            self.assertEqual(out["db_exists"], False)

    def test_stdout_json_stderr_separate(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_cli("repositories", root=d)
            self.assertEqual(r.returncode, 3)
            body = json.loads(r.stdout)          # stdout 必须是合法 JSON
            self.assertFalse(body["ok"])
            self.assertIn("错误", r.stderr)       # stderr 是人类可读摘要

    def test_skill_md_discoverable_format(self):
        p = INSTALLED.parents[1]/"SKILL.md"
        t = p.read_text(encoding="utf-8")
        self.assertTrue(t.startswith("---"), "frontmatter 缺失")
        self.assertIn("name: sourcelore", t)
        self.assertIn("description:", t)

        # 只有两个键的 frontmatter
        head = t.split("---")[1]
        keys = [ln.split(":")[0] for ln in head.splitlines()
                if ln and not ln.startswith(" ") and ":" in ln]
        self.assertEqual(sorted(keys), ["description", "name"])

    def test_repeat_query_reuses_knowledge(self):
        """重复调用不应重新采集 —— query 路径不含采集代码。"""
        src = (ROOT/"src"/"skill_interface"/"query.py").read_text(encoding="utf-8")
        self.assertNotIn("analyze(", src)
        self.assertNotIn("GitHubClient", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
