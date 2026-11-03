# F1-B / Research 批次 · 设计裁决

生成器：`tools/fusion/f1b_build_research.py`（定义在 `tools/fusion/f1b_research_def.py`）
验证器：`tools/fusion/f1b_verify_research.py`（46 条检查，只写 `F1B_RESEARCH_VERIFICATION.json`）

本批是 F1-B 的第五批。前四批（Facts 10、Collector 9、Evidence-Claims 9、Product 6，共 34 条）
已分别提交并验收。本批只追加 `SL-CAP-0035`…`SL-CAP-0039`，不改写 0001–0034。

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| Research 候选（优先核验 6 + 全库检索补充） | 13 |
| 本批正式承接的原始身份 | 10 |
| 判给其它模块的身份（新增分流） | 3 |
| 本批 canonical 能力 | 5 |
| 累计 MAPPED（全模块） | 54 |
| 累计 ROUTED（挂起分流） | 9 |
| 累计 UNREVIEWED | 80 |
| 累计 canonical | 39 |
| 去重比（本批 原始:canonical） | 2.0 : 1 |

三态之和校验：54 + 9 + 80 = 143。

按来源分布（本批 10 个身份）：U01 0、U02 7、U03 1、U04 1、U05 0、U06 1。

---

## 2. 五条 canonical 能力

| ID | 名称 | 处置 | V1 | 来源 |
|---|---|---|---|---|
| SL-CAP-0035 | 有界研究阶段流水线（R0–R4 状态机 · 预算 · 可恢复） | REIMPLEMENT | 必需 | U02-C10 |
| SL-CAP-0036 | 由广到窄的查询策略与来源去重 | ADAPT | 必需 | U02-C11（承接自 Collector 分流） |
| SL-CAP-0037 | 来源类型标记与覆盖记录（优先级不替代验证） | ADAPT | 必需 | U02-C14, U02-C12 |
| SL-CAP-0038 | 研究质量状态与结论边界（三态 + 不产报告的许可） | ADAPT | 必需 | U02-C13, U02-C15, U03-C27, U06-C23, U04-C26 |
| SL-CAP-0039 | 内联引用约束与可追溯性（校验器执行而非提示词） | ADAPT | 必需 | U02-C16 |

处置分布：REUSE 0 条、ADAPT 4 条、REIMPLEMENT 1 条、REJECT 0 条（但 SL-CAP-0038 内含两个 REJECT 级拒绝）。

---

## 3. 候选去向全表

| 候选 | 去向 | 理由 |
|---|---|---|
| U02-C10 四轮研究流程 | → SL-CAP-0035 | 改写成五阶段状态机 |
| U02-C11 Broad to Narrow | → SL-CAP-0036 | **承接自 Collector 分流** |
| U02-C12 五层来源优先级 | → SL-CAP-0037 | 降级为「不构成真伪排序」 |
| U02-C13 九节报告结构 | → SL-CAP-0038 | 只取内容骨架，排版归 Renderer |
| U02-C14 来源分桶 | → SL-CAP-0037 | 升级为 source_type 结构化字段 |
| U02-C15 置信度三档百分比 | → SL-CAP-0038（REJECT） | 未校准的虚假精准度 |
| U02-C16 内联引用规则 | → SL-CAP-0039 | 校验从提示词搬到校验器 |
| U03-C27 百分比豁免 | → SL-CAP-0038（REJECT） | 同一虚假精准度的另一出口 |
| U04-C26 必须产报告 | → SL-CAP-0038（REJECT） | 改为「允许只登记不产报告」 |
| U06-C23 供应商采纳审计 | → SL-CAP-0038 | 只借裁决结构 |
| **U02-C17 Mermaid 硬要求** | **→ Renderer（新增分流）** | 图表属呈现决策 |
| **U04-C24 不可复现观察标记** | **→ Evidence-Claims（新增分流）** | EC 的 SL-CAP-0020 已有 reproducible 三态 |
| **U05-C24 同名同义** | **→ Evidence-Claims（新增分流）** | 与 U04-C24 是同一需求的第二处证据 |
| U01-C12 eval baseline | 不进本批 | 属评估体系，非研究调度；留 Renderer/质量门 |
| U04-C17 仓库影响面调查 | 不进本批 | 属 Security 的影响面分析 |
| U05-C08 Phase 0 三分路由 | 不进本批 | 属知识库维护流程，近 Storage |
| U06-C25 三态分离产物契约 | 不进本批 | 属 EC/Storage 的产物模型 |

**不进的七个身份仍是 UNREVIEWED**，留给后续批次或 F1-C，不做越权认领。

---

## 4. 工程约束逐条落实

### R-A 单一 Collector
SL-CAP-0036 与 0037 的 `depends_on_modules` 均含 Collector，且描述明确「经 Collector 取数」。
全批无一处声明自建客户端、第二套事实库或旁路请求——由 c18 机检（正向判据：必须声明经 Collector）。

### R-B 来源优先级不能替代证据验证
这是本批最重要的一条裁决。SL-CAP-0037 把 U02-C12 的五层优先级显式降级：
来源类型只回答「这是什么类型的材料」，不回答「它可不可信」。
硬规则二写明：不因为来自 GitHub API 就认定内容为真——Issue 正文可能是用户报告，
README 可能是维护者声明，两者都是待验证主张而非事实。同时禁止未校准百分比（c26）。

### R-C 显式研究覆盖范围
SL-CAP-0037 的 `coverage_record` 分五列：requested / obtained / partial / truncated / unavailable，
并硬规则禁止把 partial、truncated、未读取与实际为空混为一谈（c23）。
SL-CAP-0038 要求报告声明「覆盖了什么、没覆盖什么、哪些结论依赖单一来源」。

### R-D 质量状态与任务状态分离
三态 complete / partial / facts_only 描述「研究的完备程度」，不描述「任务是否成功」。
边界写在 SL-CAP-0038 正文：「质量状态描述研究的完备程度，不描述任务是否成功，两者必须分开记录」（c22）。
最终枚举留 F2。

### R-E 受预算约束
SL-CAP-0035 每阶段必须声明 `stage_budget`（读取条目数上限、调用次数上限）；
预算耗尽时停下并保存有效证据与待研究清单，禁止产出「看起来完整」的报告。
允许先得 facts_only 再按需深入（c24）。

### R-F 保持可恢复
`resume_point{stage_id, evidence_already_gathered[]}` + 硬规则「从阶段边界续跑，只补缺口，
不重跑已完成的采集与分析」（c24）。

### R-G 安全与许可证
第三方页面/README/Issue/SKILL.md 是待分析数据而非指令——这条立场在全批描述中贯彻。
许可逐源独立记录（c31）；涉及 U06（无许可证）的 SL-CAP-0038 整体判 `copy_permitted=false`，
只取抽象裁决结构、不复制其规则原文（c32）。

---

## 5. 八项冲突裁决（逐条）

### C-1 U02-C12 的来源优先级是否错误替代 EC 的验证规则
**会，且上游本来就在替代。** 裁决：分桶保留为 `source_type` 字段，优先级被显式降级为
「不构成真伪排序」。任何「因为来源等级高所以该结论成立」的推理都被禁止——成立与否只能由
Evidence-Claims 的裁决状态机（SL-CAP-0028）判定。

### C-2 U02-C13 的报告结构归 Research 还是 Renderer
**拆开。** Research 定义「报告必须包含哪些内容项」（结论、证据引用、覆盖、边界、移交项）；
Renderer 决定「这些项怎么排版成文档」。九节骨架可作 Renderer 的输入，但章节顺序与图表
不属 Research。这是本批划界最清楚的一处。

### C-3 U02-C14 的来源分桶是研究组织还是 Evidence Registry 数据契约
**两者都是，但字段归 EC 定义、内容归 Research 填充。** 分桶在 Research 侧是组织手段
（决定下一步查哪类来源），在 Evidence 侧是数据契约（`source_type` 落进 evidence_record）。
本批在 SL-CAP-0037 定义字段与取值，实际落盘结构属 EC 的 SL-CAP-0020，避免两处各立一套。

### C-4 U02-C16 的内联引用约束由哪个模块执行
**约束由 Research 定义，执行归属留 unresolved 交 F1-C。** 但「必须有校验器」这一点不可协商：
上游只写祈使句却无任何判定手段，本条把「引用标识可解析」设为验收硬门槛（c28）。

### C-5 Research 与 Product 对同一功能的分析如何避免重复生成 Claim
**原则已定，去重键待 F2。** 产品语义 claim 候选由 Product 产出，生态与研究 claim 候选由
Research 产出，两者都进 Evidence-Claims 去重。unresolved 中记录了这条。

### C-6 Research 的任务中断与 Lifecycle 的知识失效如何保持正交
**正交。** Research 的 `resume_point` 管「这次研究跑到哪」；Lifecycle 的 SL-CAP-0027
（新鲜度四字段）管「上次结论今天还成不成立」。两者互不引用对方的失败语义——
研究中断不是知识失效，知识失效也不要求重跑研究。

### C-7 GitHub API 数据的采集时间与源码 Commit 固定版本如何分别保存
**两个独立字段。** `retrieved_at`（采集时刻，会过期）与 `verified_against_commit`
（版本锚点，不随时间变）在 SL-CAP-0037 中分列，并写明「不可互换」（c27）。
这是 F0 勘误 E-01「三字段不可互换」在本模块的同构延伸。

### C-8 多来源综合推断与已有 Claim 冲突时如何移交裁决
**产出 `handoff_item` 移交 EC。** 字段含 claim、conflicting_claim_ref、sources[]、reason。
硬规则：Research 不自行裁决冲突（c19）。这样 EC 的裁决状态机只面对一种输入格式，
不会出现「有的冲突在 Research 就地解决、有的留给 EC」的分裂。

---

## 6. 各条裁决要点

### SL-CAP-0035（REIMPLEMENT）
U02-C10 分轮顺序正确，但四条轮次只是散文：无状态载体、无轮间交接、无预算强制、无退出路径
（审计 blocker 级）。本能力改写成 R0–R4 五阶段状态机，每阶段定义输入、最小输出、跳过条件
与恢复点。两条反教条写进正文：阶段完成不等于结论正确（R3 只产候选）；资料读完不等于研究完成
（R4 必须列出 remaining_questions）。

### SL-CAP-0036（ADAPT，承接自分流）
U02-C11 查询模板可用，但上游完全没做去重与 URL 规范化——会让镜像转载击穿它自己的
「2+ 独立来源」三角验证。补规范化与内容哈希折叠后，`independent_source_count` 才可核对。
本条是本批唯一承接自 Collector 分流的身份，晋升记录 `from=cross_module_redirections`（c46）。

### SL-CAP-0037（ADAPT，二合一）
C14（分桶）与 C12（优先级）是同一件事的正反两面，且都必须落成字段才可机器校验。
合并后明确：分桶保留、优先级降级。C14 的思想正确（全套资产里最接近来源类型标记的设计）
但只是模板里的分组小标题；C12 分层直觉正确但仅有序数无权重、且「verified media outlet」无定义——
本条不追求量化权重，改采「有定义才可用」：进层规则不可判定时该层不启用。

### SL-CAP-0038（ADAPT，五合一含两处 REJECT）
C13 给内容骨架，U06-C23 给裁决形态，U04-C26 与 U02-C15/U03-C27 是必须显式拒绝的反面约束。
四者都指向同一件事：研究结论该以什么形态落地、什么叫「够了」。
C13 必须去掉固定基数与无条件 `Status: Complete`；U06-C23 只借结构不借锁模型层；
U04-C26 的「无新发现也必须产报告」在跨仓库场景会制造大量无价值写入，改采「允许只登记」。

### SL-CAP-0039（ADAPT）
U02-C16 引用纪律正确、示例教学可借，但整条只是祈使句、无机械校验。上游写着「必须内联引用」
却没有任何机制能判定产物是否真的引用了。本条把校验搬到校验器，并以「引用标识可解析」
作为验收硬门槛。

---

## 7. 新增分流（3 条）

| 身份 | 去向 | 理由 |
|---|---|---|
| U02-C17 Mermaid 图表硬要求 | Renderer | 图表是呈现决策，应由数据触发；Research 只定结论内容 |
| U04-C24 不可复现外部观察标记 | Evidence-Claims | 正是 EC SL-CAP-0020 的 reproducible 三态，不重复建条目 |
| U05-C24 同名同义 | Evidence-Claims | 与 U04-C24 是同一需求的第二处证据（审计均记为缺陷） |

三条只记去向，未在目标模块建 canonical。

---

## 8. 与既有批次的交接

- SL-CAP-0035 依赖 Facts / Collector / Product：R1 只消费已有确定性产物，不发起采集。
- SL-CAP-0036 / 0037 依赖 Collector：外部取数一律经 Collector 唯一入口。
- SL-CAP-0038 / 0039 依赖 Evidence-Claims：claim 候选与冲突移交 EC 裁决，引用指向 EC 的证据 ID。
- 与 Product 的分界见 C-5；与 Renderer 的分界见 C-2；与 Lifecycle 的分界见 C-6。
- 本批向 EC 新推入 2 条分流（U04-C24、U05-C24），EC 批次自己声明的分流已全部消费完毕，
  两者不冲突——EC 验证器 c49 已收窄为「只校验 EC 自己那句声明」，新推入单独报告（见第 10 节）。

---

## 9. unresolved（合计 17 项，逐条在各 canonical 的 unresolved 字段）

1. 各阶段预算数值待 F2（0035）
2. R2 无网络时是否允许缓存证据替代（F1-C，0035）
3. 研究中断与 Lifecycle 失效正交的具体接口（0035）
4. 内容哈希去重粒度（F2，0036）
5. negative_result 是否强制记录查询式（0036）
6. 同一来源反复更新是否视为新来源（F1-C，0036）
7. source_type 四值是否足够（F1-C，0037）
8. verified_against_commit 为空的合法情形（F2，0037）
9. 本条与 EC evidence_record 如何避免字段重复（F2，0037）
10. complete/partial/facts_only 判定阈值（F1-C，0038）
11. handoff_item 与 EC conflict_item 避免双写（F2，0038）
12. Research 与 Product 的 claim 去重键（F2，0038）
13. 引用最小粒度与 span 表示（F2，0039）
14. 「关键要素」的机械判定规则（F1-C，0039）
15. 校验器归属（Renderer 产物校验 vs 独立 linter，F1-C，0039）

均为 F1-C / F2 的实现决定，不构成本批验收缺口。

---

## 10. 验收

```
python3 tools/fusion/f1b_build_research.py      → RESULT: OK (exit 0)
python3 tools/fusion/f1b_verify.py              → 12/12 PASS (exit 0)
python3 tools/fusion/f1b_verify_collector.py    → 30/30 PASS (exit 0)
python3 tools/fusion/f1b_verify_ec.py           → 50/50 PASS (exit 0)
python3 tools/fusion/f1b_verify_product.py      → 43/43 PASS (exit 0)
python3 tools/fusion/f1b_verify_research.py     → 46/46 PASS (exit 0)
```

### 本轮修正的作用域错误（五处，均非数据缺陷）

本批推进后五个既有检查项报红，全部属于「历史批次检查历史事实」这一类的失效：

1. **EC c49** —— 原判据数「owner=Evidence-Claims 的分流总数必须为 0」。但本批合法地把
   U04-C24/U05-C24 推给 EC，那是正常职责裁决。已收窄为「只校验 EC 自己 def 声明的那批在接手后
   不得残留」，新推入的分流单独计数、不计失败。
2. **Product c6** —— 要求全局最大编号恒为 34。后续批次必然超过。改为「Product 自身编号 0029–0034 连续」。
3. **Product c29** —— 拿当前全局数卡历史文档。改为与 Facts c11 / EC c47 同口径：文档内累计快照自洽。
4. **Product c37** —— 重跑 `f1b_build_product.py` 会在后续草稿上触发其编号起点断言（保护性 exit 1）。
   改为调用 `f1b_stats` 重算验证幂等。
5. **Product c38** —— 「重跑前后一致」对历史批次已不适用。改判为「历史批次关键字段定格未漂移」。

核心不变量（三态互斥、合计 143、身份唯一归属、晋升留痕）一条未放宽。

### 幂等性

`f1b_build_research.py` 重跑后 `canonical_capabilities`、`cross_module_redirections`、
`routed_promotions`、`batches`、`global_state_counts`、`module_rollup` 六个核心字段逐字节一致。

---

## 11. 下一批

F1-B 剩余五个模块：Lifecycle → Security → Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0040` 起。

本批未启动 F2，未修改正式分析引擎，未处理其余五个模块。
