# Bot 模式卡片：完整诊断（2026-11-16）

## 已彻底打通的部分

### 1. Web 端认证（此前一直卡着）
```
Electron 的 Cookies SQLite 里有明文 cookie（enc_len=0, value_len=173）：
  表: ~/.config/open-deepseek-harness-desktop/session-data/Cookies
  行: host=127.0.0.1, name=dsh-auth-<sha256(host)>, value=v1.<payload>.<hmac>
用法: Cookie: <name>=<value>  →  HTTP 200
```
**不需要 token、不需要重启、不需要用户操作。** 直接从 SQLite 读即可。

### 2. Playwright 视口（此前反复失败的真正原因）
```js
window.innerWidth < 961  →  Tobs 左侧栏（含「Bot 模式」按钮）完全不渲染
```
`botModeSidebarViewport()` 要求 `matchMedia('(min-width: 961px)')`。
Playwright 默认视口 1280x720 但实测 `innerW=941` → 按钮不存在 → 我一直点不到。
**修复：`page.setViewportSize({width:1600, height:1000})`。**

### 3. 插件 slot 注册（真 bug，已修）
`registerHomeSlot()` 原先被放在 `if (!dockPanels) return;` 之后 → 永不执行。
移到检查之前后：
```
window.__bhHomeSlots__ = [{ id: "sourcelore:repo-cards", component: <function> }]
```
热加载生效（rev 16a44a77e048），无需重启。

### 4. UI 补丁
`@botharness/ui/lib/client.js` 里 `BhHomeSlot` 已打（md5 806ce8a1），
浏览器端确认 `hasBhHomeSlot: true, hasWelcome: true, slotKeyRef: true`。

## 剩下的唯一问题

Bot 模式已激活（`aria-current="page"`, `class="a-W-da_panelActive"`），
DOM 里出现 `bh-root bh-companion-stage`（角色动画层），
**但 `Welcome` 组件没有渲染** → `[data-bh-home-slots]` 数量为 0。

`Welcome` 的渲染条件（ui/lib/client.js:194272 与 194466）：
```js
const chatPane = state.selection === void 0 ? jsx(Welcome, {state, t}) : ...
// 以及
if (!workspace && state.selection === void 0) return jsx(Welcome, {state, t});
```

即：**只有「没有选中任何频道/会话」的空态才渲染 Welcome。**
当前必有 selection（选中了某个频道或 bot DM），所以走的是别的分支。

## 下一步要做的

1. 在 Bot 模式里把 selection 清空（选中态归零），让 Welcome 出现
2. 或改补丁：不只挂在 Welcome 上，也在选中频道时挂一个卡片区 —— 但那是改 Tobs 更多地方
3. 数据侧：Bot 的数据走 WebSocket RPC（`call(endpoint, payload)`），不是 REST；
   `/api/bot/home` 是 404。要查真实 endpoint 名得读 Tobs 的 call 实现。

## 工具脚本
- `~/.dsh-web/main-cookie.json` —— 主实例 cookie（600 权限）
- `~/.dsh-web/get-web-url.sh` —— 独立实例版
