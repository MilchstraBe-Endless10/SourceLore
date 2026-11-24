# 发行产物说明

SourceLore 每个 `vX.Y.Z` 版本的 GitHub Release 发布：

| 产物 | 用途 |
|---|---|
| Source code（自动归档） | 标签处的完整仓库；适用于 Git Clone 安装 |
| `sourcelore-skill-vX.Y.Z.zip` | 独立 Skill 安装——无需 Git Clone |
| `SHA256SUMS.txt` | ZIP 的 SHA-256；用 `sha256sum -c SHA256SUMS.txt` 校验 |
| `RELEASE_INFO.json` | 版本、Tag、产物名与校验和元数据 |

## ZIP 内容

```
sourcelore/
├── SKILL.md                       # Skill 入口 + frontmatter
├── references/                    # commands、safety、schema、content-qa
├── scripts/sourcelore.py          # launcher（自定位）
├── install.py                     # 自包含安装器（自举入口）
├── _sourcelore_src/src/           # 内置第一方程序源码
└── RELEASE_INFO.json              # 内嵌版本元数据 + 安装器 sha256
```

ZIP **自包含且可自举**：内含自己的 `install.py`，只下载 ZIP 的用户无须 Git Clone 即可安装——解压后在 `sourcelore/` 目录运行 `python3 install.py install`。`RELEASE_INFO.json` 记录了安装器的 SHA-256。安装后可删除 ZIP 与解压目录；技能仍可运行，因为程序源码已内置于安装目录。

ZIP **不含**：`kb.db` 或任何知识数据库、已捕获的第三方字节、`upstreams/` 快照、API Token、本地配置、安装 marker、`.venv/`，以及任何开发者本机路径。

## 版本对应

```
Git Tag vX.Y.Z
  → src/skill_interface/version.py RELEASE_VERSION = X.Y.Z
  → ZIP RELEASE_INFO.json version = X.Y.Z
  → 安装后 CLI --version = X.Y.Z
```

发布工作流（`/.github/workflows/release.yml`）在推送的 Tag 不等于 `v` + `RELEASE_VERSION` 时拒绝发布，且仅在全量测试通过后运行。

## 从发行版安装

```sh
# 下载 ZIP 与校验和，校验后，二选一：
# (a) 仅 ZIP 自举——运行解压出的 ZIP 内部安装器：
python3 /path/to/extracted/sourcelore/install.py install
# (b) 从工程检出：python3 tools/install.py install --zip sourcelore-skill-vX.Y.Z.zip
python3 tools/install.py doctor --expect-version X.Y.Z
```

完整命令见[安装指南](INSTALLATION.md) / [升级与卸载](UPGRADING.md)。
