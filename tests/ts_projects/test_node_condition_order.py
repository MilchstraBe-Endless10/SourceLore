#!/usr/bin/env python3
"""Node 条件导出键顺序语义（P5I 回归）。"""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"ts_projects"))
import sfx
import package_module_map_parser as PM


class TestKeyOrder(unittest.TestCase):
    def test_default_first_wins(self):
        """★ default 在前 → default 先命中，不能跳过。"""
        v = {"default": "./fallback.js", "import": "./esm.js"}
        r = PM.expand_condition(v, available_conditions=["import"])
        self.assertTrue(r["resolved"])
        self.assertEqual(r["condition_used"], "default")
        self.assertEqual(r["target"], "./fallback.js")

    def test_default_last_loses(self):
        v = {"import": "./esm.js", "default": "./fallback.js"}
        r = PM.expand_condition(v, available_conditions=["import"])
        self.assertEqual(r["condition_used"], "import")
        self.assertEqual(r["target"], "./esm.js")

    def test_only_default(self):
        for conds in (["import"], ["require"], []):
            r = PM.expand_condition({"default": "./d.js"},
                                    available_conditions=conds)
            self.assertEqual(r["target"], "./d.js", str(conds))

    def test_import_and_node_both_available(self):
        """★ import 与 node 同时可用 → 按配置顺序取第一个。"""
        v = {"import": "./e.js", "node": "./n.js", "default": "./d.js"}
        r = PM.expand_condition(v, available_conditions=["import", "node"])
        self.assertEqual(r["condition_used"], "import")
        self.assertEqual(r["target"], "./e.js")

    def test_require_and_node_both_available(self):
        v = {"require": "./c.cjs", "node": "./n.js"}
        r = PM.expand_condition(v, available_conditions=["require", "node"])
        self.assertEqual(r["condition_used"], "require")
        self.assertEqual(r["target"], "./c.cjs")

    def test_order_differs_same_keyset(self):
        """★ 键集合相同、顺序不同 → 不同结果。"""
        a = {"node": "./n.js", "import": "./e.js"}
        b = {"import": "./e.js", "node": "./n.js"}
        ra = PM.expand_condition(a, available_conditions=["import", "node"])
        rb = PM.expand_condition(b, available_conditions=["import", "node"])
        self.assertEqual(ra["target"], "./n.js")
        self.assertEqual(rb["target"], "./e.js")

    def test_unknown_custom_condition(self):
        r = PM.expand_condition({"custom": "./x.js"},
                                available_conditions=["import"])
        self.assertFalse(r["resolved"])
        self.assertEqual(r["reason"], "NO_MATCHING_CONDITION")

    def test_unknown_condition_indeterminate(self):
        """★ 条件集合不确定 → 不判无匹配。"""
        r = PM.expand_condition({"custom": "./x.js"},
                                available_conditions=["import"],
                                conditions_deterministic=False)
        self.assertFalse(r["resolved"])
        self.assertEqual(r["reason"], "UNKNOWN_CONDITIONS_PRESENT")

    def test_nested_conditions(self):
        v = {"node": {"import": "./n-e.js", "require": "./n-c.cjs"},
             "default": "./d.js"}
        r = PM.expand_condition(v, available_conditions=["node", "import"])
        self.assertEqual(r["target"], "./n-e.js")

    def test_null_blocks(self):
        r = PM.expand_condition({"import": None}, available_conditions=["import"])
        self.assertFalse(r["resolved"])
        self.assertEqual(r["reason"], "EXPORT_EXPLICITLY_BLOCKED")

    def test_array_fallback(self):
        r = PM.expand_condition({"default": ["./a.js", "./b.js"]},
                                available_conditions=["import"])
        self.assertEqual(r["target"], "./a.js")

    def test_types_not_runtime_default(self):
        """★ types 是 TS 键，不在 Node 默认条件里。"""
        r = PM.expand_condition({"types": "./t.d.ts", "import": "./t.js"},
                                available_conditions=["import"])
        self.assertEqual(r["condition_used"], "import",
                         "未给 types 条件时不应命中 types")

    def test_types_when_explicitly_given(self):
        r = PM.expand_condition({"types": "./t.d.ts", "import": "./t.js"},
                                available_conditions=["types", "import"])
        self.assertEqual(r["condition_used"], "types")

    def test_candidates_record_all_keys(self):
        v = {"import": "./e.js", "require": "./c.cjs", "default": "./d.js"}
        r = PM.expand_condition(v, available_conditions=["import"])
        keys = [c["condition"] for c in r["candidates"]]
        self.assertEqual(keys, ["import", "require", "default"])

    def test_skipped_reason_recorded(self):
        r = PM.expand_condition({"import": "./e.js", "require": "./c.cjs"},
                                available_conditions=["require"])
        self.assertTrue(any("import" in str(s.get("condition"))
                            for s in r.get("skipped") or []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
