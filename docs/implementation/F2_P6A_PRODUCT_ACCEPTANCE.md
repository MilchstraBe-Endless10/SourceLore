# F2-P6A 产品验收

基线 `0374c71`。

## 一、结论先说

SourceLore 现在能从安装版 Skill 完成一条完整的产品工作流：
本地授权 Git 仓库 → 建快照 → 内容事实 → 源码结构事实 → 配置与关系 → TS 项目 → 持久化 →
进程重启后查询 → 生成卡片 → 离线复用。

全程 `network_requests=0`。

但两道门禁仍然开不开：

- `REAL_GITHUB_*`：GitHub API 已限流（HTTP 403），拿不到真实仓库。
- `NATURAL_LANGUAGE_AUTO_TRIGGER`：本轮没有独立用户会话。

## 二、能力矩阵（全部走安装版 CLI 实测）

| 用户功能 | 命令 | 结果 | 网络 |
|---|---|---|---|
| 建立知识库 | `analyze <repo>` | ok, 17 内容事实 + 15 结构事实 | 0 |
| 列出仓库 | `repositories` | 1 条 | 0 |
| 固定 Commit | `analyze --commit` | 双 Commit 各自成立 | 0 |
| README | `query --type content --path README.md` | captured 可读 | 0 |
| 依赖声明 | `query --type content --path package.json` | 可读 | 0 |
| Python 符号 | `query --type code --path python/main.py` | class/method/function | 0 |
| TS 符号 | `query --type code --path src/types.ts` | ts_interface / ts_type_alias | 0 |
| Import | `query --type code --path src/app.ts` | 2 条，含 type_only | 0 |
| Alias 映射 | `query --type relation --path src/app.ts` | `@/utils → src/utils.ts` | 0 |
| TS 项目 | `query --type project` | VERIFIED，include 正确 | 0 |
| 知识卡片 | `card --path README.md` | 6352 字节 HTML | 0 |
| 离线复用 | `analyze --offline` | ok，资产指纹不变 | 0 |
| Harness 发现 | — | 见下节 | — |
| 自然语言触发 | — | **NOT_VERIFIED** | — |

## 三、原创授权仓库

`/tmp/p6a_origin`，真实 Git 对象：

```
commit A 4ec31e0f75f9e34b7352211f52cda69ee801e497   app.ts: run()
commit B 76efaf481cbbc5413787234154e5be1b3e3fc5c7   app.ts: execute()
root tree B  44309f757ccc56a79594fec827a95e7dbcf490eb
README blob  cf2c5c1f858626f165de2ff0bef793240af36921
```

README blob OID 与 `git rev-parse` 独立比对一致。9 文件 / 9 blob。

含 README.md、package.json、pyproject.toml、tsconfig.json（带注释与尾逗号）、src/{app,utils,types}.ts、python/{main,helper}.py。

**两种构建清单混用是刻意的**：为了在同一仓库里验证各知识类别都能建起来，不代表真实项目架构。

## 四、命中的缺陷

**D-42 状态名猜错。** `extract_one` 的可用状态是 `CONTENT_AVAILABLE`，我写成
`CONTENT_AVAILABLE_VERIFIED` → 全部 facts=0，链路静默空转、`ok=True`。

**D-43 导入展示字段不一致。** Python 用 `module_name`，JS/TS 用 `module_specifier`，
查询只读前者 → TS 导入全显示 None。

**D-44 module_relation_adapter 缺 ALIAS。** `expected_target_path` 直接比对 subject
（实际字段是 `resolved_target_path`）→ 永远失配。D-41 的同类问题，第三批了。

**D-45 五处 `lstrip("./")`。** 分布在 config_aware_resolver、js_ts_module_resolver、
local_module_resolver、ts_project_references、ts_project_context。虽输入来自 git Tree
（不含 `../`），但写法与 D-37 同源，统一换 `_safe_norm`。

## 五、路径安全

`tools/f2p6a_path_audit.py`：0 残留。

```
归一化  /abs/x → /abs/x        ../../etc → ../../etc   ./a/b → a/b   ✓
越界    /etc/passwd → None    ../../../etc → None     ../.. → None  ✓
合法    src/* → src/*         ../lib/* (pkg/a) → pkg/a/lib/*          ✓
```

## 六、契约审计

`tools/f2p6a_contract_audit.py`：

- 三个 adapter 都同时接受 payload 嵌套与查询扁平两种形态。
- 写读字段缺口 0（`expected_*` 由 ALIAS 映射，不是缺口）。
- `module_relation_adapter` 与 `ts_project_adapter` 均带 ALIAS。

## 七、离线复用

```
首次：captured_blob_content=9 claim=1 verif=1 facts=38 snapshot=1
再跑：net=0，指纹完全不变
--offline：ok=True，net=0
```

没有重复建快照、没有重复写事实、没有覆盖旧 Commit。

## 八、产品级 Gold

20 条，全部走安装版 CLI。阻断指标全零：

错误肯定 0 / 错误否定 0 / 错仓库或 Commit 0 / 只读查询写入 0 / 非预期网络 0 / 卡片安全违规 0。

## 九、测试

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77
blob_capture59 content_persistence63 content_skill49
source_analysis88 js_ts_analysis72 module_resolution148 ts_projects136
product_acceptance21
= 1381，失败 0，退出码全 0
```

## 十、门禁

| 门禁 | 状态 |
|---|---|
| A SKILL_PACKAGE_INTEGRITY | **DONE** |
| B SKILL_DISCOVERY | **PARTIAL** |
| C LOCAL_REPOSITORY_KNOWLEDGE_E2E | **DONE** |
| D REAL_GITHUB_COLLECTION | **BLOCKED**（403 限流）|
| E REAL_GITHUB_CONTENT_PERSISTENCE | **BLOCKED** |
| F REAL_GITHUB_KNOWLEDGE_E2E | **BLOCKED** |
| G PERSISTED_KNOWLEDGE_QUERY | **DONE** |
| H KNOWLEDGE_CARD_RENDERING | **DONE** |
| I KNOWLEDGE_EVIDENCE_TRACEABILITY | **DONE** |
| J OFFLINE_REUSE | **DONE** |
| K MULTI_COMMIT_ISOLATION | **DONE** |
| L CROSS_MODULE_CONTRACT_INTEGRITY | **DONE** |
| M PATH_SECURITY_REGRESSION | **DONE** |
| N INSTALLED_SKILL_PRODUCT_E2E | **DONE** |
| O NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** |
| P DISTRIBUTION_READY | **NOT_READY** |

`B SKILL_DISCOVERY` 给 PARTIAL：Skill 目录结构完整、launcher 可执行、SKILL.md 可读，
但「Harness 运行时实际发现」需要独立会话证据，我拿不出，也不编。

## 十一、给人看的操作

```
初始化：  sourcelore analyze /path/to/repo
列表：    sourcelore repositories
概览：    sourcelore inspect <repository_id>
README：  sourcelore query <rid> --commit <sha> --type content --path README.md
源码：    sourcelore query <rid> --commit <sha> --type code --path <file>
Alia：    sourcelore query <rid> --commit <sha> --type relation --path <file>
项目：    sourcelore query <rid> --commit <sha> --type project
卡片：    sourcelore card --repository-id <rid> --commit <sha> --path README.md
```

用户不需要理解 asset_id / verification_id / blob_oid。那些只在需要追溯证据时再看。

## 十二、还没到产品标准

- 真实 GitHub 采集走不通（外部限流）。
- 自然语言触发没有独立会话证据。
- 本地仓库入口只读 Git 对象，不读工作区未提交内容。
- 卡片是单文件 HTML，没有导航目录。
- `inspect` 的概览字段仍偏技术化。
