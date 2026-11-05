#!/usr/bin/env python3
"""A. Skill 基础：CLI 行为、退出码、错误拒绝。"""
import sys, subprocess, unittest, json, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx

CLI = str(sfx.CLI)

def run(*args, root=None):
    cmd = [sys.executable, CLI]
    if root: cmd += ["--data-root", root]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)

class TestCLI(unittest.TestCase):
    def test_version(self):
        r = run("--version"); self.assertEqual(r.returncode, 0)
        self.assertIn("skill_version", json.loads(r.stdout))

    def test_help(self):
        r = run("--help"); self.assertEqual(r.returncode, 0)
        self.assertIn("analyze", r.stdout)

    def test_usage_error_exit_2(self):
        r = run("bogus"); self.assertEqual(r.returncode, 2)

    def test_missing_arg_exit_2(self):
        r = run("inspect"); self.assertEqual(r.returncode, 2)

    def test_db_missing_exit_3(self):
        with tempfile.TemporaryDirectory() as d:
            r = run("repositories", root=d)
            self.assertEqual(r.returncode, 3)
            self.assertFalse(json.loads(r.stdout)["ok"])

    def test_status_no_creds(self):
        with tempfile.TemporaryDirectory() as d:
            r = run("status", root=d)
            self.assertEqual(r.returncode, 0)
            out = json.loads(r.stdout)
            blob = json.dumps(out).lower()
            for bad in ("api_key","apikey","token","secret","password"):
                self.assertNotIn(bad, blob, f"status 不得输出 {bad}")

    def test_db_guard_rejects_repo_path(self):
        sys.path.insert(0, str(ROOT/"src"/"skill_interface"))
        import paths
        with self.assertRaises(RuntimeError):
            paths.guard_inside_project_db(ROOT/"kb.db")

class TestInstall(unittest.TestCase):
    def test_installed_skill_exists(self):
        p = Path.home()/".agents"/"skills"/"sourcelore"/"SKILL.md"
        self.assertTrue(p.exists(), "Skill 未安装")
        t = p.read_text(encoding="utf-8")
        self.assertIn("name: sourcelore", t)
        self.assertIn("description:", t)
        for f in ("scripts/sourcelore.py","references/commands.md",
                  "references/knowledge-schema.md","references/safety.md"):
            self.assertTrue((p.parent/f).exists(), f)

    def test_cli_runs_from_install_dir(self):
        inst = Path.home()/".agents"/"skills"/"sourcelore"/"scripts"/"sourcelore.py"
        r = subprocess.run([sys.executable, str(inst), "--version"],
                           capture_output=True, text=True, timeout=60, cwd="/tmp")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("skill_version", r.stdout)

    def test_other_skills_intact(self):
        base = Path.home()/".agents"/"skills"
        self.assertTrue((base/"omarchy"/"SKILL.md").exists())
        self.assertTrue((base/"diagnose-crash").is_dir())

if __name__ == "__main__":
    unittest.main(verbosity=2)
