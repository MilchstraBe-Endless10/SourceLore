# Bot 模式面板接入 · 权威机制（2026-11-07 20:48）

## 我一开始错在哪
把插件注册到 `shell.overlay` —— 那是 **DSH 主界面**的浮层，不是 **Bot 模式**。
用户要的是 Bot 模式界面（Tobs，由 `@botharness/ui` 渲染）。

## 真机制（两处独立证据）
### 证据一：本机真实可用的 Bot 插件范例
`node_modules/dsh-agent-model-statusbar/client.js:317-327`
```js
function apply(ctx) {
  ctx.slots.inject("shell.overlay", function () {
    return ctx.slots.register(
      { name: "shell.overlay", id: "dsh-agent-model-statusbar", order: 45, label: "本地模型" },
      function () { return h(StatusBar) },
    )
  })
}
exports.apply = apply
exports.inject = ["slots"]   // ★ 少了这一行整包**静默失效**
```
模块外壳必须是：
```js
window.__ModuleLoader__.load({ id: "<pkg>", factory: (require) => { ...
  return module.exports } })
```

### 证据二：Bot 模式的槽位名（`@botharness/ui/lib/client.js`）
```
bh:home                        Bot 主页区        ← 本插件用这个
bh:workspace-rail              工作区侧栏
bh:channels                    频道列表
bh:channel-body                消息主体
botharness.settings.section    Bot 设置页分区
shell.overlay                  DSH 主界面浮层（★ 不是 Bot）
```
内置 Bot 面板走另一条路（`dockPanels`/`channelSidebar`，见 `DockPanelRegistry`、
`createChannelSidebarRegistry`，`scope: 'channel'|'personabot'`），
但那是 `@botharness/ui` 内部构建的注册表，**第三方插件拿不到**
—— 第三方唯一公开入口就是 `ctx.slots`。

## 已实现
`plugin/dsh-sourcelore-cards/client.js`：
- 外壳 `__ModuleLoader__.load({id, factory})`
- `exports.inject = ["slots"]`
- `ctx.slots.inject("bh:home", …)` → `ctx.slots.register({name:"bh:home", id, order:40, label:"源码知识卡片"}, Panel)`
- 卡片墙：状态色带（绿=已验证/黄=已观察/灰=证据不足/紫=不支持）、悬停浮起、点击展开关联链、
  导出到 Obsidian 按钮、刷新
- 验证：`node -e vm` 加载 → `apply: function` / `inject: ["slots"]`

## 剩余
- 重启 DSH 生效（需用户同意；用户此前已重启过一次，但那时装的是错的槽位）
- 重启后在 **Bot 模式** 的 Home 区看「源码知识卡片」块
- 若 bh:home 槽不渲染，退到 `botharness.settings.section`（作为设置页分区）

## 客户端已按 Bot 槽位重写并验证（2026-11-07 20:49）
```
node -e vm 加载 client.js（mock window.__ModuleLoader__）
→ id: dsh-sourcelore-cards | apply: function | inject: ["slots"]
```
外壳：
```js
window.__ModuleLoader__.load({
  id: "dsh-sourcelore-cards",
  factory: (require) => { ... exports.apply = apply
                          exports.inject = ["slots"]
                          return module.exports },
})
```
槽位：`ctx.slots.inject("bh:home", () => ctx.slots.register(
  {name:"bh:home", id, order:40, label:"源码知识卡片"}, () => h(Panel)))`

## 待验证（重启后）
- Bot 模式 Home 区是否出现「源码知识卡片」块
- 若 bh:home 不渲染 → 退 `botharness.settings.section`

## 点击 Bot 模式的障碍（记下来，别重复试）
- `ydotool` 需 `ydotoold` 守护进程（socket 不存在），启动需 sudo → 未自行启动
- `hyprctl dispatch movecursor X Y` 语法在 0.56 走 hl.dsp 新语法，裸参数报错
→ 改为：让用户点 Bot 模式，或重启后由用户确认
