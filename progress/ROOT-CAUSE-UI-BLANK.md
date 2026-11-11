# Bot 面板白屏根因（2026-11-11 自查确认）

## 根因

`@botharness/ui` 的 `Welcome` 组件原本用 **`react_jsx_runtime.jsx()`** ——
这是 JSX runtime 的**单子元素**版本，严格只接受一个 `children`。

我在给 Welcome 加 `BhHomeSlot` 槽位时，把 children 写成数组：

```js
// ❌ 崩溃：jsx() 收到数组 children
react_jsx_runtime.jsx("div", { children: [A, B] })

// ✅ 正确：多子元素必须用 jsxs()
react_jsx_runtime.jsxs("div", { children: [A, B] })
```

`jsx()` 内部对 children 做单节点校验，收到数组直接抛错 →
React 渲染中断 → 整个 Bot 面板空白（连「从左侧选择」空状态都不显示）。

## 为什么排查了很久

- 回滚 UI 包 → 面板恢复；打补丁 → 面板空白。现象指向补丁，但我误判为
  「卡片组件抛错」，于是给卡片加错误边界，实际崩在更外层。
- 中间一度怀疑坐标点错、缓存、Bot 数据为空 —— 都不是。

## 附带发现的两个既有 bug

1. 原版 `Welcome` 的 `className` 写了**两遍**（`"bh-content"` 和 `"bhx78zum5..."`），
   这是上游原有的重复 prop，一并修正。
2. 我的 `SafePanel` 写成 `React.createElement`（大写），但插件作用域内只有
   `react`（小写，来自 `require("react")`）→ 错误边界本身也会崩。

## 验证方式

修好后 Bot 面板恢复显示「从左侧选择一个 Bot 或频道开始」，
说明 Welcome 正常渲染、BhHomeSlot 槽位已插入且不破坏布局。

## 教训

改第三方压缩产物时，`jsx` / `jsxs` 的区别必须核对；单子变多子一定要换函数。
否则整个宿主面板白屏，而错误发生在被改的框架层，看起来像「插件坏了」。
