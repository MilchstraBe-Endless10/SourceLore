# F2-P6E 请求 DAG

## 为什么需要这一层

P6C 建了 `request_budget.py`，但它只在**采集内部**生效。
P6D 的教训写得很清楚：预算模块不管验收编排，结果连续三轮在同一份 60/小时配额上折损。

本轮把「一次 E2E 要几次请求」提到编排层。

## 三个分类，不合并

```python
certain_requests      依赖都已解析 → 确定要发
conditional_requests  依赖前序响应 → 条件要发
optional_requests     可做可不做
```

输出两个数：

```
minimum_required_requests = len(certain)
maximum_planned_requests  = len(certain) + len(conditional)
```

**不把未解析依赖伪造成确定值。** 任务书 §3.4 明确要求这一点。

## 去重键

```python
(method, endpoint, immutable_target_identity, repository_id, commit_sha)
```

同 Commit 的同 Blob 只发一次。**不同 Commit 或不同仓库绝不合并** —— 后两项就是干这个的。

## 省请求的三种情形

| 情形 | 省掉的请求 |
|---|---|
| 已知固定 commit_sha | `GET ref`（直接从 sha 取 commit/tree） |
| 已知 root_tree_sha | `GET commit`（改为 optional） |
| Tree 已在本地 | `GET tree` |
| Blob 字节已在本地且完整 | `GET blob` |

每一条都对应一个可验证条件，不是拍脑袋估的。

## is-plain-obj 的估算

全冷启动、取 LICENSE/README/package.json/index.js：

| 操作 | 次数 | 确定性 |
|---|---|---|
| repository metadata | 1 | 确定 |
| resolve ref | 1 | 确定 |
| commit detail | 1 | 确定（拿到 tree sha 需要它） |
| root tree | 1 | 确定（真正拿到后 blob OID 才确定） |
| blob × 4 | 4 | **条件**（OID 依赖 tree 响应） |

`minimum = 4`，`maximum = 8`。

这解释了为什么任务书说「不要再写约 5 次」——4 个 blob 各自一次，加上元数据/ref/commit/tree 四次，
冷启动是 **8**，不是 5。

若 commit 已知（不必解析 ref）：7。若 tree 也已知：6。

## 阶段

```
PREFLIGHT → IDENTITY_VERIFIED → AUTHORIZATION_VERIFIED → TREE_AVAILABLE
→ BLOBS_CAPTURED → KNOWLEDGE_PERSISTED → KNOWLEDGE_VERIFIED
→ INSTALLED_SKILL_QUERY_PASSED → CARD_RENDERED → OFFLINE_REUSE_VERIFIED
```

十个阶段，顺序不可跳。`plan_state` 只按已完成阶段推进，**不会因为 preflight 通过就说采集成功**。

## 暂停状态

```
PREFLIGHT_BUDGET_BLOCKED  REMOTE_RATE_LIMITED  AUTHORIZATION_BLOCKED
BLOB_CAPTURE_INCOMPLETE   FACTS_INCOMPLETE     VERIFICATION_INCOMPLETE
INSTALLED_SKILL_FAILED    E2E_COMPLETE
```

每个状态都能指出「停在哪、缺什么」，而不是一个笼统的 FAILED。
