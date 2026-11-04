# SourceLore 运行时探测（F2-P0）

**这是测试资产，不是产品。** 不得作为已获准公开分发的 Skill。

- `skill/` — 隔离的探测 Skill（放在临时 HOME 的 `~/.agents/skills/` 下才发现）
- `scripts/` — 确定性本地工具（纯 stdlib，无外部依赖）
- `artifacts/` — 探测产出的状态/记录（受控目录，可清理）

隔离原则：所有运行时实验使用**临时 HOME 副本**，不触碰真实
`~/.config/open-deepseek-harness-desktop/` 的持久配置。
