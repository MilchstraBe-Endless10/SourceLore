# SourceLore 环境审计（M0-01）

- 审计时间：2026-10-31T09:42:01+08:00 ~ 2026-10-31T09:48:00+08:00
- 执行者：Tobs PersonaBot Orchestrator（DeepSeek-V4.1 Flash）
- 审计方式：全部为真实命令实际执行，输出逐条记录；未执行的项一律标 `NOT_RUN`，无法判定的标 `UNKNOWN`
- 结论：**PASS**（无阻塞项）

---

## 1. 会话与平台身份

| 项目 | 实测值 | 判据 |
|---|---|---|
| 会话 ID | `botharness-4540a7d7-0399-4ccb-926e-c3b1dec39ab7` | 运行时上下文注入 |
| 当前工作目录（会话） | `/home/arlune_innersea/.config/open-deepseek-harness-desktop/dsh-home/botharness/bots/bot-ec1834997cac4e88b40966a5ddec4586/memory` | 运行时上下文 |
| 项目根目录 | `/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore` | 用户指定，非会话 cwd |
| DSH_HOME | `/home/arlune_innersea/.config/open-deepseek-harness-desktop/dsh-home` | 环境变量 |
| DSH_PROFILE | `web` | 环境变量 |
| DSH_PROFILE_DIR | `<DSH_HOME>/profiles/web` | 环境变量 |
| DSH_WEB_URL | `http://127.0.0.1:40387` | 环境变量 |
| DSH 实现根 | `/home/arlune_innersea/.config/open-deepseek-harness-desktop/runtime/0.2.1-rc.3/` | 运行时上下文 |
| `dsh --version` | `0.2.1-rc.2` | 实际执行 |
| `dsh` 可执行路径 | `<runtime>/0.2.1-rc.3/package-runtime/bin/dsh` | `command -v dsh` |

> 注意：安装目录标 `0.2.1-rc.3`，而 `dsh --version` 自报 `0.2.1-rc.2`。这不是错误，是版本字符串与实际包目录不一致，记录在案，不影响开发；本项目的 DSH Skill 接入验证（M6）以真实 Catalog 与真实加载结果为准，不以版本号推断。

## 2. 操作系统与硬件

| 项目 | 实测值 | 命令 |
|---|---|---|
| 内核 | `Linux Starwhisper 7.2.8-9-omarchy #1 SMP PREEMPT_DYNAMIC Sat, 17 Oct 2026 22:09:33 +0000 x86_64` | `uname -a` |
| 发行版 | Omarchy，`ID=omarchy`，`ID_LIKE=arch`，`BUILD_ID=4.0.6` | `/etc/os-release` |
| 架构 | x86_64 | `uname -a` |
| 系统时钟 | `2026-10-31T09:42:01+08:00`（Asia/Shanghai） | 运行时上下文 |

## 3. 用户与权限

```
uid=1000(arlune_innersea) gid=1000(arlune_innersea)
groups=1000(arlune_innersea),5(tty),992(input),995(audio),998(wheel)
```

普通用户 `arlune_innersea`，属 `wheel` 组。本次 M0 全部操作均以普通用户完成，**未使用 sudo**。

## 4. 目标父目录与挂载

```
BASE=/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)
realpath: /mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)
```

`realpath` 与配置路径完全一致，无符号链接跳转。

```
Filesystem                                        Type  1K-blocks     Used  Available Use% Mounted on
/dev/mapper/Server_Data_Center-Server_Data_Center ext4 7739012352 51436172 7297476420   1% /mnt/Server_Data_Center
```

```
TARGET                  SOURCE                                            FSTYPE OPTIONS
/mnt/Server_Data_Center /dev/mapper/Server_Data_Center-Server_Data_Center ext4   rw,nosuid,nodev,noatime
```

- 挂载点：独立卷 `/mnt/Server_Data_Center`，不是根分区，不是 overlay，不是网络文件系统
- 文件系统：ext4，`rw` 可写
- 容量：总 7.3T，已用 51.4G，可用 **6.8T**，使用率 1%
- `BASE_WRITABLE=YES`（`test -w` 实测）
- 父目录属主：`arlune_innersea:arlune_innersea`，权限 `drwxr-xr-x`

### 目标目录检查

M0 开始时 `SourceLore/` 已存在且为**空目录**（`ls -la` 仅显示 `.` 与 `..`），无历史内容需要保护或复用。写入探测（创建后立即删除临时文件）成功。

## 5. 工具链

| 工具 | 路径 | 版本 | 状态 |
|---|---|---|---|
| git | `/usr/bin/git` | `2.56.0` | OK |
| python3 | `/usr/bin/python3` | `3.14.8` | OK |
| node | — | `v24.22.1` | OK |
| rg (ripgrep) | — | 存在 | OK |
| jq | — | 存在 | OK |
| gh | mise 管理 | `2.102.0` | OK |
| bwrap | — | 存在 | OK |
| dsh | `<runtime>/…/bin/dsh` | `0.2.1-rc.2` | OK |

### Python 能力核验

```
python3 --version        → Python 3.14.8
/usr/bin/python3.14      存在
python3 -m venv --help   → VENV_OK（venv 模块可用）
sqlite3 FTS5 测试         → FTS5_OK（CREATE VIRTUAL TABLE ... USING fts5 成功）
```

- Python 3.14.8 ≫ 文档要求的 3.11+，满足 `pyproject.toml` 的 CLI 基础
- venv 可用 → 依赖装进项目独立 venv，**绝不污染系统 Python**
- SQLite FTS5 原生可用 → M5 的默认索引方案无需降级

## 6. 网络

```
curl https://api.github.com/rate_limit
→ github_api=200  time=2.453621s
```

GitHub API 直连可达，无代理阻碍。

### gh 登录身份

```
github.com
  ✓ Logged in to github.com account MilchstraBe-Endless10 (keyring)
  - Active account: true
  - Git operations protocol: https
  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

- 账号：`MilchstraBe-Endless10`，token 存于 keyring（**未读取、未打印 token 内容**）
- scope 含 `repo` → M9 具备创建/推送私有仓库的技术前提
- 说明：M9 发布前仍需按文档要求重新核实目标仓库所有权，且严禁覆盖他人已有内容

## 7. 模型路由

`<DSH_HOME>/profiles/web/cordis.patch.yml`：

```yaml
- config:
    provider: omniroute
    model: workbuddy/deepseek-v4.1-flash
  id: agent-default-model
  name: '@deepseek-ai/dsh-agent-default-model'
```

模型目录中该条目标注 `contextWindow: 131072`。

- 实际 route：`omniroute` / `workbuddy/deepseek-v4.1-flash`
- 与文档要求「当前执行模型 DeepSeek-V4.1 Flash」**一致**
- **上下文窗口 131072**：这是本项目最重要的工程约束。Flash-First 协议要求一回合只做一个小任务，正好与之匹配；本会话将严格执行「小任务 → 落盘 → 汇报」节奏，禁止把大段上游源码一次性读入上下文。

## 8. DSH Skill 发现机制

### Provider 启用状态

`cordis.patch.yml` 中以下插件均已注册：

```yaml
- id: '@deepseek-ai/dsh-skill'
- id: '@deepseek-ai/dsh-skill-filesystem'
- id: '@deepseek-ai/dsh-skill-office'
- id: '@deepseek-ai/dsh-tool-skill'
```

### 实际发现根

| 候选根 | 实测结果 |
|---|---|
| `<DSH_HOME>/skills`（用户级） | **存在**，内含 `expert-team/`（含 `SKILL.md` 82,207 字节、`references/`、`scripts/`、`assets/`） |
| `<DSH_HOME>/profiles/web/skills` | 不存在 |
| `<DSH_HOME>/.agents/skills` | 不存在 |
| `<projectRoot>/.dsh/skills`（项目级） | 本项目已创建空目录，待 M6 安装 |
| `customSkillDirs` | `cordis.patch.yml` / `cordis.yml` 中**未配置** |

### Catalog 实测

`skillmgr_list` → **共 37 个 skill**，`expert-team` 出现在列表中，来源标注为本地用户级目录。

结论（对 M6 的关键判据）：

1. 用户级发现根 `<DSH_HOME>/skills` **经实测确认有效** —— `expert-team` 既是文件系统里的目录，也确实出现在 Catalog 中
2. 所以 `SourceLore/skills/sourcelore/SKILL.md` 只是**源码原件**，不能被假定为自动发现；M6 必须把它安装到真实发现根（项目级 `<projectRoot>/.dsh/skills/sourcelore/` 或用户级），再用 Catalog 复验
3. Skill 名称必须 kebab-case，`sourcelore` 符合
4. 发现的是根目录下的**直属** `<name>/SKILL.md` bundle，不递归扫描 —— 安装时目录层级不能错

### frontmatter 参考样例

`expert-team/SKILL.md` 实际使用的字段：

```yaml
---
name: expert-team
description: ...
whenToUse: ...
---
```

M6 编写 `sourcelore/SKILL.md` 时以此为本机真实格式依据，而不是照搬文档里的抽象描述。

## 9. Tobs 工作区授权

`list_workspace_grants` 实测两个 Grant，均为 `orchestratorWrite: true`：

| grant_id | 路径 | 标题 | 用途 |
|---|---|---|---|
| `3f38248f-f469-4b27-8363-881aae5ad56c` | `/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)` | `GitHub_Knowledge_Base(Gihub知识库)` | **本项目使用**，覆盖 SourceLore 根 |
| `91cf2e44-2fcc-452b-882e-c0cf2b8103b5` | `<DSH_HOME>/botharness/tob-workspaces/bot-ec1834997cac4e88b40966a5ddec4586` | `Tob` | Bot 自身工作区，与本项目无关 |

- 授权路径与文档要求的父目录**逐字一致**
- 授权范围是父目录而非全盘，符合文档「避免无边界的全盘授权」
- 本会话文件写入路径已在该 Grant 覆盖范围内

## 10. M0 Gate 判定

| Gate 条件（文档原文） | 实测结论 | 状态 |
|---|---|---|
| 可读取和安全写入指定目录 | `BASE_WRITABLE=YES`；SourceLore 已成功创建骨架并 `git init` | **PASS** |
| 模型能运行最小工具实验 | bash、文件读写、git、python3 venv、FTS5、curl 全部实际执行成功 | **PASS** |
| DSH 技能路径有依据 | 用户级根 `<DSH_HOME>/skills` 经 Catalog 交叉验证有效；三个 skill Provider 已注册 | **PASS** |

**M0-01 结果：PASS**

## 11. 与全局 AGENTS.md 的偏差声明

1. **产出目录**：`AGENTS.md` 规定 AI 产出默认写入 `/mnt/Server_Data_Center/Personal_Files(个人文件)/Cosmos_File/AI产出数据文件`。本项目按用户明示的总控提示词，全部代码与文档写入 SourceLore 项目根。用户明示优先。
2. **sudo 策略**：`AGENTS.md` 保留 sudo 15 分钟密码缓存，文档手册要求「不得擅自 sudo」。本次 M0 未使用 sudo，后续也以普通用户完成全部开发；若遇权限问题，先记录 `BLOCKED_*` 并向用户报告，不自行提权。
3. **知识资产隔离**：`knowledge/`、`cache/`、`upstreams/` 已写入 `.gitignore`，源码 Git 不跟踪。这与文档 D 节「严禁混淆两种写入」一致。

## 12. 未执行 / 未知项

| 项 | 状态 | 原因 |
|---|---|---|
| 六个上游仓库的真实 Commit 与 LICENSE | `NOT_RUN` | 属于 M1，M0 不做 |
| `sourcelore` Skill 的实际加载 | `NOT_RUN` | 属于 M6 |
| Tobs Bot DM 内真实调用 SourceLore | `NOT_RUN` | 属于 M7 |
| GitHub 私有仓库创建与推送 | `NOT_RUN` | 属于 M9 |
| 磁盘剩余空间随分析增长的容量规划 | `UNKNOWN` | 6.8T 余量对小型/中型仓库足够；大型仓库的实际占用待 M8 实测 |

---

**审计人**：Tobs PersonaBot（bot-ec1834997cac4e88b40966a5ddec4586）
**证据来源**：本次会话实际执行的命令输出，未做任何推断性填充
