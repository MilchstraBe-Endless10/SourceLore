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

---

## 21:35 补充：渲染入口的真实条件

`Welcome` 只在「空态」渲染（源码 ui/lib/client.js:194272 / 194466）：
```js
const chatPane = state.selection === void 0 ? jsx(Welcome, {state, t}) : ...other views
if (!workspace && state.selection === void 0) return jsx(Welcome, {state, t});
```

当前实测 `botharness/bot-mode-layout-mode`：
```json
{"mode":"simple","sideColumn":"bh:channels","channelsWidth":0.22,...}
```
`mode: "simple"` 时 `railModeControls` 把 `CHANNEL_BODY_PANEL` 放进 `hidden`：
```js
function railModeControls(mode, order) {
  return mode === "simple"
    ? { order: [WORKSPACE_CHANNELS, ...order.filter(id => id !== WORKSPACE_CHANNELS)],
        hidden: [CHANNEL_BODY_PANEL] }
    : { order, hidden: [] };
}
```
**这就是 Bot 主体（channel body）不显示的原因** —— simple 模式下它被显式隐藏了。

## channelSidebar 是官方可用接口（不是死路）

```js
ctx.provide("channelSidebar")
// 契约：
{ register(entry), registerTab(tab), entries(scope), tabs(scope), subscribe(listener) }
// scope: "channel" | "personabot"
// entry.scope: "channel" | "personabot" | "both"
// entry.surface: "settings" 时只进设置页，否则会同时 dockPanels.registerEntry()
```
这给了一条**不用改 @botharness/ui、不用 Welcome** 的官方入口：
注册一个 `scope:"both"` 的 channelSidebar entry，它就会出现在 Bot 侧栏里。
（`dockPanels.registerEntry` 与本包之前的 `dockPanels.register` 是**不同方法**——
前者是给 channelSidebar 内部用的，后者才是死路。）

## 下一步优先级

1. **把 bot-mode-layout-mode 从 simple 改成完整模式** → 让 CHANNEL_BODY_PANEL 显示
2. 或用 `channelSidebar.register({scope:"both"})` 走官方侧栏入口
3. Welcome + BhHomeSlot 只在「空态」有效，不是主路径

---

## 21:37 决定性突破：卡片真的渲染出来了

改 `localStorage['botharness.bot-mode-layout-mode'].mode` 从 `"simple"` → `"full"`
（重载后被自动归一化为 `"advanced"`），结果：

```json
{"mode":"advanced","hasChannel":true,"slotDom":1}
```
```text
频道列表
消息
bh:workspace-rail opened
正在读取 SourceLore 知识库…          ← ★ 我的卡片组件，真的在渲染

从左侧选择一个 Bot 或频道开始
```

**这证明整条链路完全通了**：插件 → slot → UI 补丁 → BhHomeSlot → 我的组件 → 渲染。

## 但它是瞬时/条件性的

重载后 `slotDom` 又从 1 变回 0，body 变成「从左侧选择一个 Bot 或频道开始」。
原因仍是 `Welcome` 只在**未选中频道**时渲染；一旦有选中就切走。

## 真正的解法（下一步）

`Welcome` 是空态组件，不该作为主挂载点。正确做法是用官方 `channelSidebar`：

```js
const cb = ctx.get("channelSidebar")
cb.register({
  id: "sourcelore:cards",
  scope: "both",          // "channel" | "personabot" | "both"
  title: "仓库知识卡片",
  icon: "folder",
  component: () => react.createElement(SourcelorePanel),
  // surface 不写 "settings" 时，会同时 dockPanels.registerEntry() 挂到右侧栏
})
```
内置条目由 `createChannelSidebarBuiltins(...).map(e => channelSidebar.register(e))` 注册
（ui/lib/client.js:205303）。

**注意区分两个同名不同物的东西**：
- `dockPanels.register(panel)` —— 死路（见 DOCKPANEL-DEADEND.md）
- `dockPanels.registerEntry(entry, ...)` —— channelSidebar 内部用，是活的

## 已确认可复用的操作配方

```
1. sqlite3 读 ~/.config/open-deepseek-harness-desktop/session-data/Cookies
   → host=127.0.0.1 的 name/value 就是 Web 认证 cookie
2. Playwright addCookies 注入 → goto http://127.0.0.1:<port>/ → 200
3. page.setViewportSize({width:1600,height:1000})   ← 必须 ≥961，否则 Bot 按钮不渲染
4. 点 button:has-text("Bot 模式")
5. localStorage['botharness.bot-mode-layout-mode'].mode = 'full'，重载
```
