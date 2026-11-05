#!/usr/bin/env python3
"""D. 知识呈现：卡片生成、HTML 可打开、限制保留、无恶意脚本。"""
import sys, unittest, tempfile, shutil, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tests"/"skill_interface"))
import sfx
for p in ("research","views","lifecycle","storage","collector","facts",
          "evidence_claims","runtime","renderer","skill_interface"):
    if str(ROOT/"src"/p) not in sys.path:
        sys.path.insert(0, str(ROOT/"src"/p))
if str(ROOT/"tests"/"views") not in sys.path:
    sys.path.insert(0, str(ROOT/"tests"/"views"))
import vfx, render as R

EVENT = re.compile(r'(?<=[ \t\n])on[a-z]+\s*=\s*["\']', re.I)


class TestRender(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rd_"))
        self.ks = vfx.fresh(self.tmp)
        src, cand, res, ad = vfx.run_full(self.ks)
        self.vid = src["verification_id"]
        self.rid = vfx.REPO

    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_card_generated(self):
        out = R.render_card(verification_id=self.vid,
                            repository_id=self.rid, data_root=str(self.tmp))
        hp = Path(out["html_path"])
        self.assertTrue(hp.exists(), "卡片 HTML 未生成")
        self.assertGreater(hp.stat().st_size, 1000)
        self.assertTrue(Path(out["json_path"]).exists())
        self.assertTrue(out["preview_allowed"])
        self.assertFalse(out["distribution_allowed"])

    def test_html_has_csp_and_no_script(self):
        out = R.render_card(verification_id=self.vid,
                            repository_id=self.rid, data_root=str(self.tmp))
        t = Path(out["html_path"]).read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", t)
        self.assertIn("Content-Security-Policy", t)
        self.assertIn("script-src 'none'", t)
        self.assertNotIn("<script", t.lower())
        self.assertIsNone(EVENT.search(t))

    def test_limitations_present(self):
        out = R.render_card(verification_id=self.vid,
                            repository_id=self.rid, data_root=str(self.tmp))
        js = json.loads(Path(out["json_path"]).read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(js["limitations"]), 1)
        # ★ 分发门禁在 distribution 字段，不在 limitations —— 断言对象必须对
        d = js["distribution"]
        self.assertFalse(d["distribution_allowed"])
        self.assertEqual(d["freeze_state"], "FROZEN_INTERNAL_RESTRICTED")
        ids = {b["id"] for b in d["blockers"]}
        self.assertEqual(ids, {"B-1", "B-2", "B-3"})
        # 限制文本里也要有可读的分发警告
        self.assertTrue(any("分发门禁" in x for x in js["limitations"]))

    def test_card_does_not_touch_db(self):
        """★ 渲染不得写入知识库。"""
        before = self.tmp/"kb.db"
        size0 = before.stat().st_size
        R.render_card(verification_id=self.vid, repository_id=self.rid,
                      data_root=str(self.tmp))
        self.assertEqual(size0, before.stat().st_size)


if __name__ == "__main__":
    unittest.main(verbosity=2)
