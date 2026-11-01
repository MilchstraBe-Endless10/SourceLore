# UPSTREAM-05 审计：walterfan/lazy-rabbit-skills · skills/project-knowledge-base

- 任务：UPSTREAM-05（M1 多源上游审计，第五源）
- 审计对象：`walterfan/lazy-rabbit-skills`，子树 `skills/project-knowledge-base/`
- 上游固定提交：`284971cdd2666878d13716af8f26f51521cd915c`
- 审计方式：本地固定快照静态阅读，零脚本执行、零依赖安装
- 审计执行：DeepSeek-V4.1 Flash（DSH 执行 Agent）
- 审计时间：2026-11-02 00:30 +08:00

---

## 1. 上游事实

### 1.1 仓储身份

| 项 | 值 |
|---|---|
| Repository ID | 1275141665 |
| URL | https://github.com/walterfan/lazy-rabbit-skills |
| 描述 | lazy rabbit's AI skills |
| 默认分支 | master |
| 固定提交 SHA | 284971cdd2666878d13716af8f26f51521cd915c |
| 提交日期 | 2026-08-16T01:54:22Z |
| 提交信息 | add more skills |
| 作者 | Walter Fan |
| 主语言 | Python |
| 体积 | 981 KB |
| Star / Fork / Issue | 0 / 0 / 0 |
| 归档 / 派生 | 否 / 否 |
| 创建时间 | 2026-06-20T09:56:51Z |
| 最近推送 | 2026-08-16T01:54:31Z |

该仓库是作者个人维护的 skill 集合，含 40 余个并列 skill。本审计只取 `skills/project-knowledge-base/` 一棵子树。`pkb-collect` 与 `pkb-refer` 是它的两个兄弟 skill，正文中被引用，但未读未判。

### 1.2 固定快照

| 项 | 值 |
|---|---|
| 快照目录 | upstreams/UPSTREAM-05-lazy-rabbit-skills |
| tree.json SHA | 284971cdd2666878d13716af8f26f51521cd915c |
| tree.json 条目 | 477（truncated = false） |
| 落地 blob 数 | 66 |
| files.tsv 行数 | 66 |
| 总字节 | 488925 |
| 内容校验 | 共 66 行，失败=0 |

快照完整性用真实命令核验，不是引用上游元数据。逐行取 `files.tsv` 的路径与哈希，用 `git hash-object` 重算 blob SHA，用 `wc -c` 重算字节数，66 行全部一致，退出码 0。磁盘上 `tree/` 的实际文件数也是 66，与 TSV 行数相等，无缺失、无多余。

TSV 形态与前三个上游一致：无表头，三列 `path<TAB>bytes<TAB>git_blob_sha`，第 1 列为仓库相对路径，校验时需在其前缀 `tree/`。

固定 SHA 的核验全部在本地快照上完成。本轮没有重新拉取远程内容，也没有切换到 main 分支，避免漂移内容替换已有证据。

### 1.3 真实文件清单

快照根部只有三项：`LICENSE`、`README.md`、`skills/`。子树 `skills/project-knowledge-base/` 的结构如下。

顶层文件：

| 文件 | 字节 |
|---|---|
| Makefile | 2211 |
| SKILL.md | 50060 |
| poetry.lock | 111770 |
| prompts.md | 14846 |
| pyproject.toml | 756 |

`references/` 6 个文件：`c4-standard.md`、`commands.md`（17123 B）、`failure-modes.md`（8059 B）、`help-text.md`、`sphinx-bilingual.md`（16236 B）、`verification-gates.md`（3618 B）。

`scripts/` 18 个文件：

| 脚本 | 在 SKILL.md 中声明 |
|---|---|
| check_pkb_staleness.py | 是 |
| check_translation_sync.py | 是 |
| extract_api_signatures.py | 是 |
| gen_changelog.sh | 是 |
| gen_dep_graph.py | 是 |
| gen_index.py | 是（作为 gen_index.py 在命令表中提及） |
| gen_repo_map.sh | 是 |
| gen_tech_stack.py | 是 |
| init_pkb.sh | 是 |
| pkb_review_status.py | 是 |
| strip_confidential.py | 是 |
| update_doc_level1.sh | 是 |
| generated_output.py | 否 |
| generated_output.sh | 否 |
| render_landing.py | 否 |
| translate_po.py | 否 |
| validate_skill_consistency.py | 否 |
| validate_template_links.py | 否 |

`tests/` 3 个文件：`__init__.py`（1 字节）、`test_bilingual_scaffold.py`（2801 B，1 类 2 方法）、`test_confidentiality.py`（12442 B，5 个测试类共 17 方法）。合计 6 类 19 方法。

`templates/` 四组：`adr/`、`changes/`、`docs/`（00–12 共 13 个编号页）、`sphinx/`。

配置文件三个：`pyproject.toml`（Poetry，`requires-python = "^3.10"`，11 个 Sphinx/i18n 依赖，`package-mode = false`）、`poetry.lock`、`Makefile`。

这是 M1 五源中第一个同时具备脚本层、测试层与依赖清单的上游。UPSTREAM-04 的子树上零脚本、零测试、零 CI，两者在工程完整度上不在一个层级。

### 1.4 许可证

| 项 | 值 |
|---|---|
| 声明 | Apache-2.0 |
| API spdx_id | Apache-2.0 |
| API blob SHA | 261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64 |
| API size | 11357 |
| 本地字节 | 11357 |
| 本地行数 | 201 |
| 逐字节一致 | 是 |

快照中的 `LICENSE` 是完整的 Apache License 2.0 原文，首行为 `Apache License`、次行 `Version 2.0, January 2004`，`Apache License` 全文出现 4 次，201 行。与 API 返回的 blob SHA 和字节数逐项吻合。

关于 NOTICE：快照根目录只有 `LICENSE`、`README.md`、`skills/` 三项，无独立 `NOTICE` 文件。全树大小写不敏感检索 `NOTICE|copyright|third.party|third-party`，只命中两处：`LICENSE` 本身（Apache-2.0 原文含 Copyright 段落）与 `references/commands.md`（正文提及，非声明）。没有第三方版权声明文件。

因此许可证义务判定如下。Apache-2.0 §4 要求再分发时保留 LICENSE 与 NOTICE（若有）。本仓库无 NOTICE，故仅有保留许可证与修改声明的义务。`pyproject.toml` 声明的 11 个依赖（sphinx、myst-parser、sphinx-rtd-theme、furo、sphinx-copybutton、sphinx-design、sphinx-autobuild、sphinxcontrib-mermaid、sphinxcontrib-plantuml、sphinx-intl、polib）均为文档构建工具，仓库内未 vendored 任何第三方源码。SourceLore 不复制其代码，只借鉴设计，不产生再分发义务。

这是五源中第一个许可证可以确定判定的上游：01 与 02 未知，03 为 NOASSERTION，04 为 MIT。

### 1.5 静态 / 动态状态

本轮全部为静态审计。18 个脚本一个都没执行，测试一个都没跑，依赖一个都没装。凡涉及行为判断的结论，均基于源码阅读，标记为 `NOT_RUN`。

---

## 2. 能力审计

判定沿用 UPSTREAM-04 的四档口径：REUSE 原样采纳取向，ADAPT 借骨架改细节，REIMPLEMENT 只借概念不借实现（缺失或实现有实质缺陷），REJECT 不采纳。

能力边界按源码实际提供的机制切分，共 28 项。没有按 27 项凑数：UPSTREAM-04 的 27 是那一轮真实切分的结果，本轮真实切分出来是 28。

### 2.1 能力矩阵

| 能力 | 上游实现位置 | 判定 | 治理与证据 |
|---|---|---|---|
| C01 脚本优先、规则先行、零token前置 | SKILL.md L131–L136；L306–L315 | REUSE | 零token确定性层，先跑规则判断是否过期，规则说没事就不花 token |
| C02 三级更新梯度 L1/L2/L3 | SKILL.md L138–L140；L339–L347 | REUSE | L1 零token机械改、L2 低token受限上下文、L3 人主导AI只润色 |
| C03 旁车产物与叙事页分离 | SKILL.md L158–L162；scripts/generated_output.py L19–L23 | REUSE | 脚本写 _generated/，永不覆盖人工维护的叙事页 |
| C04 review_status 人机权限分离 | SKILL.md L262–L284；L372–L385（Phase C step 6） | REUSE | approved 只能人设，AI 永远 pending |
| C05 产物必须留 [NEEDS INPUT] 而非编造 | SKILL.md L158–L161；L370（Phase B on fail）；generated_output.py L65 | REUSE | 机械抽取遇到缺信息留标记，不补叙述 |
| C06 Auto-generated 头与出处强制 | SKILL.md L158–L161；generated_output.py L35–L48 | REUSE | 每个脚本产物必须带生成者与 provenance |
| C07 命令族与编号页集 | SKILL.md L69–L97；L194–L218 | ADAPT | 20 个 /PKB-* 命令映射到固定 00–12 编号页 |
| C08 Phase 0 三分路由 | SKILL.md L327–L337 | ADAPT | 全量发现 / 快路径 / 仅输出三类分流 |
| C09 PKB_ROOT 与项目分离 | SKILL.md L54–L64 | ADAPT | 知识库可落在项目外，显式声明根路径 |
| C10 契约式 Postconditions | SKILL.md L99–L118 | ADAPT | 写盘后必须满足的硬条件 |
| C11 回滚与降级路径 | SKILL.md L394–L396 | ADAPT | Phase C 不达标回 Phase B；tree 不可用降级 ls -R |
| C12 渐进式 AI 投喂 | SKILL.md L414–L418；templates/sphinx/ai-guide.md | ADAPT | 三轮渐进阅读：概览→深潜→模块验收 |
| C13 C4 强制顺序 | SKILL.md L120–L122；references/c4-standard.md | ADAPT | 架构文档必须 Context→Container→Component→Code |
| C14 版本页脚七字段 | SKILL.md L262–L284 | ADAPT | last_updated/commit/updated_by/review_status/... |
| C15 发布节奏绑定 | SKILL.md L164–L170 | ADAPT | 文档更新挂到 release/PR 检查单 |
| C16 测试用例维护触发 | SKILL.md L387–L392 | ADAPT | 四条触发条件维护活文档 |
| C17 过期检测机制 | scripts/check_pkb_staleness.py L206–L262 | REIMPLEMENT | mtime 启发式 |
| C18 索引生成 | scripts/gen_index.py L73–L112 | REIMPLEMENT | 仅生成候选，不写权威索引 |
| C19 人类主导的语义补充 | SKILL.md L138–L140；templates/adr/template.md L1–L5 | REIMPLEMENT | L3 由人提供 why，AI 只润色 |
| C20 保密切分与发布脱敏 | SKILL.md L286–L303；scripts/strip_confidential.py | REIMPLEMENT | L1–L5 五级，发布前强制 strip |
| C21 冲突处理 | SKILL.md 全文无定义 | REIMPLEMENT | 缺失 |
| C22 并发写入保护 | 无锁、无版本号、无 CAS | REIMPLEMENT | 缺失 |
| C23 结构化查询 | 全文只有文件系统遍历与文本搜索 | REIMPLEMENT | 缺失 |
| C24 不可复现外部观察标记 | 无字段定义 | REIMPLEMENT | 缺失 |
| C25 测试覆盖作为质量证据 | tests/（3 文件） | REIMPLEMENT | 3 文件 19 方法 |
| C26 知识库住在被分析仓库内 | SKILL.md L54–L64 | REJECT | PKB_ROOT 默认项目内 |
| C27 产出面向人类的整册项目文档 | SKILL.md L69–L97；L219–L260 | REJECT | 00–12 编号页 + Sphinx 双语站点 |
| C28 双语 Sphinx 站与 gettext 流程 | SKILL.md L123–L125；references/sphinx-bilingual.md | REJECT | Sphinx + myst + sphinx-intl |

统计：REUSE 6 / ADAPT 10 / REIMPLEMENT 9 / REJECT 3 = 28 项。

### 2.2 六个指定技术方向

任务指定要逐个交代六个方向。以下按方向给结论，不按能力编号。

**方向一：知识新鲜度判定。** 上游有实现，实现在 `scripts/check_pkb_staleness.py`。这是本审计最重要的一条发现：它判定过期用的是文件系统修改时间与文档最后一页写时间的差，即 `days_behind = max(0, (src_mtime - doc_mtime).days)`（L241），并据此分三档（`detect_level`，L149–L153，`<= 3` / `<= 14` / 其余）。这不是内容变化。源文件被改动但 mtime 未变（git checkout、rsync -t、解压覆盖、构建产物替换）会判为不陈旧；源文件被改回旧内容但 mtime 更新会误报陈旧。取整到天，同一天内的改动恒为 0。检测还有单向下界：`src_mtime <= doc_mtime` 直接跳过。判为 REIMPLEMENT，只借「零 token 先行」的取向，不借实现。

**方向二：索引与派生视图。** `scripts/gen_index.py` 对真实文档目录生成 `index.md` 形态的内容，但输出落到 `_generated/index.generated.md`，标题写死为 `Index Regeneration Candidate`，页内标 `maintained-by: human+ai`。它从不写 `index.md`。这是把矛盾改名而不是解决：SKILL.md 声称有编号页集契约，权威索引却依旧靠人手写，脚本产物不算数。另外每次都是全量重建，无增量路径。判为 REIMPLEMENT。

**方向三：脚本产物与人工内容的边界。** 这一条上游做得最好，也是唯一被代码强制的边界。`scripts/generated_output.py` 的 `generated_output_path()`（L19–L23）把输出目录钉死在 `<doc_dir>/_generated`，写侧不提供指向叙事页的分支；`render_markdown_artifact()`（L35–L68）强制写入 `<!-- Auto-generated by ... -->` 头与 provenance 段，并把 `needs_input` 渲染为 `[NEEDS INPUT: ...]` 而非编造内容。判为 REUSE。

**方向四：人工权限与批准流。** 页脚七字段中的 `review_status` 规定：只有人能设 `approved`，AI 永远设 `pending`（SKILL.md L262–L284，Phase C step 6 L372–L385）。这条把「谁有权批准」编码进了字段值域，是五源里最干净的权限边界表达。判为 REUSE。但同一页的「Context 必须人写」只有模板顶部两行 HTML 注释兜着（`templates/adr/template.md` L1–L5），没有代码出口，判为 REIMPLEMENT（C19、D3）。同一份文档里，一条有机制、一条没机制，对照很清楚。

**方向五：知识冲突与并发。** 两者都缺失。全文检索没有任何关于两条知识互相矛盾时如何处理的规则，没有裁决机制（C21）。所有脚本直接覆写，无锁、无版本号、无 CAS，多人或人机同时写会静默丢写（C22）。判为 REIMPLEMENT。

**方向六：结构化查询。** 缺失。全文只有文件系统遍历与文本搜索，没有索引数据结构，也没有查询接口，检索靠人或模型自己 glob（C23）。与 UPSTREAM-04 D10 是同一类缺口。

六个方向合起来的图景：这个上游在「怎么不花 token」和「生成物怎么不污染人工内容」上想得比 UPSTREAM-04 深，在「怎么判断知识真的过期」上想错了，在「冲突、并发、查询」上完全没想。

---

## 3. 测试审计

这一节必须把四件事分开：文件是否存在、覆盖了什么、哪些脚本没被测、测试是否真的跑过。

### 3.1 文件存在性

`tests/` 下 3 个文件，6 个测试类，19 个测试方法。

| 文件 | 字节 | 类 | 方法数 |
|---|---|---|---|
| __init__.py | 1 | — | — |
| test_bilingual_scaffold.py | 2801 | BilingualScaffoldTests | 2 |
| test_confidentiality.py | 12442 | 5 个 | 17 |

`test_confidentiality.py` 的 5 个测试类共 17 个方法：`TemplateConfidentialityFieldTests`（1 方法）、`StripConfidentialTests`（6 方法）、`ReviewStatusConfidentialityTests`（3 方法）、`SkillDocumentationTests`（1 方法）、`SphinxConfBadgeTests`（2 方法）、`PublishFlowWiringTests`（1 方法）。

### 3.2 覆盖了什么

19 个方法里 12 个集中在保密分级一条线：模板必须声明 `confidentiality`、strip 脚本的默认阈值与 `--min-level` 行为、dry-run 不删文件、review status 扫描的级别回落、Skill 文档提到分级、conf 渲染标签、Makefile 依赖顺序。其余分布在双语脚手架装配（2 个）与发布流程装配（1 个）等。

这个分布本身说明上游的重心：保密与发布投放被认真对待，新鲜度判定没有被认真对待。

### 3.3 哪些脚本没被测

18 个脚本里，只有 3 个被测试触及：`init_pkb.sh`、`strip_confidential.py`、`pkb_review_status.py`。

以下 5 个在 `tests/` 下的引用数经 grep 逐个确认为 0：

| 脚本 | tests/ 引用数 | 职责 |
|---|---|---|
| check_pkb_staleness.py | 0 | 过期检测（全篇哲学的技术支点） |
| gen_index.py | 0 | 索引生成 |
| validate_skill_consistency.py | 0 | Skill 一致性校验 |
| check_translation_sync.py | 0 | 翻译同步检查 |
| gen_repo_map.sh | 0 | 目录树生成 |

被漏掉的正好是最该有回归保护的那几个。特别是 `check_pkb_staleness.py`：整个 skill 的核心主张是「先跑零 token 规则，规则说没事才不花 token」，而这个支点脚本没有一行测试。它的缺陷（D1、D4、D9、D12）全部只能靠代码阅读发现，不可能被现有测试拦住。

### 3.4 测试是否真的跑过

没有。

本轮对 `tests/` 只做了静态阅读：读文件、数列、提取类与方法清单、grep 引用关系。没有执行 `pytest`，没有安装 Poetry 依赖，没有运行任何一个测试方法。

因此本审计不给出任何「19 个测试通过」或「测试全绿」的表述。测试状态记为 `NOT_RUN`。19 是方法数量，不是通过数。这两个数在报告里必须分开写，混在一起就是伪造测试结果。

同理，18 个脚本全部未执行。上文关于 `check_pkb_staleness.py` 行为的所有判断，都是从 `detect_staleness()` L206–L262 的比较逻辑和 `detect_level()` L149–L153 的阈值分支读出来的，不是跑出来的。

---

## 4. 缺陷清单

本节是缺陷 ID 的唯一权威源。JSON 的 `defects` 与本表逐条对应。

| ID | 严重度 | 文件 | 位置 | 问题 | 修复方向 |
|---|---|---|---|---|---|
| D1 | blocker | scripts/check_pkb_staleness.py | scripts/check_pkb_staleness.py L206–L262 | 过期判定用文件系统 mtime 之差，不是内容之差。detect_staleness() 核心比较是 src_mtime 与 doc_mtime，days_behind = max(0, (src_mtime - doc_mtime).days)。后果：源文件被改动但 mtime 未变（git checkout、rsync -t、解压、构建产物覆盖）则判定为不陈旧；源文件被改回旧内容但 mtime 更新则误报陈旧。mtime 是文件系统元数据，不是证据身份 | 以 (path, content_hash) 为判据：按 claim 的 evidence_refs 收集依赖路径，在新 commit 上只重算这些路径的哈希；哈希不等即 stale + content_changed，路径消失即 stale + source_removed。mtime 至多作为廉价预筛，绝不能作为终判 |
| D2 | blocker | scripts/gen_index.py | scripts/gen_index.py L73–L112 | 只产出候选索引，不写权威索引。build_index() 的输出经 render_markdown_artifact 落到 _generated/index.generated.md，标题定为 Index Regeneration Candidate，页内标 maintained-by: human+ai。权威的 index.md 全流程无人生成。SKILL.md L69–L97 声称有编号页集契约，但没有任何机制保证 index.md 与真实页集一致 —— 矛盾被改名而非解决 | 权威索引必须由生成器直接产出并可被校验：index.md 全量确定生成，内容仅由现有页集合决定，diff 为空即视为一致；如需人工介入，只允许订阅标题/描述覆盖层，不允许整页手写 |
| D3 | blocker | skills/project-knowledge-base/SKILL.md | skills/project-knowledge-base/SKILL.md L372–L385；templates/adr/template.md L1–L5 | 人类必须提供 why 的规则无强制手段。templates/adr/template.md 顶部只有两行 HTML 注释声明 Context/Problem/Constraints/Goals 应由人写或复核，Phase C 也只是散文要求。没有任何代码阻止 AI 自行填写 Context。规则可被跳过而无痕迹 | 把该规则落到单写者约束：Context 段带写者签名与写入方式，AI 上下文之外写入该段视为契约违约并在校验阶段失败；或将该段拆为独立文件由人直接提供 |
| D4 | high | scripts/check_pkb_staleness.py | scripts/check_pkb_staleness.py L115–L153, L206–L262 | 检测为单向下界，只看源新于文档，不看相反情形，也不看「源已改但文档从未记录该源」。同时阈值是硬编码启发式（detect_level: <=3 / <=14 / else），与内容是否真的变化无关。后果：一处只改注释的提交触发 critical，一处改了语义的提交因 mtime 相同完全不报 | 去掉时间阈值，改为「依赖路径的 content_hash 集合是否与 claim 记录一致」的布尔判定；陈旧与否不设天数档位 |
| D5 | high | scripts/gen_index.py | scripts/gen_index.py L73–L112 | 索引全量重建，无增量路径。build_index 每次遍历 existing_docs(doc_dir) 全目录并重新拼 SECTIONS 全部 toctree。页数增长时耗时线性上升，且每次产物的 diff 噪声与页数成正比。与 UPSTREAM-04 D9 是同一失效模式 | 索引改为由页脚元数据聚合：每页在页脚声明自己的归属段与顺序，索引只拼接这些声明并按需排序；新增或修改一页只影响该页一处 |
| D6 | high | skills/project-knowledge-base/scripts/check_pkb_staleness.py | skills/project-knowledge-base/scripts/check_pkb_staleness.py L1–L371（覆盖 scripts/ 下全部 18 个文件） | check_pkb_staleness.py、gen_index.py 等核心机制无任何测试。18 个脚本中仅 3 个被测试触及（init_pkb.sh、strip_confidential.py、pkb_review_status.py）。grep 确认 check_pkb_staleness / gen_index / validate_skill_consistency / check_translation_sync / gen_repo_map 在 tests/ 下引用数均为 0。整套「零token先行」哲学的支点脚本没有一行回归保护 | 机制类脚本必须先有失败用例才允许合入：至少覆盖 mtime 未变内容已变、路径消失、回退提交三种判据 |
| D7 | high | SKILL.md | SKILL.md L142–L157；scripts/（18 个文件） | 文档声称的能力与实际不符。Script-first automation toolkit 表列出 12 个脚本，磁盘上有 18 个；6 个存在但未声明（generated_output.py/sh、render_landing.py、translate_po.py、validate_skill_consistency.py、validate_template_links.py）。文档面与真实实现面双向漂移 | 脚本清单改为生成物：由 scripts/ 目录扫描生成并纳入校验，任何增删都必须在 SKILL.md 体现，不一致即 CI 失败 |
| D8 | medium | SKILL.md | SKILL.md L194–L218；L219–L260 | 命令表与目录结构两处描述需人工保持同步。L195 有一条注释 Keep in sync with references/commands.md，即承认同步靠人工。没有任何校验保证该表与 references/commands.md 一致 | 命令表由 references/commands.md 或代码常量单一权威源生成，禁止两处手写 |
| D9 | medium | scripts/check_pkb_staleness.py | scripts/check_pkb_staleness.py L37–L97 | 源到文档映射硬编码在 DEFAULT_SOURCE_DOC_MAP 中（如 Dockerfile* → 08-build/10-runbook）。新增构建文件或目录结构调整时，映射不会自动更新，检测会静默漏掉新源。同时该映射是全局的，无法表达「这个仓库的 Dockerfile 只影响 08」这类项目差异 | 映射应由文档侧声明：每个页面在页脚列出自己的依赖 glob，反向聚合得到判据；不再维护全局映射表 |
| D10 | medium | skills/project-knowledge-base/scripts/gen_index.py | skills/project-knowledge-base/scripts/gen_index.py L1–L20（所有 import generated_output 的脚本同此） | 脚本不独立。check_pkb_staleness.py、gen_index.py 均 import 同目录的 generated_output 模块（sys.path 注入），单独分发或复制会失败。对 skill 这类以目录整体分发的形态是可接受的，但意味着任何复制粘贴式复用都会断 | 如要复用，必须整目录引入或显式声明内部依赖；SourceLore 若采纳其产物契约，应把生成器契约实现为可独立导入的库 |
| D11 | medium | SKILL.md | SKILL.md L306–L326 | 陈旧告警的阈值是经验值而非判据：「10+ relevant commits」与「30 天」都是拍出来的数，文档未给依据，也未说明为何这两个数能代表知识失效。用户收到 warning 时无法判断该不该信 | 告警必须绑定可验证判据（哈希集合差异），而非经验计数 |
| D12 | medium | scripts/check_pkb_staleness.py | scripts/check_pkb_staleness.py L241 | days_behind 用整数天取整，同一天内的改动恒为 0。配合 detect_level 的 <=3 阈值，短周期内的真实陈旧完全不可见。仓库若以小时级节奏提交，该检测形同虚设 | 以内容哈希而非时间差为判据时该问题自动消失；若保留时间维度，必须保留秒级精度并说明其仅为辅助信号 |
| D13 | medium | SKILL.md | SKILL.md L158–L162；scripts/update_doc_level1.sh | L1 机械改动的边界未定义。「path rename, version bump」两类被举为例，但没有任何机制区分一次改动属于 L1 还是 L2/L3。Phase 0.5 要求 AI 自行分类，分类错误会让人工复核被跳过（L1 保留原 review_status） | L1 白名单必须显式：只有可机械判定的改动形态（纯路径替换、纯版本号替换）进入 L1，其余一律 L2 起步；白名单由脚本实现而非由模型判断 |
| D14 | medium | SKILL.md | SKILL.md L99–L118 | Postconditions 是散文条件，无一条可机械核验。「each doc follows a template or the numbered page contract」没有给出契约的可执行形式，Verification 阶段也只能靠模型自行比对。与 UPSTREAM-04 D14 同类 | Postcondition 必须落为可执行检查：模板必填节、页脚字段、路径有效性各自有脚本出口，任一失败即判定 Phase C 未完成 |
| D15 | low | SKILL.md | SKILL.md L262–L284 | 页脚 commit 存短 SHA（git rev-parse --short HEAD），长度不足以作为长期标识，仓库增长后存在前缀碰撞可能；且它指向的是「写入时的 HEAD」，不是「该页内容对应的源版本」，语义本身就偏 | 存完整 40 位 SHA，并同时存该页依赖路径的内容哈希，使「这页依据的是什么」可精确重建 |
| D16 | low | skills/project-knowledge-base/tests/test_confidentiality.py | skills/project-knowledge-base/tests/test_confidentiality.py L1–L40（tests/ 共 3 文件、19 方法） | 测试总量偏少。19 个用例中 12 个集中在保密分级，其余分散在双语脚手架与发布流程装配。templates/ 下 13 个编号页模板的必填节结构无测试 | 模板结构测试化：每个模板必须能被解析出必填节清单，与 SKILL.md 的页集契约比对 |
| D17 | low | SKILL.md | SKILL.md L444–L467 | Additional Resources 列出的参考文件与正文引用需保持同步，无校验机制。references/ 下 7 个文件的用途散布在正文各处，新增引用时容易漏登记 | 参考资料清单由 references/ 目录扫描生成 |
| D18 | low | scripts/gen_index.py | scripts/gen_index.py L114–L130 | gen_index.py 的 --stdout 与 --output-file 两条出口并存，默认写旁车。三种输出模式没有任何测试覆盖，参数组合的行为（如同时给两者）未定义 | CLI 参数互斥关系应在参数解析期显式拒绝，并补参数矩阵测试 |

统计：blocker 3 / high 4 / medium 7 / low 4 = 18 项。三个 blocker 是 D1, D2, D3。

三个 blocker 有共同的形状：规则写得很清楚，机制也能跑，但机制测的东西不是规则声称的东西。D1 声称测内容新鲜度，实测算 mtime；D2 声称维护索引，实测只产出候选；D3 声称人必须写 why，实测只有一行注释。其余 high 与 medium 大多是这一形状的下游后果。

---

## 5. 可复用能力与融合落点

### 5.1 最有价值的机制

如果只能从这一源拿走一件事，应当是 C03：旁车产物与叙事页的物理隔离。

理由不是它新奇，而是它在本审计覆盖的所有上游里，是唯一被代码而非文风强制的边界。UPSTREAM-04 用散文写了「索引是派生视图，禁止手改」（其 C03，判 REUSE），但整棵树里没有任何生成器，也就没有任何东西真的把派生层与权威层隔开。这一源有一行 `generated_output_path()`，把输出目录固定为 `_generated`，写过人的东西就再也写不回去。

这条对 SourceLore 的直接价值：INDEX 与所有派生视图必须有独立命名空间，生成器不提供指向权威层的写分支。代码里没有那个分支，比文档里写一百句「不要手改」都有用。

### 5.2 三条可采纳约束

| 采纳形态 | 依据能力 | 落在 SourceLore 的哪一层 |
|---|---|---|
| 派生层物理隔离，生成器写不到权威层，由代码保证 | C03 | 存储层 / 产物契约 |
| `approved` 迁移只接受人签发凭证，AI 上下文内直接拒绝 | C04 | Claim 状态机 |
| 缺信息落显式标记不补叙述，产物必带生成者与 provenance | C05、C06 | 产物契约 / 溯源 |

这三条都是约束，不是新实体。它们不引入任何与 01–04 并行的数据结构。

### 5.3 不能采纳的

C17（mtime 判新鲜度）、C18（只产候选索引）、C19（人写 why 无出口）、C21/C22/C23（冲突、并发、查询全缺）一律 REIMPLEMENT：概念可借，实现必须自建。

C26（知识库住在被分析仓库内）、C27（整册项目文档产物流水线）、C28（双语 Sphinx 站）REJECT。C26 与 UPSTREAM-04 C25 是同一方案，维持既有拒绝。

---

## 6. 与 UPSTREAM-01–04 的交叉关系

### 6.1 与 UPSTREAM-01

UPSTREAM-01 提供确定性仓储事实抽取（机读 schema）。本源也有确定性脚本层（`gen_repo_map.sh`、`gen_tech_stack.py`、`extract_api_signatures.py`），取向一致，但产物是给人读的文档，不是机读结构。抽取形态取 01，分层调度思路取 05，两者不合并成第二套数据模型。

### 6.2 与 UPSTREAM-03

UPSTREAM-03 的 Product Model / Claim / Evidence 是 SourceLore 的权威数据模型。本源没有对应概念：知识单位是整页文档，没有 claim 这个粒度，也没有证据字段。因此本源不提供 Claim 结构，只提供围绕「谁有权改、何时该重算」的流程约束。融合时它只能落在调度层与产物契约层，不得侵入 03 的实体定义。

### 6.3 与 UPSTREAM-04

这一对最有信息量。新鲜度方面，04 的 `verified-against` 是自由文本、无机制（其 D3）；05 有机制但机制错误（mtime，其 D1）。两者合起来说明同一件事：新鲜度必须由内容哈希集合判定，字段语义借 04，执行取向借 05，实现必须自建。

索引方面，04 的 D2/D9 与 05 的 D2/D5 是同一失效模式的两个变体：一方完全没有生成器，一方只生成候选且全量重建。SourceLore 的索引必须同时满足三件事：确定性、可校验、可增量。缺一条就会退化到其中一边。

人主导写入方面，04 的 D14（三处完成检查全散文）与 05 的 D3（模板注释兜底）是同一类。两个独立上游用两种笔法犯同一个错，这本身就是判据：散文式约束不可作为机制。

### 6.4 不建第二套模型

本轮未新增任何与 01–04 并行的数据模型。05 的全部可采纳内容归结为三类：调度分档（C02）、产物契约（C03/C06）、权限边界（C04）。三者都是对既有模型的约束，不是新实体。

---

## 7. 集成风险

### 7.1 MANIFEST_FORMAT_DIVERGENCE

已登记。五个上游的文件清单形态不一致：

| 上游 | 形态 |
|---|---|
| UPSTREAM-01 | 无 files.tsv |
| UPSTREAM-02 | git ls-tree 转储，列序 type/bytes/path，第 1 列为 tree 或 blob，含目录行，无哈希列 |
| UPSTREAM-03 | path/bytes/blob_sha 三列，无表头 |
| UPSTREAM-04 | path/bytes/blob_sha 三列，无表头 |
| UPSTREAM-05 | path/bytes/blob_sha 三列，无表头 |

五种形态三套语义。不存在通用列号规则：按列号硬解 UPSTREAM-02 会把 `blob` 当路径、把字节数当哈希。

处理：仅登记，不改写。任何解析器必须按上游 ID 分派，禁止写通式解析。本轮不动任何既有 Manifest，也不把不同 TSV 交给同一套固定列号规则处理。

Manifest V2 提案（本轮不迁移）：统一为 `path<TAB>bytes<TAB>blob_sha<TAB>kind`，无表头，目录不入表。迁移需逐上游重算，是独立一轮的活。

### 7.2 MTIME_FALSE_CONFIDENCE

已登记，high。若 SourceLore 把 `check_pkb_staleness.py` 当 freshness 基线，会把 mtime 误判引进本已计划用内容哈希的机制，直接退化 UPSTREAM-04 D3 的修复目标。明令禁止复用其实现，只可复刻取向。

### 7.3 CANDIDATE_INDEX_TRAP

已登记，medium。把权威索引降格为候选文件，会让索引与真实页集长期漂移，且漂移不可检测。索引必须可校验：生成物与磁盘内容 diff 为空即一致。

---

## 8. 遗留未决

- U1　C01 的零token前置与 UPSTREAM-04 C11 verified-against 字段的结合方式　状态：待融合设计阶段决定。字段语义与执行策略分属两层，本轮只确认二者互补不冲突
- U2　L1 白名单的具体边界　状态：未定。见 integration_decisions.open Q2
- U3　references/ 下 commands.md、failure-modes.md、sphinx-bilingual.md 未通读　状态：已登记未读。三者分别为 17123 / 8059 / 16236 字节，内容为命令细则与配置指南，不改变能力判定；如需二次审计应单列
- U4　templates/docs/ 下 13 个编号页模板结构未逐份审计　状态：已登记未读。D16 已记录其结构无测试覆盖
- U5　6 个未声明的脚本是否属于设计上不对外模块　状态：未定。D7 记录为文档面漂移，但源码未说明其是否内部模块

---

## 9. SHA 规范化

自本轮起，所有新记录使用 40 位完整 Git Commit SHA。

两个字段语义不同，不得相互替代：

- `upstream_pinned_sha`：被审计的上游提交。本源为 `284971cdd2666878d13716af8f26f51521cd915c`。
- `audit_git_commit`：产生本审计的 SourceLore 提交。回填阶段写入 TASKS/STATE，与上游事实无关。

UPSTREAM-03 遗留的短 SHA `d19f63277` 在本轮规范化，落地结果如下。

`progress/TASKS.json` 中 UPSTREAM-03 的 `git_commit` 字段原值 `d19f63277`，经本地 git 解析为完整 40 位：

| 核验项 | 命令 | 结果 |
| --- | --- | --- |
| 完整 SHA | `git rev-parse d19f63277` | `d19f63277fdf47675e5f28edad356dbaec0e78b2`（exit 0，长度 40） |
| 前缀唯一性 | `git rev-list --all \| grep -c '^d19f63277'` | `1` |
| 对象类型 | `git cat-file -t d19f63277fdf47675e5f28edad356dbaec0e78b2` | `commit` |
| 提交标题 | `git log -1 --format=%s` | `audit(upstream): 完成 UPSTREAM-03 repository-discovery 审计` |

只改 `git_commit` 这一处字段，另在同一条任务下新增 `sha_normalized_note` 记录规范化依据。审计事实、判定与 `audit_sha`（`557703fffe69c9ab97eff67acabea6b346afd89c`，UPSTREAM-03 的 `upstream_pinned_sha`）均未改动，未重写历史。

这里必须分清：`d19f63277fdf47675e5f28edad356dbaec0e78b2` 是 `audit_git_commit`，即产生 UPSTREAM-03 审计的 SourceLore 提交；`557703fffe69c9ab97eff67acabea6b346afd89c` 是 `upstream_pinned_sha`，即被审计的上游提交。两者语义不同，不可相互替代。

---

## 10. 验收

九项门禁逐条实跑，全部通过。下表退出码为本轮真实执行结果，不是声明。

| # | 门禁 | 检查内容 | 退出码 |
| --- | --- | --- | --- |
| 1 | 上游 SHA 与快照匹配 | `upstream.commit_sha` / `pinned_sha` / `snapshot.tree_json_sha` / `sha_convention.upstream_pinned_sha` 四处均为 `284971cdd2666878d13716af8f26f51521cd915c`，且等于 GitHub API `tree.json.sha` 与本地清单 | 0 |
| 2 | 全部证据路径与行号可解析 | 8 个 `evidence` 路径命中 8/8（file 7、dir 1）；18 条缺陷的文件路径与行号命中 18/18；文档内 48 处行号引用失败 0 | 0 |
| 3 | Markdown 与 JSON 一致 | 能力 28 项逐条比对（ID 与判定），6/10/9/3 两侧相同；缺陷 18 条 ID 与严重度逐条比对，3/4/7/4 两侧相同 | 0 |
| 4 | Apache-2.0 与 NOTICE 处理有据 | `LICENSE` 11357 字节 / 201 行，blob SHA `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`，与 GitHub API 的 size 与 sha 三方一致；全树 NOTICE 文件数 0 | 0 |
| 5 | 静态与动态不混淆 | `test_status.status = NOT_RUN`、`dynamic_tests_run = false`；全文对动态执行结果的肯定式断言共 0 处，所有结论均限于静态阅读 | 0 |
| 6 | 前四个上游结论不变 | UPSTREAM-01–04 四份记录与 HEAD 零差异；本轮 `TASKS.json` 改动只落在 UPSTREAM-03 的 `git_commit` 与 UPSTREAM-05 任务体 | 0 |
| 7 | 账本与真实 Git 状态一致 | `STATE.last_verified_commit`、`last_revision_commit` 对象均存在；全部 `git_commit` 为 40 位且可解析；DONE 7 / PENDING 1（仅 UPSTREAM-06） | 0 |
| 8 | 未执行上游代码、未装依赖 | 快照 66 个文件全部在 `tree.json` 登记，未登记 0、哈希不符 0；无缓存目录、无 `.pyc`。`poetry.lock` 属上游原物（sha `9a2f1855…`，size 111770） | 0 |
| 9 | 无敏感或未授权第三方内容 | 私钥 / 凭据字面量 / GitHub token / 云 AK / 家目录 / 内网地址命中 0；文档内无嵌入的上游源码块（代码块 0 处）；`upstreams/` 被 `.gitignore` 忽略且未出现在 `git status` | 0 |

门禁 5 与门禁 8 在前一版判据下各失败过一次，都是检查器误报，不是数据问题：门禁 5 把第 231 行的否定表述当成了肯定断言；门禁 8 用文件名黑名单把上游自带的 `poetry.lock` 当成了安装产物。两处判据改为「只匹配肯定式断言」与「以 `tree.json` 登记为准」，复跑退出码均为 0。判据本身也已修正，后续源不重复踩。

---

## 11. 本轮不做

- 不启动 UPSTREAM-06
- 不修改 SourceLore 正式分析引擎
- 不实现知识库
- 不改写任何既有 Manifest，不迁移到 Manifest V2
- 不执行上游脚本，不安装上游依赖
