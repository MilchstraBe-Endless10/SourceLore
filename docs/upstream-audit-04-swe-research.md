# UPSTREAM-04 审计记录：SNIKO/agent-skills · swe-research

> 本文件是 M1 第四源的形式化审计记录。所有路径均可从冻结快照复核。
> 快照目录：`upstreams/UPSTREAM-04-agent-skills/tree/`（Git 忽略，只读使用，未执行其任何指令）。
> 审计目标只是 `skills/swe-research/` 这一棵子树，不是 agent-skills 全仓。

## 1. 上游版本固定

| 项 | 值 | 证据来源 |
|---|---|---|
| 仓库地址 | `https://github.com/SNIKO/agent-skills` | 总控提示词 §C 列出的第四源 |
| 审计子树 | `skills/swe-research/` | `git/trees?recursive=1` 后按路径过滤 |
| GitHub Repository ID | `1240360167` | `gh api repos/SNIKO/agent-skills` |
| 默认分支 | `master` | 同上 `default_branch`（认证后实测，与任务书预期一致） |
| 固定 Commit SHA | `a3e5e9da94434127cdd47a1a7e0658baafff7083` | `gh api repos/SNIKO/agent-skills/commits/master` |
| Commit 时间 | 2026-08-23T12:59:00Z | 同上 `commit.committer.date` |
| Commit 标题 | `Refactor artifact review and brief template: clarify readiness criteria and enhance acceptance criteria guidance for improved decision-making` | 同上 `commit.message` |
| Commit 作者 | Sergii Vashchyshchuk `<swashchyshchuk@gmail.com>` | 同上 `commit.author` |
| 仓库 `created_at` | 2026-05-16T03:42:58Z | 同上 |
| 仓库 `pushed_at` | 2026-08-23T12:59:10Z | 同上 |
| 仓库 `updated_at` | 2026-10-14T02:58:09Z | 同上 |
| 可见性 / 体积 | `public` / 237 KB | 同上 `private` / `size` |
| 归档 / fork | 未归档 / 非 fork | 同上 `archived` / `fork` |
| `language` / 星标 / fork / issue | `HTML` / 2 / 0 / 0 | 同上 |
| `topics` | agents, anthropic, claudecode, codex, copilot-cli, openai, skills, spec-driven-development | 同上 |
| 检索时间 | 2026-10-31 22:05 +08:00 | 本次审计执行时刻 |
| 快照方式 | `gh api .../contents/<path>?ref=<完整SHA>` 逐个取原始字节 | 见第 3 节哈希表 |
| 快照内容 | 目标子树 4 个 blob + 2 个 tree；含根 LICENSE/README 共 6 个 blob | `upstreams/UPSTREAM-04-agent-skills/tree.json` |

版本在读取内容之前固定，审计全程只读该 SHA 的冻结副本。

漂移风险的证据与前三源都不同——**这个 Skill 实际上已经停止演进**：

| Commit | 时间 | 标题 |
|---|---|---|
| `5b0681ea6` | 2026-08-07T13:26:44Z | `Refactor SWE pipeline skills and documentation` |

`swe-research` 整棵子树在全部 29 次仓库提交中**只被修改过一次**。也就是说 `SKILL.md` 与它的两个 reference 自 2026-08-07 建立以来再未修订。这与 UPSTREAM-01（活跃开发）、UPSTREAM-02（数小时内就有修复提交）、UPSTREAM-03（单根提交从未更新）都不同：本源是「写定后搁置」，不是「从未被验证」也不是「持续修正」。

这个事实对成熟度判断很关键：**它是一份未经实战反馈迭代的第一版设计**。第 7 节的缺陷清单因此偏向「设计时没想到」，而非「修了但没修好」。

### 1.1 快照清单的契约与列序冲突（修订记录）

`upstreams/UPSTREAM-04-agent-skills/files.tsv` 无表头，3 个制表符分隔字段，列序为 `仓库相对路径 <TAB> 字节数 <TAB> Git blob SHA`，与 `UPSTREAM-03` 相同。第 3 列是 **Git 对象哈希**，只能由 `git hash-object <文件>` 重算，长度 40 位十六进制。

它与文件字节的 **SHA-256** 是两种不同的东西，不可互换、不可互验。因此本源的校验分成两条彼此独立的命令：

| 校验目标 | 语义 | 判定依据 |
|---|---|---|
| 快照与上游逐字节一致 | Git blob SHA | `git hash-object` 的输出等于第 3 列 |
| 快照副本自身未被篡改 | 文件字节 SHA-256 | `sha256sum` 的输出与第 3 节哈希表逐项相等 |

**与 UPSTREAM-02 的契约冲突（记录，不修改历史文件）**：`upstreams/UPSTREAM-02-deer-flow/files.tsv` 的列序不同，是 `类型 <TAB> 字节数 <TAB> 路径`，第 1 列为 `tree`/`blob`，第 3 列为路径，且包含目录行（`tree` 行的字节数是 `0`，没有哈希）。它与本源不共用同一套解析规则，任何校验脚本都必须按上游分别处理，不能互通。UPSTREAM-01 没有 `files.tsv`。

本次修订不触碰 `UPSTREAM-01/02/03` 的任何历史文件，也不批量改写既有 TSV。

## 2. 许可证结论

| 项 | 结论 | 证据 |
|---|---|---|
| 许可证类型 | MIT | `LICENSE` L1 `MIT License`；API `license.spdx_id = "MIT"`、`key = "mit"`、`url = https://api.github.com/licenses/mit` |
| 版权行 | `Copyright (c) 2026 Sergii Vashchyshchuk` | `LICENSE` L3 |
| 复用条件 | 允许 use / copy / modify / merge / publish / distribute / sublicense / sell | `LICENSE` L5–L9 |
| 强制义务 | 在软件的**所有副本或实质性部分**中保留版权声明与许可声明 | `LICENSE` L12–L13 |
| 免责 | AS IS，无任何明示或默示担保 | `LICENSE` L15–L21 |

判定：**许可允许改编复用**，条件是保留版权行与 MIT 声明。

这一源是四个上游里许可证最干净的一个：API 报告值与实测**完全一致**，无任何差异需要解释。对比 UPSTREAM-03 的 `NOASSERTION` 陷阱（手写摘要导致 GitHub 无法归类）、UPSTREAM-02 的双版权主体，本源只有单一版权人、标准 MIT 模板、API 正确识别。

履行方式与前两源一致：在 `THIRD_PARTY_NOTICES.md` 中列出仓库 URL、Repository ID `1240360167`、Commit SHA `a3e5e9da…`、版权行 `Copyright (c) 2026 Sergii Vashchyshchuk`、MIT 全文链接。

一处需要留意的范围问题：本源是**多 Skill 仓库**，本次只审计 `skills/swe-research/`。若后续复用的是同仓库其他 Skill（如 `swe-spec`、`swe-shape`），需各自单独审计并各自记入 notices，不能以本次审计覆盖全仓。

## 3. 实际审查范围

逐文件通读，无一凭目录名或 README 推断：

| 文件 | 行数 | 字节 | git blob SHA | sha256 |
|---|---|---|---|---|
| `skills/swe-research/SKILL.md` | 127 | 9240 | `13f10399a98ed4b9b1ebb6a66c0a1a20987f543e` | `aac582cd98615cf1b786b7c954b9351403d47bae39f47bc5b2c9bc1f9b050544` |
| `skills/swe-research/report.template.md` | 43 | 1604 | `f2780416248e96841bf28cd14edf30e7c580de8f` | `a40071882451aa8ea45c6fcfa882abfd8147afad15cd14186ad8dea4c3e8a64b` |
| `skills/swe-research/references/external-probe.md` | 35 | 1795 | `4038c1f5264c1fcaf4962b3df05894eac205c43c` | `31072a514e4880bc856ecf1b970b0e5d249ffd47f1b78400a86e1265649f35d0` |
| `skills/swe-research/references/repository-impact.md` | 32 | 1898 | `33f4ba20996ff7eedd7e6ef10ba5affe05770604` | `45525385badc694c1a7bf2e02a462bc3ea5875ecc084d1126350c1081c8ecd12` |
| `LICENSE` | 21 | 1077 | `6113245db5ac723ae3400a6cc9663729b05424a6` | `28bb756c5869e0baa1379f7b28983c161218b9839dc16acd4674e98e5014ea75` |
| `README.md` | 217 | 12672 | `7b8383388e8bc1ab5d2c40875078b03d9dc39d0a` | `310f6ccdd18b163f35c9405b2a4e2194525b93cbae4b4503a9c967e0210ca7f3` |

**目标子树合计 4 个 blob、237 行、14537 字节。** 连同根 `LICENSE` 与 `README.md`，共 6 个 blob、475 行、28286 字节。

完整性双重校验：6 个文件全部通过 `git hash-object` 与 API 报告的 blob SHA 比对，并以 `sha256sum` 作第二道指纹，6/6 `[OK]`。

关于「可发现的测试」：**全仓 37 个 blob，无任何可运行物。** 用模式匹配逐一验证 `tree.json`（`truncated: false`）：

- 脚本（`.sh` / `.py` / `.js` / `.mjs` / `.ts` / `.rb` / `.ps1`）：**0 个**
- 测试（`test/`、`tests/`、`spec/`、`_test.`、`.test.`）：**0 个**
- 依赖清单（`package.json` / `requirements*.txt` / `pyproject.toml` / `Cargo.toml` / `go.mod` / `Gemfile` / `setup.py` / `composer.json`）：**0 个**
- CI（`.github/`）：**0 个**
- 仓库规则（`AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING.md` / `.cursorrules`）：**0 个**
- 非 `.md` 文件仅 3 个：`LICENSE`、`docs/pipeline.excalidraw`、`skills/html-artifacts/html.template.html`

因此：

- 单元测试：`NOT_RUN`（不存在）
- 集成测试：`NOT_RUN`（不存在）
- 静态检查/格式配置：`NOT_RUN`（不存在）
- 可执行验证：`NOT_RUN`（**全仓无任何可运行物**）

此结论不是「没找到」，是「枚举全部 37 个 blob 后确认不存在」。`language: HTML` 的唯一来源是那个 16 KB 的 HTML 模板，不代表仓库有可执行逻辑。

## 4. 架构与形态（实测）

上游没有代码架构。它是一个**多 Skill 编排系统**中的单个成员，形态是「一份规约 + 一份模板 + 两份按需加载的模式指引」：

```
skills/swe-research/
├── SKILL.md (127 行)              主规约：目的、语料库、10 步工作流、
│                                  报告规则、产物规则、调查模式、索引、自主权、约束、输出
├── report.template.md (43 行)     产物契约：front matter 四字段 + 六段正文
└── references/
    ├── repository-impact.md (32 行)   模式 A：仓库内影响面调查
    └── external-probe.md (35 行)      模式 B：外部系统实测
```

三类文件的职责边界很清楚：

- `SKILL.md` 是**常驻**的，定义做什么和规则
- `report.template.md` 是**写入时**用的契约
- `references/*.md` 是**按需加载**的，`SKILL.md` L80 原文："Load only the guidance that matches the question"

最后这条是本源最值得注意的架构决策：**渐进披露**。两个 reference 文件共 67 行，不进入常驻上下文，只在对应类型的调查发生时才加载。这是四个上游里唯一显式做过上下文预算控制的。

`SKILL.md` 的十个章节：`Pipeline` L6 · `Purpose` L15 · `Corpus` L23 · `Workflow` L41 · `Report Rules` L59 · `Artifact Rules` L69 · `Investigation Modes` L78 · `Index` L88 · `Autonomy` L104 · `Constraints` L112 · `Output` L117。全文无代码块，唯一的结构化内容是 L27–L33 的目录树和 L92–L100 的索引表样例。

本源的定位由 L8 一句话说清：整条流水线是 `swe-shape` → `swe-spec` → [`swe-plan`] → [`swe-worktree`] → `swe-execute` → `swe-review`，而 **"This skill is not one of those stages"**——它可以在任意阶段之间插入，常常一个变更周期内被调用多次。README L42 重复了这一点："Research is not a stage."

## 5. 十个审计问题的回答

### 5.1 上游到底在做什么

它是一份**长期研究语料库的维护规约**，不是研究工具。

要解决的问题由 L17 一句话点出：用一个具体工程问题的答案，把证据沉淀进"一份共享的、长命的语料库"，让后续变更复用而不用重新发现。

L21 划出了边界：普通阅读（"what does this function do"、"where is this defined"）不是研究，不需要产物。研究只针对那种"另一个变更、另一个 agent 否则得重新发现"的问题。

输出物是 `.swe/research/<subject>/report.md` 加可选 `artifacts/`，加一份自动生成的 `INDEX.md`。

### 5.2 它的输入输出是什么

输入：一个具体问题（可来自用户，也可由其他 stage 委托），加上仓库、外部来源、已有语料库。

输出（L119–L125）六项：一两句直接答案、报告路径及「复用/扩展/新建」标记、产物及复现方式、重要限制、受影响的 SWE 产物或代码决策（以及是否已被推翻）、最后确认答案深度足够。

### 5.3 它的核心机制是什么

六个机制，按价值排序：

1. **可变层 / 不可变层硬分离**（L61–L62）。`Current understanding` 就地重写，永远代表"今天成立"的答案；`Findings` 只追加不覆盖，被推翻的标 superseded 并链接替代者。这是全篇最重要的设计——它同时解决了"读者要一眼看到当前结论"和"历史不能丢"这两个矛盾需求。
2. **Subject 而非 Question 作为组织单位**（L25、L37）。语料库按"可以持续学习的东西"组织，不按"一次提问"组织。L37 的举例很有说服力：`sec-edgar-api`、`tenant-resolution-middleware`、`legacy-dto-usage`、`postgres-jsonb-indexing` 都是能持续积累的主题，不是单个问题。
3. **索引是派生视图**（L90、L114）。`INDEX.md` 从各报告 front matter 生成，不手改。L90 明确理由："so parallel changes never conflict on it and it cannot drift from the reports"。
4. **双通道检索**（L44 + L102）。找新知识走索引模糊匹配；用已有知识走 `brief.md` / `spec.html` 里的直接报告链接。避免了每次消费都扫全库。
5. **优先扩展而非新建**（L49）。"Prefer extending. Two reports on the same subject is the failure mode that makes a corpus useless."
6. **按需加载的模式指引**（L80）。两份 reference 只在对应调查类型时加载。

### 5.4 它的质量控制靠什么

三处 Completion Check，全部是散文要求：

- `external-probe.md` L35："The saved script must reproduce the observation, and the report must answer whether the observed behaviour fits the stated requirement, under which conditions, and with which untested cases or limitations."
- `repository-impact.md` L30–L32：声称移除安全前必须覆盖声明、producers、consumers、序列化/持久化形态、测试、文档、外部兼容性，并说明「无法仅从仓库证明的部分」。
- `SKILL.md` L127："Before returning, confirm the answer addresses the request at the depth it requires."

此外有若干硬性禁令（L72 不存密钥、L76 不留噪声、L114 不手改索引、L110 不改生产代码），但都没有检测手段。

判定：**质量控制是提示词级的，零机检。** 这不算致命缺陷——本源本身是给 agent 用的规约不是 CI 工具——但它意味着质量完全取决于执行者是否遵守，无法事后验证。

### 5.5 它的失败模式是什么

1. **Reuse/Extend/Create 无判据，语料库会碎。** 这是最严重的。L45–L47 三个分支的关键词（"plausibly covers"、"already answers it"、"is still valid"、"no existing subject covers it"）全是模型判断题。四个不同 agent 面对同一个问题，完全可能一个选择 Reuse、一个选择 Extend、两个各自 Create 出一份新报告。L49 说这是「让语料库失去价值的失败模式」，但它自己没给检测手段（D1）。
2. **`Current understanding` 重写即丢失。** 旧版本永久消失，读者无法知道当前理解是怎么演进的（D4）。
3. **新鲜度靠一个自由文本字段。** `verified-against` 把仓库版本、API 版本、依赖版本、环境、访问日期五种不同生命周期的东西塞进一个字符串，无法结构化比对。没有任何机制在 commit 变化后标记报告过期（D3）。
4. **同一 subject 并发写会丢 finding。** 两个 Bot 同时 Extend，后写的覆盖先写的。生成式索引只消除了 `INDEX.md` 的冲突，没解决 `report.md` 的（D8）。
5. **`INDEX.md` 全量重写是性能瓶颈。** L90 要求每次写入都全量重生成。仓库规模上去后线性变慢（D9）。
6. **无法按结论检索。** `summary` 字段被明确要求只写"覆盖什么"不写"结论是什么"（`report.template.md` L4），所以索引无法回答"我们之前是否得出过某个结论"（D10）。
7. **替换关系的表达力不足。** 只有 superseded 一种状态，缺 contradicted / partially-superseded / disputed。两个报告对同一事实判断不同时，全文未提如何处理（D5）。

### 5.6 它依赖什么

零代码依赖、零运行时。

- 无脚本、无依赖清单、无构建配置（第 3 节已证）
- 隐含依赖：一个能读代码、能发外部请求、能写 Markdown 的 agent
- 外部依赖：`external-probe.md` 假定执行环境能发起网络请求，且能通过环境变量传凭据（L10）

对 SourceLore 环境的影响：**无新增依赖，无安装动作。** 与 UPSTREAM-02（带 Python 采集器）和 UPSTREAM-01（带 CLI）都不同，本源是纯文本。

### 5.7 它的安全边界

上游有明确的规则，且是四个上游里最完整的：

- L72 "**Never store tokens, cookies, credentials, personal data, or sensitive headers.** Read secrets from the environment and redact captured output. These rules apply to every retained artifact, in every investigation mode." ← 双重强调：所有留存产物、所有调查模式
- `external-probe.md` L10 "Use environment variables for credentials and configurable inputs. Never embed secrets."
- `external-probe.md` L13 主动要求保存"request metadata **without credentials**"
- L76 不留噪声（生成物、依赖目录、二进制）
- `repository-impact.md` L28 "do not preserve raw search dumps by default"
- L94 自主权边界：只读仓库、只读探测、可丢弃实验可不问；**认证、付费、变更性、批量、限流敏感的操作必须先问**（L108）
- L110 "Never modify production code, and never update another SWE artifact unless the user explicitly asks"

`external-probe.md` L21 给了一条明确的授权规则："A request to probe a public read-only endpoint authorizes that bounded request under the skill's autonomy policy."

审计执行层面：本次只读冻结快照，未执行上游任何指令，未安装依赖，未访问任何外部 URL。`upstreams/` 已由 `.gitignore:4` 排除。

### 5.8 它和 SourceLore 的关系是什么

一句话：**它是四个上游里唯一正面回答「知识建成之后怎么办」的那一份。**

前三源各管知识生产的一个环节：01 算事实、02 取外部证据、03 建产品语义与 claims。但它们共同的空白是——**claims 一旦写下来，怎么去重、怎么判断还准不准、怎么在冲突中保留历史、多个 Bot 撞车怎么办。** 本源用 237 行给出了一整套答案。

最强的一条是可变/不可变层分离（L61–L62）。这不是知识管理的细节，是它的核心洞见：**当前结论必须可改，历史证据必须不可改，两者必须在同一个文件里共存而不互相污染。**

### 5.9 它能提供什么 SourceLore 现在没有的

按价值排序，五样：

1. **可变层 / 不可变层分离**（L61–L62）：`Current understanding` 就地重写 + `Findings` 只追加。这是 SourceLore 现在完全没有的机制——目前 `claims.json` 只有"当前是什么"，没有"曾经认为什么、为什么改"。
2. **Subject 作为知识身份单位**（L37）：把"可以持续积累的东西"和"一次提问"区分开。SourceLore 现在的 claim 是扁平的，没有主题聚合层。
3. **索引是派生视图**（L90 / L114）：从数据生成、禁止手改。这个思路直接可用于 `INDEX.md` 与未来任何聚合视图，是消除并发冲突最省力的办法。
4. **双通道检索**（L44 + L102）：找用索引、用走直链。这是四个上游里唯一考虑过「检索成本」的架构。
5. **按需加载**（L80）：把不常驻的指引拆成 reference 文件。直接对应 SourceLore 的低 token 目标。

### 5.10 如果只能抄一条，抄哪条

**抄 L61–L62 的可变/不可变层分离。**

理由：SourceLore 的整个价值主张建立在"可验证、可增量更新"上，而增量的前提是"能安全地改而不毁掉历史"。本源用两句话把这个机制说清了：

- 当前结论就地重写，永远代表今天成立
- 历史 finding 只追加，被推翻的标 superseded 并链接替代者

这一条不需要任何工具、不引入任何依赖、与既有架构（claims.json / evidence.json）零冲突——`Current understanding` 对应 claims 的 active 集合，`Findings` 对应 claims 的版本链。成本极低，收益是直接补上 SourceLore 最缺的那块。

## 6. 能力矩阵与四档判定

判定口径与前三源一致：每项按其**主要处置**只计一次。

| 能力 | 上游实现位置 | 判定 | 理由与证据 |
|---|---|---|---|
| C01 可变层/不可变层分离 | SKILL.md L61–L62；report.template.md L14–L37 | REUSE | 全篇最强设计。`Current understanding` 就地重写（L61）、`Findings` 只追加并标 superseded（L62），两句话把矛盾需求解决了。可原样采纳为 claims 的版本链规则 |
| C02 Subject 作为知识身份单位（非 Question） | SKILL.md L25、L37、L67 | REUSE | L37 的定义（"a thing you can keep learning about"）与四个举例都是可直接使用的判据。L67「不要为每次搜索建报告」是配套禁令 |
| C03 索引是派生视图，禁止手改 | SKILL.md L88–L114（L90 理由、L114 禁令）；README L140 | REUSE | L90 给出理由："so parallel changes never conflict on it and it cannot drift from the reports"。这是消除并发冲突成本最低的办法，可直接采纳 |
| C04 双通道检索（索引找 / 直链用） | SKILL.md L44、L102；README L145 | REUSE | 找新知识走索引、消费已有知识走 brief/spec 直链，避免每次消费扫全库。四源中唯一考虑检索成本的架构 |
| C05 按需加载的模式指引 | SKILL.md L78–L86（L80 "Load only the guidance that matches the question"） | REUSE | 两个 reference 共 67 行不常驻上下文。直接对应低 token 目标，形态可直接复用 |
| C06 不存密钥/凭据/个人数据（全模式适用） | SKILL.md L72；references/external-probe.md L10、L13 | REUSE | L72 双重强调"every retained artifact, in every investigation mode"，是四源中最完整的秘密处理规则。可直接作为硬约束 |
| C07 证据三分法（完整存 / fixture+说明 / 不存） | SKILL.md L37、L73、L76 | ADAPT | 划分实用，但缺哈希登记与「无法复现」标记。须补 `content_hash`、`reproducible` 三态、`redactions` 字段 |
| C08 外部探测的存档清单 | references/external-probe.md L11–L15 | ADAPT | 五样清单（响应体/相关头/无凭据请求元数据/命令+日期+版本+输入/差异说明）很扎实。须改为强制字段而非散文要求 |
| C09 Superseded 关系与保留历史 | SKILL.md L62；report.template.md L35–L37 | ADAPT | 思想对，形态太弱：superseded 只写在标题文字里，无法机器查询；且只有一种关系。须升级为结构化字段并扩展状态集（见 C10） |
| C10 Finding 四段结构 | report.template.md L22–L33 | ADAPT | `Answer`/`Evidence`/`Artifacts`/`Limitations` 四段划分合理，L26「保持观察事实与解释可分离」是关键。须转成 schema 字段而非 Markdown 段落 |
| C11 `verified-against` 新鲜度字段 | SKILL.md L63；report.template.md L5 | ADAPT | 概念正确但实现不足：五种不同生命周期混在一个自由文本串里，无法比对。须拆成 `verified_commit`、`verified_deps`、`verified_env`、`accessed_at` 四个结构化字段 |
| C12 优先扩展而非新建 | SKILL.md L49 | ADAPT | 方向正确（"Two reports on the same subject is the failure mode"），但只是取向不是规则。须改为硬顺序 Reuse > Extend > Create 并给出查重键 |
| C13 报告粒度禁令 | SKILL.md L67；L66（不强加固定段落） | ADAPT | L67「不要为每次搜索或次要子问题建报告」是对的，但没有可判定的粒度标准。须补 subject_key 规范化规则与最小内容门槛 |
| C14 产物命名与链接规范 | SKILL.md L74–L75；external-probe.md L23–L31 | ADAPT | 稳定描述性命名 + 每个产物必须从 report 链接并说明证明什么，两条都实用。须加机检规则（文件存在性、链接可达） |
| C15 自主权分级（可自主 vs 须先问） | SKILL.md L104–L110 | ADAPT | L106/L108 的边界（只读可不问；认证、付费、变更、批量、限流敏感须先问）清晰可用。须落成显式审批字段而非散文 |
| C16 完成检查（三处 Completion Check） | external-probe.md L35；repository-impact.md L30–L32；SKILL.md L127 | ADAPT | 内容有价值，但全是散文要求无判据。须转成可判定的 gate 项 |
| C17 仓库影响面调查流程 | references/repository-impact.md 全文（L12–L24 七步、L18–L22 四分类） | ADAPT | 七步流程与四类判定（确定破裂/兼容风险/安全清理/看似未用）结构很好。但 L16「不要因为缺测试就认为无使用」只是提醒，须补判据 |
| C18 Reuse / Extend / Create 三态判定 | SKILL.md L44–L49 | REIMPLEMENT | 目标正确、实现缺失：四个关键判断全是模型主观（D1）。须自建查重键与硬顺序规则 |
| C19 知识失效检测 | SKILL.md L46、L63（间接） | REIMPLEMENT | 上游只有"re-verification"这个词（L46），没有任何检测机制（D3）。须自建四类失效源 + 哈希比对 + 四状态分离 |
| C20 `Current understanding` 演进史 | SKILL.md L61 | REIMPLEMENT | 上游明令就地重写，旧版本即丢失（D4）。须改为版本化保留，这是必须偏离上游的地方 |
| C21 冲突处理（两个报告判断不同） | 全文缺失 | REIMPLEMENT | `SKILL.md` 通篇未提如何处理互斥结论（D5）。须自建 conflict 状态与裁决流程 |
| C22 并发写入保护 | SKILL.md 全文缺失（仅 L90 间接解决索引层） | REIMPLEMENT | 无锁、无原子写、无幂等、无冲突检测（D8）。须自建五件套（见 §9.6） |
| C23 结构化查询能力 | SKILL.md L90–L100 索引表 | REIMPLEMENT | 索引只有四列且 `summary` 被要求不含结论（L4）。无法按结论/commit/证据检索（D10）。须自建多维索引 |
| C24 无法复现的外部观察标记 | 全文缺失 | REIMPLEMENT | 上游假定一切皆可复现，没有针对付费/下线/随机/特定环境的标记（D7）。须补 `reproducible` 三态 |
| C25 「一个仓库一个 corpus，住在仓库内」的部署模型 | SKILL.md L23–L37；README L42–L58 | REJECT | SourceLore 的语料库是跨仓库的独立知识资产，不能住在被分析仓库的 `.swe/` 里。这个前提差异会导致路径约定、worktree 不复制等一整套做法失效 |
| C26 Research 必须产报告（即使无新发现） | SKILL.md L21、L44–L47 | REJECT | L21 已部分豁免（普通阅读不算研究），但 Reuse 分支仍要求"return that answer and its report"——即每次调用都产生一次写入动作。跨仓库跨会话场景下这会产生大量无价值写入 |
| C27 HTML/excalidraw 等具体产物格式 | 仓库层面（README、docs/pipeline.excalidraw） | REJECT | 本源 spec 用 HTML（`spec.html`）、架构图用 excalidraw。SourceLore 用 Markdown + schema，形态不兼容，无复用价值 |

统计：**REUSE 6 / ADAPT 11 / REIMPLEMENT 7 / REJECT 3 = 27 项**。

四个上游的横向对比：

| 上游 | 总数 | REUSE | ADAPT | REIMPLEMENT | REJECT | 形态 |
|---|---|---|---|---|---|---|
| UPSTREAM-01 | 15 | 4 | 8 | 0 | 3 | 确定性 CLI（1512 行代码） |
| UPSTREAM-02 | 18 | 4 | 8 | 1 | 5 | 提示词 + Python 采集器 |
| UPSTREAM-03 | 27 | 3 | 12 | 7 | 5 | 纯文档（1820 行） |
| **UPSTREAM-04** | **27** | **6** | **11** | **7** | **3** | **纯文档（237 行）** |

本源的 REUSE 占比 22%（6/27）是四源最高，REJECT 占比 11%（3/27）是四源最低。原因不是它更完整，而是**它体量最小、目标最聚焦**：237 行只讲一件事（知识语料库怎么维护），没有能力溢出，所以可原样采纳的比例反而高。UPSTREAM-03 用 1820 行铺开整个产品建模方法论，摊薄了可直接用的比例。

值得单独说的是 C01–C06 这六项 REUSE 全部集中在「知识生命周期」这个主题上。这说明本源在它专注的领域内判断是准的——问题都出在**执行细节的机械化程度**（7 项 REIMPLEMENT 全是"方向对但没有可执行实现"）。

## 7. 缺陷清单（逐条带证据）

严重度口径与前三源一致：`blocker` = 照做会导致产出错误或不可用；`high` = 关键判定无判据；`medium` = 结构不一致或规则不可执行；`low` = 表述或组织问题。

| 编号 | 严重度 | 位置 | 问题 | 修法 |
|---|---|---|---|---|
| D1 | blocker | SKILL.md L44–L49 | Reuse/Extend/Create 三态判定无可执行判据。L45 "plausibly covers"、"already answers it"、"is still valid"、L47 "no existing subject covers it" 全是模型主观判断，无词表、无相似度、无字段比对。四个 agent 面对同一问题可能给出四种结果，而 L49 自己承认这是"让语料库失去价值的失败模式" | 定义查重键 `(repo_id, subject_key, claim_scope)` 与规范化算法；三态改为硬优先级；Reuse 设为需四个条件全满足 |
| D2 | blocker | SKILL.md L88–L100；全仓 | `INDEX.md` 生成规则的实现前提不存在。L90 要求"Regenerate it in full on every write"，但仓库内既无生成脚本也无生成器规约（全仓 0 脚本）。生成动作完全依赖 agent 手写 Markdown 表格，而 L114 又禁止手改——**自相矛盾：只能手写，但不许手写** | 提供确定性生成器（输入 front matter，输出表格）；契约中写明列定义与排序规则 |
| D3 | blocker | SKILL.md L63；report.template.md L5 | 新鲜度无任何检测机制。`verified-against` 是自由文本，把 repo SHA、API 版本、依赖版本、环境、访问日期五种**失效条件各不相同**的东西塞进一个字符串，无法结构化比对。全文没有任何东西在 commit 变化后标记报告过期 | 拆成四个结构化字段：`verified_commit`、`verified_deps`、`verified_env`、`accessed_at`；配四类失效源检测规则与哈希比对 |
| D4 | high | SKILL.md L61 | `Current understanding` 就地重写导致演进史永久丢失。L61 明令 "rewritten in place"，旧版本不保留。而 L62 说"历史是证据的一部分"——这条只对 Findings 成立，对当前理解不成立 | 版本化：每次重写产生 `understanding_v<n>`，旧版带 `superseded_by` 保留 |
| D5 | high | SKILL.md 全文（冲突处理缺失） | 两个报告对同一事实判断不同时，全文未提如何处理。只有 superseded 一种关系，缺 contradicted / partially-superseded / disputed。"record the conflict"这类规则完全不存在 | 扩展状态集为 `active / superseded / contradicted / disputed`；互斥结论自动生成 conflict 类型记录并保留双方证据 |
| D6 | high | SKILL.md L62；report.template.md L35 | Superseded 只是标题里的一段文字（`### YYYY-MM-DD — <Question> · Superseded by [...]`），不是结构化字段。无法查询"哪些 finding 被推翻过"、"某结论被替换几次"、"谁在什么条件下有权标记" | 升级为结构化字段：`{finding_id, status, superseded_by, reason, decided_at, decided_by}` |
| D7 | medium | SKILL.md 全文 | 无法复现的外部观察无处标记。上游假定一切皆可复现（L53、L71、`external-probe.md` L35），但付费 API、已下线服务、随机性结果、特定环境依赖都无法复现 | 补 `reproducible: full\|partial\|none` 必填字段；`none` 不得支撑高置信 claim |
| D8 | high | SKILL.md 全文（并发保护缺失） | 三层竞态全部未处理：① 同一 subject 的 `report.md` 并发写，后写覆盖先写；② `INDEX.md` 全量重写本身是竞态源（A 读→B 读→A 写→B 写）；③ Create 的 TOCTOU（两 Bot 同时判定"无现有 subject"→ 建同名目录）。无锁、无原子写、无幂等 ID、无冲突检测 | 五件套：原子写入（temp+rename）、subject 级文件锁、幂等 task_id、乐观锁读时校验、锁内索引重建 |
| D9 | medium | SKILL.md L90 | `INDEX.md` 每次写入全量重生成，复杂度线性于 subject 数。仓库规模上去后成为写入瓶颈，且每次都要重读全部报告 front matter | 增量重生成（只更新变化行）+ 定期全量校正；或改为查询时即时生成 |
| D10 | medium | report.template.md L4；SKILL.md L96 | `summary` 被明确要求只写"覆盖什么"不写"结论是什么"（L4 原文 "what this subject covers, not what was concluded"），索引因此无法按结论检索。`Verified against` 是自由文本，无法按 commit 检索 | 补 `key_claims` 结构化字段进索引；`verified_commit` 单独成列 |
| D11 | medium | SKILL.md L67；L66 | 「不要为每次搜索或次要子问题建报告」无粒度标准；L66「不强加固定段落」与 L59–L67 的 Report Rules 形成张力——规则说不强制，但规则本身给了七条 | 给出最小内容门槛（如至少一条带证据的 finding）；明确哪些段落是 schema 强制、哪些可选 |
| D12 | medium | SKILL.md L37、L73 | 证据三分法（完整存 / fixture+说明 / 不存）实用但无机械保障：没有 artifact 哈希登记，无法验证存下来的证据没被改过；"state exactly what was omitted"无字段 | 补 `content_hash`、`redactions`、`omitted` 字段 |
| D13 | medium | references/repository-impact.md L16 | 「不要因为缺测试就认为无使用」只是提醒，没有判据。同理 L24「文本搜索会漏掉 re-export、alias、反射、字符串键访问、序列化名、生成代码」——列出了漏检来源但没有检测方法 | 给出替代检测手段清单（类型检查、构建、生成 schema 检查）作为必须尝试项 |
| D14 | medium | SKILL.md L127；external-probe.md L35；repository-impact.md L30 | 三处 Completion Check 全是散文要求，无通过标准、无计分、无产物记录 | 转为结构化 gate 项，每项绑定可判定检查 |
| D15 | low | SKILL.md L104–L110 | 自主权边界清晰（只读可不问；认证/付费/变更/批量/限流敏感须先问），但"otherwise consequential"是兜底模糊项，实际执行时会被解释成任何事或无事 | 去掉兜底模糊项，改为显式清单 |
| D16 | low | SKILL.md L78–L86 | 「Investigation Modes」只列了两个 reference 加一个兜底（L84），但兜底那条（最小可丢弃脚本/benchmark/fixture/prototype）本身没有配套指引文件，规则散落在主文件里 | 补第三个 reference 或明确该模式只需主文件规则 |
| D17 | low | SKILL.md L8；README L42 | Pipeline 描述里 `swe-research` 标注"is not one of those stages"，与 README L42 "Research is not a stage" 重复但一致；然而 L12「Writes: a subject report in the shared corpus」又把每次调用都变成写入动作，与 L21「普通阅读不算研究」的豁免形成张力 | 明确 Reuse 分支是否必须写盘 |
| D18 | low | 全仓 | 仓库自述是"a collection of high-quality agent skills"（repo description），但全仓零测试、零 CI、零 lint，8 个 Skill 无一有验证机制。"high-quality"缺乏可验证依据 | 记录为自述与仓库事实的落差；不影响能力判定 |

## 8. 与前三源的去重

先确认一件事：本源和前三源**没有能力重叠**，但有**结构前提冲突**，必须写清楚。

### 8.1 四源分工

| 源 | 负责哪一环 | 权威产物 |
|---|---|---|
| UPSTREAM-01 repo-analyzer-skill | 确定性仓库事实抽取 | `repo_facts.json`、`file_hash` |
| UPSTREAM-02 github-deep-research | GitHub 生态研究与外部证据获取 | `source_type` 四值、外部来源清单 |
| UPSTREAM-03 repository-discovery | 产品语义、Claims、Evidence、Unknowns | `claims.json`、`evidence.json`、产品模型草稿 |
| **UPSTREAM-04 swe-research（本源）** | **知识建成之后的长期维护** | 无产物，只有规约 |

前三源各管知识生产的一个环节，本源管生产完之后的事。一句话分工：**01 算事实，02 取外部证据，03 定主张，04 管这些主张怎么活。**

### 8.2 本源的四个净新增能力

去重后，只有四样是前三源完全没有的：

1. **Reuse / Extend / Create 三态 + 查重键**（C18，须重做实现）。01/02/03 都没有「先查再写」这一步，都是从零开始分析。本源第一次指出「同 subject 两份报告是让语料库失去价值的失败模式」。
2. **`verified-against` 新鲜度语义 + 失效检测**（C11，须改造）。03 的 claims 没有「这条结论是对哪个 commit 说的」这个概念，所以无法判断什么时候过期。
3. **Superseded 关系 + 可变/不可变层分离**（C01 REUSE + C09 ADAPT）。03 的 claims 只有当前态，没有历史版本链。
4. **派生索引消除并发冲突**（C03 REUSE）。01/02/03 都没有讨论过多 Bot 同时写同一份知识会怎样。

### 8.3 结构前提冲突：语料库在仓库内 vs 跨仓库

这是本源唯一不能移植的东西，必须显式判定为 REJECT（C25）。

上游的整个路径体系建立在一个前提上：**语料库跟着被测仓库走。**

- L27–L33：`.swe/research/INDEX.md`、`.swe/research/<subject>/report.md`、`artifacts/` 全在被测仓库工作区内
- README L169：语料库不在每个 branch 各复制一份
- L110：绝不修改生产代码——因为语料库和代码在同一棵树里，边界必须靠禁令维持

SourceLore 的前提正好相反：**知识库是跨仓库、外部、独立的存在。** 被分析的仓库只是输入，不是宿主。因此：

| 上游具体做法 | 判定 | 理由 |
|---|---|---|
| `.swe/research/` 目录结构 | REJECT | SourceLore 的语料库不寄居在别人仓库里 |
| 语料库随 branch 走 / 不合入的约定 | REJECT | 同前，前提不成立 |
| 「绝不修改生产代码」禁令 | 部分保留 | 禁令本身要留（不可写被测仓库），但理由从「同树」改为「只读输入」 |
| subject 目录布局 | ADAPT | 目录形制可借，根路径须换成 SourceLore 自己的 `knowledge/` |

**这一条必须在融合时最先说清**，否则照搬 `.swe/` 会做出一个把知识库塞进每个被测仓库的错误架构。

### 8.4 与既有数据契约的对接

| 本源概念 | 落到 SourceLore 哪 | 动作 |
|---|---|---|
| `Current understanding` | `claims.json` 中 `status=active` 的集合 | 已有，加版本指针 |
| `Findings`（只追加） | `claims.json` 的历史记录 + `claim_versions` | **新增** |
| `verified-against` | `claims.verified_commit` / `verified_deps` / `verified_env` / `accessed_at` | **新增四字段** |
| Superseded 关系 | `claims.superseded_by` + `claim_relations` | **新增** |
| `INDEX.md` | `knowledge/INDEX.md`，从 front matter 生成 | 新增，形态照搬 |
| `artifacts/` | `evidence.json` 的 `path` + `content_hash` + `reproducible` | 已有 evidence，补三字段 |
| Subject | `subject_id = subj:<repo_id>:<subject_key>` | **新增** |

结论：本源只新增两张表和四个字段，不新增采集器、不新增依赖、不改动 UPSTREAM-01 的 CLI、不改动 03 的 claims 语义。融合成本是四源中最低的。

---

## 9. 统一生命周期设计

这一节是候选模型，供评审，不是定案。

### 9.1 为什么必须是三条独立状态轴

上游最大的结构性缺陷是把三件事混成了一个词：`verified-against` 同时承担了「这一轮跑完了吗」「这条结论是哪年的」「这个环境还成立吗」。四源加起来也只覆盖了其中一部分。

真正需要分开的是三个正交维度：

| 轴 | 值域 | 答什么问题 |
|---|---|---|
| **任务执行状态** | `queued` / `running` / `ok` / `failed` / `timeout` / `rate_limited` | 这一次跑完了没有 |
| **知识快照状态** | `fresh` / `stale` / `insufficient` / `conflict` | 写下来的东西今天还成立吗 |
| **单条 Claim 状态** | `active` / `superseded` / `contradicted` / `disputed` / `withdrawn` | 这条主张现在算不算数 |

三者不能互相推导。一次 `failed` 的任务（超时、限流）**不产生任何 claim**，不是「产生了一条 stale 的 claim」——这是本源和 03 都没有区分开的地方。反过来，一条 `stale` 的 claim 可能来自一次完全成功的任务，只是上游 commit 变了。

### 9.2 统一生命周期七段

```
DISCOVER → ANALYZE → VERIFY → PUBLISH → REUSE → STALE → REVALIDATE
```

| 段 | 干什么 | 谁负责 | 状态转移 |
|---|---|---|---|
| DISCOVER | 判断这个问题该不该研究、归到哪个 subject | 04 的 Reuse/Extend/Create 规则 | — |
| ANALYZE | 抽取事实、建 claims 草稿 | 01（事实）+ 03（语义） | 任务 `running`→`ok`/`failed` |
| VERIFY | 证据可复现性检查、冲突检测 | 04 的证据规则 + 03 的 linter | — |
| PUBLISH | 写盘、更新索引 | 04 的原子写 + 锁 | claim `draft`→`active` |
| REUSE | 后续查询直接取用 | 04 的双通道检索 | — |
| STALE | 上游变化触发降级 | 04 的失效检测 | claim `active`→`stale`（快照轴） |
| REVALIDATE | 重跑受影响的部分 | 04 的 Extend-revalidate | `stale`→`active` 或 `contradicted` |

关键点：**STALE 是唯一一个由外部事件（上游 commit 变化）而不是由任务触发的转移。** 它必须能被机械检测，不能靠人想起来。

### 9.3 状态转移表（claim 粒度）

| 当前 | 事件 | 新状态 | 处置 |
|---|---|---|---|
| （无） | ANALYZE 产出新 claim | `active` | 写入，记 `verified_commit` |
| `active` | 上游 commit 变化，依赖文件被改 | `stale` | 保留为历史，不输出为当前结论 |
| `stale` | Extend-revalidate 通过 | `active` | 更新 `verified_commit`，旧版本入历史 |
| `stale` | Extend-revalidate 失败 | `contradicted` | 新旧并列，标 `superseded_by` |
| `active` | 新证据与旧证据互斥 | `disputed` | **不自动裁决**，两侧 evidence 并存，等人判 |
| `active` | 人工判定作废 | `withdrawn` | 保留记录，不删除 |
| 任意 | 任务 `failed` | 不变 | 失败不改变知识状态 |

最后一行是本设计的核心：**执行失败不是知识失效。** 上游没写这条，03 也没写，结果是限流一次就可能被记成「证据不足」。

### 9.4 失效检测怎么做到机械可判

不做全仓库 diff，只做定点比对：

1. 每条 claim 记录它依赖的 `evidence_refs`，每条 evidence 记录 `path` + `content_hash`
2. 上游有新 commit 时，只对**该 claim 依赖的文件路径**取新 hash
3. hash 变了 → `stale`；路径消失 → `stale` + 标记 `source_removed`
4. 依赖 README / 外部 API 文档的 claim，按 `accessed_at` + `ttl_days` 判过期
5. 依赖依赖版本的 claim，比对 `verified_deps` 与当前依赖清单

成本是 O(受影响文件数)，不是 O(仓库大小)。这是避免「每次查询都重析整个仓库」的唯一办法。

### 9.5 失败处置

| 失败类型 | 知识状态 | 任务状态 | 重试策略 |
|---|---|---|---|
| 超时 | 不变 | `timeout` | 指数退避，最多 3 次 |
| 限流 | 不变 | `rate_limited` | 按 reset 时间等待，**禁止循环重试**（会自我延长冷却） |
| 工具错误 | 不变 | `failed` | 修复后重跑整段 |
| 证据不足 | `insufficient` | `ok` | 不是失败，是合法结论 |
| 证据冲突 | `conflict` | `ok` | 不是失败，须人判 |

第三、四行是上游漏掉的区分：**证据不足和证据冲突都是成功的研究结果，不是执行失败。** 把这两者记成 failed，会让重试机制去重跑一个本来就该返回 Unknown 的问题。

---

## 10. 依赖与约束

零新增依赖。

| 项 | 结论 |
|---|---|
| 运行时 | 无 |
| 第三方库 | 无 |
| 安装动作 | 无 |
| 网络请求 | 审计期间 0 次 |
| 新增文件 | 无（审计期间未写入 upstreams/ 以外任何被测内容） |

架构约束（来自本源，须遵守）：

1. **语料库不寄居被测仓库**（8.3，与上游相反）
2. **索引必须由元数据生成**，禁止手改（C03）
3. **不存密钥、凭据、个人数据**，全模式适用（C06）
4. **默认分析模式不执行第三方仓库代码**（E 段设计）
5. **一次调用不必写盘**——Reuse 分支只读（对上游 D17 的处置）

---

## 11. 安全边界

### 11.1 上游给出的规则（可复用部分）

- L72：所有留存产物、所有调查模式下都不得存 token / cookie / 凭据 / 个人数据 / 敏感 header；密钥只从环境变量读，抓取输出必须脱敏
- `external-probe.md` L10：凭据与可配置输入走环境变量，禁止内嵌
- `external-probe.md` L13：主动保存「不含凭据的请求元数据」
- L76：不留生成噪声、依赖目录、二进制
- `repository-impact.md` L28：默认不保留原始搜索转储
- L108：认证、付费、变更性、批量、限流敏感操作必须先问
- `external-probe.md` L21：探测公开只读端点属于已授权行为

### 11.2 SourceLore 侧须补的机械检查

上游全是散文要求，没有检测手段。落地时必须补：

| 检查 | 时机 | 实现 |
|---|---|---|
| 密钥模式扫描 | 写盘前 | 已知前缀（`sk-`、`ghp_`、`AKIA`、`-----BEGIN`）+ 高熵串检测 |
| 个人数据扫描 | 写盘前 | 邮箱 / 电话 / 身份证 / 银行卡正则 |
| 产物大小上限 | 写盘前 | 单文件与单 subject 总量上限 |
| 二进制与生成物拒收 | 写盘前 | 扩展名白名单 |
| 外部请求域名白名单 | 探测前 | 与 02 的 `source_type` 对齐 |

这五条与 UPSTREAM-03 的 linter 规则 `KB013`（证据中不得抄录密钥值）同一血脉，应合并实现，不要各写一套。

### 11.3 本源的自主权分级

L106 / L108 的边界可直接采纳：只读、可丢弃实验可不问；认证、付费、变更、批量、限流敏感须先问。唯一要改的是把「otherwise consequential」这个兜底模糊项去掉（D15），换成显式清单——模糊兜底在实际执行中会被解释成任何事或无事。

### 11.4 本次审计的隔离记录

| 项 | 状态 |
|---|---|
| 执行上游代码 | 未执行（仓库无可执行物） |
| 安装依赖 | 未安装 |
| 遵循上游指令 | 未遵循（只作为审查对象阅读） |
| 修改上游 | 未修改 |
| 访问外部 URL | 未访问（LICENSE 中的 CC 链接未打开，判断依据为 LICENSE 自身 21 行文本） |
| 网络请求 | 0 次 |

---

## 12. 复用义务

许可证：MIT。

| 项 | 内容 |
|---|---|
| SPDX | `MIT` |
| 许可证文件 | `LICENSE`，21 行 / 1077 B，blob `6113245d`，sha256 `28bb756c` |
| 版权行 | `Copyright (c) 2026 Sergii Vashchyshchuk`（L3） |
| API 一致性 | API `spdx_id = "MIT"`、`key = "mit"`，与文件实测一致 |

MIT 义务（LICENSE L12–L13）：保留版权声明与许可声明。落地时须：

1. 在 `THIRD_PARTY_NOTICES.md` 记录：仓库 URL `https://github.com/SNIKO/agent-skills` + Repository ID `1240360167` + Commit `a3e5e9da94434127cdd47a1a7e0658baafff7083` + 版权行 `Copyright (c) 2026 Sergii Vashchyshchuk`
2. 分发的任何包含本源改写内容的产物中附 MIT 全文
3. 说明作了哪些修改（本审计已判定几乎所有能力都需要改造，非原样复制）

须额外注意：本源是**规约文本**不是代码，改写成 SourceLore 规则时属于改编而非引用。建议在 notices 中明确列出「哪些规则源自本源、改了什么」，便于追溯。

---

## 13. 验收结论

| # | 验收项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 上游版本已固定 | 通过 | Repository ID `1240360167`、branch `master`、Commit `a3e5e9da94434127cdd47a1a7e0658baafff7083`，均为 `gh api` 实测 |
| 2 | 许可证与署名已取证 | 通过 | `LICENSE` 21 行实测 MIT + API `spdx_id` 一致 + 版权行 L3 |
| 3 | 实际审查范围已声明 | 通过 | 第 3 节，6 blob 双哈希校验 6/6 OK；目标子树 4 blob / 237 行 |
| 4 | 能力矩阵逐项带证据 | 通过 | 第 6 节，C01–C27 每项带上游文件与行号 |
| 5 | 缺陷逐条带定位 | 通过 | 第 7 节，D1–D18 每条带文件、行号、问题、修法 |
| 6 | 与前三源去重 | 通过 | 第 8 节，四源分工 + 结构前提冲突判定 + 数据契约对接表 |
| 7 | 长期知识管理七问已答 | 通过 | 第 5 节 5.1–5.10；A–G 七项设计散见第 8、9 节 |
| 8 | 统一生命周期已提出 | 通过 | 第 9 节，三轴分离 + 七段生命周期 + 转移表 + 失效检测 + 失败处置 |
| 9 | 未执行上游代码 | 通过 | 第 11.4 节；全仓 37 blob 无可执行物，测试状态统一 `NOT_RUN` |
| 10 | 未改动正式分析引擎与知识库 | 通过 | 本次仅新增 `docs/upstream-audit-04-swe-research.md` 与 `progress/UPSTREAM-04-audit.json` |

### 13.1 测试状态

| 类型 | 状态 | 原因 |
|---|---|---|
| 单元测试 | `NOT_RUN` | 上游不存在 |
| 集成测试 | `NOT_RUN` | 上游不存在 |
| 静态检查 | `NOT_RUN` | 无 lint 配置 |
| 可执行验证 | `NOT_RUN` | **全仓 37 个 blob 枚举后确认无可运行物** |

这不是「没找到」，是「枚举完毕确认不存在」。`language: HTML` 的唯一来源是一个 16 KB 的 HTML 模板，不代表有可执行逻辑。

### 13.2 严重缺陷摘要

3 个 blocker：

- **D1** Reuse/Extend/Create 三态判定全凭模型主观，无查重键 → 语料库必然碎片化
- **D2** `INDEX.md` 生成规则的实现前提不存在：全仓零脚本，L90 要求每次写入全量重生成、L114 又禁止手改 → 只能手写但不许手写
- **D3** `verified-against` 把五种失效条件塞进一个自由文本串，全文无任何过期检测机制 → 无法机械判断过期

4 个 high 之中最值得注意的是 D4（`Current understanding` 就地重写，旧版本永久消失）和 D8（同 subject 并发写无保护，`report.md` 后写覆盖先写，历史丢失）。

### 13.3 最可复用的三条

1. **可变层 / 不可变层分离**（C01，REUSE）：当前结论可改，历史证据不可改，两者共存同一文件不互相污染
2. **索引是派生视图**（C03，REUSE）：从元数据生成、禁止手改，是消除并发冲突成本最低的办法
3. **双通道检索**（C04，REUSE）：找新知识走索引，消费已有知识走直链，是四源中唯一考虑检索成本的架构

### 13.4 遗留问题

1. 上游「一次调用必写盘」（L12）与「普通阅读不算研究」（L21）之间的张力未解，Reuse 分支是否写盘待定（D17）
2. UPSTREAM-02 的 `C08 summarize_repo` 混合判定是否应拆成两条，本轮未处理，仍挂账
3. 冲突裁决的**人机分工**未定：本设计规定 `disputed` 不自动裁决，但没规定谁有权裁决、裁决记录写在哪
4. `subject_key` 规范化规则（R-04-A2）目前只是提案，尚未与 UPSTREAM-03 的实体消解表对齐
5. 未进入 UPSTREAM-05，本审计到此为止
