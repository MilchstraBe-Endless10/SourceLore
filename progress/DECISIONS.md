# SourceLore 决策记录

> 每条决策只记「当时为什么这么定」。后续若要推翻，写新条目，不删旧条目。

---

## D-001 项目根目录取用户指定的 SourceLore 路径

- 时间：2026-10-31
- 决策：全部代码与文档写入 `/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore`
- 理由：全局 `AGENTS.md` 规定 AI 产出默认存入 `Cosmos_File/AI产出数据文件`，但用户的总控提示词明确指定了 SourceLore 路径，且分阶段手册 §0 写死了两个目录。用户明示优先于全局默认。
- 影响：不使用 `Cosmos_File` 目录承载本项目。

## D-002 知识资产与源码 Git 严格隔离

- 时间：2026-10-31
- 决策：`knowledge/`、`cache/`、`upstreams/`、`.dsh/skills/` 全部写入 `.gitignore`
- 理由：总控提示词 §D 明文「严禁混淆 SourceLore 的两种不同写入」；源码仓库不跟踪 `knowledge/`、`upstreams/`、临时仓库、下载缓存。
- 后果：知识库产物永远留在本地磁盘，不随代码推送。

## D-003 Git 身份使用项目内局部配置

- 时间：2026-10-31
- 决策：仓库内 `git config user.name "SourceLore Dev Agent"` / `user.email "sourcelore@local.invalid"`
- 理由：不污染用户全局 Git 身份，也不冒充用户本人提交。M9 推送时如需真实署名，由用户指示后调整。

## D-004 不使用 sudo 推进开发

- 时间：2026-10-31
- 决策：全部开发以普通用户 `arlune_innersea` 完成
- 理由：分阶段手册 §5 要求权限问题不得擅自 sudo，应报 `BLOCKED_PATH` / `BLOCKED_WORKSPACE_GRANT`。
- 影响：若遇真实权限阻塞，先向用户报告并等待决定。

## D-005 上游审计一个回合只做一个源

- 时间：2026-10-31
- 决策：M1 的六个上游严格串行，一次只处理一个
- 理由：模型上下文窗口 131072（实测）。六个完整仓库同时加载必然撑爆。分阶段手册 §3 的 M1 提示词也明确要求「不要一次加载六个完整仓库」。
- 影响：M1 会跨多个回合完成，每回合结束必须落盘。

## D-006 事实采集优先用确定性脚本，模型只读结构化结果

- 时间：2026-10-31
- 决策：GitHub 元数据、目录树、语言统计、依赖文件、入口文件等一律由脚本采集并落 JSON，模型读摘要而非原始源码
- 理由：既是文档 §B Flash-First 协议要求，也是本机 131072 上下文的硬约束。同时避免模型「凭空写出」未经验证的事实。

## D-007 上游仓库 URL 必须先核实再用

- 时间：2026-10-31
- 决策：`TASKS.json` 中 UPSTREAM-01/03/04 的仓库地址标注为待核实，M1 开始前必须用真实 API 请求确认
- 理由：总控提示词 §C 只给了部分完整 URL（repo-analyzer-skill、deer-flow、project-knowledge-base、repo-security-review）；repository-discovery 与 SNIKO agent-skills 的完整地址需确认。宁可报「待确认」，不得编造 URL 后当作事实写进文档。
