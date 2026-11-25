# P2-A 静态模块关系采集与入库闭环 — 专项最终验收存档

> 版本状态：本存档验收的对象是一个**尚未公开发布的开发分支**（`dev/p2a-static-relation`），不是正式 Release。
> 正式发行版本仍为 `0.1.0-beta.3`；未发布 beta.4；beta.1/beta.2/beta.3 的 Tag 均未改动。
> 每个结论都附专项证据；CI 通过和全量回归数字只作背景，**不作为功能验收依据**。
> 本存档为脱敏公开版：不含作者本机绝对路径、不含真实知识库内容原文、不含第三方未授权知识原文。
> 完整原始证据（含本机路径与真实库转储）仅留本地，不随公开仓库分发。

## 1. 范围与身份

- 基准工程：`MilchstraBe-Endless10/SourceLore`，基准 main：`18d181275e87cb97d8c864e66fe8cea3fdc263c3`。
- 开发分支：`dev/p2a-static-relation`（基于 `18d1812`），隔离 Worktree 开发。
- 目标：把在线 GitHub 链路与本地 Git 链路的静态模块关系统一为同一套处理契约，打通「源码字节 → 解析 → 导入观察 → 同 Commit Tree → 模块解析 → 证据校验 → 入库 → 查询」闭环。
- 本轮不实施 P2-B/P2-C，不发布新版本，不修改已有 Tag。

## 2. 修改文件与真实调用链

修改/新增源码（工作树状态，`git status` 实测）：

| 文件 | 变更 | 作用 |
| --- | --- | --- |
| `src/content_persistence/module_relation_pipeline.py` | 新增 | 共享静态关系处理组件，统一 source/config/tree 快照、身份分离、证据校验、幂等写入 |
| `src/content_persistence/relation_backfill.py` | 新增 | 离线增量补全：仅复用已登记 captured bytes，零网络、幂等、A 层不变 |
| `src/content_persistence/source_fact_ingest.py` | 修改 | 新增 `build_import_subject` / `make_import_fact_id`，统一真实落库 import Fact ID 口径 |
| `src/content_persistence/module_relation_ingest.py` | 修改 | 新增 `ingest_unresolved_attempt(...)`，B 层 `evidence_record` 审计账本；修正 `AssetDraft` 顶层 import |
| `src/content_persistence/module_relation_query.py` | 修改 | 新增状态契约 `status` / `attempts` / `status_counts`，历史 `state` 兼容保留 |
| `src/skill_interface/local_content_ingest.py` | 修改 | 本地链路拆分 source/config entries，配置 blob 不再冒充源码 blob，接入共享管线 |
| `src/collector/github_knowledge_extract.py` | 修改 | 在线链路新增 `_tree_paths_from_snapshot`，接入共享管线，provenance 从捕获 meta 继承 |
| `src/skill_interface/source_knowledge.py` | 修改 | 新增 `_d3_supplement_relations`，`include_supplements` 接入 D3 可信补充来源关系 |
| `src/skill_interface/cli.py` | 修改 | 新增 `backfill-relations <repository_id> --commit <sha> [--source-snapshot-id <id>]` 子命令 |

真实调用链（运行时已验证，非仅静态推断）：

- 在线：`github_knowledge_extract.extract_captured()` → `_tree_paths_from_snapshot()` → `MRP.process_source_relations()` → `MRI.ingest_resolution()` / `MRI.ingest_unresolved_attempt()` → `query --type relation`。
- 本地：`local_content_ingest.py` → source/config entries 分离 → `MRP.process_source_relations()` → 同一入库/查询路径。
- 离线：`cli.py backfill-relations` → `relation_backfill.py` 加载 captured bytes → `MRP.process_source_relations()` → 同一入库/查询路径。
- 跨来源：`source_knowledge.query_module_relations(include_supplements=True)` → `source_provenance.resolve_supplement()` → 附加 `supplement_relations`（保留来源身份）。

## 3. 分语言关系支持范围

| 语言 | 复用组件 | 已验证范围 | 边界 |
| --- | --- | --- | --- |
| Python | `local_module_resolver.resolve_import()` | 普通/包/相对/多级相对导入、dotted name 到仓库路径转换、同名歧义、import root 不确定 | 未在仓库内找到的模块记为 unresolved，不判定为已证实外部依赖 |
| JavaScript | `js_ts_module_resolver` | 静态 import/export、相对路径、现有 CommonJS 支持范围 | 动态导入不假设可解析 |
| TypeScript | `config_aware_resolver` + tsconfig 解析器 | paths/baseUrl/references、配置已捕获/缺失/不完整/解析失败区分 | 根目录 tsconfig 不假定适用于项目所有 TS 文件 |

## 4. 实际关系样本与证据定位

确定性夹具（公开独立生成数据，无作者本机路径、零网络）：

- 在线关系夹具 `tests/module_resolution/test_online_relation_capture.py`：已捕获 `pkg/app.py`（`from .utils import helper`）+ 完整 Tree，在线入口落库 1 条本地关系。
  - 查询返回 `state=RELATIONS_FOUND`、`status=RESOLVED`。
  - 关系记录 `importing_file_path=pkg/app.py`、`resolved_target_path=pkg/utils.py`、`resolution_state=LOCAL_MODULE_RESOLVED`。
  - 导入方证据 `importing_blob_oid` 为导入文件自身 blob OID，证据引用不含目标 blob OID——修正了「配置 blob 冒充源码 blob」的定位错误。
  - 第二次运行 `written=0`、`reused>=1`，幂等。
- 样本 C `tests/module_resolution/test_pipeline_sample_c.py`：查询状态契约，区分未解析原因与已解析。

## 5. 在线与本地采集路径的区别

| 维度 | 在线 GitHub 链路 | 本地 Git 链路 |
| --- | --- | --- |
| 输入 | 已捕获并验证的源码字节 + 同 Commit Tree 快照 | 本地 Git 读取的源码 + 配置 entries |
| provenance | 从捕获文件 meta 继承首个有效 `provenance_level`，缺失记 `PROVENANCE_UNKNOWN` 并跳过 | 本地捕获来源 |
| source_snapshot_id | 在线无对应本地快照，记为 `""` | 有本地快照 ID |
| 关系处理 | 共用 `module_relation_pipeline.py`，契约一致 | 共用同一组件，契约一致 |

关键修复：在线链路此前能解析源码生成符号/导入 Facts，但 `ingest_resolution()` 从未在线调用，relation 查询恒为 `NO_RELATIONS`；现已接入并落库（第 4 节夹具佐证）。

## 6. 已有知识离线补全结果

样本 A/B 以真实隔离库副本做零网络 backfill，实测输出：

- 样本 A（arch-grower 副本，`local:4034d62ed2cf`，Commit `8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024`，Python 模块 + 607 Facts）：
  - `status=COMPLETED`、`network_requests=0`、`captured_total=15`、`tree_paths=27`、`tree_completeness=COMPLETE`。
  - `counts`：written=196、reused=0、skipped=139、resolutions=335。
  - `outcomes`：resolved=196、external=139、其余 0。
  - 第二次运行：written=0、reused=196、net=0；A 层资产指纹不变；原有 `607 Facts` 保留，新增 196 relation 事实（该仓库 extracted_fact 由 607 增至 803）。
- 样本 B（Preact 副本，`42283287`，Commit `dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab`，JS/TS + `jsconfig.json`）：
  - `status=COMPLETED`、`network_requests=0`、`captured_total=9`、`source_files=6`、`config_files=1`、`tree_paths=24`、`tree_completeness=COMPLETE`。
  - `counts`：written=33、reused=0、skipped=10、config_facts_written=2、project_facts_written=1。
  - `outcomes`：resolved=33、external=10、其余 0。
  - 第二次运行：written=0、reused=33、net=0；资产指纹不变。
- 真实知识库默认保持只读，未做批量补全或迁移。

## 7. 未解析关系及明确原因

查询新增 `status` / `status_counts`，可区分：源码未分析、导入已观察未解析、Tree 覆盖不足、配置缺失/不完整/解析失败、候选歧义、已解析、声明范围内无匹配、解析器不支持。

未解析状态**不作为 A 层权威 Fact** 写入，改为 B 层 `evidence_record` 审计账本 `module_resolution_attempt`，查询端诚实回显。实测查询中可见 `EXTERNAL_OR_UNRESOLVED` / `CONFIG_NOT_CAPTURED` 等状态；历史 `NO_RELATIONS` 不再直接解释为「已证实无依赖」。

设计约束（非缺陷）：在线默认采集不捕获 `.json`/tsconfig，关系查询对此诚实降级为 `CONFIG_NOT_CAPTURED`，不擅自网络补采。任何静态映射不代表运行时加载成功。

## 8. 资产保护与幂等性验证

- 真实库/备份/隔离库 A 层计数与指纹一致：`assets 1089 / index_rows 1085 / bindings 2`，三库指纹逐字节相同。
- 样本 A/B 两轮 backfill：第二轮 `written=0`、资产指纹不变（A/B 副本 `f41b756d…`，count=1466），无重复资产。
- 旧 Commit 与新 Commit 不混淆：补全按 `repository_id + commit_sha` 定位 captured bytes，未跨 Commit 混用。
- 已有 607 Facts、D3 绑定记录、AST 产物、派生文档均未删改。
- 幂等性另由 `tests/module_resolution/test_relation_backfill.py` 与 `test_backfill_existing_knowledge.py` 覆盖。

## 9. 全量回归结果（背景，不作功能判级）

| 测试集 | 结果 |
| --- | --- |
| `tests/module_resolution` 全量（含在线夹具与 CLI fallback 用例） | 165 tests / OK |
| trust + content_persistence + source_analysis + ts_projects + js_ts_analysis（逐文件） | 23 文件 PASS / 0 FAIL |
| skill_interface + runtime + lifecycle + acceptance_orchestration + product_* + release_installer（逐文件） | 29 文件 PASS / 0 FAIL |
| 正式 CLI 端到端 `p2a_cli_e2e.py` | `FAILS=[]`，A/B backfill rc=0，reused=196/33，network=0 |

## 10. GitHub Commit 与 CI 状态

- 基准 main：`18d181275e87cb97d8c864e66fe8cea3fdc263c3`，其 main push CI 记录 `45636388017` 为 `completed/success`。
- P2-A 开发分支 `dev/p2a-static-relation` 尚未推送，故**尚无该分支专属 CI 运行**；本轮功能判级依据为本地真实执行证据，不引用 CI。
- 推送 main 后应由 CI 复验，结果记录在后续提交；本存档不预判。

## 11. 八项 P2-A 专项门禁逐项判级

| 门禁 | 判级 | 依据（专项证据） |
| --- | --- | --- |
| `SHARED_RELATION_INGEST_READY` | **PASS** | 在线/本地/离线三路共用 `module_relation_pipeline.py`；在线夹具与样本 A/B 真实落库、幂等 |
| `ONLINE_RELATION_CAPTURE_READY` | **PASS** | `test_online_relation_capture.py` 2/2：在线入口落库 1 条本地关系、`state=RELATIONS_FOUND`、证据身份正确；零网络 |
| `LOCAL_RELATION_CAPTURE_READY` | **PASS** | 本地链路拆分 source/config entries 并接入共享管线；`test_pipeline_sample_c.py` 查询契约通过 |
| `RELATION_EVIDENCE_INTEGRITY` | **PASS** | 导入方/配置/目标三类身份分离；import Fact ID 为真实 stored ID；在线夹具 blob 身份不混用 |
| `RELATION_COVERAGE_HONESTY` | **PASS** | `status`/`status_counts` 区分未解析原因；未解析写 B 层审计账本；`NO_RELATIONS` 不再等同「无依赖」 |
| `CROSS_SOURCE_RELATION_QUERY_READY` | **PASS** | `test_d3_supplement_relation.py` 3/3；复用 `resolve_supplement()`，`include_supplements` 保留来源身份，不冒充主来源 |
| `EXISTING_KNOWLEDGE_PRESERVED` | **PASS** | 三库 A 层指纹一致；样本 A 607 Facts 保留、196 relation 新增；两轮 backfill 指纹不变 |
| `P2A_REGRESSION_PASSED` | **PASS** | module_resolution 165 OK、23+29 文件全绿、CLI e2e `FAILS=[]`（仅作背景，未替代上述功能判级） |

整体：**8 项 PASS，无 FAIL/PARTIAL**。全量回归与 CI 均未用于替代任何功能判级。

## 12. 尚未解决的能力限制（不得升格为已解决）

- 静态模块映射 ≠ 运行时模块加载成功。
- 在线默认采集不捕获 `.json`/tsconfig，相关关系诚实降级为 `CONFIG_NOT_CAPTURED`，不擅自补采。
- D3 补充来源关系仅作为 `supplement_relations` 附上，保留来源身份；不将本地解析冒充 GitHub API 解析产物。
- P2-A 未覆盖：跨文件函数调用图、类继承与类型层级图、项目级多跳推理、图谱可视化、AST 与 repo_miner 符号口径全面统一、LLM 自动推理（均属 P2-B/P2-C 或明确禁止范围）。
- 开发分支尚无专属 CI；推送 main 后需复验。
- 历史约 340 处私有路径仍在仓库历史中；授权未覆盖历史重写，未做。

## 13. 本次存档的写入范围

- 新增本文件 `progress/P2-A-STATIC-RELATION-ACCEPTANCE.md`（脱敏公开版）。
- 同步中英文技术文档（README / README.zh-CN / ARCHITECTURE / PIPELINE / USER-GUIDE / CHANGELOG 等 docs/en 与 docs/zh-CN）。
- 源码、测试变更在开发分支工作树，待提交推送；未写真实知识库、未修改已有 Tag、未发布新版本。
