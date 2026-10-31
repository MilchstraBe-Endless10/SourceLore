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
