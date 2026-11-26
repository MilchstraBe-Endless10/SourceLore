# P2-D1 真实知识资产完整性与复用链路审计（脱敏）

> 基准 main `2c05f78`，marker `2c05f78`，`version=0.1.0-beta.3`（NOT a released version）。
> 本轮只读审计：不联网、不补采、不改生产源码/安装态/真实知识库/历史资产/授权门禁；不进入 P3、不发 beta.4。
> 脱敏：不含作者本机绝对路径、真实知识库内容原文、第三方未授权知识原文；完整原始证据仅留本地，不随公开仓库分发。
> 核心问题：**为什么第一次采集能回答的技术知识，第二次会话不能准确复用？**

## 0. 结论总表（最重要的回答）

首次回答中的技术知识**大部分有永久知识资产支持**——18 个文件的正文原始字节完整保存在 CAS、SHA-256/Git OID/长度全部匹配，且可用正式 API 读回全文。第二次会话不能复用，根因**不是**"正文不存在/未采集/未持久化"，而是：

1. **DERIVATION_DEFECT（主因）**：派生器只读 README 章节化，其余 17 篇 docs 正文读进内存后从未转成可检索文档；`answer` 只固定引用 5 个合成文档。
2. **RETRIEVAL_DEFECT（主因）**：FTS 索引只写 `payload_json`（元数据），正文在 CAS 里不进全文索引；技术词检索召回为 0。
3. **PROVENANCE_DEFECT**：真实采集字节被硬编码标成 `SYNTHETIC_FIXTURE`，削弱证据等级与信任判断。
4. **REPORTING_ERROR**：首次报告的"4 supported + 1 insufficient"与新会话"4 supported + 1 refuted"是口径误读；这些 claim 全是路径存在命题，不是技术结论，不能当作"技术知识已验证"。
5. **UNSUPPORTED_LANGUAGE（次要/非全部）**：Rust 无 AST，源码符号/调用关系无法解析，只能解释"源码级技术结论"缺失，**不能解释文档正文的复用失败**。

其余分类见 §8 根因矩阵。

## 1. 恢复工程基线（§三）

- Git：main HEAD `2c05f78`；安装态/工程 marker 同为 `2c05f78`；版本 `0.1.0-beta.3`，非发行版。
- 用户自有改动（一处在用插件客户端、一份进度记录）原样保留，未 stash 覆盖、未提交。
- 三处 SKILL.md md5：工程源=安装态 `241c42e6`；hermes 态 `3e8c0671`（不一致，见 HOST_INTEGRATION_DEFECT）。
- A 层当前六库资产计数 `1219`（新增 obscura 后；不再沿用新增前的 `1089`）。指纹算法 `view_integrity.fingerprint_assets`，当前摘要 `9ae7997f21e86ddf47d1e82c770881162ce0066323f7857f095485a25fe0033e`（本轮只读计算，未与历史 `ddb2072e65fad724` 直接比对——口径为资产字典 SHA-256，历史值来自不同算法口径，见 §9）。
- Obscura 基线：RID `1209343409`，Commit `efe1c95962b33935fe9c53851566211074efe147`，Snapshot `SL-A-c44d1af81660b673922345a0ad6e0846`，整树 COMPLETE（639 条目/552 blob）。

## 2. G1：18 个内容资产逐项字节审计

审计方法：真实库 `mode=ro` 只读；CAS 目录 `<数据根>/blobs/*.bin`；文件名为裸 sha256（`src/storage/blob_content_store.py`），查询前先 `content_sha256.split("sha256:",1)[-1]` 去前缀；每项重算 SHA-256、Git blob OID（`sha1("blob <len>\0"+data)`）、字节长度；用正式 API `versioned_assets.captured_blobs(store,rid,commit,data_root)` 读回正文。

| 指标 | 结果 |
| --- | --- |
| 资产数 | 18 |
| `raw_bytes_present` | **18/18 true** |
| `raw_bytes_readable`（正式 API 读回） | **18/18 true** |
| `sha256_match` | **18/18 true** |
| `git_oid_match` | **18/18 true** |
| `byte_length_match` | **18/18 true** |
| `metadata_present` | 18/18 true |
| `capture_status` | CAPTURED |
| `provenance_level` | 全部 `SYNTHETIC_FIXTURE`（实为错误标记，见 §4） |
| `authorization_decision / basis` | payload 内为 null（授权依据记在采集 operation 记录层，不在该 payload） |
| `missing_reason` | 全部 null |

重点：`docs/Architecture-overview.md`（资产 `SL-A-f7f1bcb310896abcfe1cbb513f325bb4`）——declared `21131` B，actual `21131` B，SHA-256 `b0ffbc82…d1904`，Git OID `1a82ffa2…fbda`，四项全匹配；正式 API 读回 21065 字符，正文开头为项目"ten crates workspace"的概述，含十个 crate 职责、CDP 请求流程、渲染机制等完整段落。**结论：重点文档正文字节完整存在且可正式读回。**

判定：`captured_blob_content` 是正文存储对象（原始字节在独立 CAS 内容寻址层），不是纯元数据记录；首次采集完成了实际正文持久化；正文既不在临时内存也不只在 scratch；不是授权策略只允许派生事实不允许保存原文。

> 更正：此前会话曾根据 `payload_json` 无 `text/content` 字段、FTS 搜不到正文，得出"正文不存在/只有元数据"的结论——这是错误的（REPORTING_ERROR），本轮以 CAS 字节与正式读回 API 为准推翻。

18 项完整机器可读审计表：`progress/p2d1-g1-bytes-audit.json`（脱敏文件名，完整本地原始表另留 scratch）。

## 3. G2：授权边界核验

真实源码 `src/collector/content_acquisition_policy.py`：`POLICY_VERSION=content-authz/2`，五动作 `fetch / persist_bytes / derive_facts / internal_preview / external_distribution`；依据类型 `PROJECT_OWNED_WORK / ORIGINAL_TEST_FIXTURE / LICENSE_OBSERVED_AND_APPLICABLE / USER_EXPLICIT_GRANT`（`VERIFIED/UNVERIFIED`）。

`_EVIDENCE_CAPS`（161-168 行）：四类依据都允许 FETCH/PERSIST/DERIVE/PREVIEW，**没有任何依据允许 DISTRIBUTE**。

`--license-known` 的真实语义（preflight 88-100 行）：第三方仓库须有明确许可依据才允许写入原始字节；`LICENSE_OBSERVED_INTERNAL_ONLY` 仅放行内部采集，`copy_permitted=false` 时禁止复制到对外材料，`distribution_allowed=false` 保持不变。**"声明许可证已知"≠"全部操作已获准"**：它只解锁内部 FETCH/PERSIST/DERIVE/PREVIEW，分发恒拒绝。

- Obscura（Apache-2.0，`LICENSE_OBSERVED_AND_APPLICABLE`）：18 资产具备持久化原文、持久化派生知识、本地读取授权；不具备对外分发授权。
- 本轮未修改 `copy_permitted`，未放宽任何门禁，未把历史资产转成允许复制。

## 4. G3：SYNTHETIC_FIXTURE 来源追踪

沿真实调用链：Collector → Blob Capture → Content Ingest → Fact Extraction → Fact Persistence → Claim → Verification → Query。

- 赋值点：`src/skill_interface/content_capture.py` 第 213-244 行，生产采集函数 `capture` 在真实采集（`BF.fetch_blob` 已校验 Git OID/SHA，见 §2）后，**硬编码** `provenance_level="SYNTHETIC_FIXTURE"`，写 blob 内容与 report 都是这个默认值。
- 性质：**真实来源被错误覆盖成 fixture 默认值**（PROVENANCE_DEFECT），不是合成测试夹具冒充真实数据；字节真实性由 CAS 的 SHA/OID 独立证明。
- `captured_blob_content` 与 `extracted_fact` 的 provenance 是否一致：obscura 的 18 条 captured 全是 SYNTHETIC_FIXTURE；100 条 extracted_fact 的 payload 里 provenance 为 null（由资产类型/证据层承载，未逐条标注），来源标记链不完整。
- 真实性绑定：真实 GitHub 树、Blob OID、内容 SHA、授权记录已在 CAS 与 operation 层绑定；但 provenance 字段没反映出来。
- 影响：来源标记影响证据等级与审核呈现（`review_status=pending_review`）；不改变本轮 CAS 字节真实性，也不改分发门禁（仍 DENY）。
- 其他五库同源检查（captured+fact 的 provenance 分布）：
  - `1459544036`：1 条 null。
  - `24313173`：3 条 SYNTHETIC_FIXTURE + 55 条 null（同源标记）。
  - `38923193`：4 条 AUTHORIZED_REMOTE_SOURCE + 24 条 null。
  - `42283287`：9 条 OBSERVED + 278 条 null。
  - `local:4034d62ed2cf`：15 条 AUTHORIZED_LOCAL_FIXTURE + 607 条 null。
  - 结论：provenance 标注口径全库不统一（null 占多数），obscura 的 fixture 误标不是孤例，但各库成因需分别裁决。
- 修复原则：**不直接 UPDATE 历史 A 层资产**；后续走新增版本 + 隔离视图 + 重新裁决（见 §10 P2-D2）。

## 5. G4：文档正文检索链路审计（主根因）

链路：原始内容资产 → 正文读回 → 内容提取 → 文档派生 → 检索索引 → 正式 CLI → Bot 回答。逐段实测：

1. **正文读回正常**：`versioned_assets.captured_blobs` 18/18 读回全文（§2）。链路在"资产→读回"段无缺陷。
2. **文档派生断层（DERIVATION_DEFECT）**：`src/views/repo_miner.py` 的 `mine_project_knowledge`（638 行起）虽把 18 个正文读入 `texts`，但只产出 5 个固定文档：`project-overview / readme / structure / deps / claims`。只有 README 经 `parse_markdown` 切成章节；其余 17 篇 docs 正文被读取却**从未组织成任何可检索文档**。
3. **answer 固定引用（RETRIEVAL_DEFECT）**：`src/skill_interface/knowledge_answer.py` 的 `_INTENT_PLAN` 只引用上述 5 个合成 document，不含单篇 docs。`build_overview` 的 `core_impl` 只从 `code_rows` 的 function/class 符号逐字摘录（Rust 无 AST → 无摘录），`purpose/stack` 依赖 README 段落。
4. **FTS 只索引元数据（RETRIEVAL_DEFECT）**：`src/storage/index_store.py`（125 行起）写 `asset_fts` 的 `payload_text` 来自 `payload_json`；`captured_blob_content` 的 payload 只有路径/SHA/长度等元数据，正文在 CAS 里不进索引。实测 FTS 探针：`workspace of ten crates / stealth / MCP / rendering / ssrf / CDP` 命中全为 0。
5. **extracted_fact 不含正文段落**：只记结构化观察（标题/链接/文件元数据），`evidence_refs` 指向 `content:SL-CBLOB-…@byte:偏移`——正文靠 CAS + 偏移定位，FTS 无法召回正文段落。
6. **正式 CLI 实测复现**：对同一 Commit 用安装态 `answer` 问"架构和主要模块/核心 crate 职责/CDP 请求数据流/渲染机制"，四个问题返回的都是固定 section（"项目用途"4634 字符为 README HTML、"技术栈与清单"48 字符、"主要导出与符号"49 字符），17 篇 docs 正文一次都没出现，`evidence_refs` 为 0 或 1。

区分：这是**代码缺陷**（派生与检索链路没接正文），不是数据缺失（正文在），不是授权限制（本地读取允许），不是宿主调用错误（正式 CLI 入口本身就没有可召回的正文文档）。

## 6. G5：历史知识资产与命题裁决一致性（REPORTING_ERROR）

- 5 条 claim 全部 `review_status=pending_review`、`human_authored=false`、`origin=skill_analyze / skill_analyze_content`（**非人工复核**）；类型均为路径存在命题（`repository_path_exists` / `readme_heading_exists`），commit_sha 均指向目标 Commit。
- 5 条 verification 全部在 `current_view`：**4 supported + 1 refuted**（不是 insufficient）。
- refuted 那条：`SL-CLAIM-0835a273…`，类型 `repository_path_exists`，`normalized_path="README"`（无扩展名），而树中实际是 `README.md` → refuted 正确。
- 口径差异：首次报告"4 supported + 1 insufficient"与新会话"4 supported + 1 refuted"，差异来自报告误读/口径不一致，不是数据被改动。
- 关键判读：`pending_review` ≠ 已人工复核；`FULLY_LOCATABLE` ≠ 事实已被证明；这 5 条 claim 全是路径命题，**没有一条是技术结论**，因此不能用来证明"技术知识已被验证"。按纪律 15/18/23 处理。
- 十 crate vs 十一 crate：G1 已从 `docs/Architecture-overview.md` 正文读回"ten crates workspace"表述；`crates/` 下另有 `test-support` 辅助测试 crate。须区分 **workspace 成员数 / crate 目录数 / 辅助测试 crate 数**——目录数不等于 workspace 成员数；本轮以正文表述为准，目录名只作辅助证据，不据目录数宣称成员数。

## 7. G6：首次分析结果是否真正知识资产化

临时证据文件全部仍在（只读审计，未联网重建）：`ob_batch1.json`(11282B)、`ob_batch2.json`(4200B)、`ob_batch3.json`(10101B)、`ob_derive.json`(2611B)、`ob_answers.json`(22151B)、`obscura_content.json`(13461B)。首次回答四问的项目/架构/安装/核心 crate 均在这些 CLI 结果中可追溯。

| 技术内容 | 来源判定 |
| --- | --- |
| crate 职责 | 首次回答来自 `ob_answers.json` 当时的 README 级 block + 首次会话读取的 `Architecture-overview.md` 正文；**正文已成永久资产**（G1），但 `answer` 当前召回不到（§5）→ "已有永久资产支持，正式查询未召回" |
| CDP 请求数据流 | 同上，正文（docs/Architecture-overview.md、Use the CDP server 等）已成永久资产；当前 answer 未召回 |
| 渲染机制 | 同上，永久资产在 CAS，answer 未召回 |
| 网络/SSRF/MCP 设计 | `docs/Configure-stealth-and-proxies.md`、`docs/Use-the-MCP-server.md` 等正文已成永久资产（18 资产内）；answer 未召回；Rust 源码级细节无 AST → 仅文档级有据 |
| 可复用技术方案 | 文档级有永久资产支持；源码级为模型推断/未分析，不得当作已验证 |

`ob_derive.json`：644 节点 / 639 边 / 5 documents / 0 code_rows，`symbol_meta=SOURCE_NOT_ANALYZED`、`relation_meta=NO_RELATIONS`——图谱只有树与文档结构，无 Rust 源码语义。

## 8. 根因矩阵

每项含真实源码位置、数据证据、复现步骤、影响范围、最小修复方案（修复属 P2-D2，本轮不实施）。

| 分类 | 源码位置 | 数据证据 | 复现 | 影响 | 最小修复（P2-D2） |
| --- | --- | --- | --- | --- | --- |
| STORAGE_DEFECT | — | 无：18/18 字节完整、SHA/OID/长度全匹配 | — | 无 | 不需要 |
| CONTENT_NOT_CAPTURED | — | 无：CAPTURED，正文可读回 | — | 无 | 不需要 |
| KNOWLEDGE_NOT_PERSISTED | — | 无：正文持久化于 CAS | — | 无 | 不需要 |
| **DERIVATION_DEFECT（主因）** | `src/views/repo_miner.py` `mine_project_knowledge` 638+ 与 `build_overview` | 18 正文读入 texts 但仅 5 固定文档；仅 README 章节化 | `answer` 问架构/crate/CDP/渲染，只见固定 section | 所有非 README docs 的技术知识不可经 answer 复用 | 在派生阶段将已采 docs 正文纳入文档section（按路径/标题），保留 byte 偏移证据引用 |
| **RETRIEVAL_DEFECT（主因）** | `src/storage/index_store.py` 125+；`knowledge_answer._INTENT_PLAN` | FTS 只写 payload_json；技术词命中 0；answer 仅 5 合成文档 | FTS MATCH 技术词=0；answer 四问均固定 block | 正文存在但检索召回不到 | FTS 增补正文段落文本索引（从 CAS 读回按段落），或 answer 增加"按问题检索已采文档正文"的文档级意图 |
| **PROVENANCE_DEFECT** | `src/skill_interface/content_capture.py` 213-244 | 真实采集硬编码 SYNTHETIC_FIXTURE | 查 payload.provenance_level 全为 fixture | 证据等级/信任呈现失真；不改字节真实性 | 新增版本写真实 provenance（如 LICENSE_OBSERVED_AND_APPLICABLE），A 层不可变、隔离视图重新裁决 |
| **REPORTING_ERROR** | 首次报告口径 | 4+1 insufficient vs 4+1 refuted；claim 全为路径命题 | 对照 §6 | 把路径命题误当技术知识验证 | 报告区分路径命题与技术结论，统一按 current_view 口径 |
| UNSUPPORTED_LANGUAGE（次要） | AST 仅 Python/JS/TS | code_rows=0，symbol_meta=SOURCE_NOT_ANALYZED | 问 Rust 函数/调用关系 | 源码级技术结论缺失 | 非本轮；后续 Rust AST 支持（P3 之后），不解释为文档复用失败 |
| AUTHORIZATION_RESTRICTION | `content_acquisition_policy.py` 88-100 | DISTRIBUTE 恒拒绝 | 对外分发被门禁拦截 | 仅限制对外分发，不影响本地复用 | 不需要（本地读取已授权） |
| HOST_INTEGRATION_DEFECT | 三处 SKILL.md md5 `241c42e6` vs `3e8c0671` | hermes 态与工程/安装态不一致 | md5sum 三处 | 部分会话加载的 Skill 规则可能不同步 | 同步三处副本并 md5 核对（纪律 21） |
| UNVERIFIED（TD-004） | 宿主工具轨迹不可得 | 无法取得真实 OpenBot 独立会话自动加载轨迹 | — | 宿主自动触发验收无法判定 | 保持 PARTIAL / NOT_VERIFIED，由用户在真实独立会话验收 |

## 9. TD-004 宿主自动触发验收边界

本轮新会话确为"使用 sourcelore Skill"的自然语言会话，但无法取得真实宿主工具轨迹来区分：Bot 自动发现加载 vs 手动找 Skill vs 直接 SQLite 绕过 vs 正式入口完成检索。按约束不以内部 CLI/模拟会话代替宿主验收 → **TD-004 保持 NOT_VERIFIED/PARTIAL**，待用户在真实 OpenBot 独立新会话验收。

## 10. P2-D2 最小修复方案（仅设计，不实施）

1. 派生层：`mine_project_knowledge` 增加已采 docs 的正文文档（按文件/标题切 section，附 byte 偏移 evidence_ref），不触碰 A 层。
2. 检索层：FTS 增补正文段落索引；或 `knowledge_answer` 新增"文档正文检索"意图，从 CAS 读回匹配段落。
3. 来源层：新版本资产写真实 provenance，隔离视图重新裁决；历史 SYNTHETIC_FIXTURE 不批量升级、不直接 UPDATE。
4. 报告层：统一 current_view 口径，区分路径命题与技术结论。
5. 宿主层：同步三处 SKILL.md（md5 一致）。
所有修复走新增版本 + 隔离视图，保持 A 层不可变。

## 11. P2-D3 文档语义知识资产化差距

当前已采 docs 正文以"字节 + 结构化观察（标题/链接/元数据）"形式存在，但缺少：**段落级语义事实**（crate 职责、CDP 流程、渲染机制的可回查命题）、**文档派生视图**（把 17 篇 docs 组织成可检索知识）、**正文段落 FTS 索引**、**技术命题的 verification**（现有 5 条 claim 全是路径命题）。这导致正文"存而不可检"，是 D2 修复的重点。

## 12. 后续真实验收门禁

- G1 门禁：18/18 正文读回 + SHA/OID/长度匹配（本轮已过）。
- D2 门禁：对 4 个技术问题 `answer` 能召回至少一篇 docs 正文 section，且 evidence_refs 指向真实 byte 偏移；FTS 技术词命中 > 0。
- 来源门禁：新版本 provenance≠SYNTHETIC_FIXTURE 且隔离视图重新裁决；A 层指纹不变。
- 报告门禁：4+1 口径统一；路径命题与技术结论分开表述。
- 宿主门禁：真实独立会话工具轨迹证明走正式入口（TD-004），否则保持 NOT_VERIFIED。

## 13. 本轮执行记录

- 工具：sourcelore Skill（已重载）；真实库 SQLite `mode=ro`；正式 CLI `answer`；CAS 字节审计脚本（scratch）；正式 API `versioned_assets.captured_blobs`。
- Repository ID `1209343409`，Commit `efe1c95962b33935fe9c53851566211074efe147`。
- 网络请求：0。真实知识库写入：无。生产源码/安装态/历史资产/授权门禁：未改。第三方代码：未运行。
- 本轮写入仅限：scratch 审计脚本与发现笔记（`p2d1_*.py`、`P2D1_FINDINGS.md`、`p2d1_g1_bytes_audit.json`）及本审计文档与脱敏机器可读结果。
