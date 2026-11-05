# F2-P4C 检查点（前置三问题修复中）

**基线**：40038d6 · Crosswalk sha256 `42841207…` 已验证未变

## 用户指出的三个前置问题 —— 实测核查结论

### 1. Evidence 完整性：**确认是真缺陷，已修**

原 `_evidence_refs` 只拼接非空 `evidence_refs`/`fact_ids`，**不解析、不核对**。

已改 `src/research/evidence_selector.py`：

- 新增 `_known_fact_ids(store, repository_id)` —— 从 Storage 收集真实存在的 fact_id
- 新增 `assess_evidence_integrity(store, refs, known_facts)` —— 逐条解析
- 四个等级：`FULLY_LOCATABLE` / `PARTIALLY_LOCATABLE` /
  `UNRESOLVED_NO_INTEGRITY` / `NO_EVIDENCE`
- 必需字段校验：`tree_entry` 要 `kind/path/object_type`；
  `source_snapshot` 要 `kind/commit_sha/snapshot_asset_id/completeness_status`
- `fact:` 前缀引用必须在 Storage 里真实存在
- `EV_NONE`/`EV_UNRESOLVED` → 进 `untrusted_findings`（reason 区分
  `NO_LOCATABLE_EVIDENCE` vs `EVIDENCE_NOT_RESOLVABLE`）
- `EV_PARTIAL` → 保留 finding 但加限制"证据只能部分核对"
- finding 新增 `evidence_integrity` 与 `evidence_integrity_detail`
- 返回值新增 `evidence_integrity_summary`

### 2. Research Packet 摘要：**实测已覆盖，但需补新字段**

实测改动十个字段（coverage_state / limitations / review_status /
verdict_status / evidence_refs / dist_restrict / provenance /
packet_status / freshness / claim_refs）→ **digest 全部变化**。

但问题 1 修复后新增的 `evidence_integrity_summary` 必须一并进 digest，
否则"证据完整性变化"不会改变摘要 —— 这是本轮新增的覆盖要求。

### 3. Run 执行顺序：**确认是我的缺陷，待修**

实测：同一 candidate 的 19 次 run **共享一个 logical_identity**，
`asset_version` 在该身份内单调递增 —— 所以 `revalidation_run_store._latest`
（带 `logical_identity` 过滤 + `ORDER BY asset_version DESC`）**是正确的**。

真正的问题在**我自己的测试与验证器**：
`ORDER BY rowid DESC`（以及我一度改成全局 `asset_version DESC`）是
**跨身份**排序，库里一旦有第二个 candidate 的 run 就会取错。

## 尚未完成

1. `research_engine.py` 调用方改为 `select_findings(store, ...)`（**正在改**）
2. `research_packet.py` 收 `evidence_integrity` 并入公开字段
3. 测试与工具去掉 `rowid` 依赖，改用业务键
4. Trusted Statement Bank / `STRICT_CITED` / `DRAFT_FOR_REVIEW`
5. LLM Adapter + 逐句引用校验
6. 文档 + 账本 + 提交

## 关键约束（续跑必读）

- 本轮是 **F2-P4C**，不是 P4B；不重跑 P4B，不提前进 Product/Security/Skill
- 真实 DeepSeek-V4.1 Flash 调用仍**待验证**（尚无真实调用证据）
- 未联网 GitHub；Y6-P3 UNVERIFIED、Y6-P6 OPEN；B-1/B-2/B-3 仍 OPEN
- 证据可信度按**可核对性**判定，不以非空为准
- 排序必须用业务键（`run_id`/`logical_identity`+`asset_version`/`created_at`），
  **不得**用 `rowid`

---

## 状态更正（2026-11-05；以下取代上方旧的“尚未完成”列表）

F2-P4C 确定性合成门禁已在提交 `056de101ab2dcc6a21cfcc1af0390a8f6102fc4e` 中实现，并已本地复核。P4C 组件、三个前置问题、Gold 与离线合成回放均已通过；`REAL_LLM_CALL_VERIFIED` 仍 OPEN。

本次发现旧验收脚本误标为 P4B，且会重跑整个 `tests/research`。现已改成只运行 `test_synthesis.py` 与 `TestEvidenceIntegrity`，并实际运行 `tools/f2p4c_verify.py`：22 + 6 个定向测试、Gold 10/10、离线回放 6 场景、门禁 20/20。没有重跑 P4B 全套或前序模块回归。此前 599 项结果仍是历史证据。

真实模型调用未启动：DSH Relay 的当前 allowlist 只含 Cosmos 项目根，不包含 SourceLore 的 GitHub Knowledge Base 路径。配置文件存在，但未读取其内容或凭证；未修改 allowlist、未派发 Relay 任务。下一步需先按项目权限流程明确允许目标 workspace，并完成所需 Host 刷新。

### 验收版本证据（2026-11-05）

- `verified_commit`: `056de101ab2dcc6a21cfcc1af0390a8f6102fc4e`
- 验收时间：`2026-11-05T14:09:54+08:00`
- 验收器：`p4c-scoped-v1`；SHA-256：`d2a69f8191ae9d0bb258dc7bcc2f8d1a23dc0c616c711ab16267716c13a91fad`
- 验收工作树为 dirty；当时未提交路径为验收器与生成报告四项，`src/research/`、`tests/research/` 对 `verified_commit` 无差异。此结果不能表述为干净检出的 `056de10` 通过。
- 随后发现的未跟踪 provider 预检检查点未参与上述运行，本轮保持原样。
