# 第三方声明

本文件记录 SourceLore 在其开发过程中参考过的第三方上游，以及从每一个上游实际带入了什么。

## 总述

截至 UPSTREAM-06 完成时，**本仓库不包含任何第三方源代码、提示词、规则文本或模板**。

M1 阶段的六个上游审计全部是只读研究：上游仓库被固定在某个具体 commit、下载为本地快照、静态阅读，然后按「抽象设计思想 / 具体实现」分离的方式处理。抽象设计思想不受著作权保护；具体表达受保护。凡是上游没有给出复制许可的，本仓库只取前者，实现全部独立编写。

`upstreams/` 目录下确实保存了上游的完整快照副本，但这些目录被 `.gitignore` 排除，**不进入本仓库的历史**。它们只是审计期间的一次性只读材料，不是分发物。

## 逐源状态

| 上游 | 固定 Commit | 许可证 | 许可证依据 | 带入本仓库的内容 |
|---|---|---|---|---|
| UPSTREAM-01 jeannie-jy/repo-analyzer-skill | b8c000f60c03003cbb08e6737b2e8193289904ea | MIT | 仓库内 LICENSE | 仅抽象设计思想，无代码复制 |
| UPSTREAM-02 bytedance/deer-flow（skills/public/github-deep-research） | 44e372dd7f8a511e6223f548f55f7b4c939ca226 | MIT（双版权行） | 仓库内 LICENSE | 仅抽象设计思想，无代码复制 |
| UPSTREAM-03 maboasoft/repository-discovery | 557703fffe69c9ab97eff67acabea6b346afd89c | CC BY 4.0 | API 报 NOASSERTION，实测为 CC BY 4.0 全文 | 仅抽象设计思想，无文本复制 |
| UPSTREAM-04 SNIKO/agent-skills（skills/swe-research） | a3e5e9da94434127cdd47a1a7e0658baafff7083 | MIT（含版权行） | 仓库内 LICENSE | 仅抽象设计思想，无文本复制 |
| UPSTREAM-05 walterfan/lazy-rabbit-skills（skills/project-knowledge-base） | 284971cdd2666878d13716af8f26f51521cd915c | Apache-2.0 | 仓库内 LICENSE（201 行 / 11357 字节，与 API 三方一致），无 NOTICE | 仅抽象设计思想，无代码复制 |
| UPSTREAM-06 Consensys/repo-security-review | d5128b03d6a785bfb7c8be4139291f887c2a3215 | **无** | API `license` 为 null；`/license` 端点 404；16 个文件全文检索 LICENSE / Copyright / SPDX / © 命中 0；无 LICENSE / COPYING / NOTICE 文件 | **零复制。** 仅可取抽象设计思想，且不得复制源码、提示词、规则原文与模板 |

## 关于 UPSTREAM-06

这是六个上游中唯一没有许可证的一个。在默认著作权下，该仓库保留全部权利，不存在复制或改编的授权。

因此对该上游的处置比其他五个更严：

- 不复述其规则文本，不复制其模板，不逐句改写。
- 本审计文档只描述其机制形状（有哪些门、门的触发条件、状态如何流转），并据此独立设计 SourceLore 自己的契约。
- 该上游的 `scripts/setup.sh` 从未执行，其安装路径与命令行也未被采纳。
- 许可证状态在 `docs/upstream-manifest.json` 与 `progress/UPSTREAM-06-audit.json` 中作为独立字段记录（`license_verified_spdx: null`、`license.status: "none"`），不被任何复用判定覆盖。

「抽象设计思想」与「受版权保护的具体表达」之间的边界宽度，需要法务判断，已登记为 `progress/UPSTREAM-06-audit.json` 的未决项 U10。本仓库采取的是保守立场。

## 依赖

本仓库自身不依赖上述任何上游的代码，也不依赖它们安装的扫描器（gitleaks、osv-scanner、semgrep、pip-audit、grype）。这些工具在本项目的审计过程中一个都没有被安装或运行。

## 变更

新增第三方来源或改变任一来源的处置方式时，必须同步更新本文件与 `docs/upstream-manifest.json`，并在对应审计文档中留下证据路径。

## 与 SourceLore 开源许可证的关系

SourceLore 第一方代码采用根目录 `LICENSE`（MIT）。该许可证仅覆盖 SourceLore 自己编写的代码与文档，**不覆盖**：

- 上述六个上游仓库的任何源码、提示词、规则或受保护内容（本仓库零复制，只有不受著作权保护的抽象设计思想）；
- SourceLore 运行时采集的第三方 GitHub 仓库内容字节与派生知识数据 —— 这些受运行时 `distribution_allowed=false` 门禁约束，不随 MIT 开源自动获得分发授权；
- 用户的知识数据库、配置与生成文档。

因此「仓库以 MIT 开源」不等于「第三方知识数据可自由再分发」。发布代码与分发数据是两个独立决定。
