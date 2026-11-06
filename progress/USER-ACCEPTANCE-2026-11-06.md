# 用户使用验收 · 2026-11-06 22:14

## 环境
安装版 CLI：`~/.agents/skills/sourcelore/scripts/sourcelore.py`
status 报 project_root = 工程 src（LOCAL_DEV_LINKED_INSTALL 成立）

## 验收记录

| 阶段 | 命令 | 退出码 | 结果 |
|---|---|---|---|
| 一 | `--help` | 0 | 8 子命令齐备 |
| 二 | `status` | 0 | db_exists=false（默认根 ~/.sourcelore 不存在）|
| 二 | `repositories --data-root /tmp/p6b_real` | 0 | 1 仓库 24313173 |
| 二 | `repositories --data-root /tmp/p6f_real` | 0 | 2 仓库（24313173 仅 2 claim 残留）|
| 三 | `query 24313173 --type content --path README.md` | 0 | SUPPORTED，4 claim / 3 verif，net=0 |
| 三 | `query 38923193 --type code --path index.js` | 0 | FOUND，2 sym / 2 export / 6 fact，net=0 |
| 四 | `card 24313173 --path README.md` | 0 | 16603B README_CONTENT_CARD，net=0 |
| 四 | `card 38923193 --path index.js --code` | 0 | 6240B JAVASCRIPT_SOURCE_CARD，net=0 |

## 发现的可用性问题（三条，非严重缺陷）

**U-1 默认数据根不存在。** `~/.sourcelore/` 从未创建，
所有真实知识都在 `/tmp/p6b_real` / `/tmp/p6f_real`。
新用户开箱即用会看到「知识库尚未建立」。且 /tmp 在重启后可能被清空。

**U-2 repositories 不返回仓库名。** 只有 repository_id，
`repository` 字段为 None。用户看到 `24313173` 无法知道是哪个仓库。

**U-3 两个仓库分散在不同 data_root。** is-number 在 p6b_real、is-plain-obj 在 p6f_real，
没有一个 --data-root 能同时看到两个完整仓库。
p6f_real 里的 24313173 只有 2 条跨仓库负例 claim 残留。

## D-67 在真实 CLI 上复现
`query 38923193 --type code --path index.js` 返回 4 条事实，
display_level 全为 OBSERVED_SOURCE_FACT，0 条 SUPPORTED_SOURCE_CLAIM。
与数据库内 4 条 supported verification 矛盾。读回链路确实断开。

## 卡片内容抽检
源码卡包含 isPlainObject / 666df7c1 / 92555c3d / js_function / distribution_allowed，
不含 SUPPORTED 也不含 OBSERVED —— 卡片未区分「已观察」与「已验证」，
与任务书 §9 要求的两个层级说明不符。
