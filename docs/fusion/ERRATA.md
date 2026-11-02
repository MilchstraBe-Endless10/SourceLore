# F0 勘误记录

> 性质：**对既有审计材料的勘误登记，不是对审计结论的改写。**
> 规则：先写这里，不改原史料。只有在明确需要、且单独开最小修订提交时才纠正原始记录。
> 生成：2026-11-02 / F0 实测证据见 `docs/fusion/BASELINE.md` §3 与 `docs/fusion/F0_VERIFICATION.json`

---

## 记录格式

每条含：编号、类型、受影响对象、原表述、实测事实、影响判定、处置、是否改史料。

---

## E-01 · 字段语义错误

| 项 | 内容 |
|---|---|
| 受影响对象 | UPSTREAM-03 / 04 / 05 / 06 的 `upstreams/<ID>/tree.json` 字段 `sha` |
| 原表述 | 各源审计把 `tree.json.sha` 当作快照的树标识记录（`snapshot.tree_json_sha`），并在 UPSTREAM-06 的 SHA 一致性门禁中与 `commit_sha`、`pinned_sha` 并列比对为「一致」。 |
| 实测事实 | 实测：GitHub Trees API 在 ref 为 commit-ish 时，响应 `sha` 字段回显请求标识。四源的 `tree.json.sha` 全部等于各自的 commit SHA，全部不等于真实根 tree SHA。UPSTREAM-06：commit `d5128b03d6a785bfb7c8be4139291f887c2a3215` 的真实根 tree 是 `68af655f92d2d15f40335017c0e0819f59524413`。另两源无 tree.json：01 用 `src.tar.gz` 归档包，02 只有 `files.tsv`。 |
| 影响判定 | **不影响数据正确性。** 对 03/04/05/06 逐条比对 `tree[]` 与远端 `recursive=1` 输出：5/55/477/18 条全部同路径同 SHA，不符 0 条。受影响的是「把这三个字段当同义词」的下游逻辑。原门禁比对 `tree_json_sha == commit_sha` 之所以通过，恰恰因为该字段本来就是 commit SHA——它验证的是「抓取时用的是这个 commit」，不是「树的身份是这个 SHA」。 |
| 处置 | ① 不改历史 JSON，不动 `snapshot.tree_json_sha` 的现值。② 后续所有材料必须把 `commit_sha`、`root_tree_sha`、`tree_query_ref` 视为三个独立字段。③ F2 的 `snapshot_manifest_v2` 强制三字段分列，`root_tree_sha` 必须来自 `GET /commits/{ref}` 的 `commit.tree.sha`，不得从 trees 端点响应里取 `sha`。④ 06 的 `snapshot.tree_json_sha` 语义在本文档中记为「tree_query_ref」，不是根 tree。 |
| 是否改动历史史料 | 否 |

## E-02 · 声明过度绝对

| 项 | 内容 |
|---|---|
| 受影响对象 | `THIRD_PARTY_NOTICES.md` 总述段 |
| 原表述 | 「截至 UPSTREAM-06 完成时，**本仓库不包含任何第三方源代码、提示词、规则文本或模板**。」 |
| 实测事实 | `docs/` 下六份审计文档中存在上游原文的引文式短句。按 ≥6 连续英文单词统计：03 有 14 处、04 有 21 处、02 有 5 处、01 与 06 各 2 处、05 有 1 处。这些引文是英文原句的逐字引用（本轮不在此重复，避免二次搬运；位置见各文档的引用段落）。 |
| 影响判定 | **核心主张属实，措辞越界。** 产品代码、提示词、规则正文、模板确实零复制；但「不包含任何…文本」这句话在字面上覆盖了引文，与实际不符。引文式短句引用用于评论与对照，与「复制实现」性质不同，但性质不同不等于可以宣称不存在。 |
| 处置 | ① 本轮不改 `THIRD_PARTY_NOTICES.md`，避免与历史审计结论产生时间线混乱。② F5 重写为分层表述：产品代码与提示词零复制（属实）／ `docs/` 审计材料含引文式短句引用（据实登记）／ `upstreams/` 快照为本地只读材料、被 `.gitignore` 排除、不进入分发物。③ 不因此判定任何历史审计违规：六份 `capability_matrix` 全部是设计层判定，无实现搬运。 |
| 是否改动历史史料 | 否（留待 F5） |

## E-03 · Manifest 结构不齐

| 项 | 内容 |
|---|---|
| 受影响对象 | `docs/upstream-manifest.json` 的六行 |
| 原表述 | 各行按同一 schema 解读：`license_verified_spdx`、`disposition_counts`、`defect_counts`、`test_status` 等字段被当作通用字段。 |
| 实测事实 | 实测键数：UPSTREAM-01 为 18 键、UPSTREAM-05 为 30 键。01/02 缺 `license_verified_spdx`（**缺键，不是 null**）、缺 `disposition_counts`、缺 `defect_counts`、缺 `test_status`、缺 `snapshot_path`、缺 `total_bytes`。 |
| 影响判定 | 按统一 schema 解析会 KeyError。更实质的问题是语义：UPSTREAM-06 用显式 `license_verified_spdx: null` 表达「无许可证」，而 01/02 的缺键无法区分「无许可证」与「尚未填写」——尽管 01/02 的 MIT 实际记录在各自 audit JSON 的 `license.spdx_id` 里。 |
| 处置 | ① 不改历史数值。② F1/F2 统一 schema 时把 01/02 的缺失字段补为显式值（从各自 audit JSON 取实际许可），不再保留缺键。③ 补写属新增事实对齐，需单独提交。 |
| 是否改动历史史料 | 否 |

## E-04 · Manifest 格式分叉（结转）

| 项 | 内容 |
|---|---|
| 受影响对象 | `upstreams/UPSTREAM-02-deer-flow/files.tsv` |
| 原表述 | 既有记录已识别 `MANIFEST_FORMAT_DIVERGENCE`：02 是 `type<TAB>bytes<TAB>path`，其余是 `path<TAB>bytes<TAB>blob_sha`。 |
| 实测事实 | 实测五个 files.tsv 全部 3 列。02 首行首列是 `tree`；03/04/05/06 首行首列是实际路径（`LICENSE` / `.gitignore` 等）。 |
| 影响判定 | 按第三列统一读 blob SHA 会在 02 上读到路径字符串。这是**列序陷阱**，不是列数差异——列数都是 3，所以「列数一致」不能作为格式一致的判据。 |
| 处置 | ① 本轮只登记，不改写历史 TSV。② F2 强制通过具名适配器解析，按 `upstream_id` 分派列序，禁止写通式解析器。③ Manifest V2 统一为 `path<TAB>bytes<TAB>blob_sha<TAB>kind` 时需逐源重算，不在本轮做。 |
| 是否改动历史史料 | 否 |

## E-05 · 覆盖缺口

| 项 | 内容 |
|---|---|
| 受影响对象 | UPSTREAM-01 与 UPSTREAM-02 的快照形态 |
| 原表述 | 六源被当作形态一致的快照集合，`tree.json` 被当作通用存在物。 |
| 实测事实 | UPSTREAM-01 目录只有 `src.tar.gz` 与 `tree/`，无 `files.tsv`、无 `tree.json`；UPSTREAM-02 目录只有 `files.tsv` 与 `tree/`，无 `tree.json`。其余四源三者齐全。 |
| 影响判定 | 无法对 01/02 做「tree.json.sha vs root_tree_sha」核验。01 的获取路径是归档包而非 Trees API，其文件清单来源与其余五源不同。 |
| 处置 | ① 登记为已知形态差异。② F2 的 manifest v2 必须声明每源的 `fetch_method`（`trees_api` / `archive_tarball`）与 `has_tree_json`。③ F1 提取能力时不依赖 tree.json 的存在性。 |
| 是否改动历史史料 | 否 |

## E-06 · 语义冲突

| 项 | 内容 |
|---|---|
| 受影响对象 | UPSTREAM-06 `capability_matrix` 的 C06（判否语义） |
| 原表述 | C06 判定为 `REUSE`，表述为「不可验证即判否」——无法建立逐边界 entrypoint→sink 链则结论为 `FALSE_POSITIVE`。 |
| 实测事实 | 上游该机制把「证据不足」与「已证伪」合并为同一个否定状态。这与 SourceLore 的四态设计要求（`insufficient` 独立于 `rejected`）直接冲突。 |
| 影响判定 | 若原样采纳，会把「未证明存在」写成「不存在」，违反 F2 的「缺少证据时为 insufficient/unknown，不做无证事实」。C06 中真正可迁移的只有「必须能逐跳定位到 file:line」这一条结构纪律。 |
| 处置 | ① 不改 06 审计 JSON 的 C06 记录与 REUSE 判定——那是上游事实的正确描述。② 在 F1 中该能力的 `disposition` 记为 `ADAPT` 而非 `ADOPT_DESIGN`，并写明只采纳定位纪律、拒绝其判否语义。③ F2 的 `claim_verification_state` 明确 `insufficient` 与 `refuted` 是两个终态，前者不得降级为后者。 |
| 是否改动历史史料 | 否 |

---

## 汇总

| ID | 类型 | 严重度 | 是否改历史 | 何时处理 |
|---|---|---|---|---|
| E-01 | 字段语义错误 | high | 否 | F2（schema 三字段） |
| E-02 | 声明过度绝对 | high | 否 | F5（措辞重写） |
| E-03 | Manifest 结构不齐 | medium | 否 | F1/F2（补显式值） |
| E-04 | Manifest 格式分叉（结转） | medium | 否 | F2（具名适配器） |
| E-05 | 覆盖缺口 | medium | 否 | F2（fetch_method） |
| E-06 | 语义冲突 | medium | 否 | F1（记为 ADAPT） |

六条勘误**全部不改动历史史料**。其中 E-01 与 E-02 是硬性事实纠正，必须在对应子任务完成前生效；其余四条是结构性登记，随各自子任务落实。

---

## 本文件不做什么

- 不重写任何一份 UPSTREAM-XX 审计 Markdown 或 JSON。
- 不修改 `docs/upstream-manifest.json` 的任何历史数值。
- 不修改 `THIRD_PARTY_NOTICES.md`（措辞问题留待 F5）。
- 不重新研究六个上游。

