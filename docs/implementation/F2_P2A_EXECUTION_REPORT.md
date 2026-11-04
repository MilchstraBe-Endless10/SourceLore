# F2-P2A · 执行报告

产物：`F2_P2A_VERIFICATION.json`（15/15）、`F2_P2A_GATE_RESULTS.json`、
`F2_P2A_E2E_REPLAY.json`（真实数据回放）、`F2_P2A_FACTS_ARCHITECTURE.md`

**结论先行：确定性 Facts 抽取引擎 DONE。来源证据可定位，PARTIAL 语义正确，未越界到 Claim 裁决。**

---

## 1. 从 Collector 真实产物出发的检查（题面 §1）

先查了实际入库结构，**没有直接凭设计文档造 Schema**。结论是**原清单不足**：

| 检查项 | 原状态 |
|---|---|
| Tree 条目完整保存 | ✗ 只有 `tree_entry_count` + `blob_refs` |
| 路径/类型/mode/Blob SHA | ✗ 只有 blob 的 path/sha/size/mode_kind |
| completeness_status | ✓ |
| retrieval_scope | ✓ |
| root_tree_sha 来源 | ✓（来自 Commit 对象） |
| 定位 snapshot 资产 | ✓ |
| Blob 内容与身份关联 | ✓ |
| source_evidence_refs | ✓ |

**缺口的具体后果：** `blob_refs` 只覆盖 `type=blob`，不含目录/submodule/symlink 的完整语义，
也没有 `mode` 原值 —— 既分不出「目录 vs 普通文件」，也**做不了"不存在"判定**（没有全量清单就没有反证）。

按题面授权做了最小补齐，**并证明了向后兼容**：用 P1C 当时的输入走 `manifest_v1=True` 重建，
`content_hash` 与 `logical_identity` 与 P1C 记录**逐字一致**：

```
P1C 记录 hash : c15ea91f8d2e561987b8ba1943d52729c28e9a88ef31e9c8c5f18825a739e61f
v1 重建 hash  : c15ea91f8d2e561987b8ba1943d52729c28e9a88ef31e9c8c5f18825a739e61f
P1C 记录 ident: SL-SNAP-f6a274fe1dbf2cedf71c4cc2492b207b806ec5b8
v1 重建 ident : SL-SNAP-f6a274fe1dbf2cedf71c4cc2492b207b806ec5b8
```

---

## 2. Facts 使用的真实输入资产结构

```
asset_type        = repository_snapshot
logical_identity  = SL-SNAP-…
payload:
  repository_id, commit_sha, root_tree_sha, tree_query_ref
  retrieval_scope = "full_tree_enumeration"
  completeness_status ∈ {COMPLETE, PARTIAL, INCOMPLETE}
  tree_entry_count, blob_refs
  manifest_version = 2, tree_entries = [{path,type,mode,sha,size,object_kind,depth}]
  tree_truncated_seen, deep_walk_used, collector_version, source_provider
```

---

## 3. 实现的抽取规则

**只有一条：`file_path_observation@v1`**。参数 `target_path`；结果单值（`item_key=path:<norm>`）；
不用 LLM（注册表有断言）；确定性。

判定顺序：资产完整性 → 清单存在 → 截断 → 范围覆盖 → 结构合法 → 重复 → 命中 → 未命中(COMPLETE) → 未命中(PARTIAL)。

---

## 4. fact_id 契约与碰撞测试

```
fact_id = SL-FACT- + H(repository_id, snapshot_logical_identity,
                       rule_id, rule_version, normalized_parameters, item_key)[:40]
```

碰撞与稳定性实测：

| 场景 | 结果 |
|---|---|
| 同快照同路径两次抽取 | `fact_id` 相同 ✓ |
| 独立复算（不经抽取器） | 与抽取器结果一致 ✓ |
| 不同 `target_path` | 不同 `fact_id` ✓ |
| 不同 `repository_id` | 不同 `fact_id` ✓ |
| 不同 `commit_sha`（不同快照） | 不同 `fact_id` ✓ |
| `observed_at` 不同 | `fact_id` **不变** ✓（时间不进身份） |
| `rule_version` 不同 | `fact_id` 不同 ✓ |
| 未注册的规则版本 | `KeyError`（不静默） ✓ |

`item_key` 用规范化路径而非数组下标 —— 输入顺序变化不会让 ID 漂移。

---

## 5. COMPLETE / PARTIAL / UNKNOWN 实测

| 场景 | 实际观察 |
|---|---|
| A. COMPLETE + 路径存在 | `OBSERVED_PRESENT`，带 type/mode/blob_sha，`local_coverage_only=false` |
| B. COMPLETE + 路径不存在 | `OBSERVED_ABSENT_IN_COVERED_SCOPE`，带限定语句与「不是仓库存不存在」声明 |
| C. PARTIAL + 路径存在 | `OBSERVED_PRESENT`，**`local_coverage_only=true`** |
| D. PARTIAL + 路径不存在 | **`UNKNOWN`** / `PARTIAL_SNAPSHOT` —— 绝不推断不存在 |

其他 UNKNOWN 触发（全部有测试）：
`MANIFEST_ABSENT`（v1 快照）· `TREE_TRUNCATED` · `SCOPE_NOT_COVERING` ·
`MALFORMED_MANIFEST` · `DUPLICATE_ENTRY` · `ASSET_NOT_FOUND` · `ASSET_INTEGRITY_FAILED`。

**UNKNOWN 绝不冒充空数组 / false / NOT_FOUND** —— `__post_init__` 强制必须有原因码。

---

## 6. Evidence 引用实际结构

两条结构化引用（实际输出抽样）：

```json
{"kind":"source_snapshot","repository_id":"1296269",
 "commit_sha":"7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
 "snapshot_asset_id":"SL-A-…","snapshot_logical_identity":"SL-SNAP-…",
 "root_tree_sha":"b4eecafa9be2f2006ce1b709d6857b07069b4608",
 "tree_query_ref":"b4eecafa9be2f2006ce1b709d6857b07069b4608",
 "completeness_status":"COMPLETE","manifest_version":2,
 "rule_id":"file_path_observation","rule_version":"v1"}
{"kind":"tree_entry","path":"README","object_type":"blob",
 "mode":"100644","blob_sha":"980a0d5f19a64b4b30a87d4206aade58726b60e3"}
```

**证据对象存在 ≠ 证据足以支持任意结论。** 有专门断言要求证据是 dict 而非自然语言。

---

## 7. Facts 入库与幂等结果

```
first  = INGESTED
second = IDEMPOTENT_ALREADY_PRESENT
facts  = 1（不重复创建）
pointer_version = 1（不重复推进）
```

CAS 冲突出显式返回；注入失败后 A 层无残留；UNKNOWN 被 `REJECTED` 不入库。

---

## 8. 多仓库、多版本隔离结果

- 不同 `repository_id` 同名文件 → 不同 `fact_id`、不同资产
- 不同 `commit_sha` 的两个快照：一条 PRESENT、一条 ABSENT，**两条都正确**（针对不同 Commit）
- 旧事实**没有**被标 false；新事实**没有**被标 verified
- 来源快照资产在 Facts 入库后 `content_hash` / `logical_identity` / `asset_version` **全部未变**

---

## 9. 实际 GitHub 快照集成情况

**等级：历史真实数据回放（HISTORICAL_REAL_DATA），不是本轮实时 API 访问。**

输入来自 P1C 已采集并核验的真实记录（`F2_P1C_REAL_GITHUB.json`）：
`octocat/Hello-World` @ `7fd1a60b…`，root tree `b4eecafa…`。

回放结果（`F2_P2A_E2E_REPLAY.json`）：

```
snapshot_assets = 1   fact_assets = 1
README      → OBSERVED_PRESENT
package.json → OBSERVED_ABSENT_IN_COVERED_SCOPE
ingest: INGESTED → IDEMPOTENT_ALREADY_PRESENT
```

三者分开报告：**Mock 测试**（44 项）、**历史真实数据回放**（本条）、**实时 GitHub 请求**（本轮未重跑，沿用它 的 P1C 成功记录）。

---

## 10. P1C 重试上限口径勘误结论

题面让我核对 `配置 120` / `测试 9999` / `预期 5` 三者矛盾。

**结论：不是实现错误，是文档说明不清。**

- `DEFAULT_LIMITS["max_retry_after"] = 120` 是**生产默认值**
- 测试里 `c.limits["max_retry_after"] = 5` 是**测试专用覆盖**（避免真等 120 秒）
- 两者不矛盾：测试验证的是"截断机制生效"，不是"生产上限是多少"

**但我顺带查出一个更严重的问题：** 原测试先设 `_sleep` 再调 `install_fake`，
而 `install_fake` 会把这个 `_sleep` 覆盖成 `lambda s: None` —— 于是 `slept` 恒为空，
`assertTrue(all(s <= 5 for s in slept))` 对空列表**永远为真**。**那条断言是空跑假通过。**

修法：
1. `install_fake` 不再无条件覆盖 `_sleep`（尊重调用方已设置的值）
2. 两处退避测试改为 `install_fake` **之后**设置 `_sleep`，并加 `assertTrue(slept)` 保证非空
3. 新增两条测试固化「默认上限就是 120」与「9999 被截到 120」

**没有改任何限流安全行为。**

---

## 11. 本轮自身踩到的三个问题

1. **`extracted_fact` 不在 Storage 的 `ASSET_TYPES` 白名单** → 入库全被 `REJECTED`。
   按题面 §8 授权把它登记为最小等价类型。
2. **哈希空间混用（两次）**：`ingest_fact` 用 Storage 的 `assets.content_hash`（对整份 payload 算）
   去比 `fact.content_hash`（对观测结论算）—— 两个空间必然不等，幂等被误判 CONFLICT。
   连 `operation_log.result_hash` 也犯了同样的错。修法是都改读 payload 内的 `content_hash` 字段。
3. **`tools/f2p2a_verify.py` 里又一次 tuple-newline 陷阱**（`return X,` 换行接 f-string）。

---

## 12. 新增代码与测试文件

```
src/facts/__init__.py
src/facts/models.py        三态 + 10 个 UNKNOWN 原因码 + 四种身份派生
src/facts/rules.py         规则注册表 + describe_object（类型不冒充）
src/facts/extractor.py     唯一抽取入口，只用 Storage 公开 API
src/facts/ingest.py        入库通道 + operation_id 幂等
tests/facts/fixtures.py    确定性夹具（不联网）
tests/facts/test_extractor.py  44 项
tools/f2p2a_e2e_replay.py
tools/f2p2a_verify.py
docs/implementation/F2_P2A_{FACTS_ARCHITECTURE.md,EXECUTION_REPORT.md,
  GATE_RESULTS.json,VERIFICATION.json,E2E_REPLAY.json}
```

修改（最小、向后兼容）：
- `src/collector/source_snapshot.py` 加 `manifest_version` / `tree_entries`
- `src/storage/asset_models.py` 登记 `extracted_fact`
- `tests/collector/fake_gh.py` 不再覆盖 `_sleep`
- `tests/collector/test_github_client.py` 修两处假通过测试、加两条口径测试
- `tools/fusion/f1d_verify.py` 授权目录加 `facts`

---

## 13. 全部测试数量与退出码

```
tests/runtime     45 tests OK    exit 0
tests/storage     53 tests OK    exit 0
tests/collector   45 tests OK    exit 0
tests/facts       44 tests OK    exit 0
f2p2a_verify      15/15 PASS     exit 0
f2p1c_verify      22/22 PASS     exit 0
f2p1b_verify      16/16 PASS     exit 0
f2p1a_verify      22/22 PASS     exit 0
f1d_verify        26/26 PASS     exit 0
```

合计 187 项 unittest + 101 项验收断言，失败 0。

---

## 14. F1-D 冻结哈希

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变。

---

## 15. 尚未完成门禁

| 门禁 | 状态 |
|---|---|
| Evidence-Claims 裁决 | 未开始（F2-P2B） |
| Y6-P3 审批传递 | UNVERIFIED |
| Y6-P6 BotHarness 端到端 | OPEN |
| B-1/B-2/B-3 分发门禁 | OPEN |
| 实时 GitHub 重跑 | 未重跑（沿用 P1C 成功记录） |

---

## 16. F2-P2B Evidence-Claims 的最小可执行起点

1. **只消费 `extracted_fact`** —— 不直接读快照，证据通过 `evidence_refs` 回查。
2. **Claim ≠ Fact**：Claim 是"某主张是否被支持"的判定，必须显式引用 facts 列表。
3. **三态裁决**：`supported` / `refuted` / `insufficient_evidence`，**不得默认成 supported**。
4. **拒绝规则**：没有 fact 支撑的 Claim 一律 `insufficient_evidence`；PARTIAL 来源的事实不能单独支撑。
5. **可重放**：同一 facts 集合 + 同一裁决规则版本 → 同一裁决结论，且结论身份稳定。
