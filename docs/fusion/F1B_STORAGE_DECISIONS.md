# F1-B / Storage 批次 · 设计裁决

生成器：`tools/fusion/f1b_build_storage.py`（定义在 `tools/fusion/f1b_storage_def.py`）
验证器：`tools/fusion/f1b_verify_storage.py`（54 条检查，只写 `F1B_STORAGE_VERIFICATION.json`）

本批是 F1-B 的第九批。前八批（Facts 10、Collector 9、EC 9、Product 6、Research 5、
Lifecycle 6、Security 9、Renderer 7，共 61 条）已分别提交并验收。
本批只追加 `SL-CAP-0062`…`SL-CAP-0067`，不改写 0001–0061。

**范围声明**：本轮是融合设计与产物验证，不安装任何依赖、不建立正式数据库、
不实现持久化引擎、不要求 Docker。**不得宣称真实数据库的事务与并发性能已得到测试。**

---

## 1. 数字

| 项 | 值 |
|---|---|
| 原始能力总数 | 143 |
| Storage 候选 | 14 |
| 本批正式承接的原始身份 | 11 |
| 判给其它模块的身份（新增分流） | 2 |
| 本批 canonical 能力 | 6 |
| 累计 MAPPED（全模块） | 105 |
| 累计 ROUTED（挂起分流） | 11 |
| 累计 UNREVIEWED | 27 |
| 累计 canonical | 67 |
| 去重比（本批 原始:canonical） | 1.83 : 1 |

三态之和校验：105 + 11 + 27 = 143。

按来源分布（本批 11 个身份）：U01 0、U02 0、U03 0、U04 5、U05 5、U06 1。

---

## 2. 六条 canonical 能力

| ID | 名称 | 处置 | V1 | 来源 |
|---|---|---|---|---|
| SL-CAP-0062 | 四层资产模型与单一权威 | REIMPLEMENT | 必需 | U04-C03（承接自分流）, U05-C18 |
| SL-CAP-0063 | 身份层级与版本标识 | REIMPLEMENT | 必需 | **零来源**（内部需求，见第 7 节） |
| SL-CAP-0064 | 原子写入、乐观并发与崩溃恢复 | REIMPLEMENT | 必需 | U04-C22（承接自分流）, U05-C22 |
| SL-CAP-0065 | 可重建派生索引与跨会话查询 | REIMPLEMENT | 必需 | U04-C23（承接自分流）, U05-C23, U04-C04 |
| SL-CAP-0066 | 多仓库关系持久化 | REIMPLEMENT | 必需 | U06-C19（承接自分流） |
| SL-CAP-0067 | 知识资产根目录隔离与路径安全 | REIMPLEMENT | 必需 | U05-C09, U04-C25(REJECT), U05-C26(REJECT) |

处置分布：REUSE 0、ADAPT 0、REIMPLEMENT 6、REJECT 0（但 0067 内含两个 REJECT 级反例）。

---

## 3. 权威资产模型（四类数据的读写依赖）

```
        ┌─────────────────────────────────────────────┐
        │  A 层：不可变历史资产                        │
        │  Evidence / Findings / 历史 Claim /          │
        │  来源快照引用 / 变更记录                     │
        │  写：仅 append      读：任意                 │
        └───────────────┬─────────────────────────────┘
                        │ 派生（单向，不可回写）
                        ▼
        ┌─────────────────────────────────────────────┐
        │  B 层：可变当前视图                          │
        │  Subject 当前版本 / 当前引用 / 最新有效视图   │
        │  写：CAS update     读：任意                 │
        └───────────────┬─────────────────────────────┘
                        │ 索引构建（可整体重建）
                        ▼
        ┌─────────────────────────────────────────────┐
        │  C 层：派生索引                              │
        │  全文 / 关系 / 导航索引                      │
        │  写：rebuild only   读：查询入口             │
        └───────────────┬─────────────────────────────┘
                        │ 消费（只读）
                        ▼
        ┌─────────────────────────────────────────────┐
        │  D 层：展示产物（Renderer 负责）             │
        │  Markdown / 卡片 / 报告 / 导航页             │
        │  写：generate only  读：发布                 │
        └─────────────────────────────────────────────┘
```

**硬规则（c18/c19/c20 机检）：**
- 同一事实不得同时存在两个可独立修改的权威副本。
- B 层「当前值」与 A 层历史冲突时，以 A 层为事实源，B 层只是指针。
- C 层可被整体删除：删除后权威数据不受影响，重建后查询结果等价。
- D 层不得回写 A/B 层。

---

## 4. 身份与版本

| 类别 | 标识 | 性质 |
|---|---|---|
| 逻辑身份 | `repository_id`、`subject_id`、`claim_id` / `evidence_id` | 长期稳定、跨版本不变、永不复用 |
| 内容身份 | `content_hash` | 内容派生、确定性 |
| 业务版本 | `artifact_version`、当前版本指针、`superseded_by` | 人为推进 |

**六个标识必须分列，不得互替**（c21 机检）：`repository_id`、`subject_id`、`commit_sha`、
`root_tree_sha`、`evidence_id`/`claim_id`、`artifact_version`。

**Subject 身份约束（c22）：** 不得用仓库 URL、文件路径或 Commit SHA 作为 Subject 的永久唯一身份。
`repository_id` 可作仓库身份锚点，但不得自动等同于所有知识 Subject 的唯一身份
（一个仓库可有多个 Subject，一个 Subject 也可能跨仓库）。

这是 F0 勘误 E-01「三字段不可互换」的扩展：从「取数三字段」扩到「全部身份标识」。

---

## 5. 原子写入与并发（W-1..W-5）

| 步 | 动作 | 失败后果 |
|---|---|---|
| W-1 | 先写临时/隔离区域 | 权威位置不受影响 |
| W-2 | 校验结构完整性与引用完整性 | 拒绝提交 |
| W-3 | 记录预期当前版本 `expected_version` | 作为 CAS 基准 |
| W-4 | 版本一致才提交 B 层指针；不一致返回 CONFLICT | 禁止静默覆盖 |
| W-5 | 失败/崩溃后权威位置保持上一份已提交状态 | 临时残留可安全清理 |

**四条硬规则（c23/c24/c25/c26 机检）：**
1. **多文件重命名不得宣称跨文件原子事务**——文件系统 rename 只保证单文件原子性；
   跨文件原子性需要显式提交日志或真正的事务存储。**原子性范围必须如实声明。**
2. 并发冲突必须明确返回（CONFLICT），不得吞掉并降级为空结果。
3. 重试不得重复创建相同的不可变对象（A 层按 `content_hash` 幂等）。
4. 崩溃恢复后必须能判断哪些写入已提交：已提交 = 权威位置可见；未提交 = 仅临时区域可见。

**可选实现手段**（由 F2 选定，本批只定接口语义）：文件系统 + 原子 rename / SQLite 事务 /
单写者队列 / 乐观并发控制 CAS / 不可变对象存储 + 当前指针。

---

## 6. 跨会话查询的九项能力

| 类别 | 查询 |
|---|---|
| 按身份 | 按 `repository_id` 找仓库知识、按 `subject_id` 恢复 Subject、按 `claim_id` 找证据与裁决、按 `commit_sha` 查历史版本 |
| 按属性 | 按路径/组件找受影响知识、按状态找需重验证的条目、按知识类别（Product/Research/Security）筛选、按版本/来源/状态复合过滤 |
| 按通道 | 查新知识走索引，消费已知知识走直链 |

**五条硬规则（c27/c28/c29/c30 机检）：**
每条结果必须携带 `source_snapshot` 与 `retrieved_from_layer`；
查询结果来自已登记知识，不意味着被查仓库的实时状态，检索命中不能自动成为已验证的新 Claim；
索引可整体重建，重建后同一查询返回等价结果；
不得在没有必要时引入向量数据库或图数据库；
权限拒绝必须显式返回 `denied`，**不得伪装成空结果**。

---

## 7. 多仓库关系（五类分离）

| 关系 | 判定依据 | 身份含义 |
|---|---|---|
| R-1 同一仓库身份延续 | `repository_id` 不变 | 同一 Subject |
| R-2 Fork | `forked_from` | 关联，非延续；各自独立 Subject |
| R-3 代码依赖 | 依赖清单解析（Facts 取） | 关系条目 |
| R-4 Submodule / 仓库引用 | 仓库内引用声明 | 关系条目 |
| R-5 研究发现的关联 | Research 的证据 | 关系条目，须带 `evidence_refs` |

**硬规则（c31/c32 机检）：** 关系条目必须带 `relation_kind` + `evidence_refs` + `verification_status`
三件；无证据只能是 `suspected`，不得记 `verified`；
**不得因为仓库名相同、依赖同名包或作者相同，就认定存在经验证的组织/供应链/安全影响关系**；
跨仓库影响推断不属 Storage（需 Research、Security、EC 参与）；
不得引入图数据库。

### 关于 U06-C25 的归属（重要）
Security 批次把 `U06-C25`（三态产物契约）判给 Storage。本批最初复核后认为其语义层应由 EC 承接，
但依据本节第 11 条「**不得擅自更改已提交 canonical 的归属**」，本批**保留原判**、
不改其 owner，把分歧登记为 F1-C 待裁决项（X-6）。这是刻意的保守选择——归属调整应集中裁决，
不应在后续批次里逐个就地覆盖。

---

## 8. 根目录隔离与路径安全（P-1..P-4）

| 层 | 约束 |
|---|---|
| P-1 | 根路径必须由显式配置或参数确定，禁止隐式假设当前工作目录 |
| P-2 | 每个 `repository_id` 一个独立命名空间；路径由 identity 派生而非用户输入的 owner/name（后者可变、可重复） |
| P-3 | 任何由外部数据派生的路径，拼接前必须规范化并做根目录包含校验；**符号链接必须解析后校验真实路径** |
| P-4 | 外部源码快照只读存放，与可写产物物理分处；**自动扫描结果永不写回被分析仓库** |

**三条硬规则（c33/c34 机检）：**
1. 第三方仓库内容一律作数据处理，不因出现在配置或清单里而获得写权限。
2. 不可信内容不得通过任何方式访问本地私有文件或环境变量。
3. **知识资产根目录不得位于被分析仓库内部**——这是对上游「一仓库一 corpus 住在仓库内」的明确拒绝。

---

## 9. 安全、权限与发布（执行边界）

继承 Security 已批准的独立权限原则，Storage 的职责是**执行并持久化**，不定义权限语义：

- 保密分类 ≠ 发布授权；脱敏通过 ≠ 发布授权；人工批准不可由 AI 自动生成（语义归 Security 的 SL-CAP-0053）。
- **权限拒绝不能被吞掉并变成空查询结果**（c29 机检）。
- 不在日志、索引或错误产物中暴露凭据。
- 不可变历史保存也必须遵守必要的访问控制——「不可变」不等于「人人可读」。
- 对敏感原始材料的持久化必须有明确边界。

逻辑安全要求与 F2 实现机制分离：本轮不接入真实认证系统、不执行迁移。

---

## 10. 跨模块边界裁决（M-A … M-H）

| 编号 | 事项 | 裁决 |
|---|---|---|
| M-A | `SL-CAP-0009` Canonical Knowledge Registry 是否应迁移权威 owner 至 Storage | **不迁移**。0009 是实体消解的**语义权威清单**（名字/别名/类型/路径/来源），owner 保持 Facts；Storage 只持久化其产物。若 F1-C 认为应迁移，需给出理由与影响面 |
| M-B | Lifecycle 的 Subject 身份与 Storage 主键契约 | 语义定义归 Lifecycle 的 SL-CAP-0040，主键分配与不复用保证归本条的 SL-CAP-0063 |
| M-C | EC 的不可变 Evidence 与 Storage 实际写入边界 | EC 定义证据的对象与字段语义（SL-CAP-0020），Storage 定义其物理只追加写入（SL-CAP-0062 的 A 层） |
| M-D | Renderer 生成产物与 Storage 派生索引边界 | C 层索引归 Storage 构建（可从权威重建）；D 层展示产物归 Renderer 生成，Storage 不产 D 层 |
| M-E | Security 敏感数据标签与 Storage 访问控制执行点 | 分级语义归 Security（SL-CAP-0053），执行点归本条的访问控制面；**拒绝不得伪装空结果** |
| M-F | 多 Agent 并发与 DSH Adapter 运行时调度边界 | 调度（谁在何时跑）归 DSH Adapter；写入一致性（CAS/冲突返回）归本条的 SL-CAP-0064 |
| M-G | Lifecycle 版本失效逻辑与 Storage 当前版本指针 | 失效判定归 Lifecycle（SL-CAP-0042），指针推进机制归本条（SL-CAP-0062 B 层 + SL-CAP-0064 W-4） |
| M-H | 派生索引重建的触发权归属 | 重建**能否**归 Storage（技术契约）；**何时**触发归 Lifecycle 与 Storage 的联合契约，不得由 Renderer 单方触发 |

**所有需要调整归属的项目进入 F1-C，不擅自更改。**

---

## 11. F1-C 待裁决项（X-1 … X-7）

| 编号 | 事项 | 建议 owner | 涉及 ID |
|---|---|---|---|
| X-1 | `SL-CAP-0009` 权威 owner 是否迁至 Storage | 保持 Facts（建议） | SL-CAP-0009, SL-CAP-0063 |
| X-2 | 跨仓库 Subject 的主键表示 | Lifecycle + Storage 联合 | SL-CAP-0040, SL-CAP-0063 |
| X-3 | `U06-C25` 三态产物契约 owner 存疑（Security 判 Storage，本批复核倾向 EC 语义层） | 待裁（保留原判 Storage） | 原始身份 U06-C25 |
| X-4 | B 层当前视图与 A 层历史冲突时的用户可见判定 | Renderer + Lifecycle | SL-CAP-0062, SL-CAP-0041 |
| X-5 | 跨文件原子性的实现路径（提交日志 vs 单文件事务库） | F2 | SL-CAP-0064 |
| X-6 | 是否最终需要向量或图检索 | F2（本批明确不预设） | SL-CAP-0065 |
| X-7 | 知识根目录默认位置与分支/commit 是否共用命名空间 | F2 | SL-CAP-0067 |

---

## 12. 零来源能力与 REJECT 处理

### 零来源：SL-CAP-0063（身份层级与版本标识）
**内部需求依据**：四层模型（SL-CAP-0062）落地必须有主键契约。六源中没有任何一处
给出「逻辑身份 / 内容哈希 / 业务版本」三者分离的存储层定义——上游索引表只有四列且
`summary` 被要求不含结论，既无内容哈希也无版本链。
本条与 SL-CAP-0040 的关系是「语义定义 vs 存储分配」，并把 F0 勘误 E-01 从取数三字段扩展到全部身份标识。
**不伪造第三方来源。**

### REJECT 处理：`U04-C25` 与 `U05-C26`
两者均被原始审计判 REJECT（「一个仓库一个 corpus，住在仓库内」的部署模型）。
本批**保留其 REJECT verdict 并登记在 SL-CAP-0067 的 refs 中作为反面约束**——
它们确实被用来约束设计（硬规则三「知识资产根目录不得位于被分析仓库内部」），
不是可有可无的闲置条目。这是本批唯一包含 REJECT verdict 的地方，理由如实写明。

---

## 13. 本轮修掉的问题

### 一处归属争议的处理（按第 11 节保守处理）
本批曾把 `U06-C25` 从 Storage 改判为 EC 并写入草稿。这**违反「不得擅自更改已提交 canonical 的归属」**，
且会让 Security 验证器 c50 的历史断言误红。已做两件事：
1. 从 `DEFERRED_TO_OTHER_MODULE` 撤出 C25，恢复原判 owner=Storage（c53 专检这条）。
2. Security 验证器 c50 收窄作用域：只校验 Security 自己声明的那几条「要么在分流表且去向正确、
   要么已被承接」；对仍待裁决的条目不作硬断言。

**教训记在这里**：归属调整应集中到 F1-C，不应在后续批次里就地覆盖前一模块的裁决。

### 构建缓存残留
第一次构建已把 C25 写入草稿，撤出 def 后重新构建时它仍作为既有分流失效残留。
处理方式：从 `/tmp/pre-storage.json` 恢复构建前快照再重建，彻底消除该记录。
**这说明「def 改了就重跑」不够——被撤出的条目需要从草稿基线重来。**

### Security 验证器作用域
c50 原判据要求五条分流全部仍在路由表。本批 Storage 承接 `U06-C19` 后它移入 mapped，
属晋升的正常结果。已改为如上所述的三分支判据。

---

## 14. 验收

```
python3 tools/fusion/f1b_build_storage.py      → RESULT: OK      exit 0
python3 tools/fusion/f1b_verify.py              → 12/12 PASS      exit 0
python3 tools/fusion/f1b_verify_collector.py    → 30/30 PASS      exit 0
python3 tools/fusion/f1b_verify_ec.py           → 50/50 PASS      exit 0
python3 tools/fusion/f1b_verify_product.py      → 43/43 PASS      exit 0
python3 tools/fusion/f1b_verify_research.py     → 46/46 PASS      exit 0
python3 tools/fusion/f1b_verify_lifecycle.py    → 48/48 PASS      exit 0
python3 tools/fusion/f1b_verify_security.py     → 53/53 PASS      exit 0
python3 tools/fusion/f1b_verify_renderer.py     → 48/48 PASS      exit 0
python3 tools/fusion/f1b_verify_storage.py      → 54/54 PASS      exit 0
```

幂等性：重跑后六个核心字段逐字节一致，分流零重复、无幽灵晋升、无 ID 漂移。

**重要边界**：以上全部是 F1 设计与产物验证。**真实数据库的事务语义、并发吞吐、
崩溃恢复的实际行为均未测试**——本轮不安装依赖、不建库、不实现引擎。

---

## 15. 下一批

F1-B 剩余最后一模块：DSH Adapter。新 ID 从 `SL-CAP-0068` 起。

本批未启动 F2，未修改正式分析引擎，未处理 DSH Adapter。
