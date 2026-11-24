# 版本管理

SourceLore 遵循 [语义化版本 2.0.0](https://semver.org/spec/v2.0.0.html)。

唯一权威版本常量是 `src/skill_interface/version.py` 中的 `RELEASE_VERSION`。
所有对外版本展示面都必须读取该模块：CLI `--version`、`status`、安装器元数据、
更新/卸载、发行打包、CHANGELOG、Git Tag 与 GitHub Release 标题。任何文件都不得
硬编码另一份版本字符串。

## 格式

`MAJOR.MINOR.PATCH[-预发布]`

- **MAJOR** — CLI/Skill 接口或数据模型的不兼容变更。
- **MINOR** — 向后兼容的新功能。
- **PATCH** — 向后兼容的修复。
- **预发布**（`-beta.N`、`-rc.N`）— 尚未稳定，预发布之间可能变化。首个公开版本为
  `0.1.0-beta.1`。

Git Tag 为版本号加 `v` 前缀（如 `v0.1.0-beta.1`），在 `version.py` 中同样以
`RELEASE_TAG` 暴露。

## 内部代号与对外版本

历史内部研发代号 `f2p5a` 仅作为 `DEV_CODENAME` 留在文档中，它不是版本号，
不得当作版本展示。`SKILL_VERSION` 作为兼容别名保留，值等于 `RELEASE_VERSION`。

## 版本 ↔ 产物对应

每次发行必须满足：

```
Git Tag (vX.Y.Z) → Git Commit → Release ZIP（内含 RELEASE_INFO.json 的 VERSION）
                 → 安装后 CLI --version
```

`tools/build_release.py` 把 `RELEASE_VERSION` 写入 ZIP 内的 `RELEASE_INFO.json`；
安装器把已安装版本写入 marker；`sourcelore.py --version` 读取同一份 `version.py`。
任一处不一致即为发行错误。

## 数据库兼容性

知识库**数据根**（含 `kb.db`）是用户数据，位于源码安装目录之外。升级 SourceLore
绝不隐式迁移或清空它。`version.py` 中的 `SCHEMA_VERSION` 记录当前 Schema 版本；
未来 Schema 变更必须提供备份、兼容性检查、可复现迁移与失败停止条件。见
[UPGRADING.md](UPGRADING.md) 与 DATA-MODEL.md 的 A/B/C/D 完整性规则。

## 不在本版本管理中

- 已采集的第三方仓库快照与派生知识数据 —— 仍受运行时 `distribution_allowed=false`
  策略约束。
- 用户自己的知识数据库与生成文档。
- 每机器的本地路径与 Agent 宿主 marker（永不入库）。
