# UPSTREAM-02 审计记录：bytedance/deer-flow · github-deep-research

> 本文件是 M1 第二源的形式化审计记录。所有路径均可从冻结快照复核。
> 快照目录：`upstreams/UPSTREAM-02-deer-flow/tree/`（Git 忽略，只读使用，未执行其任何代码）。
> 审计目标只是 `skills/public/github-deep-research/` 这一棵子树，不是 deer-flow 全仓。

## 1. 上游版本固定

| 项 | 值 | 证据来源 |
|---|---|---|
| 仓库地址 | `https://github.com/bytedance/deer-flow` | 总控提示词 §C 列出的第二源 |
| 审计子树 | `skills/public/github-deep-research/` | `git/trees?recursive=1` 后按路径过滤 |
| GitHub Repository ID | `979115477` | `gh api repos/bytedance/deer-flow` |
| 默认分支 | `main` | 同上 `default_branch` |
| 固定 Commit SHA | `44e372dd7f8a511e6223f548f55f7b4c939ca226` | `gh api repos/bytedance/deer-flow/commits/main` |
| Commit 时间 | 2026-10-31T03:35:36Z | 同上 `commit.committer.date` |
| Commit 标题 | `feat(runtime): support Queue and Steer during active Web runs (#7729)` | 同上 `commit.message` |
| 仓库 `pushed_at` | 2026-10-31T03:35:36Z | 同上 |
| 可见性 / 体积 / 归档 | `public` / 97338 KB / 未归档、非 fork | 同上 `private` / `size` / `archived` / `fork` |
| 检索时间 | 2026-10-31 12:43 +08:00 | 本次审计执行时刻 |
| 快照方式 | `gh api .../contents/<path>?ref=<完整SHA>` 逐个取原始字节 | 见第 3 节哈希表 |
| 快照内容 | 3 个 blob + 2 个 tree，无其他文件 | `upstreams/UPSTREAM-02-deer-flow/files.tsv` |

版本在读取源码之前固定，审计全程只读该 SHA 的冻结副本，不跟随分支漂移。这一点对本源格外重要：根仓 `pushed_at` 为 2026-10-31T03:35:36Z，与本文件写作时间只隔数小时，**分支漂移是随时可能发生的现实，不是理论风险**。

该子树近三次变更（`gh api commits?path=…`）本身构成有力的侧证，说明上游对自己的实现缺陷有察觉：

| Commit | 时间 | 标题 | 对应缺陷 |
|---|---|---|---|
| `4ff0b0bff1` | 2026-10-19 | `fix(github-research): resolve the tree against the repository's default branch (#7074)` | 对应 D8 |
| `033fb1aa1f` | 2026-10-21 | `fix(github-research): report a failed fetch instead of returning it as content (#7221)` | 对应 D6 的被修复部分 |
| `5ca17829be` | 2026-10-26 | `fix(skills): exclude pull requests from GitHub issue research (#7516)` | 对应 D3 |

三次修复全部指向「数据静默错误」，而 D3 的修复本身又引入了 D4。这条时间线是本文档最重要的外部证据之一：**同类缺陷有反复复发的记录**。

## 2. 许可证结论

| 项 | 结论 | 证据 |
|---|---|---|
| 许可证类型 | MIT | `LICENSE` 第 1 行 `MIT License`；API `license.spdx_id = "MIT"`、`license.path = "LICENSE"` |
| 版权行 | `Copyright (c) 2025 Bytedance Ltd. and/or its affiliates`、`Copyright (c) 2025-2026 DeerFlow Authors` | `LICENSE` 版权段 |
| 复用条件 | 允许 use / copy / modify / merge / publish / distribute / sublicense / sell | `LICENSE` 许可正文 |
| 强制义务 | 在软件的**所有副本或实质性部分**中保留版权与许可声明 | `LICENSE` 义务段 |
| 免责 | AS IS，无任何明示或默示担保 | `LICENSE` 免责段 |

判定：**许可允许改编复用**，条件是保留双版权行与 MIT 声明。履行方式与 UPSTREAM-01 一致：在 `THIRD_PARTY_NOTICES.md` 中列出仓库 URL、Repository ID `979115477`、Commit SHA `44e372dd…`、两行版权、MIT 全文链接。

注意一处与 UPSTREAM-01 的差异：本仓库有**两个**版权主体（Bytedance 与 DeerFlow Authors），且版权年份跨 2025–2026。义务履行时两行都要保留，不能只留其一。

## 3. 实际审查范围

逐文件通读，无一凭目录名或 README 推断：

| 文件 | 行数 | 字节 | sha256 |
|---|---|---|---|
| `SKILL.md` | 168 | 5257 | `b6a19fa2cf70b60a4cc920d8ebee079b6126eaa483eb612abe346dcbb0b02683` |
| `scripts/github_api.py` | 358 | 12571 | `03ef058acd92e18de24e9672235c789e44741001d135cf3c6d3b5b6f6da7e660` |
| `assets/report_template.md` | 192 | 3580 | `fdd14d2ebf049ef7bf7bb839ac76c259bd4cfa05614a22b844a4e97210f62502` |
| `LICENSE` | 21 | 1134 | `b23dff4d4bac8d17b6efaaa7e88c2b730149c4dda45699ce676b719cfdffe7e1` |

合计 718 行、22.5 KB。这是本子树在冻结 SHA 上的全部内容。

关于「可发现的测试」：子树内**不存在**任何测试文件。逐一验证过 `files.tsv`，没有 `test*`、`tests/`、`requirements*`、`pyproject.toml`、`setup.cfg`、任何 `.json` 或 `.yml`。因此：

- 单元测试：`NOT_RUN`（不存在）
- 集成测试：`NOT_RUN`（不存在）
- 静态检查/格式配置：`NOT_RUN`（不存在）

此结论不是「没找到」，是「枚举全部 3 个 blob 后确认不存在」。

## 4. 架构与分层（实测）

上游的架构不是代码分层，而是**提示词分层**——这是它与 UPSTREAM-01 最根本的形态差异。

```
SKILL.md            散文规格：四轮流程、搜索预算、来源优先级、报告 9 节、置信度三档、引用规则
assets/report_template.md  输出契约的字面骨架：带 {SLOT} 的固定小节与固定基数
scripts/github_api.py      唯一的确定性取数层：10 个 CLI 命令，单页 GET，无状态
                          ↑
                    （中间什么都没有）
```

三层之间**没有任何程序化连接**：

- `SKILL.md` 不会调用 `github_api.py`，它用自然语言让 LLM「Directly execute `scripts/github_api.py` … without `read_file()`」（L40）；
- 脚本不知道报告长什么样，它只把 JSON 或字符串打到 stdout；
- 模板不由任何代码填充，是给 LLM 抄的格式范例。

所以「四轮研究」是**一个状态机的描述，不是一个状态机的实现**。轮次之间没有交接结构：没有轮次产物 schema，没有「第 1 轮事实摘要」被第 2 轮读取的机制，也没有任何东西阻止 LLM 在第 2 轮忘掉第 1 轮取到的东西。整个编排责任落在一次对话的上下文窗口上。

`github_api.py` 自身的分层很浅，但清楚：`RequestsFallback`（L13-50）提供与 `requests` 同形的 `get`；`GitHubAPI`（L64-230）做端点封装；`format_tree` / `summarize_repo`（L232-312）做呈现；`main()` + `commands`（L315-358）做 CLI 分发。全文件单类、单文件、无配置、无抽象接口。

## 5. 十个审计问题的回答

十个问题逐条回答，每条只给从实现读出来的事实与行号，不采信 `SKILL.md` 中的自我描述。

### 5.1 四轮 GitHub 深度研究：输入、处理、输出、阶段交接

- **输入**：`SKILL.md` 没有定义入口参数。使用者（LLM）从用户请求里自己提取 `owner` 与 `repo`，再手工拼命令行。脚本层面输入是 `sys.argv`：`owner`、`repo`、可选 `command`（`github_api.py:315-327`），缺省命令为 `summary`。
- **处理**：只有第 1 轮有确定性实现（10 个 CLI 命令）。第 2、3 轮完全外包给 `web_search` / `web_fetch`，第 4 轮又回到 CLI 的 `commits`/`issues`/`prs`/`contributors`。
- **输出**：脚本输出为 JSON（`json.dumps(result, indent=2, default=str)`，L355）或一行字符串（`tree`、`readme` 命令）。最终报告产物由 LLM 按 `assets/report_template.md` 手写成 markdown。
- **阶段交接**：**不存在**。没有中间产物文件，没有阶段间 schema，没有把第 1 轮取到的数据固定下来给后续轮次读取的机制。交接的唯一载体是 LLM 的上下文。

结论：所谓「四轮」，是提示词给出的四条行为建议（`SKILL.md:10-15` 仅 4 个要点，无任何状态、无前置条件、无完成判据），**不是可执行流程**。

### 5.2 GitHub API 认证、分页、限流、重试、缓存、数据完整性

逐项实测（`scripts/github_api.py`）：

| 维度 | 实现 | 判定 |
|---|---|---|
| 认证 | `os.getenv("GITHUB_TOKEN")`（L327）→ `Authorization: token {token}`（L72）。无 token 时降级为匿名（60 次/小时） | **可用但脆弱**：匿名时无任何提示，配额从 5000 掉到 60 |
| 分页 | 仅 `get_issues` 有 `while` 循环（L186-194），其余全部单页 `per_page=min(limit,100)` | **基本不分页**（详见 D1、D4） |
| 限流 | `grep -ci` 结果：`x-ratelimit` / `X-RateLimit` / `Retry-After` 均为 **0 次出现** | **完全未实现** |
| 重试 | `retry` **0 次**、`sleep` **0 次**、`backoff` **0 次** | **完全未实现**。任何一次 5xx 或网络抖动都会让整条命令失败 |
| 缓存 | `cache` **0 次**、`etag`/`ETag`/`If-None-Match` 均 **0 次** | **完全未实现**。同一份数据在四轮里可能被重复取 3 次，每次都是完整配额消耗 |
| 超时 | 唯一防护：`timeout=30`（L94 与 L45） | 有，但超时后无重试 |
| 数据完整性 | 无 `Link` header 解析（全文仅 L293 注释提到，且未使用）；无 `truncated` 标志检查 | **无**：GitHub 的 `trees` 接口在超大仓库会返回 `truncated: true`，本脚本不检查，直接把不完整的树当完整树呈现 |

这六项合起来是一个明确的判断：这个客户端在**正常一次通过**的情形下能工作，在**任何异常**（限流、超时、5xx、树截断、多页）下会静默给出错误结果或直接崩掉，而调用者（LLM）无法从输出里分辨是哪种。

### 5.3 Issue/PR/Release/Commit/Contributor 五类数据如何收集

| 类别 | 端点 | 页数 | 关键限制 |
|---|---|---|---|
| Issue | `/repos/{o}/{r}/issues`（L166） | 循环，但有 D4 缺陷 | `labels` 参数接收却未使用（L186-188 的实际逻辑里 `params["labels"]` 只在 `if labels` 时加，但调用方从不传值）；`state="all"` 时按 updated 排序，历史 issue 会被挤出 |
| PR | `/repos/{o}/{r}/pulls`（L198） | **单页** | 无过滤、无分页。100 条以上静默截断 |
| Release | `/repos/{o}/{r}/releases`（L207） | **单页** | `limit=10` 默认值写在签名里，调用方不传，只有最近 10 个 |
| Commit | `/repos/{o}/{r}/commits`（L149） | **单页** | 有 `since` 无 `until`，无法取「某时间段内」；无法按路径过滤（上游自己的 `commits?path=` 能用，脚本不暴露） |
| Contributor | `/repos/{o}/{r}/contributors`（L143） | **单页** | 上限 100，且见 D5 的双重调用与截断 |

五类全部是「取最近一页」。这意味着脚本无法回答任何**需要完整序列**的问题：无「贡献者总数」、无「PR 总数」、无「版本发布节奏」。而 `SKILL.md` L74-75 明确要求第 4 轮「Analyze commit history for timeline」、`report_template.md` L38-56 要求「Complete Chronological Timeline」——**要求的是完整时间线，供给的是单页切片**。这是本审计中「需求与能力错配」最严重的一处。

### 5.4 外部搜索来源的可靠性、去重、证据优先级、交叉验证

`SKILL.md` L30-35 给了五层来源优先级（官方文档/仓库 > 技术博客 > 新闻 > 社区 > 社交媒体），L150-152 要求「三角验证 2+ 来源」、「记录冲突信息」。这些都是合理的**原则**，实现情况如下：

- **优先级**：仅以序数描述（最高 / 最低），**没有数字化权重，没有可执行判定**。什么算「经核实的媒体」（L33 原文 "verified media outlets"）没有定义。
- **去重**：**零实现**。全文没有 URL 规范化、没有去掉 tracking 参数、没有 canonical 化、没有按域名聚合。`web_search` 返回同一篇文章的多个镜像会被当作多个独立来源——这直接破坏「三角验证」的有效性：所谓「2+ 来源」可能是一个人写的一篇稿子被三个站转载。
- **证据优先级**：只有文字排序，没有把来源层级写进引用结构。`report_template.md` L139-155 分了四个桶（Primary / Media / Academic-Technical / Community），这是唯一接近实现的机制，但分桶由 LLM 手工决定，无校验。
- **交叉验证**：无机制。`SKILL.md` L151 的 "Always verify claims with 2+ sources" 是祈使句，不是检查。

结论：来源可靠性体系是**规范层面的完备、实现层面的空白**。

### 5.5 活跃度、维护状况、版本历史、社区反馈如何分析

- **活跃度**：脚本提供 `get_commit_activity`（`/stats/commit_activity`，L224-226）与 `get_code_frequency`（L228-230）——**但这两个方法不在 `commands` 字典里**（L329-338 共 10 项，已逐一 grep 确认），CLI 无法调用，属于死代码。实际可用于活跃度判断的只有 `summary` 里的 `pushed_at` / `updated_at` 两个时间戳，以及单页 commits 的第一条日期。
- **维护状况**：无 open issue 数随时间变化、无平均响应时长、无 stale issue 比例。`summary.open_issues`（`summarize_repo` L272）只有一个瞬时快照数，不含任何时间维度。
- **版本历史**：`get_releases` 单页 10 条、`get_tags`（L213-217）同样是死代码。无法画出版本节奏。
- **社区反馈**：`search_issues`（L219-222，`/search/issues`）也是死代码。`SKILL.md` 让 LLM 用 `web_search "{topic} issues"` 去搜——即让搜索引擎替代 API 做结构化检索，结果质量与可复现性都不可控。

四个维度里有三个维度所依赖的能力，正是那四个死代码方法。这不是巧合，是**能力已写但未接线**的直接后果：`SKILL.md` L47-58 列出的「可用命令」只有 10 条，与 `commands` 字典完全对齐，说明上游自己也认为那四个不在可用面上。

### 5.6 陈旧材料、矛盾来源、不可用数据如何处理

- **陈旧材料**：无任何时间戳比较逻辑。`SKILL.md` 提到 `{TIME_SCOPE}`（模板 L185），但无过期判定。没有任何地方检查「这条数据是 6 年前的状态」。
- **矛盾来源**：`SKILL.md` L150-152 要求 "Document conflicting information"，但报告结构里**没有承载冲突的字段**。`report_template.md` 的 `Sources` 一节（L139-155）只分桶列举，无法表达「A 说 X、B 说 not X」。
- **不可用数据**：这是最严重的一项。`summarize_repo`（L257-312）用三个独立 `try/except Exception:`（L287-289、L291-298、L300-312）把取数失败降级成 `{}` / `"N/A"` / `None`，**不记录失败原因，不区分「查询失败」与「数据确实为空」**。下游 LLM 看到 `contributor_count: "N/A"` 时，无法判断是没权限、限流了、还是仓库真没人贡献。

  这一点与上游自己修过的 D6 是同一类缺陷的回归：`GitHubAPIError` 的 docstring（L53-61）明确写过，曾经的做法是「把失败放在与成功相同 stdout 通道、相同退出码上，导致限流运行与缺失 README 看起来一样」；修复方式是改成抛异常。但 `summarize_repo` 用 `except Exception` 把异常又吞回去了——**修复只覆盖了内容读取器，没覆盖汇总器**。

- 唯一处理得当的是 `get_tree` 的 `HEAD` 语义：docstring（L119-121）说明 `HEAD` 由 GitHub 解析为默认分支，避免返回陈旧的 `master`。这个设计正确（不是 "main"，而是让服务端解析），但它带来另一个问题：**分支在会话期间漂移时，四轮取到的是不同时刻的默认分支**（详见 D8）。

### 5.7 对 DeerFlow 专属工具的依赖：哪些能直接工作，哪些必须适配

逐一枚举 `SKILL.md` 中出现的非标准库依赖：

| 位置 | 原文依赖 | 在 DSH/Tobs 中的可用性 |
|---|---|---|
| L8 | "combining GitHub API, `web_search`, `web_fetch`" | `web_search`/`web_fetch` 在 DSH 中确实存在，但**接口不同**：上游假定的返回结构是 `{title, url, snippet}`（L153 原文），DSH 的搜索结果形状需实测对齐，不能假定额字段 |
| L40 | "Directly execute `scripts/github_api.py` without `read_file()`" | 这是 DeerFlow 的 **agent 工具使用指令**：它要求 agent 用执行工具而非读文件工具拿结果。DSH 里对应的是 bash，语义可迁移但措辞无意义 |
| L61 / L66 | "3-5 `web_search`" / "5-10 `web_search` + `web_fetch`" | 预算以散文给出，无强制执行。DSH 需自己加计数器 |
| L70 | "Use `web_fetch` on valuable URLs for full content" | 可用，但 DSH 的抓取有截断行为，上游未考虑 |
| L153 | 引用字段 `{title, url, snippet}` | 必须实测 DSH 实际字段名后再写适配层 |

再看脚本侧：唯一第三方依赖是 `requests`，且**是可选的**——L7-19 的 `try: import requests / except ImportError:` 提供 `RequestsFallback`，纯 stdlib（`urllib`）也能跑。这意味着**脚本本体的可移植性高于它看起来的样子**：不需要 `pip install` 就能在 DSH 运行。

但可移植不等于可以搬用。结论：

- **能直接工作的**：`requests` 可选设计、端点清单、`Accept: application/vnd.github.raw` 取原文的用法、`get_tree` 用 `HEAD` 让服务端解析默认分支的技巧、CLI 命令到方法的映射表。
- **必须适配的**：取数通道——DSH 平台侧有已认证的 `gh`，再让脚本自带 token 会制造第二套凭据面（这与 UPSTREAM-01 对 `github_client.py` 的判定一致）；`web_search` 结果字段；轮次预算的强制点。
- **无法迁移的**：L40 的 "without `read_file()`" 指令本身、散文形态的轮次规格。

### 5.8 如何区分 GitHub API 数据、README 声明、网络文章和模型推断

**上游没有做这个区分，这是本审计认为的第二严重问题。**

- `scripts/github_api.py` 的输出只有两种形态：JSON 或字符串。没有任何字段标注「这是 API 事实」。
- `SKILL.md` L150-152 要求区分事实与观点（"Distinguish facts from opinions"），但这是给 LLM 的祈使句。
- `report_template.md` 的引用格式是 `[citation:Title](URL)`（L29-34 示例），**只有标题和 URL，没有来源类型字段、没有取数时间、没有 Commit SHA**。所以：
  - 一条来自 GitHub API 的 `stars: 84743` 和一条来自某博客的「据说有 10 万星」在结构上**长得一模一样**；
  - 一个 2026-10-31 取的数字与一个 2024 年的数字无法在结构上区分。
- 上游对这件事的唯一自觉是 `GitHubAPIError` 的 docstring（L53-61），它承认过「失败与成功长得一样」的危害，但只修了异常通道，**没有建立来源类型标记**。

对照 UPSTREAM-01：那边至少把 API 事实写进 `repo_facts.json` 并声明为唯一契约（虽然引用校验只验路径存在）；这边连契约层都没有。**这就是 UPSTREAM-02 在融合时必须被彻底重建的部分。**

### 5.9 是否存在虚假精准度、未经验证的统计结论或证据缺失

有，且有三处可精确指认：

1. **`contributor_count` 的静默截断（D5）**。`summarize_repo` L292 先调 `get_contributors(limit=1)` 并把结果绑定到 `contributors` 变量后**从不使用**，L294-296 再调 `get_contributors(limit=100)` 取 `len(...)`。注释（L293）自己写着 "GitHub returns Link header with total, but we approximate"。后果：一个有 300 名贡献者的仓库，`contributor_count` 报 **100**。这是一个看起来精确的整数，实际是被 `per_page` 上限截断的近似值，**没有任何标注说明它是近似**。这是教科书式的虚假精准度：两次 HTTP 调用本可合成一次，浪费一次配额，换来一个错误答案。

2. **置信度三档的百分比（`SKILL.md` L123-131、`report_template.md` L159-168）**。「High (90%+) / Medium (70-89%) / Low (50-69%)」这三个区间是**未校准的启发式**：没有任何样本集、没有过任何准确率测量、没有任何机制把「2 个来源」映射到「85%」。它们唯一的功能是让报告读起来专业。

3. **`report_template.md` 的固定基数（详见 D10）**：3 个阶段、2 个分析节、3 行指标、2 个竞品。当主体只有 1 个竞品或 5 个阶段时，模板没有「不适用」的合法出口，只有「少填一格」或「硬凑一格」两种选择。而模板页脚 `**Status:** Complete`（L192）是无条件出现的——**没有任何表达「降级/未完成」的通路**。

三条合起来是一个结构性判断：这套报告体系在结构上**倾向于让填充率驱动结论**，而不是让证据驱动结论。它不会有恶意造假，但会造成系统性过度自信。

### 5.10 如何避免与 UPSTREAM-01 的事实收集模块重复

**结论先说：两者边界清楚，不重复，而且必须互补。**

| 维度 | UPSTREAM-01（repo-analyzer-skill） | UPSTREAM-02（github-deep-research） |
|---|---|---|
| 对象 | **仓库内部**：代码、目录、依赖、入口点、架构 | **仓库外部**：生态位、社区、对比、时间线、外部报道 |
| 产出形态 | 结构化事实契约 `repo_facts.json` + 13 键 JSON 报告 | 散文式 markdown 报告（9 节） |
| 确定性来源 | 脚本计算（树、语言、依赖、git 统计），零 LLM | 脚本取数（API），但**结论全由 LLM 综合** |
| 是否依赖外部搜索 | 否 | 是（第 2、3 轮的 `web_search`/`web_fetch`） |
| 覆盖的数据 | 源码事实 | 时间线、活跃度、竞品、社区情绪 |
| 最大缺陷 | 引用只验路径存在（6.1） | 无来源类型标记（5.8） |

两者的**唯一交集**是 GitHub API 取数。这个交集必须按下面的方式消解：

1. **只保留一个 Collector**。UPSTREAM-01 的 `github_client.py` 已被判 `REJECT`（理由：平台已有认证 `gh`，自带 token 通道会制造第二套凭据面）。UPSTREAM-02 的 `github_api.py` 必须判同样的结果，理由相同。
2. **两条流水线共用同一个 Collector 的同一份输出**。UPSTREAM-01 需要的（元数据、树、语言、依赖清单、commits 首页）与 UPSTREAM-02 需要的（releases、tags、issues、PRs、contributors、commit activity）都是同一个 API 面的子集，没有理由调用两次。
3. **事实只计算一次**。`stars`、`contributor_count`、`open_issues` 这类数字属于 Collector 的确定性输出，两个模块都只能**读**，不能各自重算——否则就是 UPSTREAM-01 最忌讳的「LLM 重算事实」，只是换成了「两个模块各算一遍」。
4. **来源类型的边界**：Collector 产出的一切是 `source_type: github_api`；README 是 `readme_claim`；网络文章是 `external_web`；LLM 的归纳是 `inference`。UPSTREAM-02 的独特价值正是后三类，因为 UPSTREAM-01 根本不出这四类。**互补关系 = 确定性事实 vs 带来源的叙述**，不是「两个分析器」。

一句话总结边界：UPSTREAM-01 回答「这个仓库内部是什么」，UPSTREAM-02 回答「这个仓库在外面是什么、走到哪一步了」。两者共用同一套事实底座，但绝不在同一层产出结论。

## 6. 能力矩阵与四档判定

判定标记：`REUSE` 可直接搬用；`ADAPT` 借鉴后必改；`REIMPLEMENT` 只取思想重写；`REJECT` 明确不用。

硬性约束（Human 指令）：**SourceLore 只允许一个统一的 GitHub 数据采集入口**。以下每一行凡涉及取数，都流入同一个 Collector。

| 能力 | 上游实现位置 | 判定 | 理由与证据 |
|---|---|---|---|
| GitHub 端点清单与取数语义 | `scripts/github_api.py` L101-230（`get_repo_info`/`get_readme`/`get_tree`/`get_file_content`/`get_languages`/`get_contributors`/`get_recent_commits`/`get_issues`/`get_pull_requests`/`get_releases`/`get_tags`/`search_issues`/`get_commit_activity`/`get_code_frequency`） | **ADAPT** | 端点是事实、路径正确、`Accept: application/vnd.github.raw` 的用法正确，可作 Collector 的端点规格表。必须重写的是它周边的每一样东西：全部改走平台 `gh api`（不新建 token 通道）、强制多页遍历、检查 `trees.truncated`、暴露 `since`+`until`+`path` 过滤。 |
| `get_tree` 用 `HEAD` 让服务端解析默认分支 | L114-125 与其 docstring L119-121 | **REUSE** | 唯一一处设计得对的地方：不硬编 `main`/`master`，交给服务端解析。但**只能用于「解析默认分支名」这一次**，解析完必须立刻钉 SHA；把 `HEAD` 用于后续取文就是缺陷 D8。 |
| 原始内容直取（raw accept） | L150-152、L127-137 的 `accept="application/vnd.github.raw"` | **REUSE** | 取 README 与单文件正文的正确方式，避免 base64 解码环节。Collector 直接沿用，但 ref 必须是固定 SHA。 |
| `requests` 为可选依赖的降级结构 | L7-19 的 `try: import requests` + `RequestsFallback` | **ADAPT** | 结构思想可用（不让单一依赖阻断运行），但 Collector 本身不联网时更该走 `gh api` 子进程，`urllib` 回退面留着也是第二套通道。取其「优雅降级」思想，弃其双通道实现。 |
| 失败必须是异常而非字符串 | L53-61 `GitHubAPIError` 及其 docstring 记录的历史回归 | **REUSE** | 这条判断被上游自己的缺陷史证明是对的（"a rate-limited run and a missing README looked alike"）。Collector 的契约要写死：任何取数失败必须抛出携带 HTTP 状态与 endpoint 的异常，禁止把失败写进数据通道。 |
| 分页遍历 + 短页终止 | `get_issues` L186-194 的 `while` 循环 | **ADAPT** | 循环本身可借，但 `if len(items) < limit: break` 是错的——GitHub 固定每页返回 `per_page` 条，过滤掉 PR 后靠 `limit` 比较会提前退出（D4）。正确判据是「本页返回条数 < **per_page**」或「`Link` 无 `rel="next"`」。 |
| Issue 排除 PR 的语义 | L192 `if "pull_request" not in item` | **REUSE** | GitHub 的 `/issues` 混排 PR 是被反复踩的坑，上游为此专门发过修复 commit `5ca17829be`。语义直接沿用。 |
| 摘要聚合 `summarize_repo` | L257-312 | **REJECT（照搬）／REIMPLEMENT（思想）** | 明确不能用：`except Exception` 三处吞异常（D7）、`contributor_count` 双调用且截断到 100（D5）。但「每个仓库产一个扁平的摘要对象供下游直接消费」这个想法值得保留，重写为 Collector 的确定性输出，缺失值用显式 `unavailable` 原因而非 `"N/A"`。 |
| 树格式化 `format_tree` | L232-255 | **REJECT** | `"\n".join(lines[:100])` 静默截断且无任何标记（D2），`max_depth=3` 之外静默丢弃。UPSTREAM-01 的 D4（树截断静默丢子树）已经让我们决定必须显式列出未覆盖项；这里更差，连 `truncated` 标志都没有。Collector 需要的是结构化树，不是给人看的缩进字符串。 |
| 四轮研究流程 | `SKILL.md` L10-15、L61-75 | **REIMPLEMENT** | 分轮、Broad-to-Narrow 的探索顺序是对的（先建骨架再挖细节），但它只是散文，没有状态、没有交接、没有终止判据。SourceLore 需要把它实现成显式状态机：每轮的输入契约、产物 schema、预算、以及「本轮信息不足以进入下一轮」的退出路径。 |
| 查询策略 Broad to Narrow | `SKILL.md` L19-28 的查询模板序列 | **ADAPT** | 模板本身可用（`"{topic} overview"` → `"{topic} architecture"` → `"{topic} issues"`），但必须补上去重与规范化，否则「三角验证」会被镜像站击穿。 |
| 五层来源优先级 | `SKILL.md` L30-35 | **ADAPT** | 分层的直觉正确（官方 > 博客 > 新闻 > 社区 > 社交）。必须数字化为可执行权重，并为每一层给出**可判定的入层规则**（什么叫 "verified media outlet" 必须有定义或白名单）。 |
| 报告 9 节结构 | `SKILL.md` L77-89 + `assets/report_template.md` | **ADAPT** | 节的划分（Metadata / Executive Summary / Timeline / Analysis / Metrics / Strengths & Weaknesses / Sources / Confidence / Methodology）覆盖面合理，可作为 SourceLore 生态报告骨架。但必须去掉固定基数（D10）、去掉无条件 `Status: Complete`、把 `Confidence` 从百分比换成「证据明确列出的可核查条件」。 |
| 模板分桶的来源清单 | `report_template.md` L139-155（Primary / Media / Academic-Technical / Community） | **ADAPT** | 这是全套资产里最接近「来源类型标记」的东西，思想正确。必须升级为结构化字段（`source_type` + `retrieved_at` + `commit_sha`），而不是四个 markdown 小节。 |
| 置信度三档百分比 | `SKILL.md` L123-131、模板 L159-168 | **REJECT** | 未校准的数字（见 5.9）。SourceLore 的置信度必须可机械复核：要么是「N 个独立来源、其中 M 个是 primary」这样的可数陈述，要么是「未验证」。绝不输出看起来精确的百分比。 |
| 强制内联引用规则 | `SKILL.md` L146-152 的 "CRITICAL" 与 L156-168 好/坏示例 | **ADAPT** | 强制引用的纪律正确，示例教学的方式也好用。但它是祈使句，无机械校验。SourceLore 必须把这件事从提示词搬到校验器（这正是 UPSTREAM-01 D1 与本源 5.8 合并后的必然要求）。 |
| Mermaid 图表硬要求 | `SKILL.md` L91-121（Gantt / flowchart / pie 三套字面模板） | **REJECT** | 为了产出图表而要求图表：`report_template.md` L74-83 的 `flowchart TD` 固定 4 节点，与真实架构无关时也必须填。这是「形式驱动的虚构」的直接源头之一。图表应由数据触发，不应被模板要求。 |
| 自建 GitHub REST 客户端 | `scripts/github_api.py` 全文（自带 `GITHUB_TOKEN`、`BASE_URL`、`_get`） | **REJECT** | 与 UPSTREAM-01 对 `github_client.py` 的判定完全一致，且 Human 指令明文禁止第二个客户端。平台侧已有认证 `gh api`；再自带一套就是第二套凭据面、第二套配额口径、第二个故障点。 |

统计：本表共 **18 项**能力，`REUSE` 4 项（C02、C03、C05、C07）、`ADAPT` 8 项（C01、C04、C06、C11、C12、C13、C14、C16）、`REIMPLEMENT` 1 项（C10）、`REJECT` 5 项（C08、C09、C15、C17、C18）。

其中 `summarize_repo`（C08）是「照搬判 REJECT / 思想判 REIMPLEMENT」的混合判定，矩阵中只记 REJECT 一票以免重复计数；它「每个仓库产一个扁平摘要供下游消费」的思想，在第 8 节的融合设计里以重写形态保留。

## 7. 缺陷清单（逐条带证据）

严重度：`blocker` = 会静默产出错误知识，必须在任何实现之前修复；`high` = 会导致数据缺失或误判；`medium` = 影响可用性；`low` = 代码卫生。

### D1（blocker）全部取数都是单页，无法支撑「完整时间线」

- `get_pull_requests` L198-205、`get_releases` L207-211、`get_recent_commits` L149-164、`get_contributors` L143-147 全部只有一次 GET，`per_page=min(limit,100)`。
- 而 `SKILL.md` L74-75 要求 "Analyze commit history for timeline"，`report_template.md` L38-56 要求 "**Complete** Chronological Timeline"。
- 后果：报告的「完整时间线」实际建立在一页切片上，且**报告里没有任何地方说明只有一页**。这是本文档判定的最重要缺陷：它让「看起来很完整的报告」与「实际看到的数据量」彻底脱钩。

### D2（blocker）`format_tree` 静默截断到 100 行且丢弃深层路径

```python
return "\n".join(lines[:100])  # Limit output
```

- L255。截断无标记、无计数、无省略号。
- 同时 L243 `if depth < max_depth:` 把 `max_depth=3` 之外的所有路径直接丢弃，也不记录。
- 后果：一个 500 文件的仓库呈现为 100 行，LLM 据其判断「项目结构简单」。这属于 5.9 里「虚假精准度」的另一种形态——**虚假的简洁**。

### D3（high）`get_issues` 的短页判据错误，PR 密集仓库静默少返回

- L192 `if len(items) < limit: break`。
- GitHub 每页返回 `per_page` 条（此处等于 `limit`），但 L191 先过滤掉 `pull_request` 条目，`issues` 的增长量小于 `items` 的长度。判据应比较 `len(items) < per_page`，实际比较了 `len(issues) 相关` 的量纲错位版本：当一页里 PR 占多数时，`issues` 累积远慢于 `limit`，循环会继续翻页直到取满或页尽——但一旦某页因过滤后「看起来短」就 break，剩余页再也取不到。
- 这正是 commit `5ca17829be`（"exclude pull requests from GitHub issue research"）引入的逻辑。修复一个问题（PR 混排）时引入了另一个（分页提前终止），说明该修复没有测试覆盖。

### D4（medium）`labels` 参数接收但调用方永不传值

- `get_issues` 签名 L171 有 `labels: Optional[str] = None`，L186-187 有 `if labels: params["labels"] = labels`，但 `commands` L336 的 lambda 是 `api.get_issues(owner, repo)`，永远走默认值。
- 后果：按 label 过滤 issue 的能力存在但不可达，同 `get_tags` 等四个死代码方法一样，属于「写了没接线」。

### D5（high）`contributor_count` 双调用 + 静默截断到 100

```python
contributors = self.get_contributors(owner, repo, limit=1)
# GitHub returns Link header with total, but we approximate
summary["contributor_count"] = len(self.get_contributors(owner, repo, limit=100))
```

- L292-296。`contributors` 变量绑定后从未使用（第一次调用的结果被丢弃）；注释承认是近似但输出字段名为 `contributor_count`，读起来是精确计数。
- 后果：300 贡献者的仓库报 100。多消耗 1 次 API 配额，换来错误数字，且报告里无标注。

### D6（high，已被上游部分修复）失败曾被写进数据通道

- `GitHubAPIError` docstring L53-61 自述：内容读取器曾返回 `"[README not found: HTTP 404]"` 这样的字符串，使得「限流运行」与「缺失 README」在 stdout 上无法区分，退出码也相同。
- 修复方式正确（改抛异常）。**但同文件 L287、L297、L311 的 `except Exception:` 把这条纪律又破了**：`summarize_repo` 仍在把异常吞成 `{}`/`"N/A"`/`None`。
- 判据：这是一个修复不彻底的缺陷，其残留部分（D7）必须按 blocker 对待。

### D7（blocker）`summarize_repo` 用 `except Exception` 吞掉取数失败，不区分「失败」与「空」

- L287-289：`languages` 失败 → `{}`
- L291-298：`contributor_count` 失败 → `"N/A"`
- L300-312：`latest_release` 失败 → `None`
- 三处都是裸 `except Exception`，既不记录异常类型，也不记录 HTTP 状态，也不让调用者知道发生了降级。
- 后果：限流、无权限、仓库不存在、真没数据，在输出上**四种情况全都长一样**。下游 LLM 无法据此降级置信度。这与 D6 的 docstring 描述的缺陷是同一个病，只是换了个位置。

### D8（medium）`get_tree` 默认浮在 `HEAD` 上，未固定 SHA

- L114-125，`branch: str = "HEAD"`，`commands` L331 调用时不传 branch。
- `HEAD` 的语义正确（让服务端解析默认分支，优于硬编码 `main`），但**解析结果没有被固定下来**。四轮研究跨多次调用，若期间上游推送（本仓 `pushed_at` 与审计时刻只隔数小时），各轮看到的是不同 commit 的树，而输出里没有任何 SHA 可供对账。
- 对照：UPSTREAM-01 的 6.2 是同类问题（取文用分支而非 SHA），已在那边判为必须修复项。这里是同一模式的第二次出现。

### D9（medium）无限流、无重试、无缓存

- `grep -ci` 实测：`retry`=0、`sleep`=0、`backoff`=0、`Retry-After`=0、`etag`/`ETag`/`If-None-Match`=0、`x-ratelimit`/`X-RateLimit`=0。
- 唯一的时间防护是 `timeout=30`（L45、L94）。
- 后果：单次 5xx 即整条命令失败；重复取同一端点（四轮流程里必然发生）每次都全额消耗配额；匿名模式（无 `GITHUB_TOKEN`）下限额 60 次/小时，而这种用法极易触顶，触顶后错误信息只是一句 `HTTP 403`。

### D10（high）模板的固定基数与无条件 `Status: Complete`

- `report_template.md` L38-56 恰好 3 个阶段；L60-70 恰好 2 个分析节；L87-101 恰好 3 行指标；L105-117 恰好 2 个竞品槽位（`{COMPETITOR_1}`、`{COMPETITOR_2}`）；L74-83 的 `flowchart TD` 固定 4 节点；L192 无条件 `**Status:** Complete`。
- 后果：主体有 5 个阶段或 1 个竞品时，模板没有「不适用」的合法出口。这是一条**结构性激励**：为了填满格子而虚构对称，比承认不确定性更省力。它不会被写成谎言，会造成系统性过度自信。

### D11（low）四个死代码方法

- `search_issues`（L219）、`get_tags`（L213）、`get_commit_activity`（L224）、`get_code_frequency`（L228）均不在 `commands` 字典（L329-338 共 10 项，已逐一 grep 确认 0 命中）。
- 讽刺之处：这三个「活跃度/版本/检索」能力恰好是 5.5 里判断维护状况所必需的，写了却不可达。

### D12（low）无测试、无依赖声明、无配置

- 子树仅 3 个 blob，无 `test*`、无 `requirements*`、无 `pyproject.toml`、无任何 `.json`/`.yml`。
- 后果：D3、D5 这类逻辑错误没有任何回归防线——D3 是在一次修复 commit 里引入的，这正是没有测试的直接代价。

## 8. SourceLore 融合设计

### 8.1 统一 Collector 契约（硬约束的落地方式）

Human 指令：**只允许一个统一的 GitHub 数据采集入口**。设计如下：

```
SourceLore Collector（唯一）
  ├── 传输：平台已认证的 `gh api`（不新建 token 通道，不设 GITHUB_TOKEN 依赖）
  ├── 输入：{repo, ref: full_sha | None}
  ├── 固定：ref 为 None 时先解析默认分支 → 立即钉成完整 SHA → 之后一切按该 SHA 取
  ├── 分页：一律翻页至 Link 无 next 或短页（短页判据比 per_page，不比 limit）
  ├── 截断：检查 trees.truncated，遇 true 必须显式登记未覆盖路径，禁止静默
  ├── 失败：抛 GithubFetchError{endpoint, http_status, attempt}，禁止写入数据通道
  ├── 缓存：按 (endpoint, params, sha) 落 cache/，命中不回源
  └── 输出：确定性事实层（JSON），每条含 source_type: "github_api" + retrieved_at + commit_sha
```

两个模块（UPSTREAM-01 的源码分析、UPSTREAM-02 的生态研究）**都只从这个 Collector 读**。任何一个模块自己发 HTTP 请求，即为违约。

对照本审计的 4 个 REJECT 项：`github_api.py` 的客户端层、`summarize_repo` 的吞异常聚合、`format_tree` 的截断串、置信度百分比，全部不在 Collector 的出口上出现。

### 8.2 生态研究知识的产品形态

UPSTREAM-02 的产物必须是**带来源证据的生态研究知识**，而不是重复的源码分析报告。具体为：

| 知识单元 | 内容 | 来源类型 | 与 UPSTREAM-01 的边界 |
|---|---|---|---|
| 生态位 | 该项目在同类方案中的位置、竞品清单 | `external_web` + `inference` | 01 不出 |
| 时间线 | 关键版本、里程碑、事件（带日期与出处） | `github_api`（releases/tags/commits）+ `external_web` | 01 只出 git 统计，不出事件叙事 |
| 活跃度画像 | commit/PR/issue 的时间序列统计 | **只用 Collector 的确定性输出** | 01 不覆盖 |
| 社区信号 | 讨论集中的痛点、反复出现的诉求 | `external_web` + `inference`，必须标 infer | 01 不覆盖 |
| 维护状况 | 响应时长、stale 比例、发布节奏 | `github_api` 计算 | 01 不覆盖 |
| 项目定位描述 | README 自称是什么 | `readme_claim`（**明确标为声明，非事实**） | 01 会读 README 但归入源码事实 |

关键纪律：**`readme_claim` 与 `github_api` 是两个不同的 `source_type`**，在报告里必须视觉可分。这正是上游 5.8 缺失、而我们必须补上的一层。

### 8.3 DeepSeek-V4.1 Flash 的低 token 分阶段研究计划

前提：不假设所有外部搜索工具可用。缺搜索时的降级路径必须写死。

**阶段 R0 — 固定与事实（零 LLM，零搜索）**

- Collector 按 `gh api` 解析默认分支 → 钉 SHA。
- 批量取：repo 元数据、languages、releases、tags、contributors 全页、commits（近 12 个月）、issues/PRs（按 state 分桶，全页）。
- 产出 `ecosystem_facts.json`。**此文件由脚本生成，LLM 只读不算**（沿用 UPSTREAM-01 的事实契约纪律）。
- token 成本：0。这一步结束后，无论后续搜索是否可用，活跃度/维护/版本三项已有确定性答案。

**阶段 R1 — 骨架（1 次 LLM 调用，零搜索）**

- 输入：`ecosystem_facts.json` 的压缩摘要（仅计数、时间序列、版本列表、Issue/PR 标题的词频 top-N）。
- 产出：研究缺口清单——哪些问题**只能**靠外部来源回答（生态位、社区情绪、竞品）。
- token 成本：约 4k 输入 / 1k 输出。不搜索也能出这一阶段。

**阶段 R2 — 定向外部检索（有条件，可整段跳过）**

- 若 `web_search` 可用：仅执行 R1 列出的缺口查询，每缺口最多 2 条查询，总计上限 6 条。
- 每条结果立即规范化（去 tracking 参数、按 canonical URL 去重），落 `external_sources.json`。
- **若不可用：直接跳到 R3，把缺口原样写进报告的「未覆盖」节。不编造、不推断替代。**
- token 成本上限：约 6k。

**阶段 R3 — 交叉验证与冲突登记（1 次 LLM 调用）**

- 输入：`ecosystem_facts.json` 的事实 + `external_sources.json` 的片段。
- 产出：带 `source_type` 的断言列表；每条断言标 `verified`（≥2 个独立来源且至少 1 个 primary）或 `single_source` 或 `inferred`。
- **冲突的断言必须并列保留，不得由模型二选一。**
- token 成本：约 8k。

**阶段 R4 — 渲染（1 次 LLM 调用，或纯脚本）**

- 由渲染器按 schema 输出 markdown；基数由数据决定，模板不设固定槽位。
- 报告头部强制包含：`commit_sha`、`retrieved_at`、`collector_version`、`coverage`（哪些节有数据、哪些跳过及原因）。
- 状态字段取值只能是 `complete` / `partial` / `facts_only`（无外部来源时）之一，**禁止无条件 Complete**。
- token 成本：约 6k。

总计 LLM 调用 3–4 次、搜索 0–6 次、token 约 20k 上限，且**在完全无搜索能力的条件下仍能产出 `facts_only` 级别的可用知识**（R0+R1+R4 全走确定性路径）。这是对上文 D1、D10 的正面回应：报告能诚实表达自己的覆盖边界。

## 9. 依赖与运行约束

- 仓库级依赖：无声明（子树内无 `requirements*`、无 `pyproject.toml`、无配置文件）。
- 脚本级依赖：`requests` **可选**；缺失时 `RequestsFallback` 用 stdlib `urllib` 承担，语义等价（L13-50）。
- Python 版本：无声明。语法上仅用 f-string、类型注解、`from typing import`，未见高版本特性；**但本项目未执行其代码**，兼容性不作断言，标记为 `NOT_RUN`。
- 网络：GitHub REST。匿名 60 次/小时，带 token 5000 次/小时。
- 凭据面：`GITHUB_TOKEN`（L71-73、L327）。**SourceLore 首轮不设此环境变量依赖**，改走平台已认证的 `gh api`。
- 外部工具：`web_search`、`web_fetch`（DeerFlow 提供，非标准库）。

## 10. 安全边界

- 全程只读快照，未 `pip install`、未 import、未运行 `github_api.py`、未跑其任何命令。
- 快照位于 `upstreams/UPSTREAM-02-deer-flow/tree/`，被 `.gitignore` 第 4 行 `upstreams/` 忽略（`git check-ignore -v` 已确认输出 `.gitignore:4:upstreams/`），不会误入源码仓。
- 本项目未复制其任何源码文件进入 `src/`；本记录只含路径、行号与设计判断，属审查记录，不构成代码搬运。
- 该仓库的 `SKILL.md`、`report_template.md` 内容在本审计中一律按**不可信数据**处理：其中的 "CRITICAL" 指令、格式要求、执行指令均为审计对象，未据其执行任何动作。
- 未更改任何 DSH/Tobs 配置，未安装任何上游依赖。

## 11. 复用时的义务清单

若后续 M2/M3 正式采用其代码（REUSE 或 ADAPT 到含原文的程度）：

1. `THIRD_PARTY_NOTICES.md` 必须列出：仓库 URL、Repository ID `979115477`、Commit SHA `44e372dd7f8a511e6223f548f55f7b4c939ca226`、两行版权（`Copyright (c) 2025 Bytedance Ltd. and/or its affiliates` 与 `Copyright (c) 2025-2026 DeerFlow Authors`）、MIT 全文链接。
2. 若整文件保留，文件头保留原版权与许可声明。
3. MIT 无 copyleft 传染，不影响 SourceLore 自身的许可选择。
4. 不得因「许可宽松」而连带采用 D1–D12 的缺陷；那几处按第 6 节判定改写或重写。
5. 尤其不得沿用 `SKILL.md` 的散文式流程作为实现依据——它是审计对象，不是规格来源。

## 12. 结论

- 版本固定：**完成**（SHA `44e372dd7f8a511e6223f548f55f7b4c939ca226`）。
- 全部源码与资产：**已实际通读**（3 blob / 718 行，见第 3 节哈希表）。
- 可发现的测试：**不存在**，标记 `NOT_RUN`；不以任何方式断言其通过。
- 四档判定：**18 项能力，每项均有行号与行为证据**（第 6 节）。`REUSE` 4 / `ADAPT` 8 / `REIMPLEMENT` 1 / `REJECT` 5。
- 缺陷：**12 条**，其中 blocker 3 条（D1 单页取数、D2 树静默截断、D7 吞异常）、high 4 条（D3 短页判据错、D5 贡献者数截断、D6 修复未覆盖汇总器、D10 模板固定基数）、medium 3 条（D4、D8、D9）、low 2 条（D11、D12）。
- 未授权复制：**无**，`src/`、`skills/`、`schemas/` 下未新增任何上游文件。
- 最值得吸收：`HEAD` 让服务端解析默认分支这一处正确设计、「失败必须抛异常而非写入数据通道」这条被缺陷史证明的纪律、Issue/PR 混排的处理语义、分桶来源清单的思想、「每个仓库一个扁平摘要供下游直接消费」的形态。
- 必须自建：统一 Collector（含多页、截断登记、失败异常、按 SHA 缓存）、`source_type` 四分类标记、去重与 URL 规范化、可机械复核的置信度、无固定基数的报告 schema、显式 `partial` 状态。
- 与 UPSTREAM-01 的关系：**互补而非重复**。01 出确定性源码事实，02 出带来源的生态叙述，两者共用同一个 Collector，事实只算一次。
