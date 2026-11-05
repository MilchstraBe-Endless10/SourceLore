# F2-P3D · 只读知识视图契约

产物：`F2_P3D_E2E_REPLAY.json`、`F2_P3D_VERIFICATION.json`、
`F2_P3D_GATE_RESULTS.json`、`F2_STATS_AUDIT.json`、`F2_P3D_EXECUTION_REPORT.md`

**本轮只做只读投影。不是 Renderer，不是发布。**

---

## 1. 职责边界

`KnowledgeViewAssembler` 只做一件事：

> 从已提交的权威资产里读取、验证关联关系、组装结构化视图，并保留全部限制信息。

它**不做**：采集 GitHub、抽 Fact、验 Claim、推新鲜度、改 review、
改指针、重新入队、联网、发布。

**没有第二套 Claim 裁决器。** 数据缺失时返回明确诊断码，不用自然语言补造。

---

## 2. 五条状态轴（结构上分离）

| 轴 | 来源 | 取值 |
|---|---|---|
| A. Evidence Verification | EC | `supported` / `refuted` / `insufficient_evidence` |
| B. Freshness | Lifecycle | `NOT_APPLICABLE_TO_PINNED` / `VERSION_ALIGNED` / `POSSIBLY_STALE` / `UNKNOWN` |
| C. Review | Claim | `pending_review` / `approved`（**只有人能改**） |
| D. Execution | Runtime | `SUCCESS` / `FAILED` / `TIMEOUT` / `CANCELLED` / `UNKNOWN` |
| E. Provenance + Authorization | 观测 / 执行记录 | 来源等级**与**授权类别，分别判断 |

视图里**没有** `is_valid` / `overall_status` / `combined_status` / `final_verdict`。
合并裁决字段是被测试明确禁止的。

---

## 3. 视图 Schema

```
view_id, view_schema_version, projection_rule_version, query_scope, status
repository_id, subject_id
claim_id, claim_type, claim_commit_sha, claim_payload
verification_id, verification_status, verification_rule_version, verification_evidence_level
applicability_scope, freshness_state, watch_id, requested_ref,
observed_commit_sha, baseline_commit_sha, last_observed_at,
freshness_reason_code, source_evidence_conflict, current_applicability
review_status, human_authored
execution_run_ref, execution_status, execution_stages
provenance_level, provenance_basis,
evidence_source_level, execution_source_level,
snapshot_source_level, snapshot_source_provider, mixed_provenance
authorization_class, authorization_kind, authorization_is_test_only
evidence_refs, source_snapshot_refs, fact_refs
local_coverage_only, coverage_scope, no_usable_evidence
limitations, conflict_indicators, history_refs, distribution_restrictions
```

`status` 只有 `OK` 或明确诊断码；**没有"没有知识"这种模糊结果**。

---

## 4. 来源分层（§4 E 的落地）

**来源真实性与授权有效性分别判断**，且来源本身分三层：

```
evidence_source_level   候选/评估观测的来源（决定知识可不可信）
execution_source_level  本次实际取数用的 adapter 来源
snapshot_source_level   快照自身记录的来源（如存在）
provenance_level        以上各层中**最弱**者（保守合成）
mixed_provenance        多层不一致时为 true
```

实测结论：**快照 payload 不含 `provenance_level`**（只有 `source_provider`）。
来源等级存在于观测记录与执行记录，所以视图不凭空给快照编一个等级 ——
这一点由测试 `test_snapshot_has_no_provenance_field_acknowledged` 固化。

---

## 5. 视图身份

```
view_id = SL-VIEW- + H(query_scope, subject_id,
                       sorted(source_asset_refs), sorted(content_digests),
                       view_schema_version, projection_rule_version)[:32]
```

- 顺序无关
- 时间戳不参与
- 不同 Claim / Commit 不碰撞
- 重复装配不写任何资产

---

## 6. 诊断码（明确，不伪装成"没有知识"）

```
VIEW_INTEGRITY_FAILED      资产哈希校验失败
DANGLING_REFERENCE         引用了不存在的资产
SOURCE_MISSING             快照无法定位
VERSION_MISMATCH           Claim / Verification 版本不一致
CLAIM_NOT_FOUND            Claim 不存在
VERIFICATION_NOT_FOUND     Verification 不存在
CLAIM_VERIFICATION_MISMATCH Verification 引用的不是这个 Claim
REPOSITORY_MISMATCH        仓库不一致
COMMIT_MISMATCH            Commit 不一致
EVIDENCE_CORRUPT           证据链损坏（写了 id 却找不到）
CURRENT_APPLICABILITY_UNKNOWN 无法判定当前适用性
PARTIAL_COVERAGE_ONLY      仅局部覆盖
```

**`no_usable_evidence` ≠ `EVIDENCE_CORRUPT`。** 前者是 `insufficient_evidence` 的正常形态
（`fact_ids` 里是 `None`），后者是"写了 id 却找不到"。初版把两者混为一谈，
导致合法的证据不足裁决被误报为损坏 —— 已修，并有用例固化。

---

## 7. 当前 Ref 的严格门禁

`current_applicability` 只可能取：

```
ALIGNED_AT_OBSERVATION_TIME_ONLY   VERSION_ALIGNED 是在观测时刻的结论
STALE_AT_OBSERVATION_TIME          POSSIBLY_STALE
PINNED_COMMIT_IMMUTABLE            PINNED_COMMIT
SYNTHETIC_ONLY                     来源是合成
CURRENT_APPLICABILITY_UNKNOWN      证据不足
```

**没有 `CURRENT_VALID` 这种取值。** 视图结构上无法声称"这是当前 master 的权威结论"。

---

## 8. 版本关系

A→B 的视图互不覆盖：

- A 的 Claim / Verification 仍绑 A，`review_status` 仍 `pending_review`
- B 的 Claim / Verification 独立身份、绑 B
- `history_refs` 记录 `source_claim_id` / `source_verification_id` / `candidate_id`
- `relation = revalidated_at_newer_commit`

A 上 supported、B 上 refuted 是**两个不同 Commit 下各自成立的结论**，
视图不提供跨版本合并，因此不可能被误读成"证据自相矛盾"。

---

## 9. 分发限制（独立结论）

```
distribution_allowed = false        （恒定，与 Claim 裁决无关）
freeze_state = FROZEN_INTERNAL_RESTRICTED
scope = LOCAL_INTERNAL_TEST_ONLY
blockers = B-1 OPEN / B-2 OPEN / B-3 OPEN
```

`supported` 不推导出 `distribution_allowed=true`。
U06 的 `copy_permitted=false` 不被改写成 true。

---

## 10. 明确不做

- 不写回权威数据库
- 不生成 Markdown / HTML / 网页 / 知识卡片
- 不运行外部模板代码
- 不向任何会话发送"已发布"消息
- 不把测试结果提升为生产知识
- 不修改冻结 Crosswalk
