# F2-P3B · 重新验证候选队列与受控授权边界

产物：`F2_P3B_P3A_IMPLEMENTATION_AUDIT.json`、`F2_P3B_E2E_REPLAY.json`、
`F2_P3B_VERIFICATION.json`、`F2_P3B_GATE_RESULTS.json`、`F2_P3B_EXECUTION_REPORT.md`

**立场：本轮只生成提议与计划。绝不执行采集、抽取或裁决。**

---

## 1. P3A 实现核验（题面 §1）—— 一处实质不符

逐项查了 P3A 的真实代码，**不按交接里的字段名假定**：

| 检查项 | 结果 |
|---|---|
| `freshness_assessment` schema | OK，16 个字段，可读写 |
| POSSIBLY_STALE 带可信证据 | OK（`evidence_refs`） |
| **`conflict_detected`** | **不存在于 FreshnessAssessment** |
| watch → claim 关联 | OK |
| old/new commit | OK（`baseline_commit_sha` / `observed_commit_sha`） |
| `observation_id` | OK |
| `source_evidence_refs` | OK |
| 可通过 Storage API 读取 | OK |
| 重复评估幂等 | OK |
| 并发 CAS 修复 | 仍在（`_write` 检查 `idempotent`） |

`conflict_detected` 只存在于 **EC 的 Verification**（`src/evidence_claims/ec_models.py`），
`src/lifecycle/` 里 0 次命中。

**处理（按题面要求："缺失不能解释成 false"）：**
新增向后兼容的三态字段 `source_evidence_conflict`：

```
CONFLICT_NONE       已核验：无冲突
CONFLICT_DETECTED   已核验：确有冲突
CONFLICT_UNKNOWN    未核验（默认值，不得当作无冲突）
```

默认值为 `CONFLICT_UNKNOWN`，因此**旧记录读出来不会被误认为"无冲突"**。
候选门禁对 `CONFLICT_DETECTED` 与 `CONFLICT_UNKNOWN` 都拒绝，原因码分开。

---

## 2. 候选语义（严格限定）

候选**只**表示："某历史 Claim 对某个新观测 Commit 可能不再适用，建议重查。"

候选**不**表示：旧 Claim 已 false / 旧 Verification 已 refuted / 新 Commit 已 supported /
用户已批准 / Harness 已执行 / 新知识可发布。

每条候选有结构化来源：`source_assessment_id`、`source_verification_id`、
`observation_id`、`source_level`、`revalidation_of`。

---

## 3. 候选生成门禁（15 条）

顺序执行，任一失败即返回明确 reason_code：

| # | 条件 | 失败原因码 |
|---|---|---|
| 1-3 | Assessment 存在 / 类型正确 / 哈希可核验 | `ASSESSMENT_NOT_FOUND` / `ASSESSMENT_INTEGRITY_FAILED` |
| 4 | `freshness_state = POSSIBLY_STALE` | `NOT_POSSIBLY_STALE` |
| 5 | `applicability_scope = TRACKING_REF` | `NOT_TRACKING_REF` |
| 14 | 冲突已核验且无冲突 | `UNRESOLVED_CONFLICT` / `CONFLICT_NOT_VERIFIED` |
| 6-8 | watch 存在且 repo/ref 一致 | `WATCH_NOT_FOUND` / `REPOSITORY_MISMATCH` / `REF_MISMATCH` |
| 9 | baseline 与 watch 一致 | `BASELINE_COMMIT_MISMATCH` |
| 10-11 | 目标是合法 commit 且不同于 baseline | `TARGET_COMMIT_INVALID` / `TARGET_EQUALS_BASELINE` |
| 12 | Claim 真实存在 | `CLAIM_NOT_FOUND` |
| 13 | 源 Verification 可定位 | `VERIFICATION_NOT_FOUND` |
| 15 | 观测来源级别合法 | `OBSERVATION_NOT_TRUSTED` |

缺失、冲突、损坏**都不会**被转换成"没有待办"。

---

## 4. 来源等级隔离

| 等级 | 可进真实调度？ | 用途 |
|---|---|---|
| `REAL_LIVE_API` | **是**（唯一） | 真实 Ref 解析 |
| `HISTORICAL_REAL_DATA` | 否 | 可追溯回放 |
| `SYNTHETIC_FIXTURE` | 否 | 状态转换测试 |

合成来源的候选**会入队（保留可追溯性）但状态为 `BLOCKED`**，
`state_reason = SYNTHETIC_SOURCE_NOT_DISPATCHABLE`，Dry-Run 拒绝生成计划。

历史真实观测明确记录其历史时点，**不当作当前 Ref 的最新状态**。

---

## 5. 候选身份

```
candidate_id = SL-REVAL- + H(watch_id, source_claim_id, target_commit_sha,
                             repository_id, revalidation_rule_version,
                             canonical_scope)[:32]
```

不含时间戳、不含自由文本。→ 同 watch + 同 Claim + 同目标重复提议身份一致；
不同目标 / 不同 watch / 不同仓库身份不同。

`candidate_id` 与 `operation_id` 分别定义。

---

## 6. 旧 Claim 与新 Claim

Claim 身份含 Commit（P2B 冻结契约），所以目标 Commit 必须形成新 Claim。

候选保存 `expected_target_claim_identity`，按 P2B 同一契约确定性计算：

```
H(repository_id, target_commit_sha, claim_type, {normalized_path, expected_exists}, schema)
```

缺必要参数时返回 `None`（记录待生成条件，**不猜**）。
本轮**不真正生成**新 Fact / 新 Claim / 新 Verification。

---

## 7. 单活动候选的原子协调（§7 方案 A）

**拒绝不安全流程**（"先查 pending 再插入"，两进程都能通过）。

采用：**每个 watch 一个版本化队列资产**，把**候选历史列表**与**活动槽位**放进
**同一个 payload**，一次 CAS 写入完成两件事：

```
WatchQueueState {
  queue_id, watch_id, repository_id,
  active_candidate_id,           ← 唯一活动槽位
  active_target_commit_sha,
  history_candidate_ids          ← 全部候选（含被取代的）
}
```

Storage 的 `append_asset_and_advance` 用 `BEGIN IMMEDIATE`，K4 在**事务内**校验
`pointer_version` —— 所以"加候选 + 推槽位"是原子的。

候选自身也落 A 层资产（可追溯），但**活动性只由队列决定** ——
结构上不可能有两个活动候选，因为只有一个字段。

---

## 8. A→B→C 与 Ref 回退

| 情况 | 处理 |
|---|---|
| A→B | 建 B 的候选，状态 `PROPOSED` |
| 重复观测 B | 同候选，`IDEMPOTENT`，不推进版本 |
| B 未处理又来 C | B 保留在 `history`；C 成为活动候选；B 标 `SUPERSEDED`（**不静默覆盖**） |
| B 已授权又来 C | 授权不转移 —— C 是新候选，`target_commit_sha` 不同 |
| B 执行中来 C | 本轮只定义契约（`SUPERSEDED` 不覆盖执行态；执行态属 Runtime） |
| Ref 从 B 回 A | 历史候选**不删除**，重新评估 Activity 目标 |

---

## 9. 状态机

```
PROPOSED   提议已成立，等待授权
BLOCKED    来源不可调度 / 条件不满足
SUPERSEDED 被更新的目标取代（历史保留）
CANCELLED  人工取消
```

**本轮不实现 `AUTHORIZED`。** P3B 未通过 Y6-P3 审批门禁，
所以不引入该状态、也不制造任何平台批准回执。

执行状态（SUCCESS/FAILED/TIMEOUT/UNKNOWN）属 Runtime，**不与候选状态合并**。

---

## 10. 受控调度（Dry-Run）

`prepare_revalidation_plan(candidate_id)` 只读生成计划，
**最多完成 `PLAN_READY`**。

三个事件严格分开，计划里显式标注：

```json
"events_distinguished": {
  "PLAN_READY": true,
  "EXECUTION_AUTHORIZED": false,
  "EXECUTION_COMPLETED": false
}
```

`side_effects` 全为 false：不调 Collector、不调 GitHub、不抽 Facts、
不裁决 Claim、不改 Verification、不改 review_status。

---

## 11. 明确不做

- 不调用真实 GitHub API / Collector / Facts 抽取器 / EC 裁决器
- 不改旧 Verification、不改人工审核状态、不自动批准、不发布知识
- 不建第二套权威数据库
- 不修改 F1-D 冻结基线
