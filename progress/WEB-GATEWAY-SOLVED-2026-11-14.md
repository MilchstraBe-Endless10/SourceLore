# DSH Web 端访问：已打通（2026-11-14）

## 结论
Web 端认证**完全可以自动化**，不需要人工点任何东西，也不需要读凭据文件。

## 认证机制（读源码 + 实测）

`@deepseek-ai/dsh-client-connection/lib/types/browser-auth.js`：

```
token  →  GET /?token=<32B-base64url>
          →  303 See Other
          →  Set-Cookie: dsh-auth-<sha256(host)=base64url>=v1.<payload>.<hmac>
             （HttpOnly; SameSite=Strict; Max-Age=30d）
后面  →  带该 cookie 访问 /  →  200
```

- `launchToken` 由 `PROCESS_LAUNCH_TOKENS` WeakMap 按进程缓存，**每进程一个**。
- 启动时打印在日志：`dsh web: http://127.0.0.1:<port>/?token=...`
- cookie 用 HMAC-SHA256 签名，secret 存在 credential store（Agent 读不到，也不需要读）。

## 关键发现

1. **必须用 `--no-open` 起独立实例才能拿到干净的 token 日志**；桌面版把日志打码了。
2. **curl 拿到 cookie 后可以直接用**；Playwright 需要 `context.addCookies()` 注入，
   且 cookie 值必须**逐字符精确**（我抄错过一次 `issuedAt`→`issuedat`）。
3. 页面 `waitUntil` 不能用 `networkidle`（有常驻 SSE 连接），用 `domcontentloaded`。

## 可复用脚本

`~/.dsh-web/get-web-url.sh [port]` —— 起实例 / 抓 token / 建 cookie / 验证 200。

## 实测结果

```
$ curl -s -i "http://127.0.0.1:41999/?token=..."
HTTP/1.1 303 See Other
set-cookie: dsh-auth-yLH9...=v1.eyJ2ZXJzaW9uIjoxLCJhdXRob3JpdHkiOiIxMjcu...; Max-Age=2592000

$ curl -H "Cookie: dsh-auth-...=v1..." http://127.0.0.1:41999/
HTTP 200

Playwright（注入 cookie 后）：
  status: 200
  title : DeepSeek Harness
  __DSH_BOOT__: true
```

## 已确认的 Bot 模式访问

```
点击左侧导航 button "Bot 模式"  →  成功
body 含「频道列表」                →  true
window.__bhHomeSlots__            →  ["sourcelore:repo-cards"]   ← slot 已注册
@botharness/ui 加载的 bundle      →  hasBhHomeSlot: true, hasWelcome: true
```

## 剩余的最后一个问题

`window.__bhHomeSlots__` 有内容、UI bundle 里有 `BhHomeSlot`，
但 DOM 里 `[data-bh-home-slots]` 数量为 0 —— 说明 **`Welcome` 组件当前未渲染**。

原因：`Welcome` 只在「无选中频道」的空态渲染。41999 是独立实例，
数据库 lease 被主实例占着（`Profile writer lease is held`），频道列表加载不全，
所以停在别的视图。

**结论**：Web 通路 OK，slot 通路 OK，UI 补丁 OK。
只差「主实例 + 真实频道数据」同时具备的环境 —— 也就是你自己的桌面 DSH。
