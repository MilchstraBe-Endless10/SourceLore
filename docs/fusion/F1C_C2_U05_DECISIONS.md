# F1-C-C2 · UPSTREAM-05 全部剩余 UNREVIEWED 终裁

产物：裁决数据 `tools/fusion/f1c_c2_decisions.py`　验收 `tools/fusion/f1c_c2_verify.py`
清算记录 `F1C_C2_U05_RECONCILIATION.json`　全局历史验证 `tools/fusion/f1c_history_verify.py`

---

## 1. 真实集合是 10 项，不是 11 项

按第 2 节要求，以「U05 全量 28 项 − 已 MAPPED − 已 ROUTED」现算：

```
C07 C08 C12 C13 C15 C16 C21 C25 C27 C28  →  10 项
```

**11 是上一轮汇报抄错的。** `F1C_REMAINDER_BASELINE.json` 自 F1-C-A 起记录的 U05 未审组
一直是这 10 项（该文件 `unreviewed_by_class` 里「知识库维护流程」标注 count=10，可逐个数出）。
数据文件无误，未强行凑 11。

已在前批处理的 6 项**未重复计算**：`C18`→0062、`C22`→0064、`C23`→0065、
`C04`/`C14`/`C19`→F1-C-B/C1 已承接。

---

## 2. 逐项终裁

| 身份 | 原处置 | 方向 | owner | 承接 |
|---|---|---|---|---|
| C07 命令族与编号页集 | ADAPT | 承接 | Lifecycle | SL-CAP-0040 + amendment |
| C08 Phase 0 三分路由 | ADAPT | 承接 | Research | SL-CAP-0035 + amendment |
| C12 渐进式 AI 投喂 | ADAPT | 承接 | Research | SL-CAP-0035 + amendment |
| C13 C4 强制顺序 | ADAPT | 承接 | Research | SL-CAP-0035 + amendment |
| C15 发布节奏绑定 | ADAPT | 承接 | Lifecycle | SL-CAP-0043 + amendment |
| C16 测试用例维护触发 | ADAPT | 承接 | Lifecycle | SL-CAP-0044 + amendment |
| C21 冲突处理 | REIMPLEMENT | 承接 | Evidence-Claims | SL-CAP-0028 + conflict 旁支 |
| C25 测试覆盖作为质量证据 | REIMPLEMENT | 承接 | Evidence-Claims | SL-CAP-0075 + 覆盖率禁令 |
| C27 产出整册项目文档 | **REJECT** | **拒绝** | — | 保持 UNREVIEWED |
| C28 双语 Sphinx 站 | **REJECT** | **拒绝** | — | 保持 UNREVIEWED |

统计：**承接 8、新增 canonical 0、拒绝 2、延期 0。**

---

## 3. 六个重点能力的裁决依据

### C12 渐进式 AI 投喂 → Research / SL-CAP-0035

**验明其真正解决的问题：研究过程中的读取顺序，不是模型上下文管理。**
机制是「三轮渐进阅读：概览→深潜→模块验收」，why 写「轮次划分（先全局后局部）
可作为 research 任务的默认读取顺序参考」。

归 SL-CAP-0035 的 R1 内读阶段。**不新建第二套无界上下文加载机制**——
上下文预算与按需加载已由 SL-CAP-0068（Skill 渐进加载）与 SL-CAP-0070（调用预算）覆盖，
本条只管「读什么次序」，不管「能装多少」。

### C13 C4 强制顺序 → Research / SL-CAP-0035（部分采纳 + 明确拒绝）

三类逐项区分：

| 面向 | 裁决 |
|---|---|
| C4 作为可选架构表达方法 | **采纳其粒度降序**（系统边界→部署单元→组件→代码） |
| 固定要求所有仓库按 C4 四级产出 | **明确拒绝**——不得要求所有仓库都产出 C4 四级结构 |
| 无足够关系证据时强行补全结构图 | **明确拒绝**——与该身份同源的强制输出机制已在 SL-CAP-0057 被拒 |

**不因上游要求强制 C4，就把它变成 SourceLore 全局必执行规则。** 结构层级只在关系证据充分时使用。

### C15 发布节奏绑定 → Lifecycle / SL-CAP-0043

机制是「文档更新挂到 release/PR 检查单」，指**变更触发的时机绑定**。

不是 Renderer（不是文档生成）、不是 Security（不是发布审批）、不是 DSH-Adapter（不是调度），
而是 Lifecycle 的变更触发分类。

**关键区分：Release 触发 ≠ 人工公开发布许可。** 前者是「该重验了」，后者是 SL-CAP-0053 的权限门。
二者在 amendment 里被显式隔离，不得混同。

### C16 测试用例维护触发 → Lifecycle / SL-CAP-0044

四条触发条件绑死上游自己的文档体系，可迁移的部分是**路径 B 的枚举清单**：
测试文件的新增/修改/删除本身就是一类变化集。

不是「源码变化引起知识重验」（路径 A）、不是「测试执行任务」、不是「测试结果作为证据」（EC）。
**F1 阶段不要求实际运行测试**——amendment 里明确写了「只要求识别与登记」。

### C21 冲突处理 → Evidence-Claims / SL-CAP-0028（conflict 旁支）

**按冲突类型分开归属，不合并成一个全局冲突状态机**（这是本项最容易判错的地方）：

| 冲突类型 | 归属 |
|---|---|
| ① Claim 之间证据冲突 | **本条**（EC 裁决状态机） |
| ② 历史知识与当前理解冲突 | SL-CAP-0041（可变/不可变层分离） |
| ③ 多 Agent 并发写入冲突 | SL-CAP-0064（CAS 明确返回 CONFLICT） |
| ④ 人工内容与生成内容冲突 | SL-CAP-0058（生成/人工物理隔离） |

**原始 C21 的主要语义是 ①**——上游是知识治理语境下的「两条知识矛盾」，
且 why 要求的是「裁决权归属」。故 owner=EC，做法是补 `conflict` 旁支状态，
并在 amendment 里写明「不得把这四类合并成一个全局冲突机」。

### C25 测试覆盖作为质量证据 → EC / SL-CAP-0075

覆盖率的四个问题（按第 5 节要求逐条核实）：

| 问题 | 答案 |
|---|---|
| 是否只是测试运行的测量结果 | **是** |
| 能否证明某功能正确 | **不能** |
| 能否证明某 Claim 得到支持 | **不能** |
| 能否作为评测基线的一项输入 | **可以**，但只是一项 |

补四条禁令（写入 SL-CAP-0075 `f1c_amendments`）：

```
T-1 覆盖率不等于正确性——高覆盖率只说明代码被执行过，不说明结果正确
T-2 测试存在不等于测试通过——存在测试文件/用例不构成「已验证」证据
T-3 测试通过不等于全部功能已验证——覆盖偏斜时未覆盖部分仍是未知
T-4 上游若存在测试目录或覆盖率数字，不得直接提升为「已验证」
```

准入原则：**机制必被测**，不以「有 tests 目录」为准入。

---

## 4. 其余四项的裁决依据

**C07 命令族与编号页集 → Lifecycle / SL-CAP-0040**
审计 why 明确：「页集本身绑死具体项目文档结构，SourceLore 不做项目文档生成，
只需要它的『可枚举优先于自由命名』这一条」。补进 Subject 命名原则——`subject_key` 必须可枚举，
不得自由起名（自由命名会让同一实体在不同批次得到不同键）。

**C08 Phase 0 三分路由 → Research / SL-CAP-0035**
分流依据是「要不要读仓库」，与 0035 的 R1「只消费既有产物、不发起采集」同构。
补为 R0 前的显式档位选择（full / fast / output_only），必须记录在 `research_scope` 里。

**C27 产出整册项目文档 → REJECT**
原始 disposition 已是 REJECT，维持。**拒绝的是具体机制**（00–12 编号页 + Sphinx 双语站点的文档流水线），
**不是拒绝产出可读视图**——后者已由 SL-CAP-0055 承接。
**不得通过改写成「人类可读报告」重新引入该机制。**

**C28 双语 Sphinx 站与 gettext → REJECT**
原始 REJECT，维持。拒绝的是具体构建链（Sphinx + myst + sphinx-intl）。
多语言若需要属 F2 呈现层选型，不由此条引入。

---

## 5. 两项 REJECT 为何保持 UNREVIEWED

现三态模型（MAPPED / ROUTED / UNREVIEWED）**无法表达「已裁决为拒绝」**。
按第 6 节「不得通过假 MAPPED 消除它」的要求：

- 保持真实旧状态 `UNREVIEWED`；
- 终态 `REJECTED_WITH_REASON` 只记在裁决数据与清算记录里；
- 标记 `awaiting: F1-C-D terminal_disposition 迁移`；
- **不假称已映射**。

所以本批后 UNREVIEWED 是 12 项（含 U05 的两项 REJECT 与 U01/U02/U03 的 10 项未处理）。

---

## 6. 历史保护增强（第 7 节）

新增**独立全局历史验证入口** `tools/fusion/f1c_history_verify.py`，可被 F1-D 直接调用。
十项检查覆盖：身份映射保持、ID 不复用、amendment 留痕、REJECT 原判未擦除、
许可证隔离、新旧能力无重复 owner、身份唯一性与三态守恒未被削弱、原始索引/审计/引擎未变、
以及**自身不依赖任何历史批次验证器**（`c10` 机检：不得 import `f1b_verify*`）。

**修掉一处检查器缺陷**：初版 `c5` 把 `upstream_disposition`（上游原始处置，不得改写）
与 `verdict`（SourceLore 自己的裁定，可与上游不同）混为一谈，
误报 `UPSTREAM-06::C13`（上游 ADAPT 但 SourceLore 判 REJECT，属正常）。
已改为只校验前者与 RAW 索引一致。

---

## 7. 数字

| 项 | F1-C-C1 后 | 本批后 |
|---|---|---|
| MAPPED | 123 | **131** |
| ROUTED | 0 | 0 |
| UNREVIEWED | 20 | **12** |
| 合计 | 143 | 143 |
| canonical | 75 | **75**（无新增） |

**新增 canonical = 0。** 八项全部复用已有能力 + amendment，符合「优先复用已有 75 条」的要求。

---

## 8. 下一批起点

剩余 12 项 UNREVIEWED：

| 来源 | 身份 | 原处置 |
|---|---|---|
| U03 | C23 五档证据优先级 | REJECT |
| U03 | C24 D2 图规范（强制 D2） | REJECT |
| U03 | C25 不得依赖 AST/图数据库/索引 | REJECT |
| U03 | C26 每个术语独立成页 | REJECT |
| U04 | C05 按需加载的模式指引 | REUSE |
| U04 | C06 不存密钥/凭据/个人数据 | REUSE |
| U04 | C13 报告粒度禁令 | ADAPT |
| U04 | C21 冲突处理（两报告判断不同） | REIMPLEMENT |
| U04 | C27 HTML/excalidraw 等产物格式 | REJECT |
| U05 | C27 产出整册项目文档 | REJECT（本批已裁） |
| U05 | C28 双语 Sphinx 站 | REJECT（本批已裁） |
| U06 | C21 模型分层 | REJECT |

**下批重点**：U04-C21「冲突处理（两报告判断不同）」与本批 U05-C21 名称相同但语义不同——
前者是**报告之间**的判断差异（Research 层），后者是**Claim 之间**的证据冲突（EC 层）。
这两项极易被判成同一条，必须分开裁。

**U03 的四项 REJECT 集中且同源**（证据优先级、强制 D2、禁用基础设施、术语独立成页），
建议成组处理并统一以「反例约束」方式登记，而非逐条新建。
