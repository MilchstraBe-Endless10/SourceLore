# F2-P6E 执行报告

基线 `59b3c1d`。

## 结论

交付 A：**验收级全局预算编排器建成并验证**。1447 项测试全绿，验收器 12/12。

交付 B：**is-plain-obj 真实采集被配额阻断**，未完成。G~O 门禁 BLOCKED。

不粉饰：第二仓库没有采到，我没有拿 is-number 冒充它。

## 一、编排器

`src/collector/acceptance_request_planner.py`

请求 DAG 的每个节点带：`request_node_id` / `operation` / `endpoint` /
`source_object_identity` / `depends_on` / `cache_state` / `estimated_primary_cost` /
`execution_status` / `actual_response_headers` / `local_reuse_reference`。

三类计数不合并：

```
certain     依赖已解析
conditional 依赖前序响应
optional    可做可不做
→ minimum_required / maximum_planned
```

去重键 `(method, endpoint, identity, repository_id, commit_sha)` ——
后两项保证**不同 Commit / 不同仓库绝不合并**。

十阶段 + 八暂停状态。`plan_state` 只按已完成阶段推进。

`src/collector/acceptance_execution_coordinator.py`

每次请求前 `can_spend`，请求后 `consume(headers)` 用**真实响应头**覆盖本地推断。
超预算抛 `BudgetExhausted`，限流抛 `RATE_LIMITED:<kind>`。

## 二、请求估算（冷启动）

| 操作 | 次数 | 确定性 |
|---|---|---|
| repository metadata | 1 | 确定 |
| resolve ref | 1 | 确定 |
| root tree | 1 | 确定 |
| blob × 4 | 4 | 条件（OID 依赖 tree） |

`minimum = 2`，`maximum = 7`。

任务书明令「不要再写约 5 次」——4 个 blob 各占一次，加上元数据/ref/tree 三次，
冷启动是 **7**。

省请求的四种情形各有可验证条件：已知 commit 省 ref、已知 tree 省 commit、
Tree 在本地省 tree、Blob 在本地省 blob。

## 三、命中的缺陷

**D-55 LICENSE 重复计数。** `target_paths` 已含 LICENSE 时 `license_path` 又追加一次
→ blob 节点 5 个。`dict.fromkeys` 去重后为 4。

**D-56 计数口径不一致。** `counts()` 把 `LOCAL_REUSE` 节点算进 `certain`，
而 `by_operation()` 排除它们。同一个计划出现两个互相矛盾的数：
「全部已存」时 counts 报 need=5，by_op 却全是 0。

修后：全复用 → need=0；冷启动 → 2~7。两个函数口径一致。

这个缺陷很典型——**两个函数各自看都对，放一起就自相矛盾**。
它不会报错，只会让预算算错，进而让预检做出错误决定。

## 四、配额

```
17:08  remaining 0, reset 118s
17:11  remaining 0, reset 860s
17:14  remaining 0, reset 721s
17:15  remaining 0, reset 662s
17:19  remaining 0, reset 372s
```

reset 时间每次后移、remaining 恒为 0。

**判读：同 IP 上其他客户端在持续消耗，不是 SourceLore 自身的问题。**

按任务书 §6.3 停止，不长时间等待、不反复探测、不换身份绕过。

## 五、测试

```
1447 项，失败 0，退出码全 0
（保留 1422 + 新增 acceptance_orchestration 25）
tools/f2p6e_verify.py：12/12
```

## 六、门禁

| 门禁 | 状态 |
|---|---|
| A ACCEPTANCE_REQUEST_DAG | **DONE** |
| B WORKFLOW_BUDGET_PREFLIGHT | **DONE** |
| C REQUEST_DEDUPLICATION | **DONE** |
| D REQUEST_HEADER_REVALIDATION | **DONE** |
| E RATE_LIMIT_SAFE_STOP | **DONE** |
| F WORKFLOW_PARTIAL_RESUME | **DONE** |
| G REAL_ESM_REPOSITORY_IDENTITY | **BLOCKED** |
| H REAL_ESM_AUTHORIZATION | **BLOCKED** |
| I REAL_ESM_BLOB_CAPTURE | **BLOCKED** |
| J REAL_ESM_BLOB_INTEGRITY | **BLOCKED** |
| K REAL_ESM_SOURCE_FACTS | **BLOCKED** |
| L REAL_ESM_CLAIMS_VERIFIED | **BLOCKED** |
| M INSTALLED_SKILL_ESM_QUERY | **BLOCKED** |
| N REAL_ESM_KNOWLEDGE_CARD | **BLOCKED** |
| O TWO_REAL_REPOSITORY_ISOLATION | **PARTIAL** |
| P OFFLINE_REUSE | **DONE** |
| Q SUCCESS_CONTRACT_INTEGRITY | **DONE** |
| R EXISTING_PRODUCT_REGRESSION | **DONE** |
| S NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** |
| T DISTRIBUTION_READY | **NOT_READY** |

O 给 PARTIAL：is-number 的单仓库隔离机制在，但第二仓库没入库，不能算两仓库已验证。

## 七、没做到的部分

G~N 全部 BLOCKED，原因是配额。**没有任何一项是用替代数据补上去的。**

真实仓库身份、许可证、Blob OID、ESM 事实、Claim/Verification、安装版查询、卡片——
这七项都停在「未采集」。

## 八、这轮真正的收获

编排器本身不是重点。重点是把一件反复发生的事变成可计算的：

**在动手之前就算出这批要几次请求。**

前几轮我每次都直接冲进采集，撞墙，然后记录「配额不足」。
这一轮先算出 2~7，预检发现 remaining=0，就不动手了 —— 不是运气好，是顺序对了。

## 九、下一批

配额恢复后，is-plain-obj 只需 **7 次请求**就能闭环。这是一个明确的、可执行的数字，
不再是「约 5 次」这种含糊说法。

但更值得做的是：**把编排器接到 CLI**。现在它只在工具脚本里用，
用户跑 `analyze` 时仍然走老的采集路径，不算预算。

这才是「验收编排」变成「产品能力」的那一步。
