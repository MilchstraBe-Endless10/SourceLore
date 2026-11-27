# P2-D3 技术语义知识持久化与跨进程复用 — 验收报告

- 阶段：P2-D3（承接 P2-D2 `b5b21a0`）
- 版本：`0.1.0-beta.3`（**NOT a released version**；无 beta.4 / 无新 Tag / 无 Release）
- 工作分支：`dev/p2d3-semantic-knowledge`
- 日期：2026-11-27
- 分发：内部预览，`distribution_allowed: false`；文档已脱敏，无本机绝对路径、无第三方未授权原文

## 1. 要回答的问题

SourceLore 能否把宿主模型已经研究、理解并有证据支持的技术知识真正保存下来，让**下一次独立会话**直接复用，而不是每次重读全部原文、重做相同研究？

结论：**能，但有明确边界**。在隔离资产上完成端到端验证：语义命题作为新的权威资产类型持久化到同一 `kb.db`，可被独立进程直接查询，正式 answer 优先返回命题而非要求模型重新分析；所有命题强制来源继承、支持性封顶、授权 DENY、证据可回查到原始字节。

## 2. 已复用的历史模块（不新建第四套存储）

| 既有能力 | 位置 | D3 用法 |
|---|---|---|
| Research Packet 生产 | `src/research/research_engine.py` → `src/skill_interface/query.py` | 作为宿主研究的入口；但只产 Research Packet，不产语义命题 |
| 证据/裁决口径 | `src/evidence_claims/*`、`src/trust/*` | `supported/refuted/insufficient_evidence` 口径复用；`verification_status` 复用 EC 术语 |
| 正文派生与全文检索 | `src/views/section_fts.py`（D2 产出） | 语义证据从 `section_fts` 召回，携带 byte/SHA/OID/行号 |
| Storage A 层 | `src/storage/knowledge_store.py` | 语义命题复用同一 `kb.db` 的 A 层，不另建库 |
| 宿主注入式 client | `src/research/llm_adapter.py` | 作为宿主模型协作接口；未注入时拒绝生产 |

## 3. 实际新增功能与源码位置

| 文件 | 作用 |
|---|---|
| `src/semantic_knowledge/semantic_models.py` | 五轴分类契约（`knowledge_kind` / `support_level` / `source_category` / `verification_status` / `coverage_state`）；身份不含时间戳；来源只降不升；`distribution_allowed`/`copy_permitted` 最保守继承 |
| `src/semantic_knowledge/semantic_store.py` | 语义命题持久化 / 幂等 / 回读；按 `asset_type` 精确过滤 |
| `src/semantic_knowledge/semantic_pipeline.py` | 宿主注入 client 提候选命题（只能按证据下标引用）；确定性程序做证据校验、来源继承、支持性封顶、幂等落库 |
| `src/storage/asset_models.py` | `ASSET_TYPES` 新增 `semantic_proposition` |
| `src/skill_interface/cli.py` | 新增 `semantic-produce` / `semantic-query` 子命令 |
| `src/skill_interface/paths.py` | 导入路径注册 `semantic_knowledge` |
| `src/skill_interface/knowledge_answer.py` | answer 增加 `semantic_knowledge` 字段，语义命题按问题相关性确定性排序后置顶，保留 `content_retrieval` 原文回查链 |
| `src/skill_interface/content_capture.py` | D3-00：来源标记条件化；未证实时默认 `UNVERIFIED_REMOTE_SOURCE`，不冒充 `AUTHORIZED_REMOTE_SOURCE` |

## 4. 语义知识分类与数据契约

- 五轴分开：`knowledge_kind`（architecture/dependency/data_flow/core_module/api_surface/install_configuration/…）、`support_level`（directly/partially/not supported）、`source_category`（源码 / 文档自述 / 未验证）、`verification_status`（supported / insufficient_evidence / refuted）、`coverage_state`（answerable / partially / insufficient）。
- **来源只降不升**：证据 `provenance_level`、`copy_permitted`、`distribution_allowed` 原样继承；历史误标（如早期 `SYNTHETIC_FIXTURE`）不得在本层洗白。
- **支持性封顶**：文档自述 + 源码事实类命题 → 最高 `PARTIALLY_SUPPORTED`；无完整证据 → `NOT_SUPPORTED`；`PARTIALLY_SUPPORTED` 映射为 `insufficient_evidence + PARTIAL`，绝不冒充源码已验证。
- **幂等身份**：`logical_identity` 不含时间戳；同命题同证据同内容哈希 → `IDEMPOTENT_ALREADY_PRESENT`；同命题不同内容 → 新增版本、历史保留。
- **授权继承**：任一证据 `distribution_allowed=false` 或 `copy_permitted=false`，命题继承 false。

## 5. 宿主模型与确定性程序的协作流程

1. 确定性程序从 `section_fts` 召回证据包（每条带 index、正文摘要、来源级别、byte/SHA/OID/行号）。
2. 宿主模型只读取证据包，产出候选命题，**只能通过 evidence index 引用证据**，不能自造引用或内容。
3. 未注入 client → `HOST_MODEL_NOT_CONFIGURED`，不产出任何命题，不用模型记忆补写。
4. 确定性程序逐候选：校验下标合法性 → 封顶支持性 → 继承来源与授权 → 计算幂等身份 → 落库。

## 6. Obscura 技术知识生产实例

- 仓库身份：`1209343409`；固定 Commit：`efe1c95962b33935fe9c53851566211074efe147`；18 条正文齐全。
- 证据性质：README、架构文档、MCP 使用文档、`Cargo.toml` 均为**文档自述 / 配置声明**；crate 列表只表述「workspace 清单声明」，不表述运行时调用图。
- 落库结果：7 条有证据命题，覆盖 architecture / dependency / data_flow / install_configuration / api_surface；全部 `PARTIALLY_SUPPORTED` + `insufficient_evidence` + `distribution_allowed=false` + `copy_permitted=false`，证据可定位到 byte/SHA/OID/行号。
- 另有 2 条 D3 早期测试遗留命题（`SYNTHETIC_FIXTURE` 来源），按契约保留、不删除、不洗白。
- 全程零网络请求。

## 7. 证据支持性审查

- 未发现任何命题被错误标为 `supported`：文档自述类命题全部封顶为 `PARTIALLY_SUPPORTED`。
- 历史误标来源 `SYNTHETIC_FIXTURE` 被正确继承（曾发现 `from_match` 未从 match 顶层读取 provenance 导致洗白为空格，已修复并加测试）。
- 负例覆盖：越界证据下标、无证据、错误 commit、错误仓库、文档自述升级为源码事实、授权 DENY 继承 —— 全部有专项断言。

## 8. 持久化与跨进程复用

- 独立进程直接调用正式 CLI `semantic-query` 可读回 9 条命题（7 新 + 2 历史），证明不是依赖当前进程内存、临时 JSON 或对话上下文。
- 正式 `answer` 对同一批问题优先返回语义命题（按问题相关性排序），同时保留原文回查链 `content_retrieval`；零网络、零权威写入。

## 9. 幂等、版本隔离与授权测试

- 幂等：重复生产两次，语义资产数 9→9，全部返回 `IDEMPOTENT_ALREADY_PRESENT`，无重复资产。
- 版本隔离：错误 commit / 错误仓库查询返回 0 条，不串用正文。
- 授权：任一证据 DENY → 命题 DENY；分发 DENY 保持；未授权内容不通过命题/摘要/索引/缓存泄露。

## 10. 全量回归实际状态

| 项目 | 结果 |
|---|---|
| D3 专项语义测试 | 13 PASS / 0 FAIL |
| D3-00 provenance + D2 provenance + D2 section_index | 全部 PASS |
| 全仓逐文件回归（tree-sitter venv） | **126 PASS / 0 FAIL** |
| 先前 7 项环境失败处置 | 使用已有 `sourcelore-release/.venv`（tree-sitter grammar 可用）复跑，全部通过；非功能缺陷、未联网、未改系统环境 |

CI success 不作为功能判级依据；本地真实功能验收已完成。

## 11. 真实六库 A 层保护证据

- 真实库 A 层指纹（`assets` 表身份+内容哈希）：验收前后一致。
- 真实库 `semantic_proposition` 数量：0 —— D3 从未写入真实知识库。
- 隔离副本原有 1219 条非语义资产：全部完整保留，未新增非语义资产；新增仅限 `semantic_proposition` 类型，符合「原有资产子集完整性」口径。

## 12. 当前功能边界与下一阶段任务

边界：
- 语义命题目前由宿主模型（本会话）阅读证据后注入；SourceLore 自身不内置可自动运行的模型，未注入 client 时拒绝生产。
- Obscura 等仓库的证据多为文档自述，命题只能 `PARTIALLY_SUPPORTED`；真正源码验证的事实需未来 Rust 源码解析支持。
- TD-004 宿主自动触发仍待真实会话验收，本轮保持 `PARTIAL / NOT_VERIFIED`，未用内部 CLI 冒充宿主验收。

下一阶段（不在本轮范围）：P3、Rust 正式解析器、beta.4 发布均未启动。

## 13. 提交与安装态

见随附 `p2d3-acceptance-result.json` 与 Git 提交记录。版本保持 `0.1.0-beta.3`，更新 `dev_commit`，明确 `NOT a released version`。
