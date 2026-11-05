#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全 HTML 转义与链接验证。

★ 原则：**来自仓库/Claim/路径/证据的一切文字都是不可信数据**。
   不可信内容只能作为"经转义的数据"进入**可信模板**，绝不拼进 HTML 结构。

★ 本模块**不做**"正则删 script 标签"这种伪防护。做法是：
   1. 用 html.escape() 做完整的实体转义（覆盖 < > & " '）
   2. 剥离控制字符与双向文本控制符（防视觉误导）
   3. 截断超长文本（防布局破坏）
   4. URL 白名单（只允许可信 host 的 https）
"""

import html
import re
import unicodedata
from urllib.parse import urlsplit, quote

# ── 剥离控制字符与双向文本控制符 ─────────────────────────────
# C0/C1 控制字符（除常见空白）+ 零宽/双向覆盖/隔离符
_CTRL = re.compile(
    "["
    "\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f"   # 控制字符
    "\u200b-\u200f"                          # 零宽 + 双向标记
    "\u202a-\u202e"                          # 双向覆盖
    "\u2066-\u2069"                          # 双向隔离
    "\ufeff"                                 # BOM
    "]")

MAX_TEXT = 4000          # 单字段上限（防超长破坏布局）
MAX_PATH = 240


def clean_text(value, *, limit: int = MAX_TEXT) -> str:
    """把任意值归一成安全的纯文本（未转义）。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = _CTRL.sub("", value)
    # 归一化（避免用组合字符伪造外观）
    value = unicodedata.normalize("NFC", value)
    if len(value) > limit:
        value = value[:limit] + "…（已截断）"
    return value


def esc(value, *, limit: int = MAX_TEXT) -> str:
    """★ 唯一允许把不可信文本放进 HTML 的入口。

    html.escape(quote=True) 会转义 & < > " ' —— 所以
    既不能闭合标签、也不能跳出属性值。
    """
    return html.escape(clean_text(value, limit=limit), quote=True)


def esc_path(value) -> str:
    """路径展示：截断更长、保留可读性。"""
    return esc(value, limit=MAX_PATH)


def esc_sha(value) -> str:
    """SHA 展示：只允许十六进制，其他一律按普通文本转义。"""
    raw = clean_text(value, limit=200)
    if re.fullmatch(r"[0-9a-fA-F]{7,64}", raw):
        return esc(raw, limit=64)
    return esc(raw, limit=64)


# ── URL 白名单 ────────────────────────────────────────────
ALLOWED_HOSTS = ("github.com", "api.github.com", "raw.githubusercontent.com")
ALLOWED_SCHEMES = ("https",)


def safe_url(value) -> str | None:
    """返回可安全使用的 URL 字符串；不可信时返回 None。

    ★ 只允许 https + 白名单 host + 合理路径。
      javascript: / data: / vbscript: / file: 一律拒绝。
      host 允许子域（如 codeload.github.com）。
    """
    if not isinstance(value, str):
        return None
    raw = _CTRL.sub("", value).strip()
    if not raw or len(raw) > 2000:
        return None
    try:
        parts = urlsplit(raw)
    except Exception:
        return None

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        return None
    host = (parts.hostname or "").lower()
    if not host:
        return None
    ok_host = any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)
    if not ok_host:
        return None
    # 禁止 userinfo（user:pass@host 这种混淆手法）
    if "@" in (parts.netloc or ""):
        return None
    if parts.port not in (None, 443):
        return None

    path = parts.path or "/"
    # 路径穿越：拒绝 .. 段
    if ".." in path.split("/"):
        return None
    safe_path = quote(path, safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="=&%:@!$'()*+,;/-._~") if parts.query else ""
    return f"https://{host}{safe_path}" + (f"?{query}" if query else "")


def link_or_text(value, *, label=None) -> str:
    """可验证则输出 <a>，否则输出纯文本。**不产生 javascript:/data: 链接**。"""
    url = safe_url(value)
    text = label if label is not None else (value or "")
    if url is None:
        return f'<span class="plain-url">{esc(text)}</span>'
    return (f'<a href="{esc(url)}" rel="noopener noreferrer nofollow" '
            f'target="_blank">{esc(text)}</a>')


# ── 可信模板骨架 ──────────────────────────────────────────
# 静态 CSS：不含任何外部资源，不依赖 JavaScript
BASE_CSS = """
:root {
  --fg: #1a1a1a; --bg: #ffffff; --muted: #5a5a5a; --line: #d8d8d8;
  --ok: #0b6b3a; --bad: #a11b1b; --unk: #6a4b00; --panel: #f7f7f7;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans CJK SC",
               "Microsoft YaHei", Roboto, Helvetica, Arial, sans-serif;
  font-size: 15px; line-height: 1.65;
}
.wrap { max-width: 1040px; margin: 0 auto; }
h1 { font-size: 1.6rem; margin: 0 0 4px; line-height: 1.3; word-break: break-word; }
h2 { font-size: 1.12rem; margin: 26px 0 10px; padding-bottom: 6px;
     border-bottom: 1px solid var(--line); }
h3 { font-size: 1rem; margin: 18px 0 8px; }
p, li { margin: 6px 0; }
.meta { color: var(--muted); font-size: .9rem; margin-bottom: 14px;
        word-break: break-all; }
.sha { font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
       word-break: break-all; }
.panel { background: var(--panel); border: 1px solid var(--line);
         border-radius: 6px; padding: 14px 16px; margin: 12px 0; }
.badge { display: inline-block; padding: 3px 9px; border-radius: 4px;
         font-size: .86rem; font-weight: 600; border: 1px solid currentColor; }
.badge.ok { color: var(--ok); } .badge.bad { color: var(--bad); }
.badge.unk { color: var(--unk); }
.badge.neutral { color: var(--muted); }
/* ★ 状态不只靠颜色：每个 badge 都带文字标签 */
dl { display: grid; grid-template-columns: minmax(140px, 220px) 1fr;
     gap: 6px 16px; margin: 8px 0; }
dt { color: var(--muted); font-size: .9rem; }
dd { margin: 0; word-break: break-word; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: .92rem; }
th, td { text-align: left; padding: 7px 10px; border: 1px solid var(--line);
         vertical-align: top; word-break: break-word; }
th { background: #ededed; font-weight: 600; }
ul { padding-left: 20px; }
code { font-family: ui-monospace, Consolas, monospace; font-size: .9em;
       background: #efefef; padding: 1px 4px; border-radius: 3px;
       word-break: break-all; }
.foot { margin-top: 30px; padding-top: 14px; border-top: 1px solid var(--line);
        color: var(--muted); font-size: .85rem; }
@media (max-width: 720px) {
  body { padding: 14px; font-size: 14px; }
  dl { grid-template-columns: 1fr; gap: 2px 0; }
  dt { margin-top: 8px; }
  table { font-size: .86rem; }
}
"""

# ★ 限制型 CSP：禁脚本、禁外链、禁 iframe、禁 object、禁 base
# ★ 该串是**模块内可信常量**，不含任何用户数据，所以直接内联、不做实体转义
#   （实体转义会把 ' 变成 &#x27;，虽仍有效但不利于人工核查）
BASE_CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
            "script-src 'none'; object-src 'none'; frame-src 'none'; "
            "form-action 'none'; base-uri 'none'")


def document(*, title: str, body_html: str, lang: str = "zh-CN") -> str:
    """把**可信模板生成的 body** 包成完整 HTML 文档。

    ★ body_html 必须是本模块或调用方用可信函数拼出来的，绝不能含未经转义的用户数据。
    """
    return f"""<!DOCTYPE html>
<html lang="{esc(lang, limit=16)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{BASE_CSP}">
<meta name="referrer" content="no-referrer">
<title>{esc(title, limit=200)}</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="wrap">
{body_html}
</div>
</body>
</html>
"""
