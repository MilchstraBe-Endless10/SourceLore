# F2-P5I 检查点 · 基线 11cbb26 · Crosswalk 已复算匹配

## 已完成模块
```
src/source_analysis/tsconfig_jsonc.py            JSONC 状态机（非正则）
src/source_analysis/module_config_models.py      Config/Resolution 模型 + 状态常量
src/source_analysis/tsconfig_parser.py           抽取 compilerOptions/paths/extends
src/source_analysis/tsconfig_effective_config.py paths 优先级 + extends 继承
src/source_analysis/package_module_map_parser.py imports/exports + 条件展开
src/source_analysis/config_aware_resolver.py     配置感知解析（三层状态）
src/content_persistence/module_relation_ingest.py  Config Fact + Relation Fact 入库
src/content_persistence/module_relation_adapter.py 裁决（EC 封闭码）
src/content_persistence/module_relation_query.py   只读查询
src/renderer/module_relation_card_models.py        关系卡片模型
src/renderer/module_relation_card_renderer.py      关系卡片 HTML
```
tests/module_resolution/ 83 项全绿。

## 已修真缺陷
1. **default 条件被当普通条件**：`k in available_conditions` 直接拦住 `default`，
   导致「仅 some default」时永不解析。改为循环外先记 default_entry 作兜底。
2. **package exports/imports 通配目标未展开**：`./src/feat/*.js` 里的 `*` 未替换，
   导致 TARGET_NOT_IN_TREE 误判。加 `_subpath_capture` 传入 capture。
3. **测试数据不自洽**：exports 目标相对 package.json 目录（仓库根），测试却放在 src/ 下。

## 关键语义确认
- paths 优先级：**精确 > 通配（前缀越长越优先）> `*` 兜底**，不是配置出现顺序
- `baseUrl` 缺失 → 基准是**配置目录**，绝不默认项目根
- extends 只支持本地同 Commit；npm 包/绝对路径 → `CONFIG_INHERITANCE_UNRESOLVED`
- `exports` 未列出子路径 → `SUBPATH_NOT_IN_EXPORTS`，**不据文件存在而放行**
- `null` 目标 → `EXPORT_EXPLICITLY_BLOCKED`
- 多条件同时可用 → `MULTIPLE_CONDITIONS_AVAILABLE`，**不任选**
- 16 个 EC reason_code 全部合法（D-17 不复现）

## 待做
1. 存储集成测试 + 45 项 Gold
2. 三层 E2E（安装版 CLI）
3. 全量回归 + 文档 + 提交
