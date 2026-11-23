# SourceLore 安装指南

本文说明如何从零开始安装 SourceLore，并以 CLI、Skill 或 OpenBot/DSH/Hermes 智能体的形式使用它。本文中的所有命令均来自真实 CLI 的 `--help` 输出；如与本文有出入，一律以 `python3 <技能目录>/scripts/sourcelore.py --help` 与 `python3 <技能目录>/scripts/sourcelore.py <子命令> --help` 的实际输出为准。

SourceLore 是一个**本地知识库工具**，不是模型服务。它把一个公开 GitHub 仓库的固定 Commit 采集为可回查的知识资产（Fact / Claim / Verification / Evidence），并通过 Skill + CLI 供智能体调用。它不做开放式推理，也不执行第三方仓库代码。

> 本仓库只包含源代码、文档和测试。知识数据库、已捕获的内容字节、第三方快照与本地缓存都保存在仓库之外。

---

## 1. 环境要求

| 项目 | 要求 | 说明 |
|---|---|---|
| Python | Python 3（开发与测试环境为 3.14） | CLI 直接用 Python 3 启动，无编译步骤 |
| 依赖清单 | 仓库顶层**没有** `requirements.txt` | 核心 CLI 不需要第三方 Python 包即可启动 |
| Git | 可用即可 | 用于快照与提交锁定 |
| 虚拟环境 | 可选，推荐 | 仅用于隔离 JS/TS 解析器依赖，不污染系统 Python |
| SQLite | 需支持 FTS5（可选加速） | 用于派生索引；缺失时降级，不影响核心功能 |
| `GITHUB_TOKEN` | 可选 | 提高 GitHub API 配额；未认证为 60 次/小时。离线查询从不要求它 |
| 网络 | 仅采集时需要 | 查询、问答、卡片生成均为零网络请求 |

CLI 入口脚本会**自行定位 SourceLore 工程根**（也可用环境变量 `SOURCELORE_PROJECT_ROOT` 显式指定）。因此只要 `skill/sourcelore/` 目录与工程源码保持原有相对结构，脚本即可正常工作。

### 1.1 路径中的括号与空格

工程根路径可能包含括号、空格或非 ASCII 字符（中文），例如形如：

```
/mnt/<数据卷>/<团队目录(中文)>/<知识库(中文)>/SourceLore
```

- 在 shell 中必须给这类路径**加引号**。
- 在 Python 中使用 `pathlib` 或 `open()` 传绝对路径，**不要**用字符串拼接。
- 不要用 `cd` 依赖相对路径；会话的工作目录通常不是工程根。

---

## 2. 获取源码

将 SourceLore 工程克隆或复制到本地一个固定目录。下文用 `<工程根>` 指代该目录，CLI 脚本位于：

```
<工程根>/skill/sourcelore/scripts/sourcelore.py
```

---

## 3. 验证 CLI 可直接运行

在把 Skill 安装到智能体之前，先确认脚本本身可执行：

```sh
python3 <技能目录>/scripts/sourcelore.py --version
python3 <技能目录>/scripts/sourcelore.py --help
python3 <技能目录>/scripts/sourcelore.py help
```

`--version` 返回 JSON，形如：

```json
{
  "ok": true,
  "skill_version": "f2p5a/1.0"
}
```

`--help` 会列出全部子命令：

```
usage: sourcelore [-h] [--data-root DATA_ROOT] [--version]
                  {status,repositories,help,analyze,inspect,history,query,derive,answer,card} ...
```

如果脚本报"找不到工程根"，请设置：

```sh
export SOURCELORE_PROJECT_ROOT="<工程根>"
```

---

## 4. 安装 Skill

Skill 由平台的文件系统发现机制加载。把 `<工程根>/skill/sourcelore/` **整个目录**复制到智能体的 Skill 发现目录，例如：

```sh
cp -r <工程根>/skill/sourcelore ~/.agents/skills/sourcelore
```

要点：

- 入口 `SKILL.md` 必须有 `name` 与 `description` 两个 frontmatter 字段；`description` 中要包含明确的触发语，平台才能据文件系统发现机制热加载。
- 文件系统发现是**热加载**的，无需重启智能体。
- 发现机制通常只扫描 `<发现根>/<名称>/SKILL.md` 这样的直属 bundle，安装层级必须严格，不能多套一层目录。

### 4.1 用户级与项目级发现根

以 DSH/OpenBot 为例：

- **用户级根**（如 `<DSH_HOME>/skills` 或 `~/.agents/skills/`）：所有会话都能发现。若智能体会话的工作目录不在工程根下，这是让 Skill 能被触发的必由之路。
- **项目级根**（如 `<项目根>/.dsh/skills`）：只有工作目录位于该项目下的会话才能发现。

建议至少安装到用户级根，确保任意会话都能调用。

### 4.2 三个副本必须保持同步（重要）

SourceLore 的 Skill 常见三处副本：

1. 工程源：`<工程根>/skill/sourcelore/`
2. 安装态：`~/.agents/skills/sourcelore/`
3. Hermes 态：`~/.hermes/skills/sourcelore/`

**只改工程源是不够的。** 实际加载安装态的会话看不到新命令或新规则，"已登记"是假的。历史上出现过只改工程源、导致安装版没有登记 `answer` 命令的问题。每次修改后：

- 把更新后的 `SKILL.md` 以及新增/修改的 `references/*.md`、`scripts/` 一并拷贝到三处。
- 用校验和核对三份 `SKILL.md` 是否一致：

```sh
md5sum <工程根>/skill/sourcelore/SKILL.md \
       ~/.agents/skills/sourcelore/SKILL.md \
       ~/.hermes/skills/sourcelore/SKILL.md
```

三行的哈希值应当相同。

---

## 5. 配置知识库数据根

知识库根目录默认是 `~/.sourcelore/`，可用两种方式覆盖：

```sh
# 方式一：命令行全局选项（必须放在子命令之前）
python3 <技能目录>/scripts/sourcelore.py --data-root /path/to/data status

# 方式二：环境变量
export SOURCELORE_DATA_ROOT="/path/to/data"
```

重要约束：

- 数据库文件 `kb.db` **永不写入源码仓库**；脚本内有 guard，遇到仓库路径会直接报错。
- 卡片与报告输出到 `<数据根>/preview/`。
- 不要把知识数据库、已捕获字节、第三方快照或本地配置提交进 Git。
- 首次启动时，先检查正式持久化数据根是否已配置且包含真实仓库；若不存在或为空，不要擅自创建新空库代替现有数据库，也不要删除、合并或迁移历史资产。

---

## 6. 可选：安装 JS/TS 语法解析器

源码结构分析支持：

- Python（`.py`）：用标准库 `ast`，无需额外依赖。
- JS/JSX/TS/TSX：用 tree-sitter，依赖固定版本，记录在 `requirements-treesitter.txt`：

```
tree-sitter==0.26.0
tree-sitter-javascript==0.25.0
tree-sitter-typescript==0.23.2
```

依赖必须隔离在**项目专用虚拟环境 `.venv/`** 中，不修改系统 Python，也不自动下载 grammar：

```sh
cd <工程根>
python3 -m venv .venv
.venv/bin/pip install -r requirements-treesitter.txt
```

若这些 grammar 缺失，解析器返回 `PARSER_UNAVAILABLE`，**不会**用正则凑数。此时 Python 源码分析仍可用。

---

## 7. 可选：配置 GitHub Token

设置环境变量 `GITHUB_TOKEN` 可提高配额（未认证为 60 次/小时）：

```sh
export GITHUB_TOKEN="<your-token>"
```

安全约束：

- 只从进程环境读取；不写日志、不写资产、不进 Git。
- 单次调用可用 `--no-token` 强制禁用（即便环境里有）。
- 被限流时，CLI 在 **2 秒内**返回错误 `RATE_LIMITED` 并附真实 `retry_after` 秒数；**不自动重试、不空等、不绕过**。建议先用 `--offline` 查本地，或稍后 `--refresh`。

---

## 8. 设置便捷命令（可选）

真实入口是完整脚本路径。为方便起见可设置别名，使命令与 `--help` 中的 `usage: sourcelore ...` 一致：

```sh
alias sourcelore='python3 <技能目录>/scripts/sourcelore.py'
```

之后即可写：

```sh
sourcelore status
sourcelore repositories
```

本文后续示例中用 `sourcelore` 指代该入口；实际执行时请替换为完整路径或使用上述别名。

---

## 9. 验证安装

```sh
sourcelore status
sourcelore repositories
```

- `status` 输出运行状态：skill 版本、数据根、数据库是否存在、仓库数、最近一次操作。不输出任何凭据。
- `repositories` 列出已登记仓库：`repository_id`、`commits`、`snapshot_count`、`fact_count`、`claim_count`、`knowledge_state`。

在智能体中，用自然语言触发验证：

- "我的知识库里有哪些 GitHub 项目？"
- "介绍一下这个 GitHub 项目。"

若智能体无法调用，检查：Skill 是否装在正确的发现根、`SKILL.md` 是否有 `name`+`description`、三处副本是否同步。

---

## 10. 常见错误与排查

### 10.1 退出码

所有输出 JSON 走 stdout，错误走 stderr。退出码含义：

| 退出码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 执行失败（含 GitHub 错误） |
| 2 | 参数错误 |
| 3 | 知识库不可用（未建立） |

错误 JSON 形如：

```json
{"ok": false, "error": "...", "message": "..."}
```

看到 `ok: false` 就要如实报告失败，不要粉饰。

### 10.2 典型错误状态

| 状态 / 现象 | 原因 | 处理 |
|---|---|---|
| `PARSER_UNAVAILABLE` | JS/TS 的 tree-sitter grammar 未安装 | 在 `.venv` 中安装 `requirements-treesitter.txt`；或用 Python 源码分析；不要用正则替代 |
| `OFFLINE_CACHE_MISS`（退出码 3） | 使用 `--offline` 但本地没有该 Commit 快照 | 先不带 `--offline` 采集一次，或改用已登记 Commit |
| `RATE_LIMITED` | GitHub API 配额耗尽 | 读取 `retry_after`，稍后重试；先用 `--offline` 查本地；不要自动重试或绕过 |
| `BLOB_TOO_LARGE` / `BATCH_BYTE_LIMIT` / `BATCH_PATH_LIMIT` | 内容抽取超出预算（单 Blob 256 KiB、单批 2 MiB、候选路径 32、单文件 100 Facts） | 用 `--content-path` 缩小范围 |
| 退出码 3 / 知识库不可用 | 数据根未建立或指向错误 | 用 `--data-root` 或 `SOURCELORE_DATA_ROOT` 指向含真实数据的根 |
| `kb.db` 写入被拒 | 试图把数据库写进 Git 仓库 | 改用仓库外的数据根 |
| 新命令在智能体中不生效 | 只改了工程源，安装态/ Hermes 态未同步 | 按第 4.2 节同步三处副本并用 `md5sum` 核对 |
| 路径找不到 / 命令失败 | 路径含括号空格未加引号，或用了相对路径 | shell 中加引号；Python 用 `pathlib`；用绝对路径 |

### 10.3 离线语义

`analyze` 先做本地查找，再决定是否联网：

| 情况 | 行为 |
|---|---|
| `--commit <sha>` 且本地有完整快照 | 直接复用，**0 次网络请求** |
| `--offline` 且本地有 | 复用，明确标"未访问 GitHub" |
| `--offline` 且本地无 | 报 `OFFLINE_CACHE_MISS`（退出码 3），不伪造结果 |
| `--refresh` | 允许联网重新采集 |
| 无 `--commit`（可变 Branch） | 返回 `branch_current_unknown: true` |

本地快照只能证明"过去观测过的版本"，不能证明某个 Branch 当前仍指向它。

---

## 11. 限制语义（务必理解）

- **`ROOT_ONLY`**：表示只枚举了仓库根目录。它**绝不**等同于完整的 `COMPLETE` 覆盖；缺少内容属于"未分析"，不是"不存在"。`derive` 输出 `tree_status=ROOT_ONLY` 是真实覆盖状态，不要"修正"成 COMPLETE。
- **`distribution_allowed=false`**：所有卡片与报告都是内部预览，不是正式发布；分发门禁 B-1/B-2/B-3 仍开放。本项目尚未选择开源许可证，仅供内部使用。
- **`review_status=pending_review`**：任何 `supported` 裁决都带此字段，表示这是 CLI 裁决、尚未人工复核，不可说成"已确认"。
- **`completeness_status: PARTIAL`**：Tree 被截断时，未覆盖部分不得判为"不存在"。
- **`insufficient_evidence`**：只能说"证据不足"，不得说"该命题错误"。
- **`refuted`**：只对该 Commit 成立，不得外推到其他版本或"该项目不存在"。
- 工具**不执行**仓库代码：不 `exec`、不 `eval`、不 import、不跑测试、不执行 shell。
- 只接受 `https://github.com/<owner>/<repo>`；拒绝内网地址、非 GitHub 主机、异常端口；不支持私有仓库。

安装完成后，请继续阅读[使用手册](USER-GUIDE.md)。
