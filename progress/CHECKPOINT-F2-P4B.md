# F2-P4B 检查点（中途落盘）

**基线**：8c8aabf · Crosswalk sha256 `42841207…` 已验证未变

## 已完成

**canonical 提取**（不猜 ID）：`docs/implementation/F2_P4B_RESEARCH_CANONICAL_AUDIT.json`

Research 模块 = `owner_module == "Research"` 的 5 条：

| ID | 名称 | copy_permitted |
|---|---|---|
| SL-CAP-0035 | 有界研究阶段流水线（R0–R4） | True |
| SL-CAP-0036 | 由广到窄查询策略与来源去重 | True |
| SL-CAP-0037 | 来源类型标记与覆盖记录（优先级不替代验证） | True |
| SL-CAP-0038 | 研究质量状态与结论边界（三态 + 不产报告许可） | **False** |
| SL-CAP-0039 | 内联引用约束与可追溯性 | True |

## 三条硬约束（来自 canonical 的 f1c_amendments）

1. **SL-CAP-0037 补充反例**：来源优先级**只能**用于"先看哪个资料"的取数次序，
   **不得**用于判定 claim 真伪，**不得**作为 report_tier 输入（后者归 SL-CAP-0028）。
   → 直接对应题面 §7「不得用可信度分数替代 EC 裁决」。

2. **SL-CAP-0038 补充**：报告间冲突**只做分辨与分流**，不得另建第二套状态机；
   结论状态只有 SL-CAP-0028 一处。
   → 直接对应题面 §1「Research Packet 不是新的 Claim 裁决状态机」。

3. **SL-CAP-0039**：每条实质性陈述必须内联引用 Evidence-Claims 的 ID；
   无引用的陈述只能是 inference/unknown，不得以肯定事实语气出现。
   → 直接对应题面 §5「没有来源的 finding 不得进入可采信结论集合」。

## 三个缺口（如实记录，不冒充已实现）

| 缺口 | 原因 | 处理 |
|---|---|---|
| SL-CAP-0036 假定外部采集（GitHub 元数据/README/Issue） | 本批明令禁止抓取 | 只实现**本地已登记资产**的结构化检索，缺口如实记录 |
| SL-CAP-0035 R0–R4 面向完整研究 | 本批只做最小确定性检索 | 实现 R1「内读」层的等价物：只消费已有确定性产物，不发起采集 |
| SL-CAP-0038 含 UPSTREAM-06（无许可证） | copy_permitted=false | 独立实现，**不复述其原文表达** |

## 尚未完成

1. `src/research/` 七个模块
2. `tests/research/` 六个测试文件 + gold/
3. `tools/{f2p4b_verify,f2p4b_e2e_replay,f2p4b_stats_audit}.py`
4. §13 P4A 两项回归核验（assembled_at / preview_allowed）
5. §14 离线 Gold 集（20 类）
6. 文档 + 账本 + 提交

## 关键设计（续跑必读）

- 输入权威 = `KnowledgeView`（P3D 输出），`rendered_card.json` 只作辅助展示，
  **不得**成为独立证据权威；**禁止**解析 HTML 恢复 Claim/Evidence
- 覆盖状态与 EC 裁决**正交**：`ANSWERABLE_FROM_EXISTING_EVIDENCE` 不是 `supported`
- 「查询没找到」≠「Claim 为假」；「找到 insufficient」≠「检索失败」
- 结果截断必须显式标记；LIMIT 后没出现**不等于不存在**
- 排序：范围匹配 → 仓库 → Commit → claim_type → 证据完整 → 限制可定位 → 稳定 ID
