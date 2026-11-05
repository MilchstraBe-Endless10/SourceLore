# F2-P4B · 确定性研究检索与研究包契约

产物：`F2_P4B_RESEARCH_CANONICAL_AUDIT.json`、`F2_P4B_RETRIEVAL_CAPABILITY_AUDIT.json`、
`F2_P4B_E2E_REPLAY.json`、`F2_P4B_GOLD_EVALUATION.json`、`F2_P4B_VERIFICATION.json`
回放：`docs/preview/f2p4b/`

**结论：`DETERMINISTIC_RESEARCH_CORE = DONE`。
`LLM_RESEARCH_SYNTHESIS` / `AUTONOMOUS_RESEARCH_AGENT` / `REAL_HARNESS_AUTHORIZED_E2E`
均未实现、未声称；`DISTRIBUTION_READY` 保持 `NOT_READY`。**

---

## 1. 权威边界

**Research 做**：结构化检索已登记知识、消费只读 ViewAssembler、整理证据引用、
标记覆盖范围、评估可回答性、保留多版本历史、构建结构化研究包。

**Research 不做**：改 Claim/Verification、把 insufficient 变 supported、
把缺失证据变 refuted、从仓库名推断能力、抓 GitHub、执行仓库脚本、
改 review/freshness、造新 Fact、发布为知识权威、绕过 Storage 改表、用 LLM 补造证据。

**Research Packet 是研究材料，不是新的 Claim 裁决状态机。**

---

## 2. Canonical 对应（从冻结 Crosswalk 实数提取）

`owner_module == "Research"` 共 5 条：

| ID | 名称 | 本批落地情况 |
|---|---|---|
| SL-CAP-0035 | 有界研究阶段流水线 R0–R4 | 只落地 R1「内读」语义：只消费已有确定性产物，不发起采集 |
| SL-CAP-0036 | 由广到窄查询策略与来源去重 | **缺口**：假定外部采集，本批禁止抓取 → 只实现本地结构化检索 |
| SL-CAP-0037 | 来源类型标记与覆盖记录 | 已实现；遵守其 f1c 反例：优先级**不得**用于判定真伪 |
| SL-CAP-0038 | 研究质量状态与结论边界 | 已实现；copy_permitted=false，独立实现不复述原文 |
| SL-CAP-0039 | 内联引用约束与可追溯性 | 已实现；无引用不得进可采信集合 |

三条硬约束直接来自 canonical 的 `f1c_amendments`：

1. 来源优先级只用于**取数次序**，不得判定 claim 真伪（SL-CAP-0037）
2. 冲突只做**分辨与分流**，不得另建状态机（SL-CAP-0038）
3. 每条实质陈述必须**内联引用** Evidence-Claims ID（SL-CAP-0039）

---

## 3. 检索能力（实测，不假定）

`index_rows` 列：`asset_id, asset_type, logical_identity, repository_id,
subject_id, commit_sha, asset_version`。

| 能力 | 状态 |
|---|---|
| 按 repository_id | 可用（索引级） |
| 按 subject_id / commit_sha | 可用（索引级，部分资产为空） |
| 按 asset_type | 可用 |
| 按 claim_type / verification_status | **需读 payload 后过滤**（无索引列） |
| 历史版本 | 可用（`history`） |
| **全文检索（FTS5）** | **不可用** —— `index_rows` 无 text/body 列 |
| **语义检索** | **不可用，且未声称** |

因此 Research 的检索是：**元数据过滤得候选集 → 读 payload 做结构化过滤**。
SQL 固定常量模板 + 参数绑定，不接受任何外部拼接。

---

## 4. Query Schema

```
query_id             = "SL-Q-" + H(规范化字段, sort_keys)[:32]
query_schema_version = research-query/1
query_rule_version   = query-rule/1
```

字段：`question_type / repository_id / subject_id / commit_sha /
compare_commit_sha / requested_ref / path / claim_type /
verification_status / retrieval_scope / max_results / evidence_policy /
provenance_policy / canonical_refs`。

三类问题：

| 类型 | 语义 | canonical |
|---|---|---|
| `PATH_EXISTENCE` | Q-A 路径命题 | SL-CAP-0039 |
| `KNOWN_CLAIMS` | Q-B 已验证知识检索 | SL-CAP-0037/0039 |
| `VERSION_COMPARE` | Q-C 历史版本对照 | SL-CAP-0037/0038 |

**规范化拒绝**：未知类型、缺 repository_id、缺/非法 Commit、
绝对路径、`..`、`javascript:`/`data:`/`file:`/`vbscript:`、
HTML 尖括号、SQL 语句、`$( )`、反引号、`&&`/`||`。

**自然语言只走三个固定模板**；匹配失败直接抛错，不猜语义。

---

## 5. Research Packet

必含字段（有测试逐项断言）：

```
research_id / research_schema_version / query_id / query / canonical_refs /
selected_view_ids / claim_refs / verification_refs / fact_refs /
evidence_refs / source_snapshot_refs / findings / excluded_candidates /
untrusted_findings / coverage_assessment / unresolved_questions /
limitations / conflicts / provenance_summary / review_summary /
freshness_summary / distribution_restrictions / retrieval /
packet_status / llm_used / external_network_used /
is_claim_authority / publishable_as_knowledge / content_digest
```

每个 finding 可定位到：`claim_id / verification_id / claim_commit_sha /
evidence_refs / fact_refs / verdict_status / review_status / limitations /
source_view_refs`。

**没有可定位证据的 finding 不进 `findings`，只进 `untrusted_findings`**，
且带 `reason=NO_LOCATABLE_EVIDENCE`。

---

## 6. 可回答性状态（与 EC 裁决正交）

| 状态 | 含义 |
|---|---|
| `ANSWERABLE_FROM_EXISTING_EVIDENCE` | 足以回答 |
| `PARTIALLY_ANSWERABLE` | 只覆盖一部分 / 证据链不完整 |
| `INSUFFICIENT_EVIDENCE` | 不足以回答（缺口已列） |
| `CONFLICT_REQUIRES_REVIEW` | 冲突需人工复核（Research 不裁决） |
| `RETRIEVAL_ERROR` | 检索本身失败 |

五个必须区分的情形（`coverage_assessment.distinction`）：

```
A_no_knowledge      查询没找到知识        → INSUFFICIENT_EVIDENCE
B_found_insufficient 找到 insufficient    → INSUFFICIENT_EVIDENCE
C_found_refuted      找到有效 refuted     → ANSWERABLE（结论限定该 Commit）
D_retrieval_failed   索引/资产损坏        → RETRIEVAL_ERROR
E_version_diff       不同 Commit 历史差异 → PARTIALLY_ANSWERABLE
```

**A ≠ C；B ≠ D；E 不等于证据冲突。**

---

## 7. 证据链完整性（本批发现的真缺陷）

原始实现只信 EC 的 `local_coverage_only` 标记。
实测发现两条漏判通路：

1. **快照真实完整性没被读取** —— `repository_snapshot` 的 `completeness_status=PARTIAL`
   存在，但 EC 在 insufficient 路径下不设 `local_coverage_only`。
   现在同时读 Storage 侧真实快照完整性，PARTIAL 一律带出"仅局部覆盖"限制。
2. **快照索引消失时仍声称"完全可答"** —— 现在若快照完整性无法确认
   （索引缺失 / 状态 UNKNOWN），coverage 降级为 `PARTIALLY_ANSWERABLE`
   并加 `EVIDENCE_CHAIN_UNVERIFIABLE` gap。**不改 EC 裁决，只收窄研究适用范围。**

另外，悬空引用（`index_rows` 指向不存在的 asset）原来被报成
"没有已登记 Claim"，现已区分成 `RETRIEVAL_ERROR` + `EVIDENCE_CORRUPT`。

---

## 8. 确定性

```
research_id       = "SL-R-" + H(query_id, sorted(finding_ids),
                                packet_schema, retrieval_rule)[:32]
content_digest    = H(packet 去掉 content_digest/assembled_at/elapsed_ms/
                      run_diagnostics, sort_keys)
```

- 同输入同 `research_id` 与同 `content_digest`
- 诊断元数据（`run_diagnostics`）不参与摘要
- 排序：范围匹配 → 仓库 → Commit → 类型 → 审核 → 稳定 ID
- 预算：`max_results ≤ 200`（硬上限），`evidence_refs ≤ 50`；
  截断必须显式标记，**未出现 ≠ 不存在**

---

## 9. 与 Renderer 的关系

输入权威是 `KnowledgeView`；`rendered_card.json` 只作辅助展示，
**禁止**解析 HTML 恢复 Claim/Evidence。

研究包可交给现有 Renderer 做内部预览，**复用 P4A 的 `safe_html` 与 CSP**，
不另造第二套拼接。预览不改变研究含义（内容摘要前后一致，有测试）。

---

## 10. 明确不做

不调 LLM、不联网 GitHub、不创建 Research 权威数据库、
不做 Agent 自主研究循环、不自动发布、不改 B-1/B-2/B-3 状态。
