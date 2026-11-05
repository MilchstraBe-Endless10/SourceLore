#!/usr/bin/env python3
"""B/D. GitHub Token 可选支持 + 安装同步：T-10..T-16、T-33..T-38。"""
import sys, unittest, os, json, subprocess, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx
for p in ("collector","storage","skill_interface"):
    if str(ROOT/"src"/p) not in sys.path:
        sys.path.insert(0, str(ROOT/"src"/p))

ANT = str(ROOT/"src"/"skill_interface"/"analyze.py")


class TestTokenSupport(unittest.TestCase):
    def test_optional_env_only(self):
        src = Path(ANT).read_text(encoding="utf-8")
        self.assertIn('os.environ.get("GITHUB_TOKEN")', src,
                      "只从进程环境读 token")
        # 不得从文件/CLI/配置读
        for bad in ("open(", "yaml", "json.load", "argv"):
            idx = src.find(bad)
            if idx > 0 and "GITHUB_TOKEN" in src[max(0,idx-200):idx+200]:
                self.fail(f"token 不应经 {bad} 读取")

    def test_no_second_client(self):
        src = Path(ANT).read_text(encoding="utf-8")
        self.assertEqual(src.count("GitHubClient("), 1,
                         "只能有一处 GitHubClient 实例化")

    def test_token_not_printed(self):
        src = Path(ANT).read_text(encoding="utf-8")
        for leak in ('print(_tok', 'print(token', '"token": _tok',
                     'json.dumps(_tok'):
            self.assertNotIn(leak, src, "不得打印 token")

    def test_no_token_still_runs(self):
        """★ 无 Token 仍可运行（离线路径即可验证不依赖 token）。"""
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(sfx.CLI),
                                "--data-root", d, "status"],
                               capture_output=True, text=True, timeout=60, cwd="/tmp")
            self.assertEqual(r.returncode, 0)
            self.assertTrue(json.loads(r.stdout)["ok"])

    def test_token_not_in_assets(self):
        """★ Token 不得写入知识资产。"""
        for f in (ROOT/"src"/"skill_interface").glob("*.py"):
            t = f.read_text(encoding="utf-8")
            if "_tok" in t:
                for bad in ("payload", "evidence_refs", "tree_entries"):
                    if bad in t.split("_tok")[0][-300:]:
                        self.fail(f"{f.name} 可疑地把 token 放进 {bad}")


class TestRateLimitFastFail(unittest.TestCase):
    def test_no_retry(self):
        src = Path(ANT).read_text(encoding="utf-8")
        self.assertIn('"max_retries": 0', src)
        self.assertIn('"max_retry_after": 0', src)

    def test_error_exposes_reset(self):
        src = Path(ANT).read_text(encoding="utf-8")
        self.assertIn("retry_after", src)
        self.assertIn("不会绕过限流", src)


class TestInstallSync(unittest.TestCase):
    INST = Path.home()/".agents"/"skills"/"sourcelore"
    SRC = ROOT/"skill"/"sourcelore"

    def test_installed_exists(self):
        self.assertTrue((self.INST/"SKILL.md").exists())

    def test_hashes_match(self):
        """★ 安装版本必须与仓库源一致。"""
        diffs = []
        for f in self.SRC.rglob("*"):
            if f.is_file():
                rel = f.relative_to(self.SRC)
                target = self.INST/rel
                if not target.exists():
                    diffs.append(f"{rel}: 缺失")
                elif f.read_bytes() != target.read_bytes():
                    diffs.append(f"{rel}: 内容不同")
        self.assertEqual(diffs, [], f"安装与源不一致：{diffs}")

    def test_skill_md_valid(self):
        t = (self.INST/"SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(t.startswith("---"))
        self.assertIn("name: sourcelore", t)

    def test_entry_runs_outside_cwd(self):
        r = subprocess.run([sys.executable, str(self.INST/"scripts"/"sourcelore.py"),
                            "--version"], capture_output=True, text=True,
                           timeout=60, cwd=tempfile.gettempdir())
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_other_skills_intact(self):
        base = self.INST.parent
        self.assertTrue((base/"omarchy"/"SKILL.md").exists())
        self.assertTrue((base/"diagnose-crash").is_dir())

    def test_no_temp_dependency(self):
        marker = self.INST/".sourcelore-skill.json"
        self.assertTrue(marker.exists(), "marker 必须存在以定位工程根")
        j = json.loads(marker.read_text(encoding="utf-8"))
        self.assertNotIn("/tmp/", j.get("project_root", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
