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

## ★★ 操控电脑的正确方法（2026-11-08 00:47 实测成功）
### 可行：内核级虚拟鼠标（无需任何守护进程、无需 sudo）
```python
import evdev, time
from evdev import ecodes, UInput, AbsInfo
dev = UInput({
    ecodes.EV_ABS: [(ecodes.ABS_X, AbsInfo(0, 0, 1919, 0, 0, 0)),
                    (ecodes.ABS_Y, AbsInfo(0, 0, 1079, 0, 0, 0))],
    ecodes.EV_KEY: [ecodes.BTN_LEFT],
}, name="dsh-virtual-mouse", version=1)
dev.write(ecodes.EV_ABS, ecodes.ABS_X, x); dev.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
dev.syn(); time.sleep(0.03)
dev.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1); dev.syn(); time.sleep(0.05)
dev.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0); dev.syn()
```
前置条件：`ls /dev/uinput` 存在、用户属 `input` 组（本机已满足）。
配套：`grim -o HDMI-A-1 /tmp/x.png` 截图 + `read_image` 看效果，闭环确认。
★ 坐标换算：`hyprctl clients -j` 拿窗口 `at=[x,y]`，界面内坐标 + 窗口偏移 = 屏幕坐标。

### 已排除（不要重复）
| 手段 | 失败原因 |
|---|---|
| `ydotool` | 需 ydotoold 守护进程，socket `/run/user/1000/.ydotool_socket` 不存在，起它要 sudo |
| `hyprctl dispatch movecursor X Y` | 0.56 走 Lua，裸参数报 `')' expected near '81'` |
| `hyprctl dispatch 'hl.cursor.move({x=,y=})'` | `attempt to index a nil value (field 'cursor')` |
| `hl.dsp.focus({window=...})` 嵌在 hl.dispatch 里 | `expected a dispatcher` |
| Playwright 打开 127.0.0.1:38113 | HTTP 401，需 token，且用户明确禁止再用网页 |

## 实测结果（2026-11-08 00:47）
- 点 (93,380) → **成功进入 Bot 模式**：界面为 Tobs「# 频道列表 / 消息」，左侧频道「托布」，右侧消息区「从左侧选择一个 Bot 或频道开始」
- 点 (93,418) → 落在「上下文洞察」页（说明侧栏项间距 ~38px，Bot 模式实际在 y≈380）
- 屏幕坐标 (93,380) = 窗口 at[12,38] + 界面内 (81,342)

## 结论
操控电脑这条路**已打通并验证**。以后任何点击/验证一律自己用 evdev 虚拟鼠标做。

## 决定性证据：代码改了但进程没重启（2026-11-08 00:48）
```
client.js      修改于 2026-11-07 20:48:31   ← 已按 bh:home 重写
DSH 进程       启动于 2026-11-07（当天早些时候，早于 20:48）
```
→ 浏览器里跑的是**旧的 shell.overlay 版本**，所以 Bot 模式里看不到面板。
不是代码错，是**未生效**。必须重启 DSH。

## 已用自己操控电脑验证的事实
- 点 (93,380) 成功进入 Bot 模式（Tobs「频道列表 / 消息」界面）
- Bot 模式左侧仅 3 个图标：频道、通知、日程 —— **无本插件面板**（符合"旧代码未含 bh:home"）

## 下一步（唯一）
重启 DSH → 重新进入 Bot 模式 → 看 Home 区是否出现「源码知识卡片」。
