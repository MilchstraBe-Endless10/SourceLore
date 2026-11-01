# UPSTREAM-04 检查点（2026-10-31 22:07 +08:00）

> 本文件是续跑用的过程产物，不是交付物。证据收集已完成，写作未开始。
> 压缩后从这里继续即可，不要重读上游。

## 一、恢复步骤

1. 读本文件
2. `cd "/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore"`
3. `git log --oneline -3`（应为 `46a63fa` 打头）
4. 直接开始写 `docs/upstream-audit-04-swe-research.md`，用下面第四节的分析
5. 不要重读 `upstreams/UPSTREAM-04-agent-skills/tree/` 下的文件——需要的原文已摘录在本文件

## 二、已完成事项

- Git 实测：HEAD `46a63fa534a88882e981596cbb7e160ffe93101c`，工作树干净，与上轮报告一致
- `gh auth status`：已认证 `MilchstraBe-Endless10`
- 上游版本已固定（见第三节）
- 目标 4 个 blob 全部逐行读完
- 根 `LICENSE`、`README.md` 读完
- 反向证据扫描完成（见第三节末）
- 快照 6 个 blob 的双哈希全部校验通过
- 已向用户发过一次进度报告

## 三、已固定的事实（可直接引用，不必复核）

### 仓库元数据

| 项 | 值 |
|---|---|
| 仓库 | `https://github.com/SNIKO/agent-skills` |
| Repository ID | `1240360167` |
| 默认分支 | `master`（`gh api` 实测，与用户预期一致） |
| 固定 Commit SHA | `a3e5e9da94434127cdd47a1a7e0658baafff7083` |
| Commit 时间 | 2026-08-23T12:59:00Z |
| Commit 标题 | `Refactor artifact review and brief template: clarify readiness criteria and enhance acceptance criteria guidance for improved decision-making` |
| Commit 作者 | Sergii Vashchyshchuk `<swashchyshchuk@gmail.com>` |
| `pushed_at` | 2026-08-23T12:59:10Z |
| `created_at` | 2026-05-16T03:42:58Z |
| `updated_at` | 2026-10-14T02:58:09Z |
| 可见性 / 体积 | `public` / 237 KB |
| `language` | `HTML` |
| `topics` | agents, anthropic, claudecode, codex, copilot-cli, openai, skills, spec-driven-development |
| 星标 / fork / issue | 2 / 0 / 0 |
| 归档 / fork | 未归档 / 非 fork |
| 检索时间 | 2026-10-31 22:05 +08:00 |

### 许可证

MIT。`LICENSE` 21 行 1077 B。版权行 `Copyright (c) 2026 Sergii Vashchyshchuk`（L3）。API `spdx_id = "MIT"`、`key = "mit"`、`url = https://api.github.com/licenses/mit` **与实测完全一致，无差异**。

义务：在所有副本或实质性部分中保留版权声明与许可声明（L12–L13）。署名材料：仓库 URL + Repository ID `1240360167` + Commit SHA + 版权行 `Copyright (c) 2026 Sergii Vashchyshchuk`。

### 快照完整性（6/6 全通过）

目录 `upstreams/UPSTREAM-04-agent-skills/`

| 文件 | 行 | 字节 | git blob SHA | sha256 |
|---|---|---|---|---|
| `LICENSE` | 21 | 1077 | `6113245db5ac723ae3400a6cc9663729b05424a6` | `28bb756c5869e0baa1379f7b28983c161218b9839dc16acd4674e98e5014ea75` |
| `README.md` | 217 | 12672 | `7b8383388e8bc1ab5d2c40875078b03d9dc39d0a` | `310f6ccdd18b163f35c9405b2a4e2194525b93cbae4b4503a9c967e0210ca7f3` |
| `skills/swe-research/SKILL.md` | 127 | 9240 | `13f10399a98ed4b9b1ebb6a66c0a1a20987f543e` | `aac582cd98615cf1b786b7c954b9351403d47bae39f47bc5b2c9bc1f9b050544` |
| `skills/swe-research/report.template.md` | 43 | 1604 | `f2780416248e96841bf28cd14edf30e7c580de8f` | `a40071882451aa8ea45c6fcfa882abfd8147afad15cd14186ad8dea4c3e8a64b` |
| `skills/swe-research/references/external-probe.md` | 35 | 1795 | `4038c1f5264c1fcaf4962b3df05894eac205c43c` | `31072a514e4880bc856ecf1b970b0e5d249ffd47f1b78400a86e1265649f35d0` |
| `skills/swe-research/references/repository-impact.md` | 32 | 1898 | `33f4ba20996ff7eedd7e6ef10ba5affe05770604` | `45525385badc694c1a7bf2e02a462bc3ea5875ecc084d1126350c1081c8ecd12` |

目标子树 `skills/swe-research/` 共 **4 个 blob、237 行、14537 字节**。其中 `SKILL.md` 127 行、`report.template.md` 43 行、`references/external-probe.md` 35 行、`references/repository-impact.md` 32 行。

### 反向证据（关键）

全仓 37 个 blob，`tree.json` 的 `truncated` 为 `false`：

- 脚本（`.sh/.py/.js/.mjs/.ts/.rb/.ps1`）：**0 个**
- 测试（`test/`、`tests/`、`spec/`、`_test.`、`.test.`）：**0 个**
- 依赖清单（`package.json`/`requirements*.txt`/`pyproject.toml`/`Cargo.toml`/`go.mod`/`Gemfile`/`setup.py`/`composer.json`）：**0 个**
- CI（`.github/`）：**0 个**
- 仓库规则（`AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md`/`.cursorrules`）：**0 个**
- 非 `.md` 文件仅 3 个：`LICENSE`、`docs/pipeline.excalidraw`、`skills/html-artifacts/html.template.html`

结论：**上游没有任何可运行物。`test_status` 必须为 `NOT_RUN`，理由不是「没找到」，是「枚举全部 37 个 blob 后确认不存在」。**

### 提交历史（成熟度证据）

- 全仓 29 次提交
- `skills/swe-research` subtree 历史上**只有 1 次提交**：`5b0681ea6` 2026-08-07 `Refactor SWE pipeline skills and documentation`
- 即：这个 Skill 写完后基本没再修订过，是「一次成型」的设计，未经实战打磨

## 四、A–G 七维度分析（已完成，直接用于写作）

### A. Reuse / Extend / Create

**上游做法**（`SKILL.md` L44–L49）：先读 `INDEX.md`，打开任何「subject plausibly covers the question」的报告，然后三选一：

- L45 **Reuse** — "an existing finding already answers it and is still valid. Return that answer and its report; do not re-investigate or create anything."
- L46 **Extend** — "the subject exists but this question is new, or the standing answer needs re-verification. Add a dated finding to that report."
- L47 **Create** — "no existing subject covers it. Start a new subject directory."
- L49 "Prefer extending. Two reports on the same subject is the failure mode that makes a corpus useless."

**判定：无真正可执行的判据。** 四个关键短语全是模型判断题——"plausibly covers"、"already answers it"、"is still valid"、"no existing subject covers it"。全文没有给出任何形式化的匹配条件（无词表、无相似度阈值、无字段比对规则）。唯一的硬规则是 L49 的偏好方向「prefer extending」，但连这个也只是取向而非算法。

**一个容易被忽略的设计选择**：L46 把「需要重验」（`the standing answer needs re-verification`）归进了 Extend，而不是单独一类。这等于说「过期不是独立状态，是追加一条新 finding 的触发」。这个选择省掉了一个状态，但也导致过期知识没有被显式标记（见 C）。

**SourceLore 可机器执行的规则**（我的提案）：

```
R-04-A1  查重键 = (repo_id, subject_key, claim_scope)，任一不等即可新建
R-04-A2  subject_key 由确定性规则生成：小写 + 非字母数字转 '-' + 截断 48 字符；与已有 subject 的别名表比对
R-04-A3  三态判定优先级固定为 Reuse > Extend > Create（对应上游 L49 的偏好，但改成硬顺序）
R-04-A4  Reuse 的必要条件（全部满足才可）：subject_key 命中 且 verified_commit == 当前 commit 且 无 open conflict
R-04-A5  verified_commit != 当前 commit 时强制进入 Extend-revalidate，不得 Reuse
R-04-A6  同一 (repo_id, subject_key) 下只允许一个 active report；新建即冲突，必须走 Extend
```

### B. 知识身份与去重

**上游做法**：

- L25 "One shared corpus per repository, organized by **subject**, not by question"
- L37 定义 subject 的性质："A subject is a thing you can keep learning about: `sec-edgar-api`, `tenant-resolution-middleware`, `legacy-dto-usage`, `postgres-jsonb-indexing`. It is not a single question."
- L27–L33 目录结构：`.swe/research/INDEX.md` + `<subject-slug>/report.md` + `<subject-slug>/artifacts/`
- 身份载体有两个：目录名（`subject-slug`）和 front matter 的 `subject` 字段（`report.template.md` L2 `subject: <Human-readable subject, e.g. SEC EDGAR companyfacts API>`）
- L65 分裂机制："Split a subject when it grows a coherent sub-subject worth finding on its own, and leave a link in both directions."
- L67 "Do not create a report per search query or minor subquestion."
- L62/L35 Superseded 关系（见 D）

**判定：subject 是「话题桶」不是「有身份的实体」。** 它没有独立于文件路径的 ID；仓库改名或迁移后没有任何锚定（因为设计前提是一个仓库一个 corpus，corpus 就住在仓库的 `.swe/research/` 里，仓库身份是隐含的、不需要显式记录）。`verified-against` 是自由文本（L5 模板原文："repo SHA, API/dependency version, environment, access date"），四个语义混在一个字符串里，无法结构化查询。

**SourceLore 所需的知识身份机制（我的提案）**：

七类 ID，各自解决一类消歧问题：

| ID | 形式 | 解决什么 | 稳定性来源 |
|---|---|---|---|
| `repo_id` | GitHub 数字 ID（如 `1240360167`） | 改名、迁移、URL 重复 | GitHub 分配后不变；fork 时**改变** |
| `repo_url_alias` | 原始 URL + 别名集合 | Fork、镜像、二次迁移 | 首次见到的 URL 入别名表，不互相覆盖 |
| `commit_sha` | 40 位完整 SHA | 分析依据的精确版本 | 内容寻址，天然不可变 |
| `subject_id` | `subj:<repo_id>:<subject_key>` | 研究主题 | 由 repo_id + 规范化主题名派生，可重算 |
| `claim_id` | `clm:<repo_id>:<commit_sha8>:<hash8>` | 一条可被推翻的断言 | 内容寻址；同一断言在不同 commit 下是不同 claim |
| `evidence_id` | `evd:<source_type>:<hash8>` | 一条原始证据 | 内容寻址，天然去重 |
| `snapshot_id` | `snap:<repo_id>:<commit_sha8>` | 一次分析快照 | 由 repo_id + commit 派生 |

关键判别规则：

- **仓库改名/迁移**：`repo_id` 不变 → 同一个知识库；URL 进别名表，不新建
- **Fork**：GitHub 的 fork 有**不同的** `repo_id` → 不同知识库。但 fork 与上游共享 commit SHA 历史，所以 `claim_id` 中必须含 `repo_id`，否则会把两个仓库的断言混为一谈
- **重复 URL**（http/https、带不带 `.git`、大小写）：先规范化再比对
- **同一主题不同问法**：`subject_key` 规范化后比对，但**命中不等于合并**——必须人工或模型确认，因为 `postgres-jsonb-indexing` 和 `postgres-indexing` 规范化后不同，语义上却可能重叠
- **多仓库涉及同一技术主题**：这是最危险的情况。`subject_id` 含 `repo_id`，所以天然分开；跨仓库的主题聚合必须走独立视图，绝不能合并 report

**明确禁止**：不得因为标题相似就自动合并两个 subject。上游 L49 说「两个报告是同一 subject 是失败模式」，但它没给出检测手段；SourceLore 必须给出，且检测失败时**倾向不合并**（漏合并可修，错合并会毁掉历史）。

### C. 知识新鲜度与失效检测

**上游做法**：

- `verified-against` 是唯一的新鲜度载体。L63 说它 "tells a reader whether the answer is stale"；`report.template.md` L5 原文：`verified-against: <repo SHA, API/dependency version, environment, access date>`
- L61 `Current understanding` "must always be true today"
- L90 `INDEX.md` 从 front matter 生成，"it cannot drift from the reports"
- L46 `Extend` 包含 "or the standing answer needs re-verification"

**判定：有新鲜度载体，零自动失效检测。** 没有任何东西在 commit 变化后标记报告过期；比对 `verified-against` 这个自由文本字符串与当前状态，完全靠人或模型自觉。`verified-against` 把「仓库版本」「API 版本」「依赖版本」「环境」「访问日期」五种不同生命周期的东西塞进一个字段——它们的失效条件各不相同，混在一起就无法分别判定。

**SourceLore 有效性机制（我的提案）**：

四类失效源，各有独立检测规则：

| 失效源 | 检测方式 | 触发后动作 |
|---|---|---|
| 仓库源码变化 | `verified_commit != current_commit` | 重算该 commit 下的文件哈希，与 `evidence.file_hashes` 比对；变的文件所支撑的 claim → `stale` |
| README / 文档变化 | 单独跟踪文档类文件哈希 | 文档类 claim → `stale` |
| 外部 API 变化 | 外部证据存 `retrieved_at` + 响应体哈希 | 超过 TTL 或哈希不符 → `stale` |
| 依赖版本变化 | 依赖清单文件哈希 | 依赖类 claim → `stale` |

**避免每次重查全仓**：claim 记录它依赖的 `evidence_refs`，每个 evidence 记录 `path + line_range + file_hash`。只有文件哈希变化的 evidence 才需要重验，只有引用该 evidence 的 claim 才需要重算。这是从「重查全仓」降到「重查增量文件」的关键。

**四类状态必须严格分离**（用户 §C 明确要求，上游完全没有做）：

| 状态 | 含义 | 判定者 | 后果 |
|---|---|---|---|
| `stale` | 知识曾有效，所依赖证据已变 | 确定性哈希比对 | 可用于历史研究，不得作为当前结论 |
| `insufficient` | 证据从来不足，未达结论门槛 | 置信度门槛 | 渲染为 Unknown，可随时补充 |
| `conflict` | 两条证据互相矛盾且都有效 | 证据比对 | 挂起该 claim，输出双方证据，等人工裁决 |
| `failed` | 本次分析任务执行失败（超时、限流、工具错） | 任务运行时 | **不产生 claim**，重试任务；绝不可与 stale 混淆 |

`failed` 与 `stale` 混淆是最危险的：任务失败不是「知识变旧了」，是「这次没取到」。若混为一谈，一次网络抖动就会把有效知识标记为过期。

### D. 研究历史与冲突处理

**上游做法**（这是全篇最漂亮的设计，核心是可变层与不可变层分离）：

- L61 "**`Current understanding` is rewritten in place.** It is the standing answer a reader gets if they read nothing else, and it must always be true today."
- L62 "**Findings are appended, never overwritten.** When new evidence contradicts an earlier finding, keep the old entry and mark it superseded with a link to the replacement. The history of what was believed and why is part of the evidence."
- `report.template.md` L20 注释："Appended, newest first. Never overwrite an entry: mark it superseded and link the replacement."
- L35 给出了 Superseded 的实际写法：`### YYYY-MM-DD — <Earlier question> · Superseded by [YYYY-MM-DD](#yyyy-mm-dd--question-investigated)`
- L37 "Kept for history. State briefly what changed and why the earlier conclusion no longer holds."
- L18–L33 finding 的四段结构：`**Answer:**` / `**Evidence:**` / `**Artifacts:**` / `**Limitations:**`，L26 明确 "Keep observed facts separable from interpretation."
- README L183 "Findings are evidence, not requirements or design: the owning brief or spec must incorporate a finding before downstream work treats it as authoritative. If a finding contradicts an artifact, return to the earliest affected artifact rather than working around it."
- README L185–L195 修订协议五步：停止受影响下游 → 找到最早的错误产物 → 更新它或做有界研究 → 复查下游 → 等人调用继续

**四个缺陷**：

1. **Superseded 是标题里的一段文字，不是结构化字段。** 无法机器查询「哪些 finding 被推翻过」「某条结论被替换了几次」。
2. **只有 superseded 一种关系。** 缺 `contradicted`（同时有效但互斥）、`partially-superseded`（部分被推翻）、`disputed`（有争议）。两个报告对同一事实判断不同时，`SKILL.md` 全篇未提如何处理。
3. **`Current understanding` 重写后旧版本永久丢失。** 这是最大的信息缺口：读者无法知道当前理解是怎么演进的，只能从 Findings 反推。上游说「Findings 的历史是证据的一部分」，但当前理解的演进史反而没了。
4. **没有规定谁有权标记 superseded、需要什么条件。** 模型可以单方面宣布旧结论作废。

**SourceLore 设计（我的提案）**：

- `Current understanding` 改成**版本化**：每次重写产生新版本，旧版本保留为 `understanding_v<n>`，带 `superseded_by` 指针。当前版 = 最大 n 且未标记 superseded 的那个
- Superseded 从标题文字升级为结构化字段：`{finding_id, status: active|superseded|contradicted|disputed, superseded_by: finding_id|null, reason, decided_at, decided_by}`
- 冲突不自动裁决：两条 `active` 且互斥的 finding 同时存在时，自动生成一条 `conflict` 类型的 claim，同时保留双方证据，等人工
- 原始证据**永不修改**：evidence 表只插入不更新。claim 可以变状态，但 evidence 不行

### E. 可复现实验与原始证据

**上游做法**：

- L53 "**Create reproducible artifacts.** When actual behaviour matters, write and run a minimal probe or experiment, save the script and relevant raw output, and record how it was executed."
- L71 "Scripts must be runnable and record their command, dependencies, inputs, and required environment variables."
- L72 "**Never store tokens, cookies, credentials, personal data, or sensitive headers.** Read secrets from the environment and redact captured output. These rules apply to every retained artifact, in every investigation mode." ← 全文最强的安全规则，且明确了「所有调查模式、所有留存产物」都适用
- L73 "Preserve raw responses when safe and reasonably sized. For large or sensitive output, save a minimal representative fixture and state exactly what was omitted."
- L74 命名规范：稳定、描述性（`probe-companyfacts.py`、`aapl-companyfacts.json`、`dto-field-references.md`）
- L75 "Link every retained artifact from `report.md` and explain what it proves."
- L76 "Do not retain generated noise, dependency directories, binaries, or output that does not support an answer."
- L37 "Omit `artifacts/` when repository paths and cited sources fully support the answer."
- `external-probe.md` L9 "Write a minimal reproducible probe under `artifacts/` **before** making the request." ← 先写脚本再发请求，保证可复现
- `external-probe.md` L10 "Use environment variables for credentials and configurable inputs. Never embed secrets."
- `external-probe.md` L11–L15 五样存档：响应体 / 相关响应头（分页、缓存、版本、限流、内容类型）/ 无凭据的请求元数据 / 命令+访问日期+运行时依赖版本+代表性输入
- `external-probe.md` L17 "Explain differences between documented and observed behaviour."
- `external-probe.md` L21 "A request to probe a public read-only endpoint authorizes that bounded request under the skill's autonomy policy." ← 显式授权规则
- `external-probe.md` L35 "The saved script must reproduce the observation"
- `repository-impact.md` L28 "do not preserve raw search dumps by default" ← 反向约束，防止证据膨胀

**判定：三分法清晰，但缺机械保障。**

三分法是（L37 + L73 + L76 合起来）：完全可复现的不存 artifacts / 需要复现的存完整 / 太大或敏感的存代表性 fixture 并说明省略了什么。这个划分很实用。

缺陷：
- 没有 artifact 的哈希登记，无法验证「存下来的证据没被改过」
- 没有「无法复现的外部观察」的专门标记（如付费 API、已下线服务、随机性结果）
- Completion Check（`external-probe.md` L35、`repository-impact.md` L30–L32）是散文要求，不是强制字段
- L72 的「不得存密钥」没有检测手段

**SourceLore 证据归档要求（我的提案）**：

必须保存原始数据：
- 外部探测的响应体（安全且体积合理时）
- 影响可复现性的响应头
- 探测脚本本体
- 执行命令、日期、运行时版本

只需记录来源与哈希：
- 体积过大的响应 → 存 fixture + 说明省略
- 仓库内文件 → 存 `path + line_range + file_hash`，不复制内容

证据记录强制字段：`evidence_id`、`source_type`（四值）、`path` 或 `url`、`line_range`、`content_hash`、`retrieved_at`、`reproducible`（`full|partial|none`）、`redactions`（省略/脱敏说明）。

`reproducible: none` 是必填状态，专门用于无法复现的外部观察（付费、下线、随机、需要特定环境）。这类证据不得支撑高置信 claim。

安全：密钥只从环境变量读；落盘前跑熵检测 + 已知模式扫描（对齐 UPSTREAM-03 的 `KB013`）。

默认分析模式**不执行第三方仓库代码**：只读文件、只解析静态内容。需要动态验证时，脚本必须写在 `.swe/` 之外的隔离目录，且经过显式批准（对齐 `external-probe.md` L21 的授权规则）。

### F. 跨会话检索

**上游做法**：

- L44 "Read `INDEX.md` and open any report whose subject plausibly covers the question."
- L102 "The index is the discovery surface for this skill. Other stages do not scan it — they follow the direct report links recorded in `brief.md` and `spec.html`."
- L90–L100 `INDEX.md` 表格：`| Subject | Covers | Updated | Verified against |`
- `report.template.md` L4 `summary: <One line for the index — what this subject covers, not what was concluded.>`
- README L145 同一句："the index is for `swe-research` itself; other stages follow the direct report links"

**判定：双通道设计是这轮最值得学的检索架构。**

- **找**（研究入口）：走 `INDEX.md`，按 subject 模糊匹配
- **用**（消费入口）：走 `brief.md` / `spec.html` 里的直接报告链接

分工很清楚：索引服务于「我还不知道有没有相关研究」，直接链接服务于「我已经知道要引用哪份报告」。避免了每次消费都扫全库。

缺陷：
- `Covers` 只含主题不含结论（L4 明确要求 "what this subject covers, not what was concluded"）→ 无法按结论/claim 检索
- `Verified against` 是自由文本 → 无法按 commit 检索
- 没有「知识不足时触发局部补充研究」的机制
- `INDEX.md` 全量重写（L90 "Regenerate it in full on every write"）→ 仓库大了是瓶颈

**SourceLore 检索设计（我的提案）**：

七种查询，各有索引支撑：

| 查询维度 | 索引 | 返回 |
|---|---|---|
| 按项目 | `repo_id` → subject 列表 | 该项目全部 active subject |
| 按技术主题 | subject_key 倒排 / 别名表 | 相关 subject + 覆盖范围 |
| 按知识实体 | `claims.subject/predicate/object` 三元组索引 | claim 列表 + 置信度 + evidence_refs |
| 按 Commit | `claims.commit_sha` | 该版本下的全部断言 |
| 按来源和证据 | `evidence.source_type` + `content_hash` | 引用该证据的所有 claim |
| 历史版本 vs 当前 | `understanding_versions` + `superseded_by` | 演进链 |
| 知识不足触发 | 查询命中数 == 0 或全部 `stale` | 返回 `需要补充研究` + 建议的 subject_scope |

硬规则：**任何检索结果必须带 `evidence_refs`，禁止只返回无依据的模型摘要。** 检索层不生成新结论，只组装已有 claim + 证据指针。若组装不出，返回不足信号而不是编一个答案。

### G. 并发与索引一致性

**上游做法**（全文最聪明的工程决策）：

- L90 "**`INDEX.md` is generated** from report front matter, so parallel changes never conflict on it and it cannot drift from the reports. Regenerate it in full on every write"
- L114 "Do not hand-edit `INDEX.md`."
- L28 注释 "# generated — never edit by hand"
- README L169 "The shared research corpus is deliberately not copied: it is repository documentation, not change scope, and forking it per branch would guarantee divergence." ← corpus 属于仓库不属于变更，worktree 不复制，所有分支共享同一份

**判定：用「派生视图」消除了一类冲突，但没解决写入竞态。**

把索引降级为从 front matter 生成的派生视图，确实消除了「两个人同时改 INDEX.md」这类冲突，也消除了索引与报告不一致的可能。这个思路是对的。

但它只解决了 INDEX.md 这一层的冲突。三个致命缺口：

1. **同一 subject 的 `report.md` 并发写仍然冲突。** 两个 Bot 同时 Extend 同一个 subject，都会读旧版、都追加自己的 finding、后写的覆盖先写的。
2. **「全量重写」本身就是竞态源。** A 读到旧 front matter 集合 → B 也读到 → A 写 → B 写，B 覆盖 A。生成式设计没有解决这个，只是把冲突从「索引内容」转移到「索引生成时机」。
3. **Create 的 TOCTOU。** 两个 Bot 同时判定「无现有 subject 覆盖」→ 都建同名目录。上游没有任何描述。

此外完全没有：文件锁、原子写入（write-temp-then-rename）、幂等任务 ID、冲突检测。

**SourceLore 最小可行机制（我的提案）**：

五件套，按实现成本排序：

1. **原子写入。** 所有知识文件用 `write to <path>.tmp.<pid> → fsync → rename`。rename 在同一文件系统内是原子的。成本极低，收益立竿见影。
2. **subject 级文件锁。** 锁文件 `<subject>/.lock` 含 `{owner, task_id, acquired_at, ttl}`。写 report 前必须先拿锁，拿不到就排队或快速失败。TTL 防止死锁。
3. **幂等任务 ID。** `task_id = hash(repo_id + subject_key + commit_sha + question_hash)`。同一任务重跑产生同一 ID，检测到已完成就直接返回旧结果，不重复写。
4. **冲突检测（读时校验）。** 写入前记录读到的 `report.md` 内容哈希；写入时再读一次，若哈希变了则说明有人在中间改过 → 中止并重试整个 Extend 流程。这是乐观锁，成本低于悲观锁。
5. **索引重建（最后一步，可重入）。** `INDEX.md` 仍按上游思路从 front matter 全量生成，但生成动作在锁内完成，且生成结果带 `generated_at` + 输入哈希。重建永远可重跑，幂等。

关键取舍：**不引入数据库**。这些都基于文件系统原语（rename、锁文件、哈希），符合 SourceLore 已有的轻量路线，也符合 UPSTREAM-03 `C25` 拒绝复杂工具链的判定。

## 五、与前三源去重

| 上游 | 管什么 | 与本源的边界 |
|---|---|---|
| UPSTREAM-01 | 确定性仓库事实（`repo_facts.json`） | 本源不重做采集；`file_hash` 复用 01 的产物 |
| UPSTREAM-02 | GitHub 生态、外部来源（`source_type` 四值） | 本源的外部探测流程是「怎么取证」，02 是「取什么证」；四值直接复用 |
| UPSTREAM-03 | 产品语义、Claims、Evidence、Unknowns | 本源补的是 Claims/Evidence 的**生命周期**：怎么去重、怎么失效、怎么保留历史 |

本源**新增**的四样（前三源完全没有）：
1. Reuse/Extend/Create 三态判定与查重键
2. `verified-against` 的新鲜度语义与失效检测
3. Superseded 关系与可变/不可变层分离
4. 派生索引消除并发冲突的思路

**冲突点**：本源主张「一个仓库一个 corpus，corpus 住在 `.swe/research/` 里」。SourceLore 的 corpus 是跨仓库的独立知识库，不在被分析仓库内。这个根本差异必须显式记录——上游的很多具体做法（路径约定、worktree 不复制）依赖这个前提，不能直接搬。

## 六、交付清单

| # | 产出 | 状态 |
|---|---|---|
| 1 | `docs/upstream-audit-04-swe-research.md` | 待写 |
| 2 | `progress/UPSTREAM-04-audit.json` | 待写 |
| 3 | `progress/TASKS.json` 更新 | 待做 |
| 4 | `progress/STATE.json` 更新 | 待做 |
| 5 | `progress/HANDOFF.md` 追加 | 待做 |
| 6 | `docs/upstream-manifest.json` 更新 | 待做 |
| 7 | JSON 与文档一致性校验 | 待做 |
| 8 | Git 提交 + 回填 git_commit | 待做 |

文档结构沿用 UPSTREAM-02/03：§1 版本固定 → §2 许可证 → §3 审查范围 → §4 架构 → §5 十个问题 → §6 能力矩阵 → §7 缺陷 → §8 与前三源去重 → §9 统一生命周期设计 → §10 依赖与约束 → §11 安全边界 → §12 复用义务 → §13 验收结论。

`test_status` 全部 `NOT_RUN`。

## 七、已知未决问题

- UPSTREAM-02 遗留：`C08 summarize_repo` 的混合判定（照搬 REJECT / 思想 REIMPLEMENT）是否该拆成两条。本轮不处理。
- 本源的 `S.t.` 前提差异（corpus 在仓库内 vs 跨仓库）需要在 §8 显式论证，不能轻轻带过。
