# Bot 模式主页槽位：打通（2026-11-08）

## 结论
卡片**已经出现在 Bot 模式主界面内**。截图实证：左侧「# 频道列表 / 托布」旁的消息区顶部，
渲染出「源码知识卡片 · jonschlinkert/is-number · 0 张」+「导出到 Obsidian」「刷新」按钮。

## 实现方式（两层）
1. **UI 侧补丁**（`@botharness/ui/lib/client.js`，非破坏性）：
   在 `Welcome` 组件里插入 `BhHomeSlot`，读取 `window.__bhHomeSlots__`。
   数组为空时 `BhHomeSlot` 返回 null，`Welcome` 外观与原来**逐像素一致**。
   ```js
   function BhHomeSlot() {
     const [rev, setRev] = useState(0);
     useEffect(() => { window.addEventListener("bh-home-slot", onChange); ... }, []);
     const list = window.__bhHomeSlots__;
     if (!Array.isArray(list) || !list.length) return null;
     return jsx("div", { "data-bh-home-slots": list.length,
       children: list.map(s => jsx(s.component, {}, "bh-home-" + s.id)) });
   }
   ```
   Welcome 的 children 从单个 `PanelEmptyState` 变成
   `jsx(Fragment, { children: [jsx(BhHomeSlot,{}), jsx(PanelEmptyState,{...})] })`。

2. **插件侧**（`plugin/dsh-sourcelore-cards/client.js`）：
   ```js
   var SLOT_KEY = "__bhHomeSlots__";
   function apply() {
     var list = window[SLOT_KEY] || (window[SLOT_KEY] = []);
     if (list.some(x => x && x.id === ID)) return;
     list.push({ id: ID, component: SourcelorePanel });
     window.dispatchEvent(new window.Event("bh-home-slot"));
   }
   exports.inject = ["slots"];   // 不再需要 dockPanels
   ```

## 为什么不是 dockPanels
`dockPanels.register()` 会把 panel 的 `entry` 强制置为 `undefined`，
而渲染侧只认 `panel.entry !== void 0`；且一旦有注册，
`registeredDockPanels ?? dockEntryPanels` 会把原生右侧面板整体顶掉。
详见 progress/DOCKPANEL-DEADEND.md。

## 验收状态
- [x] 卡片渲染在 Bot 模式主界面（截图 /tmp/bot_ok.png）
- [x] Bot 原生界面（频道列表、消息区、右侧面板）不受影响
- [x] 无插件注册时 Welcome 与原来一致（BhHomeSlot 返回 null）
- [x] 热更新生效：改 client.js 后不重启 DSH，HMR 自动换包（rev 变化实证）
- [ ] 卡片数据填充（当前首个仓库 is-number 默认路径无 claims，显示 0 张）

## 风险与回滚
- UI 补丁位于 `~/.config/.../node_modules/@botharness/ui/lib/client.js`，
  **DSH 升级会覆盖它**。原版备份：`/tmp/botharness-ui-client.js.orig`（md5 f12479a21c34）。
- 回滚：`cp /tmp/botharness-ui-client.js.orig <该路径>`，热更新即恢复。
- 补丁后 md5：92f358e9243c1d564823197c69702dd3。
