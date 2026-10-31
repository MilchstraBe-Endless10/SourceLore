# SourceLore 平台兼容性

- 建立时间：2026-10-31
- 依据：M0-01 实测（见 `docs/environment-audit.md`）

本文回答一个问题：SourceLore 在这台机器、这个 DSH 版本、这个 Bot 上，**哪些能力真的成立，哪些不成立，哪些还不知道**。

状态口径：`PASS` / `FAIL` / `BLOCKED` / `NOT_RUN` / `DEGRADED` / `UNKNOWN`。不允许推断性通过。

---

## 1. 运行环境矩阵

| 维度 | 本机实测 | 要求 | 状态 |
|---|---|---|---|
| OS | Omarchy（Arch 系），Linux 7.2.8，x86_64 | Linux/macOS 可运行 Python CLI | PASS |
| Python | 3.14.8 | 3.11+ | PASS |
| venv | 可用 | 依赖隔离 | PASS |
| SQLite FTS5 | 可用 | M5 索引 | PASS |
| git | 2.56.0 | 快照与提交锁定 | PASS |
| node | v24.22.1 | Skill 脚本可选 | PASS |
| 磁盘 | 6.8T 可用 ext4 | 知识库本地存储 | PASS |
| GitHub API | 200，2.45s 直连 | 事实采集 | PASS |
| gh | 2.102.0，已登录 `repo` scope | M9 发布 | PASS |

## 2. DSH Skill 兼容性

| 能力 | 实测 | 状态 | 说明 |
|---|---|---|---|
| `@deepseek-ai/dsh-skill` 注册 | 是 | PASS | Provider 基础 |
| `@deepseek-ai/dsh-skill-filesystem` 注册 | 是 | PASS | 文件系统发现 |
| `@deepseek-ai/dsh-tool-skill` 注册 | 是 | PASS | 模型可调用的 skill 工具 |
| 用户级发现根 `<DSH_HOME>/skills` | 存在且生效 | PASS | `expert-team` 在 Catalog 中可见，37 个 skill |
| 项目级发现根 `<projectRoot>/.dsh/skills` | 已创建，尚未验证 | NOT_RUN | M6 安装后验证 |
| `customSkillDirs` 自定义根 | 未配置 | UNKNOWN | 本机不需要 |
| 递归扫描子目录 | 不支持 | — | 只发现 `<root>/<name>/SKILL.md` 直属 bundle，安装层级必须严格 |
| frontmatter 字段 | `name` / `description` / `whenToUse` | PASS | 以 `expert-team/SKILL.md` 实文件为格式依据 |
| `sourcelore` Skill 实际加载 | 未开始 | NOT_RUN | M6 里程碑 |
| `/sourcelore` 斜杠命令 | 未验证 | UNKNOWN | 若 UI 不支持，改提供已验证的自然语言调用方式，不伪称支持 |

### 关键推论

`<projectRoot>/.dsh/skills` 是本项目的**项目级**安装目标。但当前 Bot 会话的 cwd 是 Bot 自己的 memory 目录，**不是** SourceLore 项目根。这意味着：

- 若 SourceLore Skill 装在项目级根，只有在 cwd 位于 SourceLore 下的会话才能发现它
- Tobs Bot DM 会话（M7 的场景）cwd 不是 SourceLore，因此**用户级根 `<DSH_HOME>/skills` 才是 Tobs 能被触发的必由之路**
- M6 需要两条路都验证：项目级 + 用户级。这个结论由 cwd 实测差异推出，尚未在 M6 前执行验证，标 `UNKNOWN` 的部分在 M6 补齐

## 3. 模型与上下文兼容性

| 项 | 实测 | 影响 |
|---|---|---|
| 实际 route | `omniroute` / `workbuddy/deepseek-v4.1-flash` | 符合文档要求 |
| 上下文窗口 | **131072 tokens** | 最重要的工程约束 |
| 工具 schema 开销 | DSH 每请求携带全量工具定义 | 长会话会挤爆上下文 |

### 对协议的直接影响

文档要求「一次只处理一个小任务」，这里不是建议而是硬约束：

1. **禁止**把完整上游仓库或完整源文件批量读入上下文
2. 事实采集一律交给确定性脚本落盘，模型只读脚本产出的结构化摘要
3. 每次任务结束前必须把状态写进 `progress/`，因为上下文随时可能被压缩
4. 大文件用分页 `sed -n` 读取，不用一次性 `read` 全文件（本次审计已实际遇到此问题，处理方式已记录）

## 4. 工作区与授权兼容性

| 项 | 实测 | 状态 |
|---|---|---|
| Grant 路径与文档要求逐字一致 | 是 | PASS |
| Grant 为 `orchestratorWrite: true` | 是 | PASS |
| 授权范围 | 父目录，非全盘 | PASS |
| 本会话 cwd 是否在 Grant 内 | **否**（Bot memory 目录） | 需注意 |
| 直接 shell 写 Grant 路径 | 实测成功（创建骨架 + git init） | PASS |
| Assignment 使用 Grant | 未执行 | NOT_RUN（M7） |

## 5. 已识别的平台陷阱

1. **cwd ≠ 项目根**：会话 cwd 在 Bot memory 目录。所有 shell 命令必须显式 `cd` 到项目根或用绝对路径，绝不依赖相对路径。
2. **路径带括号与中文**：`Team_Flie(团队文件)`、`GitHub_Knowledge_Base(Gihub知识库)`。shell 里必须加引号，Python 里用 `pathlib` 而非字符串拼接。
3. **版本字符串不一致**：目录 `0.2.1-rc.3` 与 `dsh --version` 的 `0.2.1-rc.2` 不符。任何「按版本判断能力」的逻辑都不可靠，一律以实际行为为准。
4. **Skill 源码目录不是发现根**：`skills/sourcelore/` 是原件，必须安装到发现根并回读 Catalog 验证。
5. **131072 上下文**：见第 3 节。

## 6. 尚未验证的项（M6/M7/M9 补齐）

| 项 | 计划里程碑 |
|---|---|
| `sourcelore` 在 Catalog 可见 | M6 |
| `skill({name:"sourcelore"})` 真实加载完整内容 | M6 |
| `/sourcelore` 命令是否被 UI 支持 | M6 |
| Tobs Bot DM 内真实触发分析 | M7 |
| 新 Tobs 会话回查旧知识库 | M7 |
| 私有仓库创建与推送 | M9 |

---

**维护规则**：本文只记录实测结论。任何条目从 `NOT_RUN` / `UNKNOWN` 变为 `PASS` 时，必须附上验证命令与输出摘要。
