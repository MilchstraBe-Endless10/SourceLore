# SourceLore 交接文档

> 本文件是跨会话恢复的唯一入口。任何新会话第一件事就是读它。
> 最后更新：2026-11-03T05:50:00+08:00

---

## 一、现状

M1-FUSION-GATE 进行中。**F0 完成并提交；F1 已按批次推进，F1-A、F1-B/Facts、F1-B/Collector 均已 DONE 并各自独立提交。**

> F1 曾因模型输出预算熔断中断，恢复后改为按模块分批推进。
> 清单与约束仍以 `progress/CHECKPOINT-F1.md`、`docs/fusion/BASELINE.md` §8 为准。

- 项目根：`/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore`
- 当前里程碑：**M1-FUSION-GATE（IN_PROGRESS）**
- 当前任务：**M1-FUSION-GATE-F1**（分批进行中，已完成 19/143 的正式映射）
- 已完成批次：**F1-A、F1-B/Facts（SL-CAP-0001~0010）、F1-B/Collector（SL-CAP-0011~0019）**
- 下一动作：F1-B 剩余八模块，从 Evidence-Claims 起，按同一流程逐批推进
- 开发模型：`workbuddy/deepseek-v4.1-flash`（上下文 131072，务必小步走）

## 二、已通过的 Gate

| Gate | 判定 | 证据 |
|---|---|---|
| M0 | PASS | 见 `docs/environment-audit.md` |
| UPSTREAM-01~06 单源只读审计 | PASS | 各 `docs/upstream-audit-0N-*.md` §验收 |
| **M1-FUSION-GATE / F0** | **PASS** | `docs/fusion/BASELINE.md` §7；九项门禁 exit 0 |

## 三、最后一条真实命令与退出码

```bash
python3 - <<'PY'   # F0 九项门禁：JSON 结构 / 六源数 / Git 三字段 / 差异完整性 /
                   # ERRATA 对齐 / 历史零改动 / 数字对齐 / 无文本搬运 / 执行隔离
PY
```

```
FAILURES: 0
```

`exit=0`

## 四、本回合实际修改的文件

| 文件 | 说明 |
|---|---|
| `docs/fusion/BASELINE.md` | 新建。F0 基线冻结，含六源核验表与 Git 对象核验实测输出 |
| `docs/fusion/ERRATA.md` | 新建。六条勘误，全部声明不改历史史料 |
| `docs/fusion/F0_VERIFICATION.json` | 新建。机读证据，BASELINE 与 ERRATA 均从此渲染 |
| `progress/TASKS.json` | 新增 `M1-FUSION-GATE`（IN_PROGRESS）与 `M1-FUSION-GATE-F0`（DONE） |
| `progress/STATE.json` | 推进到 M1-FUSION-GATE，next_task 设为 F1 |
| `progress/HANDOFF.md` | 本文件 |

未改动：六份 `progress/UPSTREAM-0X-audit.json`、六份 `docs/upstream-audit-0N-*.md`、
`docs/upstream-manifest.json`、`THIRD_PARTY_NOTICES.md`、`upstreams/`。

## 五、测试

**F1：未执行。** §7 的 13 项验收一项都没跑，因为映射产物还没生成。没有跑过的检查不得写成通过。

F0 门禁九项全部实跑，`FAILURES: 0`，`exit=0`。

过程中三处判据误报并已修正，不是数据问题：能力总数误算为 120（实为 143）；
「不改历史」行数判据未覆盖带补充说明的单元格；以及本节自身在描述上游引文时
**又复制了一遍**被指的英文原句——已改为描述性指代，这条错误值得记住。

## 六、Git HEAD

`58e9b3739698068a8b0cdb98f6d82ca7b40f5cf6` —— F1-B Collector 批次提交（9 canonical / 11 raw 承接 / 5 分流待办，晋升记录修复后落盘）。

## 七、下一步

**继续 F1-B 剩余模块**（Evidence-Claims → Product → Research → Lifecycle → Security → Renderer → Storage → DSH Adapter）。

已完成：F0 状态核验、六源 143 项能力全量提取（15+18+27+27+28+28，与对照数一致）、
字段结构确认（`id`/`capability`/`mechanism`/`where`/`disposition`/`why`，六源一致）、
F1-A 冲突裁决、F1-B 的 Facts 与 Collector 两批共 19 条 canonical。
未完成：其余八模块的能力归并、F1-C 边界裁决、F1-D 全量验收与 `CAPABILITY_CROSSWALK.json` 冻结。

详细恢复步骤见 `progress/CHECKPOINT-F1.md`。三条前置约束仍以 `BASELINE.md` §8 为准：

1. 能力总数是 **143 项上游候选**，不是 143 项 SourceLore 能力。F1 Gate 要求的是原始候选全覆盖，不是去重后仍为 143。
2. 每条记录必须带 `license_permission` 独立字段；UPSTREAM-06 的 28 项全部只能是「仅参考设计」。
3. 06 的 C06 判否语义（E-06）不能沿用，`disposition` 记 `ADAPT` 而非 `ADOPT_DESIGN`。

## 八、已知限制

1. **上下文 131072**：按阶段与输入预算截断，标记覆盖范围，截断不得宣布「全量」
2. **会话 cwd 不在项目根**：命令必须显式 cd
3. **路径含括号与中文**：shell 必须引号
4. **`upstreams/` 被 `.gitignore` 排除**：快照不进历史
5. **UPSTREAM-06 无许可证**：只可取抽象设计思想，不得复制任何原文
6. **Git 三字段不可互换**：`commit_sha` / `root_tree_sha` / `tree_query_ref`（E-01）

## 九、恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' && git log --oneline -5 && python3 -m json.tool progress/STATE.json && cat docs/fusion/BASELINE.md | head -60
```

然后读 `progress/STATE.json` 的 `next_task`。当前应为 `M1-FUSION-GATE-F1`。

---

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

`UPSTREAM-06`（`Consensys/repo-security-review`）仍为 PENDING，各自先钉 SHA 再审。本轮未启动 UPSTREAM-05。

### 修订轮 2（2026-11-02 00:47 +08:00）

`TASKS.json` 中 UPSTREAM-03 的 `git_commit` 原为 9 位短 SHA `d19f63277`，按 SH 规范化要求改为完整 40 位 `d19f63277fdf47675e5f28edad356dbaec0e78b2`（`git rev-parse` exit 0，`git rev-list --all | grep -c '^d19f63277'` = 1，`git cat-file -t` = commit）。只改这一个字段，新增 `sha_normalized_note` 说明来历；审计事实、`audit_sha`（`557703fffe69c9ab97eff67acabea6b346afd89c`）与历史均未改动。

---

## UPSTREAM-05 完成（2026-11-02 00:30 +08:00）

### 一句话定性

`walterfan/lazy-rabbit-skills` 的 `skills/project-knowledge-base` 是一套给 AI 编码助手用的「知识库维护手册 + 18 个辅助脚本」。它的价值不在脚本本身，而在三条约束：脚本优先、分层更新、旁车产物与人工叙述页物理分离。

### 上游形态

- 仓库 `walterfan/lazy-rabbit-skills`（Repository ID `1275141665`），默认分支 `master`，许可证 Apache-2.0。
- 固定提交 `284971cdd2666878d13716af8f26f51521cd915c`，提交时间 `2026-08-16T01:54:22Z`，主题 `add more skills`，作者 Walter Fan。
- 审计子树 `skills/project-knowledge-base`：66 个文件，488925 字节。`tree.json` 条目 477，未截断。
- 快照落在 `upstreams/UPSTREAM-05-lazy-rabbit-skills`（被 `.gitignore` 忽略，不入库）。TSV 为 3 列无表头，第三列是 Git blob SHA。

### 许可证

`LICENSE` 201 行 / 11357 字节，blob SHA `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`，与 GitHub API 的 size 与 sha 三方一致，是逐字 Apache-2.0。全树无 NOTICE。再分发须带 LICENSE 并声明修改，本轮未分发任何上游文件。

### 能力判定：28 项

REUSE 6 / ADAPT 10 / REIMPLEMENT 9 / REJECT 3。这一源不是 27 项——数量由该源实际形态决定，没有为对齐前几源去凑数。

- REUSE：脚本优先零 token 预检、三级更新梯度、旁车与叙述页分离、`review_status` 人机权限划分、`[NEEDS INPUT]` 而非编造、强制 Auto-generated 头部。
- REJECT：知识库嵌进被分析仓库内部、面向人类的整书项目文档、双语 Sphinx 站点 + gettext 流水线。

### 缺陷：18 项，其中 3 个 blocker

- D1 新鲜度基于文件 mtime——mtime 不是内容，改一个字和改整篇一样，且 `touch` 即失效。
- D2 索引生成器只产出候选清单，不落最终索引，闭环缺最后一步。
- D3 「人类必须提供 why」只写在 HTML 注释和散文里，无任何机器检查。

其余 high 4 / medium 7 / low 4。

### 最有价值的机制

`scripts/generated_output.py` 的 `generated_output_path()`（L19–L23）把脚本产物强制钉进 `_generated/` 子目录，`render_markdown_artifact()`（L35）再给每个产物盖上 `<!-- Auto-generated by ... -->` 头。对照 UPSTREAM-04：那边只有一句「不要覆盖叙述页」的文本规则，这边是代码级绑定。规则会被人忘记，路径不会。这一条直接落到 SourceLore 的旁车落盘层。

### 测试状态

`NOT_RUN`。18 个脚本里只有 3 个被测试引用，5 个零引用；`tests/` 3 文件 6 个测试类共 19 个方法——19 是方法数量，不是通过数。本轮未执行任何上游脚本或测试，未装任何依赖。

### 融合风险（3 条，1 条已登记）

1. `MANIFEST_FORMAT_DIVERGENCE`（medium）：UPSTREAM-02 的 TSV 是 `type/bytes/path` 无哈希列，其余四源是 `path/bytes/blob_sha`。本轮禁止批量重写既有 manifest，提出 Manifest V2 但不迁移，只登记冲突。
2. `MTIME_FALSE_CONFIDENCE`（high）：若照搬 mtime 判新鲜度，会在内容未变时报过期、内容变了报新鲜。必须换成 `content_hash`。
3. `CANDIDATE_INDEX_TRAP`（medium）：若照搬「只发候选」，索引会静默停在过期状态，且看起来一切正常。

### SHA 规范化

本轮起所有新记录使用完整 40 位 SHA。必须区分：`upstream_pinned_sha` 是上游事实（`284971cd…`），`audit_git_commit` 是本仓库提交（回填阶段写入），二者不可互相替代。

### 产出

- `docs/upstream-audit-05-project-knowledge-base.md`
- `progress/UPSTREAM-05-audit.json`
- `docs/upstream-manifest.json` 的 UPSTREAM-05 条目
- 账本：`TASKS.json` 的 `UPSTREAM-05` 转 DONE，`STATE.json` 同步

### 验收

九项门禁全部实跑通过，退出码均为 0。其中门禁 5 与门禁 8 各失败过一次，都是检查器误报（否定句被当断言、上游自带 `poetry.lock` 被当安装产物），判据已修正并复跑通过的过程记在审计文档 §10。

### 结转未决

1. Reuse 分支是否必须写盘（UPSTREAM-04 的 D17）——仍未评审。
2. `disputed` 的裁决权归谁、裁决记录写在哪——仍未定。
3. `subject_key` 规范化规则未与 UPSTREAM-03 的实体消解表对齐——仍挂账。
4. UPSTREAM-02 的 C08 `summarize_repo` 混合判定是否拆分——仍挂账。
5. Manifest V2 的列契约已提出但未定稿，`MANIFEST_FORMAT_DIVERGENCE` 只登记未消解。

### 下一步

只剩 `UPSTREAM-06`（`Consensys/repo-security-review`），状态仍为 PENDING，尚未钉 SHA。本轮未启动它。

## UPSTREAM-06 完成（2026-11-02 15:30 +08:00）

### 一句话定性

六个上游里唯一没有许可证的一个。它是一套成熟的漏洞审查流水线（P0 拓扑 → P1 密钥 → P2 架构 → P2a 技术栈 → P3 依赖 → P3b 可达性 → P4 OWASP → P4b LLM 安全 → P5 验证 → P6 报告 → P7 合成），但自身的边界有三处不成立：无授权却提供整套可复制的方法论、安装脚本无钉定、`--runtime` 默认可构建并运行不受信代码。

### 上游形态

`Consensys/repo-security-review`，整仓 16 个文件 / 466023 字节 / 8959 行。除 `scripts/setup.sh`（10530 字节）外全部是 Markdown。仓库里没有分析引擎代码——只有提示词、规则文本与安装脚本。固定提交 `d5128b03d6a785bfb7c8be4139291f887c2a3215`（2026-10-21，`Clarify dependency CVE triage and reporting`）。

### 许可证

**无。** API `license` 为 null，`/license` 端点 404，16 个文件全文检索 LICENSE / Copyright / SPDX / © 命中 0，树内无 LICENSE / COPYING / NOTICE，`.gitignore` 仅一行 `.DS_Store`。

处置：只取抽象设计思想，不复制源码、提示词、规则原文与模板。许可证状态在 manifest 与审计 JSON 中作为独立字段（`license_verified_spdx: null`、`license.status: "none"`），不被任何复用判定覆盖。

### 能力判定：28 项

REUSE 11 / ADAPT 11 / REIMPLEMENT 4 / REJECT 2。

REUSE 的十一条里，最值钱的四条：四节点数据流契约（entrypoint → hops → sink 逐跳 file:line）、两级的确定性前置门（Surface Gate / Boundary Gate，带置信度分级与封顶）、环境失败绝不改判 + 动态否证只降级到人工复核、族扫描与诚实否定（族里一个成员没读，整个类的「确信」就作废）。

REJECT 的两条：Claude 家族模型分层、一键安装外部扫描器。

### 缺陷：20 项，其中 3 个 blocker

- D1（blocker）无许可证
- D2（blocker）`setup.sh` 用 brew / `go install @latest` / releases 下载 / `pip --break-system-packages` / `curl | sh` 装六个工具，无版本钉定、无校验和
- D3（blocker）`--runtime` 会 build 并 run 目标仓库的 Dockerfile，加固标志只加在 run 上；`--yes` 一次跳过全部同意门

三个 blocker 有共同形状：不是功能没做，而是做了但边界不成立。

high 四条：上游自陈「边界 2 不防边界 1」、全部静态探测带 head 封顶与族扫描纪律冲突、模型分层绑死供应商、宿主路径硬编码。

### 十二项风险核验

6 成立 / 5 部分成立 / 1 不成立。唯一不成立的是「自动构建/执行 PoC」——`--poc` 只持久化不执行，`--runtime` 只执行不持久化，都不设时连 `pocs/` 目录都不创建，构造点钉在验证之后，被拒绝的 finding 永不构造。这是本轮最值得采纳的设计。

### 最有价值的机制

1. **四节点数据流契约。** 把「这里有注入」变成一条可被第二个上下文独立复核的链。跨文件边界却缺 hop 的声称被明确判为不可验证。
2. **确定性前置门 + 置信度封顶。** 非生产面 + 高置信直接终止；中置信照常验证但结果封顶。两条门各带一句纪律：绝不因为 finding 严重就跳过门；门不是误报判定。
3. **环境失败绝不改判。** 工具没跑起来不是证据。与 SourceLore 既有不变量同源——两处独立收敛，说明这是不变量级而非风格选择。
4. **族扫描与诚实否定。** 上游给的失败案例极准：读了 `curl` 包装器就宣布「SSRF 确信无」，而同目录的 `wget` 包装器没读。

### 测试状态

`NOT_RUN`。`setup.sh` 只读未执行；未安装 gitleaks / osv-scanner / semgrep / pip-audit / grype 中任何一个；未启动 Docker；未对任何真实部署发起请求。28 条能力判定与 20 条缺陷全部来自静态阅读。

### 融合风险（3 条最要紧）

1. `PROMPT_INJECTION_INHERENT`（high）：任何读取不受信仓库内容的分析阶段都暴露在提示注入下。上游自己承认边界 2 不防边界 1。SourceLore 不能靠分层代理解决。
2. `BOUNDED_SEARCH_FALSE_NEGATIVE`（high）：有界搜索的空结果被当否定证据。上游在依赖可达性上明令禁止，却在 OWASP 探测上自己就在做。
3. `SEVERITY_CONFIDENCE_COLLAPSE`（high）：把环境档位调整与置信度封顶混成同一根严重度轴。上游选择在报告里不解释，这不是修复。

### SHA 规范化

`upstream_pinned_sha` = `d5128b03d6a785bfb7c8be4139291f887c2a3215`（上游事实），`audit_git_commit` = 本仓库提交（回填阶段写入），二者不可互换。上游 SHA 不是本地 Git 对象，核验方式是比对 `tree.json.sha`、审计 JSON 三处字段与 manifest `commit`。

### 产出

- `docs/upstream-audit-06-repo-security-review.md`
- `progress/UPSTREAM-06-audit.json`
- `docs/upstream-manifest.json` 的 UPSTREAM-06 条目
- `THIRD_PARTY_NOTICES.md`（新建）
- 账本：`TASKS.json` 的 `UPSTREAM-06` 转 DONE，`STATE.json` 同步，`next_task` 改为 `M1-FUSION-GATE`

### 验收

九项门禁全部实跑，退出码均为 0。过程中发现两处真实数据缺陷并修正：D18 在文档与 JSON 中严重度不一致（medium / low），连带文档自身的统计行与表格矛盾；manifest 的 UPSTREAM-06 行仍是占位（`commit: null`、`audit_status: NOT_RUN`）。修正后复跑全部通过。

### 结转未决

1. 06 的 U10：无许可证下「抽象设计思想」与「受版权保护表达」的边界宽度，需法务判断。
2. 06 的 Q1：四节点结构在非 HTTP 场景（CLI、文件解析、CI 配置）的 hops 粒度如何定义。
3. 06 的 Q2：`auth_coverage` 的确定性抽取能做到什么精度；不足则边界门只能降级为标注。
4. 06 的 Q3：否定结论的覆盖面字段与 04 的增量机制如何共存。
5. `docs/fusion-matrix.md` 尚未产出，属 M1-FUSION-GATE。
6. 结转自 04/05：Reuse 分支是否必须写盘、`disputed` 裁决权归属、`subject_key` 规范化、UPSTREAM-02 C08 是否拆分、Manifest V2 列契约未定稿。

### 下一步

M1 六个上游全部 DONE。**M1-FUSION-GATE 需用户明确启动**；M2 开发未开始。本轮到此停止，不自动进入融合。

## M1-FUSION-GATE / F0 完成（2026-11-02 22:27 +08:00）

### 一句话定性

基线冻结完成，六源历史零改动。最重要的一条发现是 **Git 对象三字段不能互换**：GitHub Trees API 在 ref 为 commit-ish 时，响应 `sha` 字段回显请求标识，所以四源的 `tree.json.sha` 存的其实是 commit SHA，不是根 tree SHA。

### 关键发现

UPSTREAM-06 的 commit `d5128b03…` 真实根 tree 是 `68af655f92d2d15f40335017c0e0819f59524413`。三条 `gh api` 实测输出互相对照即可区分：按 commit 查 trees 返回的仍是 commit SHA，按 tree 查才返回 tree SHA；两次的 `entries` 与 `truncated` 相同，说明指向同一棵树。

**这不让历史审计失效。** 对 03/04/05/06 四源，把本地 `tree.json` 的 `tree[]` 与远端 `recursive=1` 逐条比对：5/55/477/18 条全部同路径同 SHA，不符 0 条。所以是字段语义错误，不是数据污染，blob 哈希结论全部成立。

### 六源核验

能力 143 项上游候选（15+18+27+27+28+28），缺陷 92 项（6+12+18+18+18+20）。六源状态全部 DONE。

形态不齐：UPSTREAM-01 只有 `src.tar.gz` + `tree/`，UPSTREAM-02 只有 `files.tsv` + `tree/`，两源都没有 `tree.json`，无法做上述核验。

### 六条勘误（全部不改历史史料）

| ID | 类型 | 严重度 | 何时处理 |
|---|---|---|---|
| E-01 | 字段语义错误（tree.json.sha） | high | F2 |
| E-02 | 声明过度绝对（THIRD_PARTY_NOTICES） | high | F5 |
| E-03 | Manifest 结构不齐（01/02 缺键） | medium | F1/F2 |
| E-04 | Manifest 格式分叉（02 列序） | medium | F2 |
| E-05 | 覆盖缺口（01/02 无 tree.json） | medium | F2 |
| E-06 | 语义冲突（06 C06 判否语义） | medium | F1 |

E-02 值得单独说：`THIRD_PARTY_NOTICES.md` 写「本仓库不包含任何第三方源代码、提示词、规则文本或模板」，但 `docs/` 下的审计文档确实含上游英文原句的引文式引用（03 有 14 处、04 有 21 处 ≥6 词长句）。核心主张（产品代码与提示词零复制）属实，措辞越界。本轮不改，留待 F5 重写为分层表述。

### 产出

- `docs/fusion/BASELINE.md`
- `docs/fusion/ERRATA.md`
- `docs/fusion/F0_VERIFICATION.json`（机读证据，两份 Markdown 均从此渲染）
- 账本：`TASKS.json` 新增宿主行与 F0 行，`STATE.json` 推进

### 下一个

F1（六源能力去重及归属）。需 Owner 确认后启动。

## M1-FUSION-GATE / F1 中断（2026-11-02 22:50 +08:00）

### 一句话

F1 启动了，做完状态核验和数据提取就熔断了。**没有任何半成品被当成成果提交。**

### 已完成

- F0 两提交存在性核验：`c0877e0`、`bb45ab1` 均为 commit，HEAD 与历史一致，工作树干净
- 六源能力全量提取，实测 15+18+27+27+28+28 = **143**，与指令对照数一致
- 字段结构确认六源一致，无需适配器

### 未完成

- `docs/fusion/CAPABILITY_CROSSWALK.json`
- `docs/fusion/ABILITY_DECISIONS.md`
- 十项冲突裁决
- §7 的 13 项验收
- 本任务的 Git 提交

### 账本状态

`STATE`：`active_task=M1-FUSION-GATE-F1`、`status=IN_PROGRESS`、`next_task=M1-FUSION-GATE-F1`，
`blockers` 记录中断原因。`TASKS` 的 F1 行为 `IN_PROGRESS`，`blocked_reason` 写明「非项目阻塞」。

**没有把 F1 标成 DONE。**

### 下一步

手动压缩上下文 → 读 `progress/CHECKPOINT-F1.md` → 从「二、下一步是什么」第 1 步继续。

检查点里已备好 143 项能力的完整清单与六条继承约束（06 全部仅参考设计、C06 记 ADAPT、
03 的 CC BY 4.0 署名要求、名称相似语义不同不得合并等），续跑不必重读六份审计 JSON 全文。

## M1-FUSION-GATE / F1-B Collector 批次完成（2026-11-03 04:35 +08:00）

### 一句话

F1-B 第二批次（Collector 模块）完成：9 条 canonical（`SL-CAP-0011`~`0019`）、11 个原始身份正式归属、
5 个身份分流到其它模块待承接。两个验证器全绿。F1 整体仍未完成。

### 本批做了什么

- 从 `RAW_CAPABILITY_INDEX` 全量检索出 Collector 相关候选，不是凭聊天记忆补的
- 归并为 9 条 canonical，并明确 Collector 的十项职责与六项非职责
- 关键裁决 A：唯一采集入口 —— 逻辑接口 / 当前 `gh api` 传输适配 / 可验证原始数据 / 传输可替换，四层分离；
  数据契约不得绑定 GitHub CLI 的输出格式
- 承接 11 个原始身份（其中 `U02::C01/C02/C03/C04/C07/C08/C09/C18`、`U01::C15`、`U06::C13` 直接映射）
- 本批向其它模块分流 5 条（`DEFERRED_TO_OTHER_MODULE`）：Evidence-Claims 2 条
  （`U04::C11` verified-against、`U06::C13` 存储路径）、Lifecycle 1 条（`U05::C17` 过期检测）、
  Security 2 条（`U06::C18`、`U06::C24`）、Research 1 条（`U02::C11`）
- 分流表当前共 14 条：Facts 批次留下的 9 条加本批 5 条。两者都记 ROUTED，
  只有目标模块真正建出 canonical 时才转成 MAPPED
- 另有 2 个身份（`U02::C06` → `SL-CAP-0014`、`U02::C09` → `SL-CAP-0015`）原本由 Facts 判为「去向 Collector」，
  本批建出 canonical 正式承接，按晋升规则从 ROUTED 变为 MAPPED，并在 `routed_promotions` 留迁移记录。
  这 2 条与上面 5 条分流是两个不相交的集合，所以 MAPPED 与 ROUTED 不重复计数

### 统计口径（三态互斥，实测非声明）

| 状态 | 数量 |
|---|---|
| MAPPED | 22 |
| ROUTED（去向已定、目标模块尚未承接） | 14 |
| UNREVIEWED（既未映射也未分流） | 107 |
| **合计** | **143** |

MAPPED ∩ ROUTED = ∅。`canonical_count = 19`（不是 143）。

### 验证证据

- `tools/fusion/f1b_verify_collector.py` → `30/30 PASS -> F1B_COLLECTOR_VERIFICATION.json`
- `tools/fusion/f1b_verify.py` → `汇总: 12/12 PASS`
- 两个构建器均幂等（重复运行产物字节一致）；写入都在校验通过之后

### 本批修掉的坑（下一批别再踩）

1. 验证器职责边界：`f1b_verify.py` 原先断言「全表 owner 必须是 Facts」，Collector 条目一进来就误报红。
   已收窄到 `FACTS_IDS` 范围 —— 每批验证器只判自己那一号段，全表不变量留给 F1-D。
2. Facts 构建器会静默抹掉其它模块的条目（它重写整张表）。已加闸：检测到 `SL-CAP-0010` 以外的条目就
   `exit 2` 且不写盘。整表重建的正确顺序是 `f1b_build_facts.py` → `f1b_build_collector.py` → 两个验证器。
3. 分流记录里 `owner_module` 存的是**目标**模块，不能拿它反推产出方；去重与剥离必须按
   `(upstream_id, original_capability_id)` 配对。
4. `refs` 是三元组 `(upstream_id, original_capability_id, verdict)`，不是字典；
   构建产物里对应字段叫 `upstream_refs`，元素是字典 —— 两边键名不通用，先打印再取值。
5. **晋升记录不能从运行时状态反推。** 草稿合并后原始分流已被本批消费，而原始索引不携带分流信息，
   反推会让证据在第二次运行时凭空消失。改为由定义文件 `PROMOTED_FROM_FACTS` 声明，构建器只做一致性校验。
6. 验证器 `check()` 收的是返回 `(ok, detail)` 的函数，不是结论值 —— 直接传结论会 TypeError。

### 下一步

F1-B 剩余模块：Evidence-Claims → Product → Research → Lifecycle → Security → Renderer → Storage → DSH Adapter。
每批照本批流程：检索候选 → 归并 → 裁决 → 幂等构建器 → 独立验证器 → 进度记录 → 独立提交。

## M1-FUSION-GATE / F1-B Evidence-Claims 批次完成（2026-11-03 19:00 +08:00）

### 一句话

F1-B 第三批次（Evidence-Claims）完成：9 条 canonical（`SL-CAP-0020`~`0028`）、12 个原始身份正式归属、
0 个身份外推。三个验证器全绿，已提交 `9e0f5ae`。F1 整体仍未完成。

### 本批做了什么

- 从草稿路由表与未审命中中确认 12 个身份的归属，不是凭聊天记忆补的
- 归并为 9 条 canonical，三组合并各有硬理由：C07+C08（形态面+元数据面）、
  C09+C11（同一条 claim 的「还算不算数」两维）、C06+C07（状态机的骨与边）
- U06::C05 独立成 SL-CAP-0021（证据结构 ≠ 状态机）
- 判给 Product 的 2 条、判给 Security 的 1 条不进本批

### 核心裁决

**显式拒绝「不可验证即判否」。** 上游 U06::C06 原文 can't prove → FALSE_POSITIVE。
本批取其「必须给悬置一个确定去向」的取向，去向改为 `insufficient_evidence`，硬规则：
不可验证只产生 insufficient_evidence，禁止落成 refuted；无法证明不等于已被证伪。

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 34 |
| ROUTED | 5 |
| UNREVIEWED | 104 |
| **合计** | **143** |

`canonical_count = 28`。批次视图：Facts 11/1、Collector 11/4、EC 12/0。

### 验证证据

- `f1b_verify.py` → 12/12 PASS
- `f1b_verify_collector.py` → 30/30 PASS
- `f1b_verify_ec.py` → 50/50 PASS
- 重建链 `f1b_build_collector.py` → `f1b_build_ec.py` 幂等，重复运行结果一致

### 本批修掉的坑

1. 验证器基线写死会假阳性：Facts c10/c11、Collector c27 三处判据已收窄作用域
   （判据收窄不降强度，只是去掉「历史必须等于现在」）。
2. 批次出向分流是现算视图：Facts 9→1、Collector 5→4 是下游承接的自然结果，不是数据漂移。
3. `from` 字段必须与磁盘核对：U06::C07 起初误标来自路由表，实际是未审命中，构建器断言抓出。
4. 多行 return 元组括号易错，改写成先算 `detail` 再 `return cond, detail`。

### 下一步

F1-B 剩余七模块：Product → Research → Lifecycle → Security → Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0029` 起。F1-C、F1-D 仍未启动。

## M1-FUSION-GATE / F1-B Product 批次完成（2026-11-03 20:20 +08:00）

### 一句话

F1-B 第四批次（Product）完成：6 条 canonical（`SL-CAP-0029`~`0034`）、10 个原始身份正式归属、
2 个身份外推。四个验证器全绿。F1 整体仍未完成。

### 本批做了什么

- 逐一核验用户列出的九项优先候选，再对 143 项做全库关键词检索，确认无遗漏
- 12 个候选中 10 个进本批、2 个转给 Renderer/Lifecycle、7 个明确留给后续批次（仍是 UNREVIEWED）
- 归并为 6 条 canonical，三处合并：C07+C13+C14（构建序的依赖顺序/分轮原则/精修动作）、
  C09+C10（未知项的「无资料」与「资料矛盾」两源）、C17+C11（终止条件与进展度量）

### 核心裁决

**声明不可替代实现证据。** `claim_type` 四值（fact/declaration/inference/unknown）+ 硬规则：
`evidence_refs` 为空时只能是 inference 或 unknown，不得是 fact 或 declaration。
这是防止「README 声称的功能被当成已实现功能」的唯一机械闸门。

第二硬规则：**有配置 ≠ 在运行。** 外部集成必须落在 confirmed_runtime / configured_boundary /
integration_unknown 三态，检测到 provider 配置或依赖声明即必须产出条目，哪怕状态是 unknown。

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 44 |
| ROUTED | 7 |
| UNREVIEWED | 92 |
| **合计** | **143** |

`canonical_count = 34`。批次视图：Facts 11/1、Collector 11/4、EC 12/0、Product 10/2。

### 验证证据

- `f1b_verify.py` → 12/12 PASS (exit 0)
- `f1b_verify_collector.py` → 30/30 PASS (exit 0)
- `f1b_verify_ec.py` → 50/50 PASS (exit 0)
- `f1b_verify_product.py` → 43/43 PASS (exit 0)
- `f1b_build_product.py` 重跑后六个核心字段逐字节一致（幂等成立）

### 本批修掉的问题

1. **构建器自有键集合漏了本批分流键。** 导致推给 Renderer/Lifecycle 的两条分流每跑一次追加一份，
   累积成 5 份重复，由 Collector c4c 抓到。修正为 `own_keys = 承接键 ∪ 本批分流键`——
   分离两件事必须用同一个键集合，否则幂等在映射侧成立、分流侧失效。
2. **EC 验证器两处作用域过时**（batch_summary 指向、全局数字一致），与本轮第 7 节同类问题，
   已按「历史批次判历史事实」修正，核心不变量未放宽。
3. **自写验证器两个 bug**：批次 redirected 断言漏括号、分流去向 `mod[0]` 误取字符串首字符——
   属我自己的写法错误，非数据问题。

### 下一步

F1-B 剩余六模块：Research → Lifecycle → Security → Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0035` 起。F1-C、F1-D 仍未启动。


## M1-FUSION-GATE / F1-B Research 批次完成（2026-11-03 20:35 +08:00）

### 一句话

F1-B 第五批次（Research）完成：5 条 canonical（`SL-CAP-0035`~`0039`）、10 个原始身份正式归属、
3 个身份外推。五个验证器全绿。F1 整体仍未完成。

### 本批做了什么

- 核验用户点名的六项优先候选，并按关键词全库检索补充（命中 13 个候选，人工逐条确认）
- 其中一个候选 `U02::C11` 原本由 Collector 判定「属研究流程」而挂起，本批建 canonical 正式承接
- 归并为 5 条 canonical，三处合并：C14+C12（分桶与优先级是同一件事正反两面）、
  C13+C15+U03C27+U06C23+U04C26（结论形态与「什么叫够了」，含两处 REJECT）

### 核心裁决

**来源类型不构成真伪排序。** U02-C12 的五层优先级被显式降级为 `source_type` 字段——
不因为来自 GitHub API 就认定内容为真，Issue 可能是用户报告、README 可能是维护者声明。
成立与否只能由 Evidence-Claims 的裁决状态机判。

第二条：**阶段完成 ≠ 结论正确，资料读完 ≠ 研究完成。** R3 只产 claim 候选不裁决；
R4 必须列出 remaining_questions。

第三：**缺失资料不得写成空结果。** partial / truncated / unavailable / empty 四态分列。

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 54 |
| ROUTED | 9 |
| UNREVIEWED | 80 |
| **合计** | **143** |

`canonical_count = 39`。批次视图：Facts 11/1、Collector 11/4、EC 12/0、Product 10/2、Research 10/3。

### 验证证据

- `f1b_verify.py` → 12/12 PASS (exit 0)
- `f1b_verify_collector.py` → 30/30 PASS (exit 0)
- `f1b_verify_ec.py` → 50/50 PASS (exit 0)
- `f1b_verify_product.py` → 43/43 PASS (exit 0)
- `f1b_verify_research.py` → 46/46 PASS (exit 0)
- `f1b_build_research.py` 重跑后六个核心字段逐字节一致

### 本批修掉的问题

1. **五处既有验证器作用域过时**（非数据缺陷）：EC c49 把「后续批次合法推给 EC 的分流」
   当成残留；Product c6 要求全局最大编号恒为 34；Product c29 拿当前全局数卡历史文档；
   Product c37 重跑历史构建器会触发其编号起点保护；Product c38 的「重跑前后一致」对历史批次不适用。
   全部按「历史批次判历史事实」修正，核心不变量一条未放宽。
2. **自写验证器一处正则转义退化**：`\n` 在字符类里被当成字面反斜杠与 n，改为逐行扫描。
3. **def 漏写了一处引用**：U02-C15 在承接声明里但不在 canonical refs 里，构建器一致性断言直接抓出。

### 下一步

F1-B 剩余五模块：Lifecycle → Security → Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0040` 起。F1-C、F1-D 仍未启动。


## M1-FUSION-GATE / F1-B Lifecycle 批次完成（2026-11-03 21:33 +08:00）

### 一句话

F1-B 第六批次（Lifecycle）完成：6 条 canonical（`SL-CAP-0040`~`0045`）、12 个原始身份正式归属、
5 个身份外推。六个验证器全绿。F1 整体仍未完成。

### 本批做了什么

- 先承接路由表真实指向 Lifecycle 的两条（`U05::C17`、`U03::C08`），再核验优先候选
- U04-C09/C11 已被 EC 的 SL-CAP-0027 占用，本批未重复占用
- U04-C24/U05-C24 已由 Research 判给 EC，本批未占用（SL-CAP-0045 因此是零来源独立设计）
- 归并为 6 条 canonical，三处合并：C02+C18+C12（Subject 身份的定义/判定/取向）、
  C01+C20（两层分离的空间与时间）、C17+C19+C26（三处失效判据合为一条检测机制）

### 核心裁决

**三轴正交。** 任务执行状态 / 知识有效性状态 / Claim 验证状态是三条独立轴：
任务失败不得当作知识失效；新鲜度变化不得自动映射成 refuted；不得因重验证未完成就删除旧结论。

**旧结论对旧版本成立，与它对新版本是否成立，是两个不同问题。** 前者是历史事实不可撤销，
后者是当前判定可变；压成一个布尔值就是本批要防的核心错误。

**路径 A（已知依赖检测）与路径 B（新事实发现）必须分离。** 共享 Collector 变化元数据，
但起点、判据、产物不同；路径 A 的「未受影响」不能替代路径 B 的「无新事实」。

**不重复实现 Collector / EC / Storage。** 采集归 Collector、裁决归 EC、并发与原子写归 Storage，
Lifecycle 只定义「何时、为什么、针对什么知识执行更新」。

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 66 |
| ROUTED | 12 |
| UNREVIEWED | 65 |
| **合计** | **143** |

`canonical_count = 45`。批次视图：Facts 11/1、Collector 11/4、EC 12/0、Product 10/1、Research 10/3、Lifecycle 12/5。

### 验证证据

- 六个验证器：12/12、30/30、50/50、43/43、46/46、48/48，全部 exit 0
- `build_lifecycle` 重跑六字段逐字节一致，分流 12 条零重复

### 本批修掉的问题

1. **Product 验证器三处作用域过时**（c14 出向计数、c38 历史批次定格、c43 新增分流去向）——
   皆因本批合法承接了 `U03-C08` 导致它从路由表移入 mapped。按「历史批次判历史事实」修正，
   核心不变量未放宽。
2. **def 里两处自身错误**：SL-CAP-0045 起初引用了已归 EC 的两个身份 + 已归 0042 的 U06-C26
   （同一身份重复映射），改为零来源独立设计并写明理由；一处字符串混入多余引号与字面换行，
   导致语法错误，改单行拼接。

### 下一步

F1-B 剩余四模块：Security → Renderer → Storage → DSH Adapter。
新 ID 从 `SL-CAP-0046` 起。F1-C、F1-D 仍未启动。


## M1-FUSION-GATE / F1-B Security 批次完成（2026-11-03 22:10 +08:00）

### 一句话

F1-B 第七批次（Security）完成：9 条 canonical（`SL-CAP-0046`~`0054`）、17 个原始身份正式归属、
5 个身份外推。七个验证器全绿。F1 整体仍未完成。

### 本批做了什么

- 先检查路由表真实指向 Security 的三条，其中 `U06-C18` 按实际内容改路由至 DSH-Adapter
- `U06-C05/C06/C07` 已由 EC 占用（0021/0028），未重复占用（c53 专检）
- `U05-C04` 已由 EC 承接，本批只登记依赖、不重新占用
- 归并为 9 条 canonical，四处合并：C01+C02（分层与卫生）、C03+C04+C12+C09（前置门与失效安全）、
  C15+C16（依赖可达性与严重度）、C14+C08（覆盖面与取证顺序）、U05-C20+U06-C17+C27（分级脱敏发布）

### 核心安全契约

- **四项独立检查**：位置存在 / 数据流链完整 / 安全影响成立 / 运行时可达；任一不可推出另一
- **没有足够证据只能停 unconfirmed**；无法验证停 inconclusive，不得自动判 false_positive
- **继承既有裁决**：U06-C06 的 can't prove → FALSE_POSITIVE 已在 EC 被拒，本批不重复占用该身份
- **环境失败绝不改判**：工具没跑不是证据
- **auth 覆盖 unknown 时 Boundary Gate 不生效**；不得用模型推断的 auth_coverage 自动降级
- **有界搜索空结果不得判 UNREACHABLE**，只判 INDETERMINATE
- **未跑扫描器时禁止输出「不存在该类漏洞」**
- **双重控制互不蕴含、默认全关、构造点钉在验证之后**
- **脱敏通过（P-2）≠ 允许发布**；P-3/P-4 只能由人触发，AI 不得自批
- **原始扫描输出不落盘是结构约束，不是事后删除**
- **PR Diff 核心证据在删除侧**；只看新增不得判「本次 PR 无安全影响」

### UPSTREAM-06 许可边界

16 个 U06 来源全部 `copy_permitted=false`，任何含 U06 的条目整体不可复制。
处置为 REUSE/ADAPT 只表示借用设计思想，不等于获得复制授权。
九条全部是 SourceLore 自建契约描述，未逐字搬运上游文本。
本轮未执行任何安全操作（无 setup.sh、无 Docker、无扫描器、无 PoC、无网络探测）。

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 83 |
| ROUTED | 14 |
| UNREVIEWED | 46 |
| **合计** | **143** |

`canonical_count = 54`。批次：Facts 11/1、Collector 11/4、EC 12/0、Product 10/1、Research 10/3、
Lifecycle 12/4、Security 17/5。

### 验证证据（全部 exit 0）

12/12、30/30、50/50、43/43、46/46、48/48、53/53

幂等：重跑六字段逐字节一致；分流零重复、无幽灵晋升、无 ID 漂移。

### 本批修掉的问题

1. **构建器/def 自身一处**：`U06-C28` 初版同时写进 0051 与 0052 的 refs，构成同一身份二次映射；
   改为只在 0051 正式归属，0052 仅作反例引用（引用从 18 条降到 17 条唯一）。
2. **Lifecycle 验证器两处作用域过时**（c15 出向计数、c47 分流去向），因本批合法承接 `U05-C20`。
   按「历史批次判历史事实」修正，核心不变量未放宽。
3. **三条断言措辞与 def 不一致**（c21/c23/c29 要求字面串），已对齐到 def 实际措辞。

### 下一步

F1-B 剩余三模块：Renderer → Storage → DSH Adapter。新 ID 从 `SL-CAP-0055` 起。
F1-C、F1-D 仍未启动。


## M1-FUSION-GATE / F1-B Renderer 批次完成（2026-11-03 23:02 +08:00）

### 一句话

F1-B 第八批次（Renderer）完成：7 条 canonical（`SL-CAP-0055`~`0061`）、11 个原始身份正式归属、
2 个身份外推。八个验证器全绿。F1 整体仍未完成。

### 本批做了什么

- 先承接路由表真实指向 Renderer 的三条：`U01-C10`、`U02-C17`、`U03-C15`
- `U02-C13/C16`、`U05-C06` 已被 Research/EC 占用，未重复占用（c47 专检）
- 归并为 7 条 canonical，一处大合并：C18/C19/C20/C21/C22/C12 六项合为一条静态校验规则集

### 核心渲染与权限裁决

- **多类型视图共享同一事实源**：报告/摘要/卡片/导航四类，同一事实不得出现不同数值
- **卡片不是 Claim 的第二份权威副本**：所有内容从上游派生，不得在渲染阶段创造新主张
- **九节结构不得规定为所有输出的统一模板**
- **拒绝强制出图但保留可选图表**：保留 U02-C17 的 REJECT 证据，处置改 REIMPLEMENT；
  无法可靠提取关系时不生成假图，缺图不构成报告不完整
- **生成产物与人工内容物理隔离**：写侧代码不得提供指向人工维护目录的分支
- **确认等级忠实呈现**：有引用不等于支持；facts_only 不得冒充完整报告；禁止视觉掩盖；不得提级
- **三级门禁互不推导**：生成完成 ≠ 脱敏通过 ≠ 发布授权；G-3 只能由人触发，AI 不得自批

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 94 |
| ROUTED | 13 |
| UNREVIEWED | 36 |
| **合计** | **143** |

`canonical_count = 61`。批次：Facts 11/1、Collector 11/4、EC 12/0、Product 10/1、
Research 10/2、Lifecycle 12/4、Security 17/5、Renderer 11/2。

### 验证证据（全部 exit 0）

12/12、30/30、50/50、43/43、46/46、48/48、53/53、48/48

幂等：重跑六字段逐字节一致；分流零重复、幽灵晋升 0、ID 漂移 0。

### 本批修掉的问题

1. **def 自身两处**：`SL-CAP-0055` 初版 refs 同时含 `U01-C10` 与 `U02-C13`（后者已归 Research 的
   SL-CAP-0038），属同一身份二次映射，已移除；`DEFERRED_TO_OTHER_MODULE` 里一处笔误
   `("UPSTREAM-03","C16").__class__ and (...)` 已改为正常键。
2. **Research 验证器两处作用域过时**（c15 出向计数、c45 分流去向），因本批承接 `U02-C17`。
3. **Lifecycle 验证器 c47 过严**：全局禁止任何分流指向 Lifecycle，但后续批次合法推入属正常。
   已收窄为只查本批 def 自己声明的那批。
4. **c28 断言措辞与 def 差一字**（「四项不可省略」vs「唯一不可省略的四项」），已对齐。

### 下一步

F1-B 剩余两模块：Storage → DSH-Adapter。新 ID 从 `SL-CAP-0062` 起。
已定向的 Storage 候选：`U04-C03`（派生索引）、`U04-C22`（并发写入）、`U04-C23`（结构化查询）、
`U06-C19`（多仓库拓扑）、`U06-C25`（三态产物契约）—— 后两条由 Security 批次分流指向 Storage。

F1-C、F1-D 仍未启动。


## M1-FUSION-GATE / F1-B Storage 批次完成（2026-11-04 00:00 +08:00）

### 一句话

F1-B 第九批次（Storage）完成：6 条 canonical（`SL-CAP-0062`~`0067`）、11 个原始身份正式归属、
2 个身份外推。九个验证器全绿。F1 整体仍未完成（只剩 DSH Adapter）。

### 本批做了什么

- 承接路由表真实指向 Storage 的五条：`U04-C03`、`U04-C22`、`U04-C23`、`U06-C19`，另有 `U06-C25` 保留原判未动
- `U05-C18/C22/C23` 与 `U04` 侧同名同义，合并处理（两份审计对同一缺口的独立记录）
- 归并为 6 条 canonical：四层模型、身份版本、原子写入、查询、多仓库关系、根目录隔离

### 核心持久化与查询裁决

- **四层资产读写权限分明**：A 不可变历史（仅 append）/ B 可变当前视图（CAS update）/
  C 派生索引（仅 rebuild，可整体删除重建）/ D 展示产物（仅 generate，不回写）
- **同一事实只有一个权威副本**；B 层与 A 层冲突时以 A 为事实源
- **六标识分列不可互替**：repository_id / subject_id / commit_sha / root_tree_sha /
  evidence_id·claim_id / artifact_version
- **写入五步契约**（临时区 → 校验 → 记录预期版本 → CAS 提交 → 失败留旧值）
- **并发冲突显式返回，不得静默覆盖；权限拒绝不得伪装成空结果**
- **多文件重命名不得宣称跨文件原子事务**，原子性范围必须如实声明
- **多仓库关系五类分离**（身份延续 / Fork / 代码依赖 / Submodule / 研究关联），
  不得因名字相同就认定经验证的影响关系；影响判定不归 Storage
- **知识根目录不得位于被分析仓库内**（对上游「一仓库一 corpus 在仓库内」的明确拒绝）
- 符号链接必须解析后校验真实路径；自动扫描结果永不写回被分析仓库

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 105 |
| ROUTED | 11 |
| UNREVIEWED | 27 |
| **合计** | **143** |

`canonical_count = 67`。批次：Facts 11/1、Collector 11/4、EC 12/0、Product 10/1、
Research 10/1、Lifecycle 12/4、Security 17/4、Renderer 11/2、Storage 11/2。

### 验证证据（全部 exit 0）

12/12、30/30、50/50、43/43、46/46、48/48、53/53、48/48、54/54

幂等：重跑六字段逐字节一致；分流零重复、幽灵晋升 0、ID 漂移 0。

### 本批修掉的问题

1. **一处归属争议按保守方式处理（重要教训）**：本批曾把 `U06-C25` 从 Storage 改判为 EC 并写入草稿，
   这违反「不得擅自更改已提交 canonical 的归属」。已从 def 撤出、恢复原判 owner=Storage，
   分歧登记为 F1-C 待裁决项 X-3。Security 验证器 c50 相应收窄作用域。
2. **构建残留**：`U06-C25` 已被第一次构建写入草稿，仅改 def 再重跑不能清除，
   必须从 `/tmp/pre-storage.json` 恢复构建前快照再重建。**教训：被撤出的条目要从基线重来。**
3. **三处断言措辞与 def 不匹配**（c18「禁止作为唯一权威来源」、c23「expected_version」、
   c44「不安装任何依赖」），已对齐。

### 重要边界声明

本轮全部是 F1 设计与产物验证。**真实数据库的事务语义、并发吞吐、崩溃恢复的实际行为
均未测试**——未安装依赖、未建库、未实现引擎、未用 Docker。

### 下一步

F1-B 最后一模块：DSH Adapter。新 ID 从 `SL-CAP-0068` 起。
可核候选：`U01-C06`（LLM provider 解耦）、`U01-C07`（单次调用 + 有界修复）、
`U01-C11`（prompt 资产）、`U01-C12`（eval baseline）、`U01-C13/C14`（REJECT 反例）、
`U06-C18`（成本报告，Security 已改路由指向 DSH-Adapter）、`U04-C15`（自主权分级）。

F1-C、F1-D 仍未启动。


## M1-FUSION-GATE / F1-B DSH-Adapter 批次完成 = F1-B 全部十批次收官（2026-11-04 00:12 +08:00）

### 一句话

F1-B 最后一批（DSH-Adapter）完成：6 条 canonical（`SL-CAP-0068`~`0073`）、7 个原始身份正式归属、
1 个身份外推。十个验证器全绿。**F1-B 十批次全部完成**，但 143 项原始能力**未全部完成归属裁决**。

### 本批做了什么

- 只读调查真实 Skill 接口：核实 `SKILL.md` + YAML frontmatter 结构、子文件渐进加载形态；
  确认项目内 `skills/sourcelore/` 仍是空目录（尚未实现）
- 未实测的接口一律标 `UNVERIFIED_RUNTIME_CAPABILITY`（BotHarness 发现、平台级状态接口、
  Skill 内工具调用通道、审批传递、上下文恢复、失败状态暴露共 6 项）
- 归并为 6 条 canonical：Skill 入口与渐进加载、模型适配与确定性边界、预算与有界修复与成本、
  任务检查点与幂等、权限门禁执行、九模块编排接口
- 产出 `F1B_REMAINDER_INVENTORY.json`：143 项逐条状态，从草稿计算而非手写

### 核心运行时契约

- **Skill 入口薄、能力按需加载**：入口只放路由指针，不把 73 条 canonical 塞进提示词
- **四类载体不可互替**：模型说明 / 程序契约 / 工具接口 / 人类审批
- **模型适配不绑供应商**，核心事实与存储契约不依赖模型能力
- **有界修复硬上限 2 次**，2 次失败即报错；禁止 while(true) 式循环
- **成本四类分列**：measured / billed / estimated / unavailable，**估算不得描述为账单**
- **超时不得自动解释为工具未执行**；工具成功与模型生成成功分开记录
- **AI 不得自批 approved**；需扩权时只登记不扩权
- **不绕过 Storage 改数据**；错误原样传播保留来源模块

### 统计口径（三态互斥，磁盘实算）

| 状态 | 数量 |
|---|---|
| MAPPED | 112 |
| ROUTED | 11 |
| UNREVIEWED | 20 |
| **合计** | **143** |

`canonical_count = 73`。十批次：Facts 11/1、Collector 11/4、EC 12/1、Product 10/1、
Research 10/1、Lifecycle 12/4、Security 17/3、Renderer 11/2、Storage 11/2、DSH-Adapter 7/1。

### 验证证据（全部 exit 0）

12/12、30/30、50/50、43/43、46/46、48/48、53/53、48/48、54/54、56/56

幂等：重跑六字段逐字节一致；分流零重复、幽灵晋升 0、ID 漂移 0。

### 剩余能力清单要点

- UNREVIEWED 20 项分 4 个语义组（分析与评估 / 研究报告 / 知识页面与质量门 / 知识库维护流程）
- ROUTED 11 项涉 4 个模块，**目标模块已完成但未承接**——这是 F1-C 要处理的实质问题
- REJECT 待裁 8 项；另有已形成反例引用的 REJECT 若干
- 归属争议 2 处：`U06-C25`（Storage vs EC）、`SL-CAP-0009`（Facts vs Storage）
- **清单明确声明：批次完成 ≠ 143 项归属全部完成，不得为凑 143/0/0 造 canonical**

### 本批修掉的问题

1. **Security 验证器 c52 作用域**：要求 `U06-C18` 改路由记录仍在路由表，但本批承接后它移入 mapped。
   改为「要么在路由表、要么已被 DSH-Adapter 承接」。
2. **模块名写法不一致**：`f1b_stats.BATCH_ORDER` 原是 `"DSH Adapter"`（空格），其余批次用连字符，
   会导致批次排序取不到位置。已统一为 `DSH-Adapter`，并在 `_MODULE_DEFS`/`BATCH_NAMES` 同步登记。
3. **c31 断言措辞**：def 写「负责**执行**权限门禁」，断言用了「只执行」，已对齐。

### 下一步

**F1-C 尚未启动，需 Owner 明确批准。** 最小可执行起点：

1. 裁决 2 处已知归属争议（`U06-C25`、`SL-CAP-0009`）
2. 裁决 20 项 UNREVIEWED 的归属（按清单的 4 个语义组逐组处理）
3. 处理 11 项 ROUTED 中「目标模块已完成但未承接」的条目——要么建卡承接、要么改判去向
4. 十项冲突裁决（F1 原定任务）
5. 处理 8 项待裁 REJECT

F1-D（全量验收 + 交叉表冻结）在 F1-C 之后。


## M1-FUSION-GATE / F1-C-A 完成（2026-11-04 01:19 +08:00）

### 一句话

F1-C 第一批完成：两处归属争议已裁（结论都是「保持原判」），31 项遗留身份基线已现算核清，
终态模型建议已提出。F1-C 总体仍 IN_PROGRESS。

### 裁决一：U06-C25 三态产物契约 → Storage（保持）

依据是 mechanism 逐字原文：「每个阶段写自己的 JSON，报告层只聚合；跳过阶段在输出里显式缺失而非空对象」。
三件事（一阶段一文件的落地形态、报告层聚合、跳过阶段显式缺失）全是产物存在性与完整性，
无一字涉及证据充分性判定。第三条尤其关键——它防的是「用空值冒充已完成」，
与 Storage 的 SL-CAP-0071「工具成功与模型生成成功分开记录」同属执行证据完整性。

否决「迁至 EC」：仅凭「三态」二字联想，原文无证据裁决语义，属误判风险。

**注意**：该身份仍是 ROUTED、**尚未被任何 canonical 承接**。SL-CAP-0062 只覆盖四层资产模型，
未显式定义「阶段产物一阶段一文件 + 跳过阶段显式缺失」。承接形态留 F1-C-B。

### 裁决二：SL-CAP-0009 Canonical Knowledge Registry → Facts（保持）

依据四项字段：input 是 SL-CAP-0001 的文件与符号清单（Facts 自己的产出），
output 是 `registry.json: entries[] + aliases + merge/split 记录`（决策留痕，不是存储布局），
description 全句讲「名字/别名如何归一、冲突如何留痕、不够格的去哪里」。

否决「迁至 Storage」：与 SL-CAP-0062/0064 大面积重叠，会造成一条事实两个 owner。
否决「拆分」：现有 Storage canonical 已完整承接持久化面，拆分只是重复造卡。

边界一句话：**Registry 定义「什么叫同一个实体」；Storage 定义「这条记录怎么安全落地」。**

### 遗留基线（现算，无人工录入固定数）

| 项 | 值 |
|---|---|
| 原始身份 | 143 |
| MAPPED | 112 |
| ROUTED | 11 |
| UNREVIEWED | 20 |
| 遗留合计 | 31 |

ROUTED 分布：Evidence-Claims 5、Lifecycle 4、Renderer 4、Storage 1。
**四个目标模块的批次都已完成，但这些身份没被承接**——这是 F1-C-B 要处理的实质问题。

UNREVIEWED 分 4 组：分析与评估 4、研究报告与外部资料 2、知识页面与质量门 3、知识库维护流程 11。

待裁 REJECT 8 项，**全部落在 31 项遗留集合内**，不额外新增；另有 13 项 REJECT 已绑 canonical（属 MAPPED，单列）。

### 终态模型建议

现有三态只表达「映射进度」，无法表达处置性质。建议**新增正交的 `terminal_disposition` 字段**
（ADOPTED / ADOPTED_AS_COUNTEREXAMPLE / REJECTED_WITH_REASON / DEFERRED_WITH_REASON / INTERNAL_DESIGN_ONLY），
`state` 继续表达「进没进 canonical」（守恒仍按 143）。这样十个既有验证器读 `state` 的断言不受影响。

**本批未实施**，须由 F1-C 后续批次统一做。

### 本批未做

未改动任何 owner / ID / ROUTED / UNREVIEWED；未重跑 F1-B 构建器；未启动 F1-C-B/C/D、F1-D、F2；
Crosswalk 逐字节未改（机检 `applied_changes_this_batch` 为空）。

### 验证证据（全部 exit 0）

`f1c_a_verify.py` 16/16；十个 F1-B 验证器 12/30/50/43/46/48/53/48/54/56 全绿；
基线重跑逐项一致（`f1c_a_baseline.py` 幂等）。

### 本批修掉的问题

**★ 元组换行写法踩坑四次。** `return (expr),` 后换行接 `f"..."` 会被解析成单元素元组而非二元组，
报 `ValueError: not enough values to unpack`。正确写法是先算 `detail = (...)` 再 `return (cond), detail`。
（上一批已记录「多行 return 元组是语法雷区」，本批又在同一处摔了四次 —— 说明这条要写进验证器模板本身。）

**c15 断言措辞**：文档写「唯一建议 owner：Storage」，断言查「保持 Storage」，已对齐。

### 下一步

**F1-C-B 最小执行起点**：
1. 先处理 11 项 ROUTED 的「已完成未承接」——逐条二选一：建卡承接或改判去向
2. 先定 U06-C25 的承接形态（Storage 已定，但未落 canonical）
3. 按语义组处理 20 项 UNREVIEWED（建议从 U05 系 11 项开始）
4. 8 项待裁 REJECT 逐条定性
5. 十项冲突裁决（F1 原定任务）
6. 实施终态模型扩展 + 配套验证器


## M1-FUSION-GATE / F1-C-B 完成（2026-11-04 10:10 +08:00）

### 一句话

F1-C-B 完成：11 项 ROUTED 全部清算——7 项承接到已有 canonical、1 项新建 SL-CAP-0074、3 项 DEFER。
两处前置勘误已处理。F1-C 总体仍 IN_PROGRESS。

### 门禁一：ROUTED 是 11，不是 14

真实集合 11，分布 **EC 7 / Lifecycle 2 / Renderer 1 / Storage 1**。
`F1C_REMAINDER_BASELINE.json` 记的就是这个分布，可逐个数出。
**14 是我上一轮汇报时抄错的**——恰好等于 F1-B 早期某时点的历史峰值，属记忆串扰。数据文件没错。
未触发停止条件。

### 门禁二：SL-CAP-0071 引用错误

SL-CAP-0071 的真实 owner 是 **DSH-Adapter**，不是 Storage。
修正：Storage 侧支撑完整性约束的是 SL-CAP-0062（D 层不得回写权威层）；
SL-CAP-0071 作跨模块依赖引用，不得当 Storage 能力举证。
**语义裁决不变（U06-C25 → Storage）。** 勘误已写入登记表 `decisions[F1C-A-001].errata_applied`。

### 11 项裁决

| 身份 | 方向 | 落实 |
|---|---|---|
| U04-C24 / U05-C24 | 承接 | SL-CAP-0020（reproducible 三态已覆盖） |
| U05-C04 | 承接 | SL-CAP-0028 + 值域约束（approved 只能人设） |
| U06-C10 / U06-C20 | 承接 | SL-CAP-0028（无许可，只借思想） |
| U06-C25 | **新建** | **SL-CAP-0074 阶段产物完整性投影** |
| U05-C14 | 承接 | SL-CAP-0060 + 呈现细则（content_hash 替代短 SHA） |
| U05-C19 | 承接 | SL-CAP-0028 + 字段级约束（human_authored 拒 AI 写） |
| U04-C16 | **DEFER** | owner 存疑：Lifecycle 无「任务完成判据」canonical |
| U05-C10 | **DEFER** | 分流理由含双 owner，违反「一身份一 owner」 |
| U01-C12 | **DEFER** | EC 无「评测集构建」canonical，指向悬空 |

**3 项 DEFER 仍保持 ROUTED 状态，未假称 MAPPED。**

### SL-CAP-0074 的独立必要性

不并入 0062：0062 讲四层读写权限与单一权威，插入「阶段集合完整性」会混淆两个维度。
不并入 0064：0064 讲单次写入原子性，不回答「整个 run 的产物集合是否完整」。
新条专讲「跳过阶段必须显式缺失而非空对象」，作为 0062 D 层子契约。UPSTREAM-06 无许可，自建契约。

### 应用方式（重要工程决定）

`f1c_apply_routed.py` **从 `F1B_FROZEN_BASELINE.json` 重建再叠加裁决**，不是在当前草稿上打补丁。
所以撤销裁决重跑**不会遗留历史路由**——不是靠手动删，是根本没有残留。
已验证幂等（重跑逐字节一致）、ID 从真实最大值分配、重复映射会抛错。

### 数字

| 项 | 前 | 后 |
|---|---|---|
| MAPPED | 112 | **120** |
| ROUTED | 11 | **3** |
| UNREVIEWED | 20 | 20 |
| canonical | 73 | **74** |

### 验证

`f1c_b_verify.py` 20/20；十二个验证器全链绿（12/30/50/43/46/48/53/48/54/56/16/20），全部 exit 0。

### 本批修掉的问题

1. **应用层真 bug**：首版只写 Crosswalk，没同步 `CROSSWALK_PROGRESS.json`，导致所有验证器「进度同源」检查全红。已并入应用层。
2. **★ 元组换行写法又踩 5 次**（`return (expr),` 换行接字符串 → 单元素元组）。已加全局正则自检，写完立即扫。
3. **历史验证器作用域 11 处**：mapped 定格 `==`→`>=`；Storage canonical_ids 改「本批 6 条全在」；
   Storage c51/c53 改三分支；DSH-Adapter c44 改「清单不得陈旧」。核心不变量未放宽。

### 下一步：F1-C-C

1. 先裁 3 项 DEFER 的 owner（U04-C16、U05-C10、U01-C12）
2. 20 项 UNREVIEWED，建议从 U05 系 11 项起
3. 8 项待裁 REJECT 定性
4. 十项冲突裁决

F1-C-D 再统一实施 `terminal_disposition` 与交叉表冻结。


## M1-FUSION-GATE / F1-C-C1 完成（2026-11-04 12:10 +08:00）

### 一句话

F1-C-C 阶段 1 完成：3 项 DEFER 全部终裁——2 项承接到已有 canonical、1 项新建 SL-CAP-0075。
**ROUTED 归零。** F1-C 总体仍 IN_PROGRESS。

### 三项裁决

| 身份 | 旧 owner | 新 owner | 承接 |
|---|---|---|---|
| U04-C16 完成检查（三处） | Lifecycle | **DSH-Adapter** | SL-CAP-0071 + 退出判据 G-1..G-3 |
| U05-C10 契约式 Postconditions | Lifecycle（双 owner） | **Storage** | SL-CAP-0064 + 写入后校验 W-2' |
| U01-C12 eval baseline | EC（指向悬空） | **Evidence-Claims** | **新建 SL-CAP-0075** |

### 三项裁决的关键依据

**U04-C16 → DSH-Adapter**：三处 where 全是「这一步做完没」，无一处涉及「知识还成不成立」。
SL-CAP-0071 有状态机但**没有退出判据**——记录状态 ≠ 判定完成。补 G-1（阶段需产出物或显式 skipped）、
G-2（不得模型自评）、G-3（判据可复算）。

**U05-C10 → Storage**：校验对象是**写盘后的产物**。原分流「归 Lifecycle 与 Storage」
一句话指两个 owner，本身不合规。与 0064 的 gap：W-2 是**写入前**校验，
本条要的是**写入后**校验——写入前通过不等于写入后满足。补 W-2'。
与 C16 的分野：**C16 判「做完没」→ DSH-Adapter；C10 判「写对了没」→ Storage。**

**U01-C12 → EC 新建 SL-CAP-0075**：两批都推向 EC 但 EC 无对应 canonical，指向悬空。
复核后 EC 确实合适——**判定器的主人必须能证明判定器准**，EC 拥有裁决状态机，
那「这套判据本身有多准」的校准责任自然归它。这与「判定某条 claim 真假」是不同层次，故需独立卡。

**关键区分（用户强调）**：拒绝 U01-C13/C14 的付费 API 与多模型 judge，
**不等于**拒绝离线基准评测。SL-CAP-0075 的 V1 只用 gold 集 + 确定性指标：
离线、零外部依赖、可复算。E-2 明确「任何单一指标（含 F1）不得作为唯一门槛」——
上游 click 案例 F1=0.00 已证明单指标误判。

### 历史验证器补强（第 7 节）

此前把 mapped 定格从 `==` 放宽为 `>=`，**只保证数量没减少，没保证集合内容没被换掉**——
理论上可以把 A 身份从 X 移除、同时把 B 加入 X，总数不变但语义已错。

新增 `tools/fusion/f1c_history_invariants.py`，三项集合级检查：
1. `check_identity_mapping_preserved` — 映射不得无记录变化，迁移必须来自已登记裁决
2. `check_canonical_ids_not_reused` — 已有 ID 的 name/owner 不得变更
3. `check_amendments_recorded` — 核心字段变更必须有留痕 + recon 记录

已接入 EC、F1-C-A、F1-C-B 三个验证器，均新增 `c_hist` 项并通过。
**未放宽任何不变量。**

### 数字

| 项 | F1-C-B 后 | 本批后 |
|---|---|---|
| MAPPED | 120 | **123** |
| ROUTED | 3 | **0** |
| UNREVIEWED | 20 | 20 |
| canonical | 74 | **75** |

**REJECT 0 / DEFER 0**——三项全部终裁，无残留延期。

### 验证

`f1c_c1_verify.py` 15/15；十三个验证器全链绿
（12/30/51/43/46/48/53/48/54/56/17/21/15），全部 exit 0。

### 本批修掉的问题

1. **批次标记 `F1-F1-C-B`**：生成器把 `F1-` 与已含前缀的批次名重复拼接，已修正。
2. **四处历史验证器作用域**：EC c8/c16（编号集改为「原有全在+允许并入」）、
   Renderer c45（改为「去向必须合法模块」不硬编码）、F1-C-B c14（DEFER 需带解除条件+显式解除记录）。
3. **历史不变量检查器自身缺陷**：初版把「canonical 上已存在任何 amendment」当本批新增，
   误判 F1-C-B 留下的 amendment。已改为只校验该 recon 自己声明的 AMEND 目标。

### 下一步：F1-C-C2（U05 系 11 项 UNREVIEWED）

先列完整身份与原始 disposition，按「已被现有 canonical 覆盖」分组：
- 已覆盖不重复：U05-C18→0062、U05-C22/C23→0064/0065、U05-C04/C14/C19→已处理
- 待处理重点：U05-C12（渐进式 AI 投喂）、C13（C4 强制顺序）、C15（发布节奏）、
  C16（测试用例维护触发）、C21（冲突处理）、C25（测试覆盖作为质量证据）

F1-C-D 再统一实施 `terminal_disposition` 与交叉表冻结。


## M1-FUSION-GATE / F1-C-C2 完成（2026-11-04 12:32 +08:00）

### 一句话

F1-C-C2 完成：UPSTREAM-05 剩余 **10 项**未审全部终裁——8 项承接到已有 canonical（无新增卡）、
2 项维持 REJECT。F1-C 总体仍 IN_PROGRESS。

### 先核清一个数字

**U05 未审是 10 项不是 11。** 汇报稿写 11 是上一轮的抄写错误；
`F1C_REMAINDER_BASELINE.json` 自 F1-C-A 起记录的 U05 未审组一直是这 10 项
（C07/C08/C12/C13/C15/C16/C21/C25/C27/C28），可逐个数出。数据文件无误，未强行凑 11。

### 10 项裁决

| 身份 | 方向 | owner | 承接 |
|---|---|---|---|
| C07 命令族与编号页集 | 承接 | Lifecycle | SL-CAP-0040 + 可枚举命名原则 |
| C08 Phase 0 三分路由 | 承接 | Research | SL-CAP-0035 + 档位分流 |
| C12 渐进式 AI 投喂 | 承接 | Research | SL-CAP-0035 + 读取顺序 |
| C13 C4 强制顺序 | 承接 | Research | SL-CAP-0035 + 粒度降序（拒绝强制 C4） |
| C15 发布节奏绑定 | 承接 | Lifecycle | SL-CAP-0043 + release/PR 触发 |
| C16 测试用例维护触发 | 承接 | Lifecycle | SL-CAP-0044 + 测试文件变动纳入路径 B |
| C21 冲突处理 | 承接 | Evidence-Claims | SL-CAP-0028 + conflict 旁支 |
| C25 测试覆盖作为质量证据 | 承接 | Evidence-Claims | SL-CAP-0075 + 覆盖率四条禁令 |
| C27 产出整册项目文档 | **拒绝** | — | 保持 UNREVIEWED |
| C28 双语 Sphinx 站 | **拒绝** | — | 保持 UNREVIEWED |

**新增 canonical = 0**，全部复用已有能力 + amendment。

### 三个最容易判错的地方

**① C21 四类冲突不能合并成一个全局机。**
Claim 证据冲突→EC(0028)、历史与当前冲突→Lifecycle(0041)、
并发写入冲突→Storage(0064)、人工与生成冲突→Renderer(0058)。
原始 C21 语义是①（上游知识治理语境的「两条知识矛盾」），故 owner=EC。
amendment 里写死「不得把这四类合并成一个全局冲突机」。

**② C13 采纳 C4 的合理部分、明确拒绝其强制机制。**
采纳「从粗到细的阅读粒度降序」（系统边界→部署单元→组件→代码）；
**拒绝「所有仓库必须按 C4 四级产出」**，也**拒绝「关系证据不足时补全结构图」**
（后者与 SL-CAP-0057 的强制出图拒绝同源）。

**③ C25 覆盖率四条禁令。**
覆盖率≠正确性、测试存在≠测试通过、测试通过≠全部功能已验证、
上游若有测试目录或覆盖率数字**不得直接提升为「已验证」**。
准入原则：机制必被测，不以「有 tests 目录」为准入。

### 两项 REJECT 为何保持 UNREVIEWED

现三态无法表达「已裁决为拒绝」。按第 6 节「不得假 MAPPED」：
保持真实旧状态、终态 `REJECTED_WITH_REASON` 只记在裁决数据与清算记录、
标记 `awaiting: F1-C-D terminal_disposition 迁移`。

### 历史保护增强（第 7 节）

新增**独立全局历史验证入口** `tools/fusion/f1c_history_verify.py`，可被 F1-D 直接调用，10 项检查。
其中 `c10` 机检「本入口不得 import 任何 f1b_verify*」——确保它真的独立于历史批次验证器。

**修掉一处检查器缺陷**：初版 `c5` 把 `upstream_disposition`（上游原始处置，不得改写）
与 `verdict`（SourceLore 自己的裁定，可与上游不同）混为一谈，
误报 `UPSTREAM-06::C13`（上游 ADAPT 但 SourceLore 判 REJECT，属正常）。
**教训：两个语义不同的字段，检查时不能拿一个去要求另一个。**

### 数字

| 项 | F1-C-C1 后 | 本批后 |
|---|---|---|
| MAPPED | 123 | **131** |
| ROUTED | 0 | 0 |
| UNREVIEWED | 20 | **12** |
| canonical | 75 | 75 |

### 验证

`f1c_c2_verify.py` 18/18；`f1c_history_verify.py` 10/10；
十五个验证器全链绿（12/30/51/43/46/48/53/48/54/56/17/21/15/18/10），全部 exit 0。

### 本批修掉的问题

1. **lifecycle c38 快照语义**：文档是历史快照（记 12/6/4），不能用当前值（15）去要求它。
   改为「文档须含本批历史数字 + 本批 6 条仍在 canonical_ids 中」。
2. **历史验证器 c5 字段混淆**（见上）。
3. **验证器自身两处小错**：c3 有个残留的错误集合表达式；c18 断言用 `U05::C07` 格式而文档写 `C07`，已对齐。

### 下一步：F1-C-C3（U01/U02/U03 剩余 10 项）

剩余 UNREVIEWED 12 项，其中 U05 的 C27/C28 已裁（等迁移），实际待处理 10 项：
U03 × 4（C23 五档证据优先级、C24 强制 D2、C25 禁用基础设施、C26 术语独立成页）——**全部 REJECT，同源，建议成组处理**
U04 × 5（C05 按需加载模式指引 REUSE、C06 不存密钥凭据 REUSE、C13 报告粒度禁令 ADAPT、
C21 冲突处理 REIMPLEMENT、C27 HTML/excalidraw 产物格式 REJECT）
U06 × 1（C21 模型分层 REJECT）

**最易判错**：U04-C21「冲突处理（两个报告判断不同）」与本批 U05-C21 同名但语义不同——
前者是**报告之间**的判断差异（Research 层），后者是**Claim 之间**的证据冲突（EC 层）。必须分开裁。


## M1-FUSION-GATE / F1-C-C3 完成（2026-11-04 14:40 +08:00）

### 一句话

F1-C-C3 完成：剩余 10 项全部终裁（8 承接、2 REJECT、0 新增 canonical）。
**至此 143 项原始能力全部有终裁。** F1-C 各子批次完成，剩 F1-C-D 收口。

### 十项裁决

| 身份 | 方向 | owner | 承接 |
|---|---|---|---|
| U03-C23 五档证据优先级 | 承接 | Research | SL-CAP-0037 + 反例 |
| U03-C24 D2 图规范 | 承接 | Renderer | SL-CAP-0057 + 反例 |
| U03-C25 禁 AST/图库/索引 | 承接 | Facts | SL-CAP-0001 + 技术选型立场 |
| U03-C26 术语独立成页 | 承接 | Renderer | SL-CAP-0055 + 两级策略 |
| U04-C05 按需加载模式指引 | 承接 | **DSH-Adapter** | SL-CAP-0068 + 匹配细则 |
| U04-C06 不存密钥凭据 | 承接 | **Security** | SL-CAP-0053 + 覆盖面 |
| U04-C13 报告粒度禁令 | 承接 | Lifecycle | SL-CAP-0040 + 粒度门槛 |
| U04-C21 冲突处理（两报告不同） | 承接 | **Research** | SL-CAP-0038 + 报告间分流 |
| U04-C27 HTML/excalidraw | **拒绝** | — | 保持 UNREVIEWED |
| U06-C21 模型分层 | **拒绝** | — | 保持 UNREVIEWED |

### ★ U04-C21 与 U05-C21 的边界判定（本批最关键）

同名「冲突处理」，对象完全不同：

| | U05-C21 | U04-C21 |
|---|---|---|
| 对象 | 两条 Claim 的证据互相矛盾 | 两份研究的解释不一致 |
| 性质 | 一方错，须裁决真伪 | 可能两者都对（视角不同） |
| owner | **EC / SL-CAP-0028（conflict 旁支）** | **Research / SL-CAP-0038** |
| 处理 | 进状态机，不得强行收敛 | 先分辨两类再分流 |

补两条分流规则：视角差异→并列呈现各标适用条件不判谁错；
事实冲突→产出 handoff_item 移交 EC，**Research 不自行裁决**。
**不为所有冲突建第二套统一状态机**——结论状态只有 0028 一处。

### 三条 REJECT 的实质区别（不批量同一句）

- **C23**：拒「五档机械排序」（五档无权重不成全序 + 允许任意层级 → 自我消解）；保留标注原则
- **C24**：拒「强制单一图示语法 + 无校验」（L1046 强制 D2 却无工具链、无语法校验）
- **C25**：拒「禁止使用确定性设施」这条**自我设限**（Facts 恰恰要用 AST、Storage 恰恰要用索引；
  技术选型权留 F2，不设永久禁令）
- **C26**：拒「无条件逐术语建页」，采纳两级策略（术语表 → 按需升格）

### U06-C21 的许可边界

**UPSTREAM-06 无明确复制许可（copy_permitted=false）**——零复制，
只借「按任务复杂度与工具能力选路」的抽象思想（已由 0069/0070 覆盖）。
不把任何供应商或具体模型名写死为架构前提。

### 数字

| 项 | F1-C-C2 后 | 本批后 |
|---|---|---|
| MAPPED | 131 | **139** |
| ROUTED | 0 | 0 |
| UNREVIEWED | 12 | **4** |
| canonical | 75 | 75 |

4 项 UNREVIEWED 全部是已裁 REJECT：U04-C27、U05-C27、U05-C28、U06-C21。

### 验证

`f1c_c3_verify.py` 19/19；十六个验证器全链绿
（12/30/51/43/46/48/53/48/54/56/17/21/15/18/19/10），全部 exit 0。幂等成立。

### 本批修掉的问题

**def 语法两处**：一处 `)` 误写为 `],`（`reason:` 收尾）、一处多余括号。已修正。
**两处历史验证器作用域**：F1-C-A c5（待裁 REJECT 会被后续批次承接，改为「仍在遗留集/已被 REJECT verdict 承接」）；
F1-C-C2 c14（totals_after 是快照，改为「快照自洽 + 当前未倒退」）。
**验证器自身三处**：c9 断言查错关键词（理由里是「绑死 Claude 家族」不是「供应商」）；
c15 用了函数外的 `unrev` 变量；c19 断言的 ID 格式与文档不一致。

### 下一步：F1-C-D

清单已生成 `docs/fusion/F1C_D_HANDOFF_INVENTORY.json`（`f1c_d_handoff.py` 现算）：

1. **terminal_disposition 迁移**（4 项 REJECT + 历史 ADOPTED_AS_COUNTEREXAMPLE 分类；正交字段，不改 state）
2. **8 项待议跨模块冲突**（X-2/X-4/X-5/X-6/X-7、K-7、Y-4、Y-6）
3. **7 条零来源 canonical** 的来源说明归档
4. **17 条反例绑定** + 2 条 U06 无许可引用的许可证复核
5. **冻结前**复跑 `f1c_history_verify.py`，再冻结 `CAPABILITY_CROSSWALK.json`
