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
