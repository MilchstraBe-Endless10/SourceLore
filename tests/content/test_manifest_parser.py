#!/usr/bin/env python3
"""Manifest 解析：真解析而非正则；声明≠安装；脚本只读不执行。"""
import sys, unittest, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"content"))
import sfx
from parsers import package_json as PJ
from parsers import pyproject_toml as PT

PKG = json.dumps({
    "name": "demo-app", "version": "1.2.3", "private": True,
    "dependencies": {"left-pad": "^1.0.0", "lodash": "~4.17.0"},
    "devDependencies": {"jest": "^29.0.0"},
    "scripts": {"test": "jest", "start": "node index.js"},
}, indent=2)

BAD_JSON = '{"name": "x", "dependencies": {"a": "1.0",}}'
NOT_OBJ = '[1,2,3]'

PYPROJECT = '''[project]
name = "demo"
version = "0.1.0"
dependencies = ["requests>=2.0", "click"]

[tool.pytest.ini_options]
testpaths = ["tests"]
'''


class TestPackageJson(unittest.TestCase):
    def test_valid(self):
        ok, data, _, _ = PJ.parse(PKG); self.assertTrue(ok)
        self.assertEqual(data["name"], "demo-app")

    def test_invalid_json(self):
        ok, _, code, msg = PJ.parse(BAD_JSON)
        self.assertFalse(ok)
        self.assertEqual(code, "MANIFEST_INVALID_JSON")
        self.assertIn("line", msg)

    def test_not_object(self):
        ok, _, code, _ = PJ.parse(NOT_OBJ)
        self.assertFalse(ok); self.assertEqual(code, "MANIFEST_NOT_OBJECT")

    def test_dependencies_extracted(self):
        ok, data, _, _ = PJ.parse(PKG)
        facts = PJ.extract(data, PKG)
        deps = [f for f in facts if f["kind"] == "dependency"]
        names = {f["dependency"] for f in deps}
        self.assertEqual(names, {"left-pad", "lodash", "jest"})
        fields = {f["field"] for f in deps}
        self.assertEqual(fields, {"dependencies", "devDependencies"})

    def test_scripts_read_only(self):
        """★ 脚本字段只被读取，绝不执行。"""
        ok, data, _, _ = PJ.parse(PKG)
        facts = PJ.extract(data, PKG)
        script_facts = [f for f in facts if f["kind"] == "script_declared"]
        self.assertEqual({f["script_name"] for f in script_facts}, {"test", "start"})
        import content_extractor as EX
        src = (ROOT/"src"/"content"/"parsers"/"package_json.py").read_text(encoding="utf-8")
        for bad in ("subprocess", "os.system", "exec(", "eval("):
            self.assertNotIn(bad, src, f"不得出现 {bad}")

    def test_judgement_warnings(self):
        import content_extractor as EX
        sem = EX.CLAIM_SEMANTICS[EX.F_MANIFEST_DEP]
        self.assertIn("≠ 已安装", sem["warning"])


class TestPyproject(unittest.TestCase):
    def test_available_flag(self):
        self.assertIsInstance(PT.available(), bool)

    def test_valid_or_explicit_unavailable(self):
        ok, data, code, msg = PT.parse(PYPROJECT)
        if PT.available():
            self.assertTrue(ok)
            facts = PT.extract(data, PYPROJECT)
            names = {f.get("dependency") for f in facts if f["kind"] == "dependency"}
            self.assertIn("requests", names)
        else:
            self.assertEqual(code, "PARSER_UNAVAILABLE")
            self.assertIn("拒绝用正则猜测", msg)

    def test_invalid_toml(self):
        if not PT.available():
            self.skipTest("no tomllib")
        ok, _, code, _ = PT.parse("[[[bad")
        self.assertFalse(ok)

    def test_no_regex_fallback(self):
        src = (ROOT/"src"/"content"/"parsers"/"pyproject_toml.py").read_text(encoding="utf-8")
        self.assertNotIn("re.match", src)
        self.assertIn("tomllib", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
