# P2 — Repository Deep Understanding：需求与现有能力差距分析

> 阶段定位：正式进入 P2「仓库深度理解」的**需求与现有能力分析**，本轮只提交基于真实源码的差距分析与开发方案，**不实施任何新功能**。
> 编号说明：本阶段的 "P2" 是路线图阶段名，与历史实现文档中的 `F2-P2A` / `F2-P2B`（Facts / Evidence-Claims 任务编号）不是同一编号体系，不要混淆。
> 证据来源：全部结论来自当前 main（提交 `a001d7a…` 之上）的真实源码，关键处标注 `路径:行`。本轮未重新采集 arch-grower，未做全量回归，未改源码。

## 1. 目标定义

「深度理解」在现有系统里应落到四个可检验问题：

1. 这个仓库**做什么**（项目语义）：来自 README / Manifest / 项目总览。
2. 它**由什么构成**（结构）：Tree 节点、符号、文件归属。
3. 代码**怎么组织**（静态关系）：导入解析、调用/声明边、模块依赖方向。
4. 知识**如何被问答消费**（统一入口）：answer / query 能否基于前三者给出有证据的回答。

现有系统这四层都已存在组件，但**串联深度**和**解析落定程度**参差，这是 P2 要解决的核心。

## 2. 现有组件清单与调用链（真实源码）

### 2.1 解析器层（可复用，成熟）

- 单一分派入口 `src/content_persistence/source_dispatch.py:20` `pick_parser()` / `:31` `parse_source()`：`.py` → `python_ast_parser.py`（`PARSER_VERSION=python-ast/1`，`src/source_analysis/source_models.py:13`）；其余看 `treesitter_runtime.language_for_path()` → `js_ts_parser.py`。不支持的扩展名返回 `PARSER_UNAVAILABLE`（不静默）。
- Python AST 实现 `src/source_analysis/python_ast_parser.py:27` `parse_source()`，按 scope 遍历，产出符号/导入观察。
- JS/TS 实现 `src/source_analysis/js_ts_parser.py:31`，带 grammar 版本（`:90` `parser_version=f"{PARSER_ID}/{GRAMMAR_VERSION[language]}"`）。
- 覆盖判定 `src/source_analysis/semantic_coverage.py:35` `detect_unsupported_forms()` / `:49` `classify()` / `:88` `coverage_report()`：明确区分"解析成功"与"语义被理解"，能报 `UNSUPPORTED_SEMANTIC_FORM`。
- Facts 入库 `src/content_persistence/source_fact_ingest.py`：四条规则 `SOURCE_SYMBOL_DECLARED` / `SOURCE_IMPORT_DECLARED` / `SOURCE_EXPORT_DECLARED` / `SOURCE_LOCAL_MODULE_RESOLVED`（`:14-18`），走既有 `FactObservation + ingest_fact` 框架，fact_id 符合 `SL-FACT-[0-9a-f]{40}`（`:29-33`）。
- 在线链路调用点 `src/collector/github_knowledge_extract.py:128` `SD.parse_source()` → `:136` `ingest_source_facts()` → `:153-165` `semantic_coverage`。本地链路同构：`src/skill_interface/local_content_ingest.py:118`、`:207`。

**判断**：这一层可直接复用，无需重开发（也符合 D3 "不得重新开发 AST 解析器" 的约束）。

### 2.2 repo_miner 项目知识挖掘（可复用，但符号口径不统一）

- 主入口 `src/views/repo_miner.py:617` `mine_project_knowledge()`。
- 产物文档固定五类：`project-overview`（`:410`）、`readme`（`:414`/`:447`）、`structure`（`:485`）、`dependencies`（`:569`）、`claims`（`:614`）。answer 正是消费这些文档。
- **符号抽取是正则，不是 AST**：`repo_miner.py:192` `extract_symbols_from_source()` 用 `_JS_EXPORT` / `_PY_DEF` / `_PY_CLASS` 等正则匹配"字面可见的声明"，在 `:631` 被调用。它明确注释"只陈述字面可见的声明"。

**差距**：系统与 AST 两套符号口径并存——AST Facts（`SOURCE_SYMBOL_DECLARED`，带 byte_range/line_range/parser_version）与 repo_miner 正则符号（仅 name/kind/line）。二者未对齐，深度理解时同一符号可能有两种描述，且正则口径无法覆盖 AST 能识别的形态。

### 2.3 derive 派生图谱（可复用，但依赖边未解析落定）

- 入口 `src/views/repo_derive_runner.py:63` `derive_one()`：`:26` `_load_assets()` 读 snapshot/claims/verifications，`:47` `_code_rows()` 通过 `query.run_query(qtype="code")` 取源码观察，然后 `:95` `derive_repo_graph()` + `:102` `mine_project_knowledge()`。
- 图谱 `src/views/repo_graph_derivation.py:284` `derive_repo_graph()`，版本 `DERIVATION_VERSION="repo-graph/1"`（`:26`），产出 nodes/edges 并计算 `graph_digest`（`:350`）。
- 符号/导入边 `repo_graph_derivation.py:113` `build_symbol_and_import_graph()`：`DECLARES` 边标记 `OBSERVED_IN_SOURCE`（`:157`）；`IMPORTS` 边标记 `SPECIFIER_OBSERVED`（`:184`），`module_ref` 节点的 `resolved_in_tree=None`（`:173`，注释"模块是否真实存在由树证据决定，此处不作断言"）。
- 诚实的限制声明：`repo_graph_derivation.py:329-330` "无源码符号/导入观察，模块关系为空不代表没有依赖"；`:321-328` COMPLETE 但仅根层时改判 `ROOT_ONLY`（D3 的 inspect 修正复用此逻辑）。

**差距**：derive 图谱的导入边停留在"观察到 specifier"，没有消费 `module_relation` 的 `LOCAL_MODULE_RESOLVED` 结果，因此 `resolved_in_tree` 永远是 None。两套静态关系表示（derive 的 IMPORTS 边 vs module_relation 的 resolved relation）没有打通。

### 2.4 answer 统一问答（可复用，但是字面检索，非语义理解）

- 入口 `src/skill_interface/knowledge_answer.py:148` `answer()`，确定性检索、不接 LLM（`:11` 注释）。
- 直接复用 `repo_miner.mine_project_knowledge()`（`:165-182`）拿文档，再按 `intent` + `_heading_keywords()`（`:117`，正则关键词）选 section。
- D3 已接入补充源：`:195` `SP.resolve_supplement()`，按 section 追加（`:267`），标 `verified_local_supplement` 与证据引用。

**差距**：answer 是"关键词命中 section"的字面检索，不理解图谱、不做多跳推理；与 derive 图谱（`repo-graph/1`）没有数据通路。深度理解若要回答"模块 A 依赖 B 的哪条路径""这个符号被谁引用"这类问题，当前 answer 无能为力。

### 2.5 静态模块关系三件套（能力已实现，但采集链路未接通）

- 入库 `src/content_persistence/module_relation_ingest.py`：`build_relation_fact()`（`:84`）、`ingest_resolution()`（`:192`）、`ingest_config_observation()`（`:151`）。
- 解析 `src/source_analysis/config_aware_resolver.py` + `local_module_resolver.py:47` `resolve_import()` + `js_ts_module_resolver.py:35` `resolve_js_import()`，支持相对路径、tsconfig `paths`/`base_url`/`references`。
- 查询 `src/content_persistence/module_relation_query.py:20` `query_relations()`；CLI `query --type relation` → `src/skill_interface/source_knowledge.py:30` `query_module_relations()` → `module_relation_query`。另有关系卡片 `render_relation_card()`（`:43`）。
- 裁决适配 `src/content_persistence/module_relation_adapter.py:62` `build_relation_claim()` / `:88` `verify_relation_claim()`。

**关键缺口**：`ingest_resolution()` 的**唯一生产调用点**在 `src/skill_interface/local_content_ingest.py:245`（且被 `:202-203` 限制为 `.ts/.tsx` 文件、依赖存在 tsconfig）。GitHub 在线采集链路 `src/collector/github_knowledge_extract.py` **完全没有调用 relation ingest**（其源码结构段 `:123-173` 只做 parse + source_facts + coverage）。

这正是 D3 专项里 `query --type relation` 对 GitHub ID `1459544036` 返回 `state=NO_RELATIONS` 的根因：不是"查询坏了"，而是**在线链路从未把已解析关系落库**。也不要把 `NO_RELATIONS` 解释成"已验证无依赖"。

## 3. 能力差距矩阵

| 能力 | 现状 | 可直接复用 | 缺口 |
| --- | --- | --- | --- |
| 源码解析（Python AST / JS-TS tree-sitter） | 已实现，带版本与覆盖判定 | ✓ | 语言覆盖受 tree-sitter 语法限制 |
| 源码 Facts（符号/导入/导出/本地解析） | 已实现，走统一 Facts 框架 | ✓ | 与 repo_miner 正则符号口径不一致 |
| 项目文档挖掘（五类 document） | 已实现 | ✓ | 符号用正则，非 AST |
| 派生图谱（repo-graph/1，DECLARES/IMPORTS） | 已实现 | ✓ | 导入边未解析落定，`resolved_in_tree=None` |
| 模块关系解析 + 入库 + 查询 + 卡片 | 已实现 | ✓ | **仅本地链路调用**，GitHub 在线链路未接 |
| answer 统一问答 | 已实现，D3 已接补充源 | ✓ | 字面 section 命中，无图谱通路、无多跳推理 |
| query 分派 | CLI 支持 path/claims/version/content/code/relation/project（`cli.py:74-76`）；内层 `query.py:14` 仅 path/claims/version | 部分 | 两层口径不一，需明确各自职责 |
| 跨文件调用图 / 类型层级 / 项目级依赖聚合 | 未见实现 | — | **确实缺失** |

## 4. 开发方案（仅方案，不在本轮实施）

按依赖顺序，建议分三步，每步独立可验收：

### P2-A — 打通在线链路的静态关系落库

- 在 GitHub 在线采集链路（`github_knowledge_extract.py`）的源码结构段之后，复用 `local_content_ingest._ingest_config_and_relations()` 的同一逻辑（抽取为共享函数），把已解析的 `LOCAL_MODULE_RESOLVED` 关系经 `module_relation_ingest.ingest_resolution()` 落库。
- 覆盖语言不止 `.ts/.tsx`：Python/JS 相对导入走 `local_module_resolver.resolve_import()`。
- 验收：对有完整 tree 的仓库，`query --type relation` 返回具体 relation 事实而非 `NO_RELATIONS`；明确"未采集"与"无关系"两种状态。
- 这是 TD-002 的直接修复。

### P2-B — 统一符号口径并解析落定 derive 图谱

- 让 repo_miner 的符号来源改用 AST Facts（`source_fact_ingest` 产出的 `SOURCE_SYMBOL_DECLARED`），保留正则作为降级路径并标注。
- 让 `repo_graph_derivation.build_symbol_and_import_graph()` 消费 `module_relation` 的 resolved 结果，把 `IMPORTS` 边从 `SPECIFIER_OBSERVED` 升级为 `LOCAL_MODULE_RESOLVED` 并填 `resolved_in_tree`。
- 验收：同一符号在 answer 文档与图谱里口径一致；图谱 module_ref 节点的解析状态可回查到 relation 事实。

### P2-C — answer 接入图谱，支持多跳深度问题

- 为 answer 增加一条"图谱取证"路径：对"依赖/引用/调用链"类意图，从 `repo-graph/1` 与 relation 事实取证据，仍以 D3 的 `supplement_sources` 身份标注机制保留来源。
- 不引入 LLM（保持确定性、可回查）；若未来需要 LLM，另立阶段并保留门禁。
- 验收：answer 能回答"模块 A 依赖谁""符号 X 定义在哪、被哪些文件引用"，每条结论带 fact_id / evidence_ref。

## 5. 门禁与边界（沿用既有约束）

- 不删除/改写 A 层历史资产，不重新采集已有 607 Facts，不重新开发 AST 解析器，不降低可信性门禁。
- 来源身份：跨来源仍以 D3 的权威 `subject_record` + blob 子集为准；不得借 P2 放宽 TD-003 的来源验证边界。
- 不发布新版本、不改已有 Tag、不开发可视化卡片。
- 历史约 340 处私有路径不在本阶段授权范围内。

## 6. 本轮产出与未完成

- 产出：本文档（真实源码能力差距分析 + 三阶段方案），以及已存档的 `D3-FINAL-ACCEPTANCE.md`、`TECH_DEBT.md`。
- 未完成（按用户要求本轮不做）：P2-A/B/C 的代码实现、新功能、全量回归、重新采集、版本发布。
- 未能核验：无法从源码静态确认运行时是否已有其他未提交的 relation 落库路径；结论以 main 当前源码调用点为准。
