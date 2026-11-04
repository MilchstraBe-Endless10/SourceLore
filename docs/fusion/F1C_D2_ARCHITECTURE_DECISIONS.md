# F1-C-D2 · 八项跨模块架构冲突裁决

产物：`tools/fusion/f1c_d2_decisions.py`（裁决数据）、`tools/fusion/f1c_d2_build.py`（生成器）、
`tools/fusion/f1c_d2_verify.py`（22 条验收）、`F1C_D2_CONFLICT_RESOLUTIONS.json`、`F1C_D2_F2_GATES.json`

---

## 0. 一个必须先说清的前提

**这八条编号散落在三份文档里，且同名不同义。**

| 编号 | 真实出处 | 内容 |
|---|---|---|
| X-2 / X-4 / X-5 / X-6 / X-7 | `F1B_STORAGE_DECISIONS.md §11` | Storage 的 F1-C 待裁项 |
| K-7 | `F1B_RENDERER_DECISIONS.md §10` | 人工叙事文档能否被自动更新 |
| Y-4 / Y-6 | `F1B_DSH_ADAPTER_DECISIONS.md §10` | 检查点物理存放 / BotHarness 证据缺口 |

**陷阱：`F1B_LIFECYCLE_DECISIONS.md §9` 里也有 X-1…X-6，但所指完全不同**
（例如 Lifecycle 的 X-4 是「Storage 对不可变历史与当前视图的写入责任」，Storage 的 X-4 是
「B 层与 A 层冲突的用户可见判定」）。`F1C_D_HANDOFF_INVENTORY` 里的 X-* 取自 **Storage 表**，
本批据此裁决，不混用 Lifecycle 的同名项。

---

## 1. 结果分布

| status | 数量 | 含义 |
|---|---|---|
| `DESIGN_RESOLVED` | **6** | 架构责任与契约已裁定，可实施 |
| `IMPLEMENTATION_DEPENDENCY` | **1**（X-5） | 架构已定，实现与实测必须在 F2 |
| `BLOCKED_BY_MISSING_EVIDENCE` | **1**（Y-6） | 证据不足以判断，非设计缺口 |

**没有一条被标为「已实现」。** 门禁共 30 条（F1 阶段 22 条、F2 阶段 8 条），Y-6 另有 6 个探测任务。

---

## 2. X-2 跨仓库 Subject 身份 → 分层身份

**裁定 C：三层身份分离。**

| 标识 | 性质 | 谁定义 |
|---|---|---|
| `repository_id` | **仓库**身份锚点（改名不改号） | Facts 取数 / Storage 落地 |
| `subject_id` | **逻辑知识主体**身份，永不复用 | **Lifecycle**（SL-CAP-0040）分配语义 |
| `repo_binding` | Subject 与 repository 的**关联记录**，可多对多 | **Storage**（SL-CAP-0063）持久化 |
| `workspace_id` | 运行期作用域（一次会话/一次批量） | **不参与知识身份** |
| `commit_sha` | 内容快照标识 | 版本维度，**不入身份** |
| `subject_version` | 业务版本（SL-CAP-0063 第三种身份） | 版本维度，不参与跨仓库判定 |

**硬结论：`repository_id` 不是所有 Subject 的主键。** 一个 repository 可承载多个 Subject；
一个 Subject 也可关联多个 repository。

逐项裁定：

- **仓库重命名** → `repository_id` 不变即同一 Subject，旧名记 `name_history`。
- **Fork** → 有自己的 `repository_id`，属**独立 Subject**，用 `forked_from` 关联，**不得合并**。
- **跨仓库同名实体** → **不得自动合并**。先比仓库关系，再比 `subject_key` 规范化后的 `claim_scope` 重叠；
  两者都不足以定案时保留两个独立 Subject 并登记 `possible_duplicate` 待人工确认。
- **仓库关系谁存** → Storage。
- **语义身份谁定义** → Lifecycle。
- **多仓库研究如何关联** → **Research 只能产出关联候选**，不得绕过 EC 直接认定。

---

## 3. X-4 当前视图 vs 不可变历史 → 两层并存 + 显式降级

**裁定 C：B 是指针，A 是权威；B 失效时显式标注并保留最后有效视图。**

六条逐条：

1. **B 指针指向不存在的 A 对象** → 判 `dangling_pointer`，**不静默重建**：
   保留 `last_known_good`，视图打 `pointer_invalid` 标记。**禁止伪装成空结果或「无知识」。**
2. **当前视图与历史结论不一致** → 用户**两者都看到**：当前结论 + 历史结论 + 各自 `source_snapshot`，
   标注 `supersedes` 链。**不得把不同版本的结论视为互相证伪**——版本差异不是 claim 冲突。
3. **是否保留最后有效视图** → 是。`last_known_good` 必须持久化，失败时降级并标 `degraded`。
4. **新验证结论如何形成历史修订** → 只能**追加**新 A 层记录 + 推进 B 指针（CAS）。
   **不存在「修改历史」这个动作。**
5. **写入权限** → A 层只有 Storage 追加接口；B 层只有 Storage 指针推进（受 CAS 保护）。
   **Renderer 对两层都无写权限。**
6. **谁向用户显示冲突与版本限制** → Renderer，但它**只呈现不作裁定**。

四条硬规则全部写入：不得用 B 覆盖 A、不得把版本差异当证伪、不得把读取失败伪装成无知识、Renderer 无裁决权。

**四种「冲突」的归属必须分开**（与 F1-C-C2 的 U05-C21 同一思路）：
物理一致性 → Storage；知识有效性 → Lifecycle（0041/0042）；Claim 真伪 → EC（0028）；呈现 → Renderer。

---

## 4. X-5 / X-6 / X-7 实现选型

### X-5 跨文件原子性 → `IMPLEMENTATION_DEPENDENCY`

| 项 | 裁定 |
|---|---|
| **A. F1 必须确定的行为契约** | SL-CAP-0064 五步写入契约（W-1 临时区 / W-2 校验 / W-3 记 expected_version / W-4 CAS 才推指针 / W-5 崩溃后保持上一份已提交状态） |
| **B. F2 可自由选** | 单文件事务库 / 文件系统+提交日志 / 混合，任一均可 |
| **C. 最低验收标准** | 崩溃注入（kill 进程 / 磁盘满）+ 并发 CAS 压测必须真跑 |
| **D. 必须真实实验才能确认** | 崩溃恢复原子性、并发 CAS 正确性、临时区清理可靠性——**三项都不能靠读代码断言** |
| **E. 禁止上线条件** | 任一崩溃注入用例出现半写入权威资产，或并发写出现静默覆盖 |

**「设计上要求支持事务」≠「已经验证事务正确」。** 本条明确标为第二类，不是已实现。

### X-6 向量/图检索 → `DESIGN_RESOLVED`（结论是不引入）

F1 只用文本 + 结构化检索（SL-CAP-0065 硬规则四已有「不得在没有必要时引入向量/图数据库」）。
F1 契约：Q-1 按身份定位 / Q-2 按属性过滤 / Q-3 双通道，**必须能在纯文本+结构化下实现**。
F2 引入的必要性判据：结构化过滤无法表达 **且** 实测证明文本检索召回不可接受。

### X-7 根目录与命名空间 → `DESIGN_RESOLVED`（默认位置留给 F2）

- 根目录**显式声明**（SL-CAP-0067 P-1），禁止隐式用 CWD。
- 按 `repository_id` 划命名空间（P-2），不用 owner/name。
- **commit / branch 不与 repository 共层**：commit 是版本维度（A 层记录内 `source_snapshot` 字段，
  不另开目录层）；**branch 是取数指针，不是身份，不得进入路径**。
- 默认物理位置 → F2 决定。

---

## 5. K-7 人工叙事文档 → 默认禁止，放开需七项前置

**F1 定为：默认一律不允许自动修改人工维护的正文。** 人工文档属 A 层（不可变历史 / 人工权威）。
允许的是产出一个**独立的新文件**，由人决定如何并入。

**未来若需局部插入，七项必须全部满足：**

1. 明确的用户授权（**每次操作级**，不是一次性全局开关）
2. 被允许修改的范围（哪一段、哪个标记区间，显式声明）
3. 生成内容的身份与来源（哪条 claim、哪个 run，可追溯）
4. 修改前的版本校验（CAS：生成后文档被改动过即不得插入）
5. 冲突检测（目标区间已被他人修改 → 拒绝并报冲突）
6. 人工审查与回退（可一键回退到插入前版本）
7. 不改变不可变历史

**硬规则：不得因为文档内存在 Markdown 标记，就默认 Agent 有权自动写入。**
标记只说明「这里可定位」，**不构成写入授权**。

本轮**未实际修改任何人工文档**。

---

## 6. Y-4 检查点物理存放 → 三个对象分开

| 对象 | 性质 | 归属 |
|---|---|---|
| SourceLore 知识资产 | 权威知识（A/B/C/D 四层） | Storage |
| Agent 任务执行检查点 | **执行状态，不是知识** | 语义 DSH-Adapter（0071）/ 物理 Storage（**独立分区**） |
| 模型上下文 / 热记忆 | **辅助定位手段** | 任何时候都不是唯一权威来源 |

逐条：

- **谁定义 checkpoint 内容** → DSH-Adapter（0071 的十个逻辑字段）
- **谁保存** → Storage（走 0064 五步契约）
- **谁判断可恢复** → DSH-Adapter（状态自洽 + I-1 不重复提交）
- **如何关联 run_id/task_id/subject_id** → 三者并列存储；**`subject_id` 是知识侧外键，不是执行身份**；
  checkpoint **不得因 subject_id 进入知识命名空间**
- **并发恢复防重复提交** → CAS：带 `expected checkpoint_version`，不一致即拒绝
- **检查点损坏** → 判 `checkpoint_corrupt`，**转不可自动恢复**，交人工；**不得凭热记忆推断状态续跑**
- **能否靠热记忆恢复唯一权威状态** → **不可以**

**硬规则：「任务能否恢复」与「知识是否仍然有效」是两件事。**
checkpoint 恢复成功不代表任何 claim 仍有效（后者归 SL-CAP-0042 哈希失效）。

---

## 7. Y-6 BotHarness 能力缺口 → `BLOCKED_BY_MISSING_EVIDENCE`

本批**只读复核**，未安装插件、未改全局配置、未创建正式 Skill。

| 接口 | 问题 | 证据等级 | 依据 |
|---|---|---|---|
| H-A | Skill 入口与加载方式 | **VERIFIED** | `<root>/<name>/SKILL.md` + YAML frontmatter；本机 `~/.agents/skills/` 有 diagnose-crash、omarchy 两个实例 |
| H-B | BotHarness 侧如何发现 Skill | **PARTIALLY_VERIFIED** | DSH 侧由目录扫描+description 触发（本会话 skill 清单即证据）；**BotHarness 侧未实测** |
| H-C | Harness 如何调用 Skill 内脚本 | **PARTIALLY_VERIFIED** | `skills/sourcelore/scripts/` 目录存在但**空**；调用通道未实测 |
| H-D | 平台级持久化状态接口 | **UNVERIFIED** | 未发现平台级跨会话状态存储；**本机无 BotHarness 专用目录** |
| H-E | Skill 内的人类审批传递 | **UNVERIFIED** | DSH 侧 approval policy 存在；Skill 内部传递未实测 |
| H-F | 上下文不足/模型切换后恢复 | **UNVERIFIED** | 未见平台级恢复能力 |
| H-G | 执行结果回传 | **VERIFIED（语义层）** | Skill 以 Markdown 回传、Agent 读文本；结构化通道未实测 |
| H-H | 失败/超时/取消的可观测状态 | **UNVERIFIED** | 未实测 Skill 级失败状态暴露 |

**核心事实：`skills/sourcelore/` 下 `find -type f` 返回 0 个文件**（只有空的 references/ 与 scripts/）。
**BotHarness 能否实际加载与调用 SourceLore Skill —— 未经实测，标记 UNVERIFIED。**

**设计方向：SourceLore 自行管理检查点，不假定平台提供原生恢复接口。**
平台若提供则优先用，未提供则完全靠自有 checkpoint。

**阻塞范围**：阻塞的是「能否依赖平台原生能力」这个判断，**不是架构设计本身**。
架构已定（逐项标级 + 可自建兜底）；不确定的是五项真实能力，需 F2 六个探测任务。
**探测失败 → 走全自建路径，不得停工。**

---

## 8. 两项反向处置复核

### `U06::C13`：上游 ADAPT → SourceLore **REJECT**

- **上游主张**：Semgrep 三层规则集 + 本地缓存优先 + 废弃包移除（工具化的包安全扫描方法论）
- **拒绝部分**：整体方法论的可迁移性——三层规则集绑死 Semgrep 及其规则语言；缓存与废弃包移除是其工具链实现细节
- **保留部分**：**无**。终态为 `ADOPTED_AS_COUNTEREXAMPLE`，只作 SL-CAP-0018 的反面约束
- **理由**：上游 ADAPT 的前提是「同一团队继续用 Semgrep」；SourceLore 的目标是**工具无关的安全契约**。映射进去会让契约反向依赖具体工具，违背 0057/0069 的「不锁定实现」
- **许可**：**UPSTREAM-06 无明确复制许可（`copy_permitted=false`，`spdx=null`）。本条零复制**——未复制规则集、提示词、代码或模板

### `U02::C17`：上游 REJECT → SourceLore **REIMPLEMENT**

- **上游主张**：Mermaid 图表硬要求——必须包含 Mermaid 图，按固定节点结构填写
- **拒绝部分**：**「硬要求」本身**——强制出图、固定节点结构、与实际架构无关也照画
- **保留部分**：**图表作为可选手段**（SL-CAP-0057 三条硬规则）+ Mermaid 作为**可选格式之一**（不锁定）
- **理由**：上游拒绝整个图表机制；SourceLore 认为有可选价值，只去掉「强制」与「编造」两个成分。REIMPLEMENT = 保留意图、重写机制
- **许可**：MIT / `copy_permitted=true` / `attribution_required=true`。只借抽象意图，**未复制其 Mermaid 模板或节点结构定义**

---

## 9. 反例统计口径澄清

**先前的说法「21 项反例绑定」是口径错误。**

| 项 | 实测 |
|---|---|
| `ADOPTED_AS_COUNTEREXAMPLE` 唯一身份 | **17** |
| 实际 identity → canonical 的 `verdict=REJECT` 关联边 | **17**（一对一） |
| `REJECTED_WITH_REASON` 未绑定任何 canonical | **4** |
| counterexample **角色**身份合计 | 21 |

**「反例绑定」指有实际关联边。** 那 4 项 REJECTED_WITH_REASON 的 `role` 字段虽标
`counterexample`（表示其机制可作反面参照），但**没有边就没有绑定**。

正确表述：**17 项反例绑定（17 边）+ 4 项无绑定的拒绝身份 = 21 项 counterexample 角色。**

---

## 10. 本批做了什么、没做什么

**做了：**
- 八项冲突逐项裁决，每项有唯一 owner 或明确阻塞范围
- 30 条门禁（F1 22 / F2 8）+ 6 个 Y-6 探测任务
- 两项反向处置的理由与许可边界补齐
- 反例统计口径澄清

**没做（不越界）：**
- **0 条 canonical amendment**——canonical 字段一个没改
- **未创建任何正式 Skill**（`skills/sourcelore/` 保持 0 文件）
- **未实际修改人工文档**
- **未生成 `CAPABILITY_CROSSWALK.json`**
- 未进入 F1-C-D3 / F1-D / F2

**为什么 0 条 amendment：** 八项都是**约束已有模块之间的接口**，按第 11 节要求
「优先建立独立的架构决策记录，不反复改写已有 75 条 canonical」。四层模型、可变/不可变分离、
哈希失效、裁决状态机、CAS 写入、命名空间隔离——这些机制本来就都在，缺的只是跨层契约的显式表述。

---

## 11. 下一步：F1-C-D3

1. **21 项反例角色（17 边 + 4 无绑定）的许可证逐项总审**——本批只核了 2 项反向个案的边界
2. **7 条零来源 canonical 的质量审查**（0013/0019/0045/0047/0061/0063/0073）
3. **UPSTREAM-06 相关全部条目的零复制复核**（本批只验了 C13 一处）
4. 交叉表冻结前的最后一致性检查（冻结本身留 F1-D）
