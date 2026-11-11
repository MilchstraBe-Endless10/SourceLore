# dockPanels 接入断点（2026-11-12 00:12）

## 核心事实（已确认）

1. **Tobs 官方扩展点存在且可用**：`ctx.provide("dockPanels")`，
   Tobs 自己用 `dockPanels.register()` 注册「活动中心」「插件市场」两个内置面板。
   panel 契约 `{id,title,icon,scope,order,defaultPosition,component,headerAction}`，
   id 校验 `/^[a-zA-Z0-9:@._-]{1,160}$/`、禁 `instance:` 前缀、返回 dispose。

2. **宿主 index.js 的 inject 必须留空 `[]`**。
   声明 `['dockPanels']` 会让宿主永久 pending：
   `sourcelore-cards (dsh-sourcelore-cards): pending (waiting for service: dockPanels)`
   因为 dockPanels 是客户端（浏览器 cordis）服务，宿主 Node 侧看不到。
   必须在 client.js 的 `apply(ctx)` 里 `ctx.inject(["dockPanels"], cb)`。

3. **client.js 热加载有效，不要重启**。
   验证：`curl -sN http://127.0.0.1:<port>/plugins/events | grep sourcelore`
   看 `rev` 是否变化。本次从 `845538ca7766` → `795460285e87`，说明已加载。

4. **改 `@botharness/ui` 补丁是错的**（Tobs 升级即覆盖；本次 11-11 19:57 升 1.6.1，
   md5 `f12479a2`→`1f71cba1`，`BhHomeSlot` 归零）。现已回滚为官方原版。

## 已提交

- `e8c89fb` 改用官方 dockPanels（源码实证）+ 纠正旧 DOCKPANEL-DEADEND 结论
- 后续提交：index.js inject 恢复 `[]`；client.js apply 改双路径（inject + ctx.get 轮询 40×250ms）

## 已进项目记忆

- `ins_6ef8c83b` inject 不能声明客户端服务
- `ins_f604bf4a` client.js 热加载有效、不要重启

## 待验证

当前 DSH 实例端口 44839，启动 23:58:46。
`/plugins/events` 的 rev 已变为 `795460285e87`（客户端新代码已加载），
但 **尚未在 Bot 模式里肉眼确认面板出现**。

下一步：
1. 点左侧「Bot 模式」→ 不选频道，看右侧是否出现「仓库知识卡片」面板
2. 若无：查当前实例日志（harness.log 停在 15:59，说明当前实例日志另有去处 ——
   可能是 desktop-web-restart 或 /tmp/dsh_restart_out.log，需定位）
3. 若 dockPanels 仍拿不到：改 `ctx.get("botPresentation")` 或 `channelSidebar`

## 环境

- 端口 44839；`DSH_WEB_URL=http://127.0.0.1:44839`
- 插件 pnpm symlink → `SourceLore/plugin/dsh-sourcelore-cards`
- 日志 `~/.config/open-deepseek-harness-desktop/logs/harness.log`（当前停更，需重新定位）
