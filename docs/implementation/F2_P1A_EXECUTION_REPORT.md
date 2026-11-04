# F2-P1A · 执行报告

产物：`F2_P1A_VERIFICATION.json`（22/22）、`F2_P1A_GATE_RESULTS.json`、`F2_P1A_STORAGE_DECISIONS.md`

**结论先行：本地运行时底座 DONE；Harness/BotHarness 集成仍 PARTIALLY_VERIFIED，两项门禁保持 OPEN。**

---

## 1. 持久化技术与版本（实测，非查文档）

| 项 | 值 |
|---|---|
| 语言运行时 | Python **3.14.8** |
| 存储 | **SQLite 3.54.0**（标准库 `sqlite3`） |
| journal_mode | WAL |
| synchronous | FULL（崩溃安全优先） |
| busy_timeout | 5000ms |
| schema_version | **1** |

能力逐条实测过：事务、UNIQUE、条件更新、WAL、integrity_check、跨进程，全部可用。

---

## 2. checkpoint 数据模型

```
checkpoints
  task_id            TEXT    ┐
  run_id             TEXT    ┘ 复合主键 —— 二者不可互换
  stage              TEXT
  status             TEXT
  checkpoint_version INTEGER  ← CAS 唯一依据，≥1 单调递增
  checkpoint_ref     TEXT     ← 结构化摘要（同输入可复现）
  attempt_count      INTEGER
  idempotency_key    TEXT
  input_digest       TEXT
  result_digest      TEXT
  updated_at         TEXT
```

另两张表：`attempts`（每次尝试的真实状态与退出码）、`idempotency`（幂等登记）。

**与建议字段的差异及依据：**
- `subject_id` **未进主键也未成列**。理由：它是"被研究对象"，不是"执行实例"；
  混入会被当成 run 的替代品，违反题面"三者不可互换"的本意。
- 新增 `attempts` 表。理由：单列 `attempt_count` 只能计数，不能回答"上次到底怎么失败的"，
  而 UNKNOWN/TIMEOUT 的判定必须看**最后一次尝试**的 `side_effect_possible`。

敏感字段硬拒（按名拦截）：`api_key / token / cookie / secret / password /
credential / private_key / authorization / env`。

---

## 3. CAS 实际测试结果

**单进程：**
```
create → v1
update(expected=1) → v2  ✓
update(expected=1) → CONFLICT, current_version=2  ✓（内容未被覆盖）
update(expected=1) 于不存在记录 → NOT_FOUND  ✓
```

**真实四进程并发（同一 expected_version=1）：**
```
成功 1 个（checkpoint_version=2）
CONFLICT 3 个
最终版本 = 2   ← 没有丢失更新，没有被静默覆盖两次
```

版本单调性另测：连续 3 次 CAS 得到 `[2, 3, 4]`。

---

## 4. 跨进程与崩溃恢复证据

### R-1 正常保存
进程 A（PID 1944xxx）写入 → 进程 B（**不同 PID**）读取，stage/version 一致。
测试断言 `assertNotEqual(pid_a, pid_b)`，确保是**真的两个进程**。

### R-2 中断后恢复（真实 SIGKILL）
**中断位置：`BEGIN IMMEDIATE` 之后、`COMMIT` 之前的窗口内**（INSERT 已执行）。

过程：子进程打印 `INSERTED_UNCOMMITTED` 后 `sleep(30)`，父进程 1.2 秒后 `SIGKILL`。

结果：
- `HALF/RH` 记录**不存在** → `NOT_FOUND`（未提交写入被回滚）
- 已提交的 `BASE/R0` 记录**仍在**

即：**不暴露半提交状态。** 这是 SQLite 事务的真实行为，不是 mock。

### R-5 损坏恢复
真实覆写数据库前 200 字节为 `\x00`，保留 `.backup` 副本。

结果：抛 `RuntimeError: CHECKPOINT_CORRUPT` / 或返回该错误码；
**不当作 NOT_FOUND**，**不自动重建**，备份仍在作为诊断证据。

### 多进程创建
6 个进程并发创建 6 条不同记录 → 全部成功，各记录均可读回。

---

## 5. 幂等执行与 UNKNOWN 处理

**幂等（真实副作用）：** 计数器文件，`commit_idempotent` 重复键返回
`already_committed=True`，副作用只发生 **1 次**（文件内容 `1`，不是 2）。

**UNKNOWN（受控漏窗场景）：** 子进程真的写了文件（副作用已落地），
然后 `SIGKILL` 自己，父进程拿不到 stdout。

判定：`from_exit_code(-9)` → **UNKNOWN**，`side_effect_possible=True`。
断言覆盖三条：
- 副作用文件确实存在
- 父进程回执为空
- 不得判 FAILED，不得判 NOT_FOUND

**resume 行为：** 上次 UNKNOWN → `resumable=False`，`reason=UNKNOWN_NEEDS_RECONCILE`；
上次 TIMEOUT 且副作用可能 → `TIMEOUT_SIDE_EFFECT_RISK`；
上次 FAILED 且无副作用 → `resumable=True`。

**必须保留的诚实说明：** 本地幂等登记 **不等于** 外部工具 exactly-once。
漏窗（副作用已发生、提交前崩溃）无法用本地数据库消除，只能记 UNKNOWN 并禁重做。

---

## 6. CANCELLED 实测结果

**真实 SIGTERM：** 子进程启动后写标记，父进程 1 秒后发 `SIGTERM` → 退出码为负（-15）。
映射为 `CANCELLED`，`side_effect_possible=True`。

**真实超时：** `timeout 2 sleep 5` → 退出码 **124** → `TIMEOUT`。

断言：`CANCELLED != TIMEOUT`，二者互斥且都可识别。
**SIGKILL（137/-9）映射为 UNKNOWN，明确不等于 CANCELLED**——有一项专门测这条。

---

## 7. 审批与 BotHarness 端到端状态

**审批：UNVERIFIED。**
本会话审批提示已禁用，`approval=ask` 的真实弹窗与拒绝阻断**无法实测**。
**没有通过修改全局安全配置制造虚假 PASS。** 该门禁保持 OPEN。

**BotHarness 端到端：OPEN。**
`dsh headless` 仍失败于同一处：`MISSING_CREDENTIAL`，provider route `deepseek-official`。
实际错误原文已记录在 F2-P0 报告中。本轮未复制任何凭据、未改全局凭据配置。

按第 8 节要求：**本地底座可靠性不依赖外部模型 API，因此没有为缺凭据而停工。**

---

## 8. 本轮踩到的三个真实问题

**其一，PRAGMA 顺序。** 先切 WAL 再设 busy_timeout，6 进程并发首开新库时全部
`database is locked`。修法：busy_timeout 前置 + WAL 切换加退让重试（WAL 幂等，重试安全）。

**其二，`plan_resume` 在库损坏时抛出而不是返回错误。**
调用方被迫 try/except 猜异常类型，这是接口设计错误。加了 `open_store()` 返回结构化错误。

**其三，验收脚本与 f1d 形成循环依赖。**
f1d 的 c24 原本读 F2 的验收结论，而 F2 验收又要调 f1d。改为**作用域判断**：
代码只允许在 `src/runtime/`、`tests/runtime/`，且不得有产品 Skill 入口与被追踪的 .db。

另：c4 又一次踩了 tuple-newline 陷阱（`return (expr),\n detail` 解析成单元素元组）。

---

## 9. 新增文件与数据目录

```
src/runtime/__init__.py
src/runtime/checkpoint_store.py        ← 存储核心
src/runtime/execution_result.py        ← 五态 + 四类存储错误
src/runtime/resume_coordinator.py      ← 恢复计划与推进
tests/runtime/test_checkpoint_store.py   （17 项）
tests/runtime/test_crash_recovery.py     （6 项，真实跨进程/SIGKILL/损坏）
tests/runtime/test_execution_states.py   （15 项，真实 SIGTERM/超时/UNKNOWN）
tests/runtime/test_concurrency.py        （7 项，真实多进程 CAS）
tools/f2p1a_verify.py                    （22 项总验收）
docs/implementation/F2_P1A_STORAGE_DECISIONS.md
docs/implementation/F2_P1A_EXECUTION_REPORT.md   （本文件）
docs/implementation/F2_P1A_GATE_RESULTS.json
docs/implementation/F2_P1A_VERIFICATION.json
```

**数据库文件：0 个进仓库。** 全部测试用临时目录，跑完即删；
c20 有硬断言「无被追踪的 .db、工作区无 .db 残留」。

---

## 10. 测试通过数与退出码

```
python3 -m unittest discover -s tests/runtime     45 tests   OK        exit 0
python3 tools/f2p1a_verify.py                     22/22 PASS          exit 0
python3 tools/fusion/f1d_verify.py                26/26 PASS          exit 0
python3 tools/f2p0_verify.py                      16/16 PASS          exit 0
```

失败数 0。

---

## 11. F1-D 冻结哈希与回归

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变。`git status` 该文件无改动。f1d_verify 26/26 通过。

**f1d 的两处历史断言已按作用域修正**（c20 / c24），不是删除：
它们原本断言"F1-D 当轮不得有产品代码"，现在断言"代码只能落在已授权批次目录，
且不得有产品 Skill 入口与被追踪的数据库"。**保留了原意，去掉了永远为真的时点假设。**

---

## 12. 尚未完成的 F2 门禁

| 门禁 | 状态 | 说明 |
|---|---|---|
| X-5 崩溃注入 + 并发 CAS | **SATISFIED_AT_F2P1A** | 真实 SIGKILL + 4 进程 CAS |
| 检查点与知识资产隔离 | **SATISFIED_AT_F2P1A** | 路径黑名单 + 实测拒绝 |
| Y6-P3 审批传递 | **UNVERIFIED** | 审批提示禁用，不能造假 |
| Y6-P6 BotHarness 端到端 | **OPEN** | headless 缺凭据 |
| 分发门禁 B-1/B-2/B-3 | **OPEN** | 未动（F5 / 法务） |

---

## 13. 下一批最小可执行起点

**Storage 最小可执行起点（F2-P1B 候选）：**
1. 知识资产 A/B/C 三层的**物理存储选型**（本批刻意未决）。
2. 资产写入与 checkpoint 的**跨层一致性**（同一事务边界内如何协调两套存储）。
3. 资产版本与 checkpoint_version 的**对齐规则**（两者不是同一个版本号，别混）。

**Collector 最小可执行起点：**
1. 单个上游源的最小抓取与登记（不碰分析模型）。
2. 抓取结果落 checkpoint + 幂等键，验证"重复抓取不重复入库"。

**F2-P1B 需独立批准，本轮未启动。**
