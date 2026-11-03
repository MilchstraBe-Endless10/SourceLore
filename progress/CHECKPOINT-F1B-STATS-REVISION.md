# F1-B 统计契约修订 · 检查点（2026-11-03 12:48）

## 做到哪

第B节（统计契约修订）核心缺陷已修复并重跑验证通过，Evidence-Claims 批次（第C–F节）尚未开始。

### 已完成的修复（本轮）

1. `tools/fusion/f1b_stats.py`
   - 删除 `SOURCE_MODULE`（按上游前缀推断归属是错误口径）。
   - 新增 `_MODULE_DEFS` + `_module_def()`：出向分流的权威 = 各模块 def 文件的 `DEFERRED_TO_OTHER_MODULE` 声明，减去 `promoted_keys(draft)` 已被消费的键。
   - `batches_from_draft` 的出向计数改为 `len(declared - promoted)`，不再读落盘的 `cross_module_redirections`（那是残影，不完整）。
2. `tools/fusion/f1b_build_facts.py` §3
   - `other_out` 循环跳过 `promoted_elsewhere`（从既有草稿的 `routed_promotions` 读，`to_canonical_id` 不在 `FACTS_IDS` 的晋升键），晋升身份不再写成幽灵分流记录。

### 重跑验证（真实退出码）

- `python3 tools/fusion/f1b_build_facts.py` → 退出 2（设计内：草稿已含 Collector 条目，防抹除守卫，未写盘）
- `python3 tools/fusion/f1b_build_collector.py` → 退出 0，`RESULT: OK`
- 草稿批次核对（磁盘实读）：
  - `F1-B/Facts`: ids 10 / mapped 11 / redirected **9** ✅（11 声明 − 2 晋升）
  - `F1-B/Collector`: ids 9 / mapped 11 / redirected **5** ✅
  - `batch_summary` = F1-B/Collector，`batches[-1]` 一致 ✅
  - 全局 22 / 14 / 107，sum 143 ✅；redirects 14 / promotions 2 ✅

## 下一步（按顺序）

1. 改写 `tools/fusion/f1b_verify.py` c11：批次数字从 `batch_summary`（`raw_mapped_to_this_module`/`canonical_count`）读，全局数字从 `global_state_counts` 读（现在还读旧键 `raw_mapped_to_facts`，会 KeyError）。
2. 适配 `tools/fusion/f1b_verify_collector.py`：多 `batches` 条目、`state_counts`/`b3_placeholder` 已删。
3. 跑两个验证器，留 12/12、30/30 证据。
4. 单独提交统计契约修订（含改动前后证据）。
5. 开始第C–F节：Evidence-Claims 候选提取（9 条 ROUTED→EC + 未审扫描 + U1/U2/U3/U4/U6 焦点区），语义裁决、新 ID 从 `SL-CAP-0020` 起、def/builder/verifier 三件套、`docs/fusion/F1B_EVIDENCE_CLAIMS_DECISIONS.md`。
6. 第G节十七项验收 → 更新 PROGRESS/STATE/TASKS/HANDOFF → 提交 → 第H节报告。

## 卡在哪

不卡。熔断是会话上下文额度耗尽，非项目阻塞。

## 关键不变量（续跑必读）

- 重建顺序 Facts → Collector → (新 EC builder) → 验证器；Facts 重建后必须跟 Collector 重建。
- 出向分流权威是 def 声明减晋升，永不读落盘 redirects 计数；晋升身份不得同时出现在 MAPPED 和 ROUTED。
- `SL-CAP-0001…0019` 不动；新 ID 从 `SL-CAP-0020`；`UPSTREAM-06/C06` 最终 ADAPT。
- 本轮只做统计契约修订 + Evidence-Claims，不进 F2。
