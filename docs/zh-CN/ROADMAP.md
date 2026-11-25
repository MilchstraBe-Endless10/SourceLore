# SourceLore 路线图

> **发布边界：** 公开 SourceLore 第一方源码仓库，与对外分发第三方采集知识，是两种不同决策。前者仍需 Git 历史隐私和许可证核查；后者受运行时门禁阻断。见[公开发布准备](PUBLIC-RELEASE.md)。

本文说明 SourceLore 已完成、部分完成、未实现与未来扩展的状态。状态严格采用需求文档词汇：`IMPLEMENTED`（已实现）、`PARTIAL`（部分完成）、`PLANNED`（规划中）、`BLOCKED`（受阻）、`NOT_VERIFIED`（未验证）。英文版见 [docs/en/ROADMAP.md](../en/ROADMAP.md)，事实、接口与状态与本文完全一致。

## 1. 状态总览

| 领域 | 状态 |
|---|---|
| M0 环境诊断 | IMPLEMENTED |
| M1 六源上游只读审计 | IMPLEMENTED |
| F1 融合决策 | IMPLEMENTED |
| F2 实现 P0–P6H | IMPLEMENTED |
| P0 可信性修复 | IMPLEMENTED |
| P1 内容问答层（`answer`） | IMPLEMENTED |
| 递归子目录采集 | PARTIAL（`recursive` 参数已实现，受 GitHub API 配额阻断） |
| 深层内容覆盖 | PARTIAL（三仓库仅采 3/4/9 文件） |
| 源码 `imports` 关系 | 已实现共享入库闭环（P2-A；在线/本地/离线三路诚实落库）；完整图谱覆盖仍为 PARTIAL（限于已采集源码） |
| README 语义解析 | PARTIAL（偏结构观察） |
| `answer` 接入 AST Facts / LLM | PLANNED |
| 完整调用图 / 运行时分析 | PLANNED（当前明确不做） |
| 分发合规路径 | BLOCKED（需解决 B-1/B-2/B-3 与许可） |

## 2. 已完成（IMPLEMENTED）

### 2.1 M0 环境诊断

完成本机 OS / Python / Git / Node / DSH / Skill 发现机制 / SQLite FTS5 / GitHub API 可达性的真实命令核验，结论 PASS，无阻塞项（见 `docs/environment-audit.md`）。

### 2.2 M1 六源上游只读审计

固定六个上游的具体 Commit，下载只读本地快照并静态阅读，按「抽象设计思想 / 具体实现」分离处理。审计产物为六份 `docs/upstream-audit-0N-*.md` 与 `docs/upstream-manifest.json`。UPSTREAM-06 无许可证、零复制，处置最严（见 `THIRD_PARTY_NOTICES.md`）。

### 2.3 F1 融合决策

完成能力索引、Crosswalk、批次裁决与冻结基线；冻结 `docs/fusion/CAPABILITY_CROSSWALK.json` 的 SHA-256 为 `42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b`。

### 2.4 F2 实现 P0–P6H

实现并验收从 P0 到 P6H 的各阶段能力：存储分层（A 不可变 / B 当前指针 / C 索引 / D 派生）、采集器、Facts、Evidence-Claims、Lifecycle、Renderer、Research、Skill 接口、产品验收与多仓库等。逐批裁决与验证记录在 `docs/fusion/` 与 `docs/implementation/`。

### 2.5 P0 可信性修复

固化身份核对、证据准入与视图隔离：Commit 占位值拒绝、跨仓库 Commit 阻断、`current_view` 唯一权威、证据完整性降级规则、`ROOT_ONLY` 不冒充 `COMPLETE`。由 `src/trust/policy.py`、`src/trust/tree_scope.py` 与 `tests/trust`（P0 25 项）保障。

### 2.6 P1 内容问答层（`answer`）

核实内容字节、授权门禁、解析器与项目文档生成四大底座已存在后，**未重复建设**，只补齐面向用户的自然语言意图分流与知识回答层：新增 `src/skill_interface/knowledge_answer.py` 与 `answer` 子命令，支持介绍 / 使用 / 架构 / 代码 / 证据 / 完整性六类意图，内容优先，只读、零网络、不编造、不写库。验收见 `progress/P1-CONTENT-QA-2026-11-23.md`（12 项标准全部达成）。

## 3. 部分完成（PARTIAL）

### 3.1 递归子目录采集

`src/collector/tree_collector.py` 已实现 `recursive=True` 的整树枚举与逐层 `_deep_walk` 回退，深度上限 12，`src/trust/tree_scope.py` 能从客观字段把历史误标的 `COMPLETE` 派生为 `ROOT_ONLY`。但当前三个已登记仓库的实际状态仍是 `ROOT_ONLY`：子目录未被系统性采集。递归能力**已实现但受 GitHub API 配额阻断**，等待配额或 token 条件满足后再规模化使用。

### 3.2 深层内容覆盖

已登记的 `captured_blob_content` 属单文件根层补采；三仓库实际只采到 **3 / 4 / 9** 个文件。README 解析偏结构观察（标题、链接、代码块语言），功能语义仅来自引用的 README 首段原文。无法据此回答完整架构或模块设计层面的问题。

### 3.3 源码关系（`imports`）

源码知识已具备 Python AST、JS/TS tree-sitter、tsconfig 感知的模块解析。**P2-A 补齐入库闭环**：共享管线让 GitHub 在线、本地 Git、离线补全三条路径都能诚实落库静态关系，导入方/配置/目标证据身份分离，状态可查（`status` / `status_counts`），写入幂等。夹具实测：样本 A（Python）196 关系 + 139 外部；样本 B（JS/TS）33 关系 + 2 配置事实 + 1 项目事实。完整图谱覆盖仍限于已采集源码——缺少覆盖不等于「不存在依赖」，静态映射也不证明运行时加载。跨文件调用图、类型层级、多跳推理仍不在范围内。

### 3.4 `answer` 的知识来源

`answer` 是确定性检索与组装：内容优先，基于已验证的字节与已登记资产回答，**不接 AST Facts，不接 LLM，不做开放式推理**。

## 4. 未实现 / 规划（PLANNED）

- **扩大内容采集深度**：面向大型项目，覆盖完整架构、模块设计与实现思路；需在配额、预算与授权门禁允许的前提下推进。
- **更充分接入已有 AST Facts**：让 `answer` 能利用已分析的函数、符号与模块事实，而不只依赖内容字节的字面摘录。
- **完整调用图**：当前明确不做；调用图、运行时行为、测试是否通过等结论本库不产出。
- **其他未来扩展**：在保持只读、离线、证据可核查的前提下拓展查询与问答能力。

## 5. 受阻（BLOCKED）

- **分发合规路径**：`distribution_allowed=false`、`copy_permitted=false`，分发门禁 B-1/B-2/B-3 全 OPEN；输出仅为内部预览。任何公开分发都必须先解决这三道门禁与许可问题，并由人工完成 P-3 / P-4 审批。
- **递归采集规模化**：技术上已实现，但因 GitHub API 配额（未认证 60 次/小时）受阻，需等待配额或 token 条件。

## 6. 未验证（NOT_VERIFIED）

- 完整调用图、运行时行为与测试结果类结论：本工具不产出，亦未验证。
- `answer` 接入 AST Facts / LLM 后的效果：尚未实现，因此未验证。
- 多用户主机上的文件权限隔离：`kb.db` 默认 `0644`、目录 `0755`，未做额外加固，隔离效果未验证。

## 7. 共同限制（适用于所有阶段）

- 三仓库 Tree 为 `ROOT_ONLY`：子目录未被系统性采集，架构级回答只覆盖已采文件。
- `captured_blob_content` 为单文件根层补采，三仓库实际只采 3/4/9 个文件。
- 无函数调用图、运行时行为、测试是否通过的证据——本库明确不产出此类结论。
- README 解析偏结构性，功能语义仅来自 README 首段原文引用。
- `distribution_allowed=false`、B-1/B-2/B-3 全 OPEN，输出仅内部预览，不分发。
- `answer` 是确定性检索组装，不接 LLM，不做开放式推理。

## 8. 参考

- 历史验收与缺口：`progress/P1-CONTENT-QA-2026-11-23.md`
- 状态词汇与逐项依据：`docs/en/REQUIREMENTS.md`、`docs/zh-CN/REQUIREMENTS.md`
- 相关文档：[安全与授权](SECURITY.md)、[测试](TESTING.md)、[安装指南](INSTALLATION.md)
