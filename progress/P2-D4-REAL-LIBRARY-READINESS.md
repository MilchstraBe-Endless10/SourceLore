# P2-D4 真实知识库启用与可信性收尾 — 验收报告

状态：**完成（A/B 全部通过，C 给出真实缺口与方案）**
基准提交：`6a1feaf`（P2-D3）　正式版本：`0.1.0-beta.3`　本轮未改生产源码、未发新版本。

## 1. 工程与真实库基线

- Git：HEAD / origin/main 同为 `6a1feaf`；用户自有改动（`client.js`、BOT-CARD 文档）保留未动。
- 真实数据根：资产 `1219`、快照 `6`、`semantic_proposition=0`、`kb.db-wal=0`。
- 备份：一致快照 `VACUUM INTO` 到隔离目录（含 `kb.db.snapshot`、派生视图、49 个 CAS blob）；`integrity_check=ok`。
- A 层基线指纹：`a3429309…`（`asset_id:content_hash` 全量 SHA256，固定算法）。
- 正式 launcher 探测：Obscura `1209343409 / efe1c959`、Preact `42283287 / dbeba0d5`；无并发采集/派生任务。

## 2. D4-A：真实派生视图更新

用正式 `derive` 入口，先在隔离副本验证、再对真实库执行；只重建 Obscura 正文检索索引与 Preact 图谱。

- 隔离验证：A/B 指纹不变，仅两库 `section_fts` 写入；Preact 图谱 155 节点 / 178 边。
- 真实库执行后逐项比对：CAS `49 → 49`，文件名集合与内容 SHA256 全部一致，新增/删除/内容差异均为 0。
- B 层当前指针、其他四库、A 层权威资产、授权门禁均未变；网络请求 0。

### Obscura 正文检索（正式 launcher、真实数据根、无 `SOURCELORE_PROJECT_ROOT`）

八问全部命中正文，每题 5 条 `content-sections` 证据块；正文证据在 `blocks[]`（`document_id=content-sections`），不在 `content_retrieval.matches`。

| 问题 | 正文命中 | 网络 | 权威写入 |
| --- | --- | --- | --- |
| 架构是什么 | 5 | 0 | 0 |
| 用了哪些 crate / 各自职责 | 5 | 0 | 0 |
| 数据流 | 5 | 0 | 0 |
| 安装和配置 | 5 | 0 | 0 |
| 提供哪些 API 接口 | 5 | 0 | 0 |
| MCP server 如何使用 | 5 | 0 | 0 |
| 如何隐藏浏览器指纹 | 5 | 0 | 0 |
| Rust 源码实现了哪些功能 | 5 | 0 | 0 |

Rust 源码问题返回正文含「未分析 / 未采集」降级标记，未冒充源码已验证事实。
Architecture-overview、crate 职责、CDP 流程、渲染文档均可回查到原始正文（byte/SHA/OID/行号）。

### Preact 图谱

`派生视图/42283287/<commit>/code-graph.json`：155 节点 / 178 边。符号定位、`BaseComponent` 正向/反向依赖、多跳路径均返回可回查 Fact 证据；负例 `DefinitelyNotARealSymbolXYZ` → `NOT_FOUND_IN_GRAPH`。所有关系为**静态源码关系**，未描述为运行时调用。

## 3. D4-B：封顶机制与历史来源纠正

### 3.1 七条语义命题封顶原因

诚实边界：D3 七条命题落库在隔离副本 `d3_final3`，已按 D3 交付要求清理；真实库 `semantic_proposition=0`；`p2d3-acceptance-result.json` 只有汇总、无逐条 subject。因此七条命题的**逐字 subject/proposition 原文已不可从现存资产恢复，本报告不编造**。以下按知识类别与封顶逻辑重建，逐条归因均可回查到真实源码函数与证据属性。

封顶是确定性分类逻辑 `_cap_support_level(proposed, knowledge_kind, source_category, evidence_complete)`，**不是错误统一封顶**；正反例复现确认，无需最小修复：

| 命题类别 | 封顶后支持性 | 裁决 / 覆盖 | 封顶实际原因 |
| --- | --- | --- | --- |
| 整体架构 | PARTIALLY_SUPPORTED | insufficient_evidence / PARTIAL | 证据为 `documentation_self_report`，命中源码事实类封顶 |
| crate 职责 / 依赖 | PARTIALLY_SUPPORTED | insufficient_evidence / PARTIAL | Cargo 清单属 `config_declaration`，不在 `_SOURCE_RANK` → `unverified` 兜底；只能说“清单声明”，非运行时调用图 |
| 数据流 | PARTIALLY_SUPPORTED | insufficient_evidence / PARTIAL | 文档自述，未证实运行时行为 |
| 安装配置 | PARTIALLY_SUPPORTED | insufficient_evidence / PARTIAL | 来自使用文档自述；`config_declaration` 保守兜底 |
| API 接口 | PARTIALLY_SUPPORTED | insufficient_evidence / PARTIAL | 文档自述命中 `api_surface` 源码事实类封顶 |
| MCP server 使用 | PARTIALLY_SUPPORTED | insufficient_evidence / PARTIAL | 文档自述 / 配置声明，非源码验证 |
| 可复用技术（浏览器指纹等） | PARTIALLY_SUPPORTED | insufficient_evidence / PARTIAL | 文档自述超出源码可证范围 |

共同根因三类：① `documentation_self_report` 对源码事实类命题降为部分支持；② `config_declaration` 不在 `_SOURCE_RANK` 走 `unverified` 兜底；③ 历史 `SYNTHETIC_FIXTURE` 来源误标原样继承、不升级。
未发现不该封顶却被封顶的命题；未为提高 PASS 放宽判据；本轮不改封顶源码。

### 3.2 历史 SYNTHETIC_FIXTURE 误标

- 真实库统计：A 层 `captured_blob_content` 120 条含 `SYNTHETIC`（Obscura 117 + 仓库 `24313173`）；204 条正文证据带该标记。误标资产有 commit / Blob OID / content_sha256 / source_snapshot_id 真实采集绑定，但 `source_response_digest=null`。
- 真实库**无专用来源裁决表**，`ASSET_TYPES` 封闭码表也无裁决类型（新增裁决类型被引擎拒绝）。这是待补的最小实现缺口。
- 隔离副本 PoC（从一致快照重建，用现有合法类型 `evidence_record` 追加独立裁决，未写真库、未 UPDATE A 层）：
  1. 原始错误记录保留：`provenance_level` 仍为 `SYNTHETIC_FIXTURE`，payload 哈希与 content_hash 不变 ✓
  2. 追加独立来源裁决：绑定 `repository_id=24313173`、`commit_sha=98e8ff…`、`git_blob_oid=eb8149e8…`、`content_sha256`、`source_snapshot_id`、`source_api` ✓
  3. 不提高分发权限：裁决资产与命题 `distribution_allowed=false`、`copy_permitted=false`、`raises_distribution_permission=false` ✓
  4. 当前视图可解释误标：原始记录 + 裁决记录并存（2 条），历史不洗白 ✓
- **待纠正资产清单与授权方案**（不写真库）：117 条 Obscura + 3 条 `24313173` A 层资产，建议以追加式 `source_ruling` 资产类型（需先扩展 `ASSET_TYPES`）或复用 `evidence_record` 实现；每条绑定原仓库身份、Commit、Blob OID、内容哈希、source_snapshot_id；继承最保守分发标志；由用户授权后再落库。

## 4. D4-C：真实宿主接入

核查结论：**真实 OpenBot 模型可在不新增外部模型 API、不配置额外 API Key 的情况下完成候选命题生成并通过正式入口保存**，D3 已用注入式 client（`semantic-produce` + `--tasks-file`）验证。

- 入口：`semantic-produce <rid> --commit <sha> --tasks-file <json> [--dry-run]`；`semantic-query <rid> …`。
- client 注入：CLI 内按 `question` 匹配 tasks 的候选命题；宿主把研究结论写成只读 JSON，程序只做鉴证落库。
- 证据集合：`section_fts.query_sections` 按仓库+Commit 召回，每条带下标与 byte/SHA/OID/行号；宿主只能引用下标，越界/不完整证据丢弃，不能伪造。
- 宿主输出 → 确定性校验：`_cap_support_level` / `_resolve_levels` / 来源继承 / 授权 DENY / 幂等落库；未注入 client → `HOST_MODEL_NOT_CONFIGURED`。
- 持久化：需 `--tasks-file`（写临时 JSON）与正式落库授权；dry-run 实测 `PRODUCED`、`PARTIALLY_SUPPORTED`、网络 0。
- 正式 answer 召回：`semantic_knowledge` 字段按问题相关性排序置顶，零网络零写入，原文回查链保留。

**真实缺口（最小方案）**：CLI 无独立“证据包导出”命令，宿主不易直接拿到带下标的证据来填 `evidence_indices`。当前可经 `answer` 的 `content-sections` blocks 或语义召回间接取得，D3 已验证可行。最小补全：新增 `semantic-evidence <rid> --commit <sha> --question <q>` 子命令，复用 `_evidence_packet` 输出带下标证据 JSON（只读、零网络）；或在 `semantic-produce --dry-run` 结果中附 `evidence` 字段。

**SKILL.md 兼容性**：三处副本差异——工程源/安装态 md5 一致（`241c42e6`），无语义命令指引；用户 hermes 超集（`0df70cf5`）已含 `semantic-produce` / `semantic-query` 表格行与纪律 37、`references/semantic-knowledge.md` 完整指引。用户实际使用的 hermes 态具备能力，**无需改用户超集、未覆盖任何用户修改**。最小增量补丁（仅建议，未执行）：把语义命令两行表格 + 纪律 37 合入工程源/安装态 SKILL.md，保持 hermes 超集不变。

## 5. 保护证据与回归

- A 层：八问前后全量 `asset_id:content_hash` 指纹一致，资产数 `1219` 不变。
- CAS：`49 → 49`，文件名与内容 SHA256 逐项一致。
- 语义：真实库 `semantic_proposition` 全程 `0`，未手工导入隔离 9 条命题。
- 网络：查询阶段 `network_requests=0`；权威写入 `wrote_assets=0`。
- 回归：沿用 D3 基线（专项 13/13、全仓逐文件 126 PASS / 0 FAIL）；本轮未改生产源码，无新增失败。

## 6. Git 与安装态

- 本轮交付为文档 + 机器可读结果；无生产源码修复，因此不改 `version`、不建新 Tag/Release（三个 beta Tag 未动、无 beta.4）。
- 安装态 marker：`dev_commit=6a1feaf…`、`version=0.1.0-beta.3`、`release_note=NOT a released version`。
- 待交付阶段修正项：安装态 marker `dev_branch=dev/p2d2-content-retrieval` 与当前 `dev_commit` 不一致，应同步为当前分支描述。

## 7. 停止点

本轮完成后停止，等待用户进行真实 OpenBot 语义知识生产及新会话验收。未进入 P3、未发布 beta.4、未重新采集 Obscura、未批量修改历史知识、未向真实库追加来源纠正资产。
