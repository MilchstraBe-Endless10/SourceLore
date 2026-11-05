# 自然语言自动触发 · 真实验收清单（NOT_VERIFIED）

本轮未创建独立 Harness 用户会话，故 `NATURAL_LANGUAGE_AUTO_TRIGGER` 保持 **NOT_VERIFIED**。
以下话术需在可观察的真实用户会话中逐条执行，并保留 Skill 发现与调用的原始证据。

| # | 话术 | 期望 Skill 行为 |
|---|---|---|
| 1 | 使用 SourceLore 查看我的 GitHub 知识库中已经保存的仓库 | 调 `sourcelore.py list`，返回已登记 repository_id |
| 2 | 查询这个仓库 README 的已登记标题，并显示证据 | 调 `query … --type content --path README.md`，返回标题+行号+Blob OID |
| 3 | 用 SourceLore 把这条内容知识生成卡片 | 调 `card --repository-id … --commit … --path …`，产出 HTML |
| 4 | 查一下这个仓库的依赖声明，别把声明当成已安装 | 调 `query … --type content --path package.json`，必须只答"已声明" |
| 5 | 比较这个仓库已保存的两个 Commit 的内容知识 | 两次按 Commit 查询，分别返回不同标题集合 |

判定规则：

- 必须是**真实 Harness 用户会话**，能看到 Skill 被自动选中并调用。
- CLI 主动执行不算自动触发。
- 模拟 Agent 文字不算证据。
- 任一条未通过 → 门禁保持 NOT_VERIFIED。
