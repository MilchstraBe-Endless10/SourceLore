# F2-P6A 检查点 · 基线 0374c71 · Crosswalk 已复算匹配

## 本轮定位
**不新增静态分析能力**。只证明 SourceLore 能作为一个完整产品跑通
「采集 → 入库 → 分类查询 → 卡片 → 离线复用」。

## 已知前提（从 P5A–P5J 继承）
- 模块全在，1360 项单测全绿
- 安装版 Skill 在 ~/.agents/skills/sourcelore/（launcher sha256 cfd254245b1dc043）
- 三个一直 OPEN 的门禁：
  - REAL_GITHUB_E2E（缺真实授权核验）
  - NATURAL_LANGUAGE_AUTO_TRIGGER（缺独立用户会话）
  - DISTRIBUTION_READY（B-1/B-2/B-3 OPEN）

## 关键陷阱（历史反复踩）
- D-31/D-32/D-41：**写入端与读取端字段名对不上**，只在链路末端暴露
- D-37：`lstrip("./")` 吞绝对路径与 `../` —— 安全相关
- 历史教训：不能在内存里传对象绕过持久化与进程重启

## 待办（按本轮优先级）
1. 能力矩阵：逐项实测安装版 Skill
2. 原创授权仓库完整离线工作流（含进程重启）
3. 真实 GitHub 仓库（候选 is-number，需核验具体 Commit 的 LICENSE）
4. 十项用户任务
5. 契约审计（跨模块字段）
6. 路径安全专项扫描
7. 离线复用 / 多 Commit
8. 20 项产品级 Gold
9. 自然语言触发清单（保持 NOT_VERIFIED）

## ★★ 阻断发现（2026-11-06 12:21）

### 阻断 1：原创授权仓库无法通过 CLI 建库
`analyze` 的唯一入口是 GitHub URL：
```
a.add_argument("url", help="https://github.com/<owner>/<repo>")
```
`A.analyze(url=...)` 内部走 GitHub API 采集。
**没有任何 file:// 或本地路径入口。**
→ 本轮第一项核心验收（原创授权仓库完整工作流）**无法从安装版 CLI 完成**。

### 阻断 2：GitHub API 已限流
```
GET /repos/jonschlinkert/is-number → HTTP 403 rate limit exceeded
```
按任务书 §5.4：立即返回真实错误，不重试、不等待、不绕过、不换身份。
→ 本轮第五/六项（真实 GitHub）为 **NOT_VERIFIED**，非能力缺陷而是外部条件。

## 这意味着
「验证它们能否作为同一个产品真正协同工作」这个目标，
目前**卡在 CLI 入口**——不是模块不协同，而是产品缺一条用户能走的门。

## 最小修复方向（符合任务书 §8 "可以进行的最小修复"）
给 `analyze` 增加本地只读仓库入口，让原创授权仓库也能走同一条产品链路。
不新建第二套 Storage/Facts，复用既有 ingest 路径。

## 已修（2026-11-06 12:23）
**新增本地 Git 只读入口** `src/skill_interface/local_repo_source.py`
- 只读 git ls-tree / cat-file，零网络，不执行仓库代码
- 真实 OID 自校验（SHA1(blob len\0raw) == 给定 sha）
- `analyze <本地路径>` 走本地分支 → 同一条 build_snapshot/ingest_snapshot 链路
- 实测：repo local:85cdd3850a72，commit 76efaf48…，9 文件 / 9 blob

## ★ 发现（非本轮引入，但本轮首次暴露）
`extract_file_path_observation` 返回 `observation=UNKNOWN`，
`ingest_fact` 正确拒入 A 层：
```
{'ok': False, 'error': 'PERMISSION_DENIED', 'detail': 'UNKNOWN 观察不是确定性事实，不入 A 层'}
```
→ 原 `analyze`（GitHub 路径）里 `FI.ingest_fact(store, f)` **同样静默失败且无人检查**，
  导致 `fact_count=0` 而 `claims=1`，Verification 恒 insufficient。
→ **产品缺陷：路径命题在当前设计下无事实支撑。**

## 下一步
改用内容级事实（README/Manifest → OBSERVED_PRESENT），
这才是产品主线；路径命题保留但明确标注证据不足。

## 内容链路接口（已确认）
```
extract_one(repository_id, commit_sha, file_path, git_blob_oid,
            content_asset_id, data, source_snapshot_id,
            budget, provenance_level, declared_completeness)
   → {observation, facts, status}
ingest_content_facts(store, repository_id, commit_sha, snapshot_asset_id,
                     snapshot_logical_identity, extraction_result,
                     content_asset_id, content_sha256, parser_id,
                     parser_version, file_path, git_blob_oid,
                     completeness_status, provenance_level)
```
`data` 是原始字节；`ingest_captured_blob` 返回 content_asset_id / content_sha256。

## 设计决定
本地路径**不做**路径命题（UNKNOWN 不入 A 层是框架正确行为）。
改走内容事实：README → README_HEADING；Manifest → dependency 声明；
源码 → Python AST / JS-TS 结构事实。这些是 OBSERVED_PRESENT。

## ★ 产品链路已打通（2026-11-06 12:26）
```
analyze /tmp/p6a_origin --path README.md
→ ok=True net=0 content_facts_total=17
  README.md     EXTRACTED facts=4
  package.json  EXTRACTED facts=4
  pyproject.toml EXTRACTED facts=3
  python/helper.py EXTRACTED facts=1
  python/main.py   EXTRACTED facts=1
  src/app.ts       EXTRACTED facts=1
  src/types.ts     EXTRACTED facts=1
  src/utils.ts     EXTRACTED facts=1
  tsconfig.json    EXTRACTED facts=1
```
**修的真缺陷**：`extract_one` 的可用状态是 `CONTENT_AVAILABLE`，
我最初判断 `CONTENT_AVAILABLE_VERIFIED` → 全部 facts=0。这是"状态名猜错"类缺陷。

## 关键：安装版 Skill 只装 launcher
`~/.agents/skills/sourcelore/` 只有 `sourcelore.py` + SKILL.md + references；
业务模块从工程 `src/` **实时加载**（launcher 三级项目根解析）。
所以改 src 立即生效，但**必须确认没有第二份同名模块**（本轮已查：无遮蔽）。

## 待做
1. 源码结构事实（Python AST / JS-TS）接入本地链路
2. 内容 Claim（README heading / manifest dependency）
3. 十项用户任务 + 卡片 + 离线复用
4. 契约审计 / 路径安全 / Gold / 文档

## 十项用户任务实测（安装版 CLI，2026-11-06 12:27）
| # | 任务 | 结果 |
|---|---|---|
| 1 | 列出仓库 | repositories → 1 条（local:85cdd3850a72）|
| 2 | README 知识 | query --type content → captured + content asset |
| 4 | Python 符号 | query --type code → class Worker / method Worker.run / function main |
| 5 | TS 接口与类型 | → ts_interface T / ts_type_alias Id |
| 6 | Import | → named_import @/utils (type_only=False) / #types (True) |
| 7 | Alias 映射 | query --type relation → @/utils → src/utils.ts rule=@/* resolved=1 |
| 8 | TS 项目归属 | query --type project → tsconfig.json VERIFIED include=src/**/*.ts |

全部 network_requests=0。

## 两个真缺陷
**D-42 `extract_one` 状态名猜错**：可用状态是 `CONTENT_AVAILABLE`，我判断 `CONTENT_AVAILABLE_VERIFIED`
→ 全部 facts=0，产品链路静默空转。
**D-43 导入展示字段名不一致**：Python 侧 `module_name`、JS/TS 侧 `module_specifier`，
CLI 只读前者 → TS 导入全显示 None。已统一回退。

## 待做
卡片 / 离线复用 / 多 Commit / 契约审计 / 路径安全 / Gold / 文档 / 提交

## 路径安全专项（tools/f2p6a_path_audit.py）
修 5 处 `lstrip("./")` → `_safe_norm`（只剥前导 "./"，不碰 "/" 与 ".."）：
config_aware_resolver / js_ts_module_resolver / local_module_resolver /
ts_project_references / ts_project_context。
审计结论：0 残留；归一化 5/5 正确；越界拒绝 5/5 正确。

## 契约审计（tools/f2p6a_contract_audit.py）
- **修 D-44**：`module_relation_adapter._matches` 无 ALIAS，
  `expected_target_path` / `expected_matched_rule` 直接比对 subject → 必然失配。
  已补 ALIAS 映射（resolved_target_path / matched_config_rule / state）。
- 三个 adapter 均同时兼容 payload 嵌套与查询扁平两种形态。
- 写读字段缺口：0（expected_* 由 ALIAS 处理，非缺口）。

## 离线复用实测
首次指纹：captured_blob_content=9 claim=1 verif=1 facts=38 snapshot=1
再次 analyze：net=0，指纹**完全不变**（无重建、无重复事实）
--offline：ok=True net=0
