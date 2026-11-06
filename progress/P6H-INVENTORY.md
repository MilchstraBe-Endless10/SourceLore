# P6H 只读盘点 · 2026-11-06 22:33

## 模型身份（UNVERIFIED）
- DSH profile agent-default-model: provider=qodercn, model=dfmodel, reasoningEffort=max
- 会话系统上下文声明: deepseek-v4.1-flash
- provider 列表含 zw/glm-5.3-flash 但**未被选中**
- 阻断：DSH_HOME 读取被凭据保护拦截，无法读会话日志实际 model 字段
- **判定：矛盾，UNVERIFIED。不声称运行于 GLM 5.3 Flash。**

## DeepSeekBot 定性（已查实）
- 包 deepseekbot v1.6.0，现名 Tobs（原 DeepSeekBot）
- 是 DSH 插件 + agent preset，**不指定模型**
- preset 配置：45s 提问不阻塞、subagent 改 bot_subagent、挂 persona

## Git
- HEAD ea052d9 / branch main / 工作区干净
- **无 remote**（git remote -v 空）→ 不能声称已同步 GitHub

## 数据根三处
```
/tmp/p6b_real   602112 bytes  kb.db 存在    ← is-number(完整) + is-plain-obj(部分)
/tmp/p6f_real   442368 bytes  kb.db 存在    ← is-plain-obj(完整) + is-number(2条负例残留)
~/.sourcelore   不存在                       ← 默认根，空
```
目标：`/mnt/.../GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data`

## 迁移要点（待办）
- 不能直接覆盖复制 SQLite
- 需查是否有既有导入/导出/合并机制
- 不可变 A 层不得覆盖
- Blob 按 content_sha256 去重
- 不同仓库资产不得合并
- 二次迁移验证幂等

## 既有机制盘点（关键：决定迁移方式）
- **无 import_/merge_/migrate/export 子命令**（CLI 只有 status/repositories/help/analyze/inspect/history/query/card）
- 有 `src/storage/index_store.py: rebuild_index(store)` —— 索引重建能力存在
- `tsconfig_effective_config.merge_chain` 与本任务无关（配置链合并，不是知识库合并）

→ **结论：没有可复用的知识库合并机制。**
→ 迁移必须自己设计，最小化 + 可审计。
→ 但 rebuild_index 可复用：迁移后可用它重建索引行（这也是 D-67 历史补全的潜在正路）。

## D-67 修复正路（基于上面发现）
`rebuild_index` 若能从 assets payload 重建 index_rows（含 commit_sha），
则历史 13 条 verification 的索引可用它补全 —— **不新增机制，复用既有**。
恢复后第一件事：读 `index_store.rebuild_index` 实现，确认它是否填 commit_sha。

## ★★ 重大发现：rebuild_index 是定时炸弹（D-68）

`assets` 表 commit_sha **全部为 NULL**（所有类型 0/100%）：
```
captured_blob_content  4     有commit=0
claim_candidate       19     有commit=0
claim_verification    13     有commit=0
extracted_fact        22     有commit=0
repository_snapshot    1     有commit=0
```
但 `index_rows` 里 captured_blob_content/claim_candidate/extracted_fact 的 commit **是满的**。
→ 说明 index_rows 的 commit 是写入时**直接塞进索引行**的，不是从 assets 复制的。

而 `index_store.rebuild_index()` 的实现是：
```sql
SELECT ... commit_sha ... FROM assets   ← 读 assets 的 NULL
INSERT INTO index_rows(... commit_sha ...) VALUES(..., r["commit_sha"])  ← 写 NULL
```

**后果：执行 rebuild_index 会把当前正确的索引全部清成 NULL。**
这不是修复 D-67 的正路，反而是新缺陷 D-68 —— 一个「看起来该用、实际会毁数据」的机制。

## 因此 D-67 的正确修复路径必须改
原计划「用 rebuild_index 补全历史索引」**作废**。
必须先修 rebuild_index（或在修复前绝不调用它），
再单独解决 ingest_verification 不写 index commit 的问题。
