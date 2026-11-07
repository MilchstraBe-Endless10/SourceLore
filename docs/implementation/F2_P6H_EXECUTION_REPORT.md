# F2-P6H 执行报告 · 使用环境修复与完整验收

生成时间：2026-11-06 22:48
基线：`ea052d9` → 当前 `1a7f69d`

---

## 一 · 模型身份（UNVERIFIED）

任务书要求先核对实际运行的模型，不得凭声明声称。核对结果**矛盾，无法判定**：

| 来源 | 值 |
|---|---|
| DSH profile `agent-default-model` | provider=`qodercn`, model=`dfmodel`, reasoningEffort=`max` |
| 会话系统上下文声明 | `deepseek-v4.1-flash` |
| provider 列表中的 `zw/glm-5.3-flash` | **存在但未被选中** |
| 会话日志实际 model 字段 | **读取被凭据保护拦截** |

**结论：不声称运行于 GLM 5.3 Flash，标注 UNVERIFIED。**
产品修复与模型无关，未因此停止工程工作。

## 二 · DeepSeekBot 定性（已查实）

`deepseekbot` v1.6.0，现名 **Tobs**（原 DeepSeekBot）。是 DSH **插件 + agent preset**，
不是另一个模型。preset 配置只有三件事：45 秒未答提问不阻塞、subagent 改 `bot_subagent`、挂 persona。
**它不指定模型**，模型走 DSH 的 `agent-default-model`。

## 三 · 数据根统一（P0，完成）

目标根：`/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data`

**没有既有合并机制**（CLI 无 import/merge/migrate/export 子命令），故自建最小可审计迁移
`tools/f2p6h_migrate.py`：逐资产搬运，按 `(asset_type, logical_identity, repository_id, asset_version)`
判重，不覆盖、不合并不同仓库、Blob 按内容寻址去重。

| 资产类型 | 目标库数量 |
|---|---|
| captured_blob_content | 7 |
| claim_candidate | 25 |
| claim_verification | 19 |
| extracted_fact | 75 |
| repository_snapshot | 2 |
| **合计** | **128** |

blobs：7 个。迁移前已备份至 `SourceLore_Data/_backup/20261106-223710/`（含 SHA256）。

**幂等已验证**：二次迁移 `copied={}`，assets 128 → 128。

CLI 从统一根列出 2 个仓库，各自唯一真实 commit：
- `24313173` → `98e8ff1da1a89f93d1397a24d7413ed15421c139`
- `38923193` → `666df7c10035f7e26f27ec214fe5ae3173435f34`

## 四 · 默认数据根（P0，完成）

配置：`~/.config/sourcelore/config.json`（0600）

解析优先级（`paths.py`，单一权威来源）：
1. `--data-root` 参数
2. `SOURCELORE_DATA_ROOT` 环境变量
3. `~/.config/sourcelore/config.json` 的 `data_root`
4. `~/.sourcelore`（旧默认）

**核心模块不含任何硬编码绝对路径。**

验收（不带 `--data-root`）：
```
status        → data_root=SourceLore_Data, db_exists=True, storage_available=True, repository_count=2
repositories  → 2 仓库，各自唯一真实 commit
--data-root /tmp/p6f_real 显式覆盖仍可用
```

## 五 · D-67 Verification 索引契约（P0，已修）

**根因**：`knowledge_store._index_asset` 有三级回退 `_resolve_index_commit_sha`
（source_snapshot → payload.commit_sha → payload.source_snapshot.commit_sha）。
`Claim.to_dict()` 有 `commit_sha`，回退②命中；
**`Verification.to_dict()` 既无 commit_sha 也无 source_snapshot**，三级全落空
→ `index_rows.commit_sha` 恒为 NULL → 查询按 commit 过滤读不到。

代码注释里已写着「实测该列因此全为 NULL」，说明此坑曾踩过一次，只补了 Claim 那条路。

**修复**（不改资产正文、不改哈希、不删 SQL 过滤）：
1. `ingest_verification(..., commit_sha=None)` 收到 commit 时构造
   `SourceSnapshot(commit_sha=...)` 传给 `AssetDraft`，走回退①
2. `content_claim_ingest` 从 `claim.commit_sha` 传下去
3. 历史 13 条用 `tools/f2p6h_backfill_commit.py` **只 UPDATE index_rows**（C 层可重建），
   commit 从对应 claim 索引取，歧义则不补并计入 blocked

**结果：12/13 补全，1 条阻断。**

阻断的那条是 **P6G 负例 F（跨仓库命题）**——它的 claim 属于 repo `24313173`，本库无该 repo
claim 索引。**阻断是正确行为**：该命题本就应为 insufficient，强行补全等于伪造证据。

验收（真实 is-plain-obj）：
```
query 38923193 --type code --path index.js
→ state=FOUND, net=0
→ 4 条事实 display_level 全部 SUPPORTED_SOURCE_CLAIM（此前全为 OBSERVED_SOURCE_FACT）
→ 各带真实 claim_id / verification_id
```
负例回归：不存在函数 / 错 Commit / 错仓库 / 错 kind —— **全部仍为 insufficient_evidence，无假支持**。
补全幂等：二次运行「可补 0 条」。

## 六 · 仓库名称（P1，未解决）

`repositories` 只返回 `repository_id`，`repository` 字段为 None。

**核查结论：当前库中没有仓库名的权威存储。**
- `repo_bindings` 与 `operation_log` 均为 0 行
- `repository_snapshot` payload 只有 `repository_id` / `commit_sha` / `tree_entries` 等，**无 owner/name**
- `metadata` 资产不存在

任务书禁止按 `repository_id` 硬编码映射，故**不实现**。我尝试过从 payload 读名，确认字段不存在后已回滚该改动。
可行方向：下次采集时把 owner/name 写入 snapshot payload；历史库无法追溯。

## 七 · 知识卡片裁决展示（P1，完成）

三张旧卡（`/tmp` 路径）已确认存在，新卡统一输出到 `SourceLore_Data/cards/`。

修复内容：卡片模型注入裁决索引，符号表与导出表各增两列
「裁决层级」「Claim / Verification」；`_verdict_cell` 实现五档文案，
未验证事实显式写「已观察，尚未获得命题验证」。

验收（Playwright 真实打开 `http://127.0.0.1:18991/`）：
```
标题：「源码结构卡片 · index.js」
六节结构完整：仓库身份 / 结构概览 / 符号声明 / 静态导入 / 静态导出 / 限制与免责
裁决列渲染：「已验证 · 命题成立」×4，claim=SL-CLAIM-… 与 verif=SL-VERIF-… 各 4 个
保留：CSP、distribution_allowed=false、固定 Commit、Git Blob OID、字节校验
```

## 八 · 新发现 D-68（已修）

`github_knowledge_extract.py` 三处硬编码 `provenance_level="AUTHORIZED_LOCAL_FIXTURE"`，
对**真实远程仓库**抽出的源码事实也标成「本地夹具」——**证据层降级真实数据**。

修复：来源等级继承自被抽取 blob 的 `meta.provenance_level`；未知则记 `PROVENANCE_UNKNOWN` 并跳过，不猜。

验证：
```
38923193 (真实)  抽取 sf=4 → 继承 AUTHORIZED_REMOTE_SOURCE
24313173 (合成)  抽取 sf=0 → 正确报 UNSUPPORTED_SEMANTIC_FORM (CommonJS)
```
历史资产不追溯改写（不可变 A 层）。

## 九 · 数据真实性核对（关键）

| 仓库 | blob provenance | 性质 |
|---|---|---|
| `24313173` (is-number) | `SYNTHETIC_FIXTURE` | **合成夹具，非真实 GitHub 数据** |
| `38923193` (is-plain-obj) | `AUTHORIZED_REMOTE_SOURCE` | 真实远程 |

**只有一个仓库是真实 GitHub 数据。** 合成夹具未改标为真实，符合既有铁律。

## 十 · DSH 使用验收

| 场景 | 结果 |
|---|---|
| A 显式调用（`repositories` 用默认根） | 通过：2 仓库，claims 8/17 |
| B 自然语言自动触发 | **NOT_VERIFIED** —— 本会话为显式加载，不能声称自动发现 |
| C 继续对话（按路径查源码，不手填内部 ID） | 通过：FOUND，net=0，supported 4/4 |
| D 卡片生成并打开 | 通过：浏览器真实渲染 |
| E 不支持场景（is-number CommonJS） | 通过：`SOURCE_NOT_ANALYZED`, facts=0，**未编造 supported** |

## 十一 · 全量回归

**1489 项全绿**（与 P6F 基线一致）。

注意：`pytest tests/` 并列收集会因 `sfx.CLI` 导入顺序冲突失败（收集期错误，非功能缺陷），
须按目录分组 discover，部分目录需 `-t .`（`-t` 仅对 `discover` 有效）。

## 十二 · GitHub 同步

```
git remote -v        → 空
git branch -vv       → main（无 upstream）
git ls-remote origin → fatal: 'origin' does not appear to be a git repository
```
**无远端，未推送，不能声称已同步 GitHub。**

## 十三 · 未解决 / 保留项

| 项 | 状态 |
|---|---|
| 仓库显示名称（U-2） | **未解决**，库中无权威存储，按禁令不硬编码 |
| 自然语言自动触发 | NOT_VERIFIED（需独立会话） |
| `rebuild_index`（D-69） | **危险**：从 `assets` 读 commit（该列全 NULL），执行会把正确索引清空。**禁止调用**，未修 |
| `current_view` / `repo_bindings` 迁移 | 我猜列名错误（`asset_id`/`binding_json` 不存在），未搬。**这两表在源库本就为空，无数据损失** |
| 分发门禁 B-1/B-2/B-3 | 仍 OPEN，未清洗 |

## 十四 · 是否达到开箱即用

**接近但未完全达到。**

已做到：不填 `--data-root` 就能读到真实知识；两个仓库同一根可见；源码裁决能正确读回；
卡片能打开并显示裁决状态；网络请求为 0。

未做到：仓库只显示数字 ID 不显示名称；自然语言自动触发未独立验证。

---

# 追加（2026-11-07 00:20–00:40）

## 模型
用户指示使用 DeepSeek Bot 默认模型，不再追究身份矛盾。
profile `agent-default-model` = provider `qodercn` / model `dfmodel` / reasoningEffort `max`。
★ 不再声称「运行于 GLM 5.3 Flash」。

## DeepSeekBot 实质
`deepseekbot` v1.6.0（Tobs）。DSH 插件 + agent preset。
`cordis.im.patch.yml` **不修改工作目录、环境或数据根** —— 与普通会话共享同一份
`sourcelore` 技能目录与同一 `data_root`。因此本会话的 CLI 验证对 Bot 等效。

## 本轮新增修复
| 缺陷 | 内容 | 状态 |
|---|---|---|
| U-2 | 仓库显示名：analyze 写 `observation_record` 独立资产，repositories 读回 | 已修，需重采才有值；无资产不猜 |
| D-70 | `--plan` 忽略 URL，多仓库时误报 AMBIGUOUS | 已修：按 URL 解析，找不到明确报 NOT_REGISTERED |
| D-70b | 迁移漏搬 `repo_slugs.json` | 已合并补写到统一根 |
| D-69 | `rebuild_index` 照抄 `assets.commit_sha`（整列 NULL）会清空索引 | 已修：payload 回退 + claim 反查；真实库验证 12/19→18/19，其余全保住 |


---

# 追加二（2026-11-07 12:33）

## 用户三条指令落实
### ① 卡片进 Bot，删网页路径
新模块 `src/skill_interface/bot_card.py`：`render_bot_block()` 纯函数，零写盘零联网。
`card --code` **默认**返回 `{format:"bot_block", repository:"owner/name", text:..., network_requests:0}`；
`--html` 降为显式遗留出口（原 HTML 生成路径未删净，仅不再默认）。

五档点阵字模（对齐 botui-core 的「格子亮度」语义）：
```
▣ 已验证·命题成立   ▤ 已观察·尚未验证   □ 证据不足
△ 该语义形式不支持   · 尚未分析
```

实测 preact（42283287，commit dbeba0d5）：
```
**源码知识** · preactjs/preact（42283287）
固定 Commit `dbeba0d59bb5` · 文件 `src/index.js`
符号 0 · 导出 13 · 导入 0 · 事实 13
▣ 13 项已获命题验证，可当结论引用。
```

### ② 排版调查结论（关键否定）
Bot 的 `card` 是**工具授权卡**，不是内容卡：
`cardOutcome` = allowed-once / allowed-always-tool / allowed-always-exact /
allowed-always-all / rejected；生命周期 decided/answered/cancelled/expired。
→ 挪用即「改别人排版」，禁止。知识改以**普通 agent 消息文本块**呈现，
点阵符号天然贴合 Tobs 的点阵视觉语言，不改动其任何既有排版。

Bot 视觉体系出处 `@botharness/botui-core`：
三张独立表（cells / order / brightness）、
`createDotMatrix(el,{size,cols,rows,silhouette,dots/preset})`、
`DotGlyphSpec{sides,radius,innerRadius,star,spin,aspect}`、`Envelope{stops,rest,duty,gauss,cycleMs}`。

### ③ 不再等配额 —— 证明可以完全不需要
`git clone --depth 1 --filter=blob:none` 走 git 智能 HTTP 独立通道，
不消耗 REST API 配额（实测 API remaining=0 时 clone 仍成功）。

preact 全流程零配额完成：
```
git 取 src/index.js 423B  oid 045fb679cfb6c813（与 GitHub 一致）
parse → PARSE_COMPLETE / EXTRACTED → 13 facts
13 claim + 13 verification → 全 supported
```

## 回归
**1499 项全绿**（基线 1489 + bot_presentation 新增 10）。
