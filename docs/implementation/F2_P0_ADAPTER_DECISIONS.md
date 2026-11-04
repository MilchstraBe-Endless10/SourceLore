# F2-P0 · 适配决策

本文件记录：基于实测，SourceLore 必须自建什么、复用什么、以及为什么。

**总原则：不把自建方案伪装成平台原生能力；也不因为平台缺某项能力就判定项目不可做。**

---

## AD-1 · Skill 注册：复用，不自建

**决策：复用 `dsh-skill-filesystem` 的目录发现机制，不自建注册表。**

依据（F2-P0 P1 实测）：
- `~/.agents/skills/<name>/SKILL.md` 放入即被发现，无需重启
- 移除即消失
- 根路径可由 `DSH_AGENTS_HOME` 覆盖，或由 `config.customSkillDirs` 显式指定

**Why not 自建：** 平台已经有热重载的发现机制，自建一套会与平台重复且更差。

**落地方式：** 正式 `skills/sourcelore/` 只需满足两件事：
1. `SKILL.md` 的 frontmatter 有 `name` + `description`（触发语）
2. 入口薄、细节按需加载到同目录子文件（SL-CAP-0068 已定）

**未验证风险：** BotHarness 侧是否共用同一机制。若不同，需在 F2-P1 补测。

---

## AD-2 · Checkpoint：必须自建

**决策：SourceLore 自建 checkpoint 存储与恢复协调，不依赖平台。**

依据（P2 + P4 实测）：
- 未发现平台级跨会话状态 API（H-D 仍 UNVERIFIED）
- `sessions` 有 1246 个会话文件，但那是**会话回放日志**，不是任务检查点
- `--session-id` 只能定位会话，**不能证明恢复后模型记得任务**

**关键区分（写进实现约束）：**
> **会话回放提供上下文，不提供权威状态。**
> 任务能否恢复，只以 checkpoint 记录为准。

**最小 schema（对应 SL-CAP-0071 的逻辑字段）：**

```
checkpoint {
  task_id, run_id, workspace_id, subject_id,
  requested_action, current_stage,
  checkpoint_ref, input_snapshot_ref,
  authorization_scope, attempt_count, error_category,
  checkpoint_version        ← CAS 比较基准
}
```

**物理位置（对应 Y-4 裁定）：** 独立分区，**不得进入知识资产 A/B/C 层命名空间**。

---

## AD-3 · 授权令牌：必须自建

**决策：每次写操作要求显式 `authorization_scope`，缺失或越界即拒绝。**

依据（P3 实测）：三档预设存在，但 **Skill 内部的审批传递链路未验证**。
不能假定 `approval=ask` 会覆盖到 Skill 自己发起的写操作。

**实现约束：**
- 写操作必须携带 scope，scope 必须匹配目标路径
- 不匹配 → 显式 `DENIED`，**不得降级为空结果或静默成功**
- 人工审批类操作（发布、对外）**不得由 Agent 自批**（SL-CAP-0053 P-3/P-4）

**与平台的边界：** 平台的三档预设仍生效（外层），SourceLore 的自建令牌是内层。两层独立，不互相替代。

---

## AD-4 · 结果契约：必须自建五态

**决策：SourceLore 定义自有结果五态，不依赖平台枚举。**

依据（P5 实测）：`SUCCESS / FAILED / TIMEOUT / UNKNOWN` 四态在探测侧可区分，
但那是**我们自己的分类**，不是平台原生输出；`CANCELLED` 尚未实测。

**五态定义：**

| 态 | 判据 | 禁止的混淆 |
|---|---|---|
| `SUCCESS` | 进程 exit 0 且输出可校验 | — |
| `FAILED` | 进程非零退出 | — |
| `TIMEOUT` | 外部超时终止 | **不得推断为「未执行」** |
| `CANCELLED` | 主动中断（**待实测**） | 不得与 TIMEOUT 合并 |
| `UNKNOWN` | 无可判定证据 | **不得默认成 SUCCESS 或 FAILED** |

**硬规则：超时不能自动证明工具没有执行。** 本次实测恰好无副作用残留，
但那是被观测到的单次事实，不是平台保证。

---

## AD-5 · 模型路由：环境依赖，非设计依赖

**决策：不把任何 provider 或凭据写死为架构前提。**

依据（P6 实测）：`dsh headless` 因 `MISSING_CREDENTIAL`（provider route `deepseek-official`）失败；
而运行中的 web profile 用的是另一条路由。

**处理方式：**
- **未复制任何真实凭据到隔离环境**，也未改全局凭据配置
- 记录为**环境阻塞**，不是设计缺陷
- F2-P1 复跑时用已有凭据的 provider，或由用户补齐 headless 凭据

**约束：** SourceLore **不得**要求任何特定供应商；模型只经 SL-CAP-0069 的单一适配接口接入。

---

## AD-6 · 探测产物的定位

`tools/runtime_probe/` 是**测试资产，不是产品**。

- 不得作为已获准公开分发的 Skill
- 探测 Skill 已从 `~/.agents/skills/` 清理
- `artifacts/` 中只保留证据文件，可安全删除

---

## 决策汇总

| 组件 | 复用 / 自建 | 理由 |
|---|---|---|
| Skill 发现与注册 | **复用** | 平台已有热重载发现 |
| Skill 入口结构 | **复用 + 遵守 0068** | 薄入口 + 按需加载 |
| Checkpoint 存储 | **自建** | 平台无原生状态 API |
| 恢复协调 | **自建** | 会话回放 ≠ 任务恢复 |
| 授权令牌 | **自建** | Skill 内审批传递未证 |
| 结果五态 | **自建** | 平台无原生枚举 |
| 模型适配 | **复用 0069 接口** | 不绑定供应商 |
