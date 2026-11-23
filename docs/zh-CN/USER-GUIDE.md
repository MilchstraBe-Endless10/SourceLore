# SourceLore 使用手册

本文说明如何使用 SourceLore 分析 GitHub 仓库、查询知识库、生成知识卡片与用自然语言问答。所有命令均来自真实 CLI 的 `--help` 输出，未列在此处的参数不存在。若与本文有出入，以 `python3 <技能目录>/scripts/sourcelore.py <子命令> --help` 为准。

前提：已按[安装指南](INSTALLATION.md)安装并验证。下文用 `sourcelore` 指代入口 `python3 <技能目录>/scripts/sourcelore.py`。

---

## 1. 通用约定

### 1.1 命令结构

```
sourcelore [--data-root DATA_ROOT] [--version] <子命令> [选项]
```

全局选项 `--data-root` 必须放在子命令**之前**。`--version` 返回 JSON。子命令共十个：

```
status, repositories, help, analyze, inspect, history, query, derive, answer, card
```

### 1.2 输出与退出码

- 所有输出 JSON 走 **stdout**，错误摘要走 **stderr**。
- 退出码：`0` 成功 / `1` 执行失败 / `2` 参数错误 / `3` 知识库不可用。
- 错误 JSON 形如 `{"ok": false, "error": "...", "message": "..."}`。看到 `ok:false` 必须如实报告失败。

### 1.3 权威判读纪律（避免误述）

- `tree_summary` 才是完整性的权威说明。`COMPLETE` 表示已完整枚举，`PARTIAL` 表示只有部分条目，不能推断未出现的路径不存在。
- `completeness_status: PARTIAL` / 覆盖 `ROOT_ONLY`：未覆盖部分不得判为"不存在"。
- `insufficient_evidence`：只能说"证据不足"，不得说"命题错误"。
- `refuted`：只对该 Commit 成立，不得外推。
- 库里没有某路径的 Claim ≠ 该路径在 GitHub 不存在，只能说覆盖不足。
- `content_captured=0` 时必须说"内容未采集"，不能说"文件内容如何"。
- 证据完整性需单独报告：`FULLY_LOCATABLE` 才可逐条核对；`PARTIALLY_LOCATABLE` 只能说证据链不完整。
- 报告 `supported` 时同时给出 `review_status`；`pending_review` 不是人工确认。
- 报告 `supported`/`refuted` 前先按 `current_view` 过滤，历史 Verification 只作诊断。
- 退出码 0 / `ok:true` 不等于知识可信，审计类请求须以原始资产复核。
- 不要用模型自身推理去补足 CLI 未返回的数据。

---

## 2. 快速开始

```sh
# 1. 看运行状态
sourcelore status

# 2. 列出已登记仓库
sourcelore repositories

# 3. 分析一个公开仓库（固定 Commit，本地已有则离线复用）
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha>

# 4. 查看仓库知识摘要
sourcelore inspect <repository_id>

# 5. 自然语言问答（内容优先，只读零网络）
sourcelore answer <repository_id> "介绍这个项目"

# 6. 查询具体知识
sourcelore query <repository_id> --commit <sha> --type claims

# 7. 重新生成派生项目文档（仅 D 层，离线）
sourcelore derive <repository_id>

# 8. 生成知识卡片
sourcelore card --repository-id <repository_id> --claim-id <claim_id>
```

---

## 3. 了解知识库现状

### 3.1 status

```sh
sourcelore status
```

无参数。输出运行状态：skill 版本、数据根、数据库是否存在、仓库数、最近一次操作。不输出任何凭据。

### 3.2 repositories

```sh
sourcelore repositories
```

无参数。列出已登记仓库，字段包括 `repository_id`、`commits`、`snapshot_count`、`fact_count`、`claim_count`、`knowledge_state`。

### 3.3 help

```sh
sourcelore help
sourcelore <子命令> --help
```

`help` 无参数；`<子命令> --help` 给出该子命令的权威选项列表。

### 3.4 inspect

```
usage: sourcelore inspect [-h] [--content-summary] repository_id
```

```sh
sourcelore inspect <repository_id>
sourcelore inspect <repository_id> --content-summary
```

- 位置参数 `repository_id`（必填）。
- `--content-summary`：附带内容级知识概览（Blob 数、可解析数、事实数）。

输出：Commit 列表、Tree 覆盖（含 `completeness_status`）、Facts、Claims、限制。统计知识类型按 `facts[].rule_id` 聚合；`observed_path` 常为 null，是正常的。

### 3.5 history

```
usage: sourcelore history [-h] repository_id
```

```sh
sourcelore history <repository_id>
```

列出已登记历史版本。**只列已登记 Commit，不推断祖先或先后关系。**

---

## 4. 分析仓库（采集与建库）

```
usage: sourcelore analyze [-h] [--ref REF] [--path PATH]
                          [--max-requests MAX_REQUESTS] [--commit COMMIT]
                          [--offline] [--refresh] [--no-token]
                          [--license-known] [--include-content]
                          [--content-status] [--plan] [--resume]
                          [--request-limit REQUEST_LIMIT]
                          [--reserve-requests RESERVE_REQUESTS]
                          [--content-path CONTENT_PATH]
                          url
```

位置参数 `url`：`https://github.com/<owner>/<repo>`（可带 `/tree/<ref>`）。只接受公开 GitHub 仓库；内网地址、非 GitHub 主机、异常端口会被拒绝。

选项逐项说明：

| 选项 | 含义 |
|---|---|
| `--ref REF` | 分支/标签/Commit（默认 HEAD） |
| `--path PATH` | 要观察的路径 |
| `--max-requests MAX_REQUESTS` | GitHub 请求上限 |
| `--commit COMMIT` | 固定 Commit SHA（优先复用本地缓存） |
| `--offline` | 禁用一切 GitHub 请求 |
| `--refresh` | 显式要求重新获取远程版本 |
| `--no-token` | 本次不使用 `GITHUB_TOKEN`（即便环境里有） |
| `--license-known` | 声明该仓库有明确授权依据（内部采集用）；默认不声明 |
| `--include-content` | 对已保存快照做内容级抽取（读 Blob；无字节则明确报告） |
| `--content-status` | 只报内容可用性，不采集、不联网 |
| `--plan` | 只读计划：盘点缺口并估算请求，不联网、不写资产 |
| `--resume` | 续跑：只补齐缺失内容，已完成的直接复用 |
| `--request-limit REQUEST_LIMIT` | 本次采集最多发出的 GitHub 请求数（默认 8） |
| `--reserve-requests RESERVE_REQUESTS` | 优先保留的主配额（默认 5） |
| `--content-path CONTENT_PATH` | 限定内容抽取的路径（可重复） |

### 4.1 常用分析流程

```sh
# 先看采集计划（只读，不联网、不写资产）
sourcelore analyze https://github.com/<owner>/<repo> --plan

# 以固定 Commit 采集（最常用，可复现）
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha>

# 只用本地知识，禁止联网
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --offline

# 强制重新获取远程版本
sourcelore analyze https://github.com/<owner>/<repo> --refresh

# 控制请求预算
sourcelore analyze https://github.com/<owner>/<repo> --request-limit 8 --reserve-requests 5

# 只看某路径
sourcelore analyze https://github.com/<owner>/<repo> --path README.md

# 只报内容可用性（不采集、不联网）
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --content-status

# 内容级抽取并限定路径
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --include-content --content-path README.md

# 续跑：只补齐缺失内容
sourcelore analyze https://github.com/<owner>/<repo> --commit <sha> --resume
```

### 4.2 离线语义

| 情况 | 行为 |
|---|---|
| `--commit` 且本地有完整快照 | 直接复用，0 次网络请求 |
| `--offline` 且本地有 | 复用，明确标"未访问 GitHub" |
| `--offline` 且本地无 | `OFFLINE_CACHE_MISS`，退出码 3，不伪造 |
| `--refresh` | 允许联网重新采集 |
| 无 `--commit`（可变 Branch） | 返回 `branch_current_unknown: true` |

本地快照只能证明"过去观测过的版本"，不能证明 Branch 当前仍指向它。

### 4.3 内容抽取预算与状态

- 预算：单 Blob 256 KiB、单批 2 MiB、候选路径 32、单文件 100 Facts。超限返回 `BLOB_TOO_LARGE` / `BATCH_BYTE_LIMIT` / `BATCH_PATH_LIMIT`。
- 内容状态码：`CONTENT_NOT_CAPTURED`（无字节）/ `BLOB_TOO_LARGE` / `BINARY_CONTENT` / `UNSUPPORTED_ENCODING` / `CONTENT_PARSE_FAILED` / `CONTENT_PARTIAL`。
- 关键前提：Blob 内容字节是否已采集必须看 `snapshot_inventory.content_captured`。若为 0，必须报告 `CONTENT_NOT_CAPTURED`，不得凭路径猜测文件内容。
- 支持的解析器：README（标题+行号、链接、代码块语言）、`package.json`（name/version、依赖、scripts）、`pyproject.toml`（project 字段、dependencies、tool 表）。其它文件仅元数据。

---

## 5. 查询知识（query）

```
usage: sourcelore query [-h] [--commit COMMIT]
                        [--type {path,claims,version,content,code,relation,project}]
                        [--path PATH] [--compare-commit COMPARE_COMMIT]
                        [--max-results MAX_RESULTS] [--symbol SYMBOL]
                        [--symbol-kind SYMBOL_KIND] [--module MODULE]
                        [--show-resolution] [--config CONFIG] [--file FILE]
                        repository_id
```

位置参数 `repository_id`（必填）。选项：

| 选项 | 含义 |
|---|---|
| `--commit COMMIT` | 固定 Commit（`content` 类型必需） |
| `--type {path,claims,version,content,code,relation,project}` | 查询类型 |
| `--path PATH` | 路径 |
| `--compare-commit COMPARE_COMMIT` | 对比 Commit |
| `--max-results MAX_RESULTS` | 最大结果数 |
| `--symbol SYMBOL` | 按符号 `qualified_name` 或 `name` 查 |
| `--symbol-kind SYMBOL_KIND` | 按符号类型过滤 |
| `--module MODULE` | 按静态导入模块名过滤 |
| `--show-resolution` | 显示解析状态与配置细节 |
| `--config CONFIG` | 按 tsconfig 路径过滤 |
| `--file FILE` | 按源码文件路径过滤归属 |

查询复用已存知识，**不重新访问 GitHub**。解析输出时若含未转义控制字符，用 `json.loads(out, strict=False)`；解析失败就如实说"本轮未得到可展示结果"，不要当成"没有知识"。

### 5.1 path / claims / version

```sh
# 路径存在观察（--type path 需 --path）
sourcelore query <rid> --commit <sha> --type path --path README.md

# 已登记命题
sourcelore query <rid> --commit <sha> --type claims

# 对比两个 Commit（--type version 需 --compare-commit）
sourcelore query <rid> --commit <sha> --compare-commit <other-sha> --type version
```

结果字段常见有：`coverage_state`、`coverage_meaning`、`answerable`、`findings[]`、`untrusted_findings[]`、`gaps[]`、`limitations[]`、`distribution_restrictions`。`untrusted_findings[]` 里的 Claim 已被排除，不得当结论。

### 5.2 content（内容级知识）

```sh
# 查内容级知识（--type content 必需 --commit，可带 --path）
sourcelore query <rid> --commit <sha> --type content --path README.md
```

九种状态严格区分，不得合并：

```
REPOSITORY_NOT_REGISTERED / COMMIT_NOT_REGISTERED / CONTENT_NOT_CAPTURED /
CONTENT_INTEGRITY_FAILED / FACT_NOT_REGISTERED / INSUFFICIENT_EVIDENCE /
SUPPORTED / REFUTED / RETRIEVAL_ERROR
```

尤其：没有 Blob 内容 ≠ 文件不存在；有 Blob 没抽取 Fact ≠ 命题被否定；有 Fact 没 Verification ≠ 已 supported；解析失败 ≠ 文件没有对应内容。`ContentEvidenceRef` 同时给字节偏移（权威）与行号（派生）；缺任一维即 `ref_complete=false`，不得视为完整引用。

内容概览用 `inspect <rid> --content-summary`。四种计数不可混为一谈：

| 指标 | 含义 |
|---|---|
| `file_entries` | 文件条目数（同 Blob 多路径会重复计） |
| `unique_blobs` | 唯一 Git Blob OID 数 |
| `content_assets` | 内容资产数 |
| `facts` | 已登记事实数 |

### 5.3 code（源码结构）

```sh
sourcelore query <rid> --commit <sha> --type code
sourcelore query <rid> --commit <sha> --type code --path src/app.py
sourcelore query <rid> --commit <sha> --type code --symbol Worker.run
sourcelore query <rid> --commit <sha> --type code --symbol-kind js_class
sourcelore query <rid> --commit <sha> --type code --module lodash
```

- Python（`.py`）用标准库 `ast`；JS/JSX/TS/TSX 用 tree-sitter（见安装指南）。
- JS/TS 符号类型：`js_function` / `js_async_function` / `js_generator_function` / `js_class` / `js_method` / `js_object_method` / `js_variable` / `js_arrow_function` / `js_function_expression` / `ts_interface` / `ts_type_alias` / `ts_enum` / `ts_namespace`。
- 语义纪律：arrow 绑定 ≠ function declaration；interface ≠ class；匿名 default export 不编造名字。
- `require("x")` 是调用观察（`LITERAL_REQUIRE_CALL_OBSERVED`），不是 ESM 声明；`require(var)` / `import(var)` → `DYNAMIC_MODULE_SPECIFIER`，不猜目标；`import type` → `is_type_only=true`，不是运行时依赖。
- 解析完整性：`PARSE_COMPLETE` / `PARSE_WITH_ERRORS` / `PARSE_UNSUPPORTED_SYNTAX` / `PARSER_UNAVAILABLE` / `SOURCE_INCOMPLETE` / `CONTENT_INTEGRITY_FAILED`。语法错误时不产生权威符号/导入/导出事实。
- 能确认：`SOURCE_SYMBOL_DECLARED`（声明了符号）、`SOURCE_IMPORT_DECLARED`（存在静态导入声明）、`SOURCE_LOCAL_MODULE_RESOLVED`（当前 Commit Tree 中有唯一候选路径）。不能确认函数被执行、被使用、运行时成功。
- 本地模块解析五态：`LOCAL_MODULE_RESOLVED` / `EXTERNAL_OR_UNRESOLVED` / `AMBIGUOUS_CANDIDATES` / `INSUFFICIENT_TREE_COVERAGE` / `UNSUPPORTED_IMPORT_FORM`。
- 绝不执行仓库代码。不做调用图、运行时依赖图、数据流图、动态分派。

### 5.4 relation（配置感知模块解析）

```sh
sourcelore query <rid> --commit <sha> --type relation
sourcelore query <rid> --commit <sha> --type relation --path src/app.ts
sourcelore query <rid> --commit <sha> --type relation --module ./utils
sourcelore query <rid> --commit <sha> --type relation --show-resolution
```

三层状态绝不混淆：

| 层 | 状态 | 含义 |
|---|---|---|
| 1 | `MODULE_REFERENCE_OBSERVED` | 源码里确实有该 Import |
| 2 | `CONFIG_MAPPING_CANDIDATE` | 按配置找到候选路径 |
| 3 | `LOCAL_MODULE_RESOLVED` | 当前 Commit Tree 中唯一命中 |

不存在 `RUNTIME_IMPORT_VERIFIED`——本工具不验证运行时加载。JS/TS 模块解析七态：`LOCAL_MODULE_RESOLVED` / `RELATIVE_PATH_CANDIDATE_FOUND` / `AMBIGUOUS_CANDIDATES` / `EXTERNAL_OR_UNRESOLVED` / `UNSUPPORTED_RESOLUTION_POLICY` / `INSUFFICIENT_TREE_COVERAGE` / `DYNAMIC_SPECIFIER`。本版只支持明确的相对路径（`./x`、`../y`）；裸模块名、`@/alias`、`#hash` 一律 `UNSUPPORTED_RESOLUTION_POLICY`。

### 5.5 project（TypeScript 项目知识）

```sh
sourcelore query <rid> --commit <sha> --type project
sourcelore query <rid> --commit <sha> --type project --config tsconfig.json
sourcelore query <rid> --commit <sha> --type project --file src/app.ts
sourcelore query <rid> --commit <sha> --type project --show-resolution
```

- 只认 `tsconfig.json` / `jsconfig.json` 标准命名；`extends` 引用的基础配置不登记为独立项目。
- `extends`：`files`/`include`/`exclude` 会继承（子配置有则覆盖），`references` 不继承。
- `references` 只处理同仓库同 Commit 的本地配置，检测循环与深度上限 8。`PROJECT_REFERENCE_TARGET_VERIFIED` 只表示目标配置存在，不代表 B 已构建或 A 使用了 B 的产物。
- `files` 优先于 `include` 且不受 `exclude` 影响；`exclude` 只过滤 include 扫描；`files: []` 不触发默认扫描。
- 不支持的模式（大括号、取反、绝对路径、多重 `**`）→ `UNSUPPORTED_SELECTION_RULE`。
- 归属状态各自独立：`INPUT_EXPLICITLY_LISTED` / `INPUT_MATCHED_INCLUDE` / `INPUT_EXCLUDED_FROM_INCLUDE` / `INPUT_POSSIBLE_VIA_IMPORT` / `INPUT_MATCHED_MULTIPLE_PROJECTS` / `INPUT_NOT_PROVEN` / `CONFIG_INCOMPLETE` / `UNSUPPORTED_SELECTION_RULE`。`INPUT_EXCLUDED_FROM_INCLUDE` ≠ 不可能进入 TypeScript Program。
- 项目上下文：唯一可验证 → `PROJECT_CONTEXT_SELECTED`；多候选 → `PROJECT_CONTEXT_AMBIGUOUS`（不任选）。
- 未登记的配置一律 `CONFIG_CONTENT_NOT_CAPTURED`——不猜仓库没有 tsconfig，不读工作目录，不借用其他 Commit。

---

## 6. 自然语言问答（answer）

```
usage: sourcelore answer [-h] [--commit COMMIT] repository_id question
```

```sh
sourcelore answer <repository_id> "介绍这个项目"
sourcelore answer <repository_id> "怎么使用这个库"
sourcelore answer <repository_id> "架构是怎样的"
sourcelore answer <repository_id> "核心函数是什么"
sourcelore answer <repository_id> "为什么这些结论可信"
sourcelore answer <repository_id> "知识库覆盖完整吗"
sourcelore answer <repository_id> "怎么使用" --commit <sha>
```

- 位置参数 `repository_id` 与 `question`（自然语言问题）。
- `--commit`：固定 Commit；默认取该仓库最新已登记快照。
- 只读、零网络、零写入、不执行第三方代码；答案全部来自已登记、已验证的本地资产。
- 输出含 `intent`、`blocks[]`（每块 `heading`/`body`/`refs`）、`audit`、`network_requests=0`、`wrote_assets=0`。展示时优先呈现 `blocks[].body` 真实正文，`refs` 用于追溯，不要改写正文或用推理补内容。

意图与触发：

| intent | 触发问题 | 展示内容 |
|---|---|---|
| `introduce` | 介绍 / 用途 / 功能 / 概览（默认） | 项目用途、技术栈与清单、主要导出、核心实现摘录 |
| `usage` | 怎么使用 / 安装 / API / 示例 | README 的 Install/Usage/示例章节 + Manifest 清单 |
| `architecture` | 架构 / 结构 / 模块 / 依赖 / 入口 | 导出与模块指向、文件结构、依赖声明 |
| `code` | 源码 / 函数 / 类 / 导出 / 符号 | 符号表、核心实现摘录、依赖 |
| `evidence` | 为什么可信 / 证据 / 依据 | 主张与裁决、证据定位，并附 `audit` |
| `completeness` | 完整性 / 覆盖 / 检查知识库 | 覆盖说明、文件结构，并附 `audit` |

**审计字段只在 `evidence`/`completeness` 返回**；其余意图 `audit=null`，避免统计淹没普通答案。中文提问会对英文 README 标题做中英映射（使用/安装 → `install`/`usage`，性能 → `benchmark`，许可 → `license`）。始终附常见限制：Commit 非最新、`distribution_allowed=false`、ROOT_ONLY 子目录未采集。

---

## 7. 生成知识卡片（card）

```
usage: sourcelore card [-h] --repository-id REPOSITORY_ID
                       [--claim-id CLAIM_ID]
                       [--verification-id VERIFICATION_ID]
                       [--content-fact-id CONTENT_FACT_ID]
                       [--content-claim-id CONTENT_CLAIM_ID] [--commit COMMIT]
                       [--path PATH] [--code] [--vault VAULT]
```

| 选项 | 含义 |
|---|---|
| `--repository-id REPOSITORY_ID` | 必填 |
| `--claim-id CLAIM_ID` | 按 Claim 生成 |
| `--verification-id VERIFICATION_ID` | 按 Verification 生成 |
| `--content-fact-id CONTENT_FACT_ID` | 按内容 Fact 生成 |
| `--content-claim-id CONTENT_CLAIM_ID` | 按内容 Claim 生成 |
| `--commit COMMIT` | 固定 Commit |
| `--path PATH` | 路径 |
| `--code` | 生成源码结构卡片 |
| `--vault VAULT` | 同时导出为 Obsidian 双向链接笔记（给定 vault 目录） |

```sh
# 按 Claim / Verification
sourcelore card --repository-id <rid> --claim-id <claim_id>
sourcelore card --repository-id <rid> --verification-id <verification_id>

# 内容知识卡片
sourcelore card --repository-id <rid> --commit <sha> --path README.md
sourcelore card --repository-id <rid> --content-fact-id <fact_id>
sourcelore card --repository-id <rid> --content-claim-id <claim_id>

# 源码结构卡片（Bot 内呈现文本块）
sourcelore card --repository-id <rid> --commit <sha> --path <p> --code

# 导出 Obsidian 笔记
sourcelore card --repository-id <rid> --claim-id <claim_id> --vault <vault-dir>
```

`card ... --code` 默认返回 `{"format":"bot_block","repository":"owner/name","text":"<点阵表格>","network_requests":0}`。直接把 `text` 展示给用户，**不要**打开浏览器或生成 HTML 文件。五档点阵含义：`▣ 已验证·命题成立` / `▤ 已观察·尚未验证` / `□ 证据不足` / `△ 该语义形式不支持` / `· 尚未分析`。卡片恒显示 `distribution_allowed=false` 与 `copy_permitted=false`；证据链不完整只出诊断卡，绝不出满分卡。默认不回显大段原文，证据 label 只放结构化描述（如 `heading:L2`）。

查询与卡片生成是**只读契约**：零网络请求、不写库、不重新抽取、不推进指针。

---

## 8. 生成派生文档（derive）

```
usage: sourcelore derive [-h] [repository_id]
```

```sh
sourcelore derive <repository_id>
sourcelore derive          # 省略则处理全部仓库
```

- 位置参数 `repository_id` 可选；省略则处理全部仓库。
- 生成仓库派生视图与项目知识文档，**离线，不联网**，只重建 D 层，不碰 A/B/C 层。
- 先看 `tree_status`，`ROOT_ONLY` 是正常真实状态，不要"修正"成 COMPLETE。

---

## 9. 多仓库与证据查询示例

### 9.1 多仓库盘点

用脚本循环调用并聚合，避免逐个刷屏。示例（Python）：

```python
from hermes_tools import terminal
import json

rids = ["repo-a", "repo-b", "repo-c"]
for rid in rids:
    out = terminal(f"sourcelore inspect {rid}", timeout=60)["output"]
    data = json.loads(out, strict=False)
    print(rid, data.get("knowledge_state"), data.get("completeness_status"))
```

每个仓库用 `repositories` 取 `repository_id`，再分别 `inspect`。统计时先确认每个仓库的 Commit 与覆盖状态，再比较。

### 9.2 证据查询与判读

```sh
# 1. 查某路径观察，确认覆盖状态
sourcelore query <rid> --commit <sha> --type path --path docs/README.md

# 2. 查所有命题，找 claim_id
sourcelore query <rid> --commit <sha> --type claims

# 3. 按 claim 生成卡片，查看裁决与证据定位
sourcelore card --repository-id <rid> --claim-id <claim_id>

# 4. 需要审计字段时，用 answer 的 evidence 意图
sourcelore answer <rid> "为什么这些结论可信" --commit <sha>
```

判读顺序：先看 `coverage_state` 与限制 → 再看 `findings[]` 的裁决 → 检查证据完整性（`FULLY_LOCATABLE` 才可逐条核对）→ 核对 `review_status`（`pending_review` 不是人工确认）→ 按 `current_view` 过滤掉历史 Verification。`untrusted_findings[]` 中的 Claim 已被排除。

---

## 10. 在智能体中用自然语言使用

用户不必记命令，直接用自然语言触发。Skill 会把请求映射到对应 CLI：

| 用户说的话 | 实际命令 |
|---|---|
| 用 SourceLore 分析 / 建库 | `analyze <url>` |
| 查已保存的固定 Commit（不问 GitHub） | `analyze <url> --commit <sha>` |
| 只用本地知识，禁止联网 | `analyze <url> --offline` |
| 强制重新获取远程版本 | `analyze <url> --refresh` |
| 有哪些已建的仓库 | `repositories` |
| 介绍 / 使用 / 架构等自然语言问答 | `answer <rid> "<问题>"` |
| 看看这个仓库的知识 | `inspect <rid>` |
| 这个 Commit 里 X 存在吗 | `query <rid> --commit <sha> --type path --path X` |
| 有哪些已登记命题 | `query <rid> --commit <sha> --type claims` |
| 对比两个 Commit | `query <rid> --commit <sha> --compare-commit <sha> --type version` |
| 生成知识卡片 | `card --repository-id <id> --claim-id <id>` |
| 抽取文件内容知识 | `analyze <url> --commit <sha> --include-content` |
| 查源码结构知识 | `query <rid> --commit <sha> --type code` |

边界：用户问"这个项目好不好 / 功能齐不齐 / 文档完善吗"时，不要用知识库硬答，直接说明无此类证据；要求分析私有仓库、创建 Issue/PR、提交代码或执行仓库脚本时，应拒绝。所有回答要说明：是否真正调用了 SourceLore、查询的是哪个仓库与 Commit、实际读到了什么、结果是否经过验证、有哪些覆盖限制、是否发生网络请求或数据修改。

---

## 11. 限制语义速查

- `ROOT_ONLY`：只枚举根目录，不等于 COMPLETE；缺内容属"未分析"。
- `distribution_allowed=false` / `copy_permitted=false`：仅内部预览，不可公开分发；分发门禁 B-1/B-2/B-3 仍开放。
- `review_status=pending_review`：CLI 裁决，非人工确认。
- `PARTIAL` / `insufficient_evidence` / `refuted`：均不得外推为"不存在"或"命题错误"。
- 不执行仓库代码；不支持私有仓库；只接受 `https://github.com/<owner>/<repo>`。
- 未登录受 GitHub 60 次/小时限制；限流时 2 秒内返回 `RATE_LIMITED` 与 `retry_after`，不自动重试。
- 内容受预算限制（单 Blob 256 KiB、单批 2 MiB、候选路径 32、单文件 100 Facts）。
