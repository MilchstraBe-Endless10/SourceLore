# F2-P1B · 执行报告

产物：`F2_P1B_VERIFICATION.json`（16/16）、`F2_P1B_GATE_RESULTS.json`、`F2_P1B_STORAGE_ARCHITECTURE.md`

**结论先行：A/B/C 三层存储引擎 DONE；跨库协调靠 operation_id 对账成立；集成门禁仍 OPEN。**

---

## 1. 存储技术与 Schema

SQLite 3.54.0 / Python 3.14.8，标准库 `sqlite3`。

**知识库 `knowledge.db`（schema_version=1）：**

```
assets           A 层：不可变历史（含 UPDATE/DELETE 阻止触发器）
current_view     B 层：当前指针（PRIMARY KEY (repository_id, logical_identity)）
index_rows       C 层：派生索引（可删重建）
asset_fts        C 层：FTS5 全文（本地可用）
repo_bindings    跨仓库身份关联（必须带 evidence_ref）
operation_log    跨库协调锚点（operation_id 主键）
meta             schema_version
```

**checkpoint 库：仍为独立的 `cp.db`，独立事务边界。**

PRAGMA 顺序：`busy_timeout` → `synchronous=FULL` → `foreign_keys` → `journal_mode=WAL`（带幂等重试）。

---

## 2. A/B/C 三层实际实现

**A 层**：`append_asset_and_advance()` 是唯一写入口。
不可变靠**触发器**而非自觉：`assets_no_update` / `assets_no_delete` 抛 `A_LAYER_IMMUTABLE`。
测试真的试了 UPDATE 与 DELETE，都被挡住。

**B 层**：`BEGIN IMMEDIATE` 内完成 CAS。`expected_version` 必填于更新路径；
首次发布要求 `expected_version=None` 且 B 中无记录，否则 CONFLICT。

**C 层**：`rebuild_index()` 只清 `index_rows` / `asset_fts` 再重灌，
返回 A/B 指纹前后对比，测试断言完全一致。

---

## 3. 事务与并发边界

**A/B/C 在一个事务里**，因为它们在**同一个库文件**。

我实测了 ATTACH 跨库提交：两库均 WAL 时，正常 COMMIT 成功、SIGKILL 后两库都回滚 ——
**看起来原子**。但 SQLite 的保证是"主库 WAL 时可经主库日志一次原子化"，
**两个各自为 WAL 的库，SQLite 不承诺跨库原子提交**。

因此本实现不依赖 ATTACH，而是：

> A/B/C 同库同事务（解决 W-4/W-5）；
> checkpoint 独立库独立事务；
> **两库之间没有全局事务，靠 operation_id 对账。**

**postcondition 位置**（c2 硬断言源码中两者的索引顺序）：

```python
if postcondition is not None:
    postcondition(self.conn, ctx)     # ← 在 COMMIT 之前
self._index_asset(aid, draft)
if op_id: INSERT INTO operation_log ...
self.conn.execute("COMMIT")
```

抛异常即 `ROLLBACK`，A/B/C 三层一起回滚。

---

## 4. 跨进程崩溃测试结果

### T-3 真实并发 CAS

4 个独立进程用 barrier 文件同步起跑，同争 `expected_version=1`：

```
成功 1 个（pointer_version=2）
CONFLICT 3 个
最终：assets 共 2 条（v1 + 一个 v2），pointer_version=2
```

**版本只前进一次，无丢失更新，无静默覆盖。**

### T-4 提交前崩溃

窗口：`BEGIN IMMEDIATE` 之后、`COMMIT` 之前，A 行与 B 指针都已 INSERT 但未提交。

```
子进程打印 HALF_UNCOMMITTED → 1.3s 后 SIGKILL
重启检查：
  未提交的 A 行不可见（count=0）
  B 指针指向它时返回 NOT_FOUND（不是 ok）
  先前已提交的 BASE 记录仍在（ok=True）
```

**不暴露半提交状态。**

### 损坏副本

覆写前 200 字节为 `\x00`（保留 `.backup`）：

```
显式 CHECKPOINT_CORRUPT / raised
不是 NOT_FOUND   ← 关键区分
备份仍在，可作诊断
```

---

## 5. Checkpoint 与资产跨库协调机制

**锚点：`operation_log(operation_id PRIMARY KEY, ...)`，在知识库内、与资产同事务写入。**

| 情形 | 判定 | 动作 |
|---|---|---|
| operation 已提交 + checkpoint 缺失 | `RECONCILED` | 补写 checkpoint，不重复写资产 |
| operation 已提交 + checkpoint 有意图无回执 | `RECONCILED` | 同上 |
| operation 未提交 + 无副作用 | `RETRY_SAFE` | 可幂等重试 |
| 摘要矛盾 / 库损坏 | `NEEDS_HUMAN` | **绝不自动重做** |
| 两侧一致 | `NOTHING_TO_DO` | 无动作 |

对账**只依据持久化记录**，不看模型上下文。

---

## 6. operation_id 对账与 UNKNOWN 处理实测

```
资产已提交、checkpoint 停在 asset_pending
→ RECONCILED / ASSET_COMMITTED_RESULT_NOT_RECORDED / auto_retry=False
→ write_after_asset_commit 成功写入
→ 再对账 → NOTHING_TO_DO
→ assert_no_version_double_advance：occurrences=1（只出现一次）
→ assets 仍为 1 条（对账没有重复创建）
```

`NEEDS_HUMAN` 分支的 `auto_retry=False` 有源码级断言（c9）。

**明确不宣称**：跨两库存在全局 ACID 事务；外部系统（GitHub 等）exactly-once。

---

## 7. 索引重建结果

```
rebuild_index: ok=True, indexed=3, a_b_unchanged=True
A/B 指纹前后完全一致
重建前后按仓库查询 count 相同
索引表被删 → query 返回 INDEX_MISSING（不是空列表）
```

**FTS5 实测可用。** 但有一个真实坑：`MATCH 'LI-1'` 因 `-` 被当列限定符而报
`no such column: 1`。已改为整串加双引号成短语查询，并加 LIKE 兜底。

**中文分词限制（如实记录）：** `unicode61` 不切中文，中文全文检索 count=0。
结构化查询不受影响；中文全文检索在报告里标为已知限制，未在本批修复。

---

## 8. 路径和权限安全测试

- **主防线是内部生成 ID**：`asset_id = "SL-A-" + sha256(repository_id, logical_identity, version, hash)[:32]`。
  用户输入只作数据，**不决定文件路径或行 ID**。
- ID 白名单 `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`：路径穿越、空字节、200 字符超长均在模型层拒绝（3 个测试）。
- 辅助黑名单：库路径不得含 `docs/fusion/`、`knowledge/`、`assets/`、`CAPABILITY_CROSSWALK`；
  拒绝时**不创建文件**。
- 敏感字段硬拒：`api_key/token/cookie/secret/password/credential/private_key/authorization/env`。
- 只读目录模拟写失败：报错且**不留下半成品库**。
- **未做真实 ENOSPC/EIO 注入** —— 会影响同机其他会话，已如实标注为实施边界，保持 OPEN。
- **未设自定义数据库文件权限模型**（保持默认 umask），标注为未加强项。

---

## 9. 真实踩到的四个缺陷（本批修掉）

**其一，跨仓库同名被静默合并（最严重）。**
最初 `_asset_id_for` 只用 `(logical_identity, version, hash)`，两库同名记录算出**同一个 asset_id** 撞主键；
`current_view` 也用 `logical_identity` 单列主键。两条本应独立的知识被合并成一条。
修法：asset_id 纳入 `repository_id`；A 唯一约束与 B 主键都改为带 `repository_id`；
所有读写函数的 `current_pointer` / `history` 都要求 `repository_id`。

**其二，`plan_resume` 在库损坏时抛异常而非返回错误**（P1A 遗留，本批续用并修正）。
加 `open_store()` 返回结构化错误。

**其三，对账把"有意图无回执"误判为一致。**
`ck.get("result_digest")` 为 None 时被当成"没问题"，实际那是漏窗。
改为显式分支 `ASSET_COMMITTED_RESULT_NOT_RECORDED`。

**其四，摘要口径不一致。**
`write_after_asset_commit` 用 `{asset_id, pointer_version}` 再算 sha256，
而 `operation_log` 存的是资产 `content_hash` —— 两个不同口径必然不等，下次对账误报 `DIGEST_MISMATCH`。
改为直接写回 `operation_log.result_hash`。

**另：** `FTS5 MATCH` 语法坑（上述）；验收脚本 `with` 块外访问已关闭连接。

---

## 10. 全部测试结果与退出码

```
python3 -m unittest discover -s tests/storage        46 tests   OK       exit 0
python3 tools/f2p1b_verify.py                        16/16 PASS          exit 0
python3 tools/f2p1a_verify.py                        22/22 PASS          exit 0
python3 tools/fusion/f1d_verify.py                   26/26 PASS          exit 0
python3 tools/f2p0_verify.py                         16/16 PASS          exit 0
```

storage 测试分布：knowledge_store 27 / cross_process 6 / error_injection 13。

**失败数 0。**

---

## 11. F1-D 冻结哈希

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变，git 无改动，f1d_verify 26/26 通过。

---

## 12. 未完成门禁

| 门禁 | 状态 | 说明 |
|---|---|---|
| X-5（知识库侧 CAS/崩溃/失败路径） | **SATISFIED_AT_F2P1B** | 真实 4 进程 CAS + SIGKILL + 损坏拒绝 |
| X-5（checkpoint 侧） | SATISFIED_AT_F2P1A | 两批分开记，不互相代替 |
| Y6-P3 审批传递 | **UNVERIFIED** | 审批提示禁用，未造假 PASS |
| Y6-P6 BotHarness 端到端 | **OPEN** | headless 缺凭据 |
| 真实磁盘故障注入（ENOSPC/EIO） | **OPEN** | 未实施，如实记录 |
| D 层 Renderer | **未开始** | 本批只定边界 |
| 分发门禁 B-1/B-2/B-3 | **OPEN** | 未动 |

---

## 13. F2-P1C Collector 最小可执行起点

1. **单源最小抓取**：只取一个上游源的元数据，不做分析、不调模型。
2. **落资产 + 幂等键**：`operation_id` 固定，重复抓取不得重复入库（用 `assets` 唯一约束 + `operation_log` 验证）。
3. **source_snapshot 三字段**：抓取时同时记录 `commit_sha` / `root_tree_sha` / `tree_query_ref`，
   并断言三者不被互相填充（F0 勘误 E-01..E-06 的直接防线）。
4. **跨库协调**：抓取完成 → 写资产 → 联系 checkpoint，故意在中间杀进程，验证对账。
5. **索引重建**：抓完一批后删索引重建，断言 A/B 不变、查询一致。

**F2-P1C 需独立批准，本轮未启动。**
