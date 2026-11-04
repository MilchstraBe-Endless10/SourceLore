# F2-P2B · 执行报告

产物：`F2_P2B_VERIFICATION.json`（17/17）、`F2_P2B_E2E_REPLAY.json`、
`F2_P2B_PRECONDITION_AUDIT.json`、`F2_P2B_GATE_RESULTS.json`、`F2_P2B_EC_ARCHITECTURE.md`

**结论先行：确定性证据裁决闭环 DONE。三态都有真实执行证据，无证据不产生默认结论。**

---

## 1. 两项前置核验（题面第 1 节）

### A. P2A 的 manifest_version=2 依据 —— **证据不足**

查 P1C 保存的实际记录，`tree` 字段只有：

```
completeness_status / entry_count=1 / truncated_seen / deep_walk_used
tree_query_refs / sample_paths=["README"]
```

**没有完整 tree_entries 原始响应。** P2A 回放脚本的 `ents` 是用 `rec["blob"]` 手工构造的单条，
属于题面点名的"人工补录"。

分级结论：

| 结论 | 依据 | 级别 |
|---|---|---|
| README 存在 | 真实 blob 经真实 API 读取并通过 Git 对象 sha1 校验 | **可用** |
| package.json 不存在 | 单条人工补录清单，不能证明完整覆盖 | **证据不足** |

**本批据此执行**：package.json 不存在命题 **abstain**，不判 supported。
合成夹具仅用于测试不存在判定，且带 `synthetic_provenance` 标记，不冒充真实。

### B. 46 vs 45 的差异 —— 口径不同 + 新增 2 条，**无删除**

实测：

```
P1C (a15e47d)：test_github_client 43 + test_crash_recovery 3 = 46（目录级 discover）
当前 (9d97c74)：test_github_client 45 + test_crash_recovery 3 = 48
```

P2A 报告里的 45 是**单文件** `-p test_github_client.py` 的结果，P1C 的 46 是**整个目录**的结果 ——
口径不同，不是删除。逐项 diff 确认 **只有新增，无删除**：

- `test_default_retry_after_cap_is_120`
- `test_retry_after_uses_default_cap_when_not_overridden`

**退避测试能否捕获假通过**：能。修复后 `install_fake` 不再覆盖 `_sleep`，
两处测试改为之后设置并加 `assertTrue(slept)` —— 空列表会直接失败，不再依赖 `all([])` 永真。

---

## 2. 支持的 Claim 类型

**只有 `repository_path_exists`。**

`expected_exists=true` = "该 Commit 该路径存在对应对象"；
`false` = "在已完整覆盖范围内该路径不存在"。

不支持的命题（如"项目成熟"）显式返回 `UNSUPPORTED_CLAIM_TYPE`。
实现方式：`Claim.__post_init__` 拒绝非白名单类型，`verify_path_claim` 再兜一层。

---

## 3. claim_id / verification_id 生成规则

```
claim_id        = SL-CLAIM- + H(repo, commit, claim_type, 规范化参数, schema_version)[:40]
verification_id = SL-VERIF- + H(claim_id, sorted(fact_ids), sorted(content_hashes),
                                rule_version, 验证参数)[:40]
```

实测性质：

| 场景 | 结果 |
|---|---|
| `README` vs `README/` | 同 claim_id（规范化后同命题） ✓ |
| 换证据 | claim_id 不变 ✓ |
| 事实顺序颠倒 | verification_id 不变 ✓ |
| 同一事实传两次 | fact_ids 去重，身份不变 ✓ |
| `rule_version` 变化 | verification_id 变，历史保留 ✓ |
| 时间戳 | **不参与任何身份** ✓ |

---

## 4. 三态裁决实际行为

| 场景 | 实际 |
|---|---|
| COMPLETE + PRESENT，命题"存在" | **supported** |
| COMPLETE + ABSENT，命题"不存在" | **supported** |
| PRESENT，命题"不存在" | **refuted** |
| COMPLETE + ABSENT，命题"存在" | **refuted** |
| 无任何 fact | **insufficient / `NO_FACTS`** |
| 事实属于别的 Commit | **insufficient / `COMMIT_MISMATCH`** |
| 事实属于别的仓库 | **insufficient / `REPOSITORY_MISMATCH`** |
| 事实路径不符 | **insufficient / `PATH_MISMATCH`** |
| 事实内容哈希被篡改 | **insufficient / `FACT_INTEGRITY_FAILED`** |
| 引用不存在的 fact | **insufficient / `FACT_NOT_FOUND`** |
| 同范围矛盾 | **insufficient / `CONFLICTING_EVIDENCE`** |
| 不支持命题类型 | **insufficient / `UNSUPPORTED_CLAIM_TYPE`** |

**没有任何一条路径会默认 supported 或 refuted。**

---

## 5. PARTIAL 证据处理

| 情形 | 实际 |
|---|---|
| PARTIAL + 观察到存在 | **supported**，且 `local_coverage_only=true` |
| PARTIAL + 未观察到 | Facts 侧产 UNKNOWN → **不入库** → 裁决为 `FACT_NOT_FOUND`/insufficient |

关键性质：**PARTIAL 未命中在 Facts 层就变成了 UNKNOWN 且被拒绝入库**，
所以它在 EC 层连"证据"都不存在 —— 从根上消灭了"用 UNKNOWN 当否证"的可能。
这比在 EC 层拦截更早、更彻底。

---

## 6. 证据引用回查

`resolve_fact()` 实际做了 6 项本地校验（存在性/类型/必需字段/**内容哈希独立复算**/来源快照/身份一致），
verifier 再做 3 项归属校验（仓库/Commit/路径）与 1 项 UNKNOWN 排除。

**内容哈希复算**是与 Facts 侧同一算法独立跑一遍 —— 这是防篡改的核心。

---

## 7. 冲突与 Commit 隔离

- 同仓库同 Commit 同路径出现 PRESENT 与 ABSENT（只可能来自来源损坏）→
  `insufficient` + `CONFLICTING_EVIDENCE` + `conflict_detected=true` + 两个 conflict_fact_ids。
  **没有多数票，没有取最新。**
- Commit A 存在 / Commit B 不存在 → **两条命题各自 supported**，互不证伪。
  交叉传入 → `COMMIT_MISMATCH`。

关于冲突构造的诚实说明：在当前身份契约下（identity 只由 repo/commit/scope/collector_version 决定），
**两个正常快照不可能产生同 Commit 的真实矛盾** —— 矛盾只可能来自数据损坏。
所以 t12 用受控注入构造该场景，正是为了验证"遇到损坏时不硬裁"。

---

## 8. 持久化、CAS 与幂等

- `claim_candidate` / `claim_verification` 已登记进 Storage `ASSET_TYPES`
- 重复写入 → `IDEMPOTENT_ALREADY_PRESENT`（资产数保持 1）
- 规则版本变 → 两条 verification 都保留（历史不可覆盖）
- 旧版本可 `read_verification` 读回
- 注入写入失败 → A 层无残留
- **本轮发现并修复的真实缺陷**：`ingest_claim` 推进版本时**忽略了调用方给的 `expected_version`**，
  导致错误期望版本也能成功。已加 CAS 校验。

---

## 9. 离线 Gold（SL-CAP-0075）

14 条手工 gold（`gold_cases.json`），预期由人工按规则写定，**不由裁决器生成**。

| 指标 | 值 |
|---|---|
| 总数 | 14 |
| 覆盖状态 | supported 3 / refuted 2 / insufficient 9 |
| 正确 | 14 |
| 错误 supported | 0 |
| 错误 refuted | 0 |
| 正确 abstention | 9 |
| 错误 abstention | 0 |
| 证据引用完整性 | 全部带结构化 refs 的场景均通过 |
| 阻断级错误 | 0 |
| 门禁 | **PASS** |

**混淆矩阵**（每行=人工预期，每列=实际）：

```
                 supported  refuted  insufficient
supported             3        0           0
refuted               0        2           0
insufficient          0        0           9
```

**高风险门禁已实证有效**（变异测试，只在测试内替换，不改源码）：

| 变异 | 结果 |
|---|---|
| 把"无证据"错判成 refuted | 捕获 → `MISSING_JUDGED_REFUTED` BLOCKER，gate=BLOCKED |
| 把"不充分"错判成 supported | 捕获 → `INSUFFICIENT_JUDGED_SUPPORTED` BLOCKER |
| 全部判成 supported | 捕获 → 大量 false_supported + BLOCKER |
| 空 gold 集 | 显式 `EMPTY_GOLD_SET`，不返回 accuracy=1 |

---

## 10. 真实快照集成证据级别

**`HISTORICAL_REAL_DATA`** —— P1C 真实采集记录的回放，**不是本轮实时 API 访问**。
链路：Collector → Storage → Facts → Storage → EC → Storage。

| 验证项 | 结果 |
|---|---|
| README 存在命题 | **supported** |
| README 不存在命题 | **refuted** |
| package.json 不存在命题 | **insufficient（`NO_FACTS`）** —— 依 §1A 正确 abstain |
| 错误 Commit 证据 | **拒绝**，`COMMIT_MISMATCH` |
| 重复裁决 | `INGESTED` → `IDEMPOTENT_ALREADY_PRESENT` |

资产计数：snapshot 1 / fact 1 / claim 1 / verification 1。

---

## 11. 本轮踩到的问题

1. **EC 的 `models.py` 与 `src/facts/models.py` 同名** —— 在混合 sys.path 下 `import models`
   命中了 facts 那个，导致 `hasattr(M,'SUPPORTED')` 失败。改名 `ec_models.py` 彻底消除。
2. **CAS 被忽略**（见 §8 第 5 条）。
3. **身份语义的连锁后果**：`completeness_status` 不进 snapshot identity，
   所以同 repo+commit 下 COMPLETE 与 PARTIAL 会撞 CONFLICT —— gold 必须**每个场景独立 store**。
   这不是 bug，是既有契约；我在测试里显式记了原因。
4. 验收脚本三次"查错文件/查错文案"（断言字符串不在我以为的文件里）。

---

## 12. 新增代码与测试

```
src/evidence_claims/ec_models.py           五态分离 + 16 原因码 + 双层身份
src/evidence_claims/evidence_resolver.py   证据回查（内容哈希独立复算）
src/evidence_claims/verifier.py            三态裁决规则
src/evidence_claims/verification_store.py  持久化 + 幂等 + CAS
src/evidence_claims/evaluation.py          gold 判分 + 阻断级门禁
src/evidence_claims/facts_models_proxy.py  复用 Facts 哈希算法
tests/evidence_claims/{fixtures.py,test_verifier.py,test_gold.py}
tests/evidence_claims/gold/gold_cases.json
tools/{f2p2b_e2e_replay.py,f2p2b_verify.py}
docs/implementation/F2_P2B_*（5 份）
```

修改：`src/storage/asset_models.py`（登记 2 个类型）、`tools/fusion/f1d_verify.py`（授权目录加 EC）。

---

## 13. 全部测试数量与退出码

```
tests/runtime           45 OK   exit 0
tests/storage           53 OK   exit 0
tests/collector         48 OK   exit 0
tests/facts             44 OK   exit 0
tests/evidence_claims   36 OK   exit 0
f2p2b_verify           17/17 PASS
f2p2a_verify 15/15   f2p1c 22/22   f2p1b 16/16   f2p1a 22/22   f1d 26/26
```

226 项 unittest + 118 项验收断言，失败 0。

---

## 14. F1-D 冻结哈希

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变。

---

## 15. 仍未完成门禁

| 门禁 | 状态 |
|---|---|
| F2-P3 Lifecycle | 未开始 |
| Y6-P3 审批传递 | UNVERIFIED |
| Y6-P6 BotHarness 端到端 | OPEN |
| B-1/B-2/B-3 分发门禁 | OPEN |
| 实时 GitHub 重跑 | 未重跑 |

---

## 16. F2-P3 Lifecycle 最小可执行起点

1. **只消费 `claim_candidate` + `claim_verification`**，不重跑裁决。
2. Lifecycle 管"知识何时可能过时"，**不改变已有 verification 结论**。
3. 最小规则：新 Commit 出现时，把旧 Commit 的 claim 标 `possibly_stale`，**不标 false**。
4. 新鲜度与裁决状态正交 —— `knowledge_freshness` 已是独立字段。
5. 必须测：旧结论不被改写、`possibly_stale` 不自动变成 `refuted`、历史版本可读回。
