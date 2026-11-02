# F0 基线冻结

> 任务：M1-FUSION-GATE / F0 — 基线与异常项登记
> 生成：2026-11-02 22:25 +08:00 / DeepSeek-V4.1 Flash（DSH 执行 Agent）
> 事实来源：本地 Git、文件系统、已认证 `gh api` 实测输出。**不引用历史聊天记录作为任何检查通过的依据。**
> 机器可读证据：`docs/fusion/F0_VERIFICATION.json`

---

## 1. 仓库状态

| 项 | 值 |
|---|---|
| HEAD | `b0c8e6d2897fbf53171934e9c74a864266c412d4` |
| 短 SHA | `b0c8e6d` |
| 分支 | `main` |
| 工作区 | 干净 |

最近提交：

```
b0c8e6d chore(progress): 回填 UPSTREAM-06 审计提交 SHA 至账本
094a0d8 audit(upstream): 完成 UPSTREAM-06 repo-security-review 审计
fe36c7d chore(progress): 回填 UPSTREAM-05 审计提交 SHA 至账本
cee5951 audit(upstream): 完成 UPSTREAM-05 lazy-rabbit-skills project-knowledge-base 审计
af946e9 chore(progress): 回填 UPSTREAM-04 修订提交 SHA 至账本
565199f fix(audit): align upstream-04 defect references and blob verification
```

---

## 2. 六源核验表

许可证列取自 `docs/upstream-manifest.json` 的 `license_verified_spdx`；能力/缺陷数取自各 `progress/UPSTREAM-0X-audit.json` 动态统计，非口头汇总。

| 源 | 仓库 | Commit SHA | 真实根 Tree SHA | 许可证 | 能力 | 缺陷 | 测试 |
|---|---|---|---|---|---|---|---|
| UPSTREAM-01 | `jeannie-jy/repo-analyzer-skill` | `b8c000f60c03003cbb08e6737b2e8193289904ea` | `625f45c6809a08ebdb18b69ae5f86daa5c36f1a1` | MIT | 15 | 6 | — |
| UPSTREAM-02 | `bytedance/deer-flow` | `44e372dd7f8a511e6223f548f55f7b4c939ca226` | `e87770212f1c057000c96c66dec11a341b74e957` | MIT | 18 | 12 | NOT_RUN — 上游子树不存在任何测试文件（files.tsv 全量枚举确认），其代码亦未执行；不得据此断言任何功能可用或通过 |
| UPSTREAM-03 | `maboasoft/repository-discovery` | `557703fffe69c9ab97eff67acabea6b346afd89c` | `92023d6b3878ccec01f4941ea22574f585004454` | CC-BY-4.0 | 27 | 18 | — |
| UPSTREAM-04 | `SNIKO/agent-skills` | `a3e5e9da94434127cdd47a1a7e0658baafff7083` | `b38a48ebdd022f496e629ec2eb48e75d51bdf08a` | MIT | 27 | 18 | — |
| UPSTREAM-05 | `walterfan/lazy-rabbit-skills` | `284971cdd2666878d13716af8f26f51521cd915c` | `3fee9bc635b6940ce2c7a189be494060c72cdca4` | Apache-2.0 | 28 | 18 | NOT_RUN |
| UPSTREAM-06 | `Consensys/repo-security-review` | `d5128b03d6a785bfb7c8be4139291f887c2a3215` | `68af655f92d2d15f40335017c0e0819f59524413` | **无** | 28 | 20 | NOT_RUN |

合计：能力 **143** 项（15+18+27+27+28+28，上游候选数，未去重），缺陷 **92** 项（6+12+18+18+18+20）。六源审计状态全部 `DONE`。

> 注意：能力数是**上游候选总数**，不是 SourceLore 最终独有能力数。去重与归属属 F1。

### 2.1 快照完整性

| 源 | 快照目录 | files.tsv 行 | tree/ 文件数 | tree.json |
|---|---|---|---|---|
| UPSTREAM-01 | `UPSTREAM-01-repo-analyzer-skill` | **无** | 104 | **无** |
| UPSTREAM-02 | `UPSTREAM-02-deer-flow` | 6 | 4 | **无** |
| UPSTREAM-03 | `UPSTREAM-03-repository-discovery` | 4 | 4 | 有 |
| UPSTREAM-04 | `UPSTREAM-04-agent-skills` | 6 | 6 | 有 |
| UPSTREAM-05 | `UPSTREAM-05-lazy-rabbit-skills` | 66 | 66 | 有 |
| UPSTREAM-06 | `UPSTREAM-06-repo-security-review` | 16 | 16 | 有 |

UPSTREAM-01 的快照来源是归档包 `src.tar.gz`，UPSTREAM-02 只有 `files.tsv` + `tree/`，两源均无 `tree.json`。见 F0-D05。

---

## 3. Git 对象核验（本轮强制项）

这是 F0 的核心核验。结论先行：

> **`commit_sha`、`root_tree_sha`、`tree_query_ref` 是三个不同的字段，不可互换。**
> GitHub Trees API 在 ref 是 commit-ish 时，响应里的 `sha` 字段**回显请求标识**，而不是该 commit 的根 tree SHA。

### 3.1 UPSTREAM-06 实测输出

```
$ gh api repos/Consensys/repo-security-review/commits/d5128b03... --jq '{sha:.sha, commit_tree_sha:.commit.tree.sha}'
{"sha":"d5128b03d6a785bfb7c8be4139291f887c2a3215","commit_tree_sha":"68af655f92d2d15f40335017c0e0819f59524413"}

$ gh api repos/Consensys/repo-security-review/git/trees/d5128b03... --jq '{query_ref:"commit", sha:.sha, entries:(.tree|length), truncated}'
{"query_ref":"commit","sha":"d5128b03d6a785bfb7c8be4139291f887c2a3215","entries":5,"truncated":false}

$ gh api repos/Consensys/repo-security-review/git/trees/68af655f... --jq '{query_ref:"tree", sha:.sha, entries:(.tree|length), truncated}'
{"query_ref":"tree","sha":"68af655f92d2d15f40335017c0e0819f59524413","entries":5,"truncated":false}
```

三条输出互相对照即可看出：按 commit 查 tree，返回的仍是 commit SHA；按 tree 查，才返回 tree SHA。两次的 `entries` 与 `truncated` 相同，说明指向的是同一棵树的同一份内容。

### 3.2 全六源对照

| 源 | commit SHA | 真实根 tree SHA | 本地 tree.json.sha | 该字段实为 |
|---|---|---|---|---|
| UPSTREAM-01 | `b8c000f60c03003cbb08e6737b2e8193289904ea` | `625f45c6809a08ebdb18b69ae5f86daa5c36f1a1` | `（无 tree.json）` | — |
| UPSTREAM-02 | `44e372dd7f8a511e6223f548f55f7b4c939ca226` | `e87770212f1c057000c96c66dec11a341b74e957` | `（无 tree.json）` | — |
| UPSTREAM-03 | `557703fffe69c9ab97eff67acabea6b346afd89c` | `92023d6b3878ccec01f4941ea22574f585004454` | `557703fffe69c9ab97eff67acabea6b346afd89c` | **commit SHA 回显** |
| UPSTREAM-04 | `a3e5e9da94434127cdd47a1a7e0658baafff7083` | `b38a48ebdd022f496e629ec2eb48e75d51bdf08a` | `a3e5e9da94434127cdd47a1a7e0658baafff7083` | **commit SHA 回显** |
| UPSTREAM-05 | `284971cdd2666878d13716af8f26f51521cd915c` | `3fee9bc635b6940ce2c7a189be494060c72cdca4` | `284971cdd2666878d13716af8f26f51521cd915c` | **commit SHA 回显** |
| UPSTREAM-06 | `d5128b03d6a785bfb7c8be4139291f887c2a3215` | `68af655f92d2d15f40335017c0e0819f59524413` | `d5128b03d6a785bfb7c8be4139291f887c2a3215` | **commit SHA 回显** |

四源（03/04/05/06）的 `tree.json.sha` 都等于自己的 commit SHA，都不等于真实根 tree SHA。这不是巧合，是同一个抓取方式的系统性结果。

### 3.3 内容是否受影响

**不受影响。** 对 03/04/05/06 四源，把本地 `tree.json` 的 `tree[]` 与远端真实 tree 的 `recursive=1` 输出逐条比对：

| 源 | 本地条目 | 远端条目 | 同路径同 SHA | 不符 |
|---|---|---|---|---|
| UPSTREAM-03 | 5 | 5 | 5 | 0 |
| UPSTREAM-04 | 55 | 55 | 55 | 0 |
| UPSTREAM-05 | 477 | 477 | 477 | 0 |
| UPSTREAM-06 | 18 | 18 | 18 | 0 |

所以这是**字段语义错误，不是数据污染**。16 个 blob（06）以及其他各源的 blob 哈希匹配结论全部成立，历史审计的完整性验证不需要推翻。

处置：写入 `ERRATA.md` 的 E-01；F2 的 `snapshot_manifest_v2` 必须把三个字段分开定义并各自存值。

---

## 4. 异常项登记

六项，每项带来源与处置。完整机读版本在 `F0_VERIFICATION.json` 的 `differences`。

| ID | 严重度 | 类别 | 摘要 | 处置 |
|---|---|---|---|---|
| F0-D01 | high | Git 对象语义 | UPSTREAM-03/04/05/06 的 tree.json.sha 存的是 commit SHA（请求回显），不是根 tree SHA | 写入 ERRATA |
| F0-D02 | high | 证据标注 | THIRD_PARTY_NOTICES.md 声称「本仓库不包含任何第三方源代码、提示词、规则文本或模板」，与 docs/ 审计文档中存在上游短句引用的事实不符 | 本轮不修改历史审计文档 |
| F0-D03 | medium | Manifest 结构 | manifest 六行字段不齐：UPSTREAM-01/02 缺 license_verified_spdx / disposition_counts / defect_counts / test_status 等字段，03/04/05/06 有 | F1/F2 统一 schema 时补齐为显式 null，不改写历史数值 |
| F0-D04 | medium | Manifest 格式 | MANIFEST_FORMAT_DIVERGENCE 仍存在：UPSTREAM-02 的 files.tsv 第 1 列是 type（tree/blob），其余四源是 path | F2 要求「通过具名适配器解析，绝不按第三列统一读取」 |
| F0-D05 | medium | 覆盖缺口 | UPSTREAM-01 无 tree.json，UPSTREAM-02 无 tree.json，两源快照形态与其他四源不一致 | 登记为已知形态差异 |
| F0-D06 | medium | 语义冲突 | UPSTREAM-06 C06 上游语义「无法建立完整链 → FALSE_POSITIVE（判否）」与 SourceLore 设计「证据不足 → insufficient」冲突 | F2 采用 insufficient |

### F0-D01 · UPSTREAM-03/04/05/06 的 tree.json.sha 存的是 commit SHA（请求回显），不是根 tree SHA

- 严重度：`high`　类别：`git_object_semantics`
- 证据：见 git_object_verification；六源中 4 源本地 tree.json.sha == commit_sha，均 != 真实 root_tree_sha
- 影响：任何把 tree.json.sha 当作「树身份」或「快照指纹」的下游逻辑会得到错误结论；但不影响条目内容正确性
- 处置：写入 ERRATA；F2 的 snapshot_manifest_v2 必须分离 commit_sha / root_tree_sha / tree_query_ref 三字段

### F0-D02 · THIRD_PARTY_NOTICES.md 声称「本仓库不包含任何第三方源代码、提示词、规则文本或模板」，与 docs/ 审计文档中存在上游短句引用的事实不符

- 严重度：`high`　类别：`evidence_mislabel`
- 证据：docs/upstream-audit-03/04 等文档含引号内的上游原文短句（如 "（03 文档中关于 Product Model 必须先于最终文档生成的那句英文原文引用）"）；04 有 21 处 >=6 词英文长句、03 有 14 处
- 影响：声明过度绝对，会让人误以为连引文都没有；实际是「产品代码零复制，审计文档含引文式短句引用」，性质不同
- 处置：本轮不修改历史审计文档；在 ERRATA 登记，并在 F5 重写 THIRD_PARTY_NOTICES 措辞为分层表述

### F0-D03 · manifest 六行字段不齐：UPSTREAM-01/02 缺 license_verified_spdx / disposition_counts / defect_counts / test_status 等字段，03/04/05/06 有

- 严重度：`medium`　类别：`manifest_schema`
- 证据：UPSTREAM-01 行键数 18，UPSTREAM-05 行键数 30；01/02 的 license_verified_spdx 为缺键而非 null
- 影响：按统一 schema 解析 manifest 会因缺键 KeyError；「无许可证」与「字段未填」在 06 上是靠显式 null 区分，在 01/02 上不可区分
- 处置：F1/F2 统一 schema 时补齐为显式 null，不改写历史数值

### F0-D04 · MANIFEST_FORMAT_DIVERGENCE 仍存在：UPSTREAM-02 的 files.tsv 第 1 列是 type（tree/blob），其余四源是 path

- 严重度：`medium`　类别：`manifest_format`
- 证据：实测 5 个 files.tsv：02 首行首列为 tree，03/04/05/06 首行首列为实际路径（LICENSE/.gitignore 等）；全部 3 列
- 影响：按第三列统一读 blob_sha 会在 02 上读到 path；必须具名适配器分派
- 处置：F2 要求「通过具名适配器解析，绝不按第三列统一读取」；本轮只登记

### F0-D05 · UPSTREAM-01 无 tree.json，UPSTREAM-02 无 tree.json，两源快照形态与其他四源不一致

- 严重度：`medium`　类别：`coverage_gap`
- 证据：upstreams/UPSTREAM-01-repo-analyzer-skill/ 只有 src.tar.gz 与 tree/；UPSTREAM-02-deer-flow/ 只有 files.tsv 与 tree/
- 影响：无法对 01/02 做「tree.json.sha vs root_tree_sha」核验；01 的获取路径是 tar.gz 而非 Trees API
- 处置：登记为已知形态差异；F2 的 manifest v2 需声明每源的抓取方式（trees_api / archive_tarball）

### F0-D06 · UPSTREAM-06 C06 上游语义「无法建立完整链 → FALSE_POSITIVE（判否）」与 SourceLore 设计「证据不足 → insufficient」冲突

- 严重度：`medium`　类别：`semantics_conflict`
- 证据：progress/UPSTREAM-06-audit.json capability_matrix C06 mechanism 字段
- 影响：若照搬上游，未证明存在会被写成不存在，违反「不得把未证明存在变成不存在」
- 处置：F2 采用 insufficient；C06 的可用部分只是「必须能逐跳定位」，判否语义由 SourceLore 自行定义

---

## 5. 已知问题清单（来自旧审计，本轮只登记不修改）

| ID | 问题 | 状态 | 归属 |
|---|---|---|---|
| MANIFEST_FORMAT_DIVERGENCE | UPSTREAM-02 的 files.tsv 是 type/bytes/path，其余是 path/bytes/blob_sha | 未消解 | F2 用具名适配器 |
| 不完整分页 | 历史审计中部分读取是有界窗口，已登记为各自 unresolved 的 U 项 | 已登记 | F3 完整分页 |
| 伪完整报告 | 「跳过阶段后仍可能声称完成」是上游缺陷（UPSTREAM-06 D9），非本源问题 | 已记录 | F3 失败矩阵 |
| 证据只查文件存在 | 既有 evidence 字段只校验 path，未校验行范围与内容哈希 | 未解决 | F2 evidence schema |
| 非校准置信度 | 上游的模型置信度无校准数据（UPSTREAM-06 D13/D20） | 拒绝采纳 | F2 禁止伪造百分比 |
| 知识状态混叠 | 任务执行 / 快照质量 / claim 验证三轴必须正交 | 已明确 | F2 三轴分离 |
| 禁止复制无许可源码 | UPSTREAM-06 无许可证，零文本移植 | 生效中 | F5 许可对齐 |

---

## 6. 第三方声明核对

`THIRD_PARTY_NOTICES.md` 现状：

- 记录六源许可状态，UPSTREAM-06 标为**无**并写明零复制。**这一点核对属实。**
- 声明「本仓库不包含任何第三方源代码、提示词、规则文本或模板」。**这一点措辞过度绝对**——`docs/` 下的审计文档确实含有上游原文的引文式短句（03 有 14 处、04 有 21 处 ≥6 词英文长句）。

两者性质不同：产品代码与提示词零复制属实；审计文档内的引文式短句引用不构成「复制实现」，但也不该被「不包含任何…文本」这句话覆盖。已登记为 **F0-D02**，措辞修改留给 F5，不在本轮改历史文档。

结论：**当前不存在「已采用未授权源代码」的情况。** 六源的 `capability_matrix` 全部是设计层判定，无一行搬运上游实现。

---

## 7. F0 Gate 判定

| # | 门禁条件 | 结果 | 证据 |
|---|---|---|---|
| 1 | 六源历史不变 | PASS | 工作区干净；HEAD `b0c8e6d`；六份 audit JSON 与六份 Markdown 未改动 |
| 2 | 每个差异带来源和处置 | PASS | 6 项差异，每项含 evidence / impact / disposition |
| 3 | 至少一次 Git 对象核验有真实输出 | PASS | §3.1 三条 `gh api` 实测输出，commit 与 tree 可区分 |
| 4 | 第三方声明不含「已采用未授权代码」的错误主张 | PASS | 零复制属实；措辞问题已登记 F0-D02 |
| 5 | 未复制上游文本 | PASS | 本轮只写新文档，未从上游摘取任何文本 |
| 6 | 未修改历史审计结论 | PASS | 六份审计 Markdown/JSON 零改动 |

**F0 Gate：PASS。**

---

## 8. 下一任务的前置条件

F1 具备启动条件，但有三条约束必须先写进 F1 的执行前提：

1. 能力总数是 **143 项上游候选**，不是 143 项 SourceLore 能力。去重后必然显著减少，F1 的 Gate 要求「总数与六份本地 JSON 动态一致」指的是**原始候选全覆盖**，不是去重后仍为 143。
2. `CAPABILITY_CROSSWALK.json` 的每条记录都要带 `license_permission` 独立字段。UPSTREAM-06 的 28 项全部只能是「仅参考设计」，不得出现任何形式的文本移植。
3. 06 的 C06 判否语义（F0-D06）在 F1 里不能直接沿用，`disposition` 应记为 `ADAPT` 而非 `ADOPT_DESIGN`。

