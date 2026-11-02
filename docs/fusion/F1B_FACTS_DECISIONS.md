# F1-B / Facts 模块能力裁决记录

- 任务：`M1-FUSION-GATE-F1 / F1-B`（第一模块，唯一范围：Facts）
- 输入源快照：`docs/fusion/RAW_CAPABILITY_INDEX.json`（sha256 `e62b68ed1658b95e…`，143 项，本轮未修改）
- 产物：`docs/fusion/CAPABILITY_CROSSWALK.draft.json`（草稿，未冻结）
- 生成器：`tools/fusion/f1b_build_facts.py`（定义在同目录 `f1b_facts_def.py`）
- 验收：`tools/fusion/f1b_verify.py`，12/12 PASS

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| 本轮识别为 Facts 候选 | 11 |
| 归入 Facts 的 canonical 能力 | 10 |
| 转交其他模块（同属本轮识别但归属他处） | 11 |
| 仍未处理（保持 UNMAPPED/PENDING） | 121 |
| 去重比（原始:canonical） | 1.1 : 1 |

按来源分布（Facts 消费）：U01 6 项、U02 1 项、U03 3 项、U04 0 项、U05 1 项、U06 0 项。

U04 与 U06 消费为零不是遗漏，是两个判据的结果：U04 的强项在 Claim 结构与知识失效语义（属 Evidence-Claims），U06 的强项在证据形态与安全门控（属 Evidence-Claims / Security），两者都没有针对「仓库静态事实抽取」的系统性能力。

---

## 2. 十条 canonical 能力

| ID | 名称 | 处置 | V1 | 来源 |
|---|---|---|---|---|
| SL-CAP-0001 | 确定性事实抽取（零模型前置） | REUSE | 必需 | U01-C01, U05-C01 |
| SL-CAP-0002 | repo_facts.json 单一事实契约 | ADAPT | 必需 | U01-C02 |
| SL-CAP-0003 | 代码采样与预算 | ADAPT | 必需 | U01-C04 |
| SL-CAP-0004 | 树截断与降级表示 | ADAPT | 必需 | U01-C08 |
| SL-CAP-0005 | Monorepo / Workspace 结构识别（清单级） | ADAPT | 必需（限清单级） | U01-C09 |
| SL-CAP-0006 | 入口点候选识别（规则 + 置信度） | REUSE | 必需 | U01-C05 |
| SL-CAP-0007 | 事实抽取失败与缺失的显式表示 | REIMPLEMENT | 必需 | U02-C05 |
| SL-CAP-0008 | 事实层与推理层的物理隔离 | ADAPT | 必需 | U03-C04 |
| SL-CAP-0009 | Canonical Knowledge Registry | ADAPT | 必需 | U03-C05 |
| SL-CAP-0010 | 静态集成指示符确定性扫描 | REUSE | 必需 | U03-C02 |

---

## 3. 合并与不合并

### 3.1 唯一一次真正的跨源合并

`SL-CAP-0001` 吸收了 U01-C01 与 U05-C01。判据不是名字像，而是两者构成同一机制的两半：U01-C01 给出 `extract/*` 的零 LLM 抽取实现（做什么），U05-C01 给出「哈希比对先行、未变即不启模型」的调度规则（何时做）。缺任一半，另一条都不成立。合并后调度语义下沉为 `dependencies` 中的判定前置，不再单列。

### 3.2 其余九条均为单源，未做合并

明确不合并的三组：

- `SL-CAP-0002`（事实契约）与 `SL-CAP-0007`（缺失表示）名字相邻但语义不同：前者管「事实写在哪、字段叫什么」，后者管「抽不到时怎么记」。契约里可以有 status 字段，但 status 的语义由 0007 定义，两者是结构关系不是重复。
- `SL-CAP-0003`（采样预算）与 `SL-CAP-0004`（树截断）都涉及「没看到的部分」，但不合并：0003 是主动的预算裁量，0004 是被动的传输降级，二者的触发条件、责任方、产物字段都不同。已在 `overlaps` 互相登记。
- `SL-CAP-0006`（入口点）与 `SL-CAP-0010`（集成指示符）都是静态模式匹配，但不合并：0006 判的是「程序从哪进」，0010 判的是「外部依赖被谁用」，消费方不同（前者给分析，后者给集成事实）。

### 3.3 处置不等于许可

`SL-CAP-0010` 处置为 REUSE，来源 U03 是 CC BY 4.0：概念可沿用，但署名、许可链接、修改声明三项义务必须逐项履行，且不得施加额外限制。REUSE 在这里表示「形态成立、无需改设计」，不表示「可以照抄文本」。同理 U06 若将来进入本模块，许可仍是 `copy_permitted: false`，与处置无关。

---

## 4. Facts 的边界

Facts 只做一件事：在已取到的只读快照上，用确定性手段产出可复核的事实，并对「没看到什么」负责。

明确不属于 Facts 的四条线：

| 界外内容 | 归属 | 本轮记录 |
|---|---|---|
| 网络抓取、认证、分页、远端缓存 | Collector | U02-C06、U02-C09 转出 |
| Claim 与证据的支撑关系、证据保存形态 | Evidence-Claims | U01-C03、U03-C03、U04-C07/C08/C10、U05-C05/C06、U06-C05 转出 |
| 产品功能语义、面向用户的解释 | Product | 本轮未接触 |
| 文档渲染、知识卡、图表 | Renderer | U01-C10 转出 |

`SL-CAP-0008`（事实层与推理层隔离）压在边界上：它定义的事实层属于 Facts，但物理拒绝写入的执行点在渲染侧。这条在 `unresolved` 里留了待裁决项，交由 F1-C 确认执行点归属，避免两个模块都以为自己该实现。

`SL-CAP-0007` 同理：四态 status 由 Facts 产生，但 `evidence_ref` 的指向格式属于 Evidence-Claims 的契约，已在依赖中登记，不擅自定义。

### 4.1 保留给后续模块的两项

U01-C03（citation existence check）与 U01-C10（report schema + markdown render）按指令不得进入 Facts。本轮既未纳入 canonical，也未纳入转交清单中的 Facts 一侧，只在 `cross_module_redirections` 里登记去向（Evidence-Claims 与 Renderer），`owner_module` 与处置留空待后续模块裁决。

---

## 5. 进入 V1 / 延后 / 拒绝

进入 V1：全部十条，其中 `SL-CAP-0005` 明确限定为「清单级」，不承诺包级聚合与跨包依赖图。

延后：`SL-CAP-0005` 的包级提升、`SL-CAP-0003` 的采样权重策略，均记在各自 `unresolved`，等 F1-C 裁决多包仓库是否为一等场景。

拒绝：本模块本轮没有任何一条判 REJECT。原因是 Facts 的候选本来就少，且每条都有可用内核；判 REJECT 的那批（U01-C25 禁依赖 AST 解析器/图数据库/静态分析管线、U03-C23 五档证据优先级、U05-C26 知识库住仓库内）属于方法论约束或其他模块的形态，不适合塞进 Facts 的 canonical 列表，故未纳入本模块。它们仍在原始索引中保持待处理，等待各自的归属模块裁决。

---

## 6. 信息不足、待后续裁决

1. `SL-CAP-0002`：`ref_sha` 记录了却不用于取文（上游用 branch）。让 ref_sha 成为取文输入是否需要 Collector 侧同步改契约，待 F1-C。
2. `SL-CAP-0003`：采样权重（体积 / 入口 / 依赖中心度）未定。
3. `SL-CAP-0005`：workspace 未定义时，清单级与包级之间的降级规则未定。
4. `SL-CAP-0008`：物理拒绝写入的执行点属 Facts 还是 Renderer，未定。
5. `SL-CAP-0009`：「不足以新建条目、又不该进 Unknown」的受控出口形态未定。
6. `SL-CAP-0010`：必扫面清单与 Collector 的表面定义可能重复，需确认单一来源。

---

## 7. ID 稳定性

首批分配 `SL-CAP-0001` … `SL-CAP-0010`，从 0001 起连续。后续批次只做追加，不复用、不重排。若需纠正误分类，必须在草案中写入修订原因与迁移关系，不得静默改写已提交的身份。

---

## 8. 本轮未做

未生成 `CAPABILITY_CROSSWALK.json`（正式发布件），该文件须等 F1-D 全量验收通过后才冻结。未触碰 `src/`、`tests/`、`schemas/`，未进入 F2，未处理 Facts 之外的任何模块。
