# P6H 只读盘点 · 2026-11-06 22:33

## 模型身份（UNVERIFIED）
- DSH profile agent-default-model: provider=qodercn, model=dfmodel, reasoningEffort=max
- 会话系统上下文声明: deepseek-v4.1-flash
- provider 列表含 zw/glm-5.3-flash 但**未被选中**
- 阻断：DSH_HOME 读取被凭据保护拦截，无法读会话日志实际 model 字段
- **判定：矛盾，UNVERIFIED。不声称运行于 GLM 5.3 Flash。**

## DeepSeekBot 定性（已查实）
- 包 deepseekbot v1.6.0，现名 Tobs（原 DeepSeekBot）
- 是 DSH 插件 + agent preset，**不指定模型**
- preset 配置：45s 提问不阻塞、subagent 改 bot_subagent、挂 persona

## Git
- HEAD ea052d9 / branch main / 工作区干净
- **无 remote**（git remote -v 空）→ 不能声称已同步 GitHub

## 数据根三处
```
/tmp/p6b_real   602112 bytes  kb.db 存在    ← is-number(完整) + is-plain-obj(部分)
/tmp/p6f_real   442368 bytes  kb.db 存在    ← is-plain-obj(完整) + is-number(2条负例残留)
~/.sourcelore   不存在                       ← 默认根，空
```
目标：`/mnt/.../GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data`

## 迁移要点（待办）
- 不能直接覆盖复制 SQLite
- 需查是否有既有导入/导出/合并机制
- 不可变 A 层不得覆盖
- Blob 按 content_sha256 去重
- 不同仓库资产不得合并
- 二次迁移验证幂等

## 既有机制盘点（关键：决定迁移方式）
- **无 import_/merge_/migrate/export 子命令**（CLI 只有 status/repositories/help/analyze/inspect/history/query/card）
- 有 `src/storage/index_store.py: rebuild_index(store)` —— 索引重建能力存在
- `tsconfig_effective_config.merge_chain` 与本任务无关（配置链合并，不是知识库合并）

→ **结论：没有可复用的知识库合并机制。**
→ 迁移必须自己设计，最小化 + 可审计。
→ 但 rebuild_index 可复用：迁移后可用它重建索引行（这也是 D-67 历史补全的潜在正路）。

## D-67 修复正路（基于上面发现）
`rebuild_index` 若能从 assets payload 重建 index_rows（含 commit_sha），
则历史 13 条 verification 的索引可用它补全 —— **不新增机制，复用既有**。
恢复后第一件事：读 `index_store.rebuild_index` 实现，确认它是否填 commit_sha。

## ★★ 重大发现：rebuild_index 是定时炸弹（D-68）

`assets` 表 commit_sha **全部为 NULL**（所有类型 0/100%）：
```
captured_blob_content  4     有commit=0
claim_candidate       19     有commit=0
claim_verification    13     有commit=0
extracted_fact        22     有commit=0
repository_snapshot    1     有commit=0
```
但 `index_rows` 里 captured_blob_content/claim_candidate/extracted_fact 的 commit **是满的**。
→ 说明 index_rows 的 commit 是写入时**直接塞进索引行**的，不是从 assets 复制的。

而 `index_store.rebuild_index()` 的实现是：
```sql
SELECT ... commit_sha ... FROM assets   ← 读 assets 的 NULL
INSERT INTO index_rows(... commit_sha ...) VALUES(..., r["commit_sha"])  ← 写 NULL
```

**后果：执行 rebuild_index 会把当前正确的索引全部清成 NULL。**
这不是修复 D-67 的正路，反而是新缺陷 D-68 —— 一个「看起来该用、实际会毁数据」的机制。

## 因此 D-67 的正确修复路径必须改
原计划「用 rebuild_index 补全历史索引」**作废**。
必须先修 rebuild_index（或在修复前绝不调用它），
再单独解决 ingest_verification 不写 index commit 的问题。

## D-67 真根因（19:xx 定稿）
`AssetDraft` 没有 commit_sha 字段，只有 `source_snapshot: Optional[SourceSnapshot]`。
→ index_rows 的 commit_sha 只能从 `asset.source_snapshot` 推导。

- `ingest_verification(store, verif, repository_id=...)` **不传 source_snapshot**
  → 该资产 index 行 commit_sha = NULL
- 其他资产（fact/blob/claim）的入库函数传了 source_snapshot
  → index 行 commit_sha 有值

**修复方向已明确且最小**：
1. `ingest_verification` 接受 `source_snapshot` 并传入 AssetDraft
2. 历史 13 条：用可审计的追加式索引补写（不改 assets）
3. D-68 rebuild_index 在修复 source_snapshot 传导前**禁止调用**

## D-67 真根因（最终定稿，2026-11-06 22:36）
`knowledge_store._index_asset` 有三级回退 `_resolve_index_commit_sha`：
  1. draft.source_snapshot.commit_sha
  2. payload["commit_sha"]
  3. payload["source_snapshot"]["commit_sha"]

- **Claim.to_dict() 有 commit_sha** → 回退②命中 → claim_candidate 索引完好
- **Verification.to_dict() 没有 commit_sha，也没有 source_snapshot**
  → 三级全落空 → claim_verification 索引 commit_sha = None

代码注释里已经写着「实测该列因此全为 NULL」—— 说明这个坑以前就踩过一次，
只是当时只补了 Claim 那条路，Verification 这条漏了。

## 修复方案（最小、不改资产正文）
A. `ingest_verification(store, verif, repository_id, *, commit_sha=None)`
   收到 commit_sha 时构造 `SourceSnapshot(commit_sha=...)` 传给 draft
   → 走回退①。**不动 payload、不动哈希、不动 assets**。
B. 调用方 `content_claim_ingest.ingest_content_claim` 已有 claim，从 claim.commit_sha 传下去。
C. 历史 13 条：写一次性索引补全（只 UPDATE index_rows，C 层可重建，不改 assets）。
D. D-68：`rebuild_index` 从 assets 读 commit_sha 仍是 NULL → **仍禁止调用**，
   除非同时改成也用 payload 回退。

## D-67 修复完成（2026-11-06 22:38）
代码：`ingest_verification(..., commit_sha=None)` 构造 SourceSnapshot 走回退①；
      `content_claim_ingest` 从 claim.commit_sha 传入。
历史：`tools/f2p6h_backfill_commit.py` 只 UPDATE index_rows（C 层），12/13 补全。

补全后索引填充率：
```
captured_blob_content  4/4   claim_candidate 19/19
claim_verification    12/13  extracted_fact 22/22   repository_snapshot 1/1
```
那 1 条阻断是 **P6G 负例 F（跨仓库）** —— 它的 claim 属于 repo 24313173，
本库无该 repo 的 claim 索引。**阻断是正确行为**：它本就该 insufficient，
强行补全等于伪造证据。

查询验证：4 条事实 OBSERVED_SOURCE_FACT → **SUPPORTED_SOURCE_CLAIM**，
带回真实 Claim/Verification ID，net=0。

负例回归：D/E/F/G 全部仍 insufficient_evidence（NO_MATCHING_FACT）。
幂等：再跑补全 → 可补 0 条。

## P0 迁移完成（2026-11-06 22:40）
目标根：`/mnt/.../GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data`
无覆盖复制，逐资产搬运 + 按 (type, logical_id, repo, version) 判重。

| 资产类型 | 数量 |
|---|---|
| captured_blob_content | 7 |
| claim_candidate | 25 |
| claim_verification | 19 |
| extracted_fact | 75 |
| repository_snapshot | 2 |
| **合计** | **128** |

blobs 7 个（内容寻址去重：两库各有部分重叠）。
CLI 从统一根列出 2 个仓库：24313173 / 38923193。

## 新发现 U-4：伪 Commit 混入历史列表
索引里有 `aaaaaaaa…`(40个a) 3 行 —— 是 P6G 负例 E 造的错误 commit。
`repositories` 把它当成真实历史 Commit 列了出来。

**但查询层是正确的**：用该伪 commit 查询返回
`state=CONTENT_NOT_CAPTURED, facts=0` —— 不误报。
→ 缺陷只在 `repositories` 的展示过滤，不在知识裁决。

修复：repositories 只列有 repository_snapshot 或 captured_blob_content 支撑的 commit。

## §四 默认数据根验收（2026-11-06 22:42）
配置：`~/.config/sourcelore/config.json`（0600）→ data_root 指向 SourceLore_Data
解析优先级（`paths.py`）：--data-root > SOURCELORE_DATA_ROOT > config.json > ~/.sourcelore
★ 核心模块不含任何硬编码绝对路径，配置从文件读。

不带 --data-root 实测：
```
status: data_root=<SourceLore_Data>, db_exists=True, storage_available=True, repository_count=2
repositories: 24313173 → 98e8ff1d…  38923193 → 666df7c1…
--data-root /tmp/p6f_real 仍可用（count=2）
```

## §六 U-4 修复
`list_repositories` 只把有 snapshot/blob 支撑的 commit 算作历史版本。
伪 commit `aaaa…` 已不再出现。test：两仓库各只显示 1 个真实 commit。

## 仓库名缺口（U-2 未解决）
`repo_bindings`/`operation_log` 均为空，snapshot payload 无 owner/name 字段。
**当前库中没有仓库名的权威存储** → 不能显示 `jonschlinkert/is-number` 等名称。
不得按 repository_id 硬编码映射（任务书 §六 禁止）。
可行方向：下次采集时把 owner/name 写入 snapshot payload，历史库无法追溯。

## ★★ 重要数据真实性核对（2026-11-06 22:45）
抽查 captured_blob_content 的 provenance_level：
```
24313173 (is-number)     全部 3 个 blob = SYNTHETIC_FIXTURE      ← 合成夹具
38923193 (is-plain-obj)  全部 4 个 blob = AUTHORIZED_REMOTE_SOURCE ← 真实远程
```
→ **只有一个仓库是真实 GitHub 数据。** 另一个是合成夹具。
这符合既有铁律：合成夹具永不改标成真实。
但卡片渲染层显示 "AUTHORIZED_LOCAL_FIXTURE"，与 query 层的
"AUTHORIZED_REMOTE_SOURCE" 措辞不一致 —— 需核对渲染映射（待办 U-5）。

## 浏览器验收（真实渲染）
Playwright 打开 http://127.0.0.1:18991/SL-SCARD-...html：
- 标题「源码结构卡片 · index.js」✓
- 六节结构完整（身份/概览/符号/导入/导出/限制）✓
- 裁决层级列真实渲染：「已验证 · 命题成立」+ claim=SL-CLAIM-4428bc79… ✓
- Commit / Blob OID / 字节 / 校验 全部在场 ✓
