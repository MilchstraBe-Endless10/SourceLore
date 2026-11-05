# 自然语言自动触发验收清单

**状态：NOT_VERIFIED。** 本轮会话内无法自发产生"独立用户新会话"来观察自动触发。
以下清单需在新的 Harness 会话中由用户实际执行并回传日志。

## 前置条件

- 新会话里 `sourcelore` 应出现在 available_skills 列表中（P5A 已证实）
- 会话工作目录可任意；Skill 不依赖 cwd

## 五个场景

### 场景 A — 查看已有知识库

输入原文：
```
帮我用 SourceLore 查看之前建立的 GitHub 知识库。
```
观察点：
- [ ] Agent 是否自动加载 sourcelore（而非凭记忆回答）
- [ ] 是否执行 `sourcelore.py repositories`
- [ ] 是否返回真实 repository_id 列表

### 场景 B — 分析并查已有知识

输入原文：
```
分析一下这个 GitHub 仓库，看看它有没有已保存的知识。
```
观察点：
- [ ] 是否先查本地（repositories / 缓存）再决定联网
- [ ] 是否产生了不必要的 GitHub 请求

### 场景 C — 查证据与 Commit

输入原文：
```
查询这个仓库 README 的证据和对应 Commit。
```
观察点：
- [ ] 是否执行 `query --type path --path README`
- [ ] 是否输出真实 commit_sha 与 evidence_refs

### 场景 D — 生成卡片

输入原文：
```
把这条仓库知识生成卡片。
```
观察点：
- [ ] 是否执行 `card ...`
- [ ] 是否返回真实 html_path
- [ ] 是否说明 distribution_allowed=false

### 场景 E — 对比两版本

输入原文：
```
对比这个仓库已经保存的两个版本。
```
观察点：
- [ ] 是否执行 `query --type version --compare-commit`
- [ ] 若只有 1 个版本，是否如实说"只有一个版本"
- [ ] 是否避免虚构祖先关系

## 必须记录的字段

每条记录：

| 字段 | 说明 |
|---|---|
| 输入原文 | 原样 |
| Skill 是否出现在工具调用路径 | 是/否 |
| 是否真实读取 SKILL.md | 是/否 |
| 是否调用 SourceLore CLI | 命令原文 |
| CLI 退出码 | 数字 |
| 是否返回真实资产 | ID 列表 |
| 是否产生不必要 GitHub 请求 | 是/否 |
| 是否把证据不足说成确定结论 | 是/否 |

## 判定

- 任一条"是否把证据不足说成确定结论 = 是" → 该场景 **FAIL**
- 全部场景都真实调用 CLI 且无编造 → `NATURAL_LANGUAGE_AUTO_TRIGGER = DONE`
- 未测试 → 保持 **NOT_VERIFIED**（不得因"Agent 说自己调用了"而标 DONE）
