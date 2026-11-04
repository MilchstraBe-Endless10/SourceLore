# F2-P2B · Evidence-Claims 架构

产物：`F2_P2B_PRECONDITION_AUDIT.json`、`F2_P2B_E2E_REPLAY.json`、
`F2_P2B_VERIFICATION.json`、`F2_P2B_GATE_RESULTS.json`、`F2_P2B_EXECUTION_REPORT.md`

**立场：只做确定性裁决。不调 LLM，不做 Research，不做 Renderer。**

---

## 1. 两层身份必须分开（本批地基）

| 概念 | 由什么决定 | 会随证据变吗 |
|---|---|---|
| `claim_id` | 仓库 + 固定 Commit + 命题类型 + 规范化参数 + Schema 版本 | **不会** |
| `verification_id` | claim_id + 已排序 fact_id 集合 + 事实内容摘要 + 规则版本 + 验证参数 | **会** |

同一命题换证据 → `claim_id` 不变、`verification_id` 变。
**时间戳不参与任何身份计算。**

---

## 2. 五态分离（题面第 8 节）

```
claim_type          结构化命题种类（本轮只有 repository_path_exists）
verification_status supported / refuted / insufficient_evidence
review_status       pending_review / approved —— approved 只能人产生
knowledge_freshness 只留字段，不做推断
execution_status    属于运行时，不进知识裁决
```

`Claim.__post_init__` 硬性拦截：`review_status=approved` 必须同时 `human_authored=True`，
所以 AI 在构造时就不可能自批。

---

## 3. 三态裁决的实际规则

**输入**：claim + fact_id 列表 + 规则版本。

**前置校验（任何一条失败 → insufficient，且带具体 reason_code）：**

| 校验 | reason_code |
|---|---|
| 无事实 | `NO_FACTS` |
| fact 不存在 | `FACT_NOT_FOUND` |
| fact 内容哈希复算不符 | `FACT_INTEGRITY_FAILED` |
| 来源快照缺失/身份不符 | `SNAPSHOT_NOT_FOUND` / `SNAPSHOT_INTEGRITY_FAILED` |
| 仓库不一致 | `REPOSITORY_MISMATCH` |
| Commit 不一致 | `COMMIT_MISMATCH` |
| 路径不一致 | `PATH_MISMATCH` |
| 事实本身是 UNKNOWN | `FACT_IS_UNKNOWN` |
| 不支持命题类型 | `UNSUPPORTED_CLAIM_TYPE` |
| 存储层错误 | `STORAGE_ERROR`（**并保留 storage_error 字段**） |

**结论规则：**

| 观察 | 命题 | 结论 |
|---|---|---|
| PRESENT（任意完整性） | 存在 | **supported** |
| PRESENT | 不存在 | **refuted** |
| ABSENT + COMPLETE | 不存在 | **supported** |
| ABSENT + COMPLETE | 存在 | **refuted** |
| ABSENT + 非 COMPLETE | 任意 | **insufficient** |

**冲突**：同范围同时出现 support 与 counter → `insufficient` + `CONFLICTING_EVIDENCE` +
`conflict_detected=true` + `conflict_fact_ids`。
**不得多数票，不得取最新。**

---

## 4. PARTIAL 的细粒度处理

| 情形 | 处理 |
|---|---|
| PARTIAL + 观察到存在 | 可 supported，但 `local_coverage_only=true` |
| PARTIAL + 未观察到 | `insufficient`（`PARTIAL_EVIDENCE_INSUFFICIENT`），**既不能否证存在，也不能支持不存在** |
| COMPLETE + 范围不覆盖 | 即使 COMPLETE 也不能用于不存在判定 |

关键：Facts 侧 PARTIAL 未命中产出的 UNKNOWN **根本不入库**，
所以它连"证据"都不是 —— 这条性质直接消灭了"拿 UNKNOWN 冒充否证"的可能。

---

## 5. 证据回查的 10 项校验

`evidence_resolver.resolve_fact()` 依次校验：
存在性 → 资产类型 → 必需字段 → **内容哈希独立复算** → 来源快照存在性 →
快照身份一致性。仓储/Commit/路径一致性在 verifier 里校验。
**证据对象存在 ≠ 证据足以支持结论** —— 后者由三态规则判定，不由存在性判定。

---

## 6. 持久化

- 资产类型 `claim_candidate` / `claim_verification`（已登记进 Storage `ASSET_TYPES`）
- `logical_identity` = claim_id / verification_id
- 只经 `append_asset_and_advance()`，**不建第二套库**
- 幂等：同 identity 同内容 → `IDEMPOTENT_ALREADY_PRESENT`
- 内容变（如 review_status 变）→ 新版本，历史保留
- **CAS**：调用方给 `expected_version` 就必须校验（本批实测发现初版把它忽略了）

---

## 7. 离线 Gold（SL-CAP-0075）

14 条手工 gold（`tests/evidence_claims/gold/gold_cases.json`），三条状态全覆盖：
supported 3 / refuted 2 / insufficient 9。

**高风险门禁**（`evaluation.score`）：
- `INSUFFICIENT_JUDGED_SUPPORTED` → BLOCKER
- `MISSING_JUDGED_REFUTED` → BLOCKER

有 blocker 即 `gate=BLOCKED`。**不靠 accuracy 宣布合格。**

---

## 8. 明确不做

- 自然语言语义命题（"项目安全"/"成熟"/"功能正确"）
- LLM 参与证据或判分
- 完整 Research / Renderer / 正式 Skill
- 人工审批界面（只留数据契约）
- Lifecycle（F2-P3）
