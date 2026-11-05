# F2-P4B · 执行报告

产物：`F2_P4B_RESEARCH_CONTRACT.md`、`F2_P4B_EXECUTION_REPORT.md`、
`F2_P4B_RESEARCH_CANONICAL_AUDIT.json`、`F2_P4B_RETRIEVAL_CAPABILITY_AUDIT.json`、
`F2_P4B_E2E_REPLAY.json`、`F2_P4B_GOLD_EVALUATION.json`、`F2_P4B_VERIFICATION.json`

**结论：`DETERMINISTIC_RESEARCH_CORE = DONE`。
`LLM_RESEARCH_SYNTHESIS` / `AUTONOMOUS_RESEARCH_AGENT` /
`REAL_HARNESS_AUTHORIZED_E2E` 未实现、未标记 DONE；
`DISTRIBUTION_READY` 保持 `NOT_READY`。**

**本轮未调用 LLM、未联网 GitHub、无真实人类授权**（`TEST_ONLY` 为唯一可用授权类别）。

---

## 1. Research 实际 canonical 对应关系

从冻结 Crosswalk 按 `owner_module == "Research"` **实数提取**（5 条，不猜 ID）：

```
SL-CAP-0035  有界研究阶段流水线（R0–R4 状态机 · 预算 · 可恢复）
SL-CAP-0036  由广到窄的查询策略与来源去重
SL-CAP-0037  来源类型标记与覆盖记录（优先级不替代验证）
SL-CAP-0038  研究质量状态与结论边界（三态 + 不产报告的许可）   ← copy_permitted=false
SL-CAP-0039  内联引用约束与可追溯性（校验器执行而非提示词）
```

三条来自 canonical `f1c_amendments` 的硬约束，本批直接落在实现里：

| 约束 | 落点 |
|---|---|
| 来源优先级只用于取数次序，**不得**判定 claim 真伪 | 排序链里没有任何"可信度分数"参与裁决 |
| 冲突只做分辨与分流，**不得**另建状态机 | `conflicts` 只标 `MULTI_COMMIT_DIFFERENCE` / `VERDICT_DIVERGENCE`，不改裁决 |
| 每条实质陈述必须内联引用 | 无 `evidence_refs`/`fact_refs` 的 finding 移出 `findings` |

**缺口如实记录**：SL-CAP-0036 假定外部采集（GitHub 元数据/README/Issue），
本批禁止抓取 → 只实现**本地已登记资产**的结构化检索。
SL-CAP-0035 只落地 R1「内读」语义（只消费已有确定性产物，不发起采集）。

---

## 2. Query Schema 与支持的查询类型

```
query_id = "SL-Q-" + H(规范化字段, sort_keys)[:32]
schema   = research-query/1      rule = query-rule/1
```

三类问题：`PATH_EXISTENCE`（Q-A）/ `KNOWN_CLAIMS`（Q-B）/ `VERSION_COMPARE`（Q-C）。

**自然语言只走三个固定模板**（路径存否 / 已登记 Claim / 两 Commit 对照），
匹配失败直接抛 `UNKNOWN_QUESTION_TYPE`，不猜语义。

规范化拒绝项（有测试逐条固化）：未知类型、缺 repo、缺/非法 Commit、
绝对路径、`..`、`javascript:`/`data:`/`file:`/`vbscript:`、HTML 尖括号、
SQL 语句、`$( )`、反引号、`&&`/`||`、非法 limit、超长文本。

---

## 3. Research Packet 实际结构

必含 24 个字段（逐项断言）。核心结构：

```
research_id / query_id / canonical_refs
claim_refs / verification_refs / fact_refs / evidence_refs / source_snapshot_refs
findings           ← 只含可定位证据者
untrusted_findings ← 无证据被剔除者，带 reason
excluded_candidates
coverage_assessment（含 distinction / gaps / snapshot_completeness）
limitations / conflicts / provenance_summary / review_summary / freshness_summary
distribution_restrictions
packet_status / llm_used / external_network_used
is_claim_authority=false / publishable_as_knowledge=false / content_digest
```

每个 finding 可定位：`claim_id / verification_id / claim_commit_sha /
evidence_refs / fact_refs / verdict_status / review_status / limitations /
source_view_refs`。

---

## 4. KnowledgeView 检索路径与限制

**实测 `index_rows` 列**：`asset_id, asset_type, logical_identity,
repository_id, subject_id, commit_sha, asset_version`。

| 能力 | 实测结果 |
|---|---|
| repository_id / asset_type | 索引级可用 |
| subject_id / commit_sha | 索引级可用（部分资产为空） |
| claim_type / verification_status | **须读 payload 后过滤**，无索引列 |
| 历史版本 | 可用 |
| **FTS5 全文检索** | **不可用 —— 无 text/body 列** |
| **语义检索** | **不可用，且未声称** |

因此检索路径固定为：**元数据过滤 → 读 payload 结构化过滤 → 确定性排序**。

---

## 5. Evidence 筛选与引用绑定

- 可定位证据 = Verification 的 `evidence_refs`（规范化 JSON）或非空 `fact_ids`
- 无可定位证据 → 不进 `findings`，进 `untrusted_findings`（`NO_LOCATABLE_EVIDENCE`）
- `evidence_refs ≤ 50`，`fact_refs ≤ 50`（预算硬上限）
- 每个 finding 的 `source_view_refs` 记录 `claim:<asset_id>` 与 `verification:<asset_id>`

---

## 6. 可回答性状态实测

```
s1_complete          q_path=ANSWERABLE  q_claims=ANSWERABLE  q_version=PARTIALLY
s2_partial           q_path=INSUFFICIENT q_claims=INSUFFICIENT q_version=PARTIALLY
s3_no_snapshot_index q_path=PARTIALLY   q_claims=PARTIALLY   q_version=PARTIALLY
```

五个必须区分的情形已分：

```
A_no_knowledge       没找到知识     → INSUFFICIENT_EVIDENCE
B_found_insufficient 找到 insufficient → INSUFFICIENT_EVIDENCE
C_found_refuted      找到 refuted   → ANSWERABLE（限定该 Commit）
D_retrieval_failed   通路受损       → RETRIEVAL_ERROR
E_version_diff       多 Commit 差异 → PARTIALLY_ANSWERABLE
```

`s3` 场景正是 D 类：快照索引被删除后，旧实现报"完全可答 + 无任何提示"，
现降级为 `PARTIALLY_ANSWERABLE` + `EVIDENCE_CHAIN_UNVERIFIABLE`。

---

## 7. 不同仓库、Commit 与多版本对照

| 检查 | 结果 |
|---|---|
| 错误 repository_id | 检索为空，`INSUFFICIENT_EVIDENCE`，不返回别仓库 Claim |
| 错误 Commit | `COMMIT_NOT_MATCH` 进 `excluded_candidates`，不返回别的 Commit 数据 |
| 两 Commit 对照 | 两个 Commit 并存，`PARTIALLY_ANSWERABLE` |
| 冲突判定 | 标 `MULTI_COMMIT_DIFFERENCE` / `VERDICT_DIVERGENCE_ACROSS_COMMITS`，**显式否定**"同一事实冲突"与祖先推断 |

---

## 8. 来源、审核与分发限制继承

原样保留：`provenance_level`（不做升级）、`mixed_provenance=false`、
`review_status`（不改）、`freshness_state`（不重评估）、
`limitations`（逐条带出）、`distribution_restrictions`。

研究包固定：`is_claim_authority=false`、`publishable_as_knowledge=false`。

分发门禁：`preview_allowed=True`、`distribution_allowed=False`、
`publish_blocked=True`；B-1/B-2/B-3 全部保持 OPEN。

---

## 9. 只读性与资产指纹对比

| 检查 | 结果 |
|---|---|
| A 层资产指纹 | 不变 |
| B 层指针 | 不变 |
| C 层索引 | 不变 |
| `operation_log` | 不变 |
| Checkpoint（run 数） | 不变 |
| 原始 Claim/Verification 内容哈希 | 不变 |

**负向对照**：主动写一条资产后断言指纹确实变化，证明"不变"非空转。

---

## 10. 确定性研究包哈希

```
research_id    = "SL-R-" + H(query_id, sorted(finding_ids), schema, rule)[:32]
content_digest = H(packet 去掉 content_digest/assembled_at/elapsed_ms/
                   run_diagnostics, sort_keys)
```

实测：重复运行 `research_id` 与 `content_digest` 均相同；
`include_diagnostics=True` 不改 `content_digest`；查询字段顺序无关；
A/B 两个 Commit 不碰撞。

---

## 11. 离线 Gold 数量、错误指标与阻断状态

**Gold 20 项，人工定义，不由 Research 输出反推**：

```
G01 supported      G02 refuted       G03 insufficient   G04 no_claim
G05 partial        G06 wrong_commit  G07 wrong_repo     G08 version_compare
G09 conflict       G10 test_only     G11 mixed_prov     G12 applicability
G13 missing_snapshot G14 corrupt_evidence G15 index_missing G16 truncated
G17 injection      G18 order         G19 duplicate      G20 pending_review
```

```
gold_count                20
query_success_rate        1.0
false_positive_count      0        ← 阻断级
false_negative_count      0        ← 阻断级
correct_abstention        6
wrong_abstention          0
limitation_retention_rate 1.0
blocked                   false
```

**Gold 含真实负例**（G04/G06/G07/G13/G14/G15 要求 abstention），
并有两类阻断指标（错误肯定 / 错误否定）。

---

## 12. P4A 两项回归核验结论

**A. `assembled_at`**
来源于**显式参数**，默认空串 —— 代码里没有任何 `now()` 进入 `card_id`。
因此"逐字节确定性"的实际条件是**不传 `assembled_at`**；
传入时差异只出现在页脚且带"诊断用，不参与确定性身份"字样（有测试断言行级差异）。
`safe_html` 侧无隐式时间。

**B. `preview_allowed`**
完整性失败仍只给"无法生成可信知识卡片"诊断页，不呈现裁决徽章；
装配失败显式 `ok=False` 并走阻断路径；
`preview_allowed=True` 与 `distribution_allowed=False` 始终分离，
`statement` 明确写"预览许可不等于分发许可"。

---

## 13. P3C 八阶段追踪回归

`revalidation_run` 真实记录：8 阶段、各自 `RUNNING`/`COMMITTED` 状态、
成功尾部标 `COMPLETED`、失败出口标 `FAILED_FATAL` 并带 `error_code`。
失败运行**不会**全 `COMMITTED`；且 `execution_status=SUCCESS` **不等于**
`verification_status=supported`（两者在包里是不同字段）。

**回归中发现的定位陷阱**：`revalidation_run` 的 `asset_version` 是
**每个 run 自己从 1 开始的版本号**，`ORDER BY asset_version DESC`
取到的不是"最新一次运行" —— 必须按 `rowid` 定位。

---

## 14. 新增代码与测试

```
src/research/{__init__,query_models,retriever,evidence_selector,
              coverage_evaluator,research_packet,research_engine}.py
tests/research/{__init__,rfx,test_queries(21),test_retrieval(15),
                test_evidence(13),test_research_packet(12),
                test_read_only(12),test_security(9),
                test_p4a_regression(12)}.py
tests/research/gold/{gold_queries,evaluate}.py
tools/{f2p4b_verify,f2p4b_e2e_replay}.py
docs/preview/f2p4b/{s1_complete,s2_partial,s3_no_snapshot_index}/
docs/implementation/F2_P4B_*（6 份）
```

---

## 15. 全部测试数量、失败数与退出码

```
tests/runtime           45 OK   exit 0
tests/storage           53 OK   exit 0
tests/collector         48 OK   exit 0
tests/facts             44 OK   exit 0
tests/evidence_claims   36 OK   exit 0
tests/lifecycle        142 OK   exit 0
tests/views             50 OK   exit 0
tests/renderer          59 OK   exit 0
tests/research          94 OK   exit 0
```

合计 **572** 项，失败 0。

---

## 16. F1-D 冻结 SHA-256

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变（只读）。

---

## 17. 当前 OPEN 门禁

| 门禁 | 状态 |
|---|---|
| `DISTRIBUTION_READY` | **NOT_READY**（B-1/B-2/B-3 全 OPEN） |
| `LLM_RESEARCH_SYNTHESIS` | **NOT_STARTED**（未标记 DONE） |
| `AUTONOMOUS_RESEARCH_AGENT` | **NOT_STARTED**（未标记 DONE） |
| `REAL_HARNESS_AUTHORIZED_E2E` | **OPEN**（Y6-P3 UNVERIFIED、Y6-P6 OPEN） |
| `FULL_RENDERER` | **NOT_STARTED** |
| 正式 Skill 集成 | **NOT_STARTED** |

---

## 18. 下一批最小可执行起点

建议 **LLM 研究综合（受限）**，但必须先满足：

1. **输入仍只来自 Research Packet**，不直连数据库，不重跑 EC
2. LLM 输出只能是**候选叙述**，逐句必须绑定 `finding_id`；
   无绑定的句子一律降级为 `INFERENCE`，不得以肯定语气出现
3. **禁止把 insufficient 写成否定、禁止把 refuted 写成"该软件不存在"**
4. 必须在产物里原样带出 `limitations` 与 `distribution_restrictions`
5. 必须复用 P4A `safe_html`，不得新造拼接
6. 必测：句级引用覆盖率、越界断言检出率、注入文本不执行、分发恒 False
7. Gold 集扩展：加入"LLM 越界叙述"负例，错误肯定仍是阻断级
