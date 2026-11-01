# SourceLore 交接文档

> 本文件是跨会话恢复的唯一入口。任何新会话第一件事就是读它。
> 最后更新：2026-10-31T09:58:00+08:00

---

## 一、现状

项目已初始化，M0 环境审计完成并通过 Gate。M1 尚未开始。

- 项目根：`/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore`
- 当前里程碑：**M0（已通过）**
- 当前任务：**M0-02 项目骨架与 Git 初始化（进行中，等待首个 commit）**
- 开发模型：`workbuddy/deepseek-v4.1-flash`（上下文 131072，务必小步走）

## 二、已通过的 Gate

| Gate | 判定 | 证据 |
|---|---|---|
| M0：可读取和安全写入指定目录 | PASS | `BASE_WRITABLE=YES`；骨架已创建；`git init` 成功 |
| M0：模型能运行最小工具实验 | PASS | bash / git / python3 venv / SQLite FTS5 / curl 全部实跑成功 |
| M0：DSH 技能路径有依据 | PASS | 用户级根 `<DSH_HOME>/skills` 经 Catalog 交叉验证；三个 skill Provider 已注册 |

## 三、最后一条真实命令与退出码

```
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' && git init -b main
```

```
Initialized empty Git repository in .../SourceLore/.git/
```

`exit=0`

## 四、本回合实际修改的文件

| 文件 | 说明 |
|---|---|
| `.gitignore` | 忽略 knowledge/ cache/ upstreams/ .dsh/skills/ 与 Python、密钥产物 |
| `.gitattributes` | LF 统一、二进制标注 |
| `docs/environment-audit.md` | M0-01 完整审计报告（实测数据） |
| `docs/platform-compatibility.md` | 平台兼容性矩阵与陷阱清单 |
| `progress/STATE.json` | 状态机初始值 |
| `progress/TASKS.json` | M0-01 DONE、M0-02 IN_PROGRESS、UPSTREAM-01~06 PENDING |
| `progress/HANDOFF.md` | 本文件 |

创建的目录骨架（按总控提示词 §E）：

```
src/sourcelore/{collection,evidence,lifecycle,storage}
skills/sourcelore/{references,scripts}
schemas docs tests progress reports/acceptance
knowledge cache upstreams .dsh/skills
```

## 五、测试

`NOT_RUN` —— M0 不含自动化测试，M2 才开始引入单元测试。审计类验证以真实命令输出为准，已在 `docs/environment-audit.md` 逐条记录。

## 六、Git HEAD

`NOT_COMMITTED` —— 仓库刚初始化，尚无 commit。

## 七、下一步

**M0-02 收尾**：完成首个基线提交，然后进入 M1 的 UPSTREAM-01。

M1 硬性约束（来自总控提示词 §G）：

- 六个上游**一次只处理一个**，每个都固定 Commit SHA
- 每个都要查 LICENSE / NOTICE / 文件头许可证声明
- 每个都要读 SKILL.md 与脚本，列出可复用能力与兼容性风险
- 逐个更新 `docs/upstream-manifest.json` 与 `docs/fusion-matrix.md`
- **严禁把六个 SKILL.md 原样拼接**
- 未到 M1 Gate 不得开始大规模融合编码

## 八、已知限制

1. **上下文 131072**：不能大段读上游源码，必须用脚本采事实 + 分页读取
2. **会话 cwd 不在项目根**：所有命令必须绝对路径或显式 cd
3. **路径含括号与中文**：shell 必须引号，Python 用 pathlib
4. **Skill 源码目录不是发现根**：M6 必须安装到发现根并用 Catalog 复验
5. **Tobs 会话 cwd 不是项目根**：M7 触发依赖用户级 skill 根，需专门验证
6. **上游 URL 待核实**：`TASKS.json` 中 UPSTREAM-01/03/04 的仓库地址是从记忆推测的，M1 必须先核实真实地址，核实不了就记录为待用户确认，不得凭空编造

## 九、恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' && git log --oneline -5 && python3 -m json.tool progress/STATE.json && python3 -m json.tool progress/TASKS.json | head -40
```

然后读 `progress/STATE.json` 的 `active_task`，继续该任务。

## UPSTREAM-01 完成（2026-10-31 12:15 +08:00）

**上游**：`https://github.com/jeannie-jy/repo-analyzer-skill`
Repository ID `1341818258` · 分支 `main` · Commit `b8c000f60c03003cbb08e6737b2e8193289904ea`（2026-08-31T13:46:40Z）
许可 MIT · `Copyright (c) 2026 Jingyu Wang`（账号 `jeannie-jy`）
快照：`upstreams/UPSTREAM-01-repo-analyzer-skill/tree`（104 文件，已被 `.gitignore:4 upstreams/` 忽略）

**记录**：`docs/upstream-audit-01-repo-analyzer-skill.md`（人读）+ `progress/UPSTREAM-01-audit.json`（机读台账）

**判定**：15 项能力 —— REUSE 4（事实优先分层、入口点规则+置信度、LLMClient Protocol、报告 schema/render）、
ADAPT 8（事实契约、引用校验、采样、修复循环、树截断、monorepo、提示词资产、评估基线）、
REJECT 3（外部 LLM API 直连、多模型 judge、自建 GitHub REST 客户端）。

**必须自建的六项缺陷**：
- D1(blocker) `pipeline/evidence.py` 只做集合成员测试 → 需 路径+行号+content_sha256+支撑关系
- D2(high) `facts.py:93-97` 记录 ref_sha 但 `github_client.py:217` 仍按 branch 取文
- D3(high) `code_sampler.py:94-118` 采样只看入口点/清单/体积，小核心模块结构性漏采
- D4(medium) `tree.py:161` 截断后仅展开前 30 个顶层目录，未覆盖子树无清单
- D5(medium) schema 的 `evidence` 只有 `array[string,minItems 1]`，放不下 commit/行号/哈希
- D6(low) `SKILL.md` 声称 4 节分别调用模型 + 每引用机械校验，实测为单次调用 + 存在性检查

**未执行**：未 pip install、未 import、未跑其 cli/pytest/evals；未复制任何上游源码进 `src/`、`skills/`、`schemas/`。

**下一步**：M1 其余上游（UPSTREAM-02 … 06）逐个「先固定 SHA 再读源码」。

## UPSTREAM-02 完成（2026-10-31 14:00 +08:00）

目标源：`bytedance/deer-flow`，子树 `skills/public/github-deep-research/`，钉在本仓库 `main` 的
`44e372dd7f8a511e6223f548f55f7b4c939ca226`（Repository ID 979115477，仅取该次提交的内容）。

怎么做的：认证 `gh api` 取元数据 → 全量枚举子树 blob（`files.tsv`：3 个 blob + 2 个 tree）→ 按完整
SHA 只读取回快照到 `upstreams/UPSTREAM-02-deer-flow/tree`（被 `.gitignore` 的 `upstreams/` 忽略）→
3 个文件 718 行逐行读完 → 反向 grep 做否定性证据核查 → 用三笔子树修复 commit 反查缺陷来源。
全程未安装、未 import、未执行任何上游代码。

最要紧的四条结论：

1. **四轮研究只是散文。** `SKILL.md` 里四轮就是四条 bullet，没有状态机、没有轮间交接 schema、
   没有终止判据。可以借鉴分轮与由广到深的顺序，但必须重写成显式流程。
2. **取数一次性，报告却声称完整。** `get_pull_requests` / `get_releases` / `get_recent_commits` /
   `get_contributors` 全部单页，`format_tree` 直接 `lines[:100]` 静默截断，而模板要求
   "Complete Chronological Timeline"。这是本子树最危险的地方：数据不全，但输出形态看起来是全的。
3. **失败被折叠成空数据。** `summarize_repo` 三处裸 `except Exception`，把限流、无权限、仓库不存在、
   真无数据四种情况统一降级成 `{}` / `"N/A"` / `None`。讽刺的是同文件的 `GitHubAPIError` docstring
   恰好记录了这类 bug 的历史，说明这条纪律没有被推广到全文件。
4. **来源类型完全缺失。** 引用只有标题和 URL，API 的 `stars: 84743` 与博客的「据说十万星」在结构上
   无法区分。这是「虚假精准度」的根，必须在数据结构层解决，靠提示词约束不了。

四档判定：18 项能力，`REUSE` 4 / `ADAPT` 8 / `REIMPLEMENT` 1 / `REJECT` 5。缺陷 12 条，其中
blocker 3 条（D1 单页取数、D2 树静默截断、D7 吞异常）。最值得吸收的是三处：用 `HEAD` 让服务端
解析默认分支（唯一设计正确处，但解析完必须立刻钉 SHA）、raw accept 直取文件正文、以及
「失败必须抛异常而不是写入数据通道」这条被上游自己缺陷史证明的纪律。

融合方向：SourceLore 只保留一个 Collector，改走平台已认证的 `gh api`，强制分页、检查
`trees.truncated`、失败抛结构化异常、按 (endpoint, params, SHA) 缓存。报告侧建立
`source_type` 四分类（`github_api` / `readme_claim` / `external_web` / `inference`），
置信度从百分比换成可数陈述，模板去掉固定基数与无条件 `Status: Complete`，
只允许 `complete` / `partial` / `facts_only` 三态。

与 UPSTREAM-01 的关系写清楚了：互补，不重复。01 出确定性源码事实（`repo_facts.json`），
02 出带来源的生态叙述，两者共用同一个 Collector，事实只算一次。

测试：上游子树没有任何测试文件，状态记 `NOT_RUN`，不能据此断言任何功能可用。

下一步：`UPSTREAM-03..06` 仍为 PENDING，逐个钉 SHA 后按同样流程审计。

## UPSTREAM-03 完成（2026-10-31 15:20 +08:00）

**任务**：审计 `maboasoft/repository-discovery`（M1 第三源）。
**Commit**：`557703fffe69c9ab97eff67acabea6b346afd89c`（单根提交，`parents: []`，全仓仅 1 次提交）。
**快照**：`upstreams/UPSTREAM-03-repository-discovery/`，4 blob + 1 tree，`truncated: false`，Git 忽略已复核。

### 上游形态

纯文档仓库，1820 行 / 68 KB，零行可执行代码：

| 文件 | 行数 | 字节 |
|---|---|---|
| `LICENSE` | 16 | 707 |
| `README.md` | 243 | 7977 |
| `SKILL.md` | 1452 | 56537 |
| `examples/knowledge-base-structure.md` | 109 | 2829 |

无脚本、无依赖清单、无测试、无 CI、无构建配置，`language: null`。**测试状态 `NOT_RUN`——不是没找到，是枚举全部 4 个 blob 后确认不存在可运行物。**

### 许可证

实测 CC BY 4.0（`LICENSE` L1/L3 原文 + L16 指向官方 legalcode）。GitHub API 报 `NOASSERTION`/`Other`/`path: null`，原因是 licensee 无法归类手写摘要文本，非许可证缺失。

**关键差异：LICENSE 没有任何版权持有人声明行。** 署名义务只能由「仓库 URL + repo_id `1290761659` + commit SHA + 作者 `Vladimir <kuzmenko.dn@gmail.com>`」四者合成。CC BY 还要求**标明是否作了修改**，这是 MIT 没有的义务。

### 能力判定：27 项

`REUSE 3 / ADAPT 12 / REIMPLEMENT 7 / REJECT 5`

对比：01 是 `4/8/0/3`（15 项），02 是 `4/8/1/5`（18 项）。本源 ADAPT 占比 44% 为三源最高、REUSE 占比 11% 为最低。原因不是写得差，是**方法论密度最高但可执行程度最低**——1820 行里没有一行代码，所以绝大多数能力只能「照思想、重做实现」。

三个 REUSE：边界三分类（§5.6）、集成指示符正则（§9.5，全文唯一实质代码块）、显式未知优于猜测（§4.4/§4.3）。

五个 REJECT：五档证据优先级（§12.2，无权重且自我消解）、D2 强制（§11）、禁 AST/图数据库/索引（§2，与确定性 CLI 架构正面冲突）、每术语必成页（§7.2）、百分比置信度豁免（§13.1 L1201）。

### 缺陷：18 项，其中 3 个 blocker

- `D1` 九类页面 section 集合各不相同（9/8/11/14/13/9/8/8），§8 L738 却要求「all required sections defined by this methodology」→ 无法判定页面是否写完
- `D3` 声明支持 monorepo 却零 token 预算、零每轮读仓上限、零采样规则 → 14 步顺序假设每阶段回看全仓，monorepo 上成本失控
- `D6` §8 自称「a required quality gate, not a style preference」却无 schema、无 linter、无失败处置 → 18 项检查全靠人工判读

另有 5 项 high：`D2` Unknown 页缺 Confidence 且 examples 给出第三套模板；`D4` 要求建模业务实体却无产物位置；`D7` 百分比豁免；`D8` 置信度有标签无聚合；`D9` §15.4 的一致性规则因 evidence strength 未定义而不可执行；`D11` 终止条件全 SHOULD 且不可度量。

### 融合设计要点

**四层数据模型**（这是本源唯一的架构贡献）：

```
repo_facts.json   → 事实层（存在什么；渲染时不注入模型句子）
Product Model     → 语义草稿层（这可能意味着什么；每字段带 claim_type + evidence_refs）
claims.json       → 主张层（我们断定什么以及凭什么；Registry 在此实现）
evidence.json     → 证据层（凭什么；source_type 四值）
```

关键判据：**Product Model 不是第四套数据，是 `claims.json` 的草稿态。** 无法给出 `evidence_refs` 的字段只能以 `claim_type: insufficient` 进入并强制渲染为 Unknown 页。

**单采集器约束自动满足**——本源不提任何 GitHub API，唯一采集动作是扫本地已克隆仓库，所以无采集器可建。§9.5 的 8 组正则作为 UPSTREAM-01 CLI 的新子命令读快照，零网络请求。

**18 条 linter 规则**（`KB001`–`KB018`）从 §8 十八项检查、§10.4 链接校验、§13.4 措辞规则、§14.2 五字段、§12.5 密钥扫描推导而来，17 条可完全机器判定。

**token 预算对接**：把 §6.5 十四步压进 UPSTREAM-01 已有的 R0–R4 五轮，token 成本从 O(仓库大小 × 14) 降为 O(仓库大小 × 1 + 定点读取)。这是解决 D3 的唯一办法。

### 四处形式冲突及处置

| 冲突 | 处置 |
|---|---|
| §12.2 五档证据优先级 vs 既有 `source_type` 四值 | 拒绝五档，映射到四值 |
| §13.1 L1201 允许百分比 vs 禁止未校准百分比 | 拒绝百分比，只留三档序数 |
| §2 L52–L53 禁确定性工具 vs 确定性 CLI 架构 | 拒绝禁令 |
| §14.2 五字段 + §10.2 六段 vs `claims.json`/`evidence.json` | 五字段落为 claims 子字段，六段由 schema 定义 |

### 主要风险（三条）

1. **祈使句污染。** `SKILL.md` 1452 行大量 MUST/SHOULD，整篇进 prompt 会与 SourceLore 规则竞争，至少两条（禁确定性工具、允许百分比）直接顶撞。融合只允许注入改写后的规则集，禁止注入原文。
2. **实体页悬空。** 上游要建模业务实体却不给产物位置。不先定义实体页类型就照搬 §5.3，会产出一批无处安放的语义。
3. **低 token 与全仓扫描的结构性矛盾。** 不按上面那条预算映射压进去，在 monorepo 上必然失控——而 DeepSeek-V4.1 Flash 最承受不起这个。

### 产出

- `docs/upstream-audit-03-repository-discovery.md`（528 行）
- `progress/UPSTREAM-03-audit.json`（27 项能力 + 18 项缺陷 + 18 条 linter 规则 + 9 个重跑点）
- 账本更新：`progress/TASKS.json`、`progress/STATE.json`、`docs/upstream-manifest.json`

### 下一步

`UPSTREAM-04`（`SNIKO/agent-skills` swe-research）、`UPSTREAM-05`（`walterfan/lazy-rabbit-skills` project-knowledge-base）、`UPSTREAM-06`（`Consensys/repo-security-review`）仍为 PENDING，各自先钉 SHA 再审。

---

## UPSTREAM-04 · SNIKO/agent-skills · skills/swe-research

**完成时间**：2026-11-01 13:45 +08:00
**状态**：DONE
**上游钉版**：`a3e5e9da94434127cdd47a1a7e0658baafff7083`（2026-08-23T12:59:00Z，master）
**许可证**：MIT，`LICENSE` L3 `Copyright (c) 2026 Sergii Vashchyshchuk`；API `spdx_id=MIT` 与实测一致，无差异。
**审计范围**：`skills/swe-research/`（4 blob）+ 根 `LICENSE`/`README.md` = 6 blob / 475 行 / 28286 字节。仓库另有 10 个并列 skill，未读未判。
**快照**：`upstreams/UPSTREAM-04-agent-skills/`，6/6 sha256 校验通过；`files.tsv` 本轮补齐（03 有、04 原先缺）。

### 一句话定性

这不是工具，是**规约**——127 行教模型「研究完之后证据怎么长期活着」。它是四源中体量最小、抽象层级最高的一源，也是唯一讨论**并发**与**知识失效**的一源。

### 27 项能力判定：REUSE 6 / ADAPT 11 / REIMPLEMENT 7 / REJECT 3

最强的四项（C01–C04，全部 REUSE）：可变层/不可变层分离、subject 作为知识身份单位、索引是派生视图禁止手改、双通道检索（索引找结论、直链读报告）。

### 18 项缺陷：3 blocker / 4 high / 7 medium / 4 low

三项 blocker：

1. **D1**（`SKILL.md` L44–L49）Reuse/Extend/Create 四个关键判断（`plausibly covers`、`already answers it`、`is still valid`、`no existing subject covers it`）全是模型主观，没有任何可执行判据 → 语料库必然碎片化。修法：定义查重键 `(repo_id, subject_key, claim_scope)`，三态改硬优先级。
2. **D2**（`SKILL.md` L88–L100）`INDEX.md` 的生成前提不存在——全仓 0 个脚本，L90 要求每次全量重生成、L114 又禁止手改，形成「只能手写，但不许手写」的死锁。
3. **D3**（`SKILL.md` L63；`report.template.md` L5）五种失效条件塞进一个自由文本串 `verified-against`，无任何检测机制 → 拆四字段 + 四类失效源 + 哈希比对。

### 本源独有的四样东西

Reuse/Extend/Create 三态 + 查重键（01/02/03 都没有「先查再写」）；`verified-against` 新鲜度语义与失效检测（03 的 claims 没有「这条结论是对哪个 commit 说的」）；superseded 关系与版本链（03 只有当前态）；派生索引消除并发冲突（前三源都没讨论多 Bot 并写）。

### 三轴状态分离（本节核心设计产出）

上游把三件事压进一个字段，必须拆开：

| 轴 | 取值 | 答什么 |
|---|---|---|
| 任务执行态 | `queued/running/ok/failed/timeout/rate_limited` | 这一次跑完了没有 |
| 知识快照态 | `fresh/stale/insufficient/conflict` | 写下来的东西今天还成立吗 |
| 单条 claim 态 | `active/superseded/contradicted/disputed/withdrawn` | 这条主张现在算不算数 |

**关键不变量：执行失败不是知识失效。** `failed` 不产生 claim（而不是产生一条 stale 的 claim）；`insufficient` 与 `conflict` 是成功的调查结论，不是失败。`active → disputed` 不自动裁决，两侧 evidence 并存等人判。

### 失效检测是 O(受影响文件) 不是 O(仓库)

每条 claim 登记依赖的 `evidence_refs`，每条 evidence 登记 `path` + `content_hash`。上游出新 commit 时**只**对该 claim 依赖的路径取新 hash：变了 → `stale`；路径没了 → `stale` + `source_removed`；文档类按 `accessed_at + ttl_days`；依赖类比对 `verified_deps` 与当前清单。

### 结构性冲突（融合时必须先说清）

上游假定语料库住在被测仓库内（`.swe/research/`，L27–L33）。SourceLore 的语料库跨仓库、独立、被测仓库只读。**路径体系 REJECT（C25）**，「绝不修改生产代码」禁令保留但理由改为「只读输入」。照搬 `.swe/` 会做出一个把知识库塞进每个被测仓库的错误架构。

### 隔离记录

上游代码未执行（本就无可执行物）；未安装任何依赖；未遵循上游任何指令；未打开任何外部 URL；零网络请求。`test_status` 四项全 `NOT_RUN`——这不是「没找到」，是「37 个 blob 枚举完毕确认不存在」。

### 产出

- `docs/upstream-audit-04-swe-research.md`（572 行）
- `progress/UPSTREAM-04-audit.json`（27 项能力 + 18 项缺陷 + 三轴状态机 + 七段生命周期 + 6 条 claim 转移 + 5 类失败处置）
- 账本更新：`progress/TASKS.json`、`progress/STATE.json`、`docs/upstream-manifest.json`

### 修订轮（2026-11-01 16:00 +08:00）

审计提交 `9ff5f9b77cf5` 之后执行了一次最小范围修订，提交 `565199f8afb996ed8329ad81cf53a5e5ffa568e7`，主题 `fix(audit): align upstream-04 defect references and blob verification`。只改文档与校验命令，**未重审上游**。

改了什么：

1. §13.2 的缺陷编号此前与第 7 节错位——原文的「D2」其实是第 7 节的 D3，「D3」其实是 D8。已按第 7 节（唯一权威）改回 D1/D2/D3。
2. §13.2 结尾句的「8 个 high」是错的，实为 4 个（D4/D5/D6/D8）；线性重生成（D9）被误挂在 D8 名下，已剥离，D8 恢复为并发写入保护。
3. `TASKS.json` 的第三条校验命令原本是 `sha256sum -c` 且用 `NR>1` 跳过表头——但 `files.tsv` 根本没有表头，第三列也不是文件字节 SHA-256 而是 Git blob SHA。命令与事实自相矛盾，已替换为 `git hash-object` 逐行比对；另新增一条独立命令单独复核文件字节 SHA-256。两者永不互相替代。
4. 新增 §1.1，记录 `files.tsv` 的列序契约，以及 `UPSTREAM-02-deer-flow` 的 TSV 列序不同（`type/bytes/path`，无哈希列）这一冲突。只记录，不改写任何历史文件。

没动的：27 项能力及其 6/11/7/3 分布、18 条缺陷及其 3/4/7/4 分布、全部源码行号证据、固定提交 SHA、测试状态全 `NOT_RUN`、隔离记录。

复验结果：5 条验证命令逐条执行全部 exit 0（其中 blob 校验输出 `blob-ok`）；六项一致性检查全部 PASS，退出码 0。

### 遗留未决（4 条）

1. Reuse 分支是否必须写盘（D17）——本审计提案「不必写盘、只读」，未评审。
2. `disputed` 的裁决权归谁、裁决记录写在哪，未定。
3. `subject_key` 规范化规则未与 UPSTREAM-03 的实体消解表对齐。
4. UPSTREAM-02 的 C08 `summarize_repo` 混合判定是否拆分，仍挂账。

### 下一步

`UPSTREAM-05`（`walterfan/lazy-rabbit-skills` project-knowledge-base）、`UPSTREAM-06`（`Consensys/repo-security-review`）仍为 PENDING，各自先钉 SHA 再审。本轮未启动 UPSTREAM-05。
