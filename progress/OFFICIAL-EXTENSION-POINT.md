# 【重大纠正】dockPanels 是官方扩展点，不是死路

日期：2026-11-11 · 依据：`@botharness/ui` 1.6.1 源码实证

## 之前错在哪

项目里 `progress/DOCKPANEL-DEADEND.md` 记录「dockPanels 是死路，
register() 会强制 entry=undefined 并替换内置右栏」。**这个结论是错的。**

实际源码（`ui/lib/client.js`）：

```js
const dockPanels = createDockPanelRegistry({ ... })
ctx.provide("dockPanels", dockPanels)          // ← 公开服务

// Tobs 自己就用它注册两个内置面板：
dockPanels.register(createActivityCenterPanel(actions, t, dockPanels))
dockPanels.register(createMarketPanel(actions, dockPanels, t))
```

「插件市场」面板就是这么注册进去的。第三方插件走同一个口子即可。

## 官方契约（register 校验逻辑）

```js
register(panel) {
  if (!/^[a-zA-Z0-9:@._-]{1,160}$/.test(panel.id)
      || panel.id.startsWith("instance:"))
    throw new Error("invalid_panel_definition")
  ...
  return disposeFn
}
```

panel 形状（照 `createMarketPanel`）：

```js
{
  id: "sourcelore:repo-cards",     // 唯一，禁 instance: 前缀
  title: "仓库知识卡片",
  icon: "folder",
  scope: "global",
  order: 520,                       // 内置市场是 500
  defaultPosition: { zone: "right" },
  component: () => ReactNode,       // 面板主体
  headerAction?: () => ReactNode    // 可选标题栏动作
}
```

## 为什么这条更重要

`@botharness/ui/lib/client.js` 是 **Tobs 升级会被覆盖**的文件：

- 2026-11-08 打补丁 → 2026-11-11 19:57 Tobs 升到 1.6.1，补丁全部消失
  （md5 从 `f12479a2…` 变为 `1f71cba1…`，`BhHomeSlot` 出现 0 次）
- 而用官方 `dockPanels` 注册，升级不会丢

## 已做的改动

1. `client.js`：`apply(ctx)` 改为 `ctx.inject(["dockPanels"], …)` + `registry.register(panel)`
2. `index.js`：`export const inject = []` → `['dockPanels']`

## 待验证

宿主插件改动需 DSH 重启才生效（`/plugins/events` 里 rev 仍是旧值）。
重启后应能在 Bot 模式右侧看到「仓库知识卡片」面板。
