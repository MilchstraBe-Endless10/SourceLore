# F2-P5A 执行报告

**基线** `8c6c087`（不是 056de10：前者为 R1 诊断产物提交）

## 结论

SourceLore 已从内部 Python 工程变成 **DeepSeek Harness 能发现的 Skill**。
`~/.agents/skills/sourcelore` 安装完成，本会话 available_skills 中已出现 `sourcelore`，
并通过 skill 工具成功加载正文。

首次真实 GitHub 采集成功建库；复跑时被 GitHub 未认证限流（60/h）阻断。

## 交付

```
skill/sourcelore/
  SKILL.md
  scripts/sourcelore.py          # 自包含启动器（三级工程根回退）
  references/{commands,knowledge-schema,safety}.md
src/skill_interface/
  paths.py result.py knowledge.py query.py render.py analyze.py status.py cli.py
tests/skill_interface/  41 项
tools/f2p5a_{install,e2e}.py
```

## CLI

```
sourcelore.py status
sourcelore.py repositories
sourcelore.py inspect <rid>
sourcelore.py history <rid>
sourcelore.py analyze <url> [--ref R] [--path P] [--max-requests N]
sourcelore.py query <rid> --commit S --type path|claims|version
sourcelore.py card --repository-id R [--claim-id C | --verification-id V]
```

## 接入的既有模块

`GitHubClient` / `build_snapshot` / `ingest_snapshot` /
`extract_file_path_observation` / `ingest_fact` / `build_path_claim` /
`verify_path_claim` / `ingest_claim` / `ingest_verification` /
`assemble_from_verification` / `build_card` / `render_card_html` / `run_research`。

没有第二套 Collector、Storage、Research 或 Renderer（有测试锁定）。

## 真实数据

首次采集 `octocat/Hello-World`：

```
repository_id 1296269
commit_sha    7fd1a60b01f91b314f59955a4e4d4e80d8edf11d
root_tree_sha b4eecafa9be2f2006ce1b709d6857b07069b4608
tree_entries  1        completeness COMPLETE
fact          SL-FACT-23fb9eaf7edad041595ead0a3af938350c90bfab
claim         SL-CLAIM-b2d90832050096e96bd83b284ae02bae1d817cf0
verification  SL-VERIF-3543119f023fccee7e96f646ec382a8e831bb305  → supported
```

查询 `README` → `ANSWERABLE_FROM_EXISTING_EVIDENCE`，verdict `supported`。
查询 `src/main.rs` → `INSUFFICIENT_EVIDENCE`，`answerable=false`，findings 0。

## 本轮抓到的三个缺陷

**D-1** `index_rows.commit_sha` 列存在但全为 NULL（快照也一样）。
只查列 → `commits: []`，看起来"没有版本"。已改为回读 payload。

**D-2** 限流时 CLI 挂起约 8 分钟。
`RATE_LIMITED` 在 `RETRYABLE` 集合；`retry_after` 1550–17000 秒被截到 120 秒上限，
重试 4 次。已让 analyze 用 `max_retries=0`，**限流 2 秒内返回**并带 hint。

**D-3** 测试断言用裸子串 `"requests"`，误把注释里的中文判成 import。已改正则。

## 验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface41
= 640 项，失败 0，退出码全 0
Crosswalk 42841207… 未变
```

## 分配门禁

| 门禁 | 状态 |
|---|---|
| SKILL_PACKAGE | DONE |
| SKILL_DISCOVERY | DONE |
| SKILL_CLI | DONE |
| GITHUB_KNOWLEDGE_WORKFLOW | PARTIAL（首次成功，复跑限流） |
| KNOWLEDGE_QUERY | DONE |
| KNOWLEDGE_CARD | DONE |
| HARNESS_SKILL_E2E | PARTIAL（发现+加载+子进程调用有证；话术自动触发未验） |

## 明确不做 / 不宣称

- 未开发任何模型供应商、网关、账号池、路由、Key 管理
- 未改 Harness 全局模型配置、凭据、其他 Skill
- 未改 F1-D 冻结 Crosswalk
- Skill 被发现 ≠ 用户话术能自动触发
- 首次采集成功 ≠ 限流下可用
- 卡片能开 ≠ 可对外分发（B-1/B-2/B-3 仍 OPEN）
