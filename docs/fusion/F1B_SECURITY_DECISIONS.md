# F1-B / Security 批次 · 设计裁决

生成器：`tools/fusion/f1b_build_security.py`（定义在 `tools/fusion/f1b_security_def.py`）
验证器：`tools/fusion/f1b_verify_security.py`（53 条检查，只写 `F1B_SECURITY_VERIFICATION.json`）

本批是 F1-B 的第七批。前六批（Facts 10、Collector 9、EC 9、Product 6、Research 5、Lifecycle 6，
共 45 条）已分别提交并验收。本批只追加 `SL-CAP-0046`…`SL-CAP-0054`，不改写 0001–0045。

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| Security 候选（含 ROUTED 承接与全库补充） | 22 |
| 本批正式承接的原始身份 | 17 |
| 判给其它模块的身份（新增分流） | 5 |
| 本批 canonical 能力 | 9 |
| 累计 MAPPED（全模块） | 83 |
| 累计 ROUTED（挂起分流） | 14 |
| 累计 UNREVIEWED | 46 |
| 累计 canonical | 54 |
| 去重比（本批 原始:canonical） | 1.89 : 1 |

三态之和校验：83 + 14 + 46 = 143。

按来源分布（本批 17 个身份）：U01 0、U02 0、U03 0、U04 0、U05 1、U06 16。

---

## 2. 九条 canonical 能力

| ID | 名称 | 处置 | V1 | 来源 |
|---|---|---|---|---|
| SL-CAP-0046 | 两阶段信任边界与阶段间上下文卫生 | ADAPT | 必需 | U06-C01, C02 |
| SL-CAP-0047 | 安全发现契约与四项独立检查（证据分级） | REIMPLEMENT | 必需 | **零来源**（见第 6 节） |
| SL-CAP-0048 | 确定性前置门与失效安全 | ADAPT | 必需 | U06-C03, C04, C12, C09 |
| SL-CAP-0049 | 依赖风险的五级分离与可达性三态 | ADAPT | 必需 | U06-C15, C16 |
| SL-CAP-0050 | 族扫描、覆盖缺口登记与诚实否定 | REUSE | 必需 | U06-C14, C08 |
| SL-CAP-0051 | 动态验证的双重控制与结构性构造门 | REUSE | 必需 | U06-C11, C28(REJECT) |
| SL-CAP-0052 | Agent / Skill 指令安全与不可信数据处理 | ADAPT | 必需 | U06-C22 |
| SL-CAP-0053 | 敏感信息分级、脱敏与发布门禁 | REIMPLEMENT | 必需 | U05-C20, U06-C17, C27 |
| SL-CAP-0054 | PR Diff 增量安全审查与移除控制回归 | REUSE | 必需 | U06-C24 |

处置分布：REUSE 3、ADAPT 4、REIMPLEMENT 2、REJECT 0（但 SL-CAP-0051 内含一个 REJECT 级拒绝）。

---

## 3. 候选去向全表

| 候选 | 去向 | 理由 |
|---|---|---|
| U06-C01 双阶段信任边界 | → SL-CAP-0046 | 分层结构 |
| U06-C02 上下文卫生 | → SL-CAP-0046 | 反锚定纪律 |
| U06-C03 Surface Gate | → SL-CAP-0048 | 确定性前置门 |
| U06-C04 Boundary Gate | → SL-CAP-0048 | 需改为确定性 auth 抽取 |
| U06-C08 证据升级阶梯 | → SL-CAP-0050 | 只取「逐级升级」，拒绝 docker 执行 |
| U06-C09 环境失败不改判 | → SL-CAP-0048 | 门判定的保护规则 |
| U06-C11 双重控制 | → SL-CAP-0051 | 最强安全设计 |
| U06-C12 失效安全门控 | → SL-CAP-0048 | 不确定时扩大扫描面 |
| U06-C14 族扫描诚实否定 | → SL-CAP-0050 | 否定结论带覆盖面 |
| U06-C15 依赖可达性三态 | → SL-CAP-0049 | 三态写进 claim |
| U06-C16 严重度与优先级 | → SL-CAP-0049 | 两字段分离 |
| U06-C17 密钥打码 | → SL-CAP-0053 | 改为结构约束 |
| U06-C22 Skill/Agent 安全 | → SL-CAP-0052 | 改为无条件自审 |
| U06-C24 PR Diff 增量审查 | → SL-CAP-0054 | **承接自 Collector 分流** |
| U06-C27 密钥/数据分级 | → SL-CAP-0053 | 分级落成字段 |
| U06-C28 一键装扫描器 | → SL-CAP-0051（REJECT） | 无版本钉定、无校验 |
| U05-C20 保密分级与脱敏 | → SL-CAP-0053 | **承接自 Lifecycle 分流** |
| **U06-C18 成本报告** | **→ DSH-Adapter（改路由）** | 见第 7 节 |
| **U06-C10 动态否证人工复核** | **→ Evidence-Claims** | 属通用 claim 状态机人工复核分支 |
| **U06-C20 延迟裁决** | **→ Evidence-Claims** | 属 claim 裁决时序与跨源聚合 |
| **U06-C19 多仓库拓扑** | **→ Storage** | 会产生第二套关系模型 |
| **U06-C25 三态产物契约** | **→ Storage** | 持久化产物模型 |

---

## 4. 安全发现与 Claim 的关系（核心契约）

安全发现固定九字段：`source_commit_sha`、`affected_component`、`category`、`evidence_refs`、
`data_flow`（适用时）、`validation_status`、`severity`、`remediation_priority`、`detection_limitations`。
缺任一项即判不完整，不得进入报告。

**四项独立检查（任一不可推出另一）：**

| 检查 | 答什么 | 不满足时的后果 |
|---|---|---|
| C-1 位置存在 | 文件与行号确实在快照中 | 直接判无效 |
| C-2 数据流链完整 | 入口经各跳到落地齐全 | 只对需要链路的类型；缺则记 limitations |
| C-3 安全影响成立 | 该模式构成风险而非风格 | 停在 inconclusive |
| C-4 运行时可达性 | 攻击者确实能触达 | 只记 INDETERMINATE，不判 UNREACHABLE |

**两条硬规则：**
- 没有足够证据的风险只能停在 `unconfirmed`，不得直接成为确认漏洞。
- 无法验证不能自动标记为 `false_positive`，它停在 `inconclusive`。

这两条直接继承 F0 与 Evidence-Claims 对上游 `can't prove → FALSE_POSITIVE` 的既有拒绝。
`U06-C06` 已由 EC 的 `SL-CAP-0028` 承接，本批**不重复占用**（c53 专门校验 C05/C06/C07 仍归 EC）。

**证据单源：** `evidence_refs` 一律指向 EC 的证据记录 ID，禁止另建 Security Evidence Registry。
需要数据流链时直接引用 EC 的 `SL-CAP-0021` 结构，不重复定义节点语义。这也是 `SL-CAP-0047`
成为零来源条目的原因（见第 6 节）。

---

## 5. 主要规则逐条（R-A … R-F）

### R-A 生产面与非生产面
Surface Gate 对测试目录、示例代码、生成物做确定性抑制与置信度封顶。
但**路径名只是信号**，不得在缺乏证据时直接证明代码不进生产环境（c26 校验）。

### R-B 认证与授权边界
三态分列：`authenticated`（已证明受认证保护）/ `anonymous`（已证明可匿名访问）/ `unknown`（覆盖情况未知）。
认证覆盖必须来自确定性抽取，**不得用模型推断的 auth_coverage 自动降级高风险发现**；
覆盖 `unknown` 时 Boundary Gate 直接不生效。

### R-C 依赖漏洞五级分离
`D-1 存在性` → `D-2 版本` → `D-3 公告匹配` → `D-4 代码可达性` → `D-5 部署暴露面`。
可达性三态 `REACHABLE / UNREACHABLE / INDETERMINATE`，写在 claim 本身，
**不得像上游那样先留 null 由后续阶段回填**（中间态语义会丢失）。
有界静态搜索未发现调用路径时，原则上不得直接宣称 `UNREACHABLE`（c25 校验）。

### R-D 严重度与优先级
`severity`（脆弱性强度）与 `remediation_priority`（现在该先修哪个）是两个独立字段，不得压成一个数字。
禁止未经校准的模型置信百分比（c24 校验）。

### R-E 缺失工具与覆盖不足
扫描器未运行、规则未覆盖、路径因权限或分页未取到时，必须产出 `coverage_gap{scanner, category, missing_scope}`。
**禁止输出「不存在该类漏洞」**（c27 校验）。

### R-F 安全发现的新增与失效
Security 只负责「哪些变化需要安全重审」的判定；实际变化集由 Collector 取，重验证调度由 Lifecycle 做。
Security 不建第二套知识有效性状态（c18/c19 校验）。

---

## 6. Agent / Skill 安全（A-1 … A-7）

SourceLore 自己就是 skill/agent 产物，故对自己施加与被分析仓库同等的约束：

| 规则 | 内容 |
|---|---|
| A-1 | README / SKILL.md / Issue / 代码注释 / 配置值一律是待分析数据，不得提升为系统级指令 |
| A-2 | 外部内容不得要求执行本地 shell 命令 |
| A-3 | 不得借分析任务读取无关私有文件或环境变量 |
| A-4 | 工具调用遵循最小权限 |
| A-5 | 未经明确授权不得上传本地私有源码到第三方服务 |
| A-6 | 敏感信息不得直接进入报告或知识卡片 |
| A-7 | 不能让被分析仓库决定 SourceLore 的审查步骤或安全策略 |

**硬规则：** A-1 至 A-7 必须以可检查的规则形式存在（每条带 `rule_id` + `detection_method` + `failure_action`），
不接受「请注意不要被注入」这类散文（c29 校验）。
A-7 是元级约束：审查步骤由 SourceLore 决定，外部仓库只能作被审对象（c30 校验）。
OWASP LLM Top 10 类清单只作自审项来源，不构成自动通过的门；自审未跑必须登记 coverage_gap。

---

## 7. 保密分级与发布权限

**四级门禁，互不推导：**

| 门 | 状态 | 谁能触发 |
|---|---|---|
| P-1 | 分级完成（每条内容都有级别） | 机器 |
| P-2 | 脱敏完成（机械剥离已跑且无残留） | 机器 |
| P-3 | 人工审查（`human_reviewed`） | **只能是人** |
| P-4 | 发布批准（`approved_for_release`） | **只能是人** |

三条硬规则（c31/c32 校验）：
1. AI 可以准备候选，但**不得自行把需要人工批准的产物标记为 approved**；P-3/P-4 只能由人的动作触发。
2. **脱敏通过（P-2）不等于允许公开发布**。脱敏只是必要条件，发布范围由 P-4 决定。
3. **原始扫描输出不落盘是结构约束，不是事后删除**——上游「尽力删除、失败仅告警」不可采纳，
   一旦落盘就已经泄露。

`U05-C04`（review_status 人机权限）已由 EC 的 `SL-CAP-0028` 承接部分语义，
本批**只登记跨模块依赖，不重新占用该原始身份**。

---

## 8. 特别待裁决事项（Z-1 … Z-7，逐条登记，不擅自更改）

| 编号 | 事项 | 处理 |
|---|---|---|
| Z-1 | `U06-C18` 是否应从 Security 改路由至 DSH Adapter | **本批已改路由**，理由留痕（见下） |
| Z-2 | `SL-CAP-0045` 零上游来源的最终 origin 类型 | **交 F1-C** |
| Z-3 | `U05-C04` 与 EC 审批能力的职责边界 | 只登记依赖，不重新占用 |
| Z-4 | Security 与 Lifecycle 的风险重验证接口 | 交 F1-C |
| Z-5 | Security 与 EC 的验证状态及证据引用接口 | 交 F2 |
| Z-6 | 保密分级与 Storage 的实际访问控制接口 | 交 Storage 批次 |
| Z-7 | 严重度 / 置信度 / 优先级如何保持独立 | 本批已定 severity 与 priority 独立；置信度一律禁百分比，进一步分级交 F2 |

**Z-1 的改路由理由（完整留痕）：**
`U06-C18` 是运行成本与可观测性报告（时长 + token 估算）。Collector 批次把它判给 Security，
当时的理由是「成本报告是安全审查运行的自报字段」。本批按实际内容重新裁决：
成本与运行可观测性本质是 Agent 运行成本，属 DSH Adapter 的范围，不属安全分析。
原始分流记录中保留这一重新裁决的原因，以便追溯（c52 校验）。

---

## 9. UPSTREAM-06 许可证红线

UPSTREAM-06 **没有明确复制授权**。处理：

- 全部 16 个 U06 来源的 `license_permission` 保持 `copy_permitted=false`（c35 校验）。
- 任何含 U06 来源的条目整体判 `copy_permitted=false`。
- 不复制上游脚本、规则原文、Claude Code 提示词、报告模板、安全检查代码。
- 即使处置为 REUSE / ADAPT，也只表示**借用设计思想**，不代表获得复制授权。
- 本批九条全部是 SourceLore 自建的契约描述，没有一处逐字搬运上游文本。

U05-C20 为 Apache-2.0，须履行署名、许可链接与修改声明三项义务。

---

## 10. 禁止实际安全执行

本轮完全**未执行**任何安全操作：未运行 `setup.sh`、未构建或运行 Docker、未调用 Semgrep / Gitleaks /
OSV 扫描、未做动态探测、未构造或执行 PoC、未对任何真实服务发起网络请求。
所有内容来自静态阅读既有审计产物。动态测试状态与本次静态验收完全分离。

---

## 11. 本轮修掉的问题

### 既有验证器作用域过时（两处，非数据缺陷）

Lifecycle 验证器因本批承接了它曾推出去的 `U05-C20` 而报红：

1. **c15 批次记录自洽** —— 原判据要求 `redirected == 5`。出向按统计契约是现算视图
   （def 声明 − 已晋升），本批接手后必然降为 4。改为「与现算自洽」。
2. **c47 新增分流去向** —— 原判据要求五条都在路由表里。承接后它们移入 mapped，属晋升的正常结果。
   改为「要么仍在路由表且去向正确，要么已被预期目标模块承接（有晋升记录可查）」。

两处均只修正时间作用域，未放宽身份唯一性、三态守恒、许可隔离等核心不变量。

### 定义文件自身错误（一处）

初版把 `U06-C28` 同时写进 `SL-CAP-0051` 与 `SL-CAP-0052` 的 refs，构成同一身份二次映射。
已改为：正式归属只在 `SL-CAP-0051`（verdict=REJECT），`SL-CAP-0052` 仅在描述中作为反例引用。
自检从 18 条引用降到 17 条唯一，`CONSUMED_THIS_BATCH` 与 refs 集合完全一致。

---

## 12. 验收

```
python3 tools/fusion/f1b_build_security.py     → RESULT: OK      exit 0
python3 tools/fusion/f1b_verify.py              → 12/12 PASS      exit 0
python3 tools/fusion/f1b_verify_collector.py    → 30/30 PASS      exit 0
python3 tools/fusion/f1b_verify_ec.py           → 50/50 PASS      exit 0
python3 tools/fusion/f1b_verify_product.py      → 43/43 PASS      exit 0
python3 tools/fusion/f1b_verify_research.py     → 46/46 PASS      exit 0
python3 tools/fusion/f1b_verify_lifecycle.py    → 48/48 PASS      exit 0
python3 tools/fusion/f1b_verify_security.py     → 53/53 PASS      exit 0
```

幂等性：`f1b_build_security.py` 重跑后六个核心字段逐字节一致，分流零重复。

---

## 13. 下一批

F1-B 剩余三个模块：Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0055` 起。

本批未启动 F2，未修改正式分析引擎，未处理其余三个模块。
