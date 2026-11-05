# SourceLore CLI 命令参考

统一入口：`python3 scripts/sourcelore.py <子命令>`

全局选项：`--data-root <path>`、`--version`

## status
输出运行状态：skill 版本、数据根、DB 是否存在、仓库数、最近一次操作。
不输出任何凭据。

## repositories
列出已登记仓库：`repository_id`、`commits`、`snapshot_count`、`fact_count`、
`claim_count`、`knowledge_state`。

## inspect <repository_id>
单仓库摘要：Commit 列表、Tree 覆盖（含 `completeness_status`）、Facts、Claims、限制。

## history <repository_id>
已登记历史版本。**只列已登记 Commit，不推断祖先或先后关系。**

## analyze <url> [--ref REF] [--path PATH] [--max-requests N]
采集公开仓库 → 快照 → Fact → Claim/Verification。
URL 必须是 `https://github.com/<owner>/<repo>`（可带 `/tree/<ref>`）。
`--path` 默认 `README`。
Tree 被截断时返回 `completeness_status: PARTIAL` 并带限制。

## query <repository_id> --commit <sha> [--type path|claims|version]
`--type path` 需 `--path`；`--type version` 需 `--compare-commit`。
结果复用已存知识，**不重新访问 GitHub**。

字段：`coverage_state`、`coverage_meaning`、`answerable`、`findings[]`、
`untrusted_findings[]`、`gaps[]`、`limitations[]`、`distribution_restrictions`。

## card --repository-id <id> [--claim-id <id> | --verification-id <id>]
生成卡片 HTML 与 JSON 到 `<数据根>/preview/`。返回 `html_path`。

退出码：0 成功 / 1 失败 / 2 参数错 / 3 知识库不可用。
