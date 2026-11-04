# F1-C-D2 检查点（已完成）

## 做到哪

**F1-C-D2 DONE。** 八项跨模块架构冲突全部裁决：6 DESIGN_RESOLVED / 1 IMPLEMENTATION_DEPENDENCY / 1 BLOCKED。
**0 条 canonical amendment。**

## ★ 前提：八条编号出自三份文档，同名不同义

- X-2/4/5/6/7 ← `F1B_STORAGE_DECISIONS.md §11`
- K-7 ← `F1B_RENDERER_DECISIONS.md §10`
- Y-4/Y-6 ← `F1B_DSH_ADAPTER_DECISIONS.md §10`

**`F1B_LIFECYCLE_DECISIONS.md §9` 的 X-1…X-6 所指不同，本次未混用。**
教训：跨模块编号不能跨文档复用理解。

## 八项结论

| ID | 结论 |
|---|---|
| X-2 | repository_id ≠ Subject 主键；fork 独立；跨仓库同名不自动合并 |
| X-4 | B 是指针 A 是权威；last_known_good 降级；版本差异≠证伪；失败不伪装空 |
| X-5 | 契约已定，**事务未实测**（第二类） |
| X-6 | 不引入向量/图库 |
| X-7 | commit/branch 不共层，branch 不入路径 |
| K-7 | 默认禁止改人工文档；七项前置；标记≠授权 |
| Y-4 | 检查点=执行状态非知识；独立分区；任务恢复≠知识有效 |
| Y-6 | 五项 UNVERIFIED；`skills/sourcelore/` **实测 0 文件** |

## 交付物

`f1c_d2_decisions.py` / `f1c_d2_build.py` / `f1c_d2_verify.py`（22 条）
`F1C_D2_ARCHITECTURE_DECISIONS.md` / `F1C_D2_CONFLICT_RESOLUTIONS.json` /
`F1C_D2_F2_GATES.json`（30 门禁 + 6 探测）/ `F1C_D2_VERIFICATION.json`

## ★ 反例口径纠正

17 项绑定（17 边）+ 4 项无绑定拒绝身份 = 21 项角色。
**不能说成「21 项反例绑定」**——没有边就没有绑定。

## ★ 跑通的坑：断言把否定句当违规

四条断言误报，都是把「而不是把…写成『平台已支持』」这类**否定语境里的措辞**当成违规。
**修法：句级否定判据**（按 `。；\n，` 切句，同句含否定词则放过）。
固定字符窗口（12 字）不够用。
**教训：检查「不得出现某断言」，判据必须是「同句有无否定」，不是「附近有无关键词」。**

## 下一步：F1-C-D3

1. 21 项 counterexample 角色许可证总审（本批只核 2 项）
2. 7 条零来源 canonical 质量审查
3. U06 全部条目零复制复核
4. 冻结前一致性检查（冻结留 F1-D）

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1c_d2_verify.py | tail -2
```

检索词：F1C-D2 checkpoint。
