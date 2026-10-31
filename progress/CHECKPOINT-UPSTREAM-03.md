# UPSTREAM-03 检查点（2026-10-31 20:55 +08:00）

> 用途：上下文耗尽前落盘。恢复时先读本文件，再读 `progress/STATE.json`。
> 本文件不是审计产物，不进最终交付；审计完成后可删或保留为过程记录。

## 做到哪

§1 真实状态恢复、§2 上游固定与快照、§3 五个维度的证据采集，全部完成。**写作未开始。**

- 账本状态已核对：`progress/STATE.json` 的 `active_task` 仍是 `UPSTREAM-02`，
  `progress/TASKS.json` 的 `UPSTREAM-03` 仍是 `PENDING`，最近一次提交是
  `8858a928a864ca6fadf9a9e28614fbf5144d8c52`（只改了 `progress/TASKS.json`），工作树干净。
- 上游已钉：`maboasoft/repository-discovery`，Repository ID `1290761659`，
  固定 Commit `557703fffe69c9ab97eff67acabea6b346afd89c`（单一根提交，无父提交，
  tree `92023d6b3878ccec01f4941ea22574f585004454`，2026-07-06T08:15:40Z，
  author `Vladimir <kuzmenko.dn@gmail.com>`，subject
  `Add LICENSE and initial documentation for Repository Discovery methodology`）。
- 快照在 `upstreams/UPSTREAM-03-repository-discovery/`（`tree.json` + `files.tsv` + `tree/`），
  4 个 blob 全量完整性校验通过（`git hash-object` 与 API blob SHA 逐一对齐，4/4 `[OK]`）：

  | 文件 | 行数 | 字节 | git blob | sha256 前 12 |
  |---|---|---|---|---|
  | `LICENSE` | 16 | 707 | `f5b94100c84f` | `c169bd63777b` |
  | `README.md` | 243 | 7977 | `51d17b450a54` | `13987a1b2bc0` |
  | `SKILL.md` | 1452 | 56537 | `aa16932bab77` | `8ffcd4f5e886` |
  | `examples/knowledge-base-structure.md` | 109 | 2829 | `806982cd3f26` | `d5dfd491511c` |

- 四个文件全部逐行读完，`SKILL.md` 的 §1–§18 标题行号已逐一核对（见下）。
- 上游形态已确定：纯文档方法学 skill，**无脚本、无依赖清单、无测试**，
  `language: null`、`size 22` KB。`test_status` 必须记 `NOT_RUN`，不得编造 PASS。
- 许可证：`LICENSE` 正文确认为 **CC BY 4.0**（手写摘要式，非官方全文），
  但 GitHub API 报 `spdx_id NOASSERTION` / `name Other` / `url null`。
  两值都要入账：清单保留 API 值，审计记录写人审结论。
  **LICENSE 内无版权人署名行** → 归属须用仓库 URL + Repository ID + Commit SHA + author email。

## SKILL.md 章节行号（已核对，可直接引用）

§1 Mission L24 · §2 Evolution Model L45 · §3 Scope L58 · §4 Guiding Principles L104
（4.1 L106 / 4.2 L115 / 4.3 L123 / 4.4 L130 / 4.5 L137 / 4.6 L144 / 4.7 L155）·
§5 Product Model L164（5.1 L171 / 5.2 L184 / 5.3 L199 / 5.4 L209 / 5.5 L220 / 5.6 L230 /
5.7 L248 / 5.8 L256）· §6 Workflow L268（6.1 L275 / 6.2 L326 / 6.3 L334 / 6.4 L352 /
6.5 L385 / 6.6 L424 / 6.7 L443 / 6.8 L467 / 6.9 L485）· §7 Knowledge Reconstruction L505
（7.1 L512 / 7.2 L530 / 7.3 L560 / 7.4 L580 / 7.5 L603 / 7.6 L638 / 7.7 L656 / 7.8 L674 /
7.9 L692）· §8 Structure Rules L707 · §9 Heuristics L783（9.1 L790 / 9.2 L807 / 9.3 L824 /
9.4 L840 / 9.5 L856 / 9.6 L935）· §10 Document Standards L950（10.1 L955 / 10.2 L961 /
10.3 L987 / 10.4 L997 / 10.5 L1022 / 10.6 L1030）· §11 Diagram Standards L1044
（11.1 L1049 / 11.2 L1056 / 11.3 L1071 / 11.4 L1082 / 11.5 L1097 / 11.6 L1104）·
§12 Evidence Rules L1114（12.1 L1120 / 12.2 L1142 / 12.3 L1155 / 12.4 L1162 / 12.5 L1169）·
§13 Confidence L1189（13.1 L1193 / 13.2 L1203 / 13.3 L1215 / 13.4 L1229）·
§14 Unknown Rules L1241（14.1 L1245 / 14.2 L1262 / 14.3 L1276）·
§15 Consistency L1283（15.1 L1287 / 15.2 L1295 / 15.3 L1304 / 15.4 L1310 / 15.5 L1316）·
§16 Anti-patterns L1322 · §17 Self-review L1349（17.1 L1353 / 17.2 L1362 / 17.3 L1372 /
17.4 L1383 / 17.5 L1407 / 17.6 L1420 / 17.7 L1429）· §18 Appendix L1440

## 下一步（按顺序）

1. 写 `docs/upstream-audit-03-repository-discovery.md`，§1–§12，结构照抄
   `docs/upstream-audit-02-github-deep-research.md`（459 行）。§3 要分 A–E 五轴，
   §4 必须写清与 01/02 的去重，§6 能力矩阵四档计数须与 JSON 一致。
2. 写 `progress/UPSTREAM-03-audit.json`，顶层键沿用 02 的形状
   （`task/milestone/auditor/audited_at/upstream/execution_isolation/reviewed/
   capability_matrix/defects/dependencies/security_constraints/reuse_obligations/
   fusion_design/acceptance/test_status`），另加产品模型与知识实体两节。
3. 改 `progress/TASKS.json`（UPSTREAM-03 → DONE，补 `evidence_paths`/`audit_sha`/
   `completed_at`）、`progress/STATE.json`（`active_task`→UPSTREAM-03，刷新
   `last_verified_commit`/`updated_at`/`last_test_summary`）、`progress/HANDOFF.md`
   （追加 `## UPSTREAM-03 完成（…）`）、`docs/upstream-manifest.json`
   （UPSTREAM-03 补 `commit`/`subtree`/`license_evidence_paths`/`audit_record`/
   `audit_json`/`audited_at`/`audit_status:"DONE"`）。
4. 校验：JSON 可解析、文档与 JSON 的能力计数一致、文件引用存在、许可证记录齐全。
5. 一次 Git 提交，然后回填 `git_commit`（照 UPSTREAM-02 的两步提交惯例）。
6. 用 `bot_send_message` 发中文最终报告。

## 卡在哪

上下文耗尽，**需要手动压缩后才能继续**。无技术阻塞，无审批待办。

- 五个维度的结论已在压缩摘要里成稿（A 产品模型复原 / B 证据与置信度 / C 知识库结构 /
  D 工作流可执行性 / E 低 token 适配），恢复时直接按摘要里的条目展开成文，不必重读上游。
- 若要重读，只读窗口 ≤130 行；`read` 对大文件会静默丢中间段落，这一坑已反复踩到。
- 待定小事：UPSTREAM-02 的 C08 混合判定（照搬 REJECT / 思想 REIMPLEMENT）
  是否拆成两条账，此前留作开放问题，未影响 02 的计数口径。
