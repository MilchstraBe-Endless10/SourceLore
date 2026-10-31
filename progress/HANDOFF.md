# SourceLore 交接文档

> 本文件是跨会话恢复的唯一入口。任何新会话第一件事就是读它。
> 最后更新：2026-10-31T09:58:00+08:00

---

## 一、现状

项目已初始化，M0 环境审计完成并通过 Gate。M1 尚未开始。

- 项目根：`/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore`
- 当前里程碑：**M0（已通过）**
- 当前任务：**M0-02 项目骨架与 Git 初始化（进行中，等待首个 commit）**
- 开发模型：`workbuddy/deepseek-v4.1-flash`（上下文 131072，务必小步走）

## 二、已通过的 Gate

| Gate | 判定 | 证据 |
|---|---|---|
| M0：可读取和安全写入指定目录 | PASS | `BASE_WRITABLE=YES`；骨架已创建；`git init` 成功 |
| M0：模型能运行最小工具实验 | PASS | bash / git / python3 venv / SQLite FTS5 / curl 全部实跑成功 |
| M0：DSH 技能路径有依据 | PASS | 用户级根 `<DSH_HOME>/skills` 经 Catalog 交叉验证；三个 skill Provider 已注册 |

## 三、最后一条真实命令与退出码

```
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' && git init -b main
```

```
Initialized empty Git repository in .../SourceLore/.git/
```

`exit=0`

## 四、本回合实际修改的文件

| 文件 | 说明 |
|---|---|
| `.gitignore` | 忽略 knowledge/ cache/ upstreams/ .dsh/skills/ 与 Python、密钥产物 |
| `.gitattributes` | LF 统一、二进制标注 |
| `docs/environment-audit.md` | M0-01 完整审计报告（实测数据） |
| `docs/platform-compatibility.md` | 平台兼容性矩阵与陷阱清单 |
| `progress/STATE.json` | 状态机初始值 |
| `progress/TASKS.json` | M0-01 DONE、M0-02 IN_PROGRESS、UPSTREAM-01~06 PENDING |
| `progress/HANDOFF.md` | 本文件 |

创建的目录骨架（按总控提示词 §E）：

```
src/sourcelore/{collection,evidence,lifecycle,storage}
skills/sourcelore/{references,scripts}
schemas docs tests progress reports/acceptance
knowledge cache upstreams .dsh/skills
```

## 五、测试

`NOT_RUN` —— M0 不含自动化测试，M2 才开始引入单元测试。审计类验证以真实命令输出为准，已在 `docs/environment-audit.md` 逐条记录。

## 六、Git HEAD

`NOT_COMMITTED` —— 仓库刚初始化，尚无 commit。

## 七、下一步

**M0-02 收尾**：完成首个基线提交，然后进入 M1 的 UPSTREAM-01。

M1 硬性约束（来自总控提示词 §G）：

- 六个上游**一次只处理一个**，每个都固定 Commit SHA
- 每个都要查 LICENSE / NOTICE / 文件头许可证声明
- 每个都要读 SKILL.md 与脚本，列出可复用能力与兼容性风险
- 逐个更新 `docs/upstream-manifest.json` 与 `docs/fusion-matrix.md`
- **严禁把六个 SKILL.md 原样拼接**
- 未到 M1 Gate 不得开始大规模融合编码

## 八、已知限制

1. **上下文 131072**：不能大段读上游源码，必须用脚本采事实 + 分页读取
2. **会话 cwd 不在项目根**：所有命令必须绝对路径或显式 cd
3. **路径含括号与中文**：shell 必须引号，Python 用 pathlib
4. **Skill 源码目录不是发现根**：M6 必须安装到发现根并用 Catalog 复验
5. **Tobs 会话 cwd 不是项目根**：M7 触发依赖用户级 skill 根，需专门验证
6. **上游 URL 待核实**：`TASKS.json` 中 UPSTREAM-01/03/04 的仓库地址是从记忆推测的，M1 必须先核实真实地址，核实不了就记录为待用户确认，不得凭空编造

## 九、恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' && git log --oneline -5 && python3 -m json.tool progress/STATE.json && python3 -m json.tool progress/TASKS.json | head -40
```

然后读 `progress/STATE.json` 的 `active_task`，继续该任务。
