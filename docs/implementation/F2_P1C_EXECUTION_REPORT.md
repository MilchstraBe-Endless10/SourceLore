# F2-P1C · 执行报告

产物：`F2_P1C_VERIFICATION.json`（22/22）、`F2_P1C_GATE_RESULTS.json`、
`F2_P1C_REAL_GITHUB.json`（真实取数）、`F2_P1C_TREE_ECHO_EXPERIMENT.json`（关键对照实验）、
`F2_P1C_COLLECTOR_ARCHITECTURE.md`

**结论先行：真实 GitHub 固定版本取数成功并完成入库闭环。模拟与真实分开报告，两者都过。**

---

## 1. 真实 GitHub 测试仓库与固定 Commit

| 项 | 值 |
|---|---|
| owner/repo | **octocat/Hello-World** |
| repository_id | **1296269** |
| requested_ref | master |
| commit_sha | **`7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`** |
| root_tree_sha | **`b4eecafa9be2f2006ce1b709d6857b07069b4608`** |
| tree_query_ref | `b4eecafa9be2f2006ce1b709d6857b07069b4608`（本次用的就是 root_tree_sha） |
| 凭据 | **无**（公开只读 API） |
| 请求数 / 字节 | 4 次 / 9,962 字节 |

**过程：**
1. `/repos/octocat/Hello-World` → 200，拿到 repository_id
2. `/commits/master` → 200，拿到 commit_sha 与 **`commit.tree.sha`（这才是 root_tree_sha 的合法来源）**
3. `/git/trees/{root_tree_sha}?recursive=1` → 200，`truncated=false`，1 条目
4. `/git/blobs/{blob_sha}` → 200，Git blob sha1 校验通过

---

## 2. ★ 最关键的一次对照实验：三字段确实不能混用

配额恢复后我专门做了这个对照（`F2_P1C_TREE_ECHO_EXPERIMENT.json`）：

```
用 root_tree_sha (b4eecafa…) 请求 trees → 响应 sha = b4eecafa…  ✓
用 commit_sha    (7fd1a60b…) 请求 trees → 响应 sha = 7fd1a60b…  ✗ 不是 b4eecafa…
                                          条目内容完全一致
```

**结论：Trees API 以请求的 ref 回显 `sha`，即使 ref 是 commit_sha 也不会展开成真实 tree sha。**
这独立复现了 F0 勘误 E-01..E-06 的核心事实，也证明了：

> `root_tree_sha` 只能来自 **Commit 对象的 `commit.tree.sha`**，
> 绝不能从 Trees API 响应里取。

如果当初把 Trees 响应的 `sha` 当成 root_tree_sha，就会把 **commit_sha 记成 tree sha** ——
F0 在 03/04/05/06 四份审计里踩的正是这个坑。

---

## 3. Tree / Blob 获取结果

**Tree：**

```
completeness_status = COMPLETE
entry_count         = 1
truncated_seen      = false
deep_walk_used      = false
sample_paths        = ["README"]
```

只有 1 个条目 —— 这是 Hello-World 的真实结构（一个 README），不是我截断的结果。

**Blob：**

```
path      = README
blob_sha  = 980a0d5f19a64b4b30a87d4206aade58726b60e3
verified  = true          ← Git 对象编码规则校验通过
size      = 13
sha256    = 03ba204e50d126e4674c005e04d82e84c21366780af1f43bd54a37816b6ab340
is_binary = false
```

**Git blob sha1 与本地 sha256 是两个不同身份**：前者是 Git 对象身份，后者是内容完整性校验。
测试里还专门断言「**裸内容 sha1 ≠ Git blob sha1**」：

```
sha1("hello world\n")                  = 不能当 blob sha
sha1("blob 12\0" + content)            = 3b18e512…  ← 正确的 Git 规则
```

---

## 4. source_snapshot 实际结构

```
logical_identity = SL-SNAP-f6a274fe1dbf2cedf71c4cc2492b207b806ec5b8
content_hash     = c15ea91f8d2e561987b8ba1943d52729c28e9a88ef31e9c8c5f18825a739e61f
tree_entry_count = 1
blob_refs_count  = 1
```

身份由 `(repository_id, commit_sha, retrieval_scope, collector_version)` 派生：

- `collected_at` **不进**身份，也不进内容哈希 —— 实测同一快照两次采集身份完全一致
- `requested_ref` 不进身份 —— 换 ref 名但解析到同一 commit 就是同一身份
- 不同 `repository_id` → 不同身份，即使内容一模一样

---

## 5. 错误与限流处理结果

**真实遇到的限流（不是模拟）：**

第一次尝试是在配额已耗尽的状态（`x-ratelimit-remaining: 0`，60/小时）。判定结果：

```
error_code   = RATE_LIMITED        ← 不是 FORBIDDEN，也不是"空仓库"
retryable    = true
retry_after  = 567 秒
http_status  = 403
detail       = "API rate limit exceeded for <IP>…"
```

**处理方式：** 停止请求，等待到 `reset` 时间（约 21 分钟），然后重试。**没有绕过限流，没有重试循环试探。**
（这一点很关键：GitHub 的限流窗口是刚性的，反复试探只会白耗。）

**分类矩阵（全部有测试）：**

| 响应 | error_code | retryable |
|---|---|---|
| 401 | `AUTH_FAILED` | 否 |
| 403 + `remaining=0` | `RATE_LIMITED` | 是 |
| 403 + secondary/abuse 字样 | `SECONDARY_RATE_LIMITED` | 是 |
| 403 其他 | `PERMISSION_DENIED` | 否 |
| 404 | `REPO_NOT_FOUND` | 否 |
| 429 | `SECONDARY_RATE_LIMITED` | 是 |
| 5xx | `SERVER_ERROR` | 是 |
| 超时 | `NETWORK_TIMEOUT` | 是 |

**401/403/404/429/5xx 绝不折成空仓库** —— 有断言 `data is None`。

---

## 6. A/B 入库及幂等结果

```
first  = INGESTED
second = IDEMPOTENT_ALREADY_PRESENT
assets_count          = 1
operation_log_count   = 1
pointer_version       = 1
asset_id              = SL-A-98a06b7a7308346547db9ef2239340e1
operation_id          = OP-COL-e98f77d853740debe2e2054587fce3e7
```

**同一快照重复采集：不重复建资产、不推进指针、不增历史版本。**
`asset_type = repository_snapshot`，payload 里**没有** `verified` / `claim_status`
—— 采集资产不是已验证的 Claim。

---

## 7. 跨库崩溃与对账实测

真实漏窗测试（`test_crash_recovery.py`，真子进程真信号）：

```
资产入库成功 → 打印 ASSET_COMMITTED → SIGKILL 自己（checkpoint 未写）
重启对账：
  reconcile → RECONCILED / ASSET_COMMITTED_RESULT_NOT_RECORDED
  auto_retry = False          ← 不自动重做
  write_after_asset_commit → 补写成功
  再对账 → NOTHING_TO_DO
  assets = 1、operation_log = 1、pointer_version = 1
```

另一条：入库事务中途 SIGKILL → 未提交的采集资产不可见。

---

## 8. 不同仓库资产隔离

- `asset_id` 生成纳入 `repository_id` → 不同仓库必有不同 ID
- A 层唯一约束 `(repository_id, logical_identity, asset_version)` 复合
- B 层主键 `(repository_id, logical_identity)` 复合
- `current_pointer()` **强制要求** `repository_id` 参数
- 实测：两个仓库同一 `logical_identity` → 两条独立资产、两个独立指针

---

## 9. 安全与资源限制

| 限制 | 值 | 有测试 |
|---|---|---|
| 单请求超时 | 20 秒 | ✓ |
| 最大请求数 | 40 | ✓（触发 BUDGET_EXCEEDED） |
| 最大重试 | 3 | ✓（1+3=4 次后停） |
| retry_after 上限 | 120 秒 | ✓（9999 被截断到 5） |
| 最大 Tree 条目 | 2000 | ✓（触发 PARTIAL） |
| 单 Blob 字节 | 1,000,000 | ✓（触发 BUDGET_EXCEEDED） |
| 采集总字节 | 4,000,000 | ✓ |
| 递归深度 | 12 | ✓ |

**路径防护**（全部有测试）：非 `/` 开头、`//` 协议相对、`..` 父目录、`//` 空段一律拒绝；
拼 URL 后二次校验 host 必须是 `api.github.com` 且 scheme 必须是 `https`。

**不执行**获取到的任何仓库代码。**Token 不落**任何产物（有测试把 token 塞进 client 后断言错误详情不含它）。

---

## 10. 补录 P1B 遗留缺陷（题面 §12 要求）

`tests/storage/test_p1b_regressions.py` 逐条覆盖，**每条都是"修复前会失败"的真实 bug**：

| 缺陷 | 回归测试 | 修复前症状 |
|---|---|---|
| asset_id 不含 repository_id | `test_asset_id_differs_by_repository` | 跨仓库同名撞主键、知识被静默合并 |
| result_digest=None 当一致 | `test_intent_only_is_reconciled_not_nothing` | 漏窗被判 NOTHING_TO_DO |
| 摘要口径不一致 | `test_write_then_reconcile_is_consistent` | 补写后下次对账误报 DIGEST_MISMATCH |
| FTS5 连字符语法 | `test_hyphenated_query_does_not_crash` | `no such column: 1` 报错 |
| f1d 作用域未登记 storage | `test_f1d_allowed_prefixes_include_storage` | 批次越界误报 |

**这些不是猜测的缺陷，是有明确复现路径、并且修复前后行为可观测的真实问题。**

---

## 11. 本轮踩到的四个问题

1. **入库 payload 与 content_hash 口径不一致**：最初把 `collected_at` 塞进入库 payload，
   但 `content_hash()` 算的是不含它的 content_payload → 落库哈希与快照哈希不等，
   重采被判 CONFLICT。改成 payload = content_payload，观测时间单列 `observation_record()`。

2. **条目上限 off-by-one**：先 append 再判上限，导致实际能存 limit+1 条。改成先判后加。

3. **`//evil.example/x` 未被拦住**：原来的 `"//" in path.lstrip("/")` 检查在 lstrip 之后失效。
   改为在拼 URL 前显式拒绝 `//` 开头，并二次校验 host。

4. **两个 `test_crash_recovery.py` 模块名冲突**：`tests/collector` 与 `tests/runtime` 同名，
   同进程 discover 会报 "module incorrectly imported"。验收脚本改为**子进程分别跑各目录**。

---

## 12. 新增代码与测试文件

```
src/collector/__init__.py
src/collector/github_client.py          受限客户端 + 错误分类 + 预算
src/collector/tree_collector.py         Tree 枚举 + Blob 读取（Git 对象校验）
src/collector/source_snapshot.py        标准化快照 + 确定性身份
src/collector/ingest_coordinator.py     入库唯一通道 + operation_id 幂等
tests/collector/fake_gh.py              确定性夹具（复现 GitHub sha 回显行为）
tests/collector/test_github_client.py   43 项
tests/collector/test_crash_recovery.py  3 项（真实 SIGKILL）
tests/storage/test_p1b_regressions.py   7 项（P1B 缺陷补录）
tools/f2p1c_real_github.py              真实取数脚本
tools/f2p1c_verify.py                   22 项总验收
docs/implementation/F2_P1C_COLLECTOR_ARCHITECTURE.md
docs/implementation/F2_P1C_EXECUTION_REPORT.md   （本文件）
docs/implementation/F2_P1C_GATE_RESULTS.json
docs/implementation/F2_P1C_VERIFICATION.json
docs/implementation/F2_P1C_REAL_GITHUB.json
docs/implementation/F2_P1C_TREE_ECHO_EXPERIMENT.json
```

---

## 13. 全部测试数量与退出码

```
unittest discover -s tests/runtime      45 tests   OK    exit 0
unittest discover -s tests/storage      53 tests   OK    exit 0
unittest discover -s tests/collector    46 tests   OK    exit 0
f2p1c_verify                          22/22 PASS      exit 0
f2p1a_verify                          22/22 PASS      exit 0
f2p1b_verify                          16/16 PASS      exit 0
f1d_verify                            26/26 PASS      exit 0
```

合计 **144 项 unittest + 86 项验收断言**，失败 0。

---

## 14. F1-D 冻结哈希

```
42841207b8088c8976a625850da12cbdfa6ac0d3ab3283de98a5eebe98c08e0b
```

未变，git 无改动，f1d_verify 26/26 通过。

---

## 15. OPEN 门禁

| 门禁 | 状态 |
|---|---|
| Y6-P3 审批传递 | **UNVERIFIED**（审批提示禁用，未造假） |
| Y6-P6 BotHarness 端到端 | **OPEN**（headless 缺凭据） |
| B-1/B-2/B-3 分发限制 | **OPEN**（未动） |
| 真实磁盘故障注入 | **OPEN**（P1B 遗留，未实施） |
| F2-P2 Facts | 未开始（需独立批准） |

---

## 16. F2-P2 Facts 的最小可执行起点

1. **输入只认已入库的 `repository_snapshot` 资产** —— 不直接读 GitHub，Collector 与 Facts 分层。
2. **一个最小的 Fact 抽取规则**（例如"仓库存在某路径的文件"），不引入 LLM。
3. **Fact 身份必须与快照身份关联**：`fact_id` 派生自 `(snapshot_logical_identity, 规则版本, 抽取参数)`，
   使同一快照 + 同一规则产出稳定身份。
4. **Fact ≠ Claim**：Facts 批次仍不写 `verified`；验证是后续 Evidence-Claims 的事。
5. **失败面**：抽取规则对 PARTIAL 快照的行为必须有明确策略（拒绝还是标注低置信），且要测。

**F2-P2 需独立批准，本轮未启动。**
