# 升级、更新与卸载

SourceLore 把**安装**（程序 + Skill 文件）与**知识库数据根**（你的 `kb.db`、已捕获字节和文档）分开。更新和卸载只动安装，默认保留你的数据。

## 查看当前状态

```sh
python3 tools/install.py doctor
python3 tools/install.py doctor --json
```

`doctor` 报告检测到的安装模式、已安装版本、launcher 是否有效、数据根以及数据根是否存在。它不做任何修改。

## 查看已安装版本

```sh
python3 <skill-dir>/scripts/sourcelore.py --version
```

该值必须等于所安装发行版中 `src/skill_interface/version.py` 的 `RELEASE_VERSION`。

## 更新

从 Git 检出：

```sh
git pull
python3 tools/install.py update
```

从下载的 Release ZIP（无需 Git 检出）：

```sh
python3 tools/install.py update --zip /path/to/sourcelore-skill-vX.Y.Z.zip
```

`update` 先在临时目录准备完整的新版本，切换**之前**校验完整性（必需文件齐全、`RELEASE_INFO.json` 一致），把旧安装保留为带时间戳的备份，且从不触碰数据根。任何失败都会回滚到上一个安装。

固定某个版本：直接安装该版本的 ZIP；SourceLore 不自动更新，也不联网回传任何信息。

## 回滚

更新失败时自动回滚。手动回滚可恢复 `update` 在安装目录旁留下的时间戳备份，或重装上一个 ZIP：

```sh
python3 tools/install.py update --zip /path/to/sourcelore-skill-vPREVIOUS.zip
```

## 数据兼容性

- 升级 ≠ 数据库迁移。更新不修改数据根。
- 若未来版本需要 Schema 变更，必须提供备份、兼容性检查与可复现迁移及失败停止条件；见 VERSIONING.md 与 DATA-MODEL.md。
- A/B/C/D 完整性规则与运行时 `distribution_allowed=false` 门禁在更新后保持。

## 卸载

```sh
python3 tools/install.py uninstall
```

默认卸载只删除 SourceLore 的安装程序和 Skill 文件。**保留**你的知识数据库、配置、生成的项目文档以及你自己修改过的文件。删除用户数据需要单独明确确认；安装器绝不静默删除。

## 保留本地修改

安装器拒绝覆盖不属于它的 Skill 目录（无 `.sourcelore-install.json` marker）。若你改过已安装文件，`doctor` 会把安装标记为“本地已修改”；`update` 会保留备份而非静默丢弃。替换前请先比较。
