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
