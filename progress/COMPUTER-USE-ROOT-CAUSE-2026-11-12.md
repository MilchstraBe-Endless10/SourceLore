# computer-use 为什么不工作：完整根因（2026-11-12 16:12）

## 三个包的关系（读源码得出的，不是猜）

| 包 | 角色 | 提供什么 |
|---|---|---|
| `@deepseek-ai/dsh-computer-use` | **registry / 服务** | `ctx.computerUse` 服务本身。**不提供任何模型可见工具**（README 原文：本包不添加模型可见工具） |
| `@deepseek-ai/dsh-experimental-computer-use-cua-driver-native` | provider | Cua Driver 的原生工具（需显式启用） |
| `@botharness/computer` | provider | **真正的工具**：`get_desktop_state` / `click` / `type` / `press_key` / `hotkey` / `get_screen_size` |

provider 的工作方式：注入 `computerUse` 服务 → 调 `ctx.computerUse.register(...)` → 注册成功后才暴露工具。

## 之前为什么报错

`cordis.patch.yml` 第 40-43 行的 `- insert:` 段把 **registry + cua-driver provider 都插了一遍**，
而 `@botharness/computer` 也已经是 provider。结果：

```
community-desktop.experimental.computer-use: Error: service "computerUse" has been registered
community-desktop.experimental.computer-use-provider: Error: computer use provider "..." already registered
```

registry 被加载两次（内置一次 + insert 一次）→ 后一个抛错 → 服务不可用 →
跟着所有 provider 都注册失败 → **工具全程不出现**。

## 我犯的第二个错

第一次修复时我把 **registry 和 cua-driver provider 一起删了**。
结果 registry 没了 → `@botharness/computer` 无处注册 → 工具依然不出现。
（本次启动日志确实不再报错，但那是「没加载」而不是「加载成功」。）

## 正确的配置（已写入，需重启生效）

只加回 **registry**，**不要**加 cua-driver provider：

```yaml
- insert:
    - id: community-desktop.experimental.computer-use
      name: '@deepseek-ai/dsh-computer-use'
```

`--dump-config` 已确认最终配置现在同时含：
- `botharness-computer` → `@botharness/computer` (target: local)
- `community-desktop.experimental.computer-use` → `@deepseek-ai/dsh-computer-use`

备份：`~/sl_shots/cordis.patch.yml.bak`（原始）、`.step2.bak`（中间态）

## 重启后应该看到

模型工具表里出现 `computer` 系列工具。验证：
1. 调 `get_screen_size` 看返回
2. 调 `get_desktop_state` 拿截图
3. 用它 `click` 点 Bot 模式

## 为什么必须重启

`cordis.patch.yml` 是**宿主组合配置**，只在 DSH 进程启动时读取。
client.js 能热加载，宿主配置不能。这是架构限制，不是我没找对办法。
