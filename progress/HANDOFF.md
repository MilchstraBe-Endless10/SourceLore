# SourceLore 交接文档

> 本文件是跨会话恢复的唯一入口。任何新会话第一件事就是读它。
> 最后更新：2026-11-02T15:36:00+08:00

---

## 一、现状

M1 六个上游只读审计全部完成，等用户启动 M1-FUSION-GATE。M2 开发未开始。

- 项目根：`/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore`
- 当前里程碑：**M1（六源审计 DONE）**
- 当前任务：**无**（`active_task` 为 null）
- 下一任务：**M1-FUSION-GATE**（需用户明确启动）
- 开发模型：`workbuddy/deepseek-v4.1-flash`（上下文 131072，务必小步走）

## 二、已通过的 Gate

| Gate | 判定 | 证据 |
|---|---|---|
| M0：可读取和安全写入指定目录 | PASS | `BASE_WRITABLE=YES`；骨架已创建；`git init` 成功 |
| M0：模型能运行最小工具实验 | PASS | bash / git / python3 venv / SQLite FTS5 / curl 全部实跑成功 |
| M0：DSH 技能路径有依据 | PASS | 用户级根 `<DSH_HOME>/skills` 经 Catalog 交叉验证；三个 skill Provider 已注册 |
| UPSTREAM-01~06：单源只读审计 | PASS | 每源九项门禁实跑，退出码均为 0，详见各 `docs/upstream-audit-0N-*.md` §验收 |

## 三、最后一条真实命令与退出码

```
python3 - <<'PY'  # UPSTREAM-06 九项门禁
... SHA / 证据路径 / Markdown-JSON 一致性 / 许可证处置 / 静态动态不混淆 / 快照完整性 / 敏感内容 ...
PY
```

```
FAILURES: 0
```

`exit=0`

## 四、本回合实际修改的文件

| 文件 | 说明 |
|---|---|
| `docs/upstream-audit-06-repo-security-review.md` | UPSTREAM-06 审计报告，15 章 |
| `progress/UPSTREAM-06-audit.json` | 结构化审计记录 |
| `docs/upstream-manifest.json` | 补全 UPSTREAM-06 条目（含无许可证说明） |
| `THIRD_PARTY_NOTICES.md` | 新建。六源许可状态与零复制事实 |
| `progress/TASKS.json` | UPSTREAM-06 转 DONE |
| `progress/STATE.json` | `next_task` 改为 M1-FUSION-GATE |
| `progress/HANDOFF.md` | 本文件 |

## 五、测试

`NOT_RUN`。M1 六个上游全部禁止执行上游代码、禁止安装依赖、禁止启动容器、禁止对真实部署发起请求。审计类验证以真实命令输出为准，逐条记录在各审计文档的验收节。**不得把任何一源的审计读作「该工具已通过安全测试」。**

## 六、Git HEAD

`094a0d8bb4f879d5da8046bbb91a9fbf8effecfc` —— UPSTREAM-06 审计提交。前一条 `fe36c7d` 是 UPSTREAM-05 的 SHA 回填提交。

## 七、下一步

**M1-FUSION-GATE**。六源审计已全部 DONE，但融合还没开始。

M1 硬性约束（来自总控提示词 §G）：

- 六个上游**一次只处理一个**，每个都固定 Commit SHA —— 已完成
- 每个都要查 LICENSE / NOTICE / 文件头许可证声明 —— 已完成
- 每个都要读 SKILL.md 与脚本，列出可复用能力与兼容性风险 —— 已完成
- 逐个更新 `docs/upstream-manifest.json` 与 `docs/fusion-matrix.md` —— manifest 已完成；**`docs/fusion-matrix.md` 尚未产出**，属 M1-FUSION-GATE 的活
- **严禁把六个 SKILL.md 原样拼接**
- 未到 M1 Gate 不得开始大规模融合编码

融合阶段要处理的具体账（按优先级）：

1. `MANIFEST_FORMAT_DIVERGENCE`（medium）：UPSTREAM-02 的 TSV 是 `type/bytes/path`，其余是 `path/bytes/blob_sha`。Manifest V2 已提出未定稿。
2. 06 的 C05 四节点证据结构如何并入 03 的 Claim/Evidence —— 是字段扩展还是新层，需定。
3. 06 的 C04 边界门依赖 `auth_coverage`，而该映射必须改成确定性抽取；精度不足时门只能降级为标注（06 的 Q2）。
4. 否定结论的覆盖面字段（06 的 C14）与 04 的增量机制语义冲突，需统一定义（06 的 Q3）。
5. `disputed` 的裁决权归属仍未定（结转自 UPSTREAM-04/05）。

## 八、已知限制

1. **上下文 131072**：不能大段读上游源码，必须用脚本采事实 + 分页读取
2. **会话 cwd 不在项目根**：所有命令必须绝对路径或显式 cd
3. **路径含括号与中文**：shell 必须引号，Python 用 pathlib
4. **Skill 源码目录不是发现根**：M6 必须安装到发现根并用 Catalog 复验
5. **Tobs 会话 cwd 不是项目根**：M7 触发依赖用户级 skill 根，需专门验证
6. **`upstreams/` 被 `.gitignore` 排除**：快照副本不进历史，只是审计期只读材料
7. **UPSTREAM-06 无许可证**：该源只可取抽象设计思想，不得复制任何源码、提示词、规则原文或模板；边界宽度需法务判断（其 U10）

## 九、恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' && git log --oneline -5 && python3 -m json.tool progress/STATE.json && python3 -m json.tool progress/TASKS.json | head -40
```

然后读 `progress/STATE.json` 的 `next_task`。当前应为 `M1-FUSION-GATE`。

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
