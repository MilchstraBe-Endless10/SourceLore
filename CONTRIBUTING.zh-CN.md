# 贡献 SourceLore

感谢帮助改进 SourceLore。本文涵盖开发环境、测试、源码与 Skill 同步、提交改动与许可边界。请先读[安全与授权](docs/zh-CN/SECURITY.md)：SourceLore 会采集公开 GitHub 内容，但从不执行它。

## 开发环境

```sh
git clone https://github.com/MilchstraBe-Endless10/SourceLore.git
cd SourceLore
python3 --version                 # Python 3；开发/测试于 3.14
export SOURCELORE_PROJECT_ROOT="$(pwd -P)"
python3 skill/sourcelore/scripts/sourcelore.py --version
```

核心 CLI 仅用 Python 标准库。JS/TS 解析需要项目本地 `.venv/` 中的可选 tree-sitter grammar：

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-treesitter.txt
```

绝不装入系统 Python。`GITHUB_TOKEN` 只放在环境变量中；绝不入库。

## 仓库结构

- `src/` — 按职责分组的扁平 Python 模块（storage、collector、facts、evidence_claims、lifecycle、views、renderer、skill_interface、content、source_analysis 等）。没有统一包，由 `paths.ensure_import_path()` 把目录接入 `sys.path`。
- `skill/sourcelore/` — Skill 源码（`SKILL.md`、`references/`、`scripts/`）。
- `tools/` — 安装器、发行打包与探针。
- `tests/` — 测试文件。
- `docs/{en,zh-CN}/` — 中英文文档。

## 运行测试

测试是独立脚本，含模块级 `sys.exit`；请逐文件直接执行（不要跨混合目录用单次 `unittest discover`）：

```sh
PYTHONPATH=src SOURCELORE_DATA_ROOT=<临时目录> python3 tests/<path>/test_<name>.py
```

发行前务必单独跑 P0 trust 测试与 installed-CLI 测试。记录真实通过/失败输出；不要仅凭退出码声称“测试通过”。

## 源码 / Skill 同步

常见有三份 Skill：工程源码 `skill/sourcelore/`、已安装 `~/.agents/skills/sourcelore/`、`~/.hermes/skills/sourcelore/`。改动 Skill 后要同步全部副本，并用 `md5sum` 校验。推荐用安装器（`tools/install.py install`）安装/更新，以保证 marker 与 launcher 一致。

## 提交改动

1. Fork 仓库，建主题分支。
2. 做聚焦的改动，增补或更新测试。
3. 跑相关测试与 `python3 tools/install.py doctor`。
4. 若行为或命令变化，同步更新中英文文档。
5. 提交 PR，说明改动、跑过的测试，以及对数据兼容性或 `distribution_allowed=false` 策略的影响。

不要提交 `kb.db`、已捕获字节、第三方快照、`.venv/`、本地配置、Token 或 marker 文件。不要重写 Git 历史或 force push。

## 版本与发行

版本遵循语义化版本，单一来源为 `src/skill_interface/version.py`。见[版本管理](docs/zh-CN/VERSIONING.md)、[升级与卸载](docs/zh-CN/UPGRADING.md)与[更新日志](CHANGELOG.md)。Release 由 `tools/build_release.py` 构建，仅在 CI 通过后发布。

## 许可边界

贡献即表示你同意该贡献采用项目 MIT 许可证（见 `LICENSE`）。该许可证只覆盖第一方代码——不覆盖已采集的第三方知识数据与用户数据库，后者仍受运行时 `distribution_allowed=false` 策略约束。见[第三方声明](THIRD_PARTY_NOTICES.md)。
