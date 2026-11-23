#!/usr/bin/env python3
"""安装版 CLI 真实进程测试（离线，零网络）。"""
import subprocess, sys, json, os, unittest
from pathlib import Path

SKILL = Path.home() / ".agents" / "skills" / "sourcelore" / "scripts" / "sourcelore.py"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import installed_cli_fixture as FX

COMMIT = FX.COMMIT
# ★ 测试隔离：不再使用易失的 /tmp/p6b_real（早期人工验收残留，清理后无 kb.db）。
#   每个测试类在自己的 tempfile data_root 里用原创夹具建最小知识库。
DATA = None  # 由 setUpClass 赋值


def run(*args, root=None):
    env = dict(os.environ)
    env["SOURCELORE_DATA_ROOT"] = str(root or DATA)
    # 子进程不能继承宿主可能设置的工程根/数据根覆盖，否则夹具隔离失效
    env.pop("SOURCELORE_PROJECT_ROOT", None)
    r = subprocess.run([sys.executable, str(SKILL), *args],
                       capture_output=True, text=True, env=env, timeout=120)
    try:
        payload = json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        payload = {"_raw": r.stdout[:400]}
    return r.returncode, payload, r.stderr


class TestInstalled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 每个测试类独占一个 tempfile data_root，原创夹具建库；绝不复用真实库
        cls._fixture = FX.FixtureRoot()
        global DATA
        DATA = cls._fixture.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._fixture.__exit__(None, None, None)

    def test_skill_exists(self):
        self.assertTrue(SKILL.exists(), "必须从安装目录运行，不能用内部函数")

    def test_query_readonly_zero_net(self):
        rc, p, _ = run("query", "24313173", "--commit", COMMIT,
                       "--type", "content", "--path", "README.md")
        self.assertEqual(rc, 0)
        self.assertEqual(p.get("state"), "SUPPORTED")
        self.assertEqual(p.get("network_requests"), 0, "只读查询必须零网络")

    def test_offline_analyze_zero_net(self):
        rc, p, _ = run("analyze", "https://github.com/jonschlinkert/is-number",
                       "--commit", COMMIT, "--path", "README.md",
                       "--include-content", "--license-known",
                       "--content-path", "README.md", "--offline")
        self.assertEqual(rc, 0, p)
        self.assertTrue(p.get("ok"), p)
        c = p.get("content") or {}
        self.assertEqual(c.get("network_requests"), 0, "离线不得访问 GitHub")

    def test_plan_readonly(self):
        rc, p, _ = run("analyze", "https://github.com/jonschlinkert/is-number",
                       "--commit", COMMIT, "--plan")
        self.assertEqual(rc, 0, p)
        self.assertTrue(p.get("read_only"), p)
        self.assertEqual(p.get("network_requests", 0), 0)

    def test_card(self):
        rc, p, _ = run("card", "--repository-id", "24313173",
                       "--commit", COMMIT, "--path", "README.md")
        self.assertEqual(rc, 0, p)
        self.assertTrue(p.get("ok"), p)
        self.assertGreater(p.get("html_bytes", 0), 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
