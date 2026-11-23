# SourceLore 设计思路

> 本文回答「为什么设计成现在这样」，不重复 [系统架构](ARCHITECTURE.md) 里的「是什么 / 怎么连」。架构描述结构，本文描述取舍。
>
> **取证纪律**：每条理由都指向一条真实决策记录、源码事实或实测结果——`progress/DECISIONS.md`（D-001..D-007）、`docs/fusion/BASELINE.md`（F0 勘误）、`docs/implementation/F2_P0_ADAPTER_DECISIONS.md`（AD-1..AD-6）、`docs/implementation/F2_P1B_STORAGE_ARCHITECTURE.md`、`docs/implementation/F2_P1C_COLLECTOR_ARCHITECTURE.md`、`docs/implementation/F2_P2A_FACTS_ARCHITECTURE.md`、`docs/implementation/F2_P2B_EC_ARCHITECTURE.md`，以及 `src/trust/policy.py`、`src/collector/`、`src/runtime/`。凡只能观察到「现在怎么实现」而无当时决策动机的，一律标为**当前实现的技术理由**，不虚构开发者当时的思考。可提 ADR 时引用的是上述真实决策条目，不编造编号。

---

## 6.1 为什么以固定 Commit 为知识基础

**问题**：GitHub 分支是可变的。今天读到的 README 和下周读到的可能不是同一份内容；若知识库只记「仓库 main 分支」，则同一条结论无法回查到具体版本，也无法被别人复现。

**决策依据**：
- `progress/DECISIONS.md` D-006：事实采集一律由确定性脚本完成并落 JSON，模型只读结构化结果，避免「凭空写出」未经验证的事实。固定 Commit 是这条纪律在版本维度的落点。
- `docs/fusion/BASELINE.md` §3：六源核验全部固定在具体 Commit 上，并以真实根 tree 逐条比对内容哈希，证明「字段语义错误不是数据污染」的前提就是版本被钉死。

**为什么**：
1. **消除版本漂移**。固定 Commit 让「这条结论针对哪一份文件树」成为可回答的问题；可变 ref 会把结论与时间隐式绑定，无法验证。
2. **可重复性**。给定同一 Commit，采集、抽取、裁决、派生每一步都应得到同样的结果；这是「可回查」的技术前提。
3. **证据定位**。事实携带 `commit_sha` 与路径，读者能跳回远端具体版本核对，而不是只看到一句「在某仓库里」。

**不做的事**：不把可变分支当作知识身份。`src/skill_interface/SKILL.md`「离线优先与缓存」明确：无 `--commit` 时返回 `branch_current_unknown: true`，本地快照只能证明「过去观测过的版本」，不能证明分支当前仍指向它。

---

## 6.2 为什么 `commit_sha` / `root_tree_sha` / `tree_query_ref` 必须分离

**问题**：直觉上「树的 SHA」和「提交的 SHA」似乎可以互用。实测证明不能。

**决策依据（真实实测）**：
- `docs/fusion/BASELINE.md` F0-D01（high）：UPSTREAM-03/04/05/06 四源的 `tree.json.sha` 都等于自己的 commit SHA，且都不等于真实根 tree SHA——这是同一抓取方式的系统性结果。
- `docs/implementation/F2_P1C_TREE_ECHO_EXPERIMENT.json`：用 `commit_sha=7fd1a60b…` 请求 Trees API，响应 `sha` 仍为 `7fd1a60b…`；用 `root_tree_sha=b4eecafa…` 请求，响应 `sha` 才是 `b4eecafa…`。`echo_confirmed: true`。
- `docs/implementation/F2_P1C_COLLECTOR_ARCHITECTURE.md` §2：`root_tree_sha` 的唯一合法来源是 Commit 对象的 `commit.tree.sha`，绝不用 Trees API 响应的 `sha`。

**为什么**：GitHub Trees API 在 ref 是 commit-ish 时，响应里的 `sha` **回显请求标识**，而不是它展开的那棵树的 SHA。若下游把这个回显值当作树身份或快照指纹，会得到错误结论。分离三个字段后，每个值都有唯一来源、互不回填，错误无法悄悄传播。

**当前实现的技术理由**：`build_snapshot()` 要求三字段逐个显式传入、不做自动回填；夹具 `fake_gh.py` 刻意复现「回显请求 ref」行为，测试断言的正是这一点。这是实现层对 F0-D01 的防线，而非推测出来的偏好。

---

## 6.3 为什么 A 层不可变、且修复靠新增版本而非覆盖

**问题**：知识会被更正。若允许就地改写权威记录，历史结论消失，审计链条断裂，也无法回答「这个结论以前是什么」。

**决策依据**：
- `docs/implementation/F2_P1B_STORAGE_ARCHITECTURE.md` §3：A 层用数据库触发器强制不可变——`assets_no_update` / `assets_no_delete` 均 `RAISE(ABORT, 'A_LAYER_IMMUTABLE')`；测试真的执行 `UPDATE` / `DELETE`，都被挡住。
- `progress/DECISIONS.md` D-002：知识资产（`knowledge/`、`cache/`、`upstreams/` 等）与源码 Git 严格隔离，产物永远留本地、不随代码推送。

**为什么**：
1. **历史保留**。旧版本是审计证据，不能被新结论抹掉。
2. **修复靠新增版本 + 隔离视图 + 重新派生**，而不是覆盖权威资产：新答案写成一条新版本资产，由 B 层指针决定当前采用哪条，D 层文档重新派生。旧版本仍在 A 层可查。
3. **不靠自觉**。用触发器而非约定，意味着即使调用方写错代码也无法破坏历史。

**不做的事**：不声称 A 层可删除、可更新，也不让用户输入决定资产 ID——`asset_id` 内部生成（`SL-A-` + sha256 前 32 位，输入含 `repository_id`），避免跨仓库同名记录撞主键被静默合并（P1B 实测踩坑）。

---

## 6.4 为什么当前指针与历史资产分离

**问题**：A 层保留了所有版本，但「今天哪条有效」必须有一个单一权威答案；否则历史失效的 Verification 会被混进当前结论。

**决策依据**：
- `docs/implementation/F2_P1B_STORAGE_ARCHITECTURE.md` §4：B 层 `current_view(repository_id, logical_identity)` 用比较交换（CAS）指向当前资产版本，`pointer_version` 不匹配即 `CONFLICT`；`ok` / `dangling_pointer` / 无记录三态区分，dangling 绝不报成 `NOT_FOUND`。
- `src/trust/policy.py`：`current_asset_ids()` 是「当前有效资产」的唯一来源；`resolve_verification_for_claim()` 只取当前视图中的 Verification，历史裁决走独立的 `list_historical_verifications()` 通道。

**为什么**：历史资产服务于审计与回溯，当前指针服务于结论。两者分离后：
- 一条 Claim 的历史 Verification 即使被新证据推翻，也不会「僵尸复活」混入当前查询；
- 指针可被 CAS 保护，并发写入不会互相覆盖；
- 「记录坏了」（dangling pointer）与「知识不存在」（NOT_FOUND）语义不再混淆，前者带 `last_known_good` 供诊断。

**当前实现的技术理由**：`evidence_admission()` 对非当前裁决返回 `admitted=False / insufficient_evidence`，这是「历史不直接进当前结论」在证据准入层的二次落实。

---

## 6.5 为什么 Fact 与 Claim 分离、Verification 三态且引用可定位≠结论正确

**问题**：源码里「观察到的事实」与「据此提出的知识命题」不是一回事。把两者混存，会让「有一条 Fact」被误读为「命题已验证」。

**决策依据**：
- `docs/implementation/F2_P2A_FACTS_ARCHITECTURE.md`：Fact 只做可机械复算的观察（如 `file_path_observation`），只从已提交的 `repository_snapshot` 读取，抽取器源码无网络 import、无 SQL。
- `docs/implementation/F2_P2B_EC_ARCHITECTURE.md` §1–2：`claim_id` 由仓库 + 固定 Commit + 命题类型 + 规范化参数 + Schema 版本决定，不随证据变；`verification_id` 随证据变。`verification_status` 为 `supported / refuted / insufficient_evidence` 三态；`review_status` 的 `approved` 只能由人产生（`Claim.__post_init__` 拦截 AI 自批）。
- `src/trust/policy.py` `evidence_admission()` 与 `src/skill_interface/SKILL.md`：证据完整性 `FULLY_LOCATABLE / PARTIALLY_LOCATABLE / UNRESOLVED_NO_INTEGRITY`。

**为什么**：
1. **观察与命题分层**使证据可独立复算，命题可被独立裁决。
2. **三态**避免二值强制：证据不足时不猜「是」也不猜「否」，落到 `insufficient_evidence`。
3. **引用可定位不等于结论正确**。全部引用可定位（`FULLY_LOCATABLE`）只说明证据链完整可查，仍保留原始 `status`；部分/不可解析引用会把裁决**降级**为 `insufficient_evidence`，而不是让它变成 `refuted`。完整性衡量的是「引用可回查性」，不是「命题真假」。
4. **五种状态正交**：`claim_type`、`verification_status`、`review_status`、`knowledge_freshness`、`execution_status` 各自独立——任务执行状态属于运行时，不进知识裁决。

---

## 6.6 为什么不把缺失证据判为不存在

**问题**：「没找到」有两种含义：范围之外（未采集），或范围内确实不存在。把它们都写成「不存在」，会产生确定的错误结论。

**决策依据**：
- `README.md` / `src/skill_interface/SKILL.md`：`ROOT_ONLY` 表示只枚举了仓库根目录，绝不冒充 `COMPLETE`；缺失内容记为「未分析」，不是「不存在」。
- `src/trust/policy.py` `refutation_soundness()`：ABSENT 反证要求反证事实自带 `COMPLETE` 覆盖声明；未展开子树且非根级路径不可反证；`object_type=unknown / blob_sha=null / mode=""` 的「缺失观察」不构成确定 `refuted`。
- `docs/fusion/BASELINE.md` F0-D06：上游「无法建立完整链 → FALSE_POSITIVE（判否）」与 SourceLore「证据不足 → insufficient」冲突，F2 采用 `insufficient`，只保留「逐跳可定位」的可用部分。

**为什么**：反证需要比支持更强的覆盖前提。根级精确缺路径在 `ROOT_ONLY` 下仍可判定，但子目录路径不行——子树未展开时，缺路径可能只是没采集到。历史上确有误判：`progress/AUDIT-2026-11-11.md` 记录 preact 曾有 1 条 `refuted`，其 README 正文当时只有 227 B 空壳（未采集到正文），真实 README 为 14884 B；该类误读被降级为 `insufficient_evidence`。这是「缺失不等于不存在」的真实教训，不是假设。

---

## 6.7 为什么采用 Skill + CLI 形式，并区分复用与自建

**问题**：能力要以智能体可调用的形式交付，但平台并非什么都有。

**决策依据**：`docs/implementation/F2_P0_ADAPTER_DECISIONS.md` 的 AD-1..AD-6，全部基于 P1–P6 实测：

| 组件 | 复用 / 自建 | 理由 |
|---|---|---|
| Skill 发现与注册 | **复用**文件系统发现机制 | `~/.agents/skills/<name>/SKILL.md` 放入即被发现、移除即消失，可热重载；自建注册表更差（AD-1） |
| 入口结构 | **复用 + 遵守 SL-CAP-0068** | 薄入口 + 按需加载子文件（AD-1） |
| Checkpoint 存储与恢复协调 | **自建** | 平台无跨会话状态 API；1246 个 `sessions` 是会话回放日志，**会话回放提供上下文，不提供权威状态**（AD-2） |
| 授权令牌 | **自建** | Skill 内审批传递链路未验证；写操作须显式 `authorization_scope`，缺失/越界即 `DENIED`，不得降级为空结果（AD-3） |
| 结果五态 | **自建** | 平台无原生枚举：`SUCCESS / FAILED / TIMEOUT / CANCELLED / UNKNOWN`（AD-4） |
| 模型路由 | **复用单一适配接口** | `dsh headless` 因 `MISSING_CREDENTIAL` 失败，属环境阻塞非设计缺陷；不写死 provider（AD-5） |

**为什么**：总原则是「不把自建方案伪装成平台原生能力，也不因为平台缺某项能力就判定项目不可做」。五态中 `TIMEOUT` 不得推断为「未执行」，`UNKNOWN` 不得默认成 `SUCCESS` 或 `FAILED`；`src/runtime/execution_result.py` 进一步规定 `UNKNOWN` 是非终态，副作用可能已发生而回执缺失时只允许 `UNKNOWN`，不得擅自重做。

---

## 6.8 为什么知识文档与 `answer` 都不能由数据库记录直接替代

**问题**：数据库里的 Fact / Claim / Verification 记录是机器资产，但用户需要能直接阅读的项目知识；而「自然语言问答」若接 LLM，就会重新引入不可复算的推断。

**决策依据**：
- `src/views/repo_derive_runner.py`：把一次性脚本固化为 `sourcelore derive <rid>`，离线、不联网，产出 `project-overview.md`、`file-structure.md`、`module-dependencies.md`、`claim-network.md`、`evidence-index.md` 五篇 D 层文档。数据源全部是已登记权威资产（snapshot 的 tree_entries、claim_candidate、claim_verification 的 fact_ids、`query --type code` 结果）。
- `src/skill_interface/knowledge_answer.py`：铁律「不接 LLM：本模块只做确定性检索与组装」；只读、零网络、不写资产，内容优先，审计字段只在用户问「为什么可信」时给出。

**为什么**：记录级资产回答「某条命题的证据是什么」，文档级资产回答「这个项目是什么、怎么用、结构如何」——前者不能替代后者，因此必须有 `derive`。`answer` 若接 LLM 就违背了 D-006 的确定性纪律，所以它是意图到文档章节的确定性映射，没来源就说「未分析 / 证据不足」，不从文件名猜功能。

---

## 6.9 已知技术取舍

这些不是「还没做完」，而是明确选择站在哪一边，并把另一边的代价写清楚。

| 取舍 | 选择 | 代价 / 边界 |
|---|---|---|
| 离线缓存 vs 网络新鲜度 | 离线优先，`--commit` 命中完整快照即 0 请求复用 | 本地快照只能证明「过去观测过的版本」，不能证明分支当前仍指向它；无 `--commit` 时标 `branch_current_unknown`，要新版本用 `--refresh`（SKILL.md「离线优先与缓存」） |
| 原始内容持久化 vs 授权 | 字节落 `blobs/`，FETCH / PERSIST / DERIVE / PREVIEW / DISTRIBUTE 五维独立门禁 | `distribution_allowed=false` 恒定；预览允许不等于分发允许；分发门禁 B-1/B-2/B-3 仍开放（`content_acquisition_policy.py`、F2_P5E 报告） |
| 静态解析 vs 运行时分析 | Python `ast`、JS/TS `tree-sitter` 静态观察符号与导入 | 不执行仓库代码，不产出调用图、运行时行为、测试通过证据；解析器缺失报 `PARSER_UNAVAILABLE` 而非退回正则（README、SKILL.md） |
| 简单仓库 vs 大型仓库 | 分级预算、ROOT_ONLY 起步 | 大仓库子目录未系统采集，覆盖率有限；树 `truncated=true` 时退逐层遍历并标 `PARTIAL`（`tree_collector.py`） |
| 解析覆盖度 vs 采集成本 | 单 Blob 256 KiB、单批 2 MiB、候选路径 32、单文件 Facts 100；请求上限 8、保留 5 | 超限返回 `BLOB_TOO_LARGE` / `BATCH_BYTE_LIMIT` / `BATCH_PATH_LIMIT`；覆盖被预算约束，不假装完整（`content_budget.py`、`request_budget.py`） |
| 本地使用 vs 分发 | 仅供内部预览，知识库写在仓库外 | 数据库不进 Git 仓库（`paths.guard_inside_project_db`），本项目未选开源许可证（README / INSTALLATION） |

**为什么这样取舍**：每一对都对应一条硬约束——上下文窗口、GitHub 配额、许可与授权、不可执行第三方代码。取舍的结果是「明确标注边界」，而不是「声称完成」。

---

## 6.10 为什么流水线这样分段、恢复靠 `operation_id` 对账

**问题**：采集涉及网络、字节、解析、入库、裁决、派生多阶段；任一阶段中断后，既要能续跑，又不能重复写或误判结果。

**决策依据**：
- `src/skill_interface/cli.py`：`analyze --plan`（只读盘点，不联网、不写资产）、`--resume`（零网络恢复盘点，按 Storage 缺口续跑）、`--offline`（禁一切请求）、`--request-limit`（默认 8）、`--reserve-requests`（默认 5）。`--plan` / `--resume` 曾只是「声明式空参数」，D-60 把它们接到真实函数体。
- `src/runtime/asset_checkpoint_coordinator.py`：知识资产库与 checkpoint 库是独立物理文件、独立事务边界，**没有全局 ACID**；跨库 ATTACH 的 WAL 提交「看起来原子」不等于有保证，因此不用它。锚点是知识库 `operation_log` 里的 `operation_id`。
- 对账三态：`RECONCILED`（已提交、checkpoint 缺失→补 checkpoint，不重复写资产）、`RETRY_SAFE`（未提交且无确定外部副作用→可重试）、`NEEDS_HUMAN`（库损坏/矛盾→绝不自动重做）。判定只依据持久化记录，不看模型上下文。

**为什么**：分段使每一步可独立验证、独立预算；预算预检（先建请求 DAG → 盘点本地已有资产标 `LOCAL_REUSE` → 取权威响应头 → 三条件判定）使「无需联网」的运行不会被误判；`--plan` 只读使「先看缺口」成为零风险动作；`operation_id` 对账使两库不一致可收敛，而不必伪造全局事务。结果五态（6.7）与对账三态共同保证「超时不等于没执行、UNKNOWN 不等于成功」。

**不做的事**：不声称跨两库存在全局 ACID 事务；不声称 GitHub 请求 exactly-once（本地幂等只覆盖本地登记）。逐步细节、真实命令与状态码见 [处理流水线](PIPELINE.md)。
