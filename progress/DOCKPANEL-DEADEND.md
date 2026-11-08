# dockPanels 第三方注册：已知死路（2026-11-08 实测）

## 结论
在 Bot @botharness/ui v1.6.0 里，`ctx.provide("dockPanels")` 对第三方插件可注入、可调用，
但**注册进去的面板永远不会显示自己的 UI 组件**。这不是配置问题，是 API 设计如此。

## 证据（全部来自安装包 lib/client.js，未打补丁的原版）

### 1) register() 主动清空 entry
```js
register: (panel) => add({ ...panel, entry: void 0 })
```
而决定「面板是否出现在 tab 列表」的判断是：
```js
const visibleIds = useSame(
  [...byId.values()].flatMap(p => p.entry !== void 0 && shows(p.entry) ? [p.id] : []),
  sameData)
```
`entry` 恒为 undefined → 第三方注册的面板永远进不了 visibleIds。

### 2) shows 还会二次过滤
```js
shows: entry => (entry.scope === "both" || entry.scope === settingsScope) && ...
```
注册时写 `scope:"global"` 两个条件都不满足；写 `"both"` 虽能过 shows，
但上面第 1 条已经先挡住了。

### 3) 注册会让原生面板整体消失
```js
const dockPanelList = registeredDockPanels ?? dockEntryPanels
```
只要有任何插件注册，`registeredDockPanels`（第三方 panels）就取代
`dockEntryPanels`（由原生频道派生）。于是 **右侧原有的
会话/记忆文件/记忆演化/定时任务/Browser/Computer/频道文件/Bot收件箱 全部消失**，
而第三方面板又因第 1 条不渲染 —— 净效果是界面变空。

### 4) 组件签名也对不上
```js
DockPanelBody: jsx(panel.component, { channel })
```
入参只有 `{ channel }`；entry 路径则是 `entryProps`。第三方组件拿不到自己的 state/props。

### 5) registerEntry 是唯一的「带 entry」入口，但组件恒为 null
```js
registerEntry: (entry, defaultPosition) => add({
  id: entry.id, title: entry.label, icon: entry.icon,
  scope: "channel", defaultPosition, order: entry.order,
  component: () => null,   // ← 内容靠 entryProps 注入，不是靠 component
  entry
})
```
它由 `channelSidebar.register(entry)` 间接调用，服务对象是**内建条目系统**，
不是「第三方塞一个 React 组件进 Bot 主界面」的入口。

## 能走的路只剩两条
1. 给 `@botharness/ui` 打补丁（改 Welcome/BotPanel 加 renderSlot）——上次导致 Bot 面板空白，已回滚。
2. 维持 `botharness.settings.section`（Bot 设置页里能看卡片），不碰主界面。

## 顺带验证到的有用结论（不要再走弯路）
- **DSH 有热更新**：`@deepseek-ai/dsh-client-hmr` 每 500ms stat 轮询插件 bundle 的 mtime，
  变了就 `clientModules.rebuilt(id)` 推送新版本给已开页面。改 client.js 后不用重启 DSH。
- **验证客户端是否执行**：可在插件顶层/apply 里改 `document.title` 或 `document.body.style.outline`，
  宿主用 `hyprctl clients -j` 读标题、或 `grim` 截图，零依赖即可确认。
- Bot 内建 graph 可从 `GET /plugins/events`（SSE，无需 token）读出，含每个插件的 id/rev/inject。
