#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-18..T-22 / T-36：HTML 注入与恶意输入负向测试。"""
import sys, tempfile, shutil, unittest, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for p in ("tests/renderer", "src/renderer", "src/views", "src/lifecycle",
          "src/storage", "src/collector", "src/facts", "src/evidence_claims",
          "src/runtime", "tests/views"):
    if str(ROOT/p) not in sys.path:
        sys.path.insert(0, str(ROOT/p))
import rfx
import safe_html as H
import card_models as CM, card_renderer as CRD

EVENT_ATTR = re.compile(r'(?<=[ \t\n])on[a-z]+\s*=\s*["\']', re.I)

PAYLOADS = [
    ("script 标签", "<script>alert(1)</script>"),
    ("属性注入", '"><img src=x onerror=alert(1)>'),
    ("单引号属性", "'><svg onload=alert(1)>"),
    ("javascript URL", "javascript:alert(1)"),
    ("data URL", "data:text/html,<script>alert(1)</script>"),
    ("iframe", "<iframe src='https://evil.com'></iframe>"),
    ("object", "<object data='evil.swf'></object>"),
    ("svg 脚本", "<svg><script>alert(1)</script></svg>"),
    ("body onload", "<body onload=alert(1)>"),
    ("markdown 原标签", "[click](javascript:alert(1))"),
    ("样式注入", "<style>body{background:url(javascript:alert(1))}</style>"),
    ("闭环注释", "<!--<script>alert(1)</script>-->"),
]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rh_"))
        self.ks = rfx.fresh(self.tmp)
    def tearDown(self):
        try: self.ks.close()
        except Exception: pass
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestEscaping(unittest.TestCase):
    def test_t18_script_injection_escaped(self):
        for name, payload in PAYLOADS:
            out = H.esc(payload)
            self.assertNotIn("<script", out.lower(), name)
            self.assertNotIn("<iframe", out.lower(), name)
            self.assertNotIn("<object", out.lower(), name)
            self.assertNotIn("<svg", out.lower(), name)
            self.assertNotIn("<style", out.lower(), name)
            self.assertNotIn("<body", out.lower(), name)
            # 尖括号必须变成实体
            if "<" in payload:
                self.assertIn("&lt;", out, name)

    def test_t19_event_attrs_cannot_enter_structure(self):
        """事件处理器属性不得出现在转义结果的可执行位置。"""
        for name, payload in PAYLOADS:
            out = H.esc(payload)
            self.assertIsNone(EVENT_ATTR.search(out), name)
        # 属性注入的核心：引号必须被实体化
        self.assertIn("&quot;", H.esc('"><img src=x>'))
        self.assertIn("&#x27;", H.esc("'><svg>"))

    def test_t20_js_and_data_urls_rejected(self):
        for bad in ("javascript:alert(1)", "JavaScript:alert(1)",
                    "  javascript :alert(1)  ", "data:text/html,x",
                    "vbscript:msgbox(1)", "file:///etc/passwd",
                    "about:blank"):
            self.assertIsNone(H.safe_url(bad), bad)

    def test_t20b_only_https_allowlisted(self):
        ok = H.safe_url("https://github.com/octocat/Hello-World")
        self.assertEqual(ok, "https://github.com/octocat/Hello-World")
        self.assertIsNotNone(H.safe_url("https://api.github.com/repos/x/y"))
        for bad in ("http://github.com/x", "https://evil.com/x",
                    "https://github.com.evil.com/x",
                    "https://user:pass@github.com/x",
                    "https://github.com/../../etc/passwd",
                    "//github.com/x"):
            self.assertIsNone(H.safe_url(bad), bad)

    def test_t20c_link_or_text_never_produces_bad_href(self):
        out = H.link_or_text("javascript:alert(1)")
        self.assertNotIn("<a ", out)
        self.assertIn("plain-url", out)
        out2 = H.link_or_text("https://github.com/a/b")
        self.assertIn('<a href="https://github.com/a/b"', out2)
        self.assertIn("noopener", out2)

    def test_t21_malicious_svg_markdown_no_breakout(self):
        for payload in ("<svg/onload=alert(1)>",
                        "<math><maction actiontype='statusline#http://x'>",
                        "![x](javascript:alert(1))",
                        "```<script>alert(1)</script>```"):
            out = H.esc(payload)
            self.assertIsNone(re.search(r"<svg", out, re.I))
            self.assertIsNone(re.search(r"<math", out, re.I))
            self.assertIsNone(re.search(r"<script", out, re.I))

    def test_control_and_bidi_stripped(self):
        self.assertNotIn("\u202e", H.clean_text("safe\u202etext"))
        self.assertNotIn("\u200b", H.clean_text("a\u200bb"))
        self.assertNotIn("\x00", H.clean_text("a\x00b"))
        # 归一化后仍可读
        self.assertIn("safe", H.clean_text("safe\u202etext"))

    def test_t22_overlong_text_truncated(self):
        long_path = "a" * 5000
        out = H.esc_path(long_path)
        self.assertLessEqual(len(out), H.MAX_PATH + 40)
        self.assertIn("已截断", out)
        huge = "b" * 20000
        out2 = H.esc(huge)
        self.assertLessEqual(len(out2), H.MAX_TEXT + 40)

    def test_t36_third_party_phrase_not_rendered(self):
        """不复制 UPSTREAM-06 受保护表达。"""
        protected = "Unsupported claims MUST NOT be presented as facts"
        cards, src, res = rfx.make_cards(
            ks := rfx.fresh(Path(tempfile.mkdtemp(prefix="rh2_")))
        )
        try:
            html = CRD.render_card_html(cards[-1])
            self.assertNotIn(protected, html)
        finally:
            ks.close()


class TestCardHtmlSafety(Base):
    def test_card_html_has_no_executable_surface(self):
        cards, src, res = rfx.make_cards(self.ks)
        html = CRD.render_card_html(cards[-1])
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<iframe", html.lower())
        self.assertNotIn("<object", html.lower())
        self.assertNotIn("<embed", html.lower())
        self.assertIsNone(EVENT_ATTR.search(html))
        self.assertNotIn("javascript:", html.lower())
        self.assertNotIn('src="http', html.lower())
        self.assertNotIn("@import", html.lower())

    def test_malicious_view_text_stays_escaped(self):
        """把恶意文本塞进视图字段，渲染后不得变成可执行结构。"""
        cards, src, res = rfx.make_cards(self.ks)
        c = dict(cards[-1])
        c = json.loads(json.dumps(c))
        # ★ 标题是从 claim_payload 投影出来的，所以要同时污染两处，
        #   才能真正验证"注入点全部走转义"。
        c["claim_scope"] = dict(c["claim_scope"])
        c["claim_scope"]["normalized_path"] = "<script>alert(1)</script>"
        c["title"] = "<script>alert(1)</script>"
        c["repository_id"] = '"><img src=x onerror=alert(1)>'
        c["limitations"] = list(c["limitations"]) + [
            '"><img src=x onerror=alert(1)>',
            "<svg/onload=alert(1)>"]
        html = CRD.render_card_html(c)

        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<svg", html.lower())
        self.assertIsNone(EVENT_ATTR.search(html),
                          "事件属性不得出现在属性位置")
        self.assertIn("&lt;script&gt;", html, "标题里的尖括号必须实体化")
        self.assertIn("&quot;&gt;&lt;img", html,
                      "仓库字段里的引号与尖括号必须实体化")

    def test_csp_present_and_restrictive(self):
        cards, src, res = rfx.make_cards(self.ks)
        html = CRD.render_card_html(cards[-1])
        self.assertIn('http-equiv="Content-Security-Policy"', html)
        self.assertIn("default-src 'none'", html)
        self.assertIn("script-src 'none'", html)
        self.assertIn("object-src 'none'", html)

    def test_no_external_font_or_script(self):
        cards, src, res = rfx.make_cards(self.ks)
        html = CRD.render_card_html(cards[-1])
        self.assertNotIn("fonts.googleapis", html)
        self.assertNotIn("<link", html.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
