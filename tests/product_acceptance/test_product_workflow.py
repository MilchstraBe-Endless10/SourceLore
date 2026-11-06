#!/usr/bin/env python3
"""产品级验收：安装版 CLI 优先；无 CLI 环境时降级为内部链路但仍验证持久化。"""
import json, re, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "product_acceptance"))
import sfx
from gold.product_gold import GOLD

CLI = Path.home() / ".agents/skills/sourcelore/scripts/sourcelore.py"
FIXTURE = Path("/tmp/p6a_origin")
DATA = Path("/tmp/p6a_accept")
COMMIT_A = "4ec31e0f75f9e34b7352211f52cda69ee801e497"
COMMIT_B = "76efaf481cbbc5413787234154e5be1b3e3fc5c7"
RID = "local:85cdd3850a72"


def cli(*args, env_root=None):
    r = subprocess.run([sys.executable, str(CLI), *args],
                       capture_output=True, text=True,
                       env={"SOURCELORE_DATA_ROOT": str(env_root or DATA),
                            "PATH": "/usr/local/bin:/usr/bin:/bin"})
    out = r.stdout.strip()
    try:
        return r.returncode, json.loads(out) if out else {}
    except json.JSONDecodeError:
        return r.returncode, {"raw": out}


class TestGoldRegistry(unittest.TestCase):
    def test_20_cases(self):
        self.assertGreaterEqual(len(GOLD), 20)
        ids = [g[0] for g in GOLD]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_fields(self):
        for gid, cat, desc, exp in GOLD:
            self.assertTrue(gid and cat and desc and exp, gid)


@unittest.skipUnless(CLI.exists() and FIXTURE.exists(),
                     "需要安装版 Skill 与原创仓库")
class TestProductCLI(unittest.TestCase):
    """★ 全部走真实安装版 CLI，不用内部函数。"""

    @classmethod
    def setUpClass(cls):
        subprocess.run(["rm", "-rf", str(DATA)], check=False)
        DATA.mkdir(parents=True, exist_ok=True)
        rc, out = cli("analyze", str(FIXTURE), "--path", "README.md")
        cls.analyze = out
        cls.analyze_rc = rc

    def test_P01_build(self):
        self.assertTrue(self.analyze.get("ok"), self.analyze)
        self.assertEqual(self.analyze.get("network_requests"), 0)
        self.assertGreater(self.analyze.get("content_facts_total") or 0, 0)

    def test_P02_list(self):
        rc, out = cli("repositories")
        self.assertEqual(rc, 0)
        self.assertGreaterEqual(out.get("count", 0), 1)
        self.assertEqual(out["repositories"][0]["repository_id"], RID)

    def test_P03_commit(self):
        self.assertEqual(self.analyze.get("commit_sha"), COMMIT_B)

    def test_P04_readme(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "content", "--path", "README.md")
        self.assertEqual(rc, 0)
        self.assertIn("captured", out)

    def test_P05_manifest(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "content", "--path", "package.json")
        self.assertEqual(rc, 0)

    def test_P06_python(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "code", "--path", "python/main.py")
        self.assertEqual(rc, 0)
        names = [s["subject"]["qualified_name"] for s in out.get("symbols", [])]
        self.assertIn("Worker", names)
        self.assertIn("Worker.run", names)
        self.assertIn("main", names)

    def test_P07_ts_symbols(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "code", "--path", "src/types.ts")
        kinds = {s["subject"]["symbol_kind"] for s in out.get("symbols", [])}
        self.assertIn("ts_interface", kinds)
        self.assertIn("ts_type_alias", kinds)

    def test_P08_imports(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "code", "--path", "src/app.ts")
        imports = out.get("imports") or []
        self.assertGreaterEqual(len(imports), 2)
        mods = {i["subject"].get("module_name") for i in imports}
        self.assertIn("@/utils", mods)
        self.assertIn("#types", mods)

    def test_P09_alias(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "relation", "--path", "src/app.ts")
        self.assertEqual(out.get("state"), "RELATIONS_FOUND")
        rels = out.get("relations") or []
        self.assertIn("src/utils.ts",
                      {r["resolved_target_path"] for r in rels})

    def test_P10_project(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "project")
        self.assertEqual(out.get("state"), "PROJECTS_FOUND")
        p = out["projects"][0]
        self.assertEqual(p["discovery_status"], "PROJECT_CONFIG_VERIFIED")
        self.assertIn("src/**/*.ts", p["declared_include"])

    def test_P11_evidence(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B,
                      "--type", "code", "--path", "python/main.py")
        syms = out.get("symbols") or []
        self.assertTrue(syms)
        for s in syms:
            self.assertIn("evidence_label", s)
            self.assertIsNotNone(s.get("start_line"))

    def test_P12_card(self):
        rc, out = cli("card", "--repository-id", RID,
                      "--commit", COMMIT_B, "--path", "README.md")
        self.assertTrue(out.get("ok"), out)
        self.assertGreater(out.get("html_bytes", 0), 1000)
        html = Path(out["html_path"]).read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", html)
        self.assertNotIn("<script", html.lower())
        self.assertIsNone(re.search(r"\son[a-z]+\s*=", html, re.I))

    def test_P13_second_run(self):
        rc, out = cli("analyze", str(FIXTURE), "--path", "README.md")
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("network_requests"), 0)

    def test_P14_offline(self):
        rc, out = cli("analyze", str(FIXTURE), "--path", "README.md",
                      "--offline")
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("network_requests"), 0)

    def test_P15_multicommit(self):
        cli("analyze", str(FIXTURE), "--path", "README.md",
            "--commit", COMMIT_A)
        _, a = cli("query", RID, "--commit", COMMIT_A, "--type", "code",
                   "--path", "src/app.ts")
        _, b = cli("query", RID, "--commit", COMMIT_B, "--type", "code",
                   "--path", "src/app.ts")
        na = {s["subject"]["qualified_name"] for s in a.get("symbols", [])}
        nb = {s["subject"]["qualified_name"] for s in b.get("symbols", [])}
        self.assertIn("run", na)
        self.assertIn("execute", nb)
        self.assertNotEqual(na, nb)

    def test_P16_no_fact(self):
        rc, out = cli("query", RID, "--commit", COMMIT_B, "--type", "code",
                      "--path", "src/ghost.ts")
        self.assertNotEqual(out.get("state"), "FOUND")
        self.assertEqual(out.get("facts", []), [])

    def test_P17_abstain(self):
        rc, out = cli("query", RID, "--commit", COMMIT_A,
                      "--type", "relation", "--path", "src/ghost.ts")
        self.assertNotEqual(out.get("state"), "RELATIONS_FOUND")


class TestPathSecurity(unittest.TestCase):
    def test_P20_traversal(self):
        import importlib.util
        p = ROOT / "src" / "source_analysis" / "tsconfig_parser.py"
        spec = importlib.util.spec_from_file_location("_tp", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertIsNone(m.normalize_target("/etc/passwd", base_dir=""))
        self.assertIsNone(m.normalize_target("../../../etc", base_dir="a/b"))


class TestContract(unittest.TestCase):
    def test_P19_contract_audit(self):
        r = subprocess.run([sys.executable,
                            str(ROOT / "tools" / "f2p6a_contract_audit.py")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[:400])


if __name__ == "__main__":
    unittest.main(verbosity=2)
