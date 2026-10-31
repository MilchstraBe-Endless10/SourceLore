# UPSTREAM-01 审计记录：jeannie-jy/repo-analyzer-skill

> 本文件是 M1 第一源的形式化审计记录。所有路径均可从冻结快照复核。
> 快照目录：`upstreams/UPSTREAM-01-repo-analyzer-skill/tree/`（Git 忽略，只读使用，未执行其任何代码）。

## 1. 上游版本固定

| 项 | 值 | 证据来源 |
|---|---|---|
| 仓库地址 | `https://github.com/jeannie-jy/repo-analyzer-skill` | 总控提示词 §C 第 56 行原文 |
| GitHub Repository ID | `1341818258` | `gh api repos/jeannie-jy/repo-analyzer-skill` |
| 默认分支 | `main` | 同上 `default_branch` |
| 固定 Commit SHA | `b8c000f60c03003cbb08e6737b2e8193289904ea` | `gh api repos/.../commits/main` |
| Commit 时间 | 2026-08-31T13:46:40Z | 同上 `commit.committer.date` |
| Commit 标题 | `feat: multi-model judge ensemble — JUDGE_* second provider, median combine` | 同上 `commit.message` |
| 仓库 `pushed_at` | 2026-08-31T13:53:21Z | 同上 |
| 可见性 / 体积 | `public` / 358 KB | 同上 |
| 快照方式 | tarball `repos/.../tarball/<SHA>`，`--strip-components=1` 展开 | `sha256: fa0f923e05b53553cc02d61baa0190e669ba65b2f207cc7b0ac8cd3b5b39d06f`（165703 B） |
| 快照文件数 | 104 | `find tree -type f | wc -l` |

版本在读取源码之前固定，审计全程只读该 SHA 的冻结副本，不跟随分支漂移。

## 2. 许可证结论

| 项 | 结论 | 证据 |
|---|---|---|
| 许可证类型 | MIT | `LICENSE` 第 1 行 `MIT License`；GitHub API `license.spdx_id = "MIT"`，`key = "mit"` |
| 版权人 | `Copyright (c) 2026 Jingyu Wang` | `LICENSE` 第 3 行 |
| 声明作者 | `jeannie-jy` | `pyproject.toml` 的 `authors` |
| 复用条件 | 允许 use / copy / modify / merge / publish / distribute / sublicense / sell | `LICENSE` 第 5–12 行许可正文 |
| 强制义务 | 在软件的**所有副本或实质性部分**中保留上述版权声明与许可声明 | `LICENSE` 第 14–16 行 |
| 免责 | AS IS，无任何明示或默示担保 | `LICENSE` 第 17–20 行 |

判定：**许可允许我们改编并复用其代码**，条件是保留版权与许可声明。两种版权署名（GitHub 账号 `jeannie-jy` 与真实姓名 `Jingyu Wang`）都记录在案，履行义务时二者都引用。
因此 UPSTREAM-01 的策略可以是 REUSE/ADAPT，而非只能 REIMPLEMENT。履行方式：在 `THIRD_PARTY_NOTICES.md` 中如实列出本仓库、Commit SHA、版权行与 MIT 全文链接，并在被复用文件（若整文件保留）顶部保留原声明。

## 3. 实际审查范围

逐文件读取（非凭 README 或目录名推断）：

| 类别 | 实际读取的文件 |
|---|---|
| 入口契约 | `SKILL.md`（187 行，全文） |
| 包配置 | `pyproject.toml`、`.env.example`、`.gitignore` |
| 许可证 | `LICENSE`（全文 21 行） |
| 数据契约 | `schemas/analysis_report.schema.json`（10947 B，13 个顶层必需键，逐字段核对 `evidence` 定义） |
| 核心源码 | `src/repo_analyzer/pipeline/evidence.py`（全文 77 行）、`context/code_sampler.py`（全文 166 行）、`llm/base.py`（全文 38 行）、`llm/__init__.py`、`llm/openai_client.py`（前 60 行）、`pipeline/analyze.py`（常量与修复循环段）、`pipeline/facts.py`（SHA 段）、`models.py`（类结构）、`extract/tree.py`（截断处理）、`extract/entrypoints.py`（启发式规则与置信度）、`extract/dependencies.py`（monorepo 注释）、`github_client.py`（取文与 ref 处理）、`report/render.py`（行号使用情况） |
| 自述设计文档 | `docs/ARCHITECTURE.md`（索引性引用） |
| 提示词资产 | `skill/prompts/`（4 个 md：`architecture.md`、`code-flow.md`、`risk-analysis.md`、`contribution.md`） |
| 测试 | `tests/unit/` 24 个测试文件 + `fake_client.py` + `fake_llm.py`；统计得 **255 个 `def test_`** |
| 评估 | `evals/cases/`（5 个真实仓库 gold 集）、`evals/results/baseline.md`、`baseline.json` |
| 示例产物 | `examples/reports/pallets-flask/`（`analysis.json`、`report.json`、`report.md`、`sample_manifest.json`） |

规模：`src/` 共 31 个 Python 模块、5247 行；本项目未安装、未运行、未导入其任何代码。

## 4. 架构与分层（实测）

- 分层方向 `extract/` → `pipeline/` → `report/`，`llm/` 通过 `llm/base.py` 的 `LLMClient` Protocol 隔离，仅 `cli.py` 与 `evals.py` 直接引用具体客户端。
- 事实层（`extract/*`）：元数据、树、语言、依赖、入口点候选、git 统计、文件统计、README 摘录，全部纯 Python 计算，产出 `repo_facts.json` 作为**唯一事实契约**。
- 判定层（`pipeline/*`）：`facts.py` 组装事实，`analyze.py` 组织推理与修复循环，`evidence.py` 做引用校验。
- 呈现层（`report/*`）：`schema.py` 校验、`render.py` 出 Markdown、`digest_facts.py` 压缩事实、`labels.py` 文案。
- 运行时依赖为零（`pyproject.toml` 无 `dependencies`，只用 `urllib` / `tomllib` / `dataclasses`）；`requires-python = ">=3.11"`；CLI 入口 `repo-analyzer = "repo_analyzer.cli:main"`。

## 5. 能力矩阵与四档判定

判定标记：`REUSE` 可直接搬用；`ADAPT` 借鉴后必改；`REIMPLEMENT` 只取思想重写；`REJECT` 明确不用。

| 能力 | 上游实现位置 | 判定 | 理由与证据 |
|---|---|---|---|
| 事实优先分层（抽取层零 LLM） | `src/repo_analyzer/extract/`（`tree.py`、`languages.py`、`dependencies.py`、`entrypoints.py`、`file_stats.py`、`git_stats.py`） | **REUSE** | 与 §D 强制项「确定性收集元数据/树/语言/依赖/入口」完全同构；`pyproject.toml` 零运行时依赖，`requires-python >=3.11` 与本机 3.14.8 兼容。整目录搬用并按文件保留 MIT 声明即可。 |
| 事实单一契约 `repo_facts.json` | `pipeline/facts.py:175` `"ref_sha"` 汇总体；`SKILL.md` L83 明示「唯一契约」 | **ADAPT** | 契约思想正确，但 `ref_sha` 取自 `GET commits?per_page=1&sha=branch`（`facts.py:93-97`）之后**并未把该 SHA 用于后续取文**：`fetch_file_content` 的 `contents?ref=` 传的是 `branch` 变量（`github_client.py:217`）。即事实的 SHA 与所读内容可能来自不同 commit。必须改为固定 SHA 后全程以 SHA 取文。 |
| 引用存在性校验 | `pipeline/evidence.py`（77 行全文） | **ADAPT** | 核心缺陷详见第 6 节。集合成员判定本身要保留，但必须升级为「路径 + 行号区间 + 内容哈希 + 该行内容确实支撑结论」三重校验。 |
| 预算受限代码采样 | `context/code_sampler.py`（166 行） | **ADAPT** | 分级预算（入口点 50%、单文件 25%、其余按最大文件补齐）、`skipped` 记录原因、`to_manifest()` 不落文件内容——这套设计好用。缺陷：内容只进 prompt 不进产物，事后无法复核「模型当时看到了什么版本」；需增加 `content_sha256` 入 manifest。 |
| 入口点启发式（带规则与置信度） | `extract/entrypoints.py`（`kind` + `confidence` + `heuristic` 三件套，`_add` 去重且强规则覆盖弱规则） | **REUSE** | 每条候选都写明是哪条规则命中的（如 `"**/manage.py" → cli 0.90`），完全符合 §F「证据要可追」。`tests/unit/test_extract_entrypoints.py` 有 28 个测试覆盖，可信度高。 |
| LLM 供应商解耦 | `llm/base.py` `LLMClient` Protocol（`complete(messages, *, temperature, max_tokens) -> str`） | **REUSE** | 结构性 Protocol、消息为纯 dict，替换实现无需改动 pipeline。这正是把分析接到 DSH 当前模型上的接入点。 |
| 分节推理 + 修复循环 | `pipeline/analyze.py`（`MAX_REPAIR_ATTEMPTS = 1`、`MAX_PARSE_RETRIES = 2`、`_repair_messages`） | **ADAPT** | 修复次数有界、把违规条目回灌给模型，是合理工程；但要接入 DSH 则调用点需替换，且解析重试与网络重试分开这点要保留。 |
| 树截断的两种降级 | `extract/tree.py`（`truncated` 标志 + `MAX_TOP_LEVEL_DIRS_TO_EXPAND = 30` 回退展开根层与一级目录） | **ADAPT** | 降级思路正确且明示 `truncated` 给下游。30 个顶层目录的上限是硬编码，对大型 monorepo 会静默丢子树；需改为「按目录分片遍历 + 明确记录未覆盖子树清单」。 |
| Monorepo 支持 | `extract/dependencies.py:70` 注释称规则「match both the repo root and any subdirectory (monorepos)」；`extract/` 下有 `local.py` 支持本地路径 | **ADAPT（浅）** | 实测仅在**依赖清单识别**上考虑了子目录，即把任意深度下的 `package.json`/`pyproject.toml` 都收集起来。没有 workspace 根识别、没有按包聚合事实、没有跨包依赖图，`extract/tree.py` 的展开上限还会截断大仓。结论：**monorepo 支持等级 = 浅层清单级**，不足以支撑「多包产品能力」结论。 |
| 报告 Schema 与渲染 | `report/schema.py`（362 行）、`report/render.py`（329 行）、`schemas/analysis_report.schema.json` | **REUSE** | 13 个顶层键与「每节必带证据」的结构合理；`draft-07` 可用。但 schema 里 `evidence` 仅为 `array[string, minItems 1]`，不含行号/哈希字段，需扩字段（见第 6 节）。 |
| 提示词资产 | `skill/prompts/{architecture,code-flow,risk-analysis,contribution}.md` | **ADAPT** | 以知识资产（md）而非硬编码组装提示词的做法值得沿用（`llm/prompts.py:103 load_prompt_sections`）；具体措辞要按中文产出与本地模型重写。 |
| 评估基线（gold 集 + 确定性指标 + LLM-as-judge） | `evals/cases/`（5 仓）、`evals/results/baseline.md` | **ADAPT** | 确定性指标（结构命中、入口点 P/R/F1、grounding 比）零 LLM 成本，这部分直接可用。基线数据显示入口点召回曾在 `pallets/click` 上为 0.00，说明该指标对纯库项目敏感，不应当作单一验收门槛。judge 依赖外部 provider，接入 DSH 时要换成当前模型或先跳过。 |
| 外部 LLM API 直连（`LLM_API_KEY` / `LLM_BASE_URL`） | `llm/openai_client.py`、`config.py`、`.env.example` | **REJECT** | 与 §G M3「当前模型就是语义执行者，默认不需要 `LLM_API_KEY`」直接冲突。`openai_client.py` 的 HTTP 细节与我们无关；只需保留 `LLMClient` 接口形状。 |
| 多模型 judge 集成（median combine） | `evals.py`、`.env.example` 的 `JUDGE_*` | **REJECT（本项目首轮）** | 属 §D 明确非必需项，且引入第二个外部 provider 依赖。首轮闭环不做。 |
| 自建 GitHub REST 客户端 | `github_client.py`（226 行，urllib + 退避重试 + `Retry-After`） | **REJECT** | 平台侧已有认证 `gh`，再自带一个 token 通道会制造第二套凭据面与第二套配额口径。保留其**退避语义**作为设计参考（429/5xx 退避、限流给等待秒数后交给人），实现走 `gh api`。 |

## 6. 发现的问题（逐条带证据）

### 6.1 引用校验只验路径存在，不验内容是否支持结论 —— 最高优先级缺陷

`pipeline/evidence.py` 全文只有一种判定：

```python
tree_paths = {entry.path for entry in tree.entries}
verified = [p for p in citations if p in tree_paths]
```

- 校验对象仅限 `_PATH_KEYS = ("evidence", "related_files")` 两个 dict 键下的字符串；
- 判定方式是 Python 集合成员测试；
- **没有行号区间，没有内容哈希，没有「该文件内容是否支撑该结论」的任何检查，也没有把引用绑定到固定 Commit**。

对照总控 §F 的判据「只有路径存在不等于结论受到支持」，该实现恰好只做到前一半。上游自己在 `SKILL.md` L158-166 的 Iron rule 4 也承认「evidence must be direct … the eval judge flags indirect evidence」，即**把直接性判断交给了 LLM 评审判据**——那是模型评价，不是机械校验。

结论：这套校验可以拦住「编造不存在的文件」，拦不住「引用真实文件但结论与文件无关」。SourceLore 的 evidence 层必须自建（REIMPLEMENT 的部分）：路径 + 行号 + `content_sha256` + 结论文本与所引片段的对应关系，至少前四项可机械验证。

### 6.2 Commit SHA 未真正用于取文

`pipeline/facts.py:93-97` 请求 `repos/{repo}/commits?per_page=1&sha={branch}` 得到 `ref_sha`，写入事实契约第 175 行 `"ref_sha"`；但 `github_client.py:217` 的取文请求仍是 `contents/{path}?ref={branch}`，即分支名而非 SHA。分支在多次调用之间推进时，同一份 `repo_facts.json` 的 SHA 与样本内容会错位。SourceLore 必须做「解析 → 固定 SHA → 之后一切按 SHA」的硬性顺序（§D 强制项）。

### 6.3 代码采样未覆盖小体积核心模块

`context/code_sampler.py` 的三级候选是：入口点候选（按置信度降序）→ 清单文件 → `facts.files.largest_files`（按体积）。**没有任何按「结构重要性」的选取**：`__init__.py` 的导出面、`types.py`/`models.py` 这类只有几十行却是全局契约的模块，因为体积小几乎不可能进入 `largest_files` 名单，除非恰好被入口点规则命中。文件内注释（L22-25）也自承曾因 25% 单文件上限把 `src/flask/app.py` 挡在采样之外，只把入口点上限提到 50% 来缓解——这是**对单点问题打补丁**，不是结构性修复。

### 6.4 树截断时静默丢子树

`extract/tree.py:132` 起的回退策略只展开根层 + 前 `MAX_TOP_LEVEL_DIRS_TO_EXPAND = 30` 个一级目录（`tree.py:161` 的 `top_dirs[:30]`）。超出部分既不在条目里，也不在 `skipped` 里，只在树级别留一个 `truncated=True`。下游无论做依赖统计还是入口点检索，都会把「没扫到」当成「不存在」。SourceLore 需要显式的未覆盖子树清单，并在结论里降级置信度。

### 6.5 证据字段无法承载 §F 要求

`schemas/analysis_report.schema.json` 中所有 `evidence` 均为 `{"type":"array","items":{"type":"string"},"minItems":1}`——即**只能放路径字符串**。§F 要求的 `source_type` / `commit` / `line_start` / `line_end` / `content_sha256` / `retrieved_at` 无处安放。这是数据结构层面的限制，不能靠提示词弥补。

### 6.6 声明与实现的落差（需在融合时区分对待）

`SKILL.md` L13-17 宣称「deterministic work 全由 Python 完成，LLM 只做推理，每个引用在下游机械校验后才可发布」。就机械校验这一项而言，实际是集合成员测试（6.1）。其它宣称（事实不重算、入口点带规则）与实现一致，已核过 `extract/entrypoints.py`、`pipeline/facts.py`。

## 7. 依赖与运行约束

- 运行时依赖：无（stdlib only）。开发依赖：`pytest>=8`。
- Python：`>=3.11`（分类器声明 3.11、3.12）。本机 `python3` 为 3.14.8，语法层面兼容（`from __future__ import annotations`、`datetime.UTC` 等新式用法未见阻碍），但**本项目未执行其代码**，兼容性不作断言，标记为未验证。
- 网络：GitHub REST（未认证 60 次/小时，认证 5000 次/小时）与外部 LLM chat-completions 端点。
- 凭据面：`GITHUB_TOKEN`、`LLM_API_KEY`、（可选）`JUDGE_API_KEY`。**SourceLore 首轮不设这些环境变量依赖**。

## 8. 安全边界

- 全程只读快照，未 `pip install`、未 import、未运行其 `cli.py`、未跑其 `pytest`、未跑其 `evals`。
- 快照位于 `upstreams/`，该目录被 `.gitignore` 第 4 行忽略（`git check-ignore -v` 已确认），不会误入源码仓。
- 本项目未复制其任何源码文件进入 `src/`；本记录只包含路径、行数与设计判断，属审查记录，不构成代码搬运。
- 该仓库 README 与 `SKILL.md` 内容在本审计中一律按**不可信数据**处理，未据其执行任何动作。

## 9. 复用时的义务清单

若后续 M2/M3 正式采用其代码（REUSE 或 ADAPT 到含原文的程度）：

1. `THIRD_PARTY_NOTICES.md` 必须列出：仓库 URL、GitHub Repository ID `1341818258`、Commit SHA `b8c000f6…`、`Copyright (c) 2026 Jingyu Wang`、MIT 许可全文。
2. 若整文件保留，文件头保留原版权与许可声明。
3. MIT 无 copyleft 传染，不影响 SourceLore 自身的许可选择。
4. 不得因为「许可宽松」而连带采用 6.1–6.5 的缺陷；那几处按本文判定改写。

## 10. 结论

- 版本固定：**完成**（SHA `b8c000f60c03003cbb08e6737b2e8193289904ea`）。
- 核心源码与测试：**已实际审阅**（见第 3 节清单）。
- 四档判定：**每条均有文件路径与行为证据支撑**（第 5 节）。
- 未授权复制：**无**，`src/`、`skills/`、`schemas/` 下未新增任何上游文件。
- 最值得吸收：事实优先分层与零依赖抽取层、入口点「规则+置信度」可追设计、`LLMClient` Protocol 解耦点、预算受限采样。
- 必须自建：证据语义校验（行号+哈希+支撑关系）、SHA 硬固定的取文顺序、小核心模块采样、未覆盖子树清单。
