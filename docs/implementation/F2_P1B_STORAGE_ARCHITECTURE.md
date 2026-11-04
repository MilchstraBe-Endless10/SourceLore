# F2-P1B · 存储架构

产物：`F2_P1B_VERIFICATION.json`、`F2_P1B_EXECUTION_REPORT.md`、`F2_P1B_GATE_RESULTS.json`

**结论先行：A/B/C 三层已实现；跨库协调靠 operation_id 对账，不宣称全局 ACID。**

---

## 1. 一个必须先讲的决定：为什么 A/B/C 在**一个**库

题面要求"说明两个数据库各自的事务边界"，并明确禁止"假定两个独立 SQLite 文件天然具有联合原子事务"。

**我实测了 ATTACH 跨库提交。** 结果值得记录：

| 场景 | 实测结果 |
|---|---|
| 两库均 WAL，同事务写两库后 SIGKILL | 两库都回滚（看起来原子） |
| 两库均 WAL，正常 COMMIT | 成功 |
| 两库均 delete 模式，正常 COMMIT | 成功 |

**但"看起来原子"不等于"有保证"。** SQLite 只承诺：主库处于 WAL 时，跨库提交可通过主库日志一次原子化。**两个各自为 WAL 的库，SQLite 不承诺跨库原子提交。**

所以本实现的取舍是：

> **A 层、B 层、C 层索引都在同一个库文件 `knowledge.db` 里，一个事务同时约束三层。**
> **checkpoint 保持在它自己的 `cp.db` 里，独立事务边界。**
> 两者之间**没有**全局事务 —— 由 `operation_id` 对账收敛。

这样既满足 A/B 同事务（W-4/W-5），又不依赖任何未经证明的跨库原子性。

---

## 2. 数据库与命名空间

| 库 | 文件 | 事务边界 | 权威性 |
|---|---|---|---|
| 知识资产库 | `knowledge.db` | A/B/C 单事务 | 知识权威 |
| Checkpoint 库 | `cp.db` | 独立 | 执行状态权威 |
| 派生索引 | 同在 `knowledge.db`（`index_rows` / `asset_fts`） | 与 A/B 同事务增补 | **非权威，可重建** |

**schema_version = 1**，存于 `meta` 表。打开时若版本不符直接抛 `RuntimeError`，不做静默迁移。

PRAGMA（顺序刻意如此，P1A 已实证顺序错误的后果）：

```
PRAGMA busy_timeout=5000   ← 必须在前
PRAGMA synchronous=FULL
PRAGMA foreign_keys=ON
PRAGMA journal_mode=WAL    ← 必须在后，且带幂等重试
```

完整性检查：`create=False` 打开时先跑 `PRAGMA integrity_check`，非 ok 即抛 `CHECKPOINT_CORRUPT`。
损坏**不当作空库、不自动重建**。

访问权限：数据库文件默认由进程 umask 决定；**本轮不设自定义权限模型**（保持默认 0644 / 目录 0755），
这一点在报告里如实标注为未加强项。

---

## 3. A 层：不可变权威历史

```sql
assets(
  asset_id          TEXT PRIMARY KEY,   -- 内部生成，非用户输入
  asset_type        TEXT NOT NULL,
  logical_identity  TEXT NOT NULL,
  repository_id     TEXT NOT NULL,
  subject_id        TEXT,
  asset_version     INTEGER NOT NULL CHECK(>=1),
  content_hash      TEXT NOT NULL,
  payload_json      TEXT NOT NULL,
  commit_sha        TEXT,               -- 三字段独立
  root_tree_sha     TEXT,
  tree_query_ref    TEXT,
  operation_id      TEXT,
  created_at        TEXT NOT NULL,
  UNIQUE(repository_id, logical_identity, asset_version)
)
```

**不可变靠触发器，不靠自觉：**

```sql
CREATE TRIGGER assets_no_update BEFORE UPDATE ON assets
BEGIN SELECT RAISE(ABORT, 'A_LAYER_IMMUTABLE'); END;
CREATE TRIGGER assets_no_delete BEFORE DELETE ON assets
BEGIN SELECT RAISE(ABORT, 'A_LAYER_IMMUTABLE'); END;
```

测试里真的尝试 `UPDATE` 和 `DELETE`，都被 `A_LAYER_IMMUTABLE` 挡住。

**asset_id 由内部生成**（`SL-A-` + sha256 前 32 位），输入含 repository_id。
这一条是被实测逼出来的：最初 ID 只用 (logical_identity, version, hash)，
结果**跨仓库同名记录算出同一个 ID 撞主键**，两条知识被静默合并成一条。详见报告"踩坑"一节。

**content_hash 不等于逻辑身份**：hash 只由 payload 决定；两条不同知识可以有相同 payload。
查重走 `(repository_id, logical_identity, asset_version)`，不走 hash。

---

## 4. B 层：当前指针 + CAS

```sql
current_view(
  logical_identity TEXT NOT NULL,
  repository_id    TEXT NOT NULL,
  current_asset_id TEXT NOT NULL,
  pointer_version  INTEGER NOT NULL CHECK(>=1),
  last_known_good  TEXT,
  updated_at       TEXT NOT NULL,
  PRIMARY KEY (repository_id, logical_identity)
)
```

**复合主键带 repository_id** —— 与 A 层同理，跨仓库同名不得共享一个指针。

**写入契约 W-1..W-5 的实现顺序（全在一个 `BEGIN IMMEDIATE` 内）：**

```
W-1 构造 AssetDraft（模型层校验：类型/ID 字符/敏感字段/版本）
W-2 校验结构与引用（含 source_snapshot 的 sha 格式）
W-3 读 current_view 的 pointer_version，与 expected_version 比较 → 不等即 CONFLICT
W-4 INSERT assets + UPDATE/INSERT current_view（同一事务）
    + postcondition(cursor) 在 COMMIT **之前**执行
    + C 层索引增补（同事务）
    + operation_log 写入（同事务）
W-5 COMMIT；任何异常 → ROLLBACK，不暴露部分状态
```

**W-2' 的关键点**：postcondition 是**提交前**校验，不是"先提交再检查"。
测试 `test_failing_postcondition_rolls_back_everything` 让 postcondition 抛异常，
断言 A 层 0 行、B 层无指针、C 层 0 行 —— 三层一起回滚。

**指针状态三值：**

| 状态 | 含义 | 返回 |
|---|---|---|
| `ok` | 指针指向存在的资产 | `ok=True` |
| `dangling_pointer` | 指针指向不存在的资产 | `ok=False, error=CHECKPOINT_CORRUPT, state=dangling_pointer`，带 `last_known_good` 供诊断 |
| 无记录 | 从来没发布过 | `NOT_FOUND` |

**dangling 绝不能报成 `NOT_FOUND`** —— 前者是"记录坏了"，后者是"这条知识不存在"，语义完全不同。

---

## 5. C 层：派生索引

```sql
index_rows(asset_id PK, asset_type, logical_identity, repository_id,
           subject_id, commit_sha, asset_version)
+ 索引：repository_id / subject_id / asset_type / commit_sha / logical_identity
+ FTS5 asset_fts（本地可用时）
```

**FTS5 实测可用（SQLite 3.54.0），但代码不依赖它。** 不可用时退化为 LIKE，结构化查询能力保留。

`rebuild_index()` 只 `DELETE FROM index_rows` / `asset_fts` 再重灌，**不碰 assets 与 current_view**。
返回 `a_b_unchanged` 与 A/B 指纹对比，测试断言前后指纹完全一致。

**索引缺失 ≠ 知识不存在。** 索引表被删时，`query()` 返回 `INDEX_MISSING`，**不返回空列表**。
这一条是硬规则 I3 的实现。

**查询结果必带出处**：每条结果含 `asset_id` / `asset_version` / `is_current` / `authority` 说明，
明确标注"C 层派生索引，未经 A 层回查不得视为已验证事实"。

---

## 6. 跨仓库身份（X-2 边界）

| 概念 | 是什么 | 不是什么 |
|---|---|---|
| `repository_id` | 仓库锚点 | 不是 Subject 身份 |
| `subject_id` | 知识主体身份 | 不是运行作用域 |
| `repo_bindings` | Subject ↔ 仓库关联，**必须带 evidence_ref** | 不是自动推断 |
| `commit_sha` | 版本 | 不是身份 |
| `workspace_id` | 运行作用域 | **不是 Subject 身份** |

`bind_repo()` 无 `evidence_ref` 直接 `PERMISSION_DENIED` —— 不接受无证据的自动合并。

实测断言：同一 `logical_identity` 在 `repo-a` 与 `repo-b` 下是**两条独立资产、两个独立指针**；
Fork 与重命名都不产生自动合并；`same_subject_across_repos()` 只列关系，不合并身份。

---

## 7. 跨库协调：operation_id 对账

**这是本轮最高风险处。两种库没有全局事务，只能靠一个锚点收敛。**

锚点就是知识库里的 `operation_log(operation_id PK, ...)`。
资产事务一旦 COMMIT，这条记录就在了。checkpoint 落后多少都能对出来。

**三种结局：**

| 状态 | 条件 | 动作 |
|---|---|---|
| `RECONCILED` | operation 已提交，checkpoint 缺失或只有意图无回执 | 补写 checkpoint，**不重复写资产** |
| `RETRY_SAFE` | operation 未提交，且无确定外部副作用 | 可按幂等规则重试 |
| `NEEDS_HUMAN` | 库读不出来 / 摘要矛盾 / 损坏 | **绝不自动重做**，交人工 |

对账的判定**只依据持久化记录**，不看模型上下文、不靠"我记得好像提交了"。

**两个口径必须一致**：`operation_log.result_hash` 与 `checkpoints.result_digest` 必须是同一个值。
最初这里写的是 `record_result()` 对 `{asset_id, pointer_version}` 再算的 sha256 —— 与资产 content_hash 必然不等，
导致下次对账误报 `DIGEST_MISMATCH`。已改为直接写回 `operation_log.result_hash`。

`assert_no_version_double_advance()` 断言同一 operation_id 在 `operation_log` 中只出现一次。

---

## 8. 路径与保密

- **主防线是内部生成 ID**，不是文件路径黑名单。用户传的 `repository_id` / `logical_identity` 只作为数据，
  **永远不参与决定文件路径或资产 ID**（ID 由内部 sha256 生成）。
- ID 合法性：`^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$` —— 路径穿越、空字节、超长一律在模型层拒绝。
- 辅助黑名单：库路径不得落在 `/docs/fusion/`、`knowledge/`、`assets/`、含 `CAPABILITY_CROSSWALK` 的位置。
  拒绝时**不创建文件**（测试断言）。
- 敏感字段按名硬拒（非默认禁止）：`api_key / token / cookie / secret / password / credential /
  private_key / authorization / env`。
- **不把数据库放进被分析仓库**；不对外暴露服务；不保存凭据。

---

## 9. 明确不做的事

- **不声称跨两库存在全局 ACID 事务。**
- **不声称外部系统（GitHub 请求等）exactly-once** —— 本地幂等只覆盖本地登记。
- **不实现 Claim 语义状态机**（`claim_record` 只是可选类型，无状态流转）。
- **不实现 Renderer**（D 层只做边界约束）。
- **不设数据库文件自定义权限模型**（保持默认，如实标注）。

---

## 10. 未决（留后续批次）

1. 资产内容的分片/大对象存储策略（当前整块存 `payload_json`）。
2. 索引重建在超大库上的耗时（本批只测 3~6 条量级）。
3. 真实 ENOSPC / EIO 注入（本批用只读目录做等价路径，未做真实磁盘故障）。
4. 数据库文件权限收紧（当前默认 umask）。
