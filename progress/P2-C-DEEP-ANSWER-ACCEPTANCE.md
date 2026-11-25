# P2-C 深度问答验收（脱敏版）

> 本报告只记录结构、计数、判定与可回查的证据身份；不含作者本机绝对路径、
> 不含真实知识库内容原文、不含第三方未授权知识原文。完整原始证据仅留本地，
> 不随公开仓库分发。结论均附专项证据；CI 与全量回归数字仅作背景，
> 不作为功能判级依据。

## 0. 范围与基线

- 阶段：P2-C 图谱驱动的仓库深度问答（在 P2-B 知识图谱之上）。
- 基线 main / worktree HEAD：`fb56e18dad61e65bc947877db0e13596c15f1ba6`。
- 工作分支：`dev/p2c-deep-answer`，隔离 worktree 与隔离数据副本；真实库只读。
- 发布边界：未发布 beta.4，未改 Tag，`RELEASE_VERSION` 未变。
- 网络：全程零网络请求；不做新的源码下载或第三方项目代码执行。
- 目标：把正文知识、AST Facts、静态模块关系、派生图谱与 D3 可信补充来源
  接入统一问答；不开发函数调用图、运行时分析、类型推断、模型接入、
  跨项目方案生成、图谱可视化或 beta.4 Release。

## 1. P2-B 图谱异常复现与修复

### 1.1 复现

P2-B 验收第 7 节记录：样本 A（arch-grower）正文有 47 个 AST 符号观察、
153 条导入观察，但图谱 `DECLARES=189`、`IMPORTS=0`、`RESOLVES_TO=0`。

根因不是"图谱无悬空边"或"测试通过"，而是三层口径错误叠加：

1. Python AST 导入事实以 `module_name` / `relative_level` / `imported_name`
   表达，`module_specifier` 为空；旧读取层只认 `source_reference` /
   `module_specifier`，普通 import 被丢弃，from-import 被误当符号声明。
2. 图谱分类用模糊规则（如按 subject 是否有 name 判断符号），未按真实
   rule_id 区分 `SOURCE_SYMBOL_DECLARED` / `SOURCE_IMPORT_DECLARED` /
   `SOURCE_EXPORT_DECLARED` / `SOURCE_LOCAL_MODULE_RESOLVED`。
3. `query_source_facts` 默认 `limit=200`，`_code_rows()` 一次取后截断；
   样本 A 的 `47+153=200` 正好撞上限，是静默截断假象。

### 1.2 修复

- 新建统一契约模块 `src/views/source_fact_contract.py`，按 rule_id 精确分类，
  并把 Python `module_name` + `relative_level` + `imported_name` 规范化为
  `module_specifier` / `source_reference`（只读派生，不改历史 Facts）。
  未知 rule_id 返回 `kind=None`，不冒充符号/导入/关系。
- `_code_rows()` 接入契约并按 kind 标记；`repo_graph_derivation.py` 按
  `s_kind` 精确分派符号/导入/导出，兼容历史夹具的符号 kind。
- 真实分页：`query_source_facts` 用稳定 `ORDER BY asset_id` + `offset`，
  `source_query` 用"再多取一条"探测 `has_more`，`_code_rows()` 循环拉取
  至无更多或有界上限 `MAX_PAGES=20`。
- IMPORT/EXPORT 分离：`import` 建 `IMPORTS`，`re_export` 建 `RE_EXPORTS`；
  节点与边保留 `fact_kind`，不合并身份。
- 多候选 relation：按确定性顺序取 `primary` 建一条主边，
  全部候选与歧义写入节点/边证据，不再无条件 `verified[0]`。
- AST 符号进入项目正文：新增 `AST 符号声明` 段与 AST_SOURCE 逐字摘录，
  AST 已覆盖文件不再被正则错误补全。

### 1.3 修复后真实数字（专项证据）

| 样本 | 源码事实总数 | 符号 | 导入 | 重导出 | 已解析边 | 截断 |
|---|---:|---:|---:|---:|---:|---|
| A（固定 Commit） | 553 | 218 | 335 | 0 | 0 | 否（pages=1） |
| B（固定 Commit） | 236 | 129 | 43 | 64（其中 13 re-export 建边） | 10 | 否（pages=1） |

图谱边计数：A `IMPORTS=335, DECLARES=218, TREE_CONTAINS=27`；
B `DECLARES=80, IMPORTS=43, RE_EXPORTS=13, RESOLVES_TO=10, TREE_CONTAINS=32`。
（A 218 个符号节点全部去重；B 80 个符号节点全部去重。）

证据：`tests/views/test_p2c_graph_semantics.py`，14 项专项判据全绿
（含真实 rule_id 分类、Python/JS specifier 规范化、导入不冒充符号、
符号去重、多候选不盲选、AST 符号进入正文、真实分页无静默截断、
两样本固定 Commit 数字）。

### 1.4 全量回归暴露的 P2-B 遗留退化（一并修复）

P2-C 全量回归改用 `SOURCELORE_PROJECT_ROOT` 显式指向 worktree 源码
（P2-B 回归因读安装态旧副本而未暴露以下问题），发现两处 P2-B 遗留退化，
均在本阶段从根因修复，非放宽测试：

1. 未注册仓库错误码：`knowledge_answer` 改用 `_load_assets_ex` 后，
   所有加载失败统一返回 `VERSION_NOT_FOUND`，破坏 P1 契约
   `REPOSITORY_NOT_REGISTERED`。修复：仅 `NO_SNAPSHOT`（仓库完全未注册）
   沿用原错误码，`COMMIT_NOT_FOUND` 等仍用 `VERSION_NOT_FOUND`，两者语义分离。
2. 核心实现段落缺失：P2-B §3 令 AST 覆盖文件跳过正则回退，但 AST 符号
   进入 core_impl 摘录的 `symbol_kind` 过滤过窄，漏掉 `js_function_expression`
   等细化类型，导致 is-number 的 `module.exports` 无逐字源码摘录。
   修复：按前缀匹配 `function/js_function/class/method` 所有变体，
   不伪造实现，只恢复对已有 AST 事实的合法摘录。

证据：`tests/skill_interface/test_knowledge_answer.py` 8/8 全绿
（用 worktree 源码 + 隔离数据根运行）。

## 2. 图谱真实查询链路

`src/views/graph_query.py`：纯本地只读、确定性，不修改传入图谱，
不模糊匹配建立未验证关系。能力：

- `build_index`：文件/符号/模块引用索引 + 文件级静态依赖邻接
  （一条文件依赖 = `file --IMPORTS/RE_EXPORTS--> module_ref --RESOLVES_TO--> file`）。
- `resolve_entity`：区分 `RESOLVED` / `AMBIGUOUS` / `NOT_FOUND_IN_GRAPH` /
  `NOT_FOUND`，支持路径、模块 specifier、符号名、限定名、节点 ID；
  路径 basename 兜底只返回候选，不建立关系。
- `node_query`：单节点、文件声明的符号、符号所属文件、源码证据位置。
- `forward_dependencies`：正向直接静态依赖，附证据；注明"不代表运行时调用"。
- `reverse_dependencies`：哪些文件导入并解析到目标，附证据；
  注明"反向导入不等于具体函数被调用"。
- `multi_hop`：有界 BFS（默认 `max_hops=4`、`max_visited=5000`、
  `max_paths=50`），环检测、重复节点处理、多候选路径、截断状态、
  不完整覆盖说明；`NO_PATH_FOUND` 注明"不等于证实无依赖"。

证据：`tests/views/test_p2c_graph_query.py`，14 项全绿（实体定位/歧义/
未找到区分、单节点、正反向、多跳、环、有界、不可达、输入不可变、
真实图谱正反向与符号查询）。

## 3. 统一问答与证据联合

`src/skill_interface/deep_answer.py` 在保留 `knowledge_answer.answer()`
接口兼容的前提下，叠加图谱查询；无 LLM、无写资产。

- 检索规划：按问题关键词确定性分流为 `general` / `symbol_lookup` /
  `forward_dependency` / `reverse_dependency` / `multi_hop` / `supplement`，
  只加载相关图谱结果，不输出全部 Facts。
- 输出契约复用现有结构，新增：`intent`、`resolved_entities`、
  `answer_blocks`、`evidence_refs`、`graph_paths`、`supplement_sources`、
  `supplement_relations`、`coverage`、`limitations`、`query_status`、
  `truncation`；明确区分 `network_requests=0`、`wrote_assets=0`。
- 查询状态：`ANSWERED_WITH_GRAPH` / `ANSWERED_WITH_GRAPH_PATHS` /
  `ANSWERED_TEXT_ONLY` / `ENTITY_NOT_LOCATED` / `ENTITY_AMBIGUOUS` /
  `GRAPH_NOT_AVAILABLE` / `VERSION_NOT_FOUND` / `QUERY_ERROR`；
  不用 `ok=true` 代替知识成功。
- 证据联合：正文引用 + 图谱边（`import_fact_id` / `relation_fact_id` /
  `source_ref` / `resolution_state` / `ambiguous_resolution`）汇入
  `evidence_refs`，每条附 `source_role`。

## 4. D3 补充来源联合问答

- 主查询身份保持用户指定 GitHub ID；补充来源按固定 Commit 检索。
- 补充来源（正文与关系）单独标注 `verified_local_supplement` 身份，
  不并入主图谱、不因内容等价扩大身份或使用授权。
- 同名节点不合并；当前两样本补充关系计数为 0，如实报告为空。
- 本轮不宣称 TD-003 来源真实性边界已彻底解决。

证据：问答集 `test_10_supplement_sources_isolated`（所有补充条目角色一致）、
独立夹具 `test_unauthorized_supplement_not_merged`（不同身份节点不合并）。

## 5. 实体定位与歧义

- 支持文件路径、模块名、函数名、类名、限定符号名、导入 specifier、
  图谱节点 ID。
- 同名符号不同作用域 / 同路径不同 Commit → 返回全部候选并标 `AMBIGUOUS`，
  不擅自选定、不以模糊名称建立未验证依赖。
- 无法定位（`NOT_FOUND` / `ENTITY_NOT_LOCATED`）与"已定位但无可用知识"
  严格区分。

证据：`test_p2c_graph_query.py` 的 `test_entity_ambiguous_symbol` /
`test_entity_not_found_distinct`；`test_p2c_independent_fixture.py` 的
`test_multi_version_same_path_isolated` / `test_same_name_symbol_different_scope_ambiguous`。

## 6. 技术问答集（30 题）

`tests/views/test_p2c_deep_answer_qa.py`：30 题覆盖项目功能、符号定位、
直接依赖、反向依赖、多跳关系、多来源检索、多版本隔离、证据缺失与错误前提。
每题带明确预期（intent、是否应有图证据、是否应拒绝），判级"正确答案"
而非返回非空/篇幅/测试全绿。

统计结果：**正确 30 / 30**；跨仓库污染 0；跨版本污染 0；
无证据的已验证关系 0；网络请求 0；写资产 0。
错误前提样例（如 `ghost.py` 运行时调用链、`src/component.js` 函数 A 是否调用 B）
均如实拒绝，不编造图路径。

## 7. 样本 A / B / C 专项

- A（arch-grower）：Graph IR 核心定义定位、graph_ops.py 静态依赖、
  graph.py 反向依赖、Shadow Git 相关函数证据、多跳可达性、
  通过 GitHub ID 检索本地补充、静态依赖与运行时调用区分。
- B（Preact）：JS/TS 符号定位、模块直接依赖、反向依赖、已解析目标证据、
  多跳检索、ROOT_ONLY Tree 与部分正文覆盖下的保守回答。
  不把局部数据描述为完整 Preact 实现。
- C（独立夹具）：`tests/views/test_p2c_independent_fixture.py`，10 项全绿，
  覆盖多版本同名文件、同名不同作用域符号、依赖环、多跳可达、
  不可判定路径、不完整 Tree、多配置候选目标、未授权补充、无效证据、
  大型有界图谱；纯内存夹具，陌生开发环境可独立运行，零数据根依赖。

## 8. 失败案例与能力边界

- Preact `src/index.js → src/component.js` 无多跳路径：前者只有 re-export 边
  且目标未 `RESOLVES_TO`，返回 `NO_PATH_FOUND` 是诚实结果，不编造路径。
- `Graph IR` 是概念名而非图中精确符号：图中无该符号节点时标
  `ENTITY_NOT_LOCATED`，不用模型记忆填充。
- 反向导入依赖不代表具体函数被调用；不做跨文件函数调用图/运行时分析。
- 多跳默认上限 4 跳、访问节点 5000、路径 50；触顶返回截断状态，
  不把截断当"无依赖"。
- 不做新类型推断、不做模型/供应商接入、不做跨项目比较与方案生成。

## 9. 资产保护

- 真实库 / 一致性备份 / 隔离库的 A 层指纹一致：
  `assets 1089 / index_rows 1085 / bindings 2`，指纹 `ddb2072e…`。
- 未修改或删除 A 层历史资产；未重新下载已有源码；未放宽验证策略。
- 用户自有工作区改动（main 上的两处改动）保持不动。
- 所有派生与问答测试只在隔离数据副本上进行。

## 10. 门禁判级（逐项专项证据）

| 门禁 | 判级 | 专项证据 |
|---|---|---|
| GRAPH_SEMANTIC_CLASSIFICATION_INTEGRITY | 通过 | `test_p2c_graph_semantics.py` 14/14；A 218/335/0、B 80/43/13/10 |
| GRAPH_QUERY_ENGINE_READY | 通过 | `test_p2c_graph_query.py` 14/14 |
| ENTITY_RESOLUTION_INTEGRITY | 通过 | graph_query 歧义/未找到区分 + independent_fixture 多版本/多作用域 |
| FORWARD_REVERSE_DEPENDENCY_READY | 通过 | graph_query test_forward/test_reverse + QA 依赖题 |
| BOUNDED_MULTI_HOP_QUERY_READY | 通过 | graph_query bounded/cycle_safe + independent_fixture bounded |
| EVIDENCE_GROUNDED_ANSWER_READY | 通过 | QA evidence_refs 角色齐备 + 图谱边证据字段 |
| CROSS_SOURCE_ANSWER_INTEGRITY | 通过 | QA 补充身份隔离 + independent_fixture 未授权不合并 |
| FIXED_COMMIT_QUERY_INTEGRITY | 通过 | QA 跨版本污染 0 + 语义测试固定 Commit 数字 |
| ANSWER_COVERAGE_HONESTY | 通过 | QA 错误前提拒绝 / NO_PATH_FOUND / 状态枚举 |
| EXISTING_KNOWLEDGE_PRESERVED | 通过 | A 层三库指纹一致 1089/ddb2072e |
| P2C_REGRESSION_PASSED | 通过 | 全量逐文件回归 120/120 PASS / 0 FAIL，见 §11 |

## 11. 全量回归 / CI / 安装态

- 全量回归：见本节末尾"回归结果"行（逐文件脚本，所有 `test_*.py` 独立运行）。
- CI：推送 main 后由 GitHub Actions 执行，状态在提交/推送后回填；
  仅作背景，不作为功能判级依据。
- 安装态：提交合并推送后同步开发代码副本，marker 标注真实 `dev_commit`
  与 `NOT a released version`，CLI 实跑校验；在 §12 回填。

回归结果：**逐文件全部 120 个 `test_*.py`，120 PASS / 0 FAIL**。
回归脚本显式设置 `SOURCELORE_PROJECT_ROOT` 指向 worktree 源码，
保证验证的是 P2-C 代码而非安装态旧副本；含全部 P2-C 专项与 P1/P2-B 回归。

## 12. 当前 main Commit / CI / 安装态校验

- 功能代码 main Commit：`87ca4079b552f6dd4014ae323140a8039e8ee4a5`
  （短 `87ca407`，分支 `dev/p2c-deep-answer` fast-forward 合并后推送）；
  验收文档回填为后续提交 `f6a8520`（无功能代码改动）。
- 用户自有两处改动（`plugin/dsh-sourcelore-cards/client.js`、
  `progress/BOT-CARD-SOLVED-2026-11-20.md`）在 stash → 合并 → push → pop 后
  原样保留，未提交、未删除。
- CI：run `45670128298`，commit `87ca407`，`success`，耗时 1m19s（仅作背景，
  不作为功能判级依据）。
- 安装态：备份旧 `_sourcelore_src` 后，将 worktree `src/` 逐字节复制为安装态
  `src/`（`diff -rq` 无差异），清除陈旧 `__pycache__`；两个 marker 的
  `dev_commit` 统一更新为 `87ca407`、`dev_branch=dev/p2c-deep-answer`，
  标注 `NOT a released version`、`RELEASE_VERSION` 仍为 `0.1.0-beta.3`、
  无新 tag、无 beta.4。
- 安装态实跑：`--version` 返回 `0.1.0-beta.3`；`status` 指向正确
  `project_root`、5 个仓库可用；`graph_query` / `deep_answer` /
  `source_fact_contract` 均可从安装态路径导入；
  `answer 24313173 "介绍这个项目"` 返回"核心实现（源码逐字摘录）"且
  状态 `FOUND`，证明 §1.4 修复在安装态生效。
- A 层资产保护：real / preserve / isolated 三库指纹一致
  `1089 / ddb2072e65fad724`，未修改任何历史资产。
