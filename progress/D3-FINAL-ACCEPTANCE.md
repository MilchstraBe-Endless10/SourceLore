# D3 跨来源知识关联与统一检索闭环 — 专项最终验收存档

> 版本状态：本存档验收的对象是一个**未发布开发 Commit**，不是正式 Release。
> 正式发行版本仍为 `0.1.0-beta.3`；未发布 beta.4；beta.1/beta.2/beta.3 的 Tag 均未改动。
> 每个结论都附专项证据；CI 通过和全量回归数字只作背景，**不作为功能验收依据**。
> 本存档为脱敏公开版：不含作者本机绝对路径、不含真实知识库内容原文、不含第三方未授权知识原文。
> 完整原始证据（含本机路径与真实库转储）仅留本地，不随公开仓库分发。

## 1. 范围与身份

- 目标仓库：`Tobi1chi/arch-grower`（MIT，Python 3.10+，零第三方依赖）。
- GitHub 身份 ID：`1459544036`。
- 本地补充来源 ID：`local:4034d62ed2cf`。
- 固定 Commit：`8f5daf1ad21ce3ac5adbe9cc1c4229d55c13b024`。
- Root Tree：`c668da9687b98d340616ce1e4c2ede911d090ec3`。
- A 层 GitHub 快照资产：`SL-A-87e5d19378a777ef04d2b637d12be667`（根层 9 条目，ROOT_ONLY）。
- A 层本地镜像资产：`SL-A-28728bcbf070764a5ec8aeaf3b86761f`。

## 2. 涉及 Commit

| Commit（完整） | 用途 |
| --- | --- |
| `e9d8425a1a17d09daf39bfc80275e25e42d8b4ec` | beta.3 正式发行 Commit（基线） |
| `c461a4e73231ef8512ac6be879dc4006b563a220` | D3 主体开发 Commit（来源验证 + 绑定 + 三入口接入） |
| `83b8704b8bb8f001a92a5c49a216b45ba793e04d` | 补回 Skill 规则 28/29，三处 Skill.md 字节一致 |
| `a001d7a2bf73af661db11603e07f4853be775fef` | 安装一致性测试跳过 `__pycache__/*.pyc` |
| `7b756807ffc0ac2288ca0b04e7b8a641b7734967` | beta.1 发行 Commit / Tag |
| `00247148575a2c67466ab47a9e7274334e78ac85` | beta.2 发行 Commit / Tag |

D3 开发分支：`dev/d3-source-binding`（基于 `e9d8425…`）；最终 main HEAD 为 `a001d7a…`，与 origin/main 一致。

## 3. 真实库 repo_bindings 关联记录

关联写入方式：经正式 `KnowledgeStore.bind_repo` 接口，`tools/bind_sources.py --apply` 执行；`/tmp/d3_bind_apply.json` 记录 `ok=true`、`dry_run=false`、`a_layer_unchanged=true`。真实库当前 `repo_bindings` 共 **2 行**，共用同一内容锚点 `CONTENT-ANCHOR-a567b0761b3c824f414e5ebf`：

| binding_id | subject_id | repository_id | evidence_ref（摘要） |
| --- | --- | --- | --- |
| `SL-B-3acbd317075d31eddc392cc0a4643945` | `CONTENT-ANCHOR-a567b0761b3c824f414e5ebf` | `1459544036` | `source_verified=1;method=github_identity_record+blob_subset;commit=8f5daf1…;root_tree=c668da96…;github_asset=SL-A-87e5…;local_asset=SL-A-2872…;resolved_repository=Tobi1chi/arch-grower;github_id=1459544036` |
| `SL-B-ef4f679f635cebf3ef9ddf0cf5246967` | `CONTENT-ANCHOR-a567b0761b3c824f414e5ebf` | `local:4034d62ed2cf` | 同上 |

两条均 `created_at=2026-11-25T20:46:46+0800`。写入只落 B 层，未合并 `repository_id`，未改 A 层。

## 4. 来源验证与授权依据

`/tmp/d3_bind_apply.json` 的 `verification` 记录：

- `ok=true`，`reasons=[]`，`github_id=1459544036`，`resolved_repository=Tobi1chi/arch-grower`，`local_id=local:4034d62ed2cf`。
- `commit_sha=8f5daf1…`，`root_tree_sha=c668da96…`。
- `blob_paths_compared=5`，`blob_subset_verified=true`：GitHub 根层 5 个 blob_ref 哈希是本地 27 项 blob map 的哈希一致子集。
- 判定方法：`github_identity_record + blob_subset`。权威依据是 A 层 `subject_record`：数字 ID 的权威记录中 `logical_identity=SL-REPONAME-1459544036`、payload `record_kind=repository_display_name`、`resolved_repository=Tobi1chi/arch-grower`。
- 关键约束落实：**Commit + Root Tree 相同不算身份证明**；叠加权威 ID 记录与 blob 映射一致性共同判定，防止 Fork / 伪造远端导致跨仓库知识污染。
- 反例已在隔离环境验证被拒：伪造数字 ID、本地 ID 伪装、无权威记录、blob 哈希冲突。
- 授权依据来自用户对 D3 的正式授权第 5 条（经正式存储接口写 `repo_bindings`）与"不得仅凭 Commit/Root Tree 证明同一身份"的明确约束。

**边界声明**：来源内容对应关系验证通过，**不等于**本地来源真实性、Fork 区分、第三方授权边界已全面解决。验证依赖现有 A 层权威记录与 blob 子集，未做独立的链上/远端身份二次认证，也未对第三方内容授权做新的法律判定。

## 5. A 层资产指纹（写入前后）

- 写入前记录值（`/tmp/d3_bind_apply.json.a_layer_fingerprint`）：`0f42f77f19bb424545ec5ede6fadebfebaaef2ed90189c83542e8665fb5006b9`
- 写入后只读重算当前值：`0f42f77f19bb424545ec5ede6fadebfebaaef2ed90189c83542e8665fb5006b9`
- 两者逐字节一致，`a_layer_unchanged=true`。未删除、未改写 A 层历史资产。

## 6. answer（仅 GitHub ID `1459544036`）

证据：`/tmp/d3_real_answer.json`（dev launcher 真实库 e2e）与 `/tmp/inst_answer.json`（安装态 CLI 复核）。

- `ok=true`，`repository_id=1459544036`，`commit_sha=8f5daf1…`。
- `blocks=40`，其中 `37` 个带补充源标记（`source_repository_id` / `supplement_of`）。
- `supplement_sources`：`repository_id=local:4034d62ed2cf`、`role=verified_local_supplement`、`commit_sha=8f5daf1…`，`evidence_ref` 完整保留（含 `source_verified=1`、`resolved_repository=Tobi1chi/arch-grower`、`github_id=1459544036` 及双方资产 ID）。
- `network_requests=0`、`wrote_assets=0`：零网络、零写入。
- 原始证据身份保留：补充知识带 `local:4034d62ed2cf` 来源身份，未冒名为 GitHub 在线采集。

## 7. query 三种检索的实际支持范围（仅 GitHub ID）

| 类型 | 结果 | 专项证据 / 说明 |
| --- | --- | --- |
| `code` | **PASS** | `/tmp/d3_real_query.json`：`counts={symbols:47, imports:153, facts:200, exports:0}`；`source_repository_id=local:4034d62ed2cf`、`supplement_of=1459544036`、`provenance_level=AUTHORIZED_LOCAL_FIXTURE`、`source_role=verified_local_supplement`、`network_requests=0` |
| `content` | **PASS** | `/tmp/d3_q_content2.json`（带 `--commit`）：`state=SUPPORTED`、`content_availability=CAPTURED_VERIFIED`、`coverage_status=COVERED_BY_EXTRACTED_CONTENT`；补充源身份与 `network_requests=0` 同上 |
| `relation` | **PARTIAL** | `/tmp/d3_q_relation.json`：命令成功、`ok=true`，但 `state=NO_RELATIONS`。GitHub 根层快照未捕获静态模块关系，本地补充源也无生成的 relation 记录。这是覆盖缺口，**不是**"验证为无关系" |

`content` 查询必须带 `--commit`，否则命令返回参数错误（已验证）。

## 8. inspect ROOT_ONLY 状态

证据：`/tmp/d3_real_inspect.json`。

- `tree_coverage[0]`：`coverage_scope=ROOT_ONLY`、`completeness_status=ROOT_ONLY`、`complete=false`、`coverage_reason=ROOT_ONLY_SUBTREES_UNENUMERATED`、`local_coverage_only=true`、`tree_entry_count=9`。
- 历史 payload 的 `COMPLETE` 仅作为 `recorded_completeness_status=COMPLETE` 保留供审计，不再误显示为当前完整状态。
- 结论：已正确展示旧快照的有效 ROOT_ONLY 状态，beta.3 时期"ROOT_ONLY 误显示 COMPLETE"问题已修正。

## 9. 已有知识资产保留情况

- **607 Facts**：真实库 `local:4034d62ed2cf` 下 607 条 `extracted_fact`，A 层指纹不变，未重复采集、未删改。
- **AST 产物**：47 符号 / 153 导入 / 200 facts，`CAPTURED_VERIFIED`，由 code query 专项读回佐证。
- **7 份派生文档**：其保留属于**间接证据**（由 answer/query 能从原始证据身份读回正文佐证），**未逐文件核验完成**。不得写成逐文件 PASS。

## 10. 安装态实际执行代码对应的开发 Commit

- marker（`.sourcelore-install.json`）声明：`dev_commit=c461a4e73231ef8512ac6be879dc4006b563a220`、`dev_branch=dev/d3-source-binding`，并明确标注 `NOT a released version`。
- 不止看声明：安装态四个核心文件的 SHA-256 与 `c461a4e…` 的 git blob 逐字节比对，全部一致：

| 文件 | SHA-256 |
| --- | --- |
| `src/skill_interface/cli.py` | `37ca158d258a07d3b21bf7a0a66b314f4b4806b19e14d5d1a41ff2cb430bbad5` |
| `src/skill_interface/knowledge_answer.py` | `f207ea1f1198af2b85034db62a604d7f2c7c2c765a6746507490429a142638ea` |
| `src/skill_interface/knowledge.py` | `a2b31edb266890146628c4beed30f00628bcf980b29f58668f06bfbc90f0728b` |
| `src/trust/source_provenance.py` | `e732ceb7253288c17115d72a092073000be0290e899608ae6585264c079dfcde` |

- 版本字段仍是 `0.1.0-beta.3`；D3 开发 Commit 只在 marker 与本文档记录，**不冒充正式 beta.3 Release**。

## 11. 六项 D3 专项门禁判级

| 门禁 | 判级 | 依据（专项证据） |
| --- | --- | --- |
| 1 来源真实性（非仅 Commit+RootTree，防 Fork/伪造） | **PASS**（限第 4 节边界） | 权威 `subject_record` + blob 子集；反例全拒 |
| 2 授权与合法 `repo_bindings` 写入 | **PASS** | 2 行锚点记录，`a_layer_unchanged=true` |
| 3 `answer` 正式入口接入补充源 | **PASS** | 40 blocks / 37 补充，身份保留，零网络 |
| 4 `query` 正式入口三种检索 | **PASS（content/code）+ PARTIAL（relation）** | code 47/200、content SUPPORTED、relation NO_RELATIONS |
| 5 `inspect` ROOT_ONLY 显示修正 | **PASS** | `coverage_scope=ROOT_ONLY`、`complete=false` |
| 6 独立测试夹具、无作者本机路径硬编码 | **PASS** | `tests/trust/test_source_provenance_d3.py` 用 tempfile，6/6 |

整体：**5 项 PASS；第 4 项中 relation 子项为 PARTIAL；无 FAIL**。

## 12. 未完成事项 / 边界（不得升格为已解决）

- `relation` 检索为 PARTIAL：静态模块关系未生成可回查记录，属覆盖缺口。
- 本地来源真实性、Fork 区分、第三方授权边界**未全面解决**，仅完成来源内容对应关系验证。
- 7 份派生文档保留是间接证据，**非逐文件核验**。
- 宿主端到端自动触发未完成：已确认 Skill 安装/启用与手动读取，但宿主无调用轨迹导出工具。
- 历史约 340 处私有路径仍在仓库历史中；授权未覆盖历史重写，未做。
- CI 全绿与 103/103 全量回归**仅作背景**，未用于替代上述任何功能判级。

## 13. 本次存档的写入范围

- 新增本文件 `progress/D3-FINAL-ACCEPTANCE.md`（脱敏公开版）。
- 保留并扩充 `progress/TECH_DEBT.md`（技术债务登记）。
- 未修改源码、未发布版本、未改 Tag、未重新采集 arch-grower、未重复全量回归、未写真实知识库。
