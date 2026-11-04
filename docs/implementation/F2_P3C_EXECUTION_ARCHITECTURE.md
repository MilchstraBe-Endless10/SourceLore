# F2-P3C · 受控重新验证执行架构

产物：`F2_P3C_INTERFACE_AUDIT.json`、`F2_P3C_E2E_REPLAY.json`、
`F2_P3C_VERIFICATION.json`、`F2_P3C_GATE_RESULTS.json`、`F2_P3C_EXECUTION_REPORT.md`

**两个结论分开报：A. LOCAL_CONTROLLED_EXECUTION = DONE；B. REAL_HARNESS_AUTHORIZED_E2E = OPEN。**

---

## 1. 接口核验（§1，14 项）

逐项读代码，不按交接文档猜字段。结果见 `F2_P3C_INTERFACE_AUDIT.json`。

**三个真实缺口（已记录、未假装存在）：**

| 缺口 | 影响 | 处理 |
|---|---|---|
| **无真实授权传递通道** | B 类无法完成 | 只用 TEST_ONLY 隔离授权 |
| Runtime 无 revalidation 专用阶段状态 | 无法直接复用 | 新建 `revalidation_run`，复用其状态词表 |
| Collector 无「给定 commit 收全量快照」一体化入口 | 需组合调用 | 写 `collector_adapter` 包装现有三方法，**不新建 Collector** |

`commit_for_ref(owner, name, <sha>)` 就是 `/commits/{sha}` —— 所以"按固定 Commit 取数"是可行的。

---

## 2. 授权契约（§2）

**四类批准严格分开：**

```
DEV_BATCH_APPROVAL    开发批次批准（本批）
TEST_ONLY             测试夹具生成（隔离用）
HUMAN_OPERATOR        真实人类授权（需可核验证明）
PLATFORM_APPROVAL     BotHarness 平台审批（Y6-P3，仍 UNVERIFIED）
```

**硬规则（全部有测试）：**

1. 默认拒绝
2. 无授权 / 过期 / 未生效 → 拒绝
3. candidate_id / Commit / 仓库 / Ref 不符 → 拒绝
4. 操作范围不符或含未允许操作 → 拒绝
5. 授权被撤销 → 拒绝
6. 未知来源 → 拒绝
7. **不得只凭 `approved=true` 判定**（无 source 时判 `AGENT_SELF_APPROVED`）
8. Source 是 AGENT/SELF/MODEL/LLM → 拒绝
9. **TEST_ONLY 永不进入正式调度**（`require_production=True` 拒绝）
10. 正式模式要求可核验 kind + 必须有 proof
11. **计划绑定**：`plan_digest` **重新计算**后比对（初版只比字段，可被同时篡改绕过 —— 已修）

`authorized_operations` 是固定白名单，不接受任意扩充。

---

## 3. 候选与执行的责任分离（§3）

候选状态机维持 P3B 的四态（`PROPOSED/BLOCKED/SUPERSEDED/CANCELLED`）。
**执行状态独立**在 `revalidation_run` 里，走 Runtime 词表：

```
SUCCESS / FAILED / TIMEOUT / CANCELLED / UNKNOWN
```

阶段状态是内部的（`PENDING/RUNNING/COMMITTED/FAILED_RETRYABLE/FAILED_FATAL/UNKNOWN`），
**不冒充 Harness 原生状态**。

`run_id = H(candidate_id, plan_digest, authorization_id)` —— 同候选+同计划+同授权幂等。

---

## 4. 执行前最终检查（§4）

进执行前**重新从 Storage 读**：候选、队列、评估、源 Claim、源 Verification、计划、授权。
七项校验：未取消、未取代、目标未被篡改、源 Claim 存在、队列版本符合、授权覆盖、无未解决冲突。

**`SUPERSEDED` 一律禁止新启动**（有测试，并断言此时 Collector 零调用）。

---

## 5. 只对固定目标 Commit 运行（§5）

```
fetch_commit(B) → 断言返回 sha == B → tree_sha 必须来自 commit.tree.sha
                → fetch_tree(tree_sha) → 条目结构校验
```

**没有 Ref 解析调用**（测试断言 `calls == [("fetch_commit", B), ("fetch_tree", TREE)]`）。

- 返回别的 Commit → `COLLECTED_COMMIT_MISMATCH`，**不悄悄改用**
- `tree_sha` 缺失 → `ROOT_TREE_NOT_FROM_COMMIT_OBJECT`
- **条目 sha 非法 → 拒绝**（初版直接接受 `sha="zzz"` 的损坏 tree，实测抓出后已修 —— 损坏来源不得产生 supported/refuted）
- 只读 API 超时 → `UNKNOWN` + `uncertain_side_effect=True`，**不自动重试**

---

## 6. Facts 与 Claim（§6/§7）

Facts **真正调用** `extractor.extract_file_path_observation`（规则固定 `file_path_observation@v1`）；
只消费目标快照；`UNKNOWN` 不入库（按 insufficient 处理）；
断言 fact 的 `commit_sha == B`、`snapshot_asset_id == B 的快照`。

新 Claim 用 `ec_models.build_path_claim(...)` 重新生成（**不是复制旧 ID 换 Commit**），
并断言 `claim_id == expected_target_claim_identity`；
不一致 → `TARGET_CLAIM_IDENTITY_MISMATCH`，**立即停止**且不写出错误 Claim。

`review_status` 从 `pending_review` 开始 —— **不复制旧 Claim 的人工审核状态**。

---

## 7. 跨阶段 Checkpoint（§9）

八阶段：`PREFLIGHT → AUTHORIZATION_CHECK → SNAPSHOT_COLLECT → FACT_EXTRACT →
TARGET_CLAIM_CREATE → EVIDENCE_VERIFY → RESULT_PERSIST → COMPLETION_CHECK`

每阶段记录 `run_id/stage/input_digest/operation_id/expected_outputs/
actual_outputs/execution_status/checkpoint_version/error_code`。

**授权在 `SNAPSHOT_COLLECT` 之后再查一次**（§11 C-5：不只在开始时）。

**不宣称两个独立 SQLite WAL 有全局原子事务** —— 跨库继续用 `operation_id` 对账。

---

## 8. 执行期间目标变化（§10）

B 的结果绑定 `target_commit_sha=B`，且 `freshness_context.is_current_ref_target=False`，
并带"已不是当前 Ref 目标"提示。

C 出现时：B 的结果不变、C 产生新候选、C 的授权必须独立。
**旧授权用于 C 的执行 → 拒绝，且 Collector 零调用**（有测试）。

---

## 9. 最小完成结果（§12）

`execution_status=SUCCESS` 与 `verification_status=supported/refuted/insufficient_evidence`
**是两个字段**。实测：PARTIAL 未命中时执行 SUCCESS 而裁决 insufficient —— 这是合法结果。

---

## 10. 明确不做

- 不执行真实联网重新验证（无真实授权）
- 不新建第二套 Collector/Facts/EC/Storage
- 不改旧 Verification、不改人工审核状态、不自动 approved
- 不发布当前知识视图
- 不修改 F1-D 冻结基线
