# 溯典 · SourceLore 需求规格说明书（简体中文版）

> 文档状态：基于当前源码实现的事实性描述。凡历史规划与当前代码不一致，一律以当前实现为准并显式说明。
> 状态词汇严格限定为 `IMPLEMENTED` / `PARTIAL` / `PLANNED` / `BLOCKED` / `NOT_VERIFIED`。
> 每条需求的"对应源码或测试路径"均指向工程内真实存在的 `src/` 或 `tests/` 路径；路径前缀省略工程根。
> 本英文对应版本见 `docs/en/REQUIREMENTS.md`，两版事实、接口、状态与限制完全一致。

---

## 1. 文档目的与范围

本文档定义 SourceLore 的功能需求与非功能需求，作为实现、验收与审计的共同基线。SourceLore 是一个**本地 GitHub 知识库工具**：它对公开仓库的**固定 Commit** 进行只读采集，把"某路径是否存在""某文件是否声明了某符号"这类**可验证的路径观察命题**登记为 Fact，用既有裁决规则给出 `supported` / `refuted` / `insufficient_evidence` 结论，并保留全部证据引用与限制，供 OpenBot / DSH / Hermes 通过 Skill + CLI 调用。

明确不在范围内：运行时行为分析、完整函数调用图、依赖是否已安装、测试是否通过、代码质量评价、功能是否实现、对外公开发布，以及任何第三方代码的执行。

本文档不编造历史决策；凡涉及设计取舍，仅陈述当前代码中可验证的机制。

---

## 2. 术语与约定

| 术语 | 含义 |
|---|---|
| A 层（`assets`） | 不可变的权威资产层；触发器 `A_LAYER_IMMUTABLE` 阻止任何 UPDATE / DELETE |
| B 层（`current_view`） | 当前视图层；复合主键 `repository_id + logical_identity`，以 `pointer_version` 做 CAS 指针更新 |
| C 层（`index_rows` + 可选 FTS5） | 可重建的派生索引，非权威 |
| D 层 | 查询 / 答案投影与派生文档，只读 |
| Fact（事实） | 一次路径观察的不可变记录 |
| Claim（命题） | 由 Fact 支撑的可验证陈述 |
| Verification（裁决） | 对 Claim 的判定：`supported` / `refuted` / `insufficient_evidence` |
| Evidence（证据） | 可定位的引用（字节偏移、行号等） |
| `current_asset_ids` | 唯一标识当前有效资产的来源（`src/trust/policy.py`） |
| `pending_review` | 表示裁决来自 CLI，尚未经人工确认 |
| `ROOT_ONLY` / `COMPLETE` / `PARTIAL` | 快照完整性状态；`ROOT_ONLY` 表示仅根层枚举、存在未展开子树，不得冒充 `COMPLETE` |
| `distribution_allowed` | 分发许可标志；恒为 `false`，仅允许内部预览 |

---

## 3. 总体架构（与实现一致）

```mermaid
flowchart LR
    U[用户 / OpenBot / DSH / Hermes] --> S[SourceLore Skill]
    S --> C[CLI: analyze / query / answer / derive / card]
    C --> G[采集层: GitHub 客户端 / 请求预算 / 采集策略]
    G --> P[分析层: 内容抽取 / Python ast / JS-TS tree-sitter / 模块解析]
    P --> E[Fact / Claim / Verification / Evidence]
    E --> ST[(存储: A 不可变 / B 当前指针 / C 索引)]
    ST --> Q[查询 / 问答 / 派生视图]
    Q --> D[派生文档]
```

存储边界如实描述：A / B / C 三层位于同一 `knowledge.db`，在同一事务内提交；checkpoint 位于独立的 `cp.db`，靠 `operation_id` 对账，**两者之间不存在全局 ACID**。

---

## 4. 需求规格

### 4.1 项目背景

**痛点。** 面对一个陌生的公开 GitHub 仓库，个人或团队常依赖一次性 LLM 总结来"了解项目"。这类总结存在三个根本问题：

1. **不可回查**：自然语言结论无法逐条对应到 Commit、路径、字节偏移或行号；一旦需要核实"这个结论依据哪一行"，无从追溯。
2. **不可复现与易漂移**：同一项目在不同时间、不同模型下会得到不同总结；Branch 会移动，总结却未绑定固定 Commit，导致"当前版本"的说法随上下文漂移。
3. **混淆观察与推断**：一次性总结常把"存在 Installation 标题"直接说成"安装流程完整可用"，把"清单声明依赖"说成"依赖已安装"，把"存在 test 脚本"说成"测试已通过"。这些都不是可验证的路径观察。

**为何不能只靠一次性 LLM 总结。** 一次性总结没有持久化结构来区分 Fact（观察）、Claim（命题）与 Verification（裁决），也没有"证据不足"（`insufficient_evidence`）与"命题被反驳"（`refuted`）的严格区分。它倾向于在信息空白处以推理补足，而 SourceLore 的纪律恰好相反：没有 Blob 内容 ≠ 文件不存在；有 Fact 但无 Verification ≠ 已 `supported`；解析失败 ≠ 文件没有对应内容。因此一次性总结无法满足可信性要求。

**为何要长期可查询知识库。** 项目知识需要跨版本、跨会话地稳定复用与审计。SourceLore 以固定 Commit 为锚点，把可验证命题及其证据一次性登记、持久化，此后查询与问答均为**只读、零网络**操作；A 层不可变保证历史资产不被覆盖，B 层 CAS 指针保证"当前有效资产"有唯一来源，C 层索引可随时重建。这样，OpenBot / DSH / Hermes 等 Agent 可以在任意时刻对同一 Commit 得到一致的、可逐条核对的答案，而不是重新总结、重新漂移。

### 4.2 产品目标

1. 对公开 GitHub 仓库的固定 Commit 做只读采集，生成可回查的路径观察事实与证据裁决。
2. 提供稳定的 CLI 与 Skill 接口，使 `analyze` / `query` / `answer` / `derive` / `card` 等能力可被 Agent 以结构化 JSON 消费。
3. 严格区分观察、命题、裁决、证据与完整性状态，任何结论都可追溯到源码或测试。
4. 查询与问答默认离线、零网络、不写库；采集受请求预算与授权门禁双重约束。
5. 在受限 API 配额和未闭环的法律门禁下，如实标注 `PARTIAL` / `BLOCKED` / `NOT_VERIFIED`，不将未完成项表述为已完成。

### 4.3 用户与场景

| 用户角色 | 典型场景 | 主要使用命令 |
|---|---|---|
| 独立开发者 | 在接入一个新公开库前，核实某固定版本的目录结构、关键文件、清单依赖是否真实存在，避免凭记忆或营销文档判断 | `analyze --commit ... --offline`、`query --type path / claims / version`、`inspect` |
| 代码学习者 | 以自然语言了解一个项目的用途、安装方式、模块结构与源码符号，并要求答案来自已保存内容而非模型记忆 | `answer <rid> "介绍/怎么使用/架构/源码..."`、`query --type content / code / project` |
| AI Coding Agent 使用者 | 让 OpenBot / DSH / Hermes 通过 Skill 调 CLI，用结构化 JSON 回答，且必须标注覆盖限制、网络请求次数与当前视图状态 | `answer`、`card --code`、`query --show-resolution` |
| 项目维护人员 | 维护知识库资产：登记新 Commit、重建 D 层派生视图、审计可信性、检查分发门禁与不可变层状态 | `analyze --refresh / --resume`、`derive`、`history`、`inspect --content-summary` |

### 4.4 功能需求

#### SL-FR-001 仓库注册与固定 Commit 只读采集
- **需求描述**：对形如 `https://github.com/<owner>/<repo>` 的公开仓库做只读采集，登记仓库身份与固定 Commit，并生成路径观察数据；不得推送、建 Issue 或执行仓库脚本。
- **输入**：仓库 URL；`--ref`（默认 HEAD）、`--path`（默认 `README`）、`--commit`、`--max-requests`。
- **处理逻辑**：校验 URL 仅允许 github.com 主机与常规端口；通过 GitHub 客户端解析 Commit 与 Tree；按采集策略与预算获取；只保存观察载荷与 blob 引用，不执行任何第三方代码。
- **输出**：结构化 JSON，含仓库 ID、Commit、Tree 摘要与采集状态；错误经 `ok:false` 与 stderr 报告。
- **前置条件**：网络可用（离线复用场景除外）；URL 符合白名单。
- **异常情况**：非法 URL／内网地址被拒；GitHub 错误返回退出码 1；离线缓存未命中返回 `OFFLINE_CACHE_MISS`（退出码 3）。
- **验收标准**：仅接受合规 URL；采集全程只读；所有输出为 stdout JSON，错误有退出码。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/skill_interface/analyze.py`、`src/collector/github_client.py`、`src/collector/tree_collector.py`；`tests/skill_interface/test_analyze.py`、`tests/collector/test_github_client.py`。

#### SL-FR-002 离线优先与缓存复用
- **需求描述**：采集优先复用本地已保存快照，避免无谓联网；固定 Commit 且本地快照完整时零网络请求。
- **输入**：`--commit <sha>`、`--offline`、`--refresh`；仓库 URL。
- **处理逻辑**：先做本地查找再决定是否联网；`--offline` 且本地存在则复用并标注"未访问 GitHub"；`--offline` 且本地不存在报 `OFFLINE_CACHE_MISS`；`--refresh` 显式允许重新获取；无 `--commit` 的可变 Branch 返回 `branch_current_unknown: true`。
- **输出**：JSON 中标注缓存来源、网络请求次数与 `branch_current_unknown`。
- **前置条件**：已有本地快照（离线场景）。
- **异常情况**：缓存缺失、Commit 未登记时按状态码返回，不伪造数据。
- **验收标准**：固定 Commit 复用为 0 次网络请求；离线未命中不伪造历史数据；明确"本地快照只能证明过去观测过的版本，不能证明 Branch 当前仍指向它"。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/skill_interface/cache_policy.py`、`src/skill_interface/analyze.py`；`tests/skill_interface/test_offline_cache.py`、`tests/skill_interface/test_multicommit.py`。

#### SL-FR-003 GitHub 请求预算与限流处理
- **需求描述**：约束单次采集的 GitHub 请求数量，并在被限流时快速、真实地返回。
- **输入**：`--request-limit`（默认 8）、`--reserve-requests`（默认 5）、`--max-requests`；可选环境变量 `GITHUB_TOKEN`；`--no-token` 强制单次禁用 Token。
- **处理逻辑**：本地单次请求上限默认 8、主配额优先保留默认 5；读取 `x-ratelimit-*` 头判断主／次级限流；被限流时在约 2 秒内返回 `RATE_LIMITED`，附带真实 `retry_after` 秒数；不自动重试、不空等、不绕过；Token 仅从进程环境读取，不写日志或资产。
- **输出**：预算消耗与限流诊断字段（错误码、`retry_after`）。
- **前置条件**：无。
- **异常情况**：`RATE_LIMITED` / `SECONDARY_RATE_LIMITED` 返回诊断信息；未认证配额为 60 请求/小时。
- **验收标准**：默认值与源码常量一致；限流快速返回且不伪造成功；Token 不落盘。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/collector/request_budget.py`、`src/collector/github_client.py`、`src/collector/acceptance_request_planner.py`；`tests/capture_maintenance/test_request_budget.py`、`tests/skill_interface/test_authenticated_github.py`、`tests/acceptance_orchestration/test_budget_and_resume.py`。

#### SL-FR-004 固定 Commit 与 Tree 完整性标记
- **需求描述**：为采集快照标记真实完整性，截断不冒充完整。
- **输入**：Commit 与 Tree 查询响应；快照载荷中的对象类型与子树字段。
- **处理逻辑**：区分 `COMPLETE` / `ROOT_ONLY` / `PARTIAL`；`tree_scope` 从客观字段派生范围——根层枚举但有未展开子树的历史误标被纠正为 `ROOT_ONLY`；`object_types` 区分 blob / directory / submodule / symlink。
- **输出**：`tree_summary`（完整性状态、条目、`object_types`）。
- **前置条件**：已取得快照载荷。
- **异常情况**：不完整载荷不得作出"路径不存在"的确定否定；`ROOT_ONLY` 对根级精确路径仍可判定，对子目录路径不可。
- **验收标准**：`COMPLETE + 1` 表示完整枚举且确实 1 条；`PARTIAL` 表示仅部分条目；`ROOT_ONLY` 不被标成 `COMPLETE`。
- **当前实现状态**：`IMPLEMENTED`（`ROOT_ONLY` 子目录枚举本身受 API 配额阻断，见 SL-FR-023）。
- **对应源码或测试路径**：`src/collector/tree_collector.py`、`src/collector/source_snapshot.py`、`src/trust/tree_scope.py`、`src/facts/extractor.py`；`tests/trust/test_p0_trust.py`、`tests/collector/test_crash_recovery.py`。

#### SL-FR-005 路径观察 Fact 生成
- **需求描述**：把"某路径是否存在及其类型/内容"登记为不可变 Fact。
- **输入**：快照上下文（`completeness_status`、路径条目、清单版本）。
- **处理逻辑**：命中路径生成 Observed Fact；未命中时，仅当 `COMPLETE` + 清单完整 + 范围覆盖才生成 Absent Fact，否则标 `UNKNOWN`；截断痕迹优先于状态声明。
- **输出**：Fact 记录，含 `completeness_status`、`evidence_refs`、`input_digest`。
- **前置条件**：已登记快照；完整性状态可读。
- **异常情况**：`ROOT_ONLY` / `PARTIAL` 下未命中不得推断"不存在"。
- **验收标准**：`local_coverage_only` 在非 `COMPLETE` 时为真；Absent Fact 仅在 `COMPLETE` 下产生。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/facts/extractor.py`、`src/facts/rules.py`、`src/facts/models.py`、`src/facts/ingest.py`；`tests/facts/test_extractor.py`。

#### SL-FR-006 Claim / Verification / Evidence 分离与裁决
- **需求描述**：把观察（Fact）、命题（Claim）、裁决（Verification）与证据（Evidence）分离，避免"有 Fact 即视为已验证"。
- **输入**：Claim 及其关联 Fact；Fact 引用的证据。
- **处理逻辑**：按封闭规则裁决 `supported` / `refuted` / `insufficient_evidence`；缺少证明不等于具有反证，无证据一律 `insufficient_evidence`；`refuted` 前必须通过反证准入（object_type / sha / mode / observed_at 一致性）；`review_status` 默认为 `pending_review`，仅人工动作可改为 `approved`。
- **输出**：Verification 记录（状态、`fact_ids`、哈希、`review_status`）。
- **前置条件**：Claim 与 Fact 已登记。
- **异常情况**：反证不可靠时不得产生确定 `refuted`；占位 Commit 或跨仓库 Commit 的 Claim 只登记、不裁决。
- **验收标准**：`refuted` 仅对该 Commit 成立，不外推；`pending_review` 不得表述为"已确认"。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/evidence_claims/verifier.py`、`src/evidence_claims/evaluation.py`、`src/evidence_claims/verification_store.py`、`src/evidence_claims/ec_models.py`；`tests/evidence_claims/test_verifier.py`、`tests/evidence_claims/test_gold.py`、`tests/content_persistence/test_claim_verification.py`。

#### SL-FR-007 证据完整性与可定位引用
- **需求描述**：证据链完整性必须单独报告，引用必须可逐条定位。
- **输入**：Fact / Claim 的证据引用（字节偏移、行号、标签）。
- **处理逻辑**：完整性分级 `FULLY_LOCATABLE` / `PARTIALLY_LOCATABLE` / `UNRESOLVED_NO_INTEGRITY`；含 `github:blobs` 等无法解析引用时降为 `PARTIALLY_LOCATABLE`；`untrusted_findings[]` 中的 Claim 被排除，不作结论；`label` 只放结构化描述，不回显不可信原文（D-6 规则）。
- **输出**：证据完整性等级与不可信发现列表。
- **前置条件**：证据引用可读。
- **异常情况**：任一维度缺失即 `ref_complete=false`，不得视为完整引用。
- **验收标准**：只有 `FULLY_LOCATABLE` 才表述为"证据可逐条核对"；不完整链只出诊断卡。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/trust/policy.py`、`src/research/evidence_selector.py`、`src/content/evidence_ranges.py`、`src/content/content_models.py`；`tests/trust/test_p0_trust.py`、`tests/content/test_evidence_ranges.py`、`tests/research/test_evidence.py`。

#### SL-FR-008 P0 可信性规则
- **需求描述**：以集中策略保证 Commit 身份、当前资产来源与范围声明的可信性。
- **输入**：Commit payload、仓库 ID、资产集合、当前视图指针。
- **处理逻辑**：Commit 状态五码 `COMMIT_FORMAT_VALID` / `COMMIT_BOUND_TO_REPOSITORY` / `COMMIT_SNAPSHOT_VERIFIED` / `COMMIT_UNKNOWN` / `COMMIT_IDENTITY_CONFLICT`；占位 Commit（如 `aaaa…`）永不认证；跨仓库 Commit 被阻断；`current_asset_ids` 是唯一当前有效资产来源；`ROOT_ONLY` 不冒充 `COMPLETE`。
- **输出**：可信性判定与允许的资产集合。
- **前置条件**：策略模块可用。
- **异常情况**：身份冲突返回 `COMMIT_IDENTITY_CONFLICT`；未知返回 `COMMIT_UNKNOWN`。
- **验收标准**：报告 `supported` / `refuted` 前先按 `current_view` 当前指针过滤，历史 Verification 只作诊断；派生统计复用统一可信过滤器，不重新实现遍历。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/trust/policy.py`、`src/trust/pointer_rebuild.py`、`src/trust/tree_scope.py`；`tests/trust/test_p0_trust.py`、`tests/trust/phaseD_rebuild.py`。

#### SL-FR-009 A / B / C / D 四层存储
- **需求描述**：以不可变资产、CAS 当前指针、可重建索引和只读投影组织知识。
- **输入**：资产草稿（repository_id、logical_identity、asset_version、content_hash）、操作 ID。
- **处理逻辑**：A 层 `assets` 由触发器 `assets_no_update` / `assets_no_delete` 阻止 UPDATE / DELETE（抛 `A_LAYER_IMMUTABLE`）；资产 ID 含 repository_id 以隔离跨仓库同名身份；同 `(logical_identity, asset_version)` 内容不同而 K2 冲突；B 层 `current_view` 复合主键 + `pointer_version` CAS（首发布要求不存在，否则必须版本相等）；C 层 `index_rows` 与可选 FTS5 可重建；D 层投影只读。A / B / C 在同一 `knowledge.db` 同一事务提交，postcondition 在 COMMIT 前执行。
- **输出**：提交后的资产 / 指针 / 索引状态与 `operation_log`。
- **前置条件**：数据库 schema 已初始化。
- **异常情况**：版本不符返回 CONFLICT；重复 `operation_id` 幂等跳过。
- **验收标准**：A 层任何 UPDATE / DELETE 被触发器阻断；修复只能新增版本 + 隔离视图 + 重新派生，不覆盖权威资产。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/storage/knowledge_store.py`、`src/storage/asset_models.py`、`src/storage/index_store.py`；`tests/storage/test_knowledge_store.py`、`tests/storage/test_cross_process.py`、`tests/storage/test_error_injection.py`、`tests/content_persistence/test_blob_immutability.py`。

#### SL-FR-010 checkpoint 与跨库对账
- **需求描述**：为采集 / 派生任务提供可靠 checkpoint，且不污染权威资产命名空间。
- **输入**：task_id、run_id、stage、operation_id。
- **处理逻辑**：checkpoint 存于独立 `cp.db`，其根路径不得落在 A/B/C 资产命名空间；以 `operation_id` 与资产库对账；版本不匹配返回 CONFLICT，记录不存在返回 NOT_FOUND，库损坏返回 `CHECKPOINT_CORRUPT`；检测版本双重推进。
- **输出**：checkpoint 记录与对账诊断。
- **前置条件**：checkpoint 库可用、路径合规。
- **异常情况**：跨库不存在全局事务，落后状态靠 `operation_id` 收敛。
- **验收标准**：checkpoint 不写入资产命名空间；不宣称跨库 ACID。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/runtime/checkpoint_store.py`、`src/runtime/asset_checkpoint_coordinator.py`、`src/runtime/resume_coordinator.py`；`tests/runtime/test_checkpoint_store.py`、`tests/runtime/test_concurrency.py`、`tests/runtime/test_crash_recovery.py`。

#### SL-FR-011 内容级抽取
- **需求描述**：对已保存快照的 Blob 内容做有限抽取，生成内容 Fact 与证据。
- **输入**：`--include-content`、`--content-path`、`--commit`；已采集的 Blob 字节。
- **处理逻辑**：先查 `snapshot_inventory.content_captured`；无字节则报 `CONTENT_NOT_CAPTURED`，不得凭路径猜内容；解析器：README/Markdown/文本提取标题层级与行号、链接目标、代码块语言；`package.json` 提取 name/version、依赖声明、scripts；`pyproject.toml` 提取 project 字段、dependencies、tool 表（需本机 `tomllib`，否则 `PARSER_UNAVAILABLE`）；其它仅文件元数据。
- **输出**：内容 Fact（`ContentEvidenceRef` 同时给字节偏移与行号）。
- **前置条件**：Blob 内容字节已采集。
- **异常情况**：`BLOB_TOO_LARGE` / `BINARY_CONTENT` / `UNSUPPORTED_ENCODING` / `CONTENT_PARSE_FAILED` / `CONTENT_PARTIAL`。
- **验收标准**：`content_captured=0` 时如实说"内容未采集"；README 有 Installation 标题 ≠ 安装流程可运行。
- **当前实现状态**：`IMPLEMENTED`（解析器集合有限，见限制）。
- **对应源码或测试路径**：`src/content/content_extractor.py`、`src/content/blob_reader.py`、`src/content/parsers/readme.py`、`src/content/parsers/package_json.py`、`src/content/parsers/pyproject_toml.py`、`src/content_acquisition/raw_blob_capture.py`；`tests/content/test_content_e2e.py`、`tests/content/test_readme_parser.py`、`tests/content/test_manifest_parser.py`。

#### SL-FR-012 内容预算
- **需求描述**：限制内容抽取的资源消耗，超限明确报错。
- **输入**：单 Blob 字节数、单批字节数、候选路径数、单文件 Fact 数。
- **处理逻辑**：上限为单 Blob 256 KiB、单批 2 MiB、候选路径 32、单文件 100 Facts；超限分别抛 `BLOB_TOO_LARGE` / `BATCH_BYTE_LIMIT` / `BATCH_PATH_LIMIT`。
- **输出**：预算校验结果与超限错误码。
- **前置条件**：无。
- **异常情况**：任一上限被突破即拒绝，不静默截断。
- **验收标准**：四个默认常量与源码一致；错误码可辨别。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/content/content_budget.py`；`tests/content/test_content_budget.py`。

#### SL-FR-013 Python 源码结构知识
- **需求描述**：用标准库 `ast` 抽取 Python 文件的符号与导入导出事实。
- **输入**：`query --type code --path P [--symbol NAME] [--symbol-kind K] [--module M]`。
- **处理逻辑**：记录声明、`qualified_name`（按语法嵌套如 `Worker.run`，非同名拼接）、`relative_level`、`alias`、`star_import`、`source_scope`；同名定义按出现序号区分、各自保留位置；装饰器只记存在性，不解释运行效果；条件导入、`TYPE_CHECKING`、函数内导入保留语境，不提升为无条件依赖。
- **输出**：源码符号 / 导入 / 导出 Fact。
- **前置条件**：对应 `.py` 内容已采集。
- **异常情况**：语法错误时不产生权威事实，只记录诊断；解析器缺失返回 `PARSER_UNAVAILABLE`，不用正则替代。
- **验收标准**：`SOURCE_SYMBOL_DECLARED` 仅表示"声明了"，不代表执行或完成某任务；不完整源码不得作文件范围确定否定。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/source_analysis/python_ast_parser.py`、`src/source_analysis/source_models.py`、`src/source_analysis/semantic_coverage.py`；`tests/source_analysis/test_python_ast.py`、`tests/source_analysis/test_source_gold.py`、`tests/source_analysis/test_storage_integration.py`。

#### SL-FR-014 JS / TS 源码结构知识
- **需求描述**：用 tree-sitter 抽取 JS/JSX/TS/TSX 的符号与导入导出事实。
- **输入**：`query --type code --path P`；`card --path P --code`。
- **处理逻辑**：grammar 固定为 tree-sitter-javascript 0.25.0、tree-sitter-typescript 0.23.2，安装于项目 `.venv`；符号类型含 `js_function` / `js_async_function` / `js_generator_function` / `js_class` / `js_method` / `js_object_method` / `js_variable` / `js_arrow_function` / `js_function_expression` / `ts_interface` / `ts_type_alias` / `ts_enum` / `ts_namespace`；`require("x")` 记为调用观察 `LITERAL_REQUIRE_CALL_OBSERVED` 而非 ESM 声明；`require(var)` → `DYNAMIC_MODULE_SPECIFIER`；`import type` 标 `is_type_only=true`，不作运行时依赖。
- **输出**：符号 / 导入 / 导出 Fact；`card --code` 返回 `{"format":"bot_block", "text":"<点阵表格>", "network_requests":0}`。
- **前置条件**：`.venv` 中 grammar 可用。
- **异常情况**：grammar 缺失返回 `PARSER_UNAVAILABLE`，不降级为正则。
- **验收标准**：arrow 绑定 ≠ function declaration；interface ≠ class；匿名 default export 不编造名字；点阵五档 `▣/▤/□/△/·` 语义严格区分。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/source_analysis/js_ts_parser.py`、`js_ts_symbol_rules.py`、`js_ts_import_export_rules.py`、`treesitter_runtime.py`、`src/renderer/source_card_models.py`；`requirements-treesitter.txt`；`tests/js_ts_analysis/test_parser_compatibility.py`、`tests/js_ts_analysis/test_symbols.py`、`tests/bot_presentation/test_bot_card.py`。

#### SL-FR-015 TypeScript 项目知识
- **需求描述**：从 tsconfig / jsconfig 推导项目归属与项目上下文。
- **输入**：`query --type project [--config P] [--file P] [--show-resolution]`。
- **处理逻辑**：只认标准命名 tsconfig.json / jsconfig.json；`extends` 继承 `files`/`include`/`exclude` 但不继承 `references`；`files` 优先于 `include` 且不受 `exclude` 影响；`exclude` 只过滤 include 扫描；`files: []` 不触发默认扫描；支持 `src/**/*.ts` 等模式子集，不支持 `{a,b}` / `!` / 绝对路径 / 多重 `**` → `UNSUPPORTED_SELECTION_RULE`；`references` 只处理同仓库同 Commit 本地配置（目录自动找配置、检测循环与深度上限 8）；归属状态含 `INPUT_EXPLICTLY_LISTED` / `INPUT_MATCHED_INCLUDE` / `INPUT_EXCLUDED_FROM_INCLUDE` / `INPUT_POSSIBLE_VIA_IMPORT` / `INPUT_NOT_PROVEN` 等；多候选为 `PROJECT_CONTEXT_AMBIGUOUS`，不任选。
- **输出**：项目发现、文件归属与项目上下文状态。
- **前置条件**：配置文件内容已登记。
- **异常情况**：配置内容未采集为 `CONFIG_CONTENT_NOT_CAPTURED`，不猜仓库没有 tsconfig、不读工作目录、不借用其他 Commit。
- **验收标准**：`INPUT_EXCLUDED_FROM_INCLUDE` ≠ 不可能进入 TypeScript Program；`PROJECT_REFERENCE_TARGET_VERIFIED` 不代表 B 已构建或 A 已使用其产物。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/source_analysis/ts_project_*.py`、`tsconfig*.py`、`ts_file_membership.py`、`src/content_persistence/ts_project_query.py`；`tests/ts_projects/test_project_discovery.py`、`test_files_include_exclude.py`、`test_project_references.py`、`test_inheritance_membership.py`、`test_node_condition_order.py`。

#### SL-FR-016 配置感知模块解析
- **需求描述**：结合 tsconfig / jsconfig 与 package.json 解释 JS/TS 模块引用，分层标注解析状态。
- **输入**：`query --type relation [--path P] [--module SPEC] [--show-resolution]`。
- **处理逻辑**：三层状态严格分离——`MODULE_REFERENCE_OBSERVED`（观察）→ `CONFIG_MAPPING_CANDIDATE`（配置候选）→ `LOCAL_MODULE_RESOLVED`（当前 Commit Tree 唯一命中）；tsconfig paths 优先级为精确 > 通配（前缀长者胜）> `*`，`baseUrl` 缺失以配置目录为基准；`exports` 未列子路径 → `SUBPATH_NOT_IN_EXPORTS`，`null` 阻断；条件导出 `default` 为兜底，多条件同可用 → `MULTIPLE_CONDITIONS_AVAILABLE` 不任选；Node 条件导出键按原始顺序匹配；本版只支持明确相对路径（`./x` / `../y`），裸模块名 / `@/alias` / `#hash` → `UNSUPPORTED_RESOLUTION_POLICY`。
- **输出**：模块解析状态与七态结果（`LOCAL_MODULE_RESOLVED` / `RELATIVE_PATH_CANDIDATE_FOUND` / `AMBIGUOUS_CANDIDATES` / `EXTERNAL_OR_UNRESOLVED` / `UNSUPPORTED_RESOLUTION_POLICY` / `INSUFFICIENT_TREE_COVERAGE` / `DYNAMIC_SPECIFIER`）。
- **前置条件**：配置内容与 Tree 已登记。
- **异常情况**：越界目标 → `PATH_ESCAPES_REPOSITORY`；npm 包 / 绝对路径继承 → `CONFIG_INHERITANCE_UNRESOLVED`。
- **验收标准**：**不存在 `RUNTIME_IMPORT_VERIFIED`**——不验证运行时加载；`SOURCE_LOCAL_MODULE_RESOLVED` 不构成依赖图；绝不跨 Commit 补全，绝不从本机已安装包推断。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/source_analysis/config_aware_resolver.py`、`js_ts_module_resolver.py`、`local_module_resolver.py`、`package_module_map_parser.py`、`src/content_persistence/module_relation_query.py`；`tests/module_resolution/test_paths_mapping.py`、`test_package_maps.py`、`test_tsconfig_inheritance.py`、`test_tsconfig_jsonc.py`、`test_monorepo_scope.py`。

#### SL-FR-017 结构化查询接口
- **需求描述**：提供不重新采集的只读查询，按类型返回不同知识。
- **输入**：`query <repository_id> --commit <sha> --type <type>`；`--type` 取值 `path|claims|version|content|code|relation|project`；辅助参数 `--path --compare-commit --max-results --symbol --symbol-kind --module --show-resolution --config --file`。
- **处理逻辑**：`version` 用 `--compare-commit` 对比两 Commit；`content` 类型必需 `--commit`；仅相对路径被解析；查询按 `current_view` 当前指针过滤。
- **输出**：各类型对应的结构化 JSON；`network_requests: 0`。
- **前置条件**：仓库与 Commit 已登记。
- **异常情况**：仓库未登记、Commit 未登记、内容未采集等返回明确状态码。
- **验收标准**：九种内容状态严格区分（`REPOSITORY_NOT_REGISTERED` / `COMMIT_NOT_REGISTERED` / `CONTENT_NOT_CAPTURED` / `CONTENT_INTEGRITY_FAILED` / `FACT_NOT_REGISTERED` / `INSUFFICIENT_EVIDENCE` / `SUPPORTED` / `REFUTED` / `RETRIEVAL_ERROR`），不得合并。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/skill_interface/query.py`、`src/skill_interface/cli.py`、`src/content_persistence/content_knowledge_query.py`、`source_knowledge_query.py`、`module_relation_query.py`、`ts_project_query.py`；`tests/skill_interface/test_query.py`、`tests/skill_interface/test_cli.py`。

#### SL-FR-018 自然语言问答（六意图）
- **需求描述**：以内容优先、只读零网络的方式回答"介绍 / 使用 / 架构 / 源码 / 证据 / 完整性"六类问题。
- **输入**：`answer <repository_id> "<问题>" [--commit]`。
- **处理逻辑**：意图识别按关键词顺序匹配、默认回退 `introduce`；`introduce` 取 project-overview 的 purpose/stack/entrypoints/core_impl；`usage` 优先 readme 标题命中 Install/Usage 等；`architecture` 取 entrypoints/coverage/file-structure/dependencies；`code` 取源码相关文档；`evidence` 与 `completeness` 才附加审计字段；审计统计必须按 `current_view` 当前指针过滤裁决。
- **输出**：JSON 含 `intent`、`blocks`、`audit`（仅两类意图出现）、`coverage_note`、`distribution_allowed: false`、`network_requests: 0`、`wrote_assets: 0`。
- **前置条件**：D 层派生文档已生成。
- **异常情况**：无来源支持的内容如实标注，不从文件名推断。
- **验收标准**：普通用户答案不夹带 Fact/Verification 统计；审计字段只在 `evidence` / `completeness` 出现；来源级别、审核状态、Commit 与限制均保留。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/skill_interface/knowledge_answer.py`、`src/skill_interface/knowledge.py`、`src/views/repo_miner.py`；`tests/skill_interface/test_knowledge_answer.py`。

#### SL-FR-019 派生视图重建（derive）
- **需求描述**：仅重建 D 层派生视图与项目知识文档，离线不联网。
- **输入**：`derive [repository_id]`（省略则处理全部仓库）。
- **处理逻辑**：从已登记代码观察喂入图谱推导、生成 repo card 视图与知识视图；所有派生操作基于本地已登记资产，不重新采集。
- **输出**：派生文档写入 D 层及执行报告。
- **前置条件**：A/B/C 层资产已登记。
- **异常情况**：重新派生不覆盖 A 层权威资产。
- **验收标准**：`derive` 为只读地重建 D 层；无网络请求；历史规划中"只入库不建命题"的缺口已修复（始终以当前实现为准）。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/views/repo_derive_runner.py`、`repo_graph_derivation.py`、`repo_card_projection.py`、`knowledge_view_assembler.py`；`tests/views/test_knowledge_view.py`、`tests/views/test_multiversion.py`、`tests/product_multirepo/test_plan_consistency.py`。

#### SL-FR-020 知识卡片
- **需求描述**：按证据链完整性生成不同卡片，内部预览不可冒充正式发布。
- **输入**：`card --repository-id <id> [--claim-id --verification-id --content-fact-id --content-claim-id --commit --path --code --vault]`。
- **处理逻辑**：内容卡类型 `README_CONTENT_CARD` / `MANIFEST_CONTENT_CARD` / `CONTENT_FACT_DETAIL` / `CONTENT_EVIDENCE_ERROR`；证据链不完整只出诊断卡，绝不出满分卡；默认不回显大段原文；`distribution_allowed=false` 与 `copy_permitted=false` 恒显示；HTML 输出经安全渲染。
- **输出**：默认 `bot_block` 点阵文本（可直接在 Bot 对话显示，不生成网页、不写文件），或安全 HTML／Obsidian vault 导出。
- **前置条件**：相应资产与证据已登记。
- **异常情况**：来源为 `TEST_ONLY` 时必须显式说明。
- **验收标准**：证据不完整时只出诊断卡；卡片保留来源等级、审核状态、Commit 与限制。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/renderer/card_renderer.py`、`card_models.py`、`content_card_models.py`、`source_card_models.py`、`module_relation_card_models.py`、`ts_project_card_models.py`、`safe_html.py`、`src/skill_interface/content_card.py`；`tests/renderer/test_cards.py`、`tests/renderer/test_html_security.py`、`tests/bot_presentation/test_bot_card.py`。

#### SL-FR-021 辅助命令（status / repositories / inspect / history）
- **需求描述**：提供知识库状态与已登记资产的概览能力。
- **输入**：无参命令 `status`、`repositories`；`inspect <repository_id> [--content-summary]`；`history <repository_id>`。
- **处理逻辑**：`inspect --content-summary` 区分四种计数——`file_entries`（同 Blob 多路径重复计）、`unique_blobs`（唯一 Blob OID）、`content_assets`、`facts`，不得混为一谈；`history` 列已登记历史版本。
- **输出**：结构化概览 JSON。
- **前置条件**：知识库已建立。
- **异常情况**：知识库未建立返回退出码 3。
- **验收标准**：计数口径互不混淆；命令与真实 help 一致。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/skill_interface/status.py`、`src/skill_interface/knowledge.py`、`src/skill_interface/cli.py`；`tests/skill_interface/test_cli.py`、`tests/product_acceptance/test_product_workflow.py`。

#### SL-FR-022 五维授权门禁与分发限制
- **需求描述**：把采集与使用的授权拆成五个独立维度，且分发恒被阻断。
- **输入**：授权类型（项目自有 / 原创测试夹具 / 已观测许可证 / 用户显式授权）、核验状态、仓库 ID、scope、source。
- **处理逻辑**：五维动作为 `FETCH`（fetch）、`PERSIST`（persist_bytes）、`DERIVE_FACTS`（derive_facts）、`PREVIEW`（internal_preview）、`DISTRIBUTE`（external_distribution）；每类授权依据允许前四维，分发恒不允许；裸布尔不得直接当授权，须构造可审计授权引用；`preview_allowed=True` 与 `distribution_allowed=False` 独立；B-1（第三方声明措辞）/ B-2（UPSTREAM-06 法律审查，`copy_permitted=false`）/ B-3（署名义务）三项门禁仍 OPEN。
- **输出**：逐维 ALLOW / DENY / UNKNOWN 决策与原因码。
- **前置条件**：授权引用结构完整。
- **异常情况**：未知授权类型或核验状态被拒绝。
- **验收标准**：`distribution_allowed` 恒为 `false`；UPSTREAM-06 无许可证，零代码复制，只描述机制形状。
- **当前实现状态**：`IMPLEMENTED`（门禁本身已实现）；对外分发为 `BLOCKED`（B-1/B-2/B-3 未闭环）。
- **对应源码或测试路径**：`src/collector/content_acquisition_policy.py`、`src/renderer/pre_publish_check.py`、`src/views/view_models.py`、`docs/upstream-audit-06-repo-security-review.md`；`tests/content_persistence/test_authorization.py`、`tests/renderer/test_distribution_gates.py`。

#### SL-FR-023 恢复、断点续采与中断处理
- **需求描述**：为长采集任务提供断点续采与崩溃恢复，且不推进指针越界。
- **输入**：`--resume`、`--plan`、`--request-limit`、`--reserve-requests`；checkpoint 记录。
- **处理逻辑**：基于 checkpoint 与操作账本恢复未完成请求；按当前视图过滤避免重复推进；检测版本双重推进；历史规划中 `--resume` 曾为"声明式空参数"，当前已接到真实恢复盘点（以当前实现为准）。
- **输出**：恢复报告与续采结果。
- **前置条件**：存在有效 checkpoint。
- **异常情况**：checkpoint 损坏返回 `CHECKPOINT_CORRUPT`；版本冲突返回 CONFLICT。
- **验收标准**：同一 `operation_id` 不重复写入；不因崩溃导致指针双重推进。
- **当前实现状态**：`IMPLEMENTED`；递归子目录采集为 `BLOCKED`（受 GitHub API 配额限制），当前范围为 `ROOT_ONLY`。
- **对应源码或测试路径**：`src/runtime/resume_coordinator.py`、`src/skill_interface/capture_resume_report.py`、`src/runtime/asset_checkpoint_coordinator.py`；`tests/p6f_capture/test_resume.py`、`test_crash_resume.py`、`tests/runtime/test_crash_recovery.py`。

### 4.5 非功能需求

#### SL-NFR-001 只读安全边界与禁止代码执行
- **需求描述**：绝不执行第三方仓库代码；不 `exec`、不 `eval`、不 import、不跑测试、不执行 shell；只接受 github.com 公开仓库白名单URL，拒绝内网地址与异常端口。
- **输入**：仓库 URL、采集到的文件内容。
- **处理逻辑**：解析而非执行；符号 / 导入仅作观察；HTML 安全渲染防注入。
- **输出**：安全诊断与拒绝原因。
- **异常情况**：非合规 URL 直接拒绝。
- **验收标准**：无任何代码执行路径；HTML 输出通过安全测试。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/collector/github_client.py`、`src/source_analysis/treesitter_runtime.py`、`src/renderer/safe_html.py`；`tests/renderer/test_html_security.py`、`tests/research/test_security.py`。

#### SL-NFR-002 状态词汇与不确定性表达
- **需求描述**：统一使用 `IMPLEMENTED` / `PARTIAL` / `PLANNED` / `BLOCKED` / `NOT_VERIFIED`；严格区分 `supported` / `refuted` / `insufficient_evidence`、`COMPLETE` / `ROOT_ONLY` / `PARTIAL`、内容九态等，不得合并或外推。
- **输入**：各子系统产生的状态字段。
- **处理逻辑**：集中定义状态常量；`pending_review` 不表述为"已确认"；`refuted` 只对该 Commit 成立。
- **输出**：一致的状态字段。
- **异常情况**：未知状态不降级为确定结论。
- **验收标准**：文档中不使用词汇表外的状态；跨层状态语义一致。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/evidence_claims/ec_models.py`、`src/content/content_models.py`、`src/skill_interface/result.py`、`src/trust/policy.py`；`tests/renderer/test_cards.py`。

#### SL-NFR-003 输出契约与退出码
- **需求描述**：stdout 为结构化 JSON，stderr 为可读错误，退出码真实反映结果。
- **输入**：CLI 子命令调用。
- **处理逻辑**：退出码 0 成功、1 执行失败（含 GitHub 错误）、2 参数错误、3 知识库不可用；错误 JSON 形如 `{"ok": false, "error": "...", "message": "..."}`。
- **输出**：JSON + 退出码。
- **异常情况**：`ok:false` 即真实失败，不得粉饰。
- **验收标准**：退出码 0 不等于知识可信，审计以原始资产复核为准。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/skill_interface/result.py`、`src/skill_interface/cli.py`；`tests/skill_interface/test_cli.py`、`tests/skill_interface/test_harness_invocation.py`。

#### SL-NFR-004 查询零网络与离线可用
- **需求描述**：`query` / `answer` / `derive` / `card` 及内容 / 源码 / 关系查询均只读本地、零网络、不写库、不重新抽取、不推进指针。
- **输入**：本地已登记资产。
- **处理逻辑**：所有查询路径返回 `network_requests: 0`；不触发采集。
- **输出**：本地结果 JSON。
- **异常情况**：本地无数据时报状态码，不联网兜底。
- **验收标准**：查询不产生任何网络请求或资产写入。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/content_persistence/content_knowledge_query.py`、`source_knowledge_query.py`、`module_relation_query.py`、`ts_project_query.py` 及只读视图投影实现；`tests/views/test_read_only.py`、`tests/research/test_read_only.py`、`tests/renderer/test_read_only.py`。

#### SL-NFR-005 解析依赖隔离
- **需求描述**：tree-sitter grammar 固定在项目 `.venv`，不修改系统 Python、不自动下载 grammar；缺失返回 `PARSER_UNAVAILABLE`，不降级正则。
- **输入**：`.venv` 中的 grammar 可用性。
- **处理逻辑**：版本固定 tree-sitter 0.26.0、javascript 0.25.0、typescript 0.23.2；运行时检测可用性。
- **输出**：解析器可用性状态。
- **异常情况**：缺失 grammar 返回 `PARSER_UNAVAILABLE` 及原因。
- **验收标准**：无正则兜底；系统 Python 不受影响。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`requirements-treesitter.txt`、`src/source_analysis/treesitter_runtime.py`、`src/content/parsers/pyproject_toml.py`；`tests/js_ts_analysis/test_parser_compatibility.py`、`tests/content/test_manifest_parser.py`。

#### SL-NFR-006 数据根隔离
- **需求描述**：知识数据库 `kb.db` 永不写入 Git 仓库；默认数据根 `~/.sourcelore/`，可用 `--data-root` 或 `SOURCELORE_DATA_ROOT` 覆盖；checkpoint 不得落在资产命名空间。
- **输入**：数据根配置。
- **处理逻辑**：路径校验拒绝仓库内位置与资产命名空间；脚本会拒绝将库写入源仓库。
- **输出**：生效的数据根路径。
- **异常情况**：非法数据根被拒绝。
- **验收标准**：数据库文件不在源仓库；checkpoint 与资产隔离。
- **当前实现状态**：`IMPLEMENTED`。
- **对应源码或测试路径**：`src/skill_interface/paths.py`、`src/runtime/checkpoint_store.py`、`skill/sourcelore/scripts/sourcelore.py`；`tests/runtime/test_checkpoint_store.py`。

#### SL-NFR-007 证据可追溯与审计
- **需求描述**：每条结论可追溯到源码 / 测试 / 设计记录；历史规划与当前代码不一致时以当前实现为准并说明。
- **输入**：需求条目与实现路径。
- **处理逻辑**：FR/NFR 条目附源码与测试路径；审计统计复用统一可信过滤器；派生统计不重复实现遍历。
- **输出**：可核对的追溯映射。
- **异常情况**：无可追溯来源的结论不得写入。
- **验收标准**：每条需求的路径真实存在；未完成项不写成已完成。
- **当前实现状态**：`IMPLEMENTED`（本文档即为该需求的产物）。
- **对应源码或测试路径**：`src/trust/policy.py`、`src/skill_interface/knowledge_answer.py`；`docs/implementation/`、`docs/fusion/`、`tests/trust/test_p0_trust.py`。

#### SL-NFR-008 分发限制与披露控制
- **需求描述**：所有输出为内部预览，不作正式发布；`distribution_allowed=false`、`copy_permitted=false` 恒显示；UPSTREAM-06 无许可证、零代码复制。
- **输入**：卡片 / 报告生成请求。
- **处理逻辑**：预发布检查在 `distribution_allowed` 非 true 时产生 `DISTRIBUTION_GATE_OPEN` 阻断；B-1/B-2/B-3 未闭环。
- **输出**：预览状态与门禁诊断。
- **异常情况**：分发请求被阻断。
- **验收标准**：任何输出都带内部预览标记；UPSTREAM-06 处置有据。
- **当前实现状态**：`IMPLEMENTED`（门禁）；对外分发为 `BLOCKED`。
- **对应源码或测试路径**：`src/renderer/pre_publish_check.py`、`src/collector/content_acquisition_policy.py`、`src/views/view_models.py`、`docs/upstream-audit-06-repo-security-review.md`、`THIRD_PARTY_NOTICES.md`；`tests/renderer/test_distribution_gates.py`。

### 4.6 功能状态表

| 编号 | 功能 | 状态 | 说明 |
|---|---|---|---|
| SL-FR-001 | 仓库注册与固定 Commit 只读采集 | IMPLEMENTED | 仅 github.com 白名单、只读 |
| SL-FR-002 | 离线优先与缓存复用 | IMPLEMENTED | 固定 Commit 复用 0 网络请求 |
| SL-FR-003 | GitHub 请求预算与限流处理 | IMPLEMENTED | 默认上限 8 / 保留 5；限流快速返回 |
| SL-FR-004 | 固定 Commit 与 Tree 完整性标记 | IMPLEMENTED | ROOT_ONLY 不冒充 COMPLETE |
| SL-FR-005 | 路径观察 Fact 生成 | IMPLEMENTED | Absent 仅 COMPLETE 下产生 |
| SL-FR-006 | Claim / Verification / Evidence 分离 | IMPLEMENTED | 三态裁决、pending_review |
| SL-FR-007 | 证据完整性与可定位引用 | IMPLEMENTED | 完整性三级、D-6 标签规则 |
| SL-FR-008 | P0 可信性规则 | IMPLEMENTED | 五码、current_asset_ids、当前视图过滤 |
| SL-FR-009 | A / B / C / D 四层存储 | IMPLEMENTED | A 层触发器不可变；同库单事务 |
| SL-FR-010 | checkpoint 与跨库对账 | IMPLEMENTED | 独立 cp.db；无全局 ACID |
| SL-FR-011 | 内容级抽取 | IMPLEMENTED | 解析器集合有限 |
| SL-FR-012 | 内容预算 | IMPLEMENTED | 256 KiB / 2 MiB / 32 / 100 |
| SL-FR-013 | Python 源码结构知识 | IMPLEMENTED | 标准库 ast |
| SL-FR-014 | JS / TS 源码结构知识 | IMPLEMENTED | tree-sitter 固定版本 |
| SL-FR-015 | TypeScript 项目知识 | IMPLEMENTED | tsconfig / jsconfig 语义 |
| SL-FR-016 | 配置感知模块解析 | IMPLEMENTED | 三层状态；无 RUNTIME_IMPORT_VERIFIED |
| SL-FR-017 | 结构化查询接口 | IMPLEMENTED | 七种 type；内容九态 |
| SL-FR-018 | 自然语言问答（六意图） | IMPLEMENTED | 内容优先，审计字段按需 |
| SL-FR-019 | 派生视图重建（derive） | IMPLEMENTED | 仅重建 D 层，离线 |
| SL-FR-020 | 知识卡片 | IMPLEMENTED | 证据不完整只出诊断卡 |
| SL-FR-021 | 辅助命令 | IMPLEMENTED | status / repositories / inspect / history |
| SL-FR-022 | 五维授权门禁与分发限制 | IMPLEMENTED | 分发为 BLOCKED |
| SL-FR-023 | 恢复、断点续采与中断处理 | IMPLEMENTED | 递归子目录采集 BLOCKED |
| SL-NFR-001 | 只读安全边界与禁止代码执行 | IMPLEMENTED | 无代码执行路径 |
| SL-NFR-002 | 状态词汇与不确定性表达 | IMPLEMENTED | 五态词汇统一 |
| SL-NFR-003 | 输出契约与退出码 | IMPLEMENTED | 0/1/2/3 |
| SL-NFR-004 | 查询零网络与离线可用 | IMPLEMENTED | network_requests: 0 |
| SL-NFR-005 | 解析依赖隔离 | IMPLEMENTED | .venv 隔离 |
| SL-NFR-006 | 数据根隔离 | IMPLEMENTED | kb.db 不入 Git |
| SL-NFR-007 | 证据可追溯与审计 | IMPLEMENTED | 路径可核对 |
| SL-NFR-008 | 分发限制与披露控制 | IMPLEMENTED | 分发为 BLOCKED |

---

## 5. 限制与未完成项（如实标注）

以下项目在任何输出中不得表述为已完成：

| 项目 | 状态 | 依据 |
|---|---|---|
| 递归子目录采集 | `BLOCKED`（GitHub API 配额） | 当前范围 `ROOT_ONLY`，`src/trust/tree_scope.py` |
| 完整函数调用图 | `PLANNED` / `NOT_VERIFIED` | 明确不做；`README.md` 与 Skill 文档 |
| 运行时行为分析 | `PLANNED` / `NOT_VERIFIED` | 不执行仓库代码；SL-NFR-001 |
| 对外公开发布 | `BLOCKED` | B-1/B-2/B-3 未闭环，`distribution_allowed=false` |
| 功能实现 / 测试覆盖 / 代码质量结论 | 不提供 | 超出路径观察范围 |
| 全量 Blob 内容分析 | 不提供 | 内容抽取仅限有限解析器与预算 |

已完成阶段：M0 环境诊断、M1 六源上游只读审计（UPSTREAM-06 无许可证、零代码复制）、F1 融合决策、F2 实现 P0–P6H、P0 可信性修复、P1 内容问答层。

---

## 6. 命令契约（与真实 help 一致，不得杜撰参数）

```
status
repositories
help
analyze <url> [--ref --path --max-requests --commit --offline --refresh --no-token
               --license-known --include-content --content-status --plan --resume
               --request-limit --reserve-requests --content-path]
inspect <repository_id> [--content-summary]
history <repository_id>
query <repository_id> [--commit] [--type path|claims|version|content|code|relation|project]
                       [--path] [--compare-commit] [--max-results] [--symbol]
                       [--symbol-kind] [--module] [--show-resolution] [--config] [--file]
derive [repository_id]
answer <repository_id> "<问题>" [--commit]
card --repository-id <id> [--claim-id --verification-id --content-fact-id
      --content-claim-id --commit --path --code --vault]
```

说明：`--request-limit` 默认 8、`--reserve-requests` 默认 5、`--max-results` 默认 50、`--path` 默认 `README`。历史规划中出现但当前 CLI 不存在的参数（如 `query --language` / `--relation`）已被移除，不得使用。
