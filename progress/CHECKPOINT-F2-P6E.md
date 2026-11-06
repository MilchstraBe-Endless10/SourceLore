# F2-P6E 检查点 · 基线 59b3c1d · Crosswalk 复算匹配

## 配额现状（2026-11-06 17:09）
```
GET /rate_limit → 200
remaining 0/60，reset 118 秒后
```
策略：**先写编排器，等 reset 后一次性执行**，不在等待期反复探测（每次探测都算请求）。

## 本轮要交付
A. 验收级全局请求预算编排器
B. is-plain-obj 真实 ESM 知识闭环

关键设计：把「一次 E2E 要几次请求」事先算清，再决定是否动手。
P6D 的教训就是这个 —— 预算只在采集内部生效，不管验收编排。

## 编排器已建成（2026-11-06 17:15）
**`src/collector/acceptance_request_planner.py`**
- `AcceptanceRequestPlan`：节点含 request_node_id / operation / endpoint /
  source_object_identity / depends_on / cache_state / cost / execution_status /
  actual_response_headers / local_reuse_reference
- 三类计数：certain / conditional / optional，输出 min 与 max
- `dedup_key = (method, endpoint, identity, repository_id, commit_sha)`
- 十个阶段 + 八个暂停状态
- `preflight`：三条件同时满足才放行

**`src/collector/acceptance_execution_coordinator.py`**
- `Coordinator.call()`：每次请求前 `can_spend`，每次请求后 `consume` 按真实头更新
- 超预算抛 `BudgetExhausted`，限流抛 `RATE_LIMITED:<kind>`
- `run_repo_identity`：metadata → ref → commit → tree

## 修的真缺陷
**D-55 LICENSE 重复计数**：`target_paths` 已含 LICENSE 时，`license_path` 又追加一次
→ blob 节点 5 个而不是 4。修：`dict.fromkeys` 去重。
修复后实测 `GET blob` 从 5 → **4**，冷启动范围 2~7。

## 估算（冷启动，is-plain-obj）
```
metadata 1 + ref 1 + tree 1 + blob 4 = 7 上限
minimum 2（metadata + ref 已知时）
```
任务书要求「不要写约 5 次」—— 4 个 blob 各占一次，这就是为什么是 7 不是 5。

## 配额
三次探测全 0（reset 不断后移），说明同 IP 有别的进程在花。
改用后台等待 reset 后一次性采集，不在等待期反复探测。

## 又修两个缺陷（2026-11-06 17:17）
**D-55 LICENSE 重复计数**：`target_paths` 含 LICENSE 时 `license_path` 又追加
→ blob 节点 5 个。改 `dict.fromkeys` 去重 → 4 个。

**D-56 计数口径不一致**：`counts()` 把 `LOCAL_REUSE` 节点计入 certain，
而 `by_operation()` 排除它们 → 同一个计划出现两个互相矛盾的数。
实测"全部已存"时 counts 报 need=5 而 by_op 全是 0。修：counts 跳过复用节点。
修后"全复用"→ need=0；冷启动→ 2~7。

## 验收器
`tools/f2p6e_verify.py`：12 项检查全过
（MIN_MAX_SPLIT / BLOB_COUNT_4 / REUSE_ZERO / NO_HEADER_BLOCKS /
BUDGET_OK / RATE_LIMIT_BLOCKS / PLAN_FRESH / STALE / CONTEXT_MISMATCH /
CJS_UNSUPPORTED / VALID_EMPTY / ISOLATION_ROW）

## 测试
acceptance_orchestration 25 项全绿

## ★ 配额持续归零（2026-11-06 17:08–17:19 观测）
```
17:08  remaining 0, reset 118s
17:11  remaining 0, reset 860s
17:14  remaining 0, reset 721s
17:15  remaining 0, reset 662s
17:19  remaining 0, reset 372s
```
reset 时间每次都在往后推移，remaining 始终 0 ——
说明**同 IP 上其他客户端在持续消耗**，不是 SourceLore 自己的问题。

## 结论
本轮真实采集（is-plain-obj）按任务书 §6.3 停止。
G~O 门禁将标 BLOCKED，不用 is-number 冒充第二仓库。
