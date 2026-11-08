# slot 机制最小复现结论（2026-08-08 17:53 静态验证，非猜测）

## 权威源码
`runtime/0.2.1-rc.3/node_modules/@deepseek-ai/dsh-client-ui-renderer/src/client/`
- `registry.ts`（SlotRegistry 服务层）
- `scoped-slots.tsx`（props 组装）
- 该包**带完整 TypeScript 源码**，可直接读，不必反编译 minified。

## 三条硬事实（逐行源码证据）

### ① ctx 级 renderSlot 只能渲染 root
`registry.ts:382-388`
```ts
renderSlot<K>(key: K, owner: OwnerOf<K>) {
  if (key !== 'root')
    throw new Error(`ctx-level renderSlot only renders 'root' (got "${key}");
      child slots render through the component props face`)
```

### ② renderSlot 只发给「有 children 声明的注册条目」
`scoped-slots.tsx:568-570`（standardKit 内）
```ts
if (entry.children !== undefined) {
  kit['renderSlot'] = boundRenderSlot(host, entry)
  if (Object.values(entry.children).some(spec => spec.kind === 'chain'))
    kit['renderSlotChain'] = boundRenderSlotChain(host, entry)
  ...
}
```
→ **只有 ctx.slots.register(...) 的组件 props 里才有 renderSlot**
→ 普通函数组件（如 @botharness/ui 的 `Welcome`）**永远拿不到它**

### ③ 绑定校验在 entry.children 上，失败即抛
`scoped-slots.tsx:69-83` boundRenderSlot
```ts
const declared = entry.children?.[key]
if (declared === undefined)
  throw new SlotOwnershipError(`slot '${key}' is not declared by this entry's children`)
```
绑定 per-entry 缓存（`WeakMap<StoredEntry, RenderSlotBinding>`），entry 销毁即失效。

## ★ 对我上次补丁的判决
我上次给 `Welcome` 加 `renderSlot` 参数、在 main 条目声明 `children`，
**从原理上不可能工作**：
- `renderSlot` 进的是 **main 条目注册组件的 props**（MobileBotPanel → BotPanel → BotMain → BotMainContent）
- `Welcome` 是 BotMainContent 内部调用的普通组件，它不在这条 props 链上
- 我加的 `renderSlot` prop 传参只是传 `undefined`，`extra` 恒为 null；但把单 child 改成数组等其他改动动了渲染结构 → 导致 Bot 面板空白

## 正确做法（若继续）
把**卡片组件本身注册成 main 条目的一个 child slot**，而不是改 Welcome 内部：
1. main 条目已声明 children → 它的组件（BotPanel 链）能拿到 renderSlot
2. 需要让渲染 Bot 主页的那一层真正调用 `renderSlot('botharness.bot.home', owner)`
3. 但 Bot 主页空白态是由 `Welcome` 直接返回的，不经 slot → 仍要改 Welcome
→ 结论：**必须改 `Welcome` 让它接受 `renderSlot` 并调用**，
   而 `renderSlot` 只能从 BotMainContent 的 props 逐层透传下来
   （BotMainContent 是 main 条目的组件树内，能拿到）。

即：`BotPanel(props) → BotMain(...props) → BotMainContent(...props) → Welcome(renderSlot)`
这条链是可行的 —— props 里有 renderSlot，只是组件签名把多余属性丢掉了。
上次失败点在于**改了 children 数组结构和 Welcome 内部实现**，不是这条链本身。
