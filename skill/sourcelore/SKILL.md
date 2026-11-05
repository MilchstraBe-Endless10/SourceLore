---
name: sourcelore
description: >
  GitHub 知识库工具：采集公开仓库的固定 Commit、生成可回查的路径观察事实与证据裁决，
  并按需查询、生成知识卡片。用法是先调用 scripts/sourcelore.py 执行真实 CLI，
  再由 CLI 的结构化 JSON 来回答；不得由模型自行编造仓库分析结果。
  触发词：SourceLore、分析 GitHub 仓库、为仓库建知识库、查询仓库知识、查 Commit 知识、
  生成知识卡片、对比两个 Commit、读取已有研究报告。
  不适用：需要模型推理/总结的开放式提问、私有仓库、需要修改远程仓库的操作。
---

# SourceLore · GitHub 知识库 Skill

## 这是什么

SourceLore 是一个**本地知识库工具**，不是模型服务。它做的事只有一件：

> 采集一个公开 GitHub 仓库的**固定 Commit**，把"某个路径是否存在"这类可验证命题
> 登记为 Fact，用既有的 verification 规则给出 supported / refuted / insufficient_evidence
> 裁决，并保留全部证据引用与限制。

**它不做的事**：不推断项目功能是否实现、不判断文档是否完善、不做代码质量评价、
不替你做开放式总结。凡超出"路径观察"范围的问题，它只会回答"现有知识库证据不足"。

## 何时使用

| 用户说的话 | 应当执行的命令 |
|---|---|
| 用 SourceLore 分析 / 建库 | `analyze <url>` |
| 查已保存的固定 Commit（不问 GitHub） | `analyze <url> --commit <sha>` |
| 只用本地知识，禁止联网 | `analyze <url> --offline` |
| 强制重新获取远程版本 | `analyze <url> --refresh` |
| 有哪些已建的仓库 | `repositories` |
| 看看这个仓库的知识 | `inspect <repository_id>` |
| 这个 Commit 里 X 存在吗 | `query <repo_id> --commit <sha> --type path --path X` |
| 有哪些已登记命题 | `query <repo_id> --commit <sha> --type claims` |
| 对比两个 Commit | `query <repo_id> --commit A --compare-commit B --type version` |
| 生成知识卡片 | `card --repository-id <id> --claim-id <id>` |
| 历史版本 | `history <repository_id>` |

## 何时不要使用

- 用户问"这个项目好不好 / 功能齐不齐 / 文档完善吗" → **不要用**，直接说明知识库无此类证据。
- 用户要求分析私有仓库 → 拒绝（无凭据通道）。
- 用户要求创建 Issue / 提交代码 / 执行仓库脚本 → 拒绝。

## 入口

```bash
python3 <技能目录>/scripts/sourcelore.py <子命令> [参数]
```

技能目录由安装位置决定；脚本会自行定位 SourceLore 工程根
（也可用 `SOURCELORE_PROJECT_ROOT` 指定）。

**所有输出都是 JSON，走 stdout；错误走 stderr；退出码非 0 表示真实失败。**
不要只凭 Agent 自己的话判断成功与否，要读退出码和 stdout。

## 数据位置

- 默认知识库根：`~/.sourcelore/`
- 可用 `--data-root <path>` 或环境变量 `SOURCELORE_DATA_ROOT` 覆盖
- 数据库文件 `kb.db` **永不写入 Git 仓库**（脚本会拒绝）
- 卡片与报告输出到 `<数据根>/preview/`

## 已支持

- 公开 GitHub 仓库的只读采集（受 `--max-requests` 限额控制）
- 固定 Commit 与 Tree 完整性标记（截断即标 `PARTIAL`，不会标 `COMPLETE`）
- 路径存在命题的 Fact 生成与裁决
- 按仓库 / Commit / 路径 / Claim 查询
- 知识卡片 HTML（本地可打开）
- 历史版本列举

## 尚未支持

- 功能实现、测试覆盖、代码质量等任何非路径类结论
- 私有仓库与需要认证的采集
- 全量 Blob 内容分析（仅路径观察）
- 未登录态的稳定高频采集（无 `GITHUB_TOKEN` 时受 GitHub 60/h 限制）
- 对外发布（输出恒为内部预览）

## 错误处理

| 退出码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 执行失败（含 GitHub 错误） |
| 2 | 参数错误 |
| 3 | 知识库不可用（未建立） |

错误 JSON 形如 `{"ok": false, "error": "...", "message": "..."}`，位于 stdout；
同时 stderr 有一行可读摘要。看到 `ok:false` 就要如实告诉用户失败，不要粉饰。

## 安全边界

- 只接受 `https://github.com/<owner>/<repo>`；拒绝内网地址、非 github 主机、异常端口
- 只读：不推送、不建 Issue、不执行仓库脚本
- 知识卡片保留来源等级、审核状态、Commit 与限制；来源为 `TEST_ONLY` 时必须显式说明
- 卡片与报告标 `distribution_allowed: false` —— 内部预览，不是正式发布

## 离线优先与缓存（重要）

`analyze` 先做本地查找，再决定是否联网：

| 情况 | 行为 |
|---|---|
| `--commit <sha>` 且本地有完整快照 | **直接复用，0 次网络请求** |
| `--offline` 且本地有 | 复用，明确标"未访问 GitHub" |
| `--offline` 且本地无 | 报 `OFFLINE_CACHE_MISS`（退出码 3），不伪造 |
| `--refresh` | 允许联网重新采集 |
| 无 `--commit`（可变 Branch） | 返回 `branch_current_unknown: true` |

**本地快照只能证明"过去观测过的版本"，不能证明该 Branch 当前仍指向它。**
已保存的历史版本 ≠ 远程当前最新版本。

## GitHub Token（可选）

设置环境变量 `GITHUB_TOKEN` 可提高配额（未认证 60/h）。
只从进程环境读取；不写日志、不写资产、不进 Git。
`--no-token` 可对单次调用强制禁用。

## 限流

被限流时**2 秒内返回**，错误码 `RATE_LIMITED`，附带 `retry_after` 真实秒数与提示。
**不自动重试、不空等、不绕过。** 建议先用 `--offline` 查本地，或稍后 `--refresh`。

## 关键判读纪律（务必遵守）

1. **`completeness_status: PARTIAL`** → 未覆盖部分不得判为"不存在"。
2. **`insufficient_evidence`** → 只能说"证据不足"，**不得**说"该命题错误"。
3. **`refuted`** → 只对该 Commit 成立，不得外推到别的版本或"该项目不存在"。
4. **`coverage_state: INSUFFICIENT_EVIDENCE`** → 必须如实告知用户知识库回答不了。
5. 不要用 Agent 自己的推理去补足 CLI 返回的数据。
6. **`tree_summary` 才是完整性的权威说明**：
   `COMPLETE + 1 条` = 已完整枚举、真的只有 1 个条目，不是"采集不全"；
   `COMPLETE + 0 条` = 已完整枚举、该范围为空；
   `PARTIAL` = 只有部分条目，不能推断未出现的路径不存在。
7. `tree_summary.object_types` 区分 blob / directory / submodule / symlink，
   **不要把 submodule 或目录说成普通文件**。
8. **库里没有某路径的 Claim ≠ 该路径在 GitHub 不存在**，只能说覆盖不足。
