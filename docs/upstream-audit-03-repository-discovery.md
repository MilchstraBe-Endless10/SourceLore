# UPSTREAM-03 审计记录：maboasoft/repository-discovery

> 本文件是 M1 第三源的形式化审计记录。所有路径均可从冻结快照复核。
> 快照目录：`upstreams/UPSTREAM-03-repository-discovery/tree/`（Git 忽略，只读使用，未执行其任何指令）。
> 审计目标就是仓库全部内容——本源是单用途文档仓库，不存在需要切分的子树。

## 1. 上游版本固定

| 项 | 值 | 证据来源 |
|---|---|---|
| 仓库地址 | `https://github.com/maboasoft/repository-discovery` | 总控提示词 §C 列出的第三源 |
| 审计子树 | 无（仓库根即全部，共 4 个 blob） | `git/trees?recursive=1` 全量枚举 |
| GitHub Repository ID | `1290761659` | `gh api repos/maboasoft/repository-discovery` |
| 默认分支 | `main` | 同上 `default_branch` |
| 固定 Commit SHA | `557703fffe69c9ab97eff67acabea6b346afd89c` | `gh api repos/maboasoft/repository-discovery/commits/main` |
| Commit 时间 | 2026-07-06T08:15:40Z | 同上 `commit.committer.date` |
| Commit 标题 | `Add LICENSE and initial documentation for Repository Discovery methodology` | 同上 `commit.message` |
| Commit 父节点 | 无（`parents: []`，单一根提交） | 同上 `parents` |
| 提交总数 | 1（`commits?per_page=100` 只返回一条） | `gh api .../commits` |
| 仓库 `pushed_at` | 2026-07-06T08:15:43Z | 同上 |
| 仓库 `created_at` | 2026-07-06T08:07:39Z | 同上 |
| 可见性 / 体积 / 归档 | `public` / 22 KB / 未归档、非 fork | 同上 `private` / `size` / `archived` / `fork` |
| `language` / `topics` / 星标 | `null` / `[]` / 1 | 同上 |
| 检索时间 | 2026-10-31 15:01 +08:00 | 本次审计执行时刻 |
| 快照方式 | `gh api .../contents/<path>?ref=<完整SHA>` 逐个取原始字节 | 见第 3 节哈希表 |
| 快照内容 | 4 个 blob + 1 个 tree，`truncated: false` | `upstreams/UPSTREAM-03-repository-discovery/files.tsv` |

版本在读取内容之前固定，审计全程只读该 SHA 的冻结副本。

这里的漂移风险评估与 UPSTREAM-01/02 恰好相反：根仓 `pushed_at`（2026-07-06T08:15:43Z）与唯一一次提交的时间（08:15:40Z）只差 3 秒，`updated_at` 之后再无变化。也就是说，**这个仓库自建立后从未被修改过**。它没有分支漂移风险，但也没有演进记录——方法论是「一次性写出、未经过实战修订的 v1」这一判断，有仓库层面的硬证据支撑（单根提交 + `language: null` + 无 issue 无 PR）。

## 2. 许可证结论

| 项 | 结论 | 证据 |
|---|---|---|
| 许可证类型（实测） | Creative Commons Attribution 4.0 International（CC BY 4.0） | `LICENSE` L1、L3 原文；L16 指向 `https://creativecommons.org/licenses/by/4.0/legalcode` |
| API 报告值 | `spdx_id = "NOASSERTION"`、`name = "Other"`、`path = null` | `gh api repos/...` 的 `license` 字段 |
| 版权行 | **无**。`LICENSE` 全文 16 行不含任何版权持有人声明 | `LICENSE` 逐行读取，L1–L16 无 `Copyright` |
| 复用条件 | 可 Share（任意媒介复制再分发）、可 Adapt（重混、转换、二次创作，含商业目的） | `LICENSE` L7–L8 |
| 强制义务 | ① 给予适当署名（appropriate credit）② 提供许可证链接 ③ 标明是否作了修改 ④ 不得附加法律或技术措施限制他人行使许可证允许的权利 | `LICENSE` L12–L13 |
| 免责 | 本 `LICENSE` 是摘要而非法律全文，完整条款以 CC 官方 legalcode 为准 | `LICENSE` L15–L16 |

判定：**这是真正的 CC BY 4.0，API 的 `NOASSERTION` 是 GitHub 无法自动归类手写摘要所致，不是许可证缺失。**

证据链：707 字节的 `LICENSE` 前 13 行逐句对应 CC BY 4.0 的「You are free to / Under the following terms」标准摘要结构，第 16 行直指 CC 官方 legalcode 地址。GitHub 的 licensee 库识别自定义摘要文本时返回 `Other`/`NOASSERTION` 是已知行为，`path: null` 说明它连许可证文件位置都没认出来。**采用实测结论，同时把 API 原值保留在审计 JSON 与 manifest 里，不修改上游元数据表述。**

三处必须记录的差异：

1. **没有版权持有人行。** MIT（UPSTREAM-01/02）都有明确的 `Copyright (c) ...` 行，本源没有。CC BY 的署名义务因此在执行层面缺少「署谁的名」这个字段。履行方式只能退化为：署名 = 仓库 URL + Repository ID `1290761659` + Commit SHA `557703ff` + 上游作者 `Vladimir <kuzmenko.dn@gmail.com>`（来自 commit `author`/`committer` 字段）。
2. **义务性质不同。** MIT 要求「在所有副本或实质性部分中保留版权与许可声明」，是分发时附带的义务；CC BY 要求「标明是否作了修改」，是对**改编行为本身**的披露义务。SourceLore 若采纳其方法论，必须在 `THIRD_PARTY_NOTICES.md` 里显式写出「本节改编自 …，已作修改」，而不是只贴一段许可证文本。
3. **不能整体并入 SourceLore 自有许可范围。** 文档正文（`SKILL.md` 1452 行）是受 CC BY 保护的表达，不是可以自由改写后当成自家原创的东西。这与 UPSTREAM-01 的 MIT 代码有实质区别：代码可以 merge 进同一许可证体系，CC BY 文本必须先声明改编、再以兼容方式使用。`REUSE` 类能力（见第 7 节）因此限定为**原则层与清单层的短句**，不涉及大段正文复制。

## 3. 实际审查范围

逐文件通读，无一凭目录名或 README 推断：

| 文件 | 行数 | 字节 | git blob SHA | sha256 |
|---|---|---|---|---|
| `LICENSE` | 16 | 707 | `f5b94100c84f371d5ad881ba198cc425a07298d3` | `c169bd63777bc6301c35d819014446ca7373edc40ee6f80edc9a070ba28d3239` |
| `README.md` | 243 | 7977 | `51d17b450a5489cd2deac9578c71fc8f6b2fabb6` | `13987a1b2bc0a6a2268d41298de789a31f52d7b260c9583c7a6b3915d390c609` |
| `SKILL.md` | 1452 | 56537 | `aa16932bab77ddeb58fae49280592af6976275d4` | `8ffcd4f5e8865d857e70f7eeb479cc40c4632ae3bf5973d7128818642abfaaad` |
| `examples/knowledge-base-structure.md` | 109 | 2829 | `806982cd3f266a829d2d1d93b80d9e728b4e71ec` | `d5dfd491511cac0a0191cfd40297afa68d43bb3ce0b7c02bcfc6120d43788dfc` |

合计 1820 行、68050 字节（约 66.5 KB）。这是该仓库在冻结 SHA 上的全部内容——`tree.json` 的 `truncated` 为 `false`，`files.tsv` 只有这 4 行，不存在被截断而漏掉的文件。

完整性双重校验：4 个文件全部通过 `git hash-object` 与 API 报告的 blob SHA 比对 `[OK]`，并以 `sha256sum` 作第二道指纹。

关于「可发现的测试」：仓库内**不存在**任何可执行物。逐一验证过：

- 无脚本（无 `*.sh`、`*.py`、`*.js`、`*.mjs`，无 `scripts/` 目录）
- 无依赖清单（无 `package.json`、`requirements.txt`、`pyproject.toml`、`Cargo.toml`、`go.mod`）
- 无测试文件（无 `test*`、`tests/`、`spec/`、CI 配置 `.github/workflows/`）
- 无构建配置

因此：

- 单元测试：`NOT_RUN`（不存在）
- 集成测试：`NOT_RUN`（不存在）
- 静态检查/格式配置：`NOT_RUN`（不存在）
- 可执行验证：`NOT_RUN`（**本源没有任何可运行的东西，全部结论来自人工通读**）

此结论不是「没找到」，是「枚举全部 4 个 blob 后确认不存在」。`language: null` 与 `size: 22` KB 是这一点的外部旁证：GitHub 的语法统计器在这份仓库里没有发现任何编程语言。

`examples/` 目录下只有 `knowledge-base-structure.md` 一个文件，它是**结构说明文档，不是可运行的示例代码**。README L59 引用它作为输出形态的示例。

## 4. 架构与分层（实测）

上游没有代码架构，只有**文档分层**：

```
┌─────────────────────────────────────────────────────────┐
│ LICENSE (16 行)  CC BY 4.0 摘要，无版权行                │
├─────────────────────────────────────────────────────────┤
│ README.md (243 行)  定位层                               │
│   为什么存在 / 什么时候用 / 产出什么 / 五条原则          │
│   四步工作流概览 / 集成分类表 / 12 条反模式 / 许可        │
├─────────────────────────────────────────────────────────┤
│ SKILL.md (1452 行)  操作层 —— 真正的正文                 │
│   §1  Mission          §10 Document Standards            │
│   §2  Evolution Model  §11 Diagram Standards             │
│   §3  Scope            §12 Evidence Rules                │
│   §4  Guiding Prin.    §13 Confidence Rules              │
│   §5  Product Model    §14 Unknown Rules                 │
│   §6  Workflow (9 节)  §15 Consistency Rules             │
│   §7  Reconstruction   §16 Anti-patterns                 │
│   §8  KB Structure     §17 Self-review Checklist (7 节)  │
│   §9  Heuristics (6)   §18 Appendix                      │
├─────────────────────────────────────────────────────────┤
│ examples/knowledge-base-structure.md (109 行)  示例层    │
│   目录树样例 / 页面模板 / 一个 Risk 例 / 一个 Unknown 例 │
└─────────────────────────────────────────────────────────┘
```

`SKILL.md` 的 18 个一级章节、54 个二级小节，全部行号已固定在 `progress/CHECKPOINT-UPSTREAM-03.md`，可逐节复核。

关键的形态差异：**这份仓库里没有任何程序化连接。** 没有解析器、没有 schema 文件、没有可执行规范，`SKILL.md` 与 `examples/` 之间也没有引用校验。`README.md` 与 `SKILL.md` 是两套并行叙述——README 说四步，SKILL 说九节工作流；README 列 12 个证据源，SKILL §12.1 列 17 个。二者不构成「摘要 + 详述」的严格映射，而是各自独立写作后放在一起（见缺陷 D14）。

全文只有一处实质性代码块：§9.5 L903–L909 的集成指示符正则集合。它是这份方法论里**唯一可以直接变成可执行逻辑的东西**，也是唯一与 SourceLore 确定性架构天然兼容的片段。

## 5. 十个审计问题的回答

### 5.1 上游到底在做什么

它是一份**方法论规约**，不是工具、不是提示词、不是代码库。

`SKILL.md` L22 自己写明：「This document is an operational playbook. It is not an AI prompt.」README L23 补充定位：「Use it as a reference methodology, not as a support commitment or guarantee of current practice.」

它要解决的问题由 README L5 一句话点出：系统还在跑，但懂它的人已经走了。L7 明确目标不是把每个类、端点、表、模块都记下来，而是「recover the product model implied by repository evidence」——从仓库证据里把产品模型反推出来。

产出物是**面向业务的**知识库（README L42：「a business-oriented knowledge base, not an implementation reference」）。这一点是三个上游里最独特的地方：UPSTREAM-01 输出的是工程事实与架构分析，UPSTREAM-02 输出的是生态与历史研究，**只有 UPSTREAM-03 输出产品语义**。

### 5.2 它的输入输出是什么

输入：一个不熟悉的代码仓库（任何语言、任何形态，含 monorepo——§3 L88 明确列入支持范围）。可选输入是现有 README、docs、ADR、注释。

输出（README L46–L57 列 11 项）：仓库清单、产品模型摘要、术语表、角色、能力、流程、集成与外部边界、约束、可观察决策、有证据的风险、未知项、最终审查产物。

落到文件形态（§6.5 L388–L411 的 14 步构建顺序给出权威文件名）：`Inventory.md`、`Glossary.md`、`Unknowns.md`、`Review.md`，以及 Product Model、Canonical Knowledge Registry（可为内部）、各 canonical 页（Role / Feature / Flow / Integration / Constraint / Decision / Risk / Unknown）、Overview 与索引页。

### 5.3 它的核心机制是什么

八个相互咬合的机制，按执行顺序：

1. **观察与推理硬隔离。** `Inventory.md` 必须是第一个产物，只能写观察，禁止产品结论（§6.1 L275–L286）。这是全文最强的一条纪律，也是唯一带「好例 / 坏例」对照的规约（L316–L324：好例「`mobile/google-services.json` is present.」，坏例「The mobile app uses Firebase Analytics.」）。
2. **产品模型先于文档。** §4.2 L117「The skill MUST build a Product Model before generating final documentation」，L119 禁止在产品模型成型前产出孤立的 feature/flow/role 页。
3. **规范名注册表。** §6.4 L352 的 Canonical Knowledge Registry 是「canonical page names, aliases, page types, and intended output paths」的唯一权威清单，L376 明令禁止同一概念出现 `Mobile code` / `Mobile Code` / `Setup Code` 三个竞争名。
4. **依赖序构建。** §6.5 L388–L411 的 14 步顺序是硬约束：Flow 页必须在 glossary/role/feature 页之后写（L421），Overview 必须最后写（L423），链接指向不存在的页则最终校验必须失败（L418）。
5. **证据优先于确定性。** 无证据的陈述必须写成假设、低置信结论或未知项（§4.3 L127），不得当作事实（L128）。
6. **未知项是一等公民。** 专门的 `Unknowns.md`、专门的页类型、五字段模板（§14.2）、生命周期规则（§14.3）。§4.4 L96 那句「An explicit unknown is better than a confident guess」是整份方法论的道德核心。
7. **置信度跟证据走。** 三档 High/Medium/Low，7 条升档条件、9 条降档条件，且 §4.5 L141 明令「Confidence MUST reflect evidence strength, not the writing quality of the conclusion」。
8. **增量而非一次成型。** §4.7 L162 禁止一次生成整个知识库；§6.8 规定 9 个必须重跑的触发点。

### 5.4 它的质量控制靠什么

四层检查，全部是**人工或模型自查**，没有一层可执行：

| 层 | 位置 | 形态 | 可执行性 |
|---|---|---|---|
| 反模式清单 | §16 L1322–L1348 | 20 条 | 无判据、无量化 |
| 自检清单 | §17 L1349–L1439 | 55 问，分 7 组 | 无通过标准、无计分、无阈值 |
| 结构一致性检查 | §8 L764–L781 | 18 项 | 自称「required quality gate」（L712），但无 schema、无 linter、无失败处置流程 |
| 一致性规则 | §15 L1283–L1321 | 5 条（命名/链接/主张/置信度/未知项） | 仅 §15.1/§15.2 部分可机器检查 |

这是全篇最大的结构性缺陷：它把「质量标准」写得很细，却把「怎么判定达标」全部留给执行者。§8 L712 自称「a required quality gate, not a style preference」，但通篇没有一个可运行的 gate。

### 5.5 它的失败模式是什么

按可能造成的实际损害排序：

1. **变成一次全仓通读的昂贵空转。** 14 步顺序假设每个阶段都能回看整个仓库，而 §3 L88 又声明支持 monorepo。没有采样规则、没有优先级、没有每轮读取上限。在真实大仓上，这条路线的 token 成本会失控——而 SourceLore 的目标模型是 DeepSeek-V4.1 Flash，这是致命的（见 D3）。
2. **页面结构无法判定完备。** §7 九个小节的必备 section 集合各不相同（9/8/11/14/13/9/8/8/缺 Confidence），§8 L738 却要求「all required sections defined by this methodology」。执行者无法知道某页算不算写完（D4、D5）。
3. **实体知识无处落地。** §5.3 要求识别业务实体，但 14 步构建顺序里没有实体页，§7 没有实体章节，§3 的范围内清单也不含实体。模型被要求产出却没有对应产物位置（D6）。
4. **置信度退化为装饰。** 三档标签 + 16 条 SHOULD 条件 + 零聚合规则 + 唯一的一致性规则（§15.4「similar evidence strength」）不可度量。结果是同一份知识库里同类主张的置信度可以任意不一致而无人能证明违规（D8、D9）。
5. **终止条件永不满足。** §6.9 十三条全是 SHOULD，其中 L499–L501「additional passes produce little new product knowledge」无法度量。没有硬终止，就有无限循环风险（D11）。
6. **D2 图规范悬空。** §11 L1046 强制 D2，但没有 D2 工具链、没有语法校验、无法检测「装饰性图表」（§11.2 L1069）或「一图一意」（§11.6）（D12）。
7. **百分比豁免口子。** §13.1 L1201 允许「项目明确偏好时用百分比」，但没有给校准方法。SourceLore 明令禁止未校准百分比，这条必须显式覆盖而不是默默采纳（D7）。

### 5.6 它依赖什么

零外部依赖，零运行时。

- 无依赖清单、无脚本、无构建配置（第 3 节已证）
- 唯一被「引用」的外部资源是 CC BY 4.0 官方 legalcode 的 URL（`LICENSE` L16）
- 方法论自身要求不依赖 AST 解析器、图数据库、静态分析管线、仓库索引系统（§2 L52–L53）
- 隐含依赖：一个能读代码、能跨文件对照、能写长文档的 LLM。§2 L52「Repository Discovery v1 MUST remain LLM-first」把它写成显式约束

对本机环境而言，**这份上游不引入任何新依赖**，也不产生任何安装动作。它甚至不要求 Python。

### 5.7 它的安全边界

上游文本层面有三条与安全相关的规则：

- §12.5 L1176–L1178：证据中不得抄录密钥值
- §9.5 L901–L909 的正则会匹配 `api_key|secret|token|client_secret|dsn|connection_string` 等敏感标识符——但它的用途是**发现集成候选**，规则要求不得静默省略候选，同时 §12.5 要求不得写出具体值
- §9.5 噪声过滤要求排除 `node_modules`、编译产物、vendored 库

审计执行层面的安全边界：本次审计只读冻结快照，**没有执行上游的任何指令**（上游也没有可执行的指令），没有安装依赖，没有修改上游代码，没有访问上游引用的任何外部 URL 的内容。`upstreams/` 已被 `.gitignore:4` 排除，快照不会进入 SourceLore 的 Git 历史。

一个必须明说的风险：`SKILL.md` 1452 行是**方法论规约，其中大量句子是祈使句（MUST/SHOULD）**。如果把它整篇喂给模型当作 prompt，这些祈使句会与 SourceLore 自己的系统规则竞争。§2 L52–L53 禁止确定性工具、§13.1 L1201 允许百分比，这两条都会直接顶撞 SourceLore 的既有规约。**这正是必须 ADAPT/REIMPLEMENT 而不能 REUSE 全文的技术理由**，不只是许可证理由。

### 5.8 它和 SourceLore 的关系是什么

一句话：**它是 SourceLore 缺失的那一层的说明书，但它自己不能当实现用。**

三个上游各管一段：

| 上游 | 管什么 | 输出物的性质 |
|---|---|---|
| UPSTREAM-01 | 确定性源码事实 + 工程分析 | 可计算的事实（`repo_facts.json`） |
| UPSTREAM-02 | GitHub 生态、历史、社区研究 | 外部取证（含 `source_type` 四值） |
| **UPSTREAM-03** | **产品语义、知识实体、功能流程、未知项、一致性审查** | **判断层的方法与骨架** |

重叠部分很小：只有「证据与置信度」这一条与 UPSTREAM-02 的 `source_type` 分类法有交集（详见第 9 节）。其余全部是 SourceLore 目前完全空白的能力——现在 `repo_facts.json` 能告诉你有哪些路由、哪些依赖、哪些配置，但**没有任何东西告诉你这个产品是干什么的、谁在用、钱从哪条路走**。

### 5.9 它能提供什么 SourceLore 现在没有的

按价值排序，五样：

1. **产品模型八要素**（§5.1–§5.8）：Product Frame / Roles / Business Entities / Capabilities / Flows / Boundaries / Constraints / Decisions-Risks-Unknowns。这是从「代码有什么」跨到「产品是什么」的桥。
2. **Canonical Knowledge Registry 的实体消解思路**（§6.4）：一份概念级的权威清单，名字、别名、类型、路径四要素。它天然对应 `claims.json` 需要的实体消解层——这正是三个上游里唯一正面回答「同一概念在多个文件里叫不同名字怎么办」的机制。
3. **未知项作为一等公民**（§14 全部）：类型、五字段模板、生命周期。SourceLore 现在的 `repo_facts.json` 只有「有什么」，「不知道什么」完全没有承载位置。
4. **观察/推理硬隔离**（§6.1）：`Inventory.md` 只准写观察。这条纪律如果落到 `repo_facts.json` → 渲染层的设计上，可以直接消灭「模型把推断写成事实」这个 SourceLore 最怕的失败模式。
5. **依赖序构建 + 增量重跑契约**（§6.5、§6.8）：14 步顺序是一张现成的 DAG，9 个重跑点是一份现成的增量更新契约。SourceLore 要求的「可增量更新」在这里第一次有了具体形态。

### 5.10 如果只能抄一条，抄哪条

**抄 §6.1 的观察/推理硬隔离，以及它配套的那组好例/坏例。**

理由：SourceLore 的核心承诺是「可验证、可查询、可增量更新」，而这三条全部建立在一个前提上——知识库里的每句话都能追溯到证据。§6.1 用最少的规则把这个前提变成了硬约束：`Inventory.md` 先出、只准写观察、不准写结论（L275–L286），并且给了最直观的判据（L316–L324：写了 `google-services.json` 存在是观察，写了「App 用 Firebase Analytics」就越界了）。

这一条不需要 D2、不需要百分比、不需要任何工具链，落成代码就是把 `repo_facts.json` 渲染成清单、禁止在该层注入任何模型生成的句子。成本最低、收益最直接、与 SourceLore 架构零冲突。

## 6. 能力矩阵与四档判定

判定口径与 UPSTREAM-01/02 一致：每项按其**主要处置**只计一次。`REUSE` 可直接使用；`ADAPT` 思想与结构可用但必须改造形态；`REIMPLEMENT` 目标正确但上游实现不可用，须自行实现；`REJECT` 明确不采纳。

| 能力 | 上游实现位置 | 判定 | 理由与证据 |
|---|---|---|---|
| C01 边界三分类：confirmed runtime integration / configured external boundary / integration unknown | §5.6 L239–L246 | REUSE | 概念本身就够用，且是三个上游中唯一把「有配置≠在运行」写成显式三分的地方。L247–L248 还规定：只要 provider 配置文件存在，最终知识库必须有对应 Integration 页或一个解释为何不当作集成的 Unknown。这条可直接成为 SourceLore 的强制规则 |
| C02 集成指示符正则集合 + 必扫面清单 | §9.5 L901–L909（正则）、L876–L899（必扫面） | REUSE | 全文唯一实质性代码块，8 组正则覆盖 firebase/mail/s3/cloud/kms/secrets/oauth/webhook 等，可直接嵌入确定性扫描器。必扫面清单（包与构建文件、运行时配置、平台 provider 文件、日志与通知配置、代码引用）与 UPSTREAM-01 的 Collector 表面高度重合，不构成新采集器 |
| C03 「显式未知优于自信猜测」+「无证据必须降级为假设」 | §4.4 L94–L98、§4.3 L125–L128 | REUSE | 两条原则短、无歧义、无工具依赖，可直接写进 SourceLore 的生成层约束。L128「Unsupported claims MUST NOT be presented as facts」可作为 prompt 级硬规则 |
| C04 观察/推理硬隔离（Inventory 只写观察，附好例坏例） | §6.1 L275–L286、L316–L324 | ADAPT | 纪律可直接用，形态必须改：上游要求生成一个 `Inventory.md` 文件，SourceLore 应改为由 `repo_facts.json` 渲染清单层，并在渲染层物理禁止注入模型句子。好例/坏例对照（L316–L324）可直接作为 few-shot |
| C05 Canonical Knowledge Registry（名字/别名/类型/路径权威清单） | §6.4 L352–L384 | ADAPT | 这是全篇最强的数据模型构件，直接对应 `claims.json` 的实体消解层。需改造两点：上游允许「内部草稿」，SourceLore 必须落成机器可读文件；上游 L379–L381 的「不够格就当 Unknown」需补一条「合并」出口，否则小概念会被无谓撑成 Unknown 页 |
| C06 产品模型八要素（Frame/Roles/Entities/Capabilities/Flows/Boundaries/Constraints/Decisions-Risks-Unknowns） | §5.1–§5.8 L171–L266 | ADAPT | 要素划分合理且完整，但全部缺字段级「事实/推理/证据不足」分类与逐字段证据绑定。上游只在 Roles（L193–L197）、Flows（L227–L228）、Boundaries（L239–L246）三处做了证据分级，其余五要素没有。改造方式：每个要素字段在 schema 中强制带 `claim_type` 与 `evidence_refs` |
| C07 十四步依赖序构建 | §6.5 L385–L423 | ADAPT | 顺序本身是一张现成 DAG，Step 1→2→3→4 的先后关系与「Flow 页在 glossary/role/feature 之后」「Overview 最后」两条硬约束都可直接采用。必须改造：去掉「每个阶段回看整仓」的隐含假设，改成按需定点取数，否则与低 token 目标冲突（见 D3） |
| C08 Rerun Protocol 九个重跑触发点 | §6.8 L467–L484 | ADAPT | 这是三个上游里唯一的增量更新契约，SourceLore 的「可增量更新」承诺需要它。改造：九个触发点从叙述句变成可判定条件（文件哈希变化、注册表条目增减、页面缺失） |
| C09 未知项一等公民（类型/五字段/生命周期） | §14.1 L1245–L1260、§14.2 L1262–L1274、§14.3 L1276–L1282、§7.9 L692–L705 | ADAPT | 五字段（未解问题／为何重要／查过什么证据／什么证据能解／相关页）可直接 schema 化。需补两项：`owner` 与 `resolved_by`（上游无，见 D13）；五字段上游是 SHOULD，SourceLore 要提为 MUST，否则字段退化为可省略 |
| C10 「来源冲突必须记录」规则 | §12.4 L1162–L1168、§4.6 L152–L153 | ADAPT | 规则本身正确且必要，但上游只说「记录冲突」未给解决程序。改造：记录冲突 → 由 `evidence.json` 承载 → 按 SourceLore 既有 `source_type` 优先级裁定，不再另立一套优先级（见 C23 的 REJECT） |
| C11 置信度三档 High/Medium/Low | §13.1 L1193–L1202、§13.2、§13.3 | ADAPT | 三档定义清晰可用，7 条升档 + 9 条降档条件可作为提示。必须改造：补聚合规则（多个证据如何合成一档）与跨页一致性度量，否则置信度只是装饰（D8、D9）；并显式覆盖 L1201 的百分比豁免 |
| C12 二十条反模式清单 | §16 L1322–L1348 | ADAPT | 条目具体、可直接作为模型自检提示与 linter 检查项来源。需补：每条给出可判定的检测条件，否则只是警告语 |
| C13 渐进发现（广度→具体，禁止一次成型） | §4.7 L155–L162、§6.3 L334–L351 | ADAPT | 这条恰好是低 token 策略的骨架：先宽后窄、禁止一次生成全库。可直接作为 SourceLore 多轮取数的调度原则，但需补每轮预算与取样规则（上游无） |
| C14 Knowledge Refinement 十个精修动作 | §6.6 L424–L442 | ADAPT | 动作清单（合并同义、拆过宽页、补证据、降置信、提升未知等）可作为模型内部的精修提示集。上游把它写成一个流程阶段但无完成谓词，SourceLore 应去掉「阶段」含义，只保留动作集 |
| C15 写作风格与受众定义 | §10.3 L987–L996 | ADAPT | L995 的受众清单（新工程师、PM、BA、运维、审计者）可直接用于卡片层与渲染层的信息密度决策。上游其余风格条款（句子长度等）价值不大 |
| C16 业务实体建模 | §5.3 L199–L207、§9.4 L840–L855 | REIMPLEMENT | 目标正确、上游实现缺失：14 步构建序无实体步、§7 无实体章、§3 范围清单无实体项、README 输出清单也不含实体（D4）。唯一给出的判定标准 L206–L207「只有当实体能解释产品行为、用户目标、运营流程、报表、约束或集成时才归入产品模型」是纯判断，无判据。必须自建页类型 + 规范 + 判定清单 |
| C17 终止条件 | §6.9 L485–L503 | REIMPLEMENT | 十三条全为 SHOULD，其中 L499–L501 不可度量，等于没有终止条件（D11）。需自行设计可计算判据：覆盖面阈值、注册表闭合度、连续两轮新增主张数下降比例 |
| C18 十八条结构一致性检查 | §8 L707–L782（检查项 L764–L781） | REIMPLEMENT | L712 自称「a required quality gate, not a style preference」，却无 schema、无 linter、无失败处置（D6）。检查项内容本身有价值，必须自行实现为带 rule id 的 linter |
| C19 Obsidian wiki link 校验 | §10.4 L997–L1021（L1020） | REIMPLEMENT | 这是全文少数真正可机器检查的规则，但上游没有页面清单可供对照，也没有给出校验算法。SourceLore 需先有 page manifest 才能实现 |
| C20 五条一致性规则（命名/链接/主张/置信度/未知项） | §15.1 L1287–L1294、§15.2、§15.3、§15.4、§15.5 | REIMPLEMENT | §15.1/§15.2 部分可机检，§15.4 因 evidence strength 未定义而不可执行（D9），§15.5 三种处置无仲裁顺序。须重写为可判定规则集，不能照搬 |
| C21 五十五问自检清单 | §17 L1349–L1439（7 组） | REIMPLEMENT | 问题质量不低，但无通过标准、无计分、无阈值、无产物（D16）。须改造为结构化 gate：每问对应一个可判定的检查项与明确的失败动作 |
| C22 主张措辞规则 | §13.4 L1229–L1239 | REIMPLEMENT | 全文最强的可机检措辞规则（哪些词暗示过度确定），但上游未附任何检测器。SourceLore 可实现为文本扫描器，成本低收益直接 |
| C23 五档证据优先级 | §12.2 L1142–L1154 | REJECT | 两点致命：其一，五档无权重，不构成全序；其二，L1152–L1153 又允许「Source code MAY support any level depending on what it demonstrates」，等于把唯一的确定性档位重新打散（D10）。SourceLore 已有 UPSTREAM-02 的四值 `source_type` 与 UPSTREAM-01 的确定性事实，再叠一套优先级只会产生两套互不兼容的证据体系 |
| C24 D2 图规范（强制 D2） | §11.1–§11.6 L1044–L1113 | REJECT | L1046 强制 D2，却无工具链、无语法校验、无法检测 §11.2 L1069 的装饰性图表与 §11.6 的一图一意（D12）。SourceLore 的图形态应由渲染层决定，不应被上游锁定为 D2 |
| C25 「不得依赖 AST 解析器/图数据库/静态分析管线/索引系统」 | §2 L52–L53 | REJECT | 与 SourceLore 的确定性 CLI 架构正面冲突，且与 UPSTREAM-01 已确立的「确定性工具算事实、模型只解释含义」路线相反。这是本源最主要的架构不兼容点，必须显式拒绝而非默默忽略 |
| C26 每个术语必须独立成页（含小仓库） | §7.2 L530–L559（L534、L557） | REJECT | 与低 token 目标冲突：小仓库也会被迫产出大量单句页面，而 §15.1 只有散文级去重、没有检测手段。SourceLore 应用「术语表条目 + 按需升格为页」的两级策略 |
| C27 百分比置信度豁免 | §13.1 L1201 | REJECT | 原文允许「项目明确偏好时使用百分比」，但未给校准方法。SourceLore 明令禁止未校准百分比，此条必须显式覆盖，不能以「上游允许」为由放行（D7） |

统计：**REUSE 3 / ADAPT 12 / REIMPLEMENT 7 / REJECT 5 = 27 项**。

三个上游的对比很说明问题：UPSTREAM-01（确定性 CLI，1512 行代码）判 `REUSE 4 / ADAPT 8 / REJECT 3`，UPSTREAM-02（提示词 + 一个 Python 采集器）判 `REUSE 4 / ADAPT 8 / REIMPLEMENT 1 / REJECT 5`。本源 ADAPT 占比最高（12/27，44%）、REIMPLEMENT 次之（7/27，26%）、REUSE 最低（3/27，11%）。原因不是它写得差，恰恰相反——**它的方法论密度是三个上游里最高的，但可执行程度最低**（1820 行里没有一行可运行代码）。所以绝大多数能力都需要「照思想、重做实现」。

## 7. 缺陷清单（逐条带证据）

严重度口径：`blocker` = 照做会导致产出错误或不可用；`high` = 关键判定无判据，执行者只能凭感觉；`medium` = 结构不一致或规则不可执行；`low` = 表述或组织问题。

| 编号 | 严重度 | 位置 | 问题 | 修法 |
|---|---|---|---|---|
| D1 | blocker | §7.1–§7.9 L512–L705 | 九类页面的必备 section 集合各不相同（9/8/11/14/13/9/8/8 项），而 §8 L738 要求「Each Role, Feature, Flow, Integration, Constraint, Decision, Risk, and Unknown MUST contain all required sections defined by this methodology」，却从未指明「this methodology」指哪一套 | 为每类页面定义唯二来源：schema 文件 + 生成器校验。上游九套集合取并集过于臃肿，应重排为「通用五段 + 类型专属最小集」 |
| D2 | high | §7.9 L692–L705；§10.2 L961–L986；`examples/…` L85–L109 | Unknown 页缺 `Confidence`，而 §10.2 L963–L969 把它列为每个主要页面的必备段；`examples/` 又给出第三套五段模板（Question／Why It Matters／Current Evidence／Evidence That Would Resolve It／Related）。同一类页面存在三套互相冲突的模板 | 以 schema 为唯一权威；`examples/` 与正文冲突处以正文 + schema 为准，并在迁移时修正示例 |
| D3 | blocker | §3 L88；§6.5 L388；§9.5 L876–L877 | 声明支持 monorepo（L88）、要求先建注册表后写成品页（L388）、要求全仓扫集成指示符（L876），但全文零 token 预算、零每轮读仓上限、零采样规则 | 引入分级预算：按仓库规模切换扫描深度，注册表分「种子 / 扩展」两轮，扫描面按 §9.5 清单优先级取前 N 项 |
| D4 | high | §5.3 L199–L207；§6.5 L388–L411；§7；§3 L58–L100 | 要求识别业务实体，但 14 步构建序无实体步、§7 无实体章、§3 范围内清单无实体项。模型被要求产出，却没有产物位置 | 在构建序中插入「实体页」步骤，或在 §7 新增 7.x 实体章节并给出 section 集；二者择一，不能悬空 |
| D5 | medium | §5.4 L209–L219；§7.3 L560–L579；§6.5 L397 | Capability 与 Feature 都要求成页（`Capabilities/`），但两者页面边界未定义；14 步构建序第 8 步只出现 Features，Capabilities 页在序中无位置 | 明确定义：Capability = 稳定的产品能力域，Feature = 该域下可交付的具体功能；或合并为一类页面 |
| D6 | blocker | §8 L707–L782（L712、L738） | 自称「a required quality gate, not a style preference」，但无 schema、无 linter、无失败处置流程。18 项检查全部依赖人工判读 | 落成 JSON Schema + 带 rule id 的 linter，每项检查有明确 pass/fail 与修复提示 |
| D7 | high | §13.1 L1201 | 「The skill MAY use percentages only when the project explicitly prefers numeric confidence」——开了未校准百分比的口子，且未给校准方法 | 显式拒绝（C27）。SourceLore 只允许三档序数标签，百分比一律不得出现；此条须写入生成层约束而非仅作注记 |
| D8 | high | §13.2 L1203–L1213（7 条）；§13.3 L1215–L1227（9 条）；§13 全章 | 只有 7 条升档、9 条降档的 SHOULD 条件，零聚合规则：多条证据如何合成一档没有定义。置信度是判断而非计算 | 定义聚合函数：证据计数 + 证据类型权重 + 冲突惩罚，输出三档；无法聚合时强制降为 Unknown |
| D9 | high | §15.4 L1310–L1315；§15.5 L1316–L1320 | L1311 要求「similar evidence strength SHOULD produce similar confidence」，但 evidence strength 全文未定义，唯一的一致性规则不可执行；§15.5 给出三种处置却无仲裁顺序 | 先定义可比较的 evidence strength 度量（类型 + 直接性 + 一致性），再谈一致性；§15.5 三种处置排优先级 |
| D10 | medium | §12.2 L1142–L1154（L1152–L1153） | 五档优先级无权重、不构成全序；L1152–L1153 又把源码放回「任意层级」，唯一的排序机制自我消解 | 不采纳该优先级（C23），改用既有 `source_type` 四值 + 确定性事实优先 |
| D11 | high | §6.9 L485–L503（L499–L501） | 十三条终止条件全为 SHOULD；L499–L501「additional passes produce little new product knowledge」无度量方式。没有硬终止，就有无限循环与成本失控风险 | 设计可计算终止判据：连续两轮新增主张数低于首轮 X%、注册表闭合、Unknown 全部带五字段 |
| D12 | medium | §11.1–§11.6 L1044–L1113（L1046、L1069、§11.6） | 强制 D2，但无 D2 工具链、无语法校验、无法检测装饰性图表与一图一意 | 不采纳（C24）；图形态交由渲染层决定，若要校验则用结构化中间表示而非 D2 源码 |
| D13 | medium | §14.3 L1276–L1282 | 未知项生命周期只有「保持开启直到证据/干系人/运行时观察解决」，无 owner、无触发条件、无过期机制。Unknown 可以永远挂着而无人负责 | 补 `owner`、`resolved_by`、`review_after` 三字段；到期未解则强制降级或归档 |
| D14 | medium | README L115–L195 vs SKILL §6；README L73–L86 vs SKILL §12.1；README L46–L57 vs §5.3 | README 与 SKILL 是两套并行体系而非摘要与详述：README 四步 vs SKILL 九节工作流；README 十二个证据源 vs SKILL 十七个；README 输出 11 项不含 business entities | 以 SKILL 为唯一权威，README 降格为导览；差异处标注「以 SKILL 为准」 |
| D15 | medium | §6.6 L424–L442 | 十个精修动作无完成谓词，无法判断精修是否足够 | 每个动作配一个可判定条件（如「同义合并后注册表无别名冲突」） |
| D16 | medium | §17 L1349–L1439（55 问） | 自检清单无通过标准、无计分、无阈值、无产物；55 问全部靠主观回答 | 改造为结构化 gate，每问绑定可判定检查项与失败动作 |
| D17 | low | §9.1 L790–L806、§9.2 L807–L823、§9.6 L935–L949 | 角色/流程/约束的表面清单是开放式「often found in」启发式，无权重、无完整性判据 | 保留为提示，不当作覆盖度依据；覆盖度另设可计算指标 |
| D18 | low | §2 L45–L57 | 「通过仓库实验演进方法论」要求记录实验日志，但仓库内不存在任何实验日志、issue 或修订记录（单根提交，从未更新） | 记录为方法论自述与仓库事实的落差；不影响能力判定 |

## 8. 与 UPSTREAM-01/02 的去重结论

这是本源审计的核心要求。结论先说：**三者没有真正的功能重叠，但有四处形式冲突必须在融合前解决。**

### 8.1 三者职责边界

| 维度 | UPSTREAM-01 | UPSTREAM-02 | UPSTREAM-03 |
|---|---|---|---|
| 回答的问题 | 这个仓库**有什么** | 这个项目**在外面是什么样** | 这个产品**是干什么的** |
| 产出物 | `repo_facts.json`（确定性事实） | 生态与历史研究报告 | 产品模型 + 知识库骨架 |
| 判定性质 | 可计算 | 可取证 | 可解释 |
| 失败模式 | 事实抽取不全 | 外部信息失真 | 推断冒充事实 |
| 对模型的依赖 | 只解释含义 | 只做归纳 | 全流程判断 |
| 可否重跑得同一结果 | 是（确定性） | 部分（外部状态会变） | 否（判断有方差） |

关键：**本源不新增任何 GitHub 采集行为。** 它不提 API 调用、不提 commit 查询、不提 issue 检索。它唯一的「采集」动作是扫本地已克隆的仓库文件（§9.5 必扫面清单）。因此「单一 GitHub Collector」约束（UPSTREAM-01 C15、UPSTREAM-02 C18 均判 REJECT 自建客户端）**在本源身上自动满足**——它根本没有采集器可建。

### 8.2 四处形式冲突与解法

| 冲突 | 上游主张 | SourceLore 既有约束 | 解法 |
|---|---|---|---|
| 证据优先级 | §12.2 五档优先级（C23） | UPSTREAM-02 已确立 `source_type` 四值（`github_api` / `readme_claim` / `external_web` / `inference`） | 拒绝五档（C23），一律映射到既有四值。映射规则：源码与测试 → `github_api`（经确定性采集）；README 与文档 → `readme_claim`；上游外部资料 → `external_web`；模型推断 → `inference` |
| 置信度表达 | §13.1 L1201 允许百分比（C27） | 项目明令禁止未校准百分比 | 拒绝百分比（C27），只保留三档序数标签 |
| 工具化程度 | §2 L52–L53 禁止 AST 解析器、图数据库、静态分析管线、索引系统（C25） | SourceLore 核心就是确定性 CLI + 索引 | 拒绝该禁令（C25）。理由：上游禁令是为「LLM-first 的 v1」服务，SourceLore 的架构前提不同，且 UPSTREAM-01 已证明确定性抽取可行 |
| 证据格式 | §14.2 五字段未知项 + §10.2 六段页面 | 需与 `claims.json` / `evidence.json` 兼容 | 五字段直接落为 `claims.json` 中 `type: "unknown"` 的五个必填子字段；页面六段由 schema 定义，不由上游定义 |

四处冲突全部有明确处置，无一处需要「两套并存」。

### 8.3 三层数据模型的关系

本源唯一需要新引入的概念是 **Product Model**。它和既有两个文件的关系必须说清楚，否则会出现第四套数据。

```
repo_facts.json          确定性事实层（UPSTREAM-01 CLI 产出，只增不改语义）
   │  事实：文件、路由、依赖、配置、schema、测试、脚本
   │  规则：不含任何模型句子（本源 §6.1 的观察/推理隔离落在这里）
   ↓
Product Model            产品语义草稿层（本源 §5.1–§5.8；内部态，不直接对外）
   │  内容：frame / roles / entities / capabilities / flows / boundaries / constraints
   │  规则：每个字段强制带 claim_type ∈ {fact, inference, insufficient} 与 evidence_refs
   ↓
claims.json              主张层（对外权威，一主张一条记录）
   │  内容：subject / predicate / object / claim_type / confidence / evidence_refs / page
   │  规则：Canonical Knowledge Registry（本源 §6.4）在此实现为实体消解表
   ↓
evidence.json            证据层（一证据一条，可被多主张引用）
   │  内容：source_type（四值）/ path / line_range / excerpt_hash / retrieved_at
   │  规则：本源 §12.4 的冲突记录在此落为同 subject 的多条互斥 evidence_refs
   ↓
渲染层                    Markdown 知识页（本源 §6.5 的 14 步顺序在此生效）
```

四层的关系可以压成一句话：**`repo_facts.json` 回答「存在什么」，Product Model 回答「这可能意味着什么」，`claims.json` 回答「我们断定什么以及凭什么」，`evidence.json` 回答「凭什么」本身。**

本源在其中的位置是第二层——它是唯一规定「从事实到主张该怎么走」的方法论。第一层是 UPSTREAM-01 的领地，第四层是 SourceLore 渲染层的领地，第三层由本源提供骨架（注册表 + 五字段 Unknown + claim_type 分级）、由 UPSTREAM-02 提供证据分类法。

**Product Model 不是第四套数据，是 `claims.json` 的草稿态。** 它的每个字段在进入 `claims.json` 时都必须变成一条带 `claim_type` 与 `evidence_refs` 的记录。若某字段无法给出 `evidence_refs`，则该字段只能以 `claim_type: "insufficient"` 进入，并被强制渲染为 Unknown 页——这条硬规则直接对应本源 §4.3 L127 与 §5.8 L265。

### 8.4 本源独有的、01/02 完全没有的能力

按「01 和 02 是否已经能做」逐项核对：

| 能力 | 01 有吗 | 02 有吗 | 本源独有 |
|---|---|---|---|
| 业务实体识别与消解 | 无 | 无 | ✓ |
| 角色建模（按权限而非画像） | 无 | 无 | ✓ |
| 能力域划分（跨模块、跨服务） | 无 | 无 | ✓ |
| 用户/系统流程重建 + 已确认步与推断步分离 | 无 | 无 | ✓ |
| 外部边界三分类 | 部分（能列出依赖） | 部分（能列出生态） | ✓ 分类法本身 |
| 未知项建模 | 无 | 无 | ✓ |
| 规范名注册表 / 别名消解 | 无 | 无 | ✓ |
| 依赖序构建 + 增量重跑契约 | 无 | 无 | ✓ |
| 观察/推理隔离纪律 | 部分（CLI 天然不含推断） | 无 | ✓ 纪律的显式化 |
| 主张措辞规则 | 无 | 无 | ✓ |

十项全部为本源独有。这也解释了为什么它的 ADAPT 比例最高：**能力是新的，实现是空的**，只能借思想自建实现。

## 9. SourceLore 融合设计

### 9.1 单一采集器约束的维持

本源不引入采集器，但引入了**新的扫描需求**（§9.5 的必扫面 + 8 组正则）。这些需求必须全部落在 UPSTREAM-01 已确立的 CLI 之内：

```
现有：  gh api → repo_facts.json（文件清单、语言、依赖、结构）
新增：  本地快照扫描器（读 upstreams/<id>/tree/，只读）
        输入：repo_facts.json 的文件清单
        规则：SKILL.md §9.5 L901–L909 的 8 组正则
        输出：integration_candidates[] 追加进 repo_facts.json（新字段，不改旧字段语义）
约束：  不新增网络请求；不新增第三方依赖；不读 upstreams/ 之外的路径
```

关键：这个扫描器**读的是已经存在的快照，不发任何网络请求**，所以不构成第二个 GitHub Collector。它只是 UPSTREAM-01 CLI 的一个新子命令。

### 9.2 落地为 linter 规则集

本源最有价值的部分是它把「什么是好知识库」写得很细，却完全没有实现。SourceLore 应把它落成带 rule id 的检查器。从上游可直接推导出的规则：

| rule id | 来源 | 检查内容 | 判定 |
|---|---|---|---|
| `KB001` | §8 L714 | `Inventory.md` 必须存在 | 文件存在性 |
| `KB002` | §8 L723 | Decision 必须是一等产物 | 目录中存在 Decision 页 |
| `KB003` | §8 L725 | Risk 必须是一等产物 | 目录中存在 Risk 页 |
| `KB004` | §6.4 L376 | 无竞争规范名（同一概念不得有多个 canonical 名） | 注册表内别名冲突检测 |
| `KB005` | §6.5 L418 | 所有 registry-backed 链接必须指向存在的页 | 链接目标存在性 |
| `KB006` | §10.4 L1020 | wiki link 必须可解析 | 与 KB005 合并实现 |
| `KB007` | §7.2 L534 | 每个 glossary 条目必须成页 | 条目数 == 页数（**本项按 C26 拒绝，改为条目覆盖率**） |
| `KB008` | §10.2 L961–L969 | 必备五段齐备 | 段标题存在性 |
| `KB009` | §10.2 L983 | 必备段不得为空壳 | 段内容最小长度 + 非模板句 |
| `KB010` | §13.4 L1229–L1239 | 主张措辞不得过度确定 | 措辞扫描（`proves`/`clearly`/`obviously` 等） |
| `KB011` | §14.2 L1262–L1274 | Unknown 五字段齐备 | 字段存在性 |
| `KB012` | §14.2 L1275 | 禁止「needs more research」式空洞未知 | 措辞扫描 |
| `KB013` | §12.5 L1176–L1178 | 证据中不得出现密钥值 | 熵检测 + 已知模式扫描 |
| `KB014` | §15.1 | 命名一致性 | 注册表交叉比对 |
| `KB015` | §15.3 | 主张一致性（同一 subject+predicate 不得有互斥 object 而无冲突记录） | `claims.json` 查询 |
| `KB016` | §6.9 L499 | 终止判据 | 连续两轮新增主张数 / 首轮 < 阈值 |
| `KB017` | §4.3 L128 | 无证据主张不得标为 fact | `claims.json` 中 `claim_type: fact` 必须有 `evidence_refs` |
| `KB018` | §5.6 L247–L248 | provider 配置文件存在则必须有 Integration 页或解释性 Unknown | 配置扫描结果 × 页面清单 |

18 条规则中，`KB001`–`KB006`、`KB008`–`KB018` 共 17 条可完全机器判定；`KB007` 按 C26 改为覆盖率指标而非硬失败。

### 9.3 增量更新契约

本源 §6.8 的九个重跑点需要变成可判定条件：

| 上游重跑点 | 可判定化 |
|---|---|
| 新证据出现 | `repo_facts.json` 哈希变化 |
| Product Model 变更 | `claims.json` 中 `claim_type: inference` 记录数变化 |
| 注册表变更 | 注册表条目增删或别名变更 |
| 页面新增/删除 | 页面清单差异 |
| 证据冲突被记录 | `claims.json` 新增冲突组 |
| Unknown 被解决 | Unknown 状态从 open → resolved |
| 构建序被违反 | linter `KB005` 失败 |
| 一致性审查发现新问题 | linter 结果差异 |
| 方法论修订 | linter rule 集版本变化 |

九个点全部落到「文件哈希 + 记录计数 + linter 结果」三类可观测量上，不依赖模型的自我判断。

### 9.4 与 UPSTREAM-01 的 token 预算对接

UPSTREAM-01 已确立四轮预算（R0 事实 / R1 骨架 / R2 定点搜索 / R3 交叉校验 / R4 渲染）。本源的方法论应映射进这四轮，而不是另开一套五阶段：

| UPSTREAM-01 轮次 | 本源对应 | 本源要求的下沉方式 |
|---|---|---|
| R0 事实 | §6.1 Inventory | 由 CLI 渲染，零模型调用 |
| R1 骨架 | §6.2 Product Model + §6.4 Registry | 模型只读 R0 产物 + 少量定点文件，产出草稿 claims |
| R2 定点搜索 | §9 各类启发式 | 按 §9.5 扫描面优先级取前 N 项，受预算上限约束 |
| R3 交叉校验 | §12 证据规则 + §15 一致性 | linter 跑 `KB*` 规则集，模型只处理 linter 报出的冲突 |
| R4 渲染 | §6.5 十四步构建序 + §10 文档标准 | schema 驱动渲染，模型不参与结构决策 |

这条映射解决了本源最大的落地风险（D3）：**把「每阶段回看整仓」替换为「每轮只读上一轮的产物 + 定点文件」**，token 成本从 O(仓库大小 × 14) 降为 O(仓库大小 × 1 + 定点读取)。

## 10. 依赖与运行约束

上游零依赖、零运行时、零可执行物。

- 无 `package.json` / `requirements.txt` / `pyproject.toml` / `Cargo.toml` / `go.mod`
- 无脚本、无 CI 配置、无构建流程
- 唯一外部引用：CC BY 4.0 legalcode URL（`LICENSE` L16）
- 隐含依赖：一个能读代码、能跨文件对照、能写长文档的 LLM（§2 L52 显式要求 LLM-first）

对 SourceLore 环境的影响：**无新增依赖，无安装动作，无版本冲突风险。** 这一点与 UPSTREAM-02 不同（后者带一个 Python 采集器，需核对本机 Python 版本）。

方法论自身的工具禁令（§2 L52–L53，禁 AST 解析器、图数据库、静态分析管线、索引系统）已按 C25 判定为 REJECT，不构成对 SourceLore 的约束。

## 11. 安全边界

上游文本层面与本项目执行层面分别记录。

上游要求（采纳部分）：

- §12.5 L1176–L1178：证据中不得抄录密钥值 → 落为 `KB013`
- §9.5 L915–L920：匹配到的 provider 产物不得静默省略，但只允许写配置存在，不得写具体值
- §9.5 L929–L933：噪声目录（`node_modules`、编译产物、vendored 库）应排除，且排除项必须记录在 `Review.md`

上游未覆盖而本项目必须补的：

- **快照隔离。** `upstreams/` 已由 `.gitignore:4` 排除，冻结副本不进 Git 历史。已用 `git check-ignore -v` 复核。
- **不执行上游指令。** `SKILL.md` 1452 行含大量祈使句；本次审计全程只读，未按其要求产出任何知识库，未安装任何东西。
- **不访问上游引用的外部地址。** `LICENSE` L16 的 CC legalcode 地址未访问；判断依据是 `LICENSE` 自身的 16 行文本。

必须记录的残余风险：**祈使句冲突。** 若把 `SKILL.md` 整篇作为 prompt 注入，其 MUST/SHOULD 会与 SourceLore 系统规则竞争，其中至少两条（§2 L53 禁确定性工具、§13.1 L1201 允许百分比）与既有规约直接冲突。这正是必须 ADAPT/REIMPLEMENT 而非 REUSE 全文的技术理由。融合时只允许注入改写后的规则集，不允许注入原文。

## 12. 复用时的义务清单

CC BY 4.0 的强制义务，逐条对应到具体动作：

| 义务 | 具体执行 |
|---|---|
| 适当署名 | 在 `THIRD_PARTY_NOTICES.md` 记录：仓库 `https://github.com/maboasoft/repository-discovery`、Repository ID `1290761659`、Commit `557703fffe69c9ab97eff67acabea6b346afd89c`、上游作者 `Vladimir <kuzmenko.dn@gmail.com>`。因 `LICENSE` 无版权行，署名只能以这四项合成 |
| 提供许可证链接 | 附 `https://creativecommons.org/licenses/by/4.0/legalcode` 与 `LICENSE` 快照路径 |
| 标明是否作了修改 | 本审计已对 27 项能力逐项判定，其中 12 项 ADAPT、7 项 REIMPLEMENT 均为**修改后使用**。须在 notices 中写明「以下内容改编自上述来源，已作修改」并列出改编项（C04–C15、C16–C22） |
| 不得附加额外限制 | 不得对改编部分施加比 CC BY 4.0 更严的条款 |

三处特别提示：

1. **`REUSE` 的三项也要署名。** C01、C02、C03 虽未修改，但仍然构成「使用该材料」，署名义务不因未修改而消失。
2. **不能整体并入自有许可。** `SKILL.md` 1452 行是受保护的表达。SourceLore 自己的许可证不能覆盖这些正文。可自由使用的是**思想、方法、清单结构**（不受版权保护），受保护的是**具体表述**。因此实现时须自行撰写规则文本，不得复制原句成段。
3. **`examples/knowledge-base-structure.md` 未被复用。** 它的三套冲突模板（D2）已被判为不可直接采用；如后续参考其目录树形态，同样触发署名义务。

## 13. 验收结论

| 验收项 | 结论 | 证据 |
|---|---|---|
| 上游 Commit 已完整固定 | 通过 | `557703fffe69c9ab97eff67acabea6b346afd89c`，单根提交，`parents: []`，全仓仅 1 次提交（第 1 节） |
| 实际审查范围已明确到文件与行 | 通过 | 4 个 blob 全量枚举，1820 行逐行通读，双哈希校验（第 3 节） |
| 许可证与署名来源已取证 | 通过 | `LICENSE` 16 行逐行读取，实测定为 CC BY 4.0；API `NOASSERTION` 差异已解释；无版权行的替代署名方案已给出（第 2 节） |
| Product Model 方法论已完整拆解 | 通过 | §5.1–§5.8 八要素逐节分析 + §6 工作流九节 + §7 九类页面 + §9 六组启发式（第 5 节） |
| 已提出知识实体与关系模型 | 通过 | 四层模型（`repo_facts.json` → Product Model → `claims.json` → `evidence.json`），含注册表映射与 claim_type 强制分级（第 8.3 节） |
| 与 01/02 的重叠已明确识别 | 通过 | 职责边界表 + 四处形式冲突及处置 + 十项独有能力核对（第 8 节） |
| 未把无证据的模型推断当作源码事实 | 通过 | 全部结论标注文件与行号；上游未实现的能力明确标为「缺失」而非「有缺陷的实现」；D18 记录方法论自述与仓库事实的落差 |
| 未修改真实分析引擎与其他未授权文件 | 通过 | 本次仅新增 `docs/upstream-audit-03-repository-discovery.md` 与 `progress/UPSTREAM-03-audit.json`，更新账本与 manifest；`src/`、`skills/`、`schemas/`、`tests/` 零改动 |
| 测试状态 | `NOT_RUN` | 上游无可执行物，1820 行文档无一行代码；不存在可运行的测试 |

### 结论

`maboasoft/repository-discovery` 是三个上游里**方法论密度最高、可执行程度最低**的一份。1820 行文档、零行代码、零依赖、零测试。它的价值不在实现，在于它把「从代码仓库反推产品语义」这件事拆成了可讨论的步骤，并且给出了三个上游唯一的数据模型构件（Canonical Knowledge Registry）与唯一的增量契约（Rerun Protocol）。

它的根本问题与它的价值同源：**写得越细的地方，越是无法判定。** 九套页面 section 集合互相冲突（D1）、置信度有标签无聚合（D8）、终止条件不可度量（D11）、质量门自称必需却无实现（D6）。27 项能力里只有 3 项可原样使用，12 项需改造，7 项必须自建，5 项明确拒绝。

最值得融合的四个机制，按优先级：

1. **观察/推理硬隔离**（§6.1）—— 成本最低、收益最直接、与既有架构零冲突，落成「`repo_facts.json` 渲染层禁止注入模型句子」。
2. **Canonical Knowledge Registry**（§6.4）—— 直接成为 `claims.json` 的实体消解层，补上三个上游共同的空白。
3. **未知项一等公民**（§14）—— 补上 `repo_facts.json` 只有「有什么」没有「不知道什么」的结构性缺口。
4. **十四步依赖序 + 九个重跑点**（§6.5、§6.8）—— 直接成为渲染层 DAG 与增量更新契约。

后续设计风险三条：

1. **祈使句污染。** 这是唯一会主动破坏现有规约的风险。`SKILL.md` 的 MUST/SHOULD 一旦整篇进入 prompt，至少两条会与 SourceLore 既有约束正面冲突。融合必须走「改写为规则集」，禁止注入原文。
2. **实体页悬空。** 上游要求建模业务实体却不给产物位置（D4）。若不先定义实体页类型就照搬 §5.3，会产出一批无处安放的语义。
3. **低 token 目标与全仓扫描的结构性矛盾。** 上游的 14 步顺序假设每阶段可见全仓（D3）。若不按第 9.4 节把它压进 UPSTREAM-01 的四轮预算，在 monorepo 上 token 成本会失控——而这正是 SourceLore 目标模型（DeepSeek-V4.1 Flash）最承受不起的失败方式。
