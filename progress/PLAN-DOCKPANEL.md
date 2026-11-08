# 方案：用官方 dockPanels 服务（零侵入 @botharness/ui）

## 为什么这条路最优
用户要求：①卡片进 Bot 模式 ②Bot 原有界面不变 ③升级插件不影响 ④不破坏其他东西

对比三条路：
| 方案 | 改 @botharness/ui | 升级安全性 | 结论 |
|---|---|---|---|
| 改 Welcome 加 slot | 要改 | 每次升级包被覆盖，补丁丢失 | ✗ |
| `botharness.settings.section` | 不改 | 安全 | ✗ 在设置页，不在 Bot 主界面 |
| **`dockPanels.register()`** | **不改** | **官方契约，升级兼容** | **✓** |

## 权威证据
1. `@botharness/ui` 公开导出 `./panels`（`dist/panel-api.d.mts`），
   定义 `DockPanelRegistry.register(panel: DockPanel): () => void` —— 这是官方公开 API。
2. Bot 运行时 `ctx.provide("dockPanels", dockPanels)` —— 第三方插件可 `ctx.inject(['dockPanels'])`。
3. 渲染确认：`dockPanelList = registeredDockPanels ?? dockEntryPanels`
   （`registeredDockPanels` 来自 `dockPanels.panels()`）→ 注册的面板真的会被渲染。

## DockPanel 契约
```ts
{
  id: string
  title: string
  icon?: string
  scope: 'global' | 'channel'
  binding?: 'current-bot'
  order?: number
  defaultPosition?: { zone: 'left'|'center'|'right'|'bottom', relativeTo?: string }
  component: ComponentType<DockPanelProps>   // props: { channel?, botId?, instanceId? }
}
```

## 实施步骤（每步单独验证）
1. 插件 client.js：`exports.inject = ["dockPanels"]`
2. `ctx.inject(['dockPanels'], (c) => c.effect(() => c.dockPanels.register({...})) )`
3. 重启 → 进 Bot 模式 → 确认面板出现在停靠区，且原有「频道列表/消息」不变
4. 若 zone 不合适，调 defaultPosition 再验证

## 回滚
只改插件自己的 client.js，不碰任何第三方包 → 回滚 = 改回原文件，`git checkout` 即恢复。

## 实施完成 + 离线验证（2026-08-08 18:00）
插件 `client.js` 改动：
```js
// factory 内照范例取 react
var react = require("react");

// 包装组件：DockPanel.component 是普通 react 组件
function SourcelorePanel() {
  var h = react.createElement;
  var st = react.useState({status:"loading", items:[], openIdx:-1, hoverIdx:-1});
  ...
  return h(Panel, { h: h, state: s, set: set });
}

function apply(ctx) {
  ctx.inject(["dockPanels"], function (c) {
    var dock = c.dockPanels;
    if (!dock || typeof dock.register !== "function") return;   // 无 Bot 环境时静默跳过
    c.effect(function () {
      return dock.register({
        id: ID, title: "源码知识卡片", icon: "layers",
        scope: "global", order: 60,
        defaultPosition: { zone: "right" },
        component: SourcelorePanel,
      });
    });
  });
}
exports.inject = ["slots", "dockPanels"];
```

## 离线 mock 验证结果（真跑，非推断）
```
inject 依赖: [["dockPanels"]]
注册面板: dsh-sourcelore-cards | 源码知识卡片
scope/zone: global / right
component: function
```
（mock 的 effect 立即执行 fn，与 cordis effect 真实行为一致）

## 安全性
- **不改 @botharness/ui 任何字节** → 升级包不会覆盖，补丁不会丢
- 插件自己 `git checkout` 即可回滚
- `dock.register` 返回 dispose，由 `c.effect` 管理生命周期 → 插件卸载自动撤销
- Bot 原有界面：只往停靠区**新增**一个面板，不动 channelSidebar / Welcome / 设置页

## 待重启验证
重启 DSH → 进 Bot 模式 → 看右侧停靠区是否出现「源码知识卡片」
