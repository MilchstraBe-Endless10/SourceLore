# F2-P0 · 运行时真实接入验证报告

产物：`F2_P0_RUNTIME_CAPABILITIES.json`（六项探测结构化记录）、
`F2_P0_ADAPTER_DECISIONS.md`（适配决策）、`tools/runtime_probe/`（探测实现）

**结论先行：接入路径成立，但六项中有四项只到 PARTIALLY_VERIFIED，两项 VERIFIED。**

---

## 1. 环境事实（实测，非假设）

| 项 | 实测值 | 证据 |
|---|---|---|
| Harness 包版本 | **0.2.1-rc.3** | `package.json` |
| CLI 自报版本 | 0.2.1-rc.2 | `dsh --version` |
| DSH_HOME | `~/.config/open-deepseek-harness-desktop/dsh-home` | 环境变量 |
| 默认 Skill 根 | `~/.agents/skills` | `resolveAgentsHome` 默认值 |
| **Skill 根覆盖变量** | **`DSH_AGENTS_HOME`** | `dsh-home-paths/src/index.ts:27` |
| Skill 插件 | `dsh-skill` / `dsh-skill-filesystem` / `dsh-skill-office` / `dsh-tool-skill` | web profile 配置 |
| `agents-anywhere` bridge | **存在但 disabled**，其 stateRoot 为空目录 | web profile 配置 |
| BotHarness 痕迹 | sessions 下有 `botharness-bots` 会话目录，**1246 个会话文件** | 文件系统 |
| 启动模型 | profile + patch 层（`$DSH_HOME/profiles`） | `dsh --help` |

**一个必须记下的接口：`config.customSkillDirs`**（`dsh-skill-filesystem/src/index.ts:168`）
—— Skill 根可显式指定，多个根可并存。这是比环境变量更精确的接入点。

---

## 2. 六项探测结果

| ID | 主题 | 状态 | 一句话 |
|---|---|---|---|
| **Y6-P1** | Skill 发现 | **VERIFIED** | 放入 `~/.agents/skills/` **立即**出现于 catalog，移除立即消失，**无需重启** |
| **Y6-P2** | 持久化状态 | **PARTIALLY_VERIFIED** | 本地文件跨进程可读；**未发现平台原生状态 API** |
| **Y6-P3** | 权限审批 | **PARTIALLY_VERIFIED** | 三档预设确凿；**Skill 内传递链路未实测** |
| **Y6-P4** | 任务恢复 | **PARTIALLY_VERIFIED** | 会话 id 可定位；**恢复后模型是否记得任务未证** |
| **Y6-P5** | 失败/超时/取消 | **VERIFIED** | 成功/失败/超时/未知四态可区分；**超时无残留副作用** |
| **Y6-P6** | 端到端调用 | **PARTIALLY_VERIFIED** | 发现→加载→执行→结果可校验成立；**headless 全链路被凭据阻断** |

---

## 3. P1：Skill 发现的真实证据

**不是"目录里有 SKILL.md"，是 catalog 真的变了。**

实测两次翻转：

1. `cp -r tools/runtime_probe/skill/sourcelore-probe ~/.agents/skills/`
   → 本会话 skill catalog **立即**出现 `sourcelore-probe`
2. `rm -rf ~/.agents/skills/sourcelore-probe`
   → catalog **立即**消失

**结论：DSH 侧是"目录扫描 + frontmatter description"，热重载，无需重启。**

同时验证了根路径确实影响发现：`DSH_AGENTS_HOME=/tmp/slprobe_agents` 时，装入该根的 Skill 同样可被发现机制读取。

**未验证的部分（如实标注）：** BotHarness 侧是否用**同一套**发现机制。两者的会话目录都在同一 `sessions` 根下，但 BotHarness 侧的 catalog 注入未单独实测。

---

## 4. P2：持久化——平台没有原生接口

**实测过程：**

```
write probe-key-1 "written-at-step1"   → {"op":"write","ok":true,"path":"probe-key-1.json"}   exit=0
read  probe-key-1（独立进程）           → {"op":"read","ok":true,"value":"written-at-step1"}  exit=0
write "../escape"                      → {"error":"PATH_ESCAPE_BLOCKED"}                     exit=3
```

**结论：** 本机**未发现**平台级跨会话状态存储接口（与 F1-C-D2 的 H-D 判断一致）。
验证到的是"本地文件系统持久化 + 自行做越界保护"，不是平台能力。

**这是设计依据，不是缺陷：** SourceLore 的 checkpoint 本来就该自建（Y-4 已裁定"独立分区、不入知识命名空间"）。

---

## 5. P3：审批——策略存在，传递链路未证

三档预设实测读到：

| 预设 | sandbox | approval |
|---|---|---|
| `read-only` | read-only | **never** |
| `workspace-write` | workspace-write | **ask** |
| `danger-full-access` | danger-full-access | **never** |

**必须说清楚：读配置 ≠ 验证审批链路。**
本会话审批提示已被禁用，`approval=ask` 的实际弹窗与"拒绝后是否阻断执行"**未实测**。

所以 P3 只能是 `PARTIALLY_VERIFIED`。**不能写 VERIFIED。**

---

## 6. P4：恢复——id 能定位，不等于记得任务

```
dsh headless --session-id session-does-not-exist
→ dsh: session "session-does-not-exist" does not exist; omit --session-id to start a new Session
```

`sessions` 目录按 cwd 分片持久化，1246 个会话文件证明恢复基础设施存在。

**关键区分（必须写进设计）：**
**任务可以恢复 ≠ 模型自动记得任务。** 会话回放提供的是上下文，不是权威状态。
SourceLore 必须靠**自建 checkpoint**（task_id / run_id / stage），不靠会话记忆。

---

## 7. P5：四态可区分，超时不等于没执行

| 态 | 命令 | 实测 |
|---|---|---|
| SUCCESS | `echo_tool.py ok` | exit=0，`sha256_12=2689367b205c`（可复算） |
| FAILED | `fail_tool.py 7` | exit=**7**，带 `intentional:true` |
| TIMEOUT | `timeout 2 slow_tool.py 5` | exit=**124** |
| UNKNOWN | 读不存在的键 | exit=**4**，`NOT_FOUND` |

**并且实测了最要紧的一条：超时后没有留下副作用残留。**

**必须保留的警示：** 这四个标签是**探测侧分类**，不是平台原生枚举。
**超时不能自动证明工具没有执行**——本次恰好没副作用，但这是被观测到的，不是被保证的。

---

## 8. P6：端到端——一半成立，一半被阻断

**成立的一半（真实证据）：**

1. Skill 被 catalog 发现 ✓
2. 加载返回 `skill_content`，并给出 base directory ✓
3. 按其指令执行 `echo_tool.py sourcelore-probe-token`
4. 输出 `sha256_12=8527197b4cb4`，**与独立复算完全一致** ✓
5. 结果写入受控 `artifacts/` 目录 ✓

**被阻断的一半（如实记录）：**

`dsh headless` 多次尝试全部失败于同一处：

```
dsh: MISSING_CREDENTIAL: llm-deepseek: no API key for provider route
"deepseek-official"; store DEEPSEEK_API_KEY through the credentials service
```

headless 合成配置的 provider 是 `deepseek-official`，而 web profile 用的是另一条路由。
**没有复制任何真实凭据到隔离环境，也没有修改全局凭据配置。**

所以端到端**未由 BotHarness 侧发起**，只能是 `PARTIALLY_VERIFIED`。

---

## 9. 本轮做了什么、没做什么

**做了：**
- 冻结哈希核验（`42841207…` 完全匹配）
- 六项探测，全部有真实命令与退出码
- 隔离探测 Skill（`tools/runtime_probe/skill/`）
- 四个确定性本地工具（echo / state / slow / fail）
- 结构化能力记录 + 适配决策

**没做（守住了边界）：**
- **未覆盖或重冻 Crosswalk**（哈希未变）
- **未改六份历史审计**
- **未安装任何第三方脚本**
- **未扩大 Harness 全局权限**
- **未改任何人工文档正文**
- **未部署对外服务**
- **未使用付费模型 API**
- **未执行被分析仓库的命令**
- **未实现 Collector/Storage/Facts/EC 引擎**
- **未创建正式 `skills/sourcelore/` 产品入口**

**测试 Skill 已清理**（`~/.agents/skills/sourcelore-probe` 已移除，catalog 随之消失）。

---

## 10. 需要自建的适配组件

| 组件 | 为什么必须自建 | 对应 canonical |
|---|---|---|
| **Checkpoint 存储** | 平台无原生状态接口（P2/P4） | SL-CAP-0071 |
| **恢复协调器** | 会话回放不等于任务恢复（P4） | SL-CAP-0071 |
| **授权令牌** | Skill 内审批传递未证（P3） | SL-CAP-0072 |
| **结果五态契约** | 平台无原生枚举（P5） | SL-CAP-0071 |
| **Skill 注册适配** | 复用现有机制，不自建；只需固定根与入口 | SL-CAP-0068 |

---

## 11. 真实失败、审批、恢复的表现

| 场景 | 实际表现 |
|---|---|
| 工具失败 | exit code 透传（7），带显式标记，**不吞错** |
| 超时 | 外部 `timeout` 返回 124，**无残留副作用** |
| 读取不存在 | 显式 `NOT_FOUND` + exit 4，**不伪装空结果** |
| 越界写 | `PATH_ESCAPE_BLOCKED` + exit 3，**拒绝不是成功** |
| 会话 id 不存在 | 显式报错并给出正确用法，**不静默新建** |
| 缺失凭据 | `MISSING_CREDENTIAL` 明确指名 provider route，**不降级为猜测** |

**这六条全部符合"失败必须显式"的设计要求。**

---

## 12. 本轮新增文件与修改范围

新增（全部在受控范围）：

```
docs/implementation/F2_P0_RUNTIME_PROBE_REPORT.md   （本文件）
docs/implementation/F2_P0_RUNTIME_CAPABILITIES.json
docs/implementation/F2_P0_ADAPTER_DECISIONS.md
tools/runtime_probe/README.md
tools/runtime_probe/skill/sourcelore-probe/SKILL.md
tools/runtime_probe/scripts/{echo,state,slow,fail}_tool.py
tools/runtime_probe/artifacts/                       （探测证据）
tools/f2p0_verify.py                                 （自动验证入口）
```

未修改：`docs/fusion/**`（含冻结 Crosswalk）、`progress/UPSTREAM-*-audit.json`、
人工文档、`src`/`tests`/`schemas`/`skills/sourcelore`。

---

## 13. F1-D 冻结哈希

**`42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b` —— 未变。**

---

## 14. F2-P1 的最小可执行起点

1. **自建 checkpoint 存储层**：最小 schema（task_id / run_id / stage / checkpoint_ref / attempt_count），
   按 Y-4 独立分区，**不入知识命名空间**。
2. **跨进程恢复演练**：写 checkpoint → 杀进程 → 新进程读回 → 校验 `expected checkpoint_version`。
3. **补测 CANCELLED**：SIGTERM 中断，确认状态为 CANCELLED 而非 UNKNOWN。
4. **补测 `approval=ask`**：在审批可用的隔离会话中验证"拒绝即阻断"。
5. **端到端复跑**：用已有凭据的 provider 或补齐 headless 凭据，由 BotHarness 侧发起一次。

**F2-P1 不得在同一轮内自动开始。**
