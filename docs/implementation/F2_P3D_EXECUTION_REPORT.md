# F2-P3D · 执行报告

产物：`F2_P3D_VERIFICATION.json`（24/24）、`F2_P3D_E2E_REPLAY.json`、
`F2_P3D_VIEW_CONTRACT.md`、`F2_P3D_GATE_RESULTS.json`、`F2_STATS_AUDIT.json`

**结论：`READ_ONLY_VIEW_ASSEMBLY = DONE`。**
**`RENDERER` / `RESEARCH` / `REAL_HARNESS_AUTHORIZED_E2E` / `DISTRIBUTION_READY` 全部未达，且未声称。**

---

## 1. 实际 Schema

```
view_id, view_schema_version(knowledge-view/1), projection_rule_version(projection/1),
query_scope, status
repository_id, subject_id
claim_id, claim_type, claim_commit_sha, claim_payload
verification_id, verification_status, verification_rule_version,
verification_evidence_level
applicability_scope, freshness_state, watch_id, requested_ref,
observed_commit_sha, baseline_commit_sha, last_observed_at,
freshness_reason_code, source_evidence_conflict, current_applicability
review_status, human_authored
execution_run_ref, execution_status, execution_stages
provenance_level, provenance_basis, evidence_source_level,
execution_source_level, snapshot_source_level, snapshot_source_provider,
mixed_provenance
authorization_class, authorization_kind, authorization_is_test_only
evidence_refs, source_snapshot_refs, fact_refs
local_coverage_only, coverage_scope, no_usable_evidence
limitations, conflict_indicators, history_refs, distribution_restrictions
```

---

## 2. 五条状态轴如何独立表示

| 轴 | 字段 | 实测值（端到端回放） |
|---|---|---|
| A. 证据裁决 | `verification_status` | `refuted` |
| B. 新鲜度 | `freshness_state` / `current_applicability` | `None` / `CURRENT_APPLICABILITY_UNKNOWN` |
| C. 人工审核 | `review_status` | `pending_review` |
| D. 执行 | `execution_status` | `SUCCESS` |
| E. 来源+授权 | `provenance_level` / `authorization_class` | `SYNTHETIC_FIXTURE` / `TEST_ONLY_ISOLATED` |

**视图里没有** `is_valid` / `overall_status` / `combined_status` / `final_verdict` /
`effective_status` —— 有测试逐个断言这些字段不存在。

`execution_status=SUCCESS` 与 `verification_status=refuted` 是两个不同字段，
一次执行成功但裁决否定是**合法结果**。

---

## 3. 历史 Claim 与重新验证 Claim 的关联

```
A 视图：claim_commit_sha = aaaa…，verification_status = supported
B 视图：claim_commit_sha = bbbb…，verification_status = refuted
```

两者 `view_id` 不同、互不覆盖。B 视图的 `history_refs`：

```
source_claim_id, source_verification_id, candidate_id,
revalidation_of, relation = revalidated_at_newer_commit
```

**旧 Claim 仍绑 A、`review_status` 仍 `pending_review`**（实测）。
A 上 supported 与 B 上 refuted 是**两个 Commit 下各自成立的结论**，
视图结构上不提供跨版本合并，所以不可能被误读成"证据自相矛盾"。

---

## 4. 当前 Ref 视图的来源证据等级

`current_applicability` 的取值集合里**没有 `CURRENT_VALID`**：

```
ALIGNED_AT_OBSERVATION_TIME_ONLY   VERSION_ALIGNED 只是观测时刻的结论
STALE_AT_OBSERVATION_TIME          POSSIBLY_STALE
PINNED_COMMIT_IMMUTABLE
SYNTHETIC_ONLY                     来源是合成
CURRENT_APPLICABILITY_UNKNOWN      证据不足
```

端到端回放里 B 视图的取值是 `CURRENT_APPLICABILITY_UNKNOWN` ——
因为 B 的裁决对应的是重新验证执行，而**没有对应的新鲜度评估**。
这种情况**如实报未知**，不拿 A 的评估冒充 B 的，也不用客户端时间猜 Ref 状态。

---

## 5. PARTIAL / UNKNOWN / 损坏来源如何呈现

| 情形 | 呈现 |
|---|---|
| 完整快照 + 存在 | `supported` |
| 完整快照 + 不存在 | `refuted` |
| PARTIAL + 未覆盖目标 | `insufficient_evidence`，`local_coverage_only=true`，`coverage_scope=PARTIAL`，limitations 写明"未覆盖部分不得判为不存在" |
| 无可用证据 | `insufficient_evidence` + `no_usable_evidence=true` |
| 证据链损坏 | 装配失败，返回 `EVIDENCE_CORRUPT`（不返回半成品视图） |
| 快照缺失 | `SOURCE_MISSING` / `DANGLING_REFERENCE` |

**关键修正**：`insufficient_evidence` 的 `fact_ids` 里是 `[None]` ——
这是"本次裁决没有可用证据"的正常形态，**不是**悬空引用。
初版把它误报成 `EVIDENCE_CORRUPT`，导致合法裁决无法装配。已修，并有用例固化。

---

## 6. TEST_ONLY 与真实来源的隔离结果

| 维度 | 实测 |
|---|---|
| 授权类别 | `TEST_ONLY_ISOLATED`（不是 `VERIFIABLE_PRODUCTION`） |
| `authorization_kind` | `TEST_ONLY` |
| `authorization_is_test_only` | `true` |
| 执行来源 | `execution_source_level = SYNTHETIC_FIXTURE` |
| 综合来源 | `provenance_level = SYNTHETIC_FIXTURE` |

**来源与授权分别判断**：真实历史数据不因"用了测试授权"被标成合成；
合成来源也不因"掺了真实历史基线"被标成真实。
多层不一致时取**最弱**并置 `mixed_provenance=true`。
无法判定时 `provenance_level=None` + `basis=["undetermined"]`，**不猜**。

**如实记录的工程事实**：快照 payload **不含 `provenance_level`**（只有 `source_provider`）。
来源等级存在于观测记录与执行记录。视图不给快照凭空编一个等级 ——
这条由 `test_snapshot_has_no_provenance_field_acknowledged` 固化。

---

## 7. 只读性实测与资产指纹对比

| 检查 | 结果 |
|---|---|
| A 层资产指纹 | **完全不变**（16 个资产，装配前后逐条比对 content_hash 与 version） |
| B 层指针版本 | **不变**（含 pointer_version 与 last_known_good） |
| C 层索引 | **不变**（行数与整体摘要一致） |
| `operation_log` | **不变**（operation_id / result_hash / pointer_version 全等） |
| Collector 调用 | **零**（装配前后调用列表完全相同） |
| 重复装配 3 次 | 资产数不变 |

**负向对照**（关键）：测试里主动写一条资产，断言指纹**确实发生变化** ——
证明上面的"不变"不是空转（避免"没有输入却断言结果不变"的假通过）。

---

## 8. view_id 的确定性与版本隔离

```
view_id = SL-VIEW- + H(query_scope, subject_id, sorted(source_asset_refs),
                       sorted(content_digests), schema_version,
                       projection_rule_version)[:32]
```

| 性质 | 实测 |
|---|---|
| 相同输入 → 相同身份 | ✓（重复装配同 id） |
| 输入顺序变化 → 身份不变 | ✓ |
| 时间戳不参与 | ✓（无 `assembled_at` 参与哈希） |
| 不同 Claim/Commit 不碰撞 | ✓（A 与 B 的 view_id 不同） |
| 缺失/损坏资产 | 不静默回退成旧视图，返回诊断码 |

---

## 9. P3C 三项缺陷的核查结果

### A. `plan_digest`

现有实现**已改为重算比对**（`actual_digest = plan_digest_of(plan)`）。
T-36 构造"同时篡改计划内容与其自带摘要"：授权绑定原始摘要、计划被替换成
新内容+新摘要 —— 仍被拒绝（`PLAN_DIGEST_MISMATCH`）。**修复有效。**

### B. Tree Entry SHA

T-37 用 `sha="zzz"` 的损坏条目执行：`execution_status=FAILED`，
`verification_status` 不可能是 supported/refuted。**修复有效。**

### C. `auth_ref`

实测 run/result payload 里：

- 只存 `auth_ref` = `SL-TESTAUTH-<24 hex>`（稳定标识符）
- 键名逐一扫描禁词（api_key/token/cookie/secret/password/credential/private_key/authorization/proof）
- **无任何命中**

`authorization_id` 仅出现在 `make_run_id` 的哈希载荷里，不进 payload。
**这不是"改名绕过"**：字段改名 `auth_ref` 是因为 Storage 的 `FORBIDDEN_FIELDS`
含子串 `authorization`，该护栏**未被削弱**（`FORBIDDEN_FIELDS` 一字未改）。

### D. 本批新发现的 P3C 缺陷（§1-13）

`revalidation_run_store` 把 run 记录、8 阶段、结果登记全实现了，**但执行器从未调用它** ——
执行状态完全不可追溯。按 §1 授权做最小向后兼容修复：

- PREFLIGHT 读到候选后 `create_run`（候选可执行时才建）
- 目标 Claim 建立后回写 `target_claim_id` / `expected_target_claim_identity` / `source_level`
- 完成时回写 `target_verification_id` / `verification_status` /
  `execution_status` / `auth_kind` / `test_only` / `auth_ref` /
  `execution_source_level` / `evidence_source_level` / `source_snapshot_completeness`
- 所有失败出口经 `_persist_end` 落真实状态（不伪造成功）

**P3C 142 项回归全绿**，说明修复未破坏原有行为。

---

## 10. P3B/P3C 专项断言统计核对

| 项 | 报告写 | 列表算术和 | 实跑 |
|---|---|---|---|
| P3C | **179** | **178** | f2p3c 20/20 通过 |
| P3B | **159** | **158** | f2p3b 22/22 通过 |

**结论：两处都是统计错误（人工加法），不是验证遗漏。**
两个验证器的检查项全部真实存在且通过。权威口径在 `F2_STATS_AUDIT.json`。
历史报告文件**未修改**（它们是当时的记录）。

---

## 11. 工程中发现的验证器假阳性（已修，强度不降）

| 验证器 | 问题 | 修法 |
|---|---|---|
| `f2p3b_verify` c14 / `f2p3a_verify` c9 | 裸子串 `completion` 命中 P3C 新增的 `COMPLETION_CHECK` 阶段名 | 改为只匹配 import 语句与真实 API 端点 |
| `f2p3a_verify` c7 | 裸子串 `APPROVED` 命中 `PLATFORM_APPROVAL`（授权类别名） | 改为只匹配"把状态赋值为 refuted/approved"，并**额外**断言三套状态词表无此二值 |

这些在原批次是通过的，P3C 引入新标识符后才暴露 —— 属于**跨批次回归**，
不是原批次造假。

---

## 12. 新增代码与测试

```
src/views/view_models.py              视图模型 + 五轴 + 诊断码 + view_id
src/views/view_integrity.py           只读完整性校验 + 指纹工具
src/views/knowledge_view_assembler.py 装配器（纯只读）
tests/views/vfx.py                    夹具（真实 SQLite + 真实执行器）
tests/views/test_knowledge_view.py    24 项
tests/views/test_read_only.py          9 项
tests/views/test_multiversion.py       8 项
tests/views/test_provenance.py         9 项
tools/f2p3d_verify.py、tools/f2p3d_e2e_replay.py、tools/f2p3d_stats_audit.py
docs/implementation/F2_P3D_*（4 份）、F2_STATS_AUDIT.json
```

修改：
- `src/lifecycle/revalidation_executor.py` 补 run 落库与关联（§1-13 授权修复）
- `tools/fusion/f1d_verify.py` 白名单登记 `src/views/`、`tests/views/`
- `tools/f2p3a_verify.py`、`tools/f2p3b_verify.py` 精确化两处假阳性检查

---

## 13. 全部测试通过数、失败数及退出码

```
tests/runtime           45 OK   exit 0
tests/storage           53 OK   exit 0
tests/collector         48 OK   exit 0
tests/facts             44 OK   exit 0
tests/evidence_claims   36 OK   exit 0
tests/lifecycle        142 OK   exit 0
tests/views             50 OK   exit 0
f2p3d 24/24  f2p3c 20/20  f2p3b 22/22  f2p3a 18/18
f2p2b 17/17  f2p2a 15/15  f2p1c 22/22  f2p1b 16/16  f2p1a 22/22  f1d 26/26
```

418 项 unittest + 203 项验收断言，失败 0。

---

## 14. F1-D 冻结 SHA-256

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变，f1d_verify **26/26** 通过（含白名单登记后）。

---

## 15. 当前 OPEN 门禁

| 门禁 | 状态 |
|---|---|
| `RENDERER` | **NOT_STARTED** |
| `RESEARCH` | **NOT_STARTED** |
| 正式 Skill 集成 | **NOT_STARTED** |
| `REAL_HARNESS_AUTHORIZED_E2E` | **OPEN**（无真实授权通道） |
| `DISTRIBUTION_READY` | **NOT_READY**（B-1/B-2/B-3 全 OPEN） |
| Y6-P3 审批传递 | **UNVERIFIED** |
| Y6-P6 BotHarness 端到端 | **OPEN** |

---

## 16. 下一阶段建议顺序

1. **Renderer 最小安全契约**（只读消费视图、绝不写权威库、转义与发布前检查），
   而不是直接做 Research —— 因为 Renderer 的安全边界是 §SL-CAP-0055~0061 的硬要求。
2. **Research**（消费视图做推理，但输出不得回写 Claim）。
3. **正式 Skill 集成**（最后，且必须先解决 Y6-P3 授权通道）。
4. **DISTRIBUTION** 只能在 B-1/B-2/B-3 全部关闭后讨论。

**当前阻塞**：真实平台端到端仍需 Y6-P3 + Y6-P6，本轮未联网、无真实授权。
