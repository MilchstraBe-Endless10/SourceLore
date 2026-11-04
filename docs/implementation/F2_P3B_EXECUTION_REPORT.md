# F2-P3B · 执行报告

产物：`F2_P3B_VERIFICATION.json`（22/22）、`F2_P3B_E2E_REPLAY.json`、
`F2_P3B_P3A_IMPLEMENTATION_AUDIT.json`、`F2_P3B_GATE_RESULTS.json`、
`F2_P3B_REVALIDATION_ARCHITECTURE.md`

**结论先行：候选队列与受控授权边界 DONE。只生成提议与计划，未执行任何真实工作。**

---

## 1. P3A 实现核验（§1）—— 一处实质不符，已按题面处理

逐项查了 P3A 真实代码，**没有按交接里的字段名假定**。

**`conflict_detected` 不存在于 `FreshnessAssessment`。**
它只存在于 **EC 的 `Verification`**（`src/evidence_claims/ec_models.py`）。
`src/lifecycle/*.py` 里 grep 命中 **0 次**。

按题面"缺失不能解释成 false"，补了向后兼容的三态字段：

```
CONFLICT_NONE       已核验：无冲突
CONFLICT_DETECTED   已核验：确有冲突
CONFLICT_UNKNOWN    未核验（默认，不得当作无冲突）
```

- 默认值是 `CONFLICT_UNKNOWN` → **旧记录读出来不会被误认为"无冲突"**
- 候选门禁对 `CONFLICT_DETECTED` 与 `CONFLICT_UNKNOWN` **分别拒绝**，原因码不同
- 测试 `test_t8b` 专门验证 `CONFLICT_UNKNOWN` 不放行

其余 9 项核验均通过（schema、证据、watch 关联、old/new commit、
observation_id、refs、可读性、幂等、CAS 修复仍在）。

---

## 2. 候选 Schema 与状态机

```
RevalidationCandidate {
  candidate_id, watch_id, source_claim_id, source_verification_id,
  repository_id, requested_ref, baseline_commit_sha, target_commit_sha,
  canonical_scope, revalidation_rule_version,
  status, reason_code, source_level,
  source_assessment_id, observation_id,
  expected_target_claim_identity, revalidation_of,
  state_reason, superseded_by, conflict_state, conflict_fact_ids
}
```

状态机（最小集）：

```
PROPOSED  → 提议已成立，等待授权
BLOCKED   → 来源不可调度 / 条件不满足
SUPERSEDED→ 被更新目标取代（历史保留）
CANCELLED → 人工取消
```

**本轮不实现 `AUTHORIZED`** —— P3B 未通过 Y6-P3 审批门禁，
所以不引入该状态，也不制造任何平台批准回执。

执行状态（SUCCESS/FAILED/TIMEOUT/UNKNOWN）属 Runtime，**不与候选状态合并**。

---

## 3. candidate_id 生成契约

```
candidate_id = SL-REVAL- + H(watch_id, source_claim_id, target_commit_sha,
                             repository_id, revalidation_rule_version,
                             canonical_scope)[:32]
```

实测性质：

| 场景 | 结果 |
|---|---|
| 同 watch + 同 Claim + 同目标 | 身份一致 |
| 不同 watch | 不碰撞 |
| 不同目标 Commit | 不碰撞 |
| 不同 repository_id | 不碰撞 |
| 时间戳 | 不参与身份 |
| 参数顺序 | 固定（canonical JSON） |
| 自由文本 | 不用作身份依据 |

`candidate_id` 与 `operation_id` 分别定义（后者为 `OP-RVQ-`）。

---

## 4. 生成门禁与拒绝原因

15 条按序执行，20 个原因码。实测拒绝覆盖：

| 触发 | 返回 |
|---|---|
| 评估不存在 | `ASSESSMENT_NOT_FOUND` |
| 非 POSSIBLY_STALE（如 VERSION_ALIGNED） | `NOT_POSSIBLY_STALE` |
| PINNED_COMMIT | 构造 watch 即 `ValueError`（无评估可查） |
| watch 不一致 | `WATCH_NOT_FOUND` / `WATCH_MISMATCH` |
| 仓库不一致 | `REPOSITORY_MISMATCH` |
| baseline 不一致 | `BASELINE_COMMIT_MISMATCH` |
| 来源损坏/不存在 | `ASSESSMENT_NOT_FOUND` / `ASSESSMENT_INTEGRITY_FAILED` |
| 冲突已检测 | `UNRESOLVED_CONFLICT` |
| 冲突未核验 | `CONFLICT_NOT_VERIFIED` |
| 来源等级非法 | `OBSERVATION_NOT_TRUSTED` |

**缺失、冲突、损坏都没有被转换成"没有待办"。**

---

## 5. 可信来源等级处理

| 等级 | 可进真实调度 | 实测行为 |
|---|---|---|
| `REAL_LIVE_API` | **是（唯一）** | 候选 `PROPOSED` → 计划 `PLAN_READY` |
| `HISTORICAL_REAL_DATA` | 否 | 候选 `BLOCKED` |
| `SYNTHETIC_FIXTURE` | 否 | 候选 `BLOCKED`，Dry-Run `CANDIDATE_NOT_PROPOSED` |

实测端到端：

```
基线（P1C 执行记录）        → VERSION_ALIGNED，候选 NOT_POSSIBLY_STALE
合成新 Commit B             → POSSIBLY_STALE，候选 BLOCKED，计划 CANDIDATE_NOT_PROPOSED
真实来源（live 替身）新 Commit C → POSSIBLY_STALE，候选 PROPOSED，计划 PLAN_READY
```

合成候选**入队保留可追溯性**，但状态是 `BLOCKED` 且明确标注原因。

---

## 6. A→B→C 与 Ref 回退

| 场景 | 实测 |
|---|---|
| A→B | 建 B 候选，`PROPOSED` |
| 重复观测 B | `IDEMPOTENT`，不推进版本 |
| B 未处理又来 C | B 保留在 `history`；C 成活动候选；返回 `SUPERSEDED_EXISTING` + `superseded_candidate_id` |
| 标 B 为 SUPERSEDED | 新版本写入，**旧版本仍可读**（2 个版本） |
| Ref 从 C 回 A | 评估变 `VERSION_ALIGNED` → 不产候选；**历史候选不删除** |

`mark_superseded` 走新版本，`state_reason` 写明"被 X 取代"，**不静默覆盖**。

授权不转移：新目标的候选 `target_commit_sha` 不同、`candidate_id` 不同，
且 payload 里**没有任何** authorized 字段。

---

## 7. 每个 watch 单活动候选的并发结果

### 设计（§7 方案 A）

候选历史与活动槽位放在**同一个** `WatchQueueState` payload 里，
**一次 CAS** 完成"加候选 + 推槽位"。Storage 用 `BEGIN IMMEDIATE`，
K4 在事务内校验 `pointer_version`。

结构上不可能有两个活动候选 —— 只有一个 `active_candidate_id` 字段。

### 实测（真实多进程）

| 实验 | 结果 |
|---|---|
| 4 进程同时提议同一目标 | 最多 1 个新建队列；候选资产数 = 1；活动候选数 = 1 |
| 2 进程同时提议不同目标 | 活动候选 ≤ 1，无多活动 watch |
| 不同 PID | 断言通过（`len(pids) == len(outs)`） |

**修正一处真实缺陷**：`count_active` 初版把 A 层的历史版本也算进活动候选，
导致误报"两个活动候选"。改为**只取每个 watch 的最新版本**后正确。

---

## 8. CAS、幂等及崩溃恢复

| 项 | 实测 |
|---|---|
| 重复入队（真调两次） | `IDEMPOTENT`，候选数 1，队列版本不推进 |
| 错误 `expected_version` | `CONFLICT` |
| 真实 SIGKILL（提交后） | 资产在、`OP-RVQ-` 有记录；重放不新增资产、不推进版本 |
| `operation_id` 对账 | 重复执行同一提议 → `IDEMPOTENT`，版本不变 |

SIGKILL 用 `os.kill(os.getpid(), 9)`，父进程断言 `returncode != 0`
且 stdout 有 `COMMITTED` —— **真的被杀死**。

---

## 9. 原始 Claim/Verification 不可变性

| 检查 | 结果 |
|---|---|
| Claim payload 指纹 | 提议前后**完全相等** |
| Verification payload 指纹 | 提议前后**完全相等** |
| `claim_verification` 数量 | 前后不变（不生成新 verification） |
| `extracted_fact` 集合 | 前后不变 |

指纹是 payload 的 sha256（A 层不可变，篡改会被内容哈希校验拦下 ——
这一点在测试中也顺带验证过）。

---

## 10. Dry-Run 调度是否有实际工具副作用

**没有。** 计划里 `side_effects` 全部为 false：

```
called_collector / called_github / extracted_facts /
adjudicated_claims / modified_verification / modified_review_status
```

另有独立测试断言：Dry-Run 前后**资产总数不变**（不写任何东西）。

三个事件在计划里显式分开：

```
"events_distinguished": {
  "PLAN_READY": true,
  "EXECUTION_AUTHORIZED": false,
  "EXECUTION_COMPLETED": false
}
```

`assert_no_authorization()` 会在被误标时抛错。

---

## 11. 人工授权及 Harness 审批状态

- **本轮未获得任何真实人工授权**，也没有制造平台批准回执
- `AUTHORIZED` 状态**未实现**
- 计划的 `authorization_required = True`，
  `execution_prerequisites` 里明确要求
  "human_authorization_for_this_target_commit"
- Y6-P3 仍为 **UNVERIFIED**（未借本批关闭）

---

## 12. 新增代码与测试文件

```
src/lifecycle/revalidation_models.py         候选 + 队列模型 + 20 原因码
src/lifecycle/revalidation_planner.py        15 条门禁 + 目标 Claim 身份
src/lifecycle/revalidation_queue.py          原子队列 + 幂等 + CAS
src/lifecycle/revalidation_dispatch_gate.py  Dry-Run 计划闸门
tests/lifecycle/test_revalidation_queue.py            29 项
tests/lifecycle/test_revalidation_concurrency.py       8 项
tools/f2p3b_e2e_replay.py、tools/f2p3b_verify.py
docs/implementation/F2_P3B_*（5 份）
```

修改：
- `src/lifecycle/lc_models.py` 加三态冲突字段（向后兼容）
- `src/lifecycle/freshness_evaluator.py` 透传冲突状态
- `src/lifecycle/ref_observer.py` 观测证据带 provenance 标记
- `src/storage/asset_models.py` 登记 2 个新资产类型

---

## 13. 全部测试数量及退出码

```
tests/runtime           45 OK   exit 0
tests/storage           53 OK   exit 0
tests/collector         48 OK   exit 0
tests/facts             44 OK   exit 0
tests/evidence_claims   36 OK   exit 0
tests/lifecycle         77 OK   exit 0    ← 40 (P3A) + 37 (P3B)
f2p3b_verify           22/22 PASS
f2p3a 18/18  f2p2b 17/17  f2p2a 15/15  f2p1c 22/22  f2p1b 16/16  f2p1a 22/22  f1d 26/26
```

303 项 unittest + 159 项验收断言，失败 0。

---

## 14. F1-D 冻结 SHA-256

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变，f1d_verify 26/26 通过。

---

## 15. 当前 OPEN 门禁

| 门禁 | 状态 |
|---|---|
| F2-P3C 受控重新验证执行 | 未开始 |
| Y6-P3 审批传递 | **UNVERIFIED**（本批未关闭） |
| Y6-P6 BotHarness 端到端 | **OPEN**（本批未关闭） |
| B-1/B-2/B-3 分发门禁 | **OPEN**（本批未关闭） |
| 实时 GitHub Ref 检测 | 未执行（本轮未联网） |

---

## 16. F2-P3C 受控重新验证执行的最小可执行起点

1. **只消费 `PROPOSED` 候选 + `PLAN_READY` 计划**，不重新判定资格。
2. **前置硬门禁**：必须有可追溯到人的授权记录，且授权范围**精确覆盖**
   `candidate_id + target_commit_sha`；无授权立即拒绝（不降级、不猜测）。
3. 执行顺序固定：Collector（针对 target Commit）→ Facts → 新 Claim（身份由
   `expected_target_claim_identity` 校验）→ EC 裁决。
4. **旧 Verification 一律不动**；新结果写入新 `verification_id`。
5. 执行状态（RUNNING/SUCCESS/FAILED/TIMEOUT/UNKNOWN）写 Runtime，
   **不回写候选状态**（候选只从 PROPOSED 走到 SUPERSEDED/CANCELLED）。
6. 执行中若目标又变（新 Commit C），必须保留正在执行的真实状态，
   **不得未经协调替换**。
7. 必测：无授权被拒；授权过期被拒；授权范围不匹配被拒；
   执行成功不自动 approved；执行失败不把旧 Claim 标 refuted。
