# F2-P3A · Lifecycle 架构

产物：`F2_P3A_REF_OBSERVATION_AUDIT.json`、`F2_P3A_E2E_REPLAY.json`、
`F2_P3A_VERIFICATION.json`、`F2_P3A_GATE_RESULTS.json`、`F2_P3A_EXECUTION_REPORT.md`

**立场：Lifecycle 只回答"这条结论对当前 Ref 是否仍适用"，不改写任何裁决。**

---

## 1. 五类状态必须独立

| 状态 | 归属 | 本批是否改动 |
|---|---|---|
| `verification_status` | EC 证据裁决 | **不改** |
| `knowledge_freshness` | Lifecycle | 新增（独立资产） |
| `review_status` | 人类审核 | **不改** |
| `execution_status` | Runtime/Checkpoint | 不涉及 |
| `source_completeness` | Collector | 不涉及 |

**六条禁止写进代码，不靠约定：**

- `possibly_stale → refuted`：`FRESHNESS_STATES` 里根本没有 `refuted`
- `supported → 永久新鲜`：`VERSION_ALIGNED` 的语义是"仅版本对齐"
- 新 Commit → 旧 Claim 自动 false：Lifecycle 不写 EC 任何资产
- Checkpoint 恢复成功 → 知识仍有效：两个子系统正交
- 人工审核通过 → 跳过事实验证：`review_status` 不参与裁决
- PARTIAL 来源 → 自动判定过时：`source_completeness` 不进新鲜度判定

---

## 2. 固定版本与移动 Ref 的隔离

```
PINNED_COMMIT  命题描述固定 Commit，历史适用范围不因 HEAD 移动改变
TRACKING_REF   把已验证结论用于某个可变引用（必须显式建立 watch）
```

**硬约束：`PINNED_COMMIT` 不得建立 watch。** `LifecycleWatch.__post_init__` 直接拒绝。
没有 watch 就没有评估，也就没有任何 Ref 事件能影响它。

`commit_sha` 是固定版本；Branch/Tag 是可能变化的引用；
`repository_id` 是稳定仓库身份（重命名不变）；Fork 有独立 `repository_id`。

---

## 3. Ref 观测（可信来源）

**Lifecycle 不直接抓 GitHub**，复用 Collector 的 `commit_for_ref`。

三条观测入口，各自标明来源等级：

| 入口 | 来源等级 | 依据 |
|---|---|---|
| `observe_ref_via_collector` | `REAL_LIVE_API` | 实时 `/commits/{ref}` 解析 |
| `observe_ref_from_record` | `HISTORICAL_REAL_DATA` | 采集执行记录（含 requested_ref + commit_sha） |
| `observe_ref_from_snapshot` | `HISTORICAL_REAL_DATA` | 快照 payload —— **但要求 payload 含 requested_ref** |

### 关键发现（本轮实测纠错）

`SourceSnapshot.to_asset_payload()` 返回的就是 `content_payload()`，
而它**不含 `requested_ref`**。落库 payload 的实测键为：

```
blob_refs, collector_version, commit_sha, completeness_status, deep_walk_used,
manifest_version, repository_id, retrieval_scope, root_tree_sha,
source_provider, tree_entries, tree_entry_count, tree_query_ref, tree_truncated_seen
```

**所以快照不能证明"master 当时指向该 commit"。** `observe_ref_from_snapshot`
在 payload 缺 `requested_ref` 时返回 `REF_MISMATCH`，不产生假观测。

P1C 历史数据的合法观测来源是**采集执行记录**（`F2_P1C_REAL_GITHUB.json` 同时含
`requested_ref=master` 与 `commit_sha`），故新增 `observe_ref_from_record`。

### O1..O7 落地

| 要求 | 实现 |
|---|---|
| 来源可定位 | `evidence_refs` 记录 ref/outcome |
| Commit 须经真实解析 | 只走 `commit_for_ref` 或执行记录 |
| 保留原始 Ref | `requested_ref` 独立字段 |
| 不把 Branch 当 Commit | 非 40 位十六进制 → `COMMIT_SHA_MALFORMED` |
| **不把 Tree SHA 当 Commit** | 校验 Commit 对象形状（必须有 `commit.tree.sha`）→ `NOT_A_COMMIT_OBJECT` |
| 不凭时间戳宣布更新 | `observed_at` 不进确定性身份 |
| 失败不得伪造 HEAD | 失败观测 `resolved_commit_sha` 恒为 `None`（构造期强制） |

---

## 4. 新鲜度模型

```
applicability_scope: PINNED_COMMIT | TRACKING_REF
freshness_state:     NOT_APPLICABLE_TO_PINNED | VERSION_ALIGNED | POSSIBLY_STALE | UNKNOWN
```

| 状态 | 语义 |
|---|---|
| `NOT_APPLICABLE_TO_PINNED` | 该历史 Claim 不追踪移动 Ref |
| `VERSION_ALIGNED` | 基线 Commit 与最近可信观测一致 —— **仅版本对齐** |
| `POSSIBLY_STALE` | 同一被跟踪 Ref 解析为新 Commit —— **旧 Claim 未被推翻** |
| `UNKNOWN` | 缺可信观测（11 个原因码） |

**判定顺序：** scope 检查 → 仓库归属 → Ref 归属 → 观测状态 → commit 合法性 →
scope 一致性 → `observed==baseline` → `VERSION_ALIGNED`；否则 `POSSIBLY_STALE`。

---

## 5. 情况 A..G 覆盖

| 情况 | 处理 |
|---|---|
| A 未变化 | `VERSION_ALIGNED`，时间戳不推进知识版本 |
| B 变化 | `POSSIBLY_STALE` + `TRACKED_REF_MOVED`，记录 old/new/ref/evidence |
| C 其他分支变化 | Ref 不匹配 → 不受影响 |
| D 仓库重命名 | `repository_id` 不变 → 同 watch 身份 |
| E Fork 更新 | 独立 `repository_id` → 不互相影响 |
| F 强制推送 | 只记 ref movement，**明确声明"未验证祖先关系"**，不宣称快进 |
| G Ref 不可用 | 404/403/限流**分别映射**，全部 UNKNOWN，不解释为已删除 |

---

## 6. 影响范围

只按结构化字段：`repository_id / watch_id / requested_ref / baseline_commit_sha / claim_id / retrieval_scope`。

**显式声明：`file_name_matching` 未被使用。**

同一 watch 有多条评估时，按"最需关注"聚合：`POSSIBLY_STALE > UNKNOWN > VERSION_ALIGNED`。

---

## 7. 持久化

三个新资产类型（已登记 Storage `ASSET_TYPES`）：

```
lifecycle_watch       logical_identity = watch_id
ref_observation       logical_identity = observation_id
freshness_assessment  logical_identity = assessment_id
```

- `freshness_assessment` **不是** `claim_verification`：身份、内容、历史都不共用
- **不改写 EC 的 B 层当前验证指针**
- **不改写不可变 Claim 资产来更新 `knowledge_freshness`** —— 最新时效通过关联评估查询
- `assessed_at` / `observed_at` 不进确定性身份
- CAS：调用方给 `expected_version` 必须校验

---

## 8. 明确不做

- 不自动重新验证（不重跑 Collector→Facts→EC）
- 不把 Claim 改成 refuted、不清除 supported
- 不生成新 verification_id、不改人工 review_status
- 不调 LLM 猜测新 Commit 的变化
- 不建第二套 Lifecycle 数据库
