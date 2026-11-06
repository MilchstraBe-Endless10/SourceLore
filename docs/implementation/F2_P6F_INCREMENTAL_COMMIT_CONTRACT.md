# F2-P6F 逐 Blob 即时提交契约

## D-58 的真正位置

P6E 报告把 D-58 记作「采集流程全采完才落盘」。定位后修正：

**正式路径本来就没有这个问题。**

`src/skill_interface/content_capture.py` 的循环是：

```
for item in eligible:
    got = BF.fetch_blob(...)            # 采一个
    ing = CIC.ingest_captured_blob(...) # 立刻入库（循环内）
```

问题出在 `tools/f2p6e_e2e.py` —— 我上一轮临时写的工具脚本自己另建了一套循环，
把字节攒在内存 dict 里，最后统一落盘。

**这正是任务书禁止的「两条会产生不同结果的执行路径」。**

修法不是给工具脚本补落盘，而是让它走正式路径。

## 契约

对每个选定的 Blob，顺序必须是：

```
从 Tree 取预期 OID
→ 取字节
→ 验长度
→ 算 Git Blob OID 并比对
→ 算 SHA-256
→ 验授权状态（PERSIST_DECISION）
→ 无覆盖发布到内容寻址存储
→ 提交绑定来源的 A 层资产
→ 标记完成
→ 才处理下一个
```

**任何一步失败，已完成的 Blob 不受影响。** 不回滚、不重下。

## 授权在持久化之前

`content_capture` 已经在 `PERSIST_BLOCKED` 时 **不发请求**，而不是「先写后判」。
这是关键：授权判定必须在字节落盘之前，不能等写完再决定合不合法。

## 文件系统与 SQLite 的一致性

两者没有全局原子事务，所以不能假设它们同步。允许的不一致状态：

| 状态 | 处理 |
|---|---|
| 字节已发布、资产未提交 | 孤儿字节文件。下次 `ingest_captured_blob` 按内容寻址会直接复用，不会重复下载 |
| 资产已提交、索引未完成 | 下次查询按 `repository_id+commit_sha+file_path` 找得到，视为已完成 |
| 进程终止 | 重启后按真实 Storage 盘点，**不信内存里的成功列表** |
| 已有内容损坏 | 读回时重新算 sha256，不匹配则不可当作完整资产复用 |
| 并发采同一 Blob | `reused=True`，不覆盖 |

## 状态分离

```
BLOB_FETCHED  → BLOB_VERIFIED  → BLOB_PERSISTED
FACT_PERSISTED → CLAIM_VERIFIED → CLI_QUERY_VERIFIED → CARD_RENDERED
```

前一状态成立**不自动授予**后一状态。

## 整批状态

```
TREE_COMPLETE ≠ SELECTED_BLOBS_COMPLETE ≠ CONTENT_FACTS_COMPLETE
≠ SOURCE_FACTS_COMPLETE ≠ CLAIMS_VERIFIED ≠ KNOWLEDGE_QUERYABLE
```

选定文件没全完成时，整批标 PARTIAL；但已完成文件的知识可以独立查询。
