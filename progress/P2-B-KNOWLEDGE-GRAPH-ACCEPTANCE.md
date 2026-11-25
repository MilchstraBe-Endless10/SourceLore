# P2-B AST 符号统一与可信项目知识图谱 — 专项最终验收存档

> 版本状态：本存档验收的对象是一个**尚未公开发布的开发分支**（`dev/p2b-knowledge-graph`），不是正式 Release。
> 正式发行版本仍为 `0.1.0-beta.3`；未发布 beta.4；beta.1/beta.2/beta.3 的 Tag 均未改动。
> 每个结论都附专项证据；CI 通过和全量回归数字只作背景，**不作为功能验收依据**。
> 本存档为脱敏公开版：不含作者本机绝对路径、不含真实知识库内容原文、不含第三方未授权知识原文。
> 完整原始证据（含本机路径与真实库转储）仅留本地，不随公开仓库分发。

## 1. 范围与身份

- 基准工程：`MilchstraBe-Endless10/SourceLore`，基准 main：`5777e7561fee38505506ecaf4b51c71494638ace`（P2-A 完成点）。
- 开发分支：`dev/p2b-knowledge-graph`（基于 `5777e75`），隔离 Worktree 开发。
- 目标：修复固定 Commit 派生混用、统一 AST/正则符号口径、让派生图谱消费 P2-A 静态关系、统一图谱节点与边身份并保证确定性。
- 本轮不实施 P2-C，不新增图谱问答/LLM 推理/完整调用图/可视化，不发布新版本，不修改已有 Tag。

## 2. 修改文件与真实调用链

修改/新增源码（工作树状态）：

| 文件 | 变更 | 作用 |
| --- | --- | --- |
| `src/views/versioned_assets.py` | 新增 | 统一版本化资产读取权威入口：按 repository_id + commit_sha 严格过滤 snapshot/正文/关系；指定 Commit 缺失不回退；默认走 current_view |
| `src/views/repo_derive_runner.py` | 修改 | `derive_one(commit_sha=...)`；`_load_assets_ex` 走版本化入口；`_code_rows` 改用正式 `source_knowledge.query_code(...)` 并有界分页；`_relations_rows` 消费 P2-A 关系 |
| `src/views/repo_graph_derivation.py` | 修改 | 节点/边 ID 含 repository/commit/路径/作用域/导入方；新增 `RESOLVES_TO`；悬空边剔除并如实记录；覆盖与限制字段；确定性 graph_digest |
| `src/views/repo_miner.py` | 修改 | `_blob_texts` 按固定 Commit 取正文；符号抽取改为 AST 优先、正则仅明确标注 `LITERAL_FALLBACK` 回退，附 symbol 状态覆盖 |
| `src/skill_interface/knowledge_answer.py` | 修改 | answer 侧严格按 commit 加载 snapshot/正文/补充来源；缺失返回 `VERSION_NOT_FOUND`；回传版本选择与符号来源 meta |
| `tests/views/test_p2b_knowledge_graph.py` | 新增 | 图谱身份/关系/确定性/覆盖专项 14 项 |
| `tests/views/test_p2b_commit_isolation.py` | 新增 | 样本 C 固定 Commit 正文与快照隔离 6 项 |

真实派生链（运行时已验证，非静态推断）：

- `derive_one(repository_id, commit_sha)` → `versioned_assets.select_snapshot / load_versioned_assets` → `source_knowledge.query_code(...)`（AST 源码事实）+ `query_module_relations(...)`（P2-A 关系）→ `derive_repo_graph(...)` → `code-graph.json`。
- answer：`knowledge_answer.answer(commit_sha=...)` → `_load_assets_ex` → `_code_rows` → 内容组装；无效 Commit 返回 `VERSION_NOT_FOUND`。

## 3. 固定 Commit 混用：复现与修复

**复现**（独立夹具：同一仓库两个 Commit 含同名 `app.py` 不同正文，最新 snapshot 属于 Commit B）：旧实现 `_load_assets` 按 `created_at` 取最新 snapshot、`_blob_texts` 按写入顺序取正文，`answer(commit=A)` 会把 B 的正文标成 A——混用成立。

**修复**：新增 `versioned_assets.py` 作为唯一版本选择权威入口：

| 策略 | 触发 | 行为 |
| --- | --- | --- |
| `PINNED_COMMIT` | 指定 commit_sha | assets 表按 `commit_sha` 严格过滤；缺失返回 `COMMIT_NOT_FOUND`，不回退新版本 |
| `CURRENT_VIEW` | 未指定 commit | 走 `trust/policy.current_asset_ids` 唯一权威指针 |
| `FALLBACK_LATEST` | current_view 缺失 | 兼容回退最新并显式标注来源 |

指定 Commit 下 snapshot、正文、符号、关系、claim/verification 均按同一 repository_id + commit_sha 读取；D3 补充来源也按其自身 commit 单独校验。样本 C 6 项测试实测：A/B 正文各自隔离、无效 Commit 不回退、默认走 `CURRENT_VIEW`。

## 4. AST 与正则符号统一读取契约

| 状态 | 含义 | 图谱体现 |
| --- | --- | --- |
| `AST_SOURCE` | Python AST / JS-TS tree-sitter 已成功提取 | 优先采用，符号节点携带 source_fact_id / parser_id / version / git_blob_oid / content_asset_id / line_range / provenance / extraction_status |
| `LITERAL_FALLBACK` | 该文件无适用 AST 观察，正文正则回退 | 明确标注，绝不包装成 AST Facts |
| `UNSUPPORTED` | 解析器不支持该文件类型 | 如实标注，不推断 |
| `NOT_CAPTURED` | 内容未捕获 | 如实标注，不从文件名推断 |

derive 源码输入由无效的 `query.run_query(qtype="code")` 改为正式 `source_knowledge.query_code(...)`（实测可读 47 符号 + 153 导入）；有界分页 `SOURCE_FACT_PAGE_SIZE=1000`，并在 meta 中标注来源与上限，不以固定 `max_results=500` 冒充完整图谱。AST 已覆盖但合法无符号的文件不触发正则补全。

## 5. 图谱节点与边身份规则

- 节点 ID 由 `前缀 + sha256(repository_id | commit_sha | 路径 | 限定名 | 作用域)` 派生：不同仓库、不同 Commit、同名不同作用域符号均不归并。
- module_ref ID 含导入方路径：同名 `module_specifier` 跨文件不归并；不同配置上下文关系不无条件合并。
- claim ID 含 commit。每条边起点/终点必须为实际存在的节点；悬空边剔除并计入 `coverage.dangling_edges_dropped`。
- 节点/边均排序后参与 `graph_digest`，输入顺序变化不造成摘要漂移。
- 派生契约版本 `repo-graph/1`（DERIVATION_VERSION，保持既有读者兼容）；写入独立 `code-graph.json`，不覆盖历史图谱产物。

## 6. P2-A 关系消费结果

`_relations_rows` 调用 `query_module_relations(...)`；仅当 `resolution_state=LOCAL_MODULE_RESOLVED` 且 `status=RESOLVED` 且有 `resolved_target_path` 时才建 `RESOLVES_TO` 边，携带导入 Fact ID、relation Fact ID、目标路径、解析配置、适用 Tree、原始来源身份。未解析关系只保留 `SPECIFIER_OBSERVED` 观察节点，不冒充已验证目标；`INSUFFICIENT_TREE` 等状态如实纳入覆盖说明。IMPORTS 不被命名为 CALLS。

## 7. 实际图谱样本（隔离副本，零网络）

| 样本 | Commit | selection | 节点 | 唯一 ID | 边 | 边类型 | 悬空 | 覆盖限制 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| arch-grower | `8f5daf1a…` | PINNED_COMMIT | 221 | 221 | 216 | DECLARES 189 / TREE_CONTAINS 27 / IMPORTS 0 / RESOLVES_TO 0 | 0 | tree COMPLETE depth 2；无关系事实（数据实情，诚实为空） |
| Preact | `dbeba0d5…` | PINNED_COMMIT | 140 | 140 | 158 | DECLARES 69 / IMPORTS 49 / RESOLVES_TO 8 / TREE_CONTAINS 32 | 0 | tree ROOT_ONLY（深度 0，仅根层）；关系状态 RESOLVED 40 |

Preact 的 `RESOLVES_TO` 只有 8 条而关系 RESOLVED 40 条：前者是「同一导入文件→specifier→目标」去重后实际落定的边数，后者是关系事实条数；多个事实可指向同一导入观察，故不等同。Preact 树快照仅根层，源码/关系证据支撑的文件与目标以 `in_tree=false` 补建节点，未凭树缺失删除合法观察，也未把局部图谱冒充完整 Preact 架构。

graph_digest（确定性实测）：

- arch-grower：`545a1f3e555bada84969b6817980047c2733381f6c03750f4a40fd4b681a1d3b`
- Preact：`b33327976cf8731890bd90aa342b27ba4d9ba3afaca8f77c09fcd5c61a7a35a0`

## 8. A 层资产保护

真实库 / P2-B 备份 / 隔离库三库 A 层资产指纹一致：

| 库 | assets | 指纹（前 16） |
| --- | --- | --- |
| 真实库 | 1089 | b81cd1af34145acf |
| P2-B 备份 | 1089 | b81cd1af34145acf |
| 隔离副本 | 1089 | b81cd1af34145acf |

所有派生写入隔离副本的 `派生视图/`，真实库零写入、零网络采集。

## 9. 专项功能验收

新增专项测试 20 项全部通过（图谱结构 14 项 + 固定 Commit 隔离 6 项）。逐条对应 §10：

| # | 判据 | 证据 |
| --- | --- | --- |
| 1 | AST 符号与文档口径一致 | §4；`test_evidence_fields_on_symbol` |
| 2 | 正则为明确标注回退 | §4；repo_miner symbol 状态 |
| 3 | 同 Commit 图谱消费 P2-A 关系 | Preact RESOLVED 40 / RESOLVES_TO 8 |
| 4 | 已解析导入定位真实目标 | `test_resolved_relation_creates_edge` |
| 5 | 未解析不冒充已解析 | `test_unresolved_relation_no_edge` |
| 6 | 不同 Commit 正文不污染 | 样本 C A/B 正文隔离 6 项 |
| 7 | 不同仓库/来源不错误归并 | `test_repo_isolation_same_symbol` / §8 D3 |
| 8 | 节点无重复 ID | `test_no_duplicate_node_ids`；两样本 uniq=节点数 |
| 9 | 无悬空边 | `test_no_dangling_edges`；两样本 dangling=0 |
| 10 | graph_digest 确定性 | §7 摘要；`test_digest_*` 2 项 |
| 11 | 重复派生幂等 | Preact 连续派生 3 次摘要均为 `b33327976cf…`，一致 |
| 12 | 不改 A 层资产 | §8 三库指纹一致 |
| 13 | D3/P2-A/P0/P1 回归有效 | §10 全量回归 |
| 14 | 安装态 CLI 生成/读取图谱 | §12 安装态校验 |

## 10. 全量回归

逐文件直接运行 `tests/**/test_*.py`（脚本式测试，模块级 sys.exit，cwd=文件目录、PYTHONPATH=src/*、隔离数据根）。

- 重点模块：views 6/6、module_resolution 11/11、trust 4/4、skill_interface 11/11、source_analysis 3/3、content_persistence 5/5 全通过。
- 全量结果：`116` 个测试文件逐文件运行，`PASS=116 FAIL=0`（含 views 6/6、module_resolution 11/11、trust 4/4、skill_interface 11/11、source_analysis 3/3、content_persistence 5/5）。CI 状态只作背景，不作为功能验收依据。

## 11. 门禁判级

| 门禁 | 结论 | 依据 |
| --- | --- | --- |
| FIXED_COMMIT_DERIVATION_INTEGRITY | PASS | 样本 C 6 项 + §3 |
| CANONICAL_SYMBOL_MODEL_READY | PASS | §4 统一字段与状态 |
| AST_PRIMARY_FALLBACK_CORRECT | PASS | §4 AST 优先 + 明确回退 |
| RESOLVED_RELATION_GRAPH_READY | PASS | §6 Preact 8 条已验证边 |
| GRAPH_IDENTITY_INTEGRITY | PASS | §5 + 专项 8/9 |
| GRAPH_EVIDENCE_TRACEABLE | PASS | 节点/边携带 source_fact_id / relation_fact_id / blob_oid / 来源身份 |
| GRAPH_COVERAGE_HONESTY | PASS | ROOT_ONLY / in_tree=false / 未解析计数如实记录 |
| GRAPH_DERIVATION_DETERMINISTIC | PASS | §7 摘要 + 顺序不变测试 |
| EXISTING_KNOWLEDGE_PRESERVED | PASS | §8 三库指纹一致 |
| P2B_REGRESSION_PASSED | PASS | §10 全量回归 |

## 12. main Commit / CI / 安装态

- 开发提交：`8a951e21d0a1279e67273994cda7f655cbd08672`（分支 `dev/p2b-knowledge-graph`，基于 `5777e75`）。
- main 合并：fast-forward 至 `8a951e2`；推送后 `main` / `origin/main` / 开发分支均指向 `8a951e2`，ahead/behind 为 `0/0`。
- 用户自有工作区改动在合并前以 stash 保存并在推送后原样恢复，未丢失、未提交。
- CI：run `45658778706`（commit `8a951e2`）`success`；仅作背景，不作为功能验收依据。
- 安装态：本地 `_sourcelore_src/src` 已与开发分支逐字节同步，关键文件 md5 一致；`--version` 仍为 `0.1.0-beta.3`。
- 安装态 marker 标注 `dev_commit=8a951e21d0a1279e67273994cda7f655cbd08672`、`dev_branch=dev/p2b-knowledge-graph`，并明确 `NOT a released version`。
- 安装态 CLI 实跑：隔离库 `derive local:4034d62ed2cf` 成功生成 `code-graph.json`（`graph_digest=545a1f3e555bada84969b6817980047c2733381f6c03750f4a40fd4b681a1d3b`，221 节点 / 216 边，符号走 `source_knowledge.query_code`，`selection=CURRENT_VIEW`）；新图谱可被正常读取，读取路径验证通过。
- 发布边界：`RELEASE_VERSION` 仍 `0.1.0-beta.3`，无 `v0.1.0-beta.4` Tag，无既有 Tag 改动；本轮为开发态同步，非正式 Release。
