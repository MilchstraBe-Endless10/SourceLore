# P2 后遗留技术问题专项处理 · 执行证据（脱敏）

> 基准 main：`2bdfd73`；不进入 P3，不发布 beta.4，不修改历史知识资产，不放宽来源可信性与分发门禁。
> 本文件为专项执行证据与差距分析；CI 与全量回归数字只作背景，功能判级以专项事实级断言为准。
> 脱敏：不含作者本机绝对路径、真实知识库内容原文、第三方未授权知识原文；完整原始证据仅留本地，不随公开仓库分发。

## 0. 结论总表

| 项 | 判定 | 说明 |
| --- | --- | --- |
| TD-001 | 已修复 | 根因为首开库时 `meta.schema_version` 的 check-then-insert 非原子竞争；两处源码原子化；RED→GREEN 回归 + 多轮压力验证通过 |
| TD-002 | 部分解决（已定位边界） | 底层源码事实完整，覆盖不足源于真实库派生视图过期；隔离副本离线重建成功；真实 A 层不重建、不联网 |
| TD-003 | 部分解决（差距明确） | 内容对应性/Fork 区分机制已在源码与真实数据落地；独立的远端身份二次认证与新授权法律判定仍需后续开发 |
| TD-004 | 未验证（待用户） | 必须由用户在真实 OpenBot 独立新会话验收；开发 Agent 不以内部 CLI/模拟会话/旧长会话冒充 |

## 1. 恢复真实工程状态

- 本地 MAIN、远端 main、安装态 marker `dev_commit` 均核对为同一基准 `2bdfd73`；`version=0.1.0-beta.3`，未发布版本。
- 用户自有未提交改动（一处在用插件客户端、一份进度记录）全程原样保留，未 stash 覆盖、未提交。
- A 层资产指纹：`real/preserve/isolated = 1089 / ddb2072e65fad724`，三项一致，专项前后未变。

## 2. TD-001 — 并发 UNIQUE 冲突（已修复）

### 2.1 现象与复现

- 现象：`UNIQUE constraint failed: meta.k`，多进程同时首开同一个新库时偶发。
- 隔离复现脚本：N 个进程等待同一 `go` 文件后同时首开新库并写 checkpoint。
- 修复前：`30` 轮 × `16` 进程，`16/30` 轮出现 `UNIQUE constraint failed: meta.k`（本机约 1/3 概率，与登记一致）。

### 2.2 根因

- `src/runtime/checkpoint_store.py` 的 `_init_schema()` 用 `SELECT v FROM meta WHERE k='schema_version'`，读为空再 `INSERT`。
- 该 check-then-act 非原子：多进程都读到空，各自插入同一主键 `meta.k`，唯一键冲突。
- 同类缺陷存在于 `src/storage/knowledge_store.py`，同一模式。

### 2.3 最小修复

两处均改为单条原子 `INSERT OR IGNORE INTO meta(k,v) VALUES('schema_version',?)`，再统一读回校验：

- 保留 `meta.k` 唯一约束，未删除。
- 只忽略预期的键冲突；读回缺失或版本不匹配仍显式报错，不吞未知异常。
- 不依赖重试或 CI rerun 宣告修复。

### 2.4 数据完整性核查

- 并发失败路径未产生孤立 checkpoint 或重复资产：回归断言 `meta.schema_version` 唯一值、checkpoint 数量与身份完整、`PRAGMA integrity_check=ok`。
- 当前指针一致性由既有 CAS 路径保证；本次未改动该路径。

### 2.5 专项验证

| 验证 | 结果 |
| --- | --- |
| 新回归 `tests/runtime/test_checkpoint_concurrent_init.py`（含 knowledge_store 同类用例） | 修复前 RED（首轮即捕获 UNIQUE）；修复后 `3/3` |
| 原现场 `tests/runtime/test_concurrency.py` | `7/7` |
| checkpoint 压力脚本 | 修复前 `16/30` 失败；修复后 `0/30` |
| knowledge_store 首开锁竞争独立探针 | `40` 轮 × `16` 进程 `0` 失败 |
| 全量回归 | 见 §5 |

> 观察：最初严格版回归曾出现一次 `database is locked`（FTS5 探测 + 多 DDL 的 schema 锁竞争）。独立探针 3 次并发度（8/16/24）与 40 轮压力均未复现，连续 3 次重跑回归全绿，判定为测试环境时序偶发，非稳定缺陷；按最小修复原则未扩大改动范围。

## 3. TD-002 — 旧图谱覆盖不足（部分解决，边界明确）

### 3.1 三种情况区分

| 情况 | 判定 | 证据 |
| --- | --- | --- |
| 新版解析器能力不足 | 否 | 同一批源码事实在隔离副本上可重建出完整语义图谱（DECLARES/IMPORTS/RE_EXPORTS/RESOLVES_TO） |
| 历史 Facts 缺失 | 否（样本） | Preact 该 commit 有 `236` 条源码事实；符号覆盖 `COVERED_BY_EXTRACTED_SOURCE` |
| 历史派生视图过期 | 是 | 真实库该 commit 图谱仅 `46` 节点 / `32` 边（全为 `TREE_CONTAINS`，无源码语义边）；隔离副本同 commit 为 `155` 节点 / `178` 边 |

### 3.2 离线重建验证

- 使用已有知识的隔离副本，经正式 CLI `derive`（离线、零网络）对 Preact 重建：
  - `ok=true`，`code_rows=236`，`nodes=155`，`edges=178`。
  - 关系状态 `RELATIONS_FOUND`：`40` 条关系全 `RESOLVED`，`supplement_count=0`。
  - 边类型：`TREE_CONTAINS=32`、`DECLARES=80`、`IMPORTS=43`、`RE_EXPORTS=13`、`RESOLVES_TO=10`。
- 重建前后 A 层指纹不变（1089 / ddb2072e65fad724），未写真实 A 层，未覆盖旧版本证据，未联网采集。

### 3.3 结论与缺口

- 覆盖不足只需重建派生视图即可解决，底层源码事实完整；缺失的不是底层资产，而是真实库中的派生视图新鲜度。
- 本轮按纪律未在真实库执行重建；后续如需在真实库补齐，应单独授权，仍不动 A 层、不联网。

## 4. TD-003 — 来源身份 / Commit / 授权 / Fork（部分解决，差距明确）

### 4.1 源码链路（函数存在且生产接通）

- `src/trust/source_provenance.py`：`github_identity_evidence` 要求数字 ID + A 层权威 `subject_record(repository_display_name)` + `resolved_repository` 明确；`verify_source_binding` 叠加 commit/root_tree 一致 + 双方 `blob_refs` 哈希映射一致；`resolve_supplement` 只接受 `source_verified=1` 且复核通过的本地补充源。
- 调用点确认（非仅函数存在）：正式 CLI、知识问答、来源查询三条生产链路均调用 `resolve_supplement`（`cli.py`、`knowledge_answer.py`、`source_knowledge.py`）。
- `src/collector/content_acquisition_policy.py`：保守默认（未知即拒绝写入）、五维权限分离（fetch / persist_bytes / derive_facts / internal_preview / external_distribution）、结构化授权引用（拒绝裸布尔）、分发受独立门禁约束。

### 4.2 真实数据落地

- 权威身份记录 `subject_record(repository_display_name)`：4 条（含 `preactjs/preact`、`jonschlinkert/is-number`、`sindresorhus/is-plain-obj`、`Tobi1chi/arch-grower`）。
- 严格验证绑定：`2` 条，同一内容锚点下的 GitHub 数字 ID 与本地补充源，`evidence_ref=source_verified=1;method=github_identity_record+blob_subset`，含相同 commit/root_tree 与双方资产 ID。
- Fork 区分机制：`source_provenance.py` 注释与实现明确“相同 commit + root_tree 不足以证明同一仓库身份”，以权威 ID 记录 + blob 哈希一致补强；本地补充源不得伪装成 GitHub 数字 ID。

### 4.3 未解决差距（需后续开发，本轮不放宽门禁）

- 独立的远端/链上身份二次认证仍缺失：当前验证依赖既有 A 层权威记录，未做第二来源交叉认证。
- 第三方内容授权的新法律判定未做：本轮不扩大授权、不改分发门禁。
- 通用 Fork 区分（多源交叉/签名）尚未扩展到所有仓库；当前仅对已建立绑定与权威记录的仓库生效。

## 5. 全量回归与提交证据

- 全量回归（逐文件运行 `tests/` 下 `test_*.py`，脚本式测试）：`TOTAL=122 PASS=122 FAIL=0`，`EXIT=0`（含新增 TD 回归文件，比 P2-C 基线 121 多 1）；TD 阶段未引入回归。
- 功能修复 commit：见最终提交记录（本专项所有改动在同一分支提交）。
- CI：见下方提交后回填（仅作背景，不作功能判级）。
- 安装态同步：本轮修复未触及用户入口行为契约，是否同步见提交后判断（如同步则 dev_commit 指向本专项 commit；版本仍 `0.1.0-beta.3`，非发布版本）。

## 6. TD-004 — 宿主端到端自动触发（未验证）

- 状态：未验证 / 待用户。
- 边界：必须由用户在真实 OpenBot 独立新会话中实际使用验收；开发 Agent 不使用内部 CLI 测试、模拟会话或已有长会话冒充真实宿主自动触发成功。
- 本轮未执行任何冒充行为；该项在功能验收中保持未完成。

## 7. 本轮边界与未完成

- 未修改历史知识资产、未重置真实知识库、未改旧 Tag、未发布 beta.4、未进入 P3。
- 未在真实库执行派生重建或联网采集。
- 未放宽来源可信性与分发门禁。
- 待后续开发：TD-003 的二次认证与授权边界；TD-002 真实库派生视图刷新（需单独授权）；TD-004 由用户验收。
