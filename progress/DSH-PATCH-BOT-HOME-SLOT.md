# @botharness/ui 补丁：新增公开槽位 `botharness.bot.home`

★ 用户明确授权改 `@botharness/ui` 源码（2026-11-08 10:04，原话「直接改 @botharness/ui 源码，新增一个公开 slot」）

## 改的文件
`~/.config/open-deepseek-harness-desktop/dsh-home/profiles/web/node_modules/@botharness/ui/lib/client.js`
（v1.6.0，7911535 bytes，1 links 真实目录 —— 重装包会覆盖，届时需重打补丁）
备份：`/tmp/botharness-ui-client.js.orig`（md5 f12479a21c3498c0ff8d370277a99d51）

## 四处改动（全部带 DSH-PATCH 注释便于重打）
1. `const WELCOME_SLOT = "botharness.bot.home";   // ← DSH-PATCH: 新增公开槽位`
2. `function Welcome({ state, t, renderSlot })` —— 内层从 1 个 child 改为 children 数组，
   末尾追加 `extra = renderSlot === void 0 ? null : renderSlot(WELCOME_SLOT, {})`
3. main slot 条目（`name:"main", key:PANEL_ID`）增加
   `children: { "botharness.bot.home": { kind: "list", scope: "root" } },`
   —— 这是 slot 嵌套关键：children 声明让 renderSlot 自动注入到宿主组件 props
4. props 透传：`BotMainContent(... nativeChatT, renderSlot, t = zhTranslate)`
   两处 `jsx)(Welcome, { state, t })` → `{ state, renderSlot, t }`
   （`BotMain({ appearance, prefs, workspace, ...props })` 用 ...props 已自动透传，无需改）

验证：`node --check` 通过；grep 确认 WELCOME_SLOT 1 处、children 1 处、Welcome 签名 1 处、
BotMainContent 签名 1 处、两处调用均含 renderSlot。

## 插件侧
`plugin/dsh-sourcelore-cards/client.js` 改为
```js
var HOME_SLOT = "botharness.bot.home";
ctx.slots.inject(HOME_SLOT, () => ctx.slots.register(
  { name: HOME_SLOT, id: "dsh-sourcelore-cards", order: 40, label: "源码知识卡片" }, Panel))
```

## 效果
Bot 模式主页（未选中 Bot/频道时的欢迎区）会显示「源码知识卡片」面板。

## 重打补丁方法（升级后）
```bash
cp /tmp/botharness-ui-client.js.orig <新包>/lib/client.js   # 仅当版本相同才适用
# 或按上面四处改动重新 apply
```

## 风险与回滚
- 只加代码不改既有逻辑，`renderSlot === void 0` 时 extra 为 null，无插件时行为与原来一致
- 回滚：`cp /tmp/botharness-ui-client.js.orig <该文件>`

## ★ 2026-11-08 12:25 回滚：补丁导致 Bot 面板空白
### 现象
打完补丁并重启（12:20，PID 58367）后，点「Bot 模式」：
- 先显示 DSH 首页「探索未至之境」，再变成**空白**
- 原本应显示 Tobs「# 频道列表 / 消息」界面
→ Bot 面板没能挂载。

### 回滚动作（已完成）
```
cp /tmp/botharness-ui-client.js.orig  → @botharness/ui/lib/client.js
md5 恢复 f12479a21c3498c0ff8d370277a99d51，node --check OK，botharness.bot.home 0 处
```
插件侧 `client.js` HOME_SLOT 已退回官方 `botharness.settings.section`。

### 排除的误判（重要，别再怀疑）
`dsh: warning: 2 entries did not activate` 在日志里从 **2026-11-01** 起每次启动都有
（10221 / 10277 / 10329 / 10378 / 10426 / 10472 行），
真实原因是 `computer use provider "botharness-computer" is already registered`
—— **既有问题，与本次补丁无关**。

### 补丁为什么失败（推断，未逐字验证）
`children: { "botharness.bot.home": {kind:"list", scope:"root"} }` 很可能要求
宿主组件里的 slot 必须由 `ctx.slots.register` 注册的「条目」承载，
而 `Welcome` 只是个普通组件、不是注册条目；
`renderSlot` 注入到 props 的路径我并未真正验证（只是推断 ...props 会透传）。

### 若要重试的正确顺序
1. 单独验证「children 声明 → renderSlot 自动进 props」这一步是否成立
   （写最小复现，不能靠读代码猜）
2. 再改 Welcome
3. 一次只改一处，每步重启验证
