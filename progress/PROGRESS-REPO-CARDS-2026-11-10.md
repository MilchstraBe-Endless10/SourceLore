# SourceLore 仓库知识卡片 · 进度（2026-11-10）

## 用户最终确认的需求（2026-11-09 明确给出）

SourceLore 要从「源码信息提取 Skill」升级为：
**项目知识文档 + 双层关系图谱 + DSH 原生可视化卡片** 的一体化知识系统。

三层结构：
- **A 仓库代码结构图谱**：文件树、模块依赖、调用关系（`index.js → 依赖哪些模块 → 被谁引用`）
- **B 知识主张网络**：Claim 之间因共享 Fact/Snapshot 形成的关联（★ 共享证据 ≠ 互相证明）
- **C 每个仓库的项目知识文档**：项目概览/文件结构/模块依赖/函数接口/调用关系/项目配置/知识主张/证据历史

卡片必须出现在 **Bot 模式（Tobs）界面内部**，不是 DSH 主界面。

---

## 已完成的代码（全部真实跑通）

### 1. A/B 图谱派生
`src/views/repo_graph_derivation.py`

真实产出（三仓库）：
| 仓库 | 节点 | 边 | 裁决 |
|---|---|---|---|
| is-number | 20 | 13 | 支持 6 · 未裁决 2 |
| is-plain-obj | 24 | 18 | 支持 12 · 证据不足 5 |
| preact | 46 | 32 | 支持 13 · 反驳 1 |

边类型：`TREE_CONTAINS` / `IMPORTS` / `DECLARES` / `SHARES_FACT`
决定了必须如实标注 `resolution_state`，未解析关系不得伪装成确定关系。

**踩过并修掉的三个真 bug**：
1. `lstrip("./")` 把 `.editorconfig` 吃成 `editorconfig` —— 改成循环剥 `"./"` 前缀
2. 同一 claim_id 在库里有多个 asset_version，导致 A↔A 自环 —— 按 claim_id 去重取最高版本
3. claim 重复成对出现

**关键数据事实**：`claim_candidate.payload` 里**没有** `evidence_refs`（0/39）；
真正的证据在 `claim_verification.payload.fact_ids`（30/33 有值）。B 层必须从后者取。

### 2. 卡片数据投影 + 项目文档
`src/views/repo_card_projection.py`

每仓库产出 7 个文件，写到 `SourceLore_Data/派生视图/<repo>/<commit>/`：
`project-overview.md` / `file-structure.md` / `module-dependencies.md` /
`claim-network.md` / `evidence-index.md` / `card-data.json` / `code-graph.json`

### 3. 卡片 HTML 渲染
`src/renderer/repo_card_html.py` —— 四 Tab（文件结构/知识主张/图谱统计/限制），
`esc()` 全转义、CSP 内联、零外部资源。产物：`knowledge_card.html`（截图已验证正确）。

### 4. 宿主路由
`plugin/dsh-sourcelore-cards/index.js` 新增 `/repocard?repository_id=<id>`
→ 读派生视图 card-data.json + code-graph.json。**已验证返回 200 且数据完整**。

### 5. 客户端
`plugin/dsh-sourcelore-cards/client.js` 重写为仓库知识卡片渲染，
读 `/repocard`，卡片自持 Tab 状态。

---

## 采集器的真实缺陷（必须修）

`tree_collector.py` 用 `recursive=True` 请求，但库里三个仓库的树**最大深度都是 0**，
只有根层条目（13/13/32 条），子目录（src/compat/hooks/...）内容一条没采。
快照仍标 `COMPLETE` —— 这比标 PARTIAL 更危险。

图谱派生已把这个如实报成 `tree_status: ROOT_ONLY` 并列入 limitations。

修复需要重新采集，而 **GitHub 匿名配额已用尽**（60/h），需要 token 才能深扫。
未读取、未请求任何凭据。

---

## 当前卡住的地方（唯一未完成）

**客户端新代码没有在浏览器里生效。**

事实链：
- 源文件已无调试标记（`grep -c CARD-V2-MARK` = 0）
- 服务器 rev 已更新 = `00f92fd9b8a9`
- 服务器实际提供的 bundle **确实包含**新代码（`loadRepos`×3、`entryId = ID + ":v" + BUILD`）
- 但界面仍渲染旧标题 `仓库知识卡片 · CARD-V2-MARK`

根因：bundle 响应头是
```
cache-control: public, max-age=31536000, immutable
```
一年期不可变缓存。rev 变了 URL 也变，但 Electron 内核对已加载的插件模块没有重新拉取。
Ctrl+R、Ctrl+Shift+R、Ctrl+Shift+F5 都试过，均未让新 bundle 生效。

**曾成功过一次**：在 `apply()` 里把 id 改成 `ID + ":v" + BUILD` 后，那次刷新确实换上了新版
（出现过 CARD-V2-MARK 被选中的画面）。之后再次修改就没再生效。

### 下一步该试的（按可靠性排序）

1. **给 bundle URL 加时间戳参数**，绕过 immutable 缓存 —— 但 URL 由 host 生成，不一定可控
2. 检查是否有 Service Worker 拦截 `/plugins/*`
3. 在 Bot 设置里关闭再重新启用本插件（触发重新加载）
4. 最后手段：重启 DSH（**必须用户同意**）

---

## 相关文件和路径

- 源码：`SourceLore/src/views/repo_graph_derivation.py`、`repo_card_projection.py`、
  `SourceLore/src/renderer/repo_card_html.py`
- 插件：`SourceLore/plugin/dsh-sourcelore-cards/{index.js,client.js}`
- 数据根（永久）：`SourceLore_Data/派生视图/`
- UI 补丁：`@botharness/ui/lib/client.js` 的 `BhHomeSlot`（原版备份 `/tmp/botharness-ui-client.js.orig`）
- 卡片样例截图：`/tmp/bot_final.png`（Bot 内三张卡片）、`/tmp/card_real.png`（单卡七区域）

## 检索词
repo graph derivation / 派生视图 / tree ROOT_ONLY / fact_ids 证据位置 / immutable 缓存不生效
