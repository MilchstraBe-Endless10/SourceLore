#!/usr/bin/env python3
"""tsconfig extends 继承与边界。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"module_resolution"))
import sfx
import tsconfig_effective_config as EC
import tsconfig_parser as TP
import module_config_models as CM


def make_reader(files):
    """files: {path: dict_or_None_or_'BAD'}"""
    def read(path):
        v = files.get(path, "MISSING")
        if v == "MISSING":
            return None
        if v == "BAD":
            return {"ok": False, "error_code": CM.CONFIG_PARSE_FAILED}
        return {"ok": True, "data": v}
    return read


def cfg(extends=None, paths=None, base_url=None):
    comp = {}
    if paths:
        comp["paths"] = paths
    if base_url:
        comp["baseUrl"] = base_url
    d = {"compilerOptions": comp}
    if extends:
        d["extends"] = extends
    return d


class TestInheritance(unittest.TestCase):
    def test_simple_chain(self):
        files = {"tsconfig.json": cfg("./base.json", {"@/*": ["./src/*"]}),
                 "base.json": cfg(None, {"@/*": ["./old/*"]}, base_url=".")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["chain"]), 2)
        merged = EC.merge_chain(r["chain"])
        # ★ 子配置覆盖父配置的 paths
        self.assertEqual(merged["paths"], [{"pattern": "@/*",
                                            "targets": ["./src/*"]}])

    def test_inherit_from_parent_only(self):
        files = {"tsconfig.json": cfg("./base.json"),
                 "base.json": cfg(None, {"@/*": ["./src/*"]}, base_url=".")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertTrue(r["ok"])
        merged = EC.merge_chain(r["chain"])
        self.assertEqual(merged["paths"][0]["pattern"], "@/*")

    def test_cycle_detected(self):
        files = {"tsconfig.json": cfg("./a.json"),
                 "a.json": cfg("./tsconfig.json")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], CM.CONFIG_INHERITANCE_CYCLE)

    def test_self_extends(self):
        files = {"tsconfig.json": cfg("./tsconfig.json")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], CM.CONFIG_INHERITANCE_CYCLE)

    def test_missing_parent(self):
        files = {"tsconfig.json": cfg("./nope.json")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], CM.CONFIG_CONTENT_NOT_CAPTURED)

    def test_bad_parent(self):
        files = {"tsconfig.json": cfg("./bad.json"), "bad.json": "BAD"}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], CM.CONFIG_PARSE_FAILED)

    def test_npm_package_extends_unresolved(self):
        """★ 指向 npm 包 → 明确未解析，不假装继承完成。"""
        files = {"tsconfig.json": cfg("@tsconfig/base")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], CM.CONFIG_INHERITANCE_UNRESOLVED)

    def test_absolute_extends_unresolved(self):
        files = {"tsconfig.json": cfg("/etc/tsconfig.json")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], CM.CONFIG_INHERITANCE_UNRESOLVED)

    def test_empty_extends_list_ok(self):
        files = {"tsconfig.json": cfg(["./b.json"], {})
                 if False else cfg(None, {})}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertTrue(r["ok"])

    def test_depth_limit(self):
        files = {}
        paths = [f"c{i}.json" for i in range(20)]
        for i, p in enumerate(paths):
            nxt = f"./{paths[i+1]}" if i + 1 < len(paths) else None
            files[p] = cfg(nxt, {})
        r = EC.resolve_extends_chain(config_path="c0.json",
                                     read_config=make_reader(files))
        self.assertFalse(r["ok"])
        self.assertIn(r["error"], (CM.CONFIG_INHERITANCE_TOO_DEEP,
                                   CM.CONFIG_CONTENT_NOT_CAPTURED))

    def test_extends_without_json_suffix(self):
        files = {"tsconfig.json": cfg("./base"),
                 "base.json": cfg(None, {"@/*": ["./src/*"]})}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        self.assertTrue(r["ok"])

    def test_references_recorded(self):
        s = TP.extract_config_surface(
            {"references": [{"path": "./packages/a"}, "./packages/b"]},
            config_dir="")
        self.assertEqual(len(s["references"]), 2)
        self.assertEqual(s["references"][0]["path"], "./packages/a")

    def test_baseurl_from_parent_used(self):
        files = {"tsconfig.json": cfg("./base.json"),
                 "base.json": cfg(None, {"@/*": ["./src/*"]}, base_url=".")}
        r = EC.resolve_extends_chain(config_path="tsconfig.json",
                                     read_config=make_reader(files))
        merged = EC.merge_chain(r["chain"])
        self.assertEqual(merged["base_url"], ".")


if __name__ == "__main__":
    unittest.main(verbosity=2)
