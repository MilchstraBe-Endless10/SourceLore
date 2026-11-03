# F1-B / Evidence-Claims 批次 · 检查点（2026-11-03 12:59）

## 做到哪

第B节（统计契约修订）已完成并提交 `0c1f7dd`；第C–F节（Evidence-Claims）处于「候选提取完成、裁决进行中」。

### 已完成（本段会话）

1. **第B节全部完成**，提交 `0c1f7dd`（F1-B 统计契约修订：分批视图与累计视图分离）：
   - `f1b_stats.py` 出向分流 = def 声明 − 晋升；Facts 11/9、Collector 11/5；全局 22/14/107=143。
   - `f1b_verify.py` c11 → 12/12 PASS (exit 0)；`f1b_verify_collector.py` c13/c28 → 30/30 PASS (exit 0)。
   - `F1B_FACTS_DECISIONS.md` 数字表已同步新契约。
2. **第D节候选提取已完成（磁盘实算）**：
   - ROUTED→EC 共 9 条：`U01::C03`(citation existence check)、`U03::C03`(显式未知优于自信猜测/无证据降级为假设)、`U04::C07`(证据三分法)、`U04::C08`(外部探测存档清单)、`U04::C10`(Finding 四段结构)、`U04::C11`(verified-against 新鲜度)、`U05::C05`([NEEDS INPUT] 不编造)、`U05::C06`(Auto-generated 头与出处)、`U06::C05`(四节点数据流逐跳 file:line)。
   - 未审语义命中 5 条：`U03::C01`(边界三分类——偏 Product)、`U03::C06`(产品八要素——偏 Product)、`U04::C09`(Superseded 关系与保留历史)、`U06::C04`(Boundary Gate——偏 Security)、`U06::C07`(验证状态机与 report_tier 映射)。
   - **U06::C06「不可验证即判否」当前 UNREVIEWED**——第E节要求它最终裁决 ADAPT（只取逐跳证据定位设计）并记录「can't prove → FALSE_POSITIVE」语义被拒绝。
3. 已通读 `f1b_build_collector.py`（357 行）与 `f1b_collector_def.py` 结构：def 三件套模式（CANON 列表含 refs 三元组 + DEFERRED_TO_OTHER_MODULE + 可选 PROMOTED_FROM_FACTS）、构建器幂等预剥离、晋升落盘、license per_upstream 聚合、`batches_from_draft` 现算——EC 构建器照此模板写。

## 下一步（按顺序）

1. **语义裁决**（第D/E节），产出 9 条 canonical（新 ID 从 `SL-CAP-0020` 起）：
   - 建议：U03::C01/U03::C06 判给 Product 不进本批；U06::C04 判给 Security；`U04::C09`(Superseded/历史) 归 EC（第C节职责含 historical vs current claim）；`U06::C07`(状态机/report_tier) 归 EC（claim status 与 adjudication 规则）+ U06::C06 以 ADAPT 并入同一或相邻条目，且显式拒绝「不可验证→FALSE_POSITIVE」。
   - U05::C05 的 reason 带 `[NEEDS INPUT]`——承接时不得编造内容，只登记「占位语义」，具体格式留 unresolved。
   - 每条 canonical 需：稳定 ID、唯一 owner_module、来源列表、合并/不合并理由、设计处置、逐源 licence、I/O 边界、V1 scope、unresolved、与 Facts/Collector 的依赖。
2. 写 `tools/fusion/f1b_ec_def.py`（MODULE="Evidence-Claims"，CANON 9 条，无 PROMOTED——9 条 live redirects 直接消费）。
3. 写 `tools/fusion/f1b_build_ec.py`（参照 Collector 构建器；COLLECTOR_IDS 类似改为 EC_IDS=SL-CAP-0020..0028；预剥离本批 9 键分流；晋升 `from:"cross_module_redirections"` 因 live redirects 存在；重建链 Facts→Collector→EC）。
4. 写 `tools/fusion/f1b_verify_ec.py`（30 条左右检查，限 EC ID 范围 + 本批不变量）。
5. 写 `docs/fusion/F1B_EVIDENCE_CLAIMS_DECISIONS.md`（六项 E 约束逐条落章）。
6. 跑构建链 + 三个验证器；第G节十七项验收；更新 PROGRESS/STATE/TASKS/HANDOFF；提交（统计修订已单独提交 0c1f7dd，本批第二提交）；第H节报告。

## 卡在哪

不卡。上下文额度再次熔断（本轮已两次触发换气），非项目阻塞。

## 关键不变量提醒

- 9 条 ROUTED→EC 消费后：MAPPED 22→31，ROUTED 14→5，UNREVIEWED 107 不变（若 U06::C06 ADAPT 并入则再 +1 MAPPED），总数 143 恒定。
- 新 ID `SL-CAP-0020`…起，不重排既有 19 条；`SL-CAP-0007/0008/0009` 的 owner 本轮不动。
- def 文件头部 docstring 要列全导出符号（Collector def 的遗漏是已知 polish 项，不要复制这个缺陷）。
- f1b_stats `_MODULE_DEFS` 需加 `"Evidence-Claims": "f1b_ec_def"`，否则新批次的出向分流计数为 0。
- 检索词：F1B stats revision checkpoint（热记忆已有索引条目）。
