# F1-C-C1 · 3 项 DEFER 的归属与承接裁决

产物：
- 裁决数据 `tools/fusion/f1c_c1_decisions.py`
- 应用层 `tools/fusion/f1c_apply_routed.py`（叠加顺序：F1-B 基线 → F1-C-B → 本批）
- 历史不变量 `tools/fusion/f1c_history_invariants.py`（新增，集合级校验）
- 清算记录 `docs/fusion/F1C_C1_RESOLUTION.json`
- 验收 `tools/fusion/f1c_c1_verify.py`

---

## 1. U04::C16 完成检查（三处 Completion Check）

### 结论

**唯一 owner：DSH-Adapter。承接至 SL-CAP-0071（amendment）。**

| 项 | 内容 |
|---|---|
| identity_key | `UPSTREAM-04::C16` |
| 上游来源 | external-probe.md L35；repository-impact.md L30–L32；SKILL.md L127 |
| 原始 disposition | `ADAPT` |
| 旧路由 | `ROUTED → Lifecycle` |
| 最终 owner | **DSH-Adapter** |
| 最终处置 | `ADAPT`（承接已有 canonical + amendment） |
| 承接方式 | SL-CAP-0071 追加「退出判据」三条 |

### 四个必答问题

**1. 它检查的是任务执行完成，还是知识有效性？**
**任务执行完成。** 三处 where 分别是：external-probe.md L35（外部探测做完没）、
repository-impact.md L30–L32（影响分析做完没）、SKILL.md L127（主流程阶段完成没）。
全部是「这一步做完没有」，没有一处涉及「这条知识还成不成立」。

**2. 与 SL-CAP-0071 的职责是否重合？**
**不重合，但存在 gap。** SL-CAP-0071 定义的是「状态怎么记、中断后怎么恢复」
（`current_stage`、`checkpoint_ref`、I-1..I-5），**没有定义「什么算完成」**。
记录状态 ≠ 判定退出条件——本条补的正是这个缺口。

**3. 与 Lifecycle 现有 0040–0045 是否存在实质不同的新职责？**
**不是 Lifecycle 的职责。** 0043 管「变更怎么分类、按什么顺序调度」，
0044 管「影响面怎么找」，两者都讲动作序列，不讲「一次分析任务何时算做完」。
Lifecycle 的视野是「知识随时间是否失效」，本条视野是「这次运行是否收尾」。

**4. 是否可承接至现有 canonical？**
**可以。** 作为 SL-CAP-0071 的 amendment（补充约束），不新建卡——
0071 已拥有任务状态机的全部骨架，缺的只是退出判据这一条。

### 补充的约束（写入 SL-CAP-0071）

```
G-1 阶段完成必须有产出物或显式 skipped 记录（与 SL-CAP-0074 的完整性投影对齐）
G-2 完成判据不得由模型自评——模型声称完成不构成完成证据（承接 I-2）
G-3 判据本身必须可复算：给定同一输入与产出，任何执行者应得出相同结论
```

上游原文（「确认已覆盖」「确认无遗漏」）全是散文要求、无判据，必须翻译成可判定 gate，
否则重蹈 D14。

---

## 2. U05::C10 契约式 Postconditions

### 结论

**唯一 owner：Storage。承接至 SL-CAP-0064（amendment）。**

| 项 | 内容 |
|---|---|
| identity_key | `UPSTREAM-05::C10` |
| 上游来源 | SKILL.md L99–L118 |
| 原始 disposition | `ADAPT` |
| 旧路由 | `ROUTED → Lifecycle`（原分流理由含**双 owner**，本身不合规） |
| 最终 owner | **Storage** |
| 最终处置 | `ADAPT`（承接已有 canonical + amendment） |
| 承接方式 | SL-CAP-0064 追加**写入后**校验步骤 W-2' |

### 五个必答问题

**校验对象是什么？** 是**写盘后的产物本身**——结构、引用、字段约束。
机制原文：「写盘后必须满足的硬条件」。不是任务状态，也不是知识有效性。

**由哪个模块定义成功条件？** Storage 定「什么算合法落盘」的框架；
具体 postcondition 条目来自产物类型所属模块（如 SL-CAP-0025 的溯源字段、
SL-CAP-0074 的阶段完整性）。

**由哪个模块负责执行校验？** **Storage**，在写入路径上逐条核对。

**失败后阻止写入、触发重验证还是终止任务？** **阻止提交**（对应 W-4「版本一致才提交」）。
不回滚已提交的历史对象（A 层只追加），不触发重验证（那是 Lifecycle 的事）。
失败即写回执 `rejected` 并列出未通过条目。

**已有 SL-CAP-0064/0071 或 Lifecycle 能力是否覆盖？** **部分覆盖，有 gap**。
0064 的 W-2 是**写入前**校验（结构完整性与引用完整性）；
本条要求的是**写入后**校验（落盘结果是否满足该产物类型声明的硬条件）。
写入前通过不等于写入后满足——中间还有写入本身可能引入的偏差。

### 补充的约束（写入 SL-CAP-0064）

```
W-2' 提交后、对外可见前，按产物类型声明的 postcondition 逐条核对；
     任一条不满足即拒绝本次提交（写回执 rejected 并列出未通过条目），不得先提交再补救。
硬规则：postcondition 条目必须具名且可逐条核对（上游原文的价值正在于此），
       「数据看起来没问题」不构成校验通过。
       写入前通过（W-2）不能替代写入后校验（W-2'）。
```

### 与 U04-C16 的分野（关键）

- **C16 判「任务做完没」→ DSH-Adapter**
- **C10 判「写对了没」→ Storage**

两者是不同层的退出条件，不得混为一谈。

---

## 3. U01::C12 Eval Baseline

### 结论

**唯一 owner：Evidence-Claims。新建 SL-CAP-0075。**

| 项 | 内容 |
|---|---|
| identity_key | `UPSTREAM-01::C12` |
| 上游来源 | `evals/` |
| 原始 disposition | `ADAPT` |
| 旧路由 | `ROUTED → Evidence-Claims`（两批都指向 EC，但 EC 无对应 canonical——指向悬空） |
| 最终 owner | **Evidence-Claims** |
| 最终处置 | `ADAPT`（新建 canonical） |
| V1 范围 | **V1_REQUIRED**，但**仅离线部分** |

### 五个概念拆分

| 概念 | 归属 |
|---|---|
| A 评测数据与基准任务定义 | **纳入 SL-CAP-0075** |
| B 确定性指标计算 | **纳入 SL-CAP-0075** |
| C 模型辅助评价（judge） | **明确排除于 V1**——依赖外部 provider，与被 REJECT 的 U01-C13/C14 同边界 |
| D 质量门禁与结果报告 | **部分纳入**：本条定「怎么算过」，不定「能否发布」 |
| E 评测执行调度与成本 | **不归本条**——已在 SL-CAP-0070（DSH-Adapter）覆盖 |

### 四个重点判断

**EC 是否真正拥有模型输出整体质量评价的职责？**
复核后**是**，但理由不是路由惯性。判定器的主人必须能证明判定器准：
EC 拥有裁决状态机（0028）、显式未知（0023）、四段结构（0026），
那么「这套判据本身有多准」的校准责任自然归它。
**这不是「判定某条 claim 真假」，而是「判定判据自身是否可信」——层次不同，故需独立 canonical。**

**DSH-Adapter 是否更适合负责评测执行？**
**执行**归它（SL-CAP-0070 已有预算、成本四类、有界修复）；
**判据定义**不归它。F1-B 的 DSH-Adapter 裁决原文即写明
「DSH Adapter 只记录评测运行的执行证据与成本，**不定义质量判据**」——
这句话已把 E 从本条 owner 排除。

**Research 是否应负责研究评测方法？**
否。评测方法是对**判据**的检验，不是对**外部对象**的研究。Research 的研究对象是外部生态。

**是否需要独立 canonical？**
**需要。** SL-CAP-0028 讲单条 claim 的状态迁移，不讲判定器整体校准；强行并入会混淆两个层次。

### 关键区分（用户特别强调）

> **拒绝 U01-C13/C14 的外部 API / 多模型 Judge 实现，不等于拒绝 U01-C12 的离线基准评测。**

本条的 V1 只用 gold 集 + 确定性指标：**完全离线、零外部依赖、可复算**，
与被 REJECT 的方案是两个东西。

### SL-CAP-0075 的核心契约

```
E-1 基准可离线：评测集（gold 输入与标准答案）与确定性指标（精确匹配、召回、
    字段级命中率等）必须能在无外部依赖下复算。V1 不使用任何付费 API。
E-2 指标不得单独定谳：任何单一指标（含 F1）都不得作为「质量达标」的唯一门槛——
    上游 click 案例 F1=0.00 已证明单指标会误判。必须至少两类指标交叉并报告各自数值。
E-3 评测结果必须可追溯：eval_record{基准集版本, 指标名与数值, 被测判据版本, 运行快照}。
边界：不定义「结论真假」（归 0028）、不定义「能否发布」（归 0053）、不管调度成本（归 0070）。
排除：多模型 judge 与直连外部 LLM API 不在本能力范围（U01-C13/C14 已 REJECT）。
```

### 可执行验证条件

- 给定同一 gold 集与同一被测判据版本，重跑评测必须得到相同指标数值（确定性）；
- 评测记录缺 `benchmark_version` / `criteria_version` / `source_snapshot` 任一项 → 判评测无效；
- 只报告单一指标（未交叉）→ 判未达 E-2。

---

## 4. 应用与历史保护

### 应用顺序（不破坏 F1-C-B 机制）

1. 加载 `docs/fusion/F1B_FROZEN_BASELINE.json`
2. 应用 F1-C-B 的全部裁决（8 项 ROUTED 清算 + SL-CAP-0074）
3. 应用本批三项裁决
4. 重算全局状态与进度
5. 检查幂等

**未撤销任何 F1-C-B 已通过的结果，未改动 SL-CAP-0074。**

### 历史验证器补强（第 7 节）

此前各批把 mapped 定格从 `==` 放宽为 `>=`，只保证「数量没减少」，
**没有保证「集合内容没被换掉」**——理论上可以把 A 身份从 canonical X 移除、
同时把 B 身份加入 X，总数不变但语义已错。

新增 `tools/fusion/f1c_history_invariants.py`，三个集合级检查：

| 检查 | 作用 |
|---|---|
| `check_identity_mapping_preserved` | 历史 `identity_key → canonical_id` 映射不得无记录变化；迁移必须来自已登记裁决 |
| `check_canonical_ids_not_reused` | 已有 canonical ID 的 name/owner 不得变更（内容扩展走 amendment，不改身份） |
| `check_amendments_recorded` | 核心字段变更必须同时具备 `f1c_amendments` 留痕与 reconciliation 的 `AMEND_CANONICAL` 记录 |

已接入 `f1b_verify_ec.py`（代表 F1-B 十批）、`f1c_a_verify.py`、`f1c_b_verify.py`，
三者均新增 `c_hist` 检查项并通过。

**未放宽任何不变量**：身份唯一性、三态守恒、许可证隔离、历史迁移留痕全部保持原判据。

---

## 5. 数字

| 项 | F1-C-B 后 | 本批后 |
|---|---|---|
| MAPPED | 120 | **123** |
| ROUTED | 3 | **0** |
| UNREVIEWED | 20 | 20 |
| 合计 | 143 | 143 |
| canonical | 74 | **75** |

新建：`SL-CAP-0075`「离线评测基线与判据校准（拒绝付费 API 与多模型 judge）」。

**REJECT 0 项、DEFER 0 项**——三项全部终裁，无残留延期。

---

## 6. 本批修掉的瑕疵

**批次标记 `F1-F1-C-B`。** 生成器把 `F1-` 与已含 `F1-` 前缀的批次名重复拼接。
已改为直接使用批次名。本批重跑后 SL-CAP-0074 / 0075 的 `created_in_batch` 均为正确值。

**三处历史验证器作用域**（EC c8/c16、Renderer c45、F1-C-B c14）：
EC 的编号集从「固定 20–28」改为「原有 9 条全在 + 允许后续并入」；
Renderer c45 改为「去向必须合法模块」而不硬编码具体目标（去向正确性归裁决批次）；
F1-C-B c14 改为「DEFER 必须有解除条件，解除须有显式裁决记录」。

---

## 7. 下一步：U05 系 11 项 UNREVIEWED

最小执行起点：

1. **先列 U05 系 11 项的完整身份与原始 disposition**（从 `F1C_REMAINDER_BASELINE.json` 现算）。
2. 按「是否已被现有 canonical 覆盖」分组，优先承接、其次新建、最后拒绝。
3. 注意已有覆盖：`U05-C18`（索引生成）已在 SL-CAP-0062；`U05-C22/C23` 已在 SL-CAP-0064/0065；
   `U05-C04/C14/C19` 已于 F1-C-B/C1 处理——这 6 项不重复。
4. 剩余 11 项中需重点关注 `U05-C12`（渐进式 AI 投喂）、`U05-C13`（C4 强制顺序）、
   `U05-C15`（发布节奏）、`U05-C16`（测试用例维护触发）、`U05-C21`（冲突处理）、
   `U05-C25`（测试覆盖作为质量证据）。

F1-C-D 再统一实施 `terminal_disposition` 与交叉表冻结。
