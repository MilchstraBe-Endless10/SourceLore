# F2-P1A · 存储决策

本文件记录：为什么用 SQLite、schema 怎么定、以及几个**不能想当然**的判断。

---

## SD-1 · 选型：Python 标准库 sqlite3

实测本机：Python 3.14.8 / SQLite 3.54.0。以下能力已逐条验过，不是查文档：

| 能力 | 实测结果 |
|---|---|
| 事务 | 支持，可 `BEGIN IMMEDIATE` 手动控制 |
| UNIQUE 约束 | 生效（重复插入抛 IntegrityError） |
| 条件更新 | 支持（`WHERE ... AND version=?`） |
| WAL | 支持（`PRAGMA journal_mode=WAL`） |
| busy_timeout | 可设，实测 5000ms |
| integrity_check | 返回 `ok` |
| 跨进程 | 真实两进程并发已测通 |

**为什么不用别的东西：** 标准库自带、无外部依赖、无需模型调用、单文件可搬、崩溃语义明确。
本批**不**决定完整知识库的最终存储技术——那要等 Storage 批次。

---

## SD-2 · schema 设计的三条硬理由

```sql
checkpoints(task_id, run_id, stage, status, checkpoint_version,
            checkpoint_ref, attempt_count, idempotency_key,
            input_digest, result_digest, updated_at)
PRIMARY KEY (task_id, run_id)
```

**其一，主键是 `(task_id, run_id)` 复合键，不是单列。**
题面要求 `task_id`、`run_id`、`subject_id` 不能互相替代。用复合主键是最直接的落实：
把 T1/R1 换成 T1/R2 是另一条记录，查不到就是查不到。

`subject_id` **没有进主键**，也没有进列——它是"被研究的对象"，不是"执行实例"，
混进 checkpoints 会模糊"谁在跑"与"在跑什么"。若后续批次确需，另建关联表。

**其二，`checkpoint_version` 是 CAS 唯一依据，从 1 起、单调递增。**
每次成功更新 +1，失败不动。不提供任何"无版本覆盖"的入口——
`update_checkpoint_if_version` 的签名里 `expected_version` 是必填参数。

**其三，敏感字段按名拦截，不靠调用方自觉。**
`api_key / token / cookie / secret / password / credential / private_key /
authorization / env / environ` 一律 `PermissionError`。
题面要求"默认不存储 API Key、Cookie、Token 和完整环境变量"，这里是硬拒，不是默认。

---

## SD-3 · PRAGMA 顺序：踩过的坑

**必须 `busy_timeout` 在前，`journal_mode=WAL` 在后。**

反过来的后果是实测到的：6 个进程同时首开一个新库，全部 `sqlite3.OperationalError:
database is locked`。因为切 WAL 本身要排它锁，而这时 busy_timeout 还是默认 0。

修复分两步：
1. 先 `PRAGMA busy_timeout=5000`，再切 WAL；
2. 切 WAL 加退让重试（WAL 是幂等的，已是 WAL 再设直接返回，重试安全）。

`synchronous=FULL`：崩溃安全优先于吞吐。本批不是性能批次。

---

## SD-4 · 为什么分为"执行状态"与"存储/授权错误"

题面明确：执行期状态与存储错误不应强行合并。实现上分成两个互斥集合：

```
EXECUTION_STATES = {SUCCESS, FAILED, TIMEOUT, CANCELLED, UNKNOWN}
STORAGE_ERRORS   = {NOT_FOUND, CONFLICT, PERMISSION_DENIED, CHECKPOINT_CORRUPT}
```

`ExecutionResult` 只接受前者；`storage_error()` 只接受后者。
`assertTrue(EXECUTION_STATES.isdisjoint(STORAGE_ERRORS))` 是测试里的一条硬断言。

**关键区分：** `NOT_FOUND` 是"没有这条记录"（业务语义），
`CHECKPOINT_CORRUPT` 是"库坏了"（存储语义）。损坏**绝不能**伪装成 NOT_FOUND，
否则调用方会以为"没跑过"然后重跑，而真相是"跑过但记录读不出来"。

---

## SD-5 · UNKNOWN 是**非终态**

这是本批最重要的一个语义决定。

- `SUCCESS / FAILED / TIMEOUT / CANCELLED` 是终态，可以写下结论。
- `UNKNOWN` **不是**终态：它是"副作用可能已发生、但回执缺失"，需要重新观测或人工收敛。

由此带来三条硬规则（都有测试）：
1. `UNKNOWN` 必须带 `side_effect_possible=True`，否则构造直接 ValueError。
2. `UNKNOWN` 的 `retry_allowed()` 为 False。
3. `resume_checkpoint` 遇到 `UNKNOWN` 返回 `UNKNOWN_NEEDS_RECONCILE`，`resumable=False`。

**SIGKILL ≠ 正常取消。** 137/-9 一律映射为 `UNKNOWN`，不是 `CANCELLED`。
判据：取消是"有人决定停"，SIGKILL 是"进程被外力斩断"，后者无法判断副作用边界。

---

## SD-6 · 幂等的边界（必须说清楚，别夸大）

`commit_idempotent` 保证的是**本地登记幂等**：
同一 `idempotency_key` 第二次提交返回 `already_committed=True`，不重复登记，不覆盖原摘要。

**它不保证外部工具 exactly-once。**
真实风险场景：外部副作用已发生 → checkpoint 提交前进程被杀死 → 下次启动。
此时本地登记表里没有记录，但文件真的写了。**这个窗口无法用本地数据库消除**，
唯一正确的处理是把结果记为 `UNKNOWN` 并禁止自动重做。

测试 `test_local_side_effect_committed_once` 用真实计数器文件验证了"重复请求不重复副作用"；
测试 `test_side_effect_done_but_no_receipt_is_unknown` 用真实 SIGKILL 验证了漏窗场景判 UNKNOWN。

---

## SD-7 · 损坏处理立场

- **不把损坏当空库。** `create=False` 打开时先跑 `integrity_check`，非 ok 直接抛。
- **不自动重建。** 没有任何"发现损坏就新建"的代码路径。
- **保留诊断证据。** 测试里破坏前先写 `cp.db.backup`，断言它仍在。
- **要求人工。** `plan_resume` 对损坏返回 `requires_human=True`。

---

## SD-8 · 与知识资产的隔离

`_verify_root_isolation()` 用路径黑名单硬拒：`docs/fusion/`、`knowledge/`、
`assets/`、以及任何含 `CAPABILITY_CROSSWALK` 的路径。

拒绝时**不创建文件**（测试断言 `bad.exists() == False`）。
这条对应的正是 Y-4 裁决：检查点是执行状态，不是知识资产，必须独立分区。

---

## 未决（留给后续批次）

- 完整知识库 A/B/C 层的物理存储：**本批不选**。
- `subject_id` 若需建模，另建关联表，不塞进 checkpoints。
- 数据库文件位置：本批全部位于临时目录，**没有任何 .db 进仓库**（c20 有断言）。
