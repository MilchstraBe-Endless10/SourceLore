# 突破：注册链路全线打通（2026-11-12 01:05）

## 用真实操作拿到的证据链（每一步都有屏幕/标题证据）

| 步骤 | 证据 | 结论 |
|---|---|---|
| apply 是否执行 | 窗口标题 `SL-apply-2026-11-10-1030` | ✅ 执行了 |
| dockPanels 是否可见 | 标题 `SL-svc[dockPanels,botPresentation,channelSidebar,profileCards,slots,layout,shortcuts,locale,uiWorkspace,workspaces]` | ✅ 可见且非 null |
| register 是否成功 | 标题 `SL-regFAIL-duplicate Dock panel: sourcelore:repo-cards` | ✅ **成功**（duplicate 恰恰证明前一次注册还在注册表里） |
| open 是否成功 | 标题 `SL-OPEN-ok cur=null` | ✅ 调用成功，无异常 |

**结论：`sourcelore:repo-cards` 面板已注册到 Tobs 的 dockPanels 注册表，
并且 `open()` 已被调用。**

## 之前为什么会误判「没注册」

1. `tryRegister` 的 catch 吞掉异常，只写 logger，界面上看不到
2. 诊断标题把注册结果覆盖掉了
3. 一直以为 `inject` 声明导致 pending —— 那确实是另一个真问题（已修复），
   但不是注册失败的原因

## 真正踩过的坑（都已修复）

1. **宿主 index.js 与 client.js 的 `exports.inject` 都不能声明 `dockPanels`**
   → 声明会让宿主永久 `pending (waiting for service: dockPanels)`，整个插件不挂载
   → 两处都必须 `= []`
2. **`/tmp/mouse.py` 根本不存在** —— 之前所有「点击」都在跑不存在的脚本
3. **`hl.dsp.cursor.click` 不是有效 dispatcher** —— 光标能移动，但从未按下
4. **Ctrl+Shift+R 的键码**：R 是 19（46 是 C，按成了 Ctrl+C）
5. **打 `@botharness/ui` 补丁是错的路** —— Tobs 升级即覆盖（11-11 19:57 升 1.6.1，
   md5 f12479a2→1f71cba1，BhHomeSlot 归零）

## 当前唯一未完成的验证

面板已注册并 open，但**视觉上还没在 Bot 模式里看到它**。

界面状态辨析（重要）：
- 点左侧「Bot 模式」(105,331) 后，左栏工作区出现 **Tobs(1) / Tob(1)**
- 但要看到「# 频道列表 / 消息」那一层，还需要进入具体频道
- `/tmp/e1.png` 是唯一一次真正进入 Bot 模式的截图（当时界面被远程协助浮层遮挡）

## 可复用的操作命令（已全部验证有效）

```bash
export WAYLAND_DISPLAY=wayland-1 YDOTOOL_SOCKET=/run/user/1000/.ydotool_socket
pgrep ydotoold >/dev/null || nohup ydotoold --socket-path=/run/user/1000/.ydotool_socket --socket-own=1000:1000 &
A=0x55a5d9b01af0
hyprctl dispatch "hl.dsp.focus({ window = \"address:$A\" })"
ydotool mousemove --absolute -x 105 -y 331 && ydotool click 0xC0   # 点 Bot 模式
ydotool key 29:1 42:1 19:1 19:0 42:0 29:0                          # Ctrl+Shift+R（R=19）
grim -o HDMI-A-1 /tmp/x.png
magick compare -metric AE a.png b.png null:                        # 判界面是否变化
magick x.png -crop 1300x30+300+35 +repage -resize 120% t.png       # 裁标题栏读诊断
```

## 下一步

进入 Bot 模式的具体频道（点 Tobs 后选一个频道），
右侧停靠栏应出现「仓库知识卡片」面板。
若仍不可见，查 `reg.open` 是 async 还是需要等 Tobs 的 dockview 就绪。
