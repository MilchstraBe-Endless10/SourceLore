# F1-B / Evidence-Claims 批次 · 设计裁决

生成器：`tools/fusion/f1b_build_ec.py`（定义在 `tools/fusion/f1b_ec_def.py`）
验证器：`tools/fusion/f1b_verify_ec.py`（50 条检查，只写 `F1B_EC_VERIFICATION.json`）

本批是 F1-B 的第三批，前两批（Facts、Collector）已分别提交并验收。本批只追加
`SL-CAP-0020`…`SL-CAP-0028`，不改写 0001–0019。

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| 本批承接的原始身份（ROUTED） | 9 |
| 本批另外采纳的未审命中（未审直采） | 3 |
| 本批 canonical 能力 | 9 |
| 本批出向分流（推向其它模块） | 0 |
| 累计 MAPPED（全模块） | 34 |
| 累计 ROUTED（挂起分流） | 5 |
| 累计 UNREVIEWED | 104 |
| 累计 canonical | 28 |
| 去重比（本批 原始:canonical） | 1.33 : 1 |

三态之和校验：34 + 5 + 104 = 143。

按来源分布（本批 12 个身份）：U01 1 项、U02 0 项、U03 1 项、U04 5 项、U05 2 项、U06 3 项。

U02 为零是承接边界的结果，不是遗漏：本批没有从 Collector 剥离任何采集职责，
U02 的能力已全部在前两批归属完毕。

---

## 2. 九条 canonical 能力

| ID | 名称 | 处置 | V1 | 来源 |
|---|---|---|---|---|
| SL-CAP-0020 | 证据材料存档契约（形态三分 + 强制元数据） | ADAPT | 必需 | U04-C07, U04-C08 |
| SL-CAP-0021 | 逐跳数据流证据定位（四节点 file:line） | REIMPLEMENT | 必需 | U06-C05 |
| SL-CAP-0022 | 引用存在性与定位校验 | ADAPT | 必需 | U01-C03 |
| SL-CAP-0023 | 显式未知优于自信猜测 | REUSE | 必需 | U03-C03 |
| SL-CAP-0024 | 缺料以占位符显式登记而非编造 | REUSE | 必需 | U05-C05 |
| SL-CAP-0025 | 产物自证出处（Auto-generated 头 + 溯源字段） | REUSE | 必需 | U05-C06 |
| SL-CAP-0026 | 结论四段结构与观察/解释分离 | ADAPT | 必需 | U04-C10 |
| SL-CAP-0027 | 结论生命周期与新鲜度（四字段 + 结构化替代关系） | ADAPT | 必需 | U04-C09, U04-C11 |
| SL-CAP-0028 | 裁决状态机与 report_tier 映射（不可验证 ≠ 不存在） | ADAPT | 必需 | U06-C06, U06-C07 |

处置分布：REUSE 3 条、ADAPT 5 条、REIMPLEMENT 1 条、REJECT 0 条。

REJECT 为零需要解释：本批没有「只留反例、不留实现」的条目，但 REJECT 的语义
并未消失——它落在 SL-CAP-0028 的对照组上（见第 5 节 E-6）：被拒绝的是上游的
「不可验证即判否」这条规则本身，而不是上游的某个原始身份，因此不以 verdict=REJECT
登记，而以显式拒绝条款登记。

---

## 3. 为什么是九条而不是十二条

第 D 节识别出 9 条 ROUTED 加 5 条未审语义命中，共 14 个候选。裁决后：

- 判给 Product 的 2 条（U03-C01 边界三分类、U03-C06 产品八要素）不进本批。
  这两项讲的是「产品边界怎么划」，不是「证据怎么立」，归属 Product。
- 判给 Security 的 2 条（U06-C04 Boundary Gate、U06-C07 …）中，U06-C04 归 Security；
  U06-C07 的状态机语义本批需要（结论状态如何判），因此归本批。
- 真正进入本批的 12 个身份，合成为 9 条 canonical，其中两组合并：
  - U04-C07 + U04-C08 → SL-CAP-0020：形态面与元数据面，拆开各缺一半。
  - U04-C09 + U04-C11 → SL-CAP-0027：同一条 claim 的「还算不算数」两个维度。
  - U06-C06 + U06-C07 → SL-CAP-0028：状态机的骨与边，拆开则「查不到怎么算」无处安放。
- U06-C05 独立成 SL-CAP-0021：它是证据结构（链路定位），与状态机不是一件事。

合并判据统一为「同一条能力的不同侧面，拆开后任何一侧都不完整」。名称相似但
语义不同的（如 U01-C03 的「引用校验」与 U06-C05 的「链路定位」）一律不合并。

---

## 4. 各条裁决要点

### SL-CAP-0020（ADAPT）
U04-C07 的三分法（完整存 / fixture+说明 / 不存）方向正确，但缺 `content_hash`、
`reproducible` 三态与 `redactions`；U04-C08 的五样清单（响应体、相关头、无凭据请求元数据、
命令+日期+版本+输入、差异说明）内容扎实，但只是散文要求。两者修正方向一致：散文变必填字段。
缺任一项即判材料不完整，不得当证据用。

### SL-CAP-0021（REIMPLEMENT）
U06-C05 是全篇最可迁移的证据形态，但它有两个不可沿用的问题：U06 全 28 项
`copy_permitted=false`，实现只能独立完成；上游的四节点是散文报告段落，无结构化字段、
无 `partial_flow` 降级态，缺一跳整条作废。本能力固化 schema 并补显式降级。

### SL-CAP-0022（ADAPT）
U01-C03 只做 `tree_paths` 集合成员测试，没有行号、没有哈希、没有支撑关系，
所以 present 之外的两种状态根本不存在。补齐三态后要守住一条：`unresolvable`
不得并入 `missing`——树被截断时「没找到」不等于「不存在」。这条是 F0 勘误与
Facts 的 SL-CAP-0004 在本模块的落点。

### SL-CAP-0023（REUSE）
U03-C03 两句话短、无歧义、无工具依赖，`Unsupported claims MUST NOT be presented as facts`
可直接作 prompt 级硬规则。许可 CC-BY-4.0，须履行署名、许可链接、修改声明。

### SL-CAP-0024（REUSE）
U05-C05 对应「insufficient 是成功结果」这一不变量，且上游有代码出口
（`render_markdown_artifact` 强制渲染 needs_input 列表），比纯散文要求强。
注意：其承接 reason 自带 `[NEEDS INPUT]` 标记，本批只登记占位语义与占位机制，
不代为发明渲染格式——格式留 unresolved。

### SL-CAP-0025（REUSE）
U05-C06 使「这行字是谁写的」可机械判定，直接对应 evidence_refs 溯源要求。
与 SL-CAP-0024 是 U05 的两条独立机制（一条管缺料、一条管出处），不合并。

### SL-CAP-0026（ADAPT）
U04-C10 的四段划分合理，L26「观察事实与解释可分离」是本模块最关键的不变量，
但上游写成 Markdown 段落标题，无法机器校验 evidence 段里混没混解释。修正即转 schema 字段。

### SL-CAP-0027（ADAPT）
U04-C11 把五种生命周期混在一个自由文本串里，无法比对，须拆成 `verified_commit`、
`verified_deps`、`verified_env`、`accessed_at` 四字段。U04-C09 的 superseded
只写在标题文字里、只有一种关系，无法机器查询，升级为独立关系字段并扩展为
`superseded_by` / `supersedes` / `retracted_reason`；被替代与已撤回的历史记录不得删除。

### SL-CAP-0028（ADAPT）
状态机取四主（unverified / partially_supported / supported / refuted）加两辅
（insufficient_evidence / adjudication_blocked），report_tier 固定映射为
confirmed / qualified / insufficient / refuted。source 侧九态压缩映射到本模块状态，
映射表必须逐条落盘，不得隐式换算。

---

## 5. 第 E 节六项约束的落实

### E-1 每个 canonical 只有唯一 owner 且不重排既有编号
9 条全部 `owner_module="Evidence-Claims"`，编号 0020–0028 连续，0001–0019 的 owner 未变
（c7/c8/c9/c10 覆盖）。

### E-2 每项原始身份只归属一次，且三态互斥
12 个身份全部只出现一次；分流与归属零重叠；34+5+104=143（c11/c12/c13）。

### E-3 处置与许可分离，逐源记录，不得互相推导
`disposition` 与 `license_permission` 是两个字段；许可逐源照抄，含 U06 的条目整体判
`copy_permitted=false`（c37/c38）。许可义务按 spdx 逐项保留：MIT 与 Apache-2.0 需署名，
CC-BY-4.0 另需许可链接与修改声明。

### E-4 上游无来源的条目必须写明独立设计理由
本批无零来源条目（9 条各有来源），但合并理由逐条写入 `merge_note`（c39）。

### E-5 缺口必须显式，不得静默补写
三处落点：SL-CAP-0022 的 `unresolvable` 与 `missing` 分列；SL-CAP-0024 的
`[NEEDS INPUT]` 占位不编造；SL-CAP-0020 的 `none` 形态必须登记不可获取原因
（c28/c29/c31）。

### E-6 「不可验证即判否」被显式拒绝
上游 U06-C06 的原文语义是 can't prove → FALSE_POSITIVE，把「说不清」直接归入否定。
本批裁决：只取其「必须给悬置一个确定去向」的取向，去向改为 `insufficient_evidence`。

硬规则（写入 SL-CAP-0028 与本文件）：**不可验证只产生 insufficient_evidence，
禁止落成 refuted。无法证明不等于已被证伪。**

该拒绝是裁决结论，不是待办项。理由：SourceLore 的核心不变量之一是
「insufficient 是成功结果」；若把无法证明判成否证，则「没有证据」与「有反证」在产物里
不可区分，而这正是六源审计中反复出现的静默失败形态。U06-C06 因此判 ADAPT 而非 REUSE，
且拒绝语义记入 `merge_note` 与本节（c36/c50）。

---

## 6. 与既有批次的交接

- SL-CAP-0020 / 0022 / 0025 / 0027 依赖 Collector：字节、树、行号可定位性来自 SL-CAP-0015
  与 SL-CAP-0013 的钉定快照；本批不重新定义采集。
- SL-CAP-0021 / 0022 依赖 Facts：入口点候选与树截断状态分别由 SL-CAP-0006 与
  SL-CAP-0004 提供；本批只负责把节点挂到结论上。
- SL-CAP-0027 与 Lifecycle 的过期检测共用 commit/deps 锚点；本批只定义字段与比对语义，
  不定义检测调度。U05-C17 仍在 Lifecycle 名下，未被本批抢占。
- SL-CAP-0028 的 `report_tier` 供 Renderer 消费；Renderer 批次接手时不得另立映射。

本批不向任何模块外推分流（`DEFERRED_TO_OTHER_MODULE` 为空），EC 是纯接收方。

---

## 7. 仍挂起的 5 条分流（记录在案，不属本批）

`UPSTREAM-01 C10 → Renderer`、`UPSTREAM-02 C11 → Research`、`UPSTREAM-05 C17 → Lifecycle`、
`UPSTREAM-06 C18 → Security`、`UPSTREAM-06 C24 → Security`。

---

## 8. 本批留下的 unresolved（不隐藏）

汇总 9 条的待定项，均在各自条目的 `unresolved` 字段中：

1. redactions 语法与最小复现片段切分粒度（SL-CAP-0020）
2. 跨文件 hop 是否需附带分支条件上下文；同 sink 多链路的去重键（SL-CAP-0021）
3. 符号解析在无语言分析器时的退化策略（SL-CAP-0022）
4. fact/hypothesis/unknown 是否允许模型自评（本批取机械判据）（SL-CAP-0023）
5. 占位符是否需 slot_id 后缀（SL-CAP-0024）
6. `edited_by_human` 的编辑范围表示；source_snapshot 引用形态（SL-CAP-0025）
7. answer 段混入推断的标注语法；limitations 是否允许为空（SL-CAP-0026）
8. `verified_deps` 表示形态；superseded 与 retracted 是否可并存（SL-CAP-0027）
9. refuted 所需反证强度；`adjudication_blocked` 何时自动转回（SL-CAP-0028）

这些是 F2 的实现决定，不是本批的验收缺口。

---

## 9. 验收

`python3 tools/fusion/f1b_verify_ec.py` → 50 条检查，结果写入 `F1B_EC_VERIFICATION.json`。

顺序执行（Facts → Collector → EC）时，前两批验证器为 12/12 与 30/30，本批为 50/50。

注意一处口径修正：`f1b_verify.py` 与 `f1b_verify_collector.py` 原先各自把「当时全局数字」
与「本批晋升集合」写死成判据，导致后续批次推进后必然报假阳性（实测 Facts c10/c11、
Collector c27 三条误红）。本轮已收窄作用域：Facts c10 只判 Facts 自己的 canonical 是否占用
保留项，Facts c11 改为「文档内累计快照自洽 + 原始总数 143」而非等于当前全局值，
Collector c27 只对本批晋升做 ghost 判定。判据收窄不降低强度，只是把「历史文档必须等于
现在」这条不可能成立的要求去掉。
