# P2-D2 正文检索复用修复验收（脱敏）

> 基准 main `2c05f78`，开发分支 `dev/p2d2-content-retrieval`，`version=0.1.0-beta.3`（NOT a released version）。
> 目标：证明 P2-D1 已永久保存的真实技术文档，可通过修复后的正式产品入口，在不联网、不重采、不改历史知识的前提下被准确检索复用。
> 边界：全程离线（网络请求 0），真实六库只读，A 层不可变，授权门禁不放宽，未执行第三方代码，未发布 beta.4，不进入 P3/Rust 解析器。
> 脱敏：本文不含作者本机绝对路径、真实知识库正文原文、第三方未授权知识原文；原始证据仅留本地。

## 0. 结论

通过。首次采集的正文原始字节完整保存在 CAS；P2-D1 定位的四项可修复根因已逐项落地并经隔离根端到端验证。正式 `answer` 入口对 Obscura 固定 Commit 的八个技术问题全部召回真实正文片段，命中带字节偏移与证据引用，`source_category` 明确标记为 `documentation_self_report`（文档自述），不冒充源码已验证事实。查询阶段网络请求 0、权威资产写入 0、CAS 写入 0、A 层指纹不变。

## 1. 四项根因的实际修复位置

| 根因（P2-D1） | 修复位置 | 处理方式 |
|---|---|---|
| DERIVATION_DEFECT | `src/views/content_section_derivation.py`（新增）、`src/views/repo_miner.py` | `mine_project_knowledge` 从已采正文派生 `content-sections` 文档，携带精确行号/字节范围与授权边界 |
| RETRIEVAL_DEFECT | `src/views/section_index.py`（新增）、`src/views/repo_derive_runner.py`、`src/skill_interface/knowledge_answer.py` | derive 阶段重建 C 层 `section_fts`；answer 按问题确定性关键词召回正文片段 |
| PROVENANCE_DEFECT | `src/skill_interface/content_capture.py` | 真实采集默认 `AUTHORIZED_REMOTE_SOURCE`，仅显式声明才写 `SYNTHETIC_FIXTURE`；不改历史 A 层来源 |
| HOST_INTEGRATION_DEFECT | 不改 SKILL.md（见 §8） | 差异为历史遗留与用户累积；本轮未改 SKILL，按要求不覆盖用户自有修改，仅记录并待用户在真实宿主会话验收 |

## 2. 修改前后调用链

修改前：`derive_one → mine_project_knowledge → write_derived_views`（仅 5 个固定文档）→ `asset_fts` 只索引 payload 元数据 → `answer._INTENT_PLAN` 只引用 5 个固定文档 → 技术词召回 0。

修改后：`derive_one → mine_project_knowledge`（新增 `content-sections`）→ `write_derived_views` → `section_index.rebuild_section_index`（重建 C 层 `section_fts`，repo+commit 身份隔离）→ `answer` 调 `section_index.query_sections` 召回正文片段 → `blocks` 增加 `content-sections` 块（字节偏移、asset_id、file_path、授权字段、`source_category`）。`deep_answer` 通过 `dict(base)` 继承该链路。

## 3. 正文派生覆盖统计

隔离根 `derive` 重建：写入 208 条、去重后 204 条正文片段；Obscura 固定 Commit `section_fts` 共 204 条，索引身份数 1。A/B 指纹前后一致，权威资产未变。

## 4. FTS 召回前后对比

修改前 P2-D1 实测：`workspace of ten crates / stealth / MCP / rendering / ssrf / CDP` 对 `asset_fts` 命中全为 0；正式 `answer` 四问均返回固定 section，17 篇 docs 正文一次未出现。

修改后：同一批技术词经 `section_fts` 均可召回；中文技术问题经确定性中英技术概念映射（只翻译检索词，不产出事实）命中英文文档正文。八问全部命中真实正文片段。

## 5. Obscura 八问事实级验收

八问：架构、主要模块、核心 crate 职责、浏览器接管与请求修改、渲染机制、反检测/stealth、MCP 服务、安装使用。结果：8/8 命中，每问返回 `content-sections` 块，块内 `source_category=documentation_self_report`，`copy_permitted=false`、`distribution_allowed=false`，原始字节定位与 SHA 校验 8/8 通过，正文前缀与 CAS 片段一致 8/8。

Gate 4：Cargo.toml 依赖只作 dependency declaration，未升级为运行时调用图；Rust 源码函数/行号/调用关系未伪造，源码证据不足处如实标注。

## 6. 来源标记修复与负例

`content_capture.capture` 新增可选 `provenance_level`，默认 `resolve_provenance(None) → AUTHORIZED_REMOTE_SOURCE`；只有显式 `SYNTHETIC_FIXTURE` 才产生合成夹具标记。写库与报告均使用同一 `prov` 值，调用兼容保持。专项测试 `tests/skill_interface/test_d2_provenance.py` 4 项通过：默认真实来源、显式 fixture 负例、源码无硬编码误标、预算语义未破坏。

历史来源纠正方案：历史 A 层已写入的 `SYNTHETIC_FIXTURE` 不批量升级、不直接 UPDATE（A 层不可变）；如需纠正，走新版本资产 + 隔离视图重新裁决，由独立授权轮次执行。本轮不改历史来源。

## 7. 通用性与安全

Gate 6 身份隔离：跨仓库身份（不存在仓库）与错误 Commit 的正文召回均为 0 条，未串用 Obscura 正文；P2-C 的 Commit 指定、图谱状态与歧义契约保留。

Gate 8 通用性：独立构造的 Markdown 测试样例（另一身份）用中文问题「代理 拦截 渲染」命中英文正文，验证修复不依赖 Obscura。已有其他语言仓库的通用性由同一确定性子串匹配与中英映射机制覆盖（机制与仓库无关）。

Gate 9 授权：Obscura 全部命中块 `copy_permitted=false`、`distribution_allowed=false`，无一条升级为允许分发；分发门禁不变。

Gate 7 查询只读：正式 `answer` 返回 `network_requests=0`、`wrote_assets=0`；socket 级网络拦截未触发；A 层指纹与 CAS 文件（49 个）调用前后一致。

## 8. SKILL.md 差异与处理结论

三处 SKILL.md 不一致：工程源与安装态 md5 `241c42e6`（446 行），hermes 态 md5 `d345a51e`（461 行，多 `backfill-relations` 命令与纪律 30–36）。差异是先前会话累积更新，非本轮产生。按 D2-G「安装同步与用户自有修改冲突则停止覆盖并报告」：本轮不回退、不覆盖 hermes 态，保持用户自有修改原样；该差异作为 HOST_INTEGRATION_DEFECT 的已知边界保留，需用户决定是否统一三处。TD-004 宿主自动触发仍为 NOT_VERIFIED，待用户真实独立新会话验收。

## 9. 专项测试与全量回归

专项：`tests/views/test_d2_section_index.py` 8 项通过（身份隔离、授权透传、answer 召回、字节偏移、通用性）；`tests/skill_interface/test_d2_provenance.py` 4 项通过。新增测试在修复前失败、修复后通过，能实际捕获本轮缺陷。

全量逐文件回归（124 个 `test_*.py`，隔离数据根）：117 PASS / 7 FAIL。7 项失败集中在 `tests/js_ts_analysis` 与 `tests/module_resolution`，根因是可选 tree-sitter grammar 未安装（符号解析返回空），在干净 HEAD（无 D2 改动）复跑同样 7 项失败，确认为既有环境缺口，非本轮回归。`122 PASS / 0 FAIL` 基线是 `tests/research` 单目录口径（`docs/en/TESTING.md`），与此全仓统计不冲突。未删除旧测试、未削弱断言、未靠重试刷绿。

## 10. Git 提交与安装态证据

开发分支 `dev/p2d2-content-retrieval`，功能修复独立提交（见机器可读结果 `git_commit`）。`version` 保持 `0.1.0-beta.3`，marker 更新 `dev_commit` 并标注 NOT a released version，未创建 beta.4 Tag/Release。安装态 `_sourcelore_src/src` 同步后与工程源码逐字节一致，正式入口复验不依赖 `SOURCELORE_PROJECT_ROOT`。

## 11. A 层前后指纹

隔离根 A 层指纹 `fingerprint_assets` 调用前后一致（`SL-A-f059b37b...`，摘要口径为资产字典 SHA-256）；真实六库全程只读，未发生写入。CAS 49 个文件字节与 mtime 未变。

## 12. 未解决问题与后续任务

- TD-004 宿主自动触发与轨迹导出：NOT_VERIFIED，待用户真实独立会话验收。
- SKILL.md 三处不一致：保留用户自有修改，是否统一由用户决定。
- 历史 A 层 `SYNTHETIC_FIXTURE` 来源：本轮不改，纠正需独立授权的新版本 + 隔离裁决轮次。
- tree-sitter 可选依赖：本轮不安装（无离线 wheel，且改环境超出边界）；7 项失败在干净 HEAD 复现。
- Rust 源码 AST/调用图：不在本轮范围，不进入 P3。

## 13. 执行记录

工具：SourceLore Skill（已重载）、正式 `answer`/`derive` 入口、隔离根副本（非真实六库）、专项与全量测试脚本。网络请求 0；真实知识库写入 0；生产源码仅本轮功能修复；安装态按既有机制同步。本轮写入仅限隔离副本派生索引、scratch 验收脚本/结果与本文及机器可读结果。
