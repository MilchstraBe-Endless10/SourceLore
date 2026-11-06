# F2-P6D 检查点 · 基线 625cc71 · Crosswalk 复算匹配

## 任务1 结论：plan 与执行的"不一致"已查明
P6C 的场景是：**先 plan（那时资产缺失）→ 再采集（资产入库）**。
C 里我贴的计划输出是采集前生成的，`reused=3` 是采集后的执行结果 —— 时序不同，不是判定分歧。

本轮实测同状态下：
```
--plan  → estimated_requests=0
          README.md      CLAIMS_VERIFIED
          package.json   CLAIMS_VERIFIED
          index.js       CONTENT_CAPTURED_BUT_NOT_PARSED
实际执行 → net=0, reused=3, 三个 ALREADY_CAPTURED
```
**一致**。但任务书要求的不止解释，还要机制保证 —— 本轮补：
- 统一上下文标识（repository_id/commit/data_root/plan_id/inventory_digest）
- plan 与执行复用同一只读完整性判定函数
- 计划生成后存储变化 → `PLAN_STALE_REVALIDATED`

## 待办
1. capture_plan_consistency.py（上下文标识 + 失效重校验）
2. semantic_coverage.py（区分 PARSE_COMPLETE / UNSUPPORTED_SEMANTIC_FORM / VALID_EMPTY_RESULT）
3. is-plain-obj 真实 ESM 仓库采集
4. 多仓库隔离 + 卡片 + 离线
5. Gold ≥20 + 测试 + 文档 + 提交

## 已建两个模块（2026-11-06 15:50）
**`src/collector/capture_plan_consistency.py`**
- `database_identity(root)`：绝对路径 sha256 前16，输出脱敏为 `…/<basename>`
- `inventory_digest(objects)`：按 (path, oid, state, planned) 排序后 sha256 前24
- `build_plan_context` / `finalize_plan` → plan_id + inventory_digest
- `revalidate(plan, fresh, data_root, repo, commit)` →
  `PLAN_FRESH` / `PLAN_STALE_REVALIDATED` / `PLAN_CONTEXT_MISMATCH`
  三种都返回 `use_inventory=fresh`，**永不按旧计划发请求**

**`src/source_analysis/semantic_coverage.py`**
- 状态：PARSE_COMPLETE / SUPPORTED_FACTS_EXTRACTED / VALID_EMPTY_RESULT /
  UNSUPPORTED_SEMANTIC_FORM / PARSE_FAILED / SOURCE_CONTENT_NOT_CAPTURED /
  SOURCE_FACTS_NOT_PERSISTED
- `detect_unsupported_forms`：有界识别 module.exports / exports. / require( / import(
- 实测：CJS → UNSUPPORTED_SEMANTIC_FORM（**不再误报为空**）；
  ESM 有事实 → SUPPORTED_FACTS_EXTRACTED；无未支持形态的 0 事实 → VALID_EMPTY_RESULT
- `SUPPORTED_RULE_FAMILIES` 只列真实具备的三族，不吹「完整理解 JS」

## 下一步
is-plain-obj 真实采集：先 --plan，再按预算执行

## ★ GitHub 配额耗尽（2026-11-06 15:51）
```
GET /rate_limit → 200, remaining 0/60, reset 在 2614 秒后（≈43 分钟）
```
按任务书 §6.3：**输出计划并停止，不长时间等待**。

上一轮 P6C 结束时 remaining 曾归零；本轮会话开始到现在的探测又消耗了一次配额窗口。
**is-plain-obj 真实采集无法在本轮完成。**

因此 E~L、M 门禁（真实 ESM 仓库）只能是 BLOCKED。不能用 is-number 的数据冒充第二个仓库。

## D-53 已修（2026-11-06 15:52）
`github_knowledge_extract` 原本 0 事实一律报 VALID_EMPTY_RESULT → 语义误报。
现在接 `semantic_coverage`：
```
is-number index.js → analysis_coverage = UNSUPPORTED_SEMANTIC_FORM
  recognized_but_unsupported_forms: [commonjs_module_exports]
  不再说"该文件没有导出"
```
