# F2-P1C · Collector 架构

产物：`F2_P1C_REAL_GITHUB.json`（真实取数记录）、`F2_P1C_EXECUTION_REPORT.md`、
`F2_P1C_GATE_RESULTS.json`、`F2_P1C_VERIFICATION.json`

**立场：模拟测试与真实网络测试分开报告。模拟全过不等于真实集成完成。**

---

## 1. 分层

```
github_client.py      受限 HTTP 客户端（错误分类、限流、预算）
tree_collector.py     引用解析 → Tree 枚举 → Blob 读取（Git 对象校验）
source_snapshot.py    标准化快照 + 确定性身份
ingest_coordinator.py Collector → Storage 的唯一入库通道
                      （经 asset_checkpoint_coordinator 做跨库对账）
```

**不重复实现 Storage/Checkpoint** —— 全部复用 F2-P1A/P1B 的既有组件。

---

## 2. 三字段分离（本批最容易出错处）

F0 勘误 E-01..E-06 的核心事实：

> GitHub Trees API 以 commit-ish 为 ref 时，响应里的 `sha` **回显的是请求标识**，
> 而不是它真正展开的 tree 的 sha。

所以：

| 字段 | 唯一合法来源 | **禁止** |
|---|---|---|
| `commit_sha` | `/commits/{ref}` 响应的 `sha` | 不得用 tree 响应的 sha |
| `root_tree_sha` | **Commit 对象的 `commit.tree.sha`** | **绝不用 Trees API 响应的 `sha`** |
| `tree_query_ref` | 本次实际请求用的 ref | 不得与前两者混为一谈 |

`build_snapshot()` 要求三个字段**逐个显式传入**，不做任何自动回填。
夹具 `fake_gh.py` 刻意复现"回显请求 ref"这一行为，测试断言的正是它。

---

## 3. Tree 完整性：三态而非二态

```
COMPLETE    递归或逐层遍历确实走完，且没有截断
PARTIAL     命中资源上限，或逐层遍历本身也被截断
INCOMPLETE  请求失败
```

**`truncated=true` 时绝不直接标 COMPLETE。** 处理路径：

1. 递归返回 `truncated` → 记 `truncated_seen=True`
2. 退回逐层遍历（有 `max_depth` / `max_tree_entries` / `max_requests` 上限）
3. 逐层走完且无截断 → 可为 `COMPLETE`，但 `truncated_seen=True` 必须留痕
4. 逐层仍被截断 → `PARTIAL`，**不得冒充完整**

条目类型归一：`blob` / `tree` / `commit`(submodule) / `unknown`。
`mode` 识别 `symlink`(120000) / `submodule`(160000)。
**不可解析的 type 标 `unknown`，不猜成 blob 或 tree。**

覆盖范围声明：本批只做 `full_tree_enumeration`（全树枚举），
**不声称"全仓库已做语义分析"。**

---

## 4. Blob 校验：用 Git 对象编码，不是裸 sha1

```python
sha1(f"blob {len(content)}\0" + content)
```

题面明确要求。测试直接对照：同一内容的**裸 sha1** 与 **Git blob sha1** 必须不同。

其他要点：
- 只接受 `encoding=base64`，其他编码返回 `MALFORMED`
- 解码失败**不改变原始字节**（`content_bytes` 保留），只把 `is_binary` 置 True
- 单文件超 `max_blob_bytes` → `BUDGET_EXCEEDED`
- 同时核对 `blob_sha` 与独立记录的 `sha256`（Git 身份 vs 本地哈希分离）

---

## 5. 错误契约

错误对象固定字段：`error_code / request_stage / repository_id / commit_sha /
retryable / retry_after / evidence_ref / http_status / detail`。

| 情形 | error_code | retryable |
|---|---|---|
| 401 | `AUTH_FAILED` | 否 |
| 403 + `x-ratelimit-remaining: 0` | `RATE_LIMITED` | 是 |
| 403 + 响应体含 secondary / abuse | `SECONDARY_RATE_LIMITED` | 是 |
| 403 其他 | `PERMISSION_DENIED` | 否 |
| 404 | `REPO_NOT_FOUND` | 否 |
| 429 | `SECONDARY_RATE_LIMITED` | 是 |
| 5xx | `SERVER_ERROR` | 是 |
| 超时 | `NETWORK_TIMEOUT` | 是 |
| 结构异常 | `MALFORMED_RESPONSE` | 否 |
| 预算超限 | `BUDGET_EXCEEDED` | 否 |

**401/403/404/429/5xx 绝不折成空仓库** —— 有专门的测试断言 `data is None`。

限流判定**看响应头与响应体**，不只看状态码：同样是 403，
`remaining=0` 是主限流、有 secondary 字样是次级限流、其余是权限问题，三者分开。

---

## 6. 资源上限（全部可配置且有测试）

```python
DEFAULT_LIMITS = {
    "request_timeout": 20,      # 单请求超时
    "max_requests": 40,         # 采集总请求数
    "max_retries": 3,           # 单请求重试次数
    "max_retry_after": 120,     # 服务端建议等待的上限
    "max_tree_entries": 2000,
    "max_blob_bytes": 1_000_000,
    "max_total_bytes": 4_000_000,
    "max_depth": 12,
}
```

测试覆盖：`max_requests` 触发 `BUDGET_EXCEEDED`、`max_tree_entries` 触发 `PARTIAL`、
`max_blob_bytes` 触发 `BUDGET_EXCEEDED`、`max_retries` 耗尽后不再重试、
`retry_after` 被 `max_retry_after` 截断。

---

## 7. 快照身份

```
logical_identity = SL-SNAP- + sha256(repository_id, commit_sha,
                                     retrieval_scope, collector_version)[:40]
content_hash     = sha256(content_payload)   # 不含 collected_at
```

**确定性规则（都有测试）：**
- `collected_at` 变化 → 身份与内容哈希**都不变**
- `requested_ref` 变化但解析到同一 commit → **同一身份**
- 不同 `repository_id` → **不同身份**，即使内容完全一致
- `completeness_status` 变化 → **内容哈希变化**（PARTIAL 不能冒充 COMPLETE 的内容）

---

## 8. 入库契约

- Collector **只通过** `KnowledgeStore.append_asset_and_advance()` 写入，不碰 A/B/C 表
- 资产类型固定 `repository_snapshot`，**不做任何语义升级**（不写 `verified` / `claim_status`）
- 同快照重复 → `IDEMPOTENT_ALREADY_PRESENT`，不重复建资产、不推进指针、不增版本
- 同 `operation_id` 但内容不同 → `CONFLICT`
- `operation_id` 由 `(repository_id, commit_sha, scope, collector_version)` 派生，**重试不变**

**入库 payload 必须与 `content_hash()` 同口径** —— 这一点踩过坑：
最初把 `collected_at` 也塞进入库 payload，导致落库哈希与快照哈希不等，重采被判 CONFLICT。
观测时间改放 `observation_record()`，不进内容身份。

---

## 9. 跨库协调

复用 P1B 的 `asset_checkpoint_coordinator`：

```
asset 已提交 + checkpoint 缺失        → RECONCILED（补写，不重复写资产）
asset 已提交 + 有意图无回执           → RECONCILED
asset 未提交 + 无副作用               → RETRY_SAFE
摘要矛盾 / 库损坏                     → NEEDS_HUMAN（不自动重做）
两侧一致                              → NOTHING_TO_DO
```

真实漏窗测试：入库成功后 `SIGKILL`（checkpoint 未写），重启对账 →
`RECONCILED` → 补写 → `NOTHING_TO_DO`，资产数仍为 1，指针版本仍为 1。

---

## 10. 安全边界

- 只允许 `https://api.github.com`（拼 URL 时二次校验 host/scheme）
- 拒绝：非 `/` 开头、`//` 协议相对、`..` 父目录穿越、`//` 空段
- **不执行**获取到的任何仓库代码
- Token 只从环境读、只在内存组装 header，**不进日志/checkpoint/snapshot/提交**
- 有测试把 token 塞进 client 后断言错误详情里不含它

---

## 11. 明确不做

- 不实现 Facts / Evidence-Claims / Research / Renderer / 正式 Skill
- 不做多仓库自动关联推断
- 不做非 GitHub 平台适配
- 不抓私有仓库（无合法授权时）
- **不把"GitHub 返回的内容"当成"SourceLore 已验证的知识"**
