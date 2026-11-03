# F1-C-A · 归属争议裁决与遗留基线核对

产物：`docs/fusion/F1C_DECISION_REGISTER.json`（判决登记表，F1-C 全批次共用）
基线：`docs/fusion/F1C_REMAINDER_BASELINE.json`（由 `tools/fusion/f1c_a_baseline.py` 只读现算）
验收：`tools/fusion/f1c_a_verify.py`

本批**只裁决两处归属争议、核清遗留基线、提出终态模型建议**。
不处理 31 项遗留身份，不启动 F1-D 或 F2，不改动任何既有 owner 或 canonical。

---

## 1. 裁决一：`U06::C25` 三态产物契约

### 结论

**唯一建议 owner：Storage。保持现状，不迁移。**

### 证据（逐字引原文，不靠「三态」两个字联想）

| 字段 | 内容 |
|---|---|
| capability | 三态分离的产物契约（run-metadata / 各阶段 JSON / 报告） |
| mechanism | **每个阶段写自己的 JSON，报告层只聚合；跳过阶段在输出里显式缺失而非空对象** |
| where | SKILL.md L1122–L1206；phase6 L7–L58 |
| disposition | REIMPLEMENT |
| why | 上游的产物契约是「一阶段一文件」，没有统一实体模型，也没有新鲜度与失效语义。SourceLore 的 Claim/Evidence 必须自建，不能沿用 |
| license | `spdx: null`、`copy_permitted: false` |

### 五个子问题的回答

**A. 若主要定义真实性或证据裁决，是否应由 Evidence-Claims 负责？**
→ 不符合。mechanism 全句没有一个字涉及「证据是否足以支撑结论」。它谈的是产物**怎么写、怎么聚合、缺失怎么表示**。

**B. 若主要定义持久化产物的存在与完整性，是否应由 Storage 负责？**
→ 符合。三件事全部是存在性与完整性：
一阶段一文件的落地形态、报告层的聚合方式、**跳过阶段必须显式缺失而不是留空对象**。
第三条尤其关键——它防的是「用空值冒充已完成」，这与 Storage 的 SL-CAP-0071
「工具执行成功与模型生成成功必须分开记录」同属**执行证据完整性**。

**C. 若同时涉及两层，哪一层拥有唯一语义定义权？**
→ 不涉及两层。该能力只描述产物的存在形态，不产出任何「这条证据够不够」的判断。

**D. 现有 EC canonical 是否已覆盖其语义，是否无需新增 canonical？**
→ EC 侧（SL-CAP-0020 证据存档 / SL-CAP-0023 显式未知 / SL-CAP-0028 裁决状态机）覆盖的是
「证据与结论的支持关系」，与本条「产物在不在」是不同问题，不构成语义重复。

**E. 原始处置的限制。**
→ `REIMPLEMENT` 意味着只借「一阶段一产物、跳过阶段显式缺失」这个取向，不复制其模板与脚本；
且 `copy_permitted: false`（UPSTREAM-06 无许可），本条不得逐字搬运上游产物格式。

### 为什么不改

Crosswalk 原判就是 Storage。本批**未做任何改动**——裁决与原判一致，无迁移动作。
`F1C_DECISION_REGISTER.json` 的 `applied_changes_this_batch` 为空数组，可核。

### 潜在影响

该身份**仍未被任何 canonical 承接**（`UPSTREAM-06::C25` 当前是 ROUTED，不是 MAPPED）。
Storage 的 SL-CAP-0062 只覆盖四层资产模型，**未显式定义「阶段产物一阶段一文件 + 跳过阶段显式缺失」**。
是否新建 canonical 或在 0062 上追加语义，留 F1-C-B 决定。

### 被否决的替代方案

迁至 Evidence-Claims —— 否决理由：原文无证据充分性语义，仅凭措辞联想，属误判风险。

---

## 2. 裁决二：`SL-CAP-0009` Canonical Knowledge Registry

### 结论

**唯一建议 owner：Facts。保持现状，不迁移、不拆分。**

### 证据（四项字段内容 + 输入输出来源）

| 字段 | 内容 | 指向 |
|---|---|---|
| name | Canonical Knowledge Registry（实体消解权威清单） | 语义消解 |
| description | 维护机器可读的实体权威清单：名字、别名、类型、路径、来源。所有事实引用必须指向注册表中的条目，别名冲突与合并必须留痕；无法归入现有条目且不足以新建条目的，进入受控的待定出口而非静默丢弃 | **规则与决策** |
| input_boundary | SL-CAP-0001 的文件与符号清单 | Facts 自己的产出 |
| output_boundary | registry.json: entries[] + aliases + merge/split 记录 | **决策留痕** |
| unresolved | 上游允许内部草稿，必须落成机器可读文件；「不够格当 Unknown」的补充出口尚未定义 | 语义裁定 |

### 三个候选结果的选择

**结果 1（保持 Facts，明确 Registry 只定义语义身份消解）—— 采纳。**
理由：description 全句都在讲「名字/别名/类型/路径/来源如何归一、冲突如何留痕、不够格的去哪里」，
输出是 merge/split **记录**而不是存储布局。这是「什么叫同一个实体」的裁决规则。

**结果 2（迁至 Storage，为 Facts 保留调用接口）—— 否决。**
理由：Storage 的 SL-CAP-0062（四层模型、单一权威、并发 CAS）与 SL-CAP-0064（原子写入）
已经完整覆盖持久化一面。迁移会让两条 canonical 描述同一件事，制造「同一事实两个 owner」，
违反第 4 节「不能让 Facts 和 Storage 各自维护一套可独立修改的权威实体登记表」。

**结果 3（拆分为不同职责）—— 否决。**
理由：现有 Storage canonical（0062 + 0063 + 0064）已完整承接持久化与身份/版本一面，
拆分只会**重复造卡**，正是第 4 节要避免的。

### 语义边界（本裁决的核心界定）

> **Registry 定义「什么叫同一个实体」；Storage 定义「这条实体记录怎么安全落地」。**

一句话划线，避免两边都碰。

### 为什么不改

Crosswalk 原判就是 Facts。`applied_changes_this_batch` 为空，无静默修改。

### 剩余不确定性

description 里「所有事实引用必须指向注册表中的条目」这句容易被读成持久化约束。
是否在 F1-C-B 修订该描述、增加一句边界声明，留待裁定——**本批不改内容**。

---

## 3. 遗留身份基线

数据源：`tools/fusion/f1c_a_baseline.py` **只读现算**（集合运算），无人工录入固定数。

| 项 | 值 |
|---|---|
| 原始身份 | 143 |
| MAPPED | 112 |
| ROUTED | 11 |
| UNREVIEWED | 20 |
| **遗留合计** | **31** |
| 守恒校验 | 112 + 11 + 20 = 143 |

### 11 项 ROUTED 的模块分布

| 目标模块 | 数量 | 模块批次是否已完成 |
|---|---|---|
| Evidence-Claims | 5 | 已完成 |
| Lifecycle | 4 | 已完成 |
| Renderer | 4 | 已完成 |
| Storage | 1 | 已完成 |

**全部 4 个目标模块的批次都已完成，但这些身份没被承接。** 这是 F1-C-B 要处理的实质问题：
要么建卡承接、要么改判去向。

### 20 项 UNREVIEWED 的语义分组

| 组 | 数量 | 说明 |
|---|---|---|
| 分析与评估（LLM 调用栈 / 评测基线 / 提示词资产） | 4 | U01 系 |
| 研究报告与外部资料（生态研究 / 来源结构 / 呈现形态） | 2 | U02 系 |
| 知识页面与质量门（页面结构 / 一致性 / 措辞 / 反模式） | 3 | U03 系 |
| 知识库维护流程（更新梯度 / 发布节奏 / 索引 / 并发） | 11 | U05 系 |

（分组为按上游来源的语义归类，用于 F1-C-B 分批处理，**不改变任何归属**。）

### 8 项待裁 REJECT 的实际交集

- **全部落在 31 项遗留集合之内**，不额外新增（机检通过）。
- 其中属于 ROUTED 的若干项、属于 UNREVIEWED 的若干项，构成交集。
- **另有 13 项 REJECT 已被 canonical 引用**（作为反例或负向约束），它们属 MAPPED，
  不计入遗留集合——清单中单列以示区分。

原始 REJECT 与最终设计决策分开记录：`original_disposition` 字段明确标注
「此字段是上游审计时的原始处置，不是 F1-C 的最终设计决策」。

---

## 4. 终态模型预审

### 现有三态不足以表达 F1-C 终态

`MAPPED / ROUTED / UNREVIEWED` 只表达「映射进度」，无法表达**处置性质**。F1-C 需要落定的终态至少有五类：

| 建议终态 | 含义 | 现有模型能否表达 |
|---|---|---|
| `ADOPTED` | 已映射至某条 canonical（可多对一） | 可以（= MAPPED） |
| `ADOPTED_AS_COUNTEREXAMPLE` | 被某 canonical 的拒绝机制覆盖（作为反例/负向约束登记） | **不能**（现在混在 MAPPED 里） |
| `REJECTED_WITH_REASON` | 有明确理由的拒绝，不建 canonical | **不能** |
| `DEFERRED_WITH_REASON` | 有明确理由的延期，登记去向与触发条件 | 部分（ROUTED 只表达「去哪个模块」） |
| `INTERNAL_DESIGN_ONLY` | 内部自有设计要求（零来源 canonical 的来源说明） | **不能** |

### 兼容性方案（建议，不在本批实施）

不改动现有三态字段与其守恒关系，**新增正交的 `terminal_disposition` 字段**：

```
state（不变）:            MAPPED | ROUTED | UNREVIEWED
terminal_disposition:     ADOPTED | ADOPTED_AS_COUNTEREXAMPLE |
                          REJECTED_WITH_REASON | DEFERRED_WITH_REASON |
                          INTERNAL_DESIGN_ONLY
```

两条轴互不干扰：`state` 继续表达「进没进 canonical」（守恒仍按 143），
`terminal_disposition` 表达「最终怎么处理」（F1-C 结束时必须全部有值）。

**好处**：现有十个验证器读 `state` 的断言全部不受影响；
F1-C 可以在不改数据模型的前提下先补 `terminal_disposition`。

### 实施约束

该变更**必须由 F1-C 后续批次统一实施并验证**，不得在本批直接改数据模型或改十个既有验证器。
本批只提出建议。

---

## 5. 本批未做的事

- 未改动任何 canonical 的 owner 或 ID。
- 未改动任何 ROUTED / UNREVIEWED 记录。
- 未重跑 F1-B 的十个构建器（本批为只读分析）。
- 未启动 F1-C-B、F1-C-C、F1-C-D、F1-D 或 F2。

---

## 6. F1-C-B 的最小执行起点

1. **处理 11 项 ROUTED 的「目标模块已完成但未承接」**——这是最紧的一类，
   因为它意味着前九个模块有漏接。逐条二选一：建卡承接，或改判去向。
2. 先处理 `U06-C25` 的**承接形态**（Storage 已定，但它还未被任何 canonical 覆盖）：
   新建一条 canonical，还是在 SL-CAP-0062 上追加语义。
3. 按 4 个语义组处理 20 项 UNREVIEWED（建议从 U05 系的 11 项开始，因其量大且集中）。
4. 8 项待裁 REJECT 逐条定性（`REJECTED_WITH_REASON` vs `ADOPTED_AS_COUNTEREXAMPLE`）。
5. 十项冲突裁决（F1 原定任务）。
6. 实施终态模型扩展（`terminal_disposition` 正交字段）+ 配套验证器。
