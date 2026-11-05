# F2-P5A SourceLore Skill 契约

**基线** `8c6c087` · Crosswalk sha256 `42841207…`（已复算）

## 唯一维护源

`SourceLore/skill/sourcelore/` → 安装到 `~/.agents/skills/sourcelore/`（受控复制 + marker）。
仓库是唯一源；安装目录带 `.sourcelore-skill.json` 记录工程根与源树哈希。

## 入口

```
python3 ~/.agents/skills/sourcelore/scripts/sourcelore.py <子命令>
```

src/ 下扁平模块由 `paths.ensure_import_path()` 注入 sys.path；不依赖 cwd。

## 命令集

| 命令 | 作用 |
|---|---|
| `status` | 版本/数据根/DB/仓库数/上次操作 |
| `repositories` | 已登记仓库列表 |
| `inspect <rid>` | 单仓库知识摘要 |
| `history <rid>` | 已登记 Commit 版本 |
| `analyze <url>` | 采集→快照→Fact→Claim/Verification |
| `query <rid> --commit --type` | 复用已存知识检索 |
| `card --repository-id` | 卡片 HTML |

## 输出契约

- stdout 恒为 JSON（成功与失败都是）
- stderr 一行人类可读摘要
- 退出码：0 成功 / 1 执行失败 / 2 参数错 / 3 知识库不可用

## 复用边界（不建第二套）

`skill_interface` 只做薄 CLI，全部落到既有模块：
`GitHubClient` / `build_snapshot` / `ingest_snapshot` /
`extract_file_path_observation` / `verify_path_claim` /
`assemble_from_verification` / `build_card` / `render_card_html` / `run_research`。

**禁止**在 skill 里出现第二套 GitHub 实现或第二套 Renderer（有测试锁定）。

## 安全

- URL 仅 `https://github.com/<owner>/<repo>`；拒绝其它主机/端口/userinfo
- `kb.db` 拒绝写入 Git 仓库
- 卡片 `distribution_allowed=false`
- 不读凭据、不改裁决、不写人工审核

## 已知缺陷与修复（本轮实测）

### D-1 `index_rows.commit_sha` 全为 NULL

`index_rows` 有该列但写入时为空，快照 payload 里才有 commit。
只查列会得到空 commits。**修复**：`repositories` 回读 payload。

### D-2 限流导致 CLI 挂起约 8 分钟

`_classify_http` 把 403+remaining=0 判为 `RATE_LIMITED`，该码在 `RETRYABLE` 集合。
`retry_after` 约 1550–17000 秒，被 `max_retry_after` 截到 120 秒 × 4 次尝试。

**修复（不改 Collector）**：analyze 实例化时 `max_retries=0, max_retry_after=0`。
限流时 2 秒内返回 `RATE_LIMITED` + `hint`，不绕过、不空等。

★ 这是本轮抓到的真实缺陷 —— 不修就会让 Skill 在限流时看起来"卡死"。
