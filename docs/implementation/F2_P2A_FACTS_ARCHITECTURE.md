# F2-P2A · Facts 架构

产物：`F2_P2A_E2E_REPLAY.json`、`F2_P2A_EXECUTION_REPORT.md`、
`F2_P2A_GATE_RESULTS.json`、`F2_P2A_VERIFICATION.json`

**立场：只做可机械复算的观察。推断归后续批次，判定归 Evidence-Claims。**

---

## 1. 前一阶段检查结果（题面 §1）

**结论：原 Collector 的持久化清单**不足**以支撑完整抽取。** 具体：

| 检查项 | 原状态 | 判定 |
|---|---|---|
| Tree 条目完整保存 | ✗ 只存 `tree_entry_count` 与 `blob_refs` | **不足** |
| 路径/类型/mode/Blob SHA | ✗ 仅 blob 有 path/sha/size/mode_kind | **不足** |
| completeness_status 可读 | ✓ | 可用 |
| retrieval_scope 可用 | ✓ | 可用 |
| root_tree_sha 来自固定 Commit | ✓ | 可用 |
| 能定位原始 snapshot 资产 | ✓ | 可用 |
| Blob 内容与身份关联 | ✓ | 可用 |
| source_evidence_refs 可用 | ✓ | 可用 |

**关键缺口：** `blob_refs` 只覆盖 `type=blob` 的条目，**不含目录、submodule、symlink 的完整语义**，
且没有 `mode` 原值 —— 无法区分「目录」与「普通文件」，也无从做「不存在」判定（没有全量清单就没有反证）。

因此按题面授权做了**最小的、向后兼容的补齐**：

```
manifest_version = 1  旧契约：只有 blob_refs（P1C 已产出的快照保持原哈希）
manifest_version = 2  新契约：额外保存完整 tree_entries（含 type/mode/path/sha/size）
```

**向后兼容实测**（`c12`）：用 P1C 当时的输入走 `manifest_v1=True`，
重建出来的 `content_hash` 与 `logical_identity` 与 P1C 记录**逐字一致**
（`c15ea91f…` / `SL-SNAP-f6a274fe…`）。这是硬断言，不是口头保证。

---

## 2. 输入来源（唯一）

Facts 只能从 Storage 里**已提交的 `repository_snapshot`** 资产读取：

```python
store.get_asset(snapshot_asset_id, verify=True)   # 唯一入口
```

- 不请求 GitHub（抽取器源码里没有任何网络 import，有测试断言）
- 不执行 SQL（源码里没有 SELECT/INSERT/UPDATE/DELETE，有测试断言）
- 不看当前分支、不猜缺失文件、不读模型热记忆
- 完整性校验失败 → `U_ASSET_INTEGRITY_FAILED`

---

## 3. 规则：`file_path_observation`（v1）

| 项 | 值 |
|---|---|
| rule_id | `file_path_observation` |
| rule_version | `v1` |
| 参数 | `target_path`（仓库相对路径，经 `normalize_path` 标准化） |
| 结果 | 单结果（`item_key = "path:<normalized>"`） |
| 用 LLM | **否**（注册表里有断言 `uses_llm is False`） |
| 确定性 | **是** |

**判定顺序（先否定再肯定）：**

1. 快照资产读不到 / 完整性校验失败 → UNKNOWN
2. `manifest_version` 缺失或没有 `tree_entries` → `U_MANIFEST_ABSENT`
3. `tree_truncated_seen=True` → `U_TREE_TRUNCATED`（即使 status 写着 COMPLETE 也尊重截断痕迹）
4. `retrieval_scope` 不覆盖目标路径 → `U_SCOPE_NOT_COVERING`
5. 清单结构异常 → `U_MALFORMED_MANIFEST`
6. 同一路径命中多条 → `U_DUPLICATE_ENTRY`
7. **命中** → `OBSERVED_PRESENT`（保留 type/mode 语义）
8. **未命中 + COMPLETE** → `OBSERVED_ABSENT_IN_COVERED_SCOPE`
9. **未命中 + 非 COMPLETE** → `U_PARTIAL_SNAPSHOT`

---

## 4. 三态语义（不是布尔）

```
OBSERVED_PRESENT                 快照中存在，且有真实条目为证
OBSERVED_ABSENT_IN_COVERED_SCOPE 在**已完整覆盖范围内**未发现
UNKNOWN                          无法确定，必须带 unknown_reason
```

**ABSENT 的措辞是刻意的**，`observed_value` 里带两个字段：

```json
"scope_statement": "在指定 Commit 的已完整覆盖范围内未发现该路径",
"not_a_claim":     "这不表示仓库现在不存在该文件，也不表示项目没有相关功能"
```

**PARTIAL 下的 PRESENT 仍可成立**（有真实条目），但必须带：

```json
"local_coverage_only": true
```

**PARTIAL 下的缺失绝不能推成不存在** —— 那是本轮最重要的边界。

**UNKNOWN 绝不冒充空结果。** 有 10 个固定原因码（`MANIFEST_ABSENT` / `PARTIAL_SNAPSHOT` /
`SCOPE_NOT_COVERING` / `TREE_TRUNCATED` / `ENTRY_REQUIRED_MISSING` / `BLOB_VERIFY_FAILED` /
`ASSET_INTEGRITY_FAILED` / `ASSET_NOT_FOUND` / `MALFORMED_MANIFEST` / `DUPLICATE_ENTRY`），
`FactObservation.__post_init__` 强制：UNKNOWN 必带原因，非 UNKNOWN 不得带原因。

---

## 5. 四种身份不可混淆

| 概念 | 含义 | 由什么决定 |
|---|---|---|
| `fact_id` | 事实身份 | `H(repo, snapshot_identity, rule_id, rule_version, norm_params, item_key)` |
| `content_hash` | 事实内容哈希 | `H(observation, observed_value, unknown_reason, commit_sha, completeness)` |
| `input_digest` | 输入摘要 | `H(snapshot_identity, snapshot_content_hash, rule, params, item_key)` |
| `asset_id` | Storage 物理资产 ID | Storage 内部生成 |

**`fact_id` 的稳定性：**
- `observed_at` 不进任何哈希 —— 抽取时间不是身份
- 多结果规则靠 `item_key`（不是数组下标）—— 输入顺序变了 ID 也不漂
- `rule_version` 变 → `fact_id` 变（硬契约，有测试）
- 未注册的规则版本 → `KeyError`，不会静默用旧版本

---

## 6. 对象类型不冒充

`describe_object(type, mode)` 明确区分：

| 输入 | object_kind | is_regular_file |
|---|---|---|
| `blob` + `100644` | regular_file | true |
| `blob` + `120000` | symlink | **false** |
| `commit` / `160000` | submodule | **false** |
| `tree` / `040000` | directory | **false** |
| 其他 type | unknown_object | **false** |

非普通文件时 `type_note` 明确写「不得按普通文件处理」。

---

## 7. Evidence 引用

**结构化，不是自然语言。** 至少两条：

```json
{
  "kind": "source_snapshot",
  "repository_id": "...", "commit_sha": "...",
  "snapshot_asset_id": "...", "snapshot_logical_identity": "...",
  "root_tree_sha": "...", "tree_query_ref": "...",
  "completeness_status": "...", "manifest_version": 2,
  "rule_id": "file_path_observation", "rule_version": "v1"
}
{
  "kind": "tree_entry",
  "path": "README", "object_type": "blob",
  "mode": "100644", "blob_sha": "980a0d5f..."
}
```

**证据对象存在 ≠ 证据足以支持任意结论。** Facts 只提供可重放观察；
`supported / refuted / insufficient_evidence` 的裁决留给 Evidence-Claims。

---

## 8. 入库

- 资产类型 `extracted_fact`（在 Storage `ASSET_TYPES` 中登记）
- `logical_identity = fact_id`
- 只经 `KnowledgeStore.append_asset_and_advance()`
- `operation_id` 由 `H(fact_id, content_hash, extractor_version)` 派生，重试不变
- **UNKNOWN 不入 A 层**（`REJECTED`）
- 重复抽取 → `IDEMPOTENT_ALREADY_PRESENT`
- 同 `fact_id` 不同内容 → `CONFLICT`

**payload 里没有 `verified` / `claim_status` / `supported` / `refuted`** —— 有测试断言。

---

## 9. Registry 边界

- 身份语义在 `facts/models.py`（`make_fact_id` 等纯函数）
- 权威持久化在 Storage
- **没有第二套数据库**，没有平行 Collector，没有 Claim 状态机
- 不做完整实体消解

---

## 10. 明确不做

- 不抽自然语言语义（"有文档" / "已完成开发" / "没有漏洞" 一律不做）
- 不产出 Claim 裁决
- 不调用 LLM
- 不修改来源快照
- 不用当前分支状态重写历史
