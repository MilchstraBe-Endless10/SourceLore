# SourceLore — 快速入门

简体中文 · [English](../en/QUICKSTART.md) · [完整安装指南](INSTALLATION.md) · [公开发布核查](PUBLIC-RELEASE.md)

这是一套与当前 Skill launcher、CLI 源码契约对齐的**实际可操作安装流程**。SourceLore 源代码仓库**不附带预先建立的知识数据库**；装好 Skill 仅代表工具可用，不代表作者本机的三个样例仓库已自动出现在你的知识库中。

## 一、获取源码、验证工程内入口

```sh
git clone https://github.com/MilchstraBe-Endless10/SourceLore.git
cd SourceLore
export SOURCELORE_PROJECT_ROOT="$(pwd -P)"
python3 skill/sourcelore/scripts/sourcelore.py --help
```

> 只有仓库正式改为 Public 后，所有人才能直接使用上述 `git clone`。仓库仍为 Private 时，需要有权访问的 GitHub 账户。目前项目尚未选定第一方开源许可证。

CLI 子命令包括：`status`、`repositories`、`help`、`analyze`、`inspect`、`history`、`query`、`derive`、`answer`、`card`。

## 二、正确安装 Skill 到 OpenBot 等兼容助手

安装后的 launcher 位于工程目录之外，因此必须能定位回真正的 SourceLore 工程。查找优先级为：`SOURCELORE_PROJECT_ROOT` 环境变量 → 安装目录的 `.sourcelore-skill.json` 标记 → 在父目录查找源码。

在刚刚克隆的 SourceLore 目录执行：

```sh
export SOURCELORE_PROJECT_ROOT="$(pwd -P)"
mkdir -p "$HOME/.agents/skills"

if [ -e "$HOME/.agents/skills/sourcelore" ]; then
  echo "Skill 已存在，请检查并同步现有副本，避免出现嵌套安装。"
else
  cp -a "$SOURCELORE_PROJECT_ROOT/skill/sourcelore" "$HOME/.agents/skills/sourcelore"
fi

python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ['SOURCELORE_PROJECT_ROOT']).resolve()
assert (root / 'src/skill_interface/cli.py').is_file(), '工程根无效'
skill = Path.home() / '.agents/skills/sourcelore'
assert (skill / 'SKILL.md').is_file(), '没有找到安装态 Skill'
marker = skill / '.sourcelore-skill.json'
marker.write_text(json.dumps({'project_root': str(root)}, ensure_ascii=False), encoding='utf-8')
print('已登记工程根：', marker)
PY

python3 "$HOME/.agents/skills/sourcelore/scripts/sourcelore.py" --help
```

以上操作**不覆盖现有 Skill 目录**。如果你以前安装过 SourceLore，应先对照版本，再有意识地同步 `SKILL.md`、`references/`、`scripts/`。标记文件包含本机私有绝对路径，**不得上传 GitHub**。

在 OpenBot 中给助手设置可以访问工程的工作区。如果未立即发现 Skill，新建一个聊天后重试；不同模型不能保证一定自动调用，验收以真实工具轨迹为准。

## 三、选择数据根，创建可直接使用的终端命令

数据根查找顺序为：`--data-root` 全局参数 → `SOURCELORE_DATA_ROOT` → `~/.config/sourcelore/config.json` 中的 `data_root` → `~/.sourcelore/`。

新环境可以把数据明确放到工程目录之外：

```sh
export SOURCELORE_DATA_ROOT="$HOME/SourceLore_Data"
sourcelore() {
  python3 "$HOME/.agents/skills/sourcelore/scripts/sourcelore.py" "$@"
}
sourcelore status
sourcelore repositories
```

注意：`sourcelore()` 是**本次终端会话的 shell 函数**，项目默认不会往系统里安装一个全局 `sourcelore` 可执行文件。已有知识库的用户应沿用真实的数据根，不要误创建空库后判断知识丢失。

## 四、先生成采集计划，再入库固定 Commit

```sh
# 先只读确认计划，不采集项目内容。
sourcelore analyze https://github.com/OWNER/REPO --plan

# 在已有访问和来源授权允许的情况下采集，固定真实的 40 位 Commit。
sourcelore analyze https://github.com/OWNER/REPO --commit COMMIT_SHA --request-limit 8

# 本地缓存中已有该 Commit 后才能要求纯离线复用。
sourcelore analyze https://github.com/OWNER/REPO --commit COMMIT_SHA --offline
```

把 `OWNER/REPO` 与 `COMMIT_SHA` 换成真实值。首次采集受 GitHub 请求预算与五维来源授权门禁约束。全新未缓存仓库加 `--offline` 会得到 `OFFLINE_CACHE_MISS`，不能在禁止联网时凭空建立知识。

**文件树覆盖**与**源码正文覆盖**是两种概念，`ROOT_ONLY` 不能称为完成全仓库分析。

## 五、以自然语言查询项目内容

```sh
sourcelore repositories
sourcelore answer REPOSITORY_ID "这个项目是做什么的？"
sourcelore answer REPOSITORY_ID "如何安装使用？"
sourcelore answer REPOSITORY_ID "解释主要源码实现"
sourcelore query REPOSITORY_ID --commit COMMIT_SHA --type claims
```

`answer` 负责对本地已登记内容进行确定性检索与组装，不会自行运行 LLM。若 README 或源码尚未获准采集，不得凭文件名猜测功能。CLI 裁决不等于人工复核；本地登记的 Commit 也不代表上游当前最新版本。

## 六、常见问题与安全

| 现象 | 需要检查 |
|---|---|
| 找不到工程根 | 安装态标记或 `SOURCELORE_PROJECT_ROOT` 是否指向真实源码 |
| `sourcelore: command not found` | 当前终端是否定义了上述 shell 函数 |
| 仓库列表为空 | 先核对数据根，不能随意新建/迁移库 |
| `OFFLINE_CACHE_MISS` | 固定 Commit 尚未缓存，本次不能离线获取 |
| `CONTENT_NOT_CAPTURED` | 有路径元数据不代表已经采集源码字节 |
| 看上去 Tree COMPLETE | 必须看有效的 ROOT_ONLY/部分/完整覆盖度 |

禁止执行第三方仓库代码，也不要在命令记录或公开文件中保存 GitHub Token。分发第三方知识产物仍受 SourceLore 现有 `DISTRIBUTE` 门禁限制。
