# F2-P3A · 执行报告

产物：`F2_P3A_VERIFICATION.json`（18/18）、`F2_P3A_E2E_REPLAY.json`、
`F2_P3A_REF_OBSERVATION_AUDIT.json`、`F2_P3A_GATE_RESULTS.json`、`F2_P3A_LIFECYCLE_ARCHITECTURE.md`

**结论先行：Lifecycle 版本观测与时效评估 DONE。固定历史不被改写，无效观测不产生伪失效。**

---

## 1. 实际新鲜度模型与持久化结构

```
applicability_scope: PINNED_COMMIT | TRACKING_REF
freshness_state:     NOT_APPLICABLE_TO_PINNED | VERSION_ALIGNED | POSSIBLY_STALE | UNKNOWN
```

三个新资产类型（已登记 Storage `ASSET_TYPES`）：

| 资产 | logical_identity | 说明 |
|---|---|---|
| `lifecycle_watch` | `watch_id` | 跟踪关系 |
| `ref_observation` | `observation_id` | 一次可信 Ref 观测 |
| `freshness_assessment` | `assessment_id` | 一次时效评估 |

均为 `SL-*` 前缀 + sha256 前 32 位。**观测与评估的时间戳都不进确定性身份。**

---

## 2. 固定 Commit 与移动 Ref 的语义隔离

**`PINNED_COMMIT` 不得建立 watch** —— `LifecycleWatch.__post_init__` 直接抛错。
没有 watch 就没有评估，任何 Ref 事件都无法触及固定版本的 Claim。

实测：给 `PINNED_COMMIT` 构造 watch 会 `ValueError`；
无 watch 时 `resolve_affected([])` 的受影响集合为空 —— 历史 Claim 不受影响。

---

## 3. Ref 观测证据与来源等级

三条入口，各自标明等级：

| 入口 | 等级 | 依据 |
|---|---|---|
| `observe_ref_via_collector` | `REAL_LIVE_API` | 实时 `/commits/{ref}` 解析 |
| `observe_ref_from_record` | `HISTORICAL_REAL_DATA` | 采集执行记录 |
| `observe_ref_from_snapshot` | `HISTORICAL_REAL_DATA` | 快照 payload（**要求含 requested_ref**） |

### 本轮实测纠错（重要）

我最初的审计说"快照内容载荷里有 `requested_ref`"——**这是错的**。

实测：`to_asset_payload()` 返回的就是 `content_payload()`，落库 payload 实测键为

```
blob_refs, collector_version, commit_sha, completeness_status, deep_walk_used,
manifest_version, repository_id, retrieval_scope, root_tree_sha, source_provider,
tree_entries, tree_entry_count, tree_query_ref, tree_truncated_seen
```

**没有 `requested_ref`。** 所以快照只能证明"存在某 commit 的快照"，**不能证明
"master 当时指向它"**。`observe_ref_from_snapshot` 因此返回 `REF_MISMATCH`（实测已验证）。

P1C 历史数据的合法来源是**采集执行记录**（同时含 `requested_ref=master` 与 `commit_sha`），
故新增 `observe_ref_from_record`。已修正审计文件并写入架构文档。

**Tree SHA 不能当 Commit** —— 40 位十六进制不足以证明它是 commit。
实测：Tree 对象形状（`{"sha":..., "tree":[...]}`）被 `NOT_A_COMMIT_OBJECT` 拒绝。

---

## 4. Commit 变化判定结果

| 场景 | 实测 |
|---|---|
| 同一 Ref，同一 Commit | `VERSION_ALIGNED` |
| 同一 Ref，新 Commit | `POSSIBLY_STALE` / `TRACKED_REF_MOVED` |
| 无观测 / 网络失败 | `UNKNOWN` / `OBSERVATION_FAILED` |
| 404 | `REF_UNAVAILABLE`（非"已删除"） |
| 403 / 401 | `PERMISSION_DENIED` |
| 限流 | `RATE_LIMITED` |
| 损坏来源 | `COMMIT_SHA_MALFORMED` |

**强制推送**：只记 ref movement，detail 明确写"未验证祖先关系（不假定快进）"。
测试断言 payload 里不出现 `fast_forward`。

---

## 5. POSSIBLY_STALE 与原始 verification 的隔离

实测（真实入库的 Claim + Verification）：

- `POSSIBLY_STALE` 后，verification payload 的 sha256 指纹**前后完全相等**
- `status` 仍是 `supported`
- 数据库里 `claim_verification` 数量前后不变（不自动创建新 verification）
- `review_status` 仍是 `pending_review`

源码级断言：`src/lifecycle/` 下**没有任何** `"refuted"` / `"approved"` 字面量，
`FRESHNESS_STATES` 里也不含 `refuted`。

---

## 6. 不同仓库、Branch、Fork 的影响范围

| 场景 | 实测 |
|---|---|
| master 动了，dev 没动 | master=`POSSIBLY_STALE`，dev=`VERSION_ALIGNED` |
| 交叉观测（用 master 的观测评估 dev 的 watch） | `UNKNOWN` / `REF_MISMATCH` |
| 不同 repository_id | `UNKNOWN` / `REPOSITORY_MISMATCH` |
| Fork 更新 | 原仓库 `UNKNOWN`，Fork `POSSIBLY_STALE`；两个 watch_id 不同 |
| 仓库重命名（repository_id 不变） | 同一 watch_id，不产生新身份 |

影响范围解析只用结构化字段，`explicitly_not_used` 里明确写了 `file_name_matching`。

---

## 7. 评估资产的 CAS、幂等、历史恢复

| 项 | 实测 |
|---|---|
| 首次登记 | `INGESTED` |
| 重复观测（不同时间戳） | `IDEMPOTENT_ALREADY_PRESENT`，资产数 1 |
| 重复评估（不同时间戳） | `IDEMPOTENT_ALREADY_PRESENT`，资产数 1 |
| 错误 `expected_version` | `CONFLICT` |
| 正确版本推进 | `VERSION_ADDED` |
| 旧版本读回 | `read_assessment_versions` 可读 |

**时间戳不污染身份**：`observed_at` / `assessed_at` 变化时 `observation_id` /
`assessment_id` 与内容哈希都不变（有专门测试）。

---

## 8. 跨进程中断与 operation_id 对账

**真实 SIGKILL 实验**：子进程完成资产提交并打印 `ASSET_COMMITTED`，
随后 `os.kill(getpid(), 9)`。重启验证：

- 崩溃前已提交的资产仍在（`lifecycle_watch` 数 = 1）
- `operation_log` 有 `OP-LC-` 记录
- 重放同一 watch → `IDEMPOTENT_ALREADY_PRESENT`，资产数仍为 1

**真实多进程并发 CAS**：4 个子进程同时把同一 watch 从 v1 推向 v2。
实测结果：**1 个 `VERSION_ADDED`，其余为 `CONFLICT` 或 `IDEMPOTENT`**（都属"未推进"）。
没有出现第二个 `VERSION_ADDED`。

---

## 9. 真实或历史 GitHub 数据集成情况

**等级：`HISTORICAL_REAL_DATA`。本轮未重新联网**（`live_github_refetch: false`）。

```
基线（P1C 执行记录，master → 7fd1a60b…） → VERSION_ALIGNED / HISTORICAL_REAL_DATA
"新 Commit"（合成对位 ffff…）             → POSSIBLY_STALE / SYNTHETIC_FIXTURE
网络失败                                   → UNKNOWN / OBSERVATION_FAILED
快照构造观测                               → 拒绝（REF_MISMATCH）
EC 裁决                                    → 仍 supported，未改
```

资产计数：snapshot 1 / fact 1 / claim 1 / verification 1 / watch 1 / observation 1 / assessment 2。

**必须说明：本轮没有进行实时 Ref 更新检测。** "新 Commit"是合成夹具，已明确标注
`SYNTHETIC_FIXTURE`，不冒充真实观测。

---

## 10. 本轮踩到的三个问题

1. **审计自己错了**：初版说快照 payload 含 `requested_ref`，实测不含。
   这直接改变设计——必须新增 `observe_ref_from_record`，并让快照路径返回 `REF_MISMATCH`。
2. **真缺陷：`_write` 忽略了 store 的 `idempotent` 标记**。并发 CAS 实测抓出：
   4 个进程里 2 个报 `VERSION_ADDED`（本应只 1 个）。修复后恢复正常。
3. **Tree SHA 冒充 Commit**：`b4eecafa…` 是 40 位十六进制，仅靠长度校验会放行。
   补了 `commit.tree.sha` 形状校验。

另外夹具与 evidence_claims 的 `fixtures.py` 同名冲突，改用显式路径加载。

---

## 11. 新增代码、测试与文档

```
src/lifecycle/lc_models.py            五状态分离 + 11 UNKNOWN 原因码 + 双层身份
src/lifecycle/ref_observer.py         三条观测入口 + Commit 对象形状校验
src/lifecycle/freshness_evaluator.py  新鲜度判定
src/lifecycle/impact_resolver.py      影响范围（仅结构化字段）
src/lifecycle/lifecycle_store.py      持久化 + 幂等 + CAS
tests/lifecycle/fixtures.py
tests/lifecycle/test_lifecycle.py                32 项
tests/lifecycle/test_recovery_and_mutation.py     8 项
tools/f2p3a_e2e_replay.py、tools/f2p3a_verify.py
docs/implementation/F2_P3A_*（5 份）
```

修改：`asset_models.py` 登记 3 个类型；`f1d_verify.py` 授权目录加 lifecycle。

---

## 12. 全部测试数量、失败数与退出码

```
tests/runtime           45 OK   exit 0
tests/storage           53 OK   exit 0
tests/collector         48 OK   exit 0
tests/facts             44 OK   exit 0
tests/evidence_claims   36 OK   exit 0
tests/lifecycle         40 OK   exit 0
f2p3a_verify           18/18 PASS
f2p2b 17/17  f2p2a 15/15  f2p1c 22/22  f2p1b 16/16  f2p1a 22/22  f1d 26/26
```

266 项 unittest + 136 项验收断言，失败 0。

---

## 13. F1-D 冻结 SHA-256

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变，f1d_verify 26/26 通过。

---

## 14. 未完成门禁

| 门禁 | 状态 |
|---|---|
| F2-P3B 自动重新验证协调 | 未开始 |
| Y6-P3 审批传递 | **UNVERIFIED**（本批未关闭） |
| Y6-P6 BotHarness 端到端 | **OPEN**（本批未关闭） |
| B-1/B-2/B-3 分发门禁 | **OPEN**（本批未关闭） |
| 实时 GitHub Ref 检测 | 未执行（本轮未联网） |

题面明确：Y6-P3、Y6-P6、B-1/B-2/B-3 维持原状态，不得借本批关闭 —— 三者均未动。

---

## 15. F2-P3B 自动重新验证协调的最小可执行起点

1. **只消费 `freshness_assessment`**，不重复判定新鲜度。
2. 入队条件严格：`freshness_state == POSSIBLY_STALE` 且 `conflict_detected == false`。
3. **`revalidation_candidate` 是"待办提议"，不是执行结果** —— 不自动跑 Collector。
4. 重新验证必须走 **Collector → Facts → EC** 独立工作流，产出新 `verification_id`，
   **旧 verification 保留不变**。
5. 队列必须有：幂等键（`claim_id + observed_commit_sha + rule_version`）、
   上限（每 watch 同时只允许一条 pending）、以及人工可关闭的开关。
6. 必测：不自动 approved；不把 `POSSIBLY_STALE` 当地 refuted；重复入队幂等。
