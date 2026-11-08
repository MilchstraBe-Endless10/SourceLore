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
