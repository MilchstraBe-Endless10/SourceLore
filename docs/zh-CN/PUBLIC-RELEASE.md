# 公开发布核查 — 发行版 `v0.1.0-beta.1`

> 仓库随后已改为 Public。本文记录首个开源 beta `v0.1.0-beta.1` 的逐项核验结果与证据，作为历史证据保留。beta.1 的 Tag 与 Release 未改动。

## 修订：`v0.1.0-beta.2`

后续补丁版修复了 beta.1 之后发现的两个安装缺陷：独立 Release ZIP 现在内含自己的 `install.py`（仅下载 ZIP 的用户无须 Git Clone 即可自举安装），`doctor` 改用明确的状态契约——损坏/缺失的安装不再被误报为健康，而未建立知识库仍视为正常。见 [CHANGELOG.md](../../CHANGELOG.md)、[RELEASE-ARTIFACTS.md](RELEASE-ARTIFACTS.md) 与 [INSTALLATION.md](INSTALLATION.md)。`v0.1.0-beta.1` 的 Tag 和 GitHub Release **未移动**；beta.2 是全新的 Tag 与 Release。宿主集成（OpenBot / DSH / Hermes）仍未实测——CLI 成功不代表宿主验收通过。

## 1. 两项独立决定

- **第一方代码可见性/许可证**：SourceLore 自身代码以 [MIT 许可证](../../LICENSE) 发布（`Copyright (c) 2026 MilchstraBe-Endless10 (Cosmos)`）。把 GitHub 仓库改为 Public 是另一项由所有者决定的操作，本轮工程**未执行**。
- **第三方知识输出**：运行时 `distribution_allowed=false` 门禁（B-1/B-2/B-3）保持关闭。MIT 只覆盖第一方代码，不覆盖已采集的仓库字节、派生知识数据或用户数据库。

## 2. 隐私 / 密钥审计（已实际执行）

对工作树及全部可达 Git 对象做了完整扫描：

- 193 个可达提交；扫描 1,553 个文本 Blob（用完整 `git cat-file --batch` 流，未截断）。
- 扫描的密钥模式：GitHub token（`ghp_/gho_/github_pat_`）、AWS 密钥、私钥块、`api_key/secret/token/password` 赋值、Slack token。
- 结果：**未发现真实密钥**。唯一 `api_key_kv` 命中是测试夹具中的合成字符串（`tests/content/test_content_e2e.py`），不是凭据。
- 本机私有路径约 340 处，集中在历史文档（`progress/`、`docs/environment-audit.md`、`docs/implementation/*`），即开发者用户名与挂载路径。它们**不是密钥**，但仓库公开后会暴露本机目录结构。历史提交仍包含它们；仅在当前树删除不能从历史中移除。

**待所有者决定**：是否在公开前清理 Git 历史中的私有路径（需重写历史 + force push，属于明确门禁的不可逆操作），或按现状接受。本轮未做任何历史重写。

## 3. 第三方权利

见 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)：六个上游均为只读研究，零代码/提示词/规则/模板复制。UPSTREAM-06 无许可证，按最保守方式处理（零复制）。无第三方快照入库（`.gitignore` 排除 `upstreams/`）。

## 4. 已实际构建并验证的发行产物

- 单一版本源 `src/skill_interface/version.py`：`0.1.0-beta.1`（Tag `v0.1.0-beta.1`）。
- `python3 tools/build_release.py --out dist` 生成 `sourcelore-skill-v0.1.0-beta.1.zip`（自包含：Skill 文件 + 内置 `src/` + `RELEASE_INFO.json`），`SHA256SUMS.txt` 经 `sha256sum -c` 校验通过。
- ZIP 不含 `kb.db`、已捕获字节、Token、marker 或本地配置。
- 干净环境安装验证覆盖 Git 检出与独立 ZIP 两种模式；在无 `SOURCELORE_PROJECT_ROOT`、删除 ZIP 后 launcher 仍可用；在含空格、括号、中文的路径下可用。

## 5. 剩余的所有者门禁

- [ ] 批准把仓库改为 Public（不可逆的可见性变更）。
- [ ] 决定 Git 历史私有路径是否清理（重写历史 + force push）。
- [ ] 确认 LICENSE 中的版权持有人字符串。
- [ ] 公开后用匿名浏览器检查 README、LICENSE、文档、Tag、Release 与 ZIP 下载。

## 6. 本轮不声称完成

仓库公开、历史重写、创建 GitHub Release、打开 B-1/B-2/B-3 分发门禁。见[版本管理](VERSIONING.md)、[升级与卸载](UPGRADING.md)与[更新日志](../../CHANGELOG.md)。
