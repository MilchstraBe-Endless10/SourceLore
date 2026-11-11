# 断点：DSH 重启验证 dockPanels 官方注册（2026-11-11 23:58）

## 刚刚做了什么

改用 Tobs **官方 dockPanels** 扩展点，删除了对 `@botharness/ui` 的补丁依赖。

提交：`e8c89fb`

改动：
- `plugin/dsh-sourcelore-cards/client.js`
  `apply(ctx)` → `ctx.inject(["dockPanels"], …)` → `registry.register(panel)`
- `plugin/dsh-sourcelore-cards/index.js`
  `export const inject = []` → `['dockPanels']`

## 为什么改用官方口子（源码实证）

`@botharness/ui` 1.6.1 里 Tobs 自己就是这样注册面板的：

```js
ctx.provide("dockPanels", dockPanels)
dockPanels.register(createActivityCenterPanel(...))   // 活动中心
dockPanels.register(createMarketPanel(...))           // 插件市场
```

panel 契约：
```js
{ id, title, icon, scope:"global", order, defaultPosition:{zone:"right"},
  component: () => ReactNode, headerAction?: () => ReactNode }
```
id 校验 `/^[a-zA-Z0-9:@._-]{1,160}$/`，禁 `instance:` 前缀；`register()` 返回 dispose。

**旧结论 `progress/DOCKPANEL-DEADEND.md` 是错的**，已在
`progress/OFFICIAL-EXTENSION-POINT.md` 中纠正（留档不改旧文件）。

## 为什么要重启

`index.js` 的 `inject` 是宿主侧声明，DSH 启动时才读。
重启前 `/plugins/events` 里 `dsh-sourcelore-cards` 的 `rev` 仍是旧值
`845538ca7766`、`inject: []`。

## 重启后要验证的（按序）

1. `curl -sN http://127.0.0.1:<新端口>/plugins/events | grep sourcelore`
   → 确认 `rev` 变化、`inject` 含 `dockPanels`
2. 进 Bot 模式（左侧「Bot 模式」→ 按住不选频道）
   → 右侧应出现「仓库知识卡片」面板
3. 面板内验证：3 个仓库卡片、项目文档 Tab 能读正文、
   README 原文（is-plain-obj 含 Install/Usage/代码示例）
4. 截图存档

## 若 dockPanels 仍不可用

回退方案：`ctx.get("botPresentation")` / `channelSidebar` 也是公开服务。
再不行用 DSH 原生 `tool.call.toolview` 槽位（非 Tobs）。

## 数据侧已就绪（不受重启影响）

- 三仓库文档 7.7–12.5K（原 200–1200B）
- `/repocard` 返回 5 篇文档带正文（已验证端口 44321）
- `derive` 命令已固化：`sourcelore derive <rid>`
- 最近提交链：`275e63a` → `93cbe9a` → `1de758a` → `cfc26c3` → `e8c89fb`

## 关键环境事实

- 重启前端口 40475；重启后端口会变，从 `/proc/$(pgrep -f "dsh web")/environ` 的 DSH_WEB_URL 取
- `@botharness/ui` 当前 1.6.1、md5 `1f71cba1c5fe3221d41110a1496cf7bd`（**官方原版，未打补丁**）
- 插件 HTTP 路由无需 token；页面本身需要 token（日志里有 `?token=`）

---

## 状态更新（2026-11-12 00:03）

重启完成，新端口 **44839**，DSH 启动于 23:58:46。

### 已验证

- 服务器返回的 client bundle **确实含** `exports.inject = ["dockPanels"]`
  （`curl .../client.js&rev=845538ca7766 | grep 'inject ='` 有两处命中：
   第 7 行是注释里的示例文字，第 528 行是真代码）
- 插件目录是 pnpm **symlink**，指向
  `SourceLore/plugin/dsh-sourcelore-cards` —— 加载的就是我改的那份
- 磁盘上只有一份副本（find / 确认）
- `index.js` mtime 23:55 < 启动时间 23:58:46，理论上应读到 `['dockPanels']`

### 未解释的现象

`/plugins/events` 的 graph 里仍是：
```
{"id":"dsh-sourcelore-cards","rev":"845538ca7766","inject":[]}
```
- `rev` 没变（一直是 845538ca7766，早于本次改动）
- `inject` 仍是 `[]`

推测：graph 的 inject/rev 可能是**启动时缓存的插件元数据**，
不随 client.js 改动刷新；或 index.js 的 export 未被解析器识别。

### 下一步（按序，别跳）

1. 精确点 Bot 模式（左侧导航 y≈331，不是 367——365 那行是自动化任务）
2. 看右侧是否出现「仓库知识卡片」面板
3. 若没有：查 DSH 启动日志里有没有 `[sourcelore]` 相关 warn/error
4. 若仍没有：改用 `ctx.get("dockPanels")` 直接取（不依赖 inject 声明）
