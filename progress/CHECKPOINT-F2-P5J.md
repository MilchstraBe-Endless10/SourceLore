# F2-P5J 检查点 · 基线 9433e43 · Crosswalk 已复算匹配

## 已完成
```
src/source_analysis/ts_project_models.py      项目/引用/归属模型 + 状态常量
src/source_analysis/ts_file_membership.py     files/include/exclude 语义
src/source_analysis/ts_project_references.py  references 解析 + 图 + 循环检测
src/source_analysis/ts_project_context.py     发现 + 归属 + 上下文选择
src/content_persistence/ts_project_ingest.py  三类事实入库
src/content_persistence/ts_project_adapter.py 裁决（17 状态全合法码）
src/content_persistence/ts_project_query.py   只读查询
src/renderer/ts_project_card_models.py        三型卡片模型
src/renderer/ts_project_card_renderer.py      卡片渲染
src/skill_interface/ts_project_knowledge.py   CLI 入口
```

## 已修的 P5I 语义缺口（本轮前置任务）
**Node 条件顺序**：原实现把「多个条件同时可用」一律判 MULTIPLE_CONDITIONS_AVAILABLE。
按 Node 规范，条件是**按配置对象键顺序**匹配，`default` 始终匹配。
已重写 `expand_condition`：按键遍历，首个命中且可解析者胜出；
`default` 不因在前而跳过；命中但解析不出则继续下一个；null 立即阻断。

实测：
```
default在前 {default,import} + import可用 → ./f.js（default 先命中）
default在后 {import,default} + import可用 → ./esm.js
多条件同时可用 {import,node,require} → 按顺序取 import
```

## 关键语义
- `files: []` **不触发默认扫描**（显式空数组 = 无输入文件）
- `exclude` 只过滤 include，不是绝对排除
- `files` 优先于 include，且不受 exclude 影响
- references 只读**本配置自己的**顶层字段，**不随 extends 继承**
- 项目身份 = repo+commit+config_path+blob_oid+digest，不用目录名
- 17 个状态映射全部合法 EC 码

## 待做
1. tests/ts_projects/ 三层测试 + 40 项 Gold
2. E2E（solution-style / monorepo / 多项目 / 双 Commit）
3. 全量回归 + 文档 + 提交
