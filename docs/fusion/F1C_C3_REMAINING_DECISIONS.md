# F1-C-C3 · 剩余 10 项原始能力终裁

产物：裁决数据 `tools/fusion/f1c_c3_decisions.py`　验收 `tools/fusion/f1c_c3_verify.py`
清算记录 `F1C_C3_RECONCILIATION.json`　F1-C-D 清单 `F1C_D_HANDOFF_INVENTORY.json`

**本批后 143 项原始能力全部有终裁。**

---

## 1. 十项裁决总表

| 身份 | 原处置 | 最终 verdict | 方向 | owner | 承接 |
|---|---|---|---|---|---|
| U03-C23 五档证据优先级 | REJECT | REJECT | 承接 | Research | SL-CAP-0037 + 反例 |
| U03-C24 D2 图规范 | REJECT | REJECT | 承接 | Renderer | SL-CAP-0057 + 反例 |
| U03-C25 禁 AST/图库/索引 | REJECT | REJECT | 承接 | Facts | SL-CAP-0001 + 立场 |
| U03-C26 术语独立成页 | REJECT | REJECT | 承接 | Renderer | SL-CAP-0055 + 两级策略 |
| U04-C05 按需加载模式指引 | REUSE | REUSE | 承接 | **DSH-Adapter** | SL-CAP-0068 + 匹配细则 |
| U04-C06 不存密钥凭据个人数据 | REUSE | REUSE | 承接 | **Security** | SL-CAP-0053 + 覆盖面 |
| U04-C13 报告粒度禁令 | ADAPT | ADAPT | 承接 | Lifecycle | SL-CAP-0040 + 粒度门槛 |
| U04-C21 冲突处理（两报告不同） | REIMPLEMENT | REIMPLEMENT | 承接 | **Research** | SL-CAP-0038 + 报告间分流 |
| U04-C27 HTML/excalidraw 格式 | REJECT | REJECT | **拒绝** | — | 保持 UNREVIEWED |
| U06-C21 模型分层 | REJECT | REJECT | **拒绝** | — | 保持 UNREVIEWED |

**承接 8（全带 amendment）、新增 canonical 0、拒绝 2、延期 0。**

---

## 2. UPSTREAM-03 四条（四条 REJECT 各有不同实质理由，不批量填同一句）

### C23 五档证据优先级 → SL-CAP-0037（Research）

**五档用在什么地方？** 给**研究资料排序**（哪个来源先看），属研究取数方法（§12.2 L1142–L1154），不是 Claim 验证。

**三件事分清：** ① 研究资料选择顺序 → 本条；② 来源可靠性判断 → 本条但只能做到「标类型」；
③ Claim 的证据支持关系 → **不属本条**，归 EC 的 SL-CAP-0028。

**能否替代 EC 验证规则？不能。** SL-CAP-0037 已有硬规则「来源类型不构成真伪排序」。

**是否机械真实性排序？是。** 审计已指出「五档无权重不构成全序；L1152–1153 又允许源码处任意层级，排序机制自我消解（D10）」。

**拒绝的机制：** 五档机械排序。**保留的合理部分：** 资料收集与标注原则（已由 0037 承载），
补一条「优先级只能用于取数次序，不得用于判真伪」。

### C24 强制 D2 → SL-CAP-0057（Renderer）

**D2 要求什么：** 所有架构图用 D2 语法产出（§11.1–§11.6），但 **L1046 强制 D2 却无工具链、无语法校验**。
**适用范围：** 上游全部架构文档，无「不适用」出口。
**是否已被 0057 覆盖：** 部分覆盖且更严格——0057 已定「图表可选、格式属实现选择」，D2 强制违反后一条。
**不引入全局依赖。** 拒绝的是「强制单一图示语法 + 无校验」，不是拒绝 D2 这一工具本身。

### C25 禁用 AST/图数据库/索引 → SL-CAP-0001（Facts）

**实际禁的是什么：** 上游 §2 L52–53 对**其自身**禁止依赖四类基础设施。这是自我设限声明，不是「这些技术有害」。

**扩大解释风险：** **有，且是本条最大风险。** SourceLore 的 Facts **恰恰要**用 AST，Storage **恰恰要**用可重建索引；
照搬会直接自毁。

**与 Storage 是否冲突：** 正面冲突。SL-CAP-0065 已确立 C 层索引必须可重建；其硬规则四说的是
「没有必要时不引入」而非「永远禁止」，判断权留给 F2。

**记录的是什么：** 拒绝「禁止使用确定性设施」这条方法论限制，**不是**拒绝这些技术。
技术选型权留 F2。

### C26 术语独立成页 → SL-CAP-0055（Renderer）

**属呈现/导航决策**（0055 的导航索引一型），不是知识对象定义。
**是强制机制：** §7.2 L534/L557 要求「每个术语独立成页，含小仓库」，无「不必」出口。
**已有覆盖：** 0055 的多类型视图允许布局差异；「术语表条目 + 按需升格」正是其允许形态。
**不得制造新权威对象：** 术语页只是呈现单位，权威对象仍只由上游模块产生。

---

## 3. UPSTREAM-04 五项

### C05 按需加载模式指引 → DSH-Adapter / SL-CAP-0068

**不归 Lifecycle。** 它不涉失效语义，纯属「运行时该加载哪份说明」。
对照五模块后确认：Facts/Research/Lifecycle/Storage 均无关，**DSH-Adapter 的 0068 直接对应**。
原 disposition=REUSE 只说明可复用，与 owner 无关——**没有默认归 Lifecycle**。
补一条：按问题类型匹配，单次上下文只装载匹配的那几份。

### C06 不存密钥凭据个人数据 → Security / SL-CAP-0053

同样**不归 Lifecycle**：它是**落盘时的秘密约束**，对象是「每个保留产物」。
五模块对照：只有 Security 的 0053 已是分级+脱敏+门禁。
上游的价值在覆盖面措辞——「**每个保留产物、每种模式**」，补成硬规则：无模式例外。

### C13 报告粒度禁令 → Lifecycle / SL-CAP-0040

核心是「**什么构成一个独立知识单元**」——属 Subject 身份与复用判定，归 0040。
不是 Renderer（不是排版）、不是 Research（不是研究范围）。
审计指出它「没有可判定粒度标准」，本批补两条门槛：K-1 subject_key 必须规范化；
K-2 最小内容门槛（一句可独立陈述的结论 + 至少一条证据引用）。

### ★ C21 冲突处理（两报告判断不同）→ Research / SL-CAP-0038

**这是本批最易判错的一项。原文对象是「两份研究报告之间的解释不一致」**——
where 写「全文缺失」、why 写「通篇未提如何处理互斥结论（D5）」，而上游语境是「每次调查产出一份报告」。

**与 U05-C21 的严格区分（本批边界判定）：**

| | U05-C21 | U04-C21 |
|---|---|---|
| 对象 | **两条 Claim 的证据互相矛盾** | **两份研究的解释不一致** |
| 性质 | 一方错，须裁决真伪 | 可能两者都对（视角不同），也可能其一错了 |
| owner | **Evidence-Claims（SL-CAP-0028 的 conflict 旁支）** | **Research（SL-CAP-0038）** |
| 处理 | 进状态机，不得强行收敛 | 先分辨两类再分流 |

**补两条分流规则：** R-1 视角差异 → 并列呈现、各标适用条件，不判谁错；
R-2 事实冲突 → 产出 handoff_item 移交 EC，**Research 不自行裁决**。
**不为所有冲突建第二套统一状态机**——结论状态只有 SL-CAP-0028 一处。

### C27 HTML/excalidraw 格式 → REJECT（保持 UNREVIEWED）

**拒绝行为：** 以 HTML/excalidraw 文件作为**权威产物格式**。
**潜在替代：** Markdown + schema 为权威格式；富媒体可作 Renderer 的**派生**产物（D 层），
但不得成为权威层存储格式（SL-CAP-0062 D 层不得回写权威层）。
**可作反面依据：** 已作 SL-CAP-0062 的反例——「产物格式绑死具体工具会导致形态不兼容」。

---

## 4. UPSTREAM-06 C21 模型分层 → REJECT（保持 UNREVIEWED）

**原机制：** 仅 Phase 2 用 Deep 层、其余 Standard；按家族别名（opus/sonnet/haiku）派发，不固定版本。
**绑死问题：** 机制绑死 Claude 家族与 Agent 工具，无法迁移；含「moved off the Deep tier」这类只对特定供应商有意义的说明。
**合理内核已覆盖：** 「按任务复杂度与工具能力选路」对应 SL-CAP-0069 的三类操作边界与 SL-CAP-0070 的预算。
**复制边界：** **UPSTREAM-06 无明确复制许可（copy_permitted=false）**——
只作抽象设计背景，未复制任何提示词、规则原文、代码或模板；
**不把任何供应商或具体模型名写死为架构前提。**

---

## 5. 三项 REJECT 为何保持 UNREVIEWED

三态模型无法表达「已裁决为拒绝」。按第 6 节：
保持真实旧状态、终态 `REJECTED_WITH_REASON` 只记在裁决数据与清算记录、
标 `awaiting: F1-C-D terminal_disposition 迁移`、**不假称已映射**。

所以本批后 UNREVIEWED = **4 项**（U04-C27、U05-C27、U05-C28、U06-C21），全部是已裁 REJECT。

---

## 6. 数字

| 项 | F1-C-C2 后 | 本批后 |
|---|---|---|
| MAPPED | 131 | **139** |
| ROUTED | 0 | 0 |
| UNREVIEWED | 12 | **4** |
| 合计 | 143 | 143 |
| canonical | 75 | **75**（无新增） |

**新增 canonical = 0**——八项全部复用已有能力 + amendment，符合优先复用要求。

---

## 7. 下一步：F1-C-D

见 `docs/fusion/F1C_D_HANDOFF_INVENTORY.json`（由 `f1c_d_handoff.py` 现算）：

1. **terminal_disposition 迁移**（4 项 REJECT + 历史 ADOPTED_AS_COUNTEREXAMPLE 分类）
2. **8 项待议跨模块冲突**（X-2/X-4/X-5/X-6/X-7、K-7、Y-4、Y-6）
3. **7 条零来源 canonical** 的来源说明归档
4. **17 条反例绑定**与 2 条 U06 无许可引用的许可证复核
5. **冻结前**：复跑 `f1c_history_verify.py`、冻结 `CAPABILITY_CROSSWALK.json`
