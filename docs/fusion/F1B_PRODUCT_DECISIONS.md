# F1-B / Product 批次 · 设计裁决

生成器：`tools/fusion/f1b_build_product.py`（定义在 `tools/fusion/f1b_product_def.py`）
验证器：`tools/fusion/f1b_verify_product.py`（43 条检查，只写 `F1B_PRODUCT_VERIFICATION.json`）

本批是 F1-B 的第四批，前三批（Facts 10 条、Collector 9 条、Evidence-Claims 9 条）已分别提交并验收。
本批只追加 `SL-CAP-0029`…`SL-CAP-0034`，不改写 0001–0028。

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| Product 候选（全库检索后逐一核验） | 12 |
| 本批正式承接的原始身份 | 10 |
| 判给其它模块的身份（新增分流） | 2 |
| 本批 canonical 能力 | 6 |
| 累计 MAPPED（全模块） | 44 |
| 累计 ROUTED（挂起分流） | 7 |
| 累计 UNREVIEWED | 92 |
| 累计 canonical | 34 |
| 去重比（本批 原始:canonical） | 1.67 : 1 |

三态之和校验：44 + 7 + 92 = 143。

按来源分布（本批 10 个身份）：U03 10 项，其余五源 0 项。

U03 独占不是偷懒：产品语义建模的能力集中在一个上游，这是六源审计的既有结论。
其余五源不是没有相关内容，而是相关内容已被前三批或后续批次认领：U02 的强项在外部研究流程（属 Research）、
U04 的强项在知识生命周期（属 Lifecycle/Storage）、U06 的强项在安全审查（属 Security）、
U05 的强项在知识库维护（属 Storage）、U01 的强项在确定性抽取（属 Facts/Collector）。

---

## 2. 六条 canonical 能力

| ID | 名称 | 处置 | V1 | 来源 |
|---|---|---|---|---|
| SL-CAP-0029 | 产品语义模型八要素（每字段强制带声明层级与证据引用） | ADAPT | 必需 | U03-C06 |
| SL-CAP-0030 | 外部集成边界三态（有配置 ≠ 在运行） | REUSE | 必需 | U03-C01 |
| SL-CAP-0031 | 业务实体建模与实体关系（页类型 + 判定清单） | REIMPLEMENT | 必需 | U03-C16 |
| SL-CAP-0032 | 产品语义渐进构建序（分轮推进 · 禁止一次成型 · 精修动作集） | ADAPT | 必需 | U03-C07, C13, C14 |
| SL-CAP-0033 | 产品语义的未知项与来源冲突登记 | ADAPT | 必需 | U03-C09, C10 |
| SL-CAP-0034 | 产品语义的可判定终止条件与字段置信度 | REIMPLEMENT | 必需 | U03-C17, C11 |

处置分布：REUSE 1 条、ADAPT 4 条、REIMPLEMENT 2 条、REJECT 0 条。

REJECT 为零，但被拒的语义仍然落地：本批对上游多处明确写下了拒绝理由（五档证据优先级、百分比置信度、
每术语必成页、D2 强制图规范、禁确定性工具），这些原始身份（U03-C23/C24/C25/C26/C27）不归本批，
原因见第 3 节。

---

## 3. 为什么是六条，以及 12 个候选去了哪

本轮先按用户列出的九项优先候选逐一核验（C01/C06/C07/C09/C10/C11/C13/C15/C16/C17），
再对全部 143 项做一次全库检索，确认没有漏掉的产品语义类能力。
检索方式是关键词打分（product/feature/user/role/entity/flow/功能/产品/用户/实体/流程/边界…）
对未映射未分流项打分，命中 ≥2 的共 6 条，人工确认后并入候选表。

筛选结果与去向：

| 候选 | 去向 | 理由 |
|---|---|---|
| U03-C01 | → SL-CAP-0030 | 集成三态，产品边界的核心判据 |
| U03-C06 | → SL-CAP-0029 | 八要素框架本体 |
| U03-C07 | → SL-CAP-0032 | 依赖序 |
| U03-C09 | → SL-CAP-0033 | 未知项 |
| U03-C10 | → SL-CAP-0033 | 来源冲突 |
| U03-C11 | → SL-CAP-0034 | 置信度三档 |
| U03-C13 | → SL-CAP-0032 | 渐进发现 |
| U03-C14 | → SL-CAP-0032 | 精修动作集 |
| U03-C16 | → SL-CAP-0031 | 业务实体 |
| U03-C17 | → SL-CAP-0034 | 终止条件 |
| **U03-C15** | **→ Renderer（新增分流）** | 受众清单用于信息密度决策，属渲染层 |
| **U03-C08** | **→ Lifecycle（新增分流）** | Rerun Protocol 是增量重建契约，属生命周期 |
| U03-C12 | 不进本批 | 二十条反模式清单是模型自检提示 + linter 来源，主体属 Renderer/质量门 |
| U03-C18 | 不进本批 | 十八条结构一致性检查是 linter，属 Renderer |
| U03-C19 | 不进本批 | wiki link 校验属 Renderer |
| U03-C20 | 不进本批 | 五条一致性规则属 Renderer |
| U03-C21 | 不进本批 | 五十五问自检清单属质量门 |
| U03-C22 | 不进本批 | 主张措辞规则已在 Evidence-Claims 的 SL-CAP-0023/0026 覆盖 |
| U03-C23 | 不进本批 | 五档证据优先级被 REJECT，理由已在 EC 批次裁决 |
| U03-C24/C25/C26/C27 | 不进本批 | 均判 REJECT（D2 强制图、禁确定性工具、每术语成页、百分比豁免），与 SourceLore 架构冲突，理由在各批次已记 |

**这七个「不进本批」的身份仍是 UNREVIEWED**，不是被丢弃——它们留给 Renderer、Security 或 F1-C 裁决。
本批不做越权认领，也不为了凑数把它们塞进 Product。

---

## 4. 误合并防护（逐条交代）

用户列出的六项最易错合并，本批的处理如下：

**A. 产品功能声明与产品功能实现。**
这是本批最核心的一条。SL-CAP-0029 的 `claim_type` 四值正是为此设的：`declaration`（README 声称）
与 `fact`（代码证实）是两个不同值，且硬规则要求「`evidence_refs` 为空时 `claim_type` 只能是
`inference` 或 `unknown`」。所以「README 说支持某功能」只能产出 declaration 型 claim，
不能自动产出 fact 型 claim。这条规则未合并进任何其它条目，是独立硬约束。

**B. 业务实体识别与知识库实体身份注册。**
未合并，且在 SL-CAP-0031 的 `overlaps` 中显式划界：本条识别的是被测产品内部的领域对象，
Storage 注册的是知识库自身的 subject 身份。两者名字接近、对象完全不同。

**C. 用户流程理解与源码控制流分析。**
未合并。SL-CAP-0032 管的是产品语义的分轮取数节奏（先广度后具体），
Facts 的 SL-CAP-0001/0006 管的是确定性控制流与入口点抽取。本批只消费后者，不重做。

**D. 外部集成指示符扫描与产品依赖意义分析。**
未合并。SL-CAP-0030 只定义「集成如何判状态」，不定义「依赖的语义价值」。
指示符扫描本身属 Facts/Collector，产品意义判定属 Product——两层在同一字段上交接但实现分离。

**E. 产品未知项与技术执行失败。**
未合并，且在 SL-CAP-0033 的 `overlaps` 中三重划界：产品未知项（被测产品的知识缺口）、
Evidence-Claims 的 `insufficient_evidence`（本次裁决证据不足）、技术执行失败（取数失败）。
硬规则：取数失败不等于产品未知，不得把采集异常登记为未知项。

**F. Product Model 与最终 Markdown 报告模板。**
未合并。Product 只产出要素与 provenance，呈现形态归 Renderer。本批无任何渲染相关字段。

---

## 5. 产品验证语义（第 5 节五条，逐条落章）

### P-1 声明不能替代实现证据
见第 4 节 A。机械闸门是「空 `evidence_refs` 不得标 fact/declaration」，落在 SL-CAP-0029 的
描述与输出 `field_provenance` 结构中。

### P-2 未知项必须保留
SL-CAP-0033 的五字段全部为 MUST（`type`/`scope`/`why_unknown`/`owner`/`resolved_by`），
其中 `why_unknown` 强制区分「资料不存在」与「资料存在但互相矛盾」。
硬规则：不得因缺少业务流程、权限模型或用户角色的资料就编造完整产品画像——
缺口只能以 unknown_item 存在。上游把五字段写成 SHOULD，本批提为 MUST；
不加这一条，整条规则会退化为可省略。

### P-3 功能关系必须可追溯
SL-CAP-0031 的 `entity_relation` 强制携带 `evidence_refs`；SL-CAP-0029 的 `field_provenance`
对每个字段同理。任何「模块 A 负责 B」「用户通过 C 完成 D」的结论，要么有可定位证据，
要么 claim_type 标为 inference。

### P-4 允许多种证据来源但必须保留来源类型与验证状态
四值 `claim_type` 覆盖源码（fact）、文档（declaration）、推导（inference）、缺口（unknown）四类来源；
验证状态不由 Product 自评，而是交给 Evidence-Claims 的裁决状态机（SL-CAP-0028）判定。
Product 可以提 Claim 候选，但无权把推断直接提升为已证实事实——这条边界写进 SL-CAP-0029 的
`description` 与 `overlaps`。

### P-5 不提前设计数据库
本批只产出逻辑数据契约与能力边界：`outputs` 里列的是字段清单形态（`product_model`、
`field_provenance`、`unknown_item`…），不是表结构。未新增任何 `schemas/` 文件，
未写迁移、未建索引、未定义存储布局——由 c36 实测校验。

---

## 6. 各条裁决要点

### SL-CAP-0029（ADAPT）
U03-C06 的八要素划分合理完整，但上游只对 Roles、Flows、Boundaries 三处做了证据分级，
其余五要素（Frame、Entities、Capabilities、Constraints、Decisions）没有任何证据要求。
修正点是「每字段强制 `claim_type` + `evidence_refs`」，并补硬约束：
无 `evidence_refs` 的字段不得标 fact 或 declaration。这不是形式主义——它是防止
「README 声称的功能被当成已实现功能」的唯一机械闸门。

### SL-CAP-0030（REUSE）
U03-C01 是三个上游里唯一把「有配置 ≠ 在运行」写成显式三分的地方，且自带一条可直接采纳的强制规则
（provider 配置文件存在则必须有 Integration 条目或解释性 Unknown）。直接沿用，无需改写。
三分不是分类学而是防伪机制：它挡住「仓库里有 OpenAI 的 key 配置，于是报告写支持 OpenAI」
这类从配置推到运行时行为的越级断言。

### SL-CAP-0031（REIMPLEMENT）
U03-C16 目标正确但上游实现完全缺失——十四步构建序无实体步、章节结构无实体章、
范围清单无实体项、README 输出清单亦无（审计 D4），唯一判定标准是纯判断、无判据。
所以本条不是补齐上游，而是自行设计：页类型 + 判定清单 + 关系结构。
这也是本批最重要的自建能力：没有实体层，产品模型就只剩功能列表。

### SL-CAP-0032（ADAPT，三合一）
C07 给现成依赖序（先术语、再角色功能、后流程、Overview 最后），C13 给分轮推进原则
（广度优先、禁止一次成型），C14 给轮与轮之间的精修动作集。拆开则 C07 只有顺序没有预算、
C13 只有原则没有顺序、C14 没有可挂靠的阶段，故合并。
三处均判 ADAPT：C07 的「每阶段回看整仓」与低 token 目标正面冲突（审计 D3）必须去掉；
C13 缺每轮预算与取样规则；C14 被上游写成流程阶段但无完成谓词，本条只保留动作集。

### SL-CAP-0033（ADAPT，二合一）
C09（未知项）与 C10（来源冲突）是同一件事的两个来源类别——未知可能因为「根本没有资料」，
也可能因为「资料互相矛盾」，两者共用同一套登记与生命周期载体。
C09 判 ADAPT：五字段可 schema 化，但上游缺 owner 与 resolved_by（D13），且只是 SHOULD。
C10 判 ADAPT：规则正确但上游只说记录冲突、不给解决程序；本条改为「冲突进 evidence 体系、
按既有 `source_type` 裁定、不另立优先级」，避免与 EC 已有证据体系形成两套互不兼容的排序。

### SL-CAP-0034（REIMPLEMENT，二合一）
终止条件要能判定，必须先有「本轮进展如何度量」，而进展度量正是字段置信度的升级——
两者共用 `round_record` 与 `field_provenance` 两个输入，拆开则终止条件无处可算。
C17 判 REIMPLEMENT：上游十三条终止条件全是 SHOULD，核心判据「再跑一轮也没多少新东西」
不可度量（D11），等于没有终止条件——必须自行设计三条可计算判据。
C11 判 ADAPT：三档定义清晰，但上游缺聚合规则与跨页面一致性度量（D8/D9），
且未覆盖其自身允许的百分比豁免（D7）；本条补「聚合取最小值」并明确禁止百分比。

---

## 7. 新增分流（2 条）

| 身份 | 去向 | 理由 |
|---|---|---|
| U03-C15 写作风格与受众定义 | Renderer | 受众清单用于卡片与报告的信息密度决策，属渲染层；Product 只产出内容，不决定呈现形态 |
| U03-C08 Rerun Protocol 九个触发点 | Lifecycle | 增量重建契约（文件哈希变化、注册表增减、页面缺失），属生命周期管理；Product 只管单次构建的分轮推进 |

两条都只记录去向，未在目标模块建 canonical——按既有规则，ROUTED 只有在目标模块真正建出条目时才转 MAPPED。

---

## 8. 与既有批次的交接

- SL-CAP-0029 / 0031 依赖 Facts：确定性事实（SL-CAP-0001/0002）是八要素与实体建模的唯一输入；
  本批不重新抽取任何事实。
- SL-CAP-0029 / 0030 / 0031 依赖 Collector：钉定快照与调用点候选来自 SL-CAP-0013/0015；
  本批不发起任何网络请求。
- SL-CAP-0029 / 0033 / 0034 依赖 Evidence-Claims：claim_type 的判定纪律承接 SL-CAP-0023（显式未知）
  与 SL-CAP-0028（裁决状态机）；Product 只产出 claim 候选，不提级。
- 与 Lifecycle 的分界见第 7 节；与 Storage 的分界见第 4 节 B；与 Renderer 的分界见第 4 节 F。
- 用户特别提示「UPSTREAM-03 的 Product Model 不等于授权创建第二套 Facts 或 Claim 数据库」——
  本批六条的 `outputs` 全部是逻辑字段清单，无一处声明独立存储，由 c17（越界职责表述检查）实测把关。

---

## 9. 本批留下的 unresolved（不隐藏）

汇总 6 条的待定项（合计 18 项），均在各自条目的 `unresolved` 字段中：

1. 八要素的字段级 schema（类型、可选性、嵌套深度）属 F2（SL-CAP-0029）
2. declaration 型 claim 在无 evidence_refs 时是否允许存在，待 F1-C（SL-CAP-0029）
3. Frame 要素的证据要求高于其余七项的降级规则（SL-CAP-0029）
4. 动态加载集成的静态判定边界，待 F2（SL-CAP-0030）
5. integration_unknown 是否需记录已尝试的检测手段（SL-CAP-0030）
6. 技术结构体与业务实体的判定阈值未定量，待 F1-C（SL-CAP-0031）
7. 实体关系是否要求双向可推导（SL-CAP-0031）
8. 同一概念多类名时的 entity_key 归并规则属 F2（SL-CAP-0031）
9. 轮数与预算的具体数值待 F2（SL-CAP-0032）
10. 去掉「每阶段回看整仓」后的取样规则待 F1-C（SL-CAP-0032）
11. 十类精修动作是否允许首轮使用（SL-CAP-0032）
12. unknown_item 与 insufficient_evidence 如何避免双写，待 F2（SL-CAP-0033）
13. conflict 的裁定程序（谁能裁、写在哪）（SL-CAP-0033）
14. accepted_permanent 的授予条件（SL-CAP-0033）
15. 三条终止条件同时成立时记录哪一条（SL-CAP-0034）
16. 聚合取最小值的字段覆盖门槛（SL-CAP-0034）
17. Medium 与 Low 的边界需可执行定义（SL-CAP-0034）
18. 上述全部属 F2 实现决定，不构成本批验收缺口

---

## 10. 验收

顺序执行（Facts → Collector → EC → Product）：

```
python3 tools/fusion/f1b_build_product.py       → RESULT: OK (exit 0)
python3 tools/fusion/f1b_verify.py              → 12/12 PASS (exit 0)
python3 tools/fusion/f1b_verify_collector.py    → 30/30 PASS (exit 0)
python3 tools/fusion/f1b_verify_ec.py           → 50/50 PASS (exit 0)
python3 tools/fusion/f1b_verify_product.py      → 43/43 PASS (exit 0)
```

### 本轮修正的作用域错误（两处，均非数据缺陷）

EC 验证器因本批推进产生两条误红，属用户第 7 节描述的同一类问题：

1. **c17 batch_summary 指向** —— 原判据要求 `batch_summary` 必须等于 EC 自己。
   但按统计契约 `batch_summary` 指向「业务顺序上最后完成的那一批」，Product 推进后它必然不再指向 EC。
   已改为：EC 批次条目存在 + `batch_summary` 可在 `batches[]` 定位 + 确为业务顺序最后一批。
   判据收窄不降强度——契约本身仍然被校验，只是不再要求「最后一批永远是我」。
2. **c47 全局数字一致** —— 原判据拿当前全局值去卡 EC 决策文档，而文档记录的是本批验收当时的快照。
   已改为与 Facts c11 同一口径：「文档内累计快照自洽 + 原始总数 143」。

两处都保留了核心不变量（三态互斥、合计 143、晋升留痕），只是去掉「历史必须等于现在」这条
不可能成立的隐含要求。

### 本轮修的构建器 bug（一处，非数据缺陷）

`f1b_build_product.py` 的「自有键」集合最初只装了承接键（`CONSUMED_THIS_BATCH`），
漏掉了本批自己声明的出向分流键（`DEFERRED_TO_OTHER_MODULE`）。
后果：本批打算推到 Renderer/Lifecycle 的那两条分流不被识别为「本批产物」，
每次构建都往 `cross_module_redirections` 追加一份，连跑数次累积成 5 份重复记录，
由 Collector c4c（分流与晋升记录无重复）抓到。

修正：`own_keys = 承接键 ∪ 本批分流键`。分离的两件事必须用同一个键集合剥离，
否则幂等在映射侧成立、在分流侧失效。已复验重跑后 `routed` 恒为 7 条、零重复。

### 幂等性

`f1b_build_product.py` 重复运行后 `canonical_capabilities`、`cross_module_redirections`、
`routed_promotions`、`batches`、`global_state_counts`、`module_rollup` 六个核心字段
逐字节一致，已实测校验（c37/c38 另作机检）。

---

## 11. 下一批

F1-B 剩余六个模块：Research → Lifecycle → Security → Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0035` 起。

本批未启动 F2，未修改正式分析引擎，未处理其它六个模块。
