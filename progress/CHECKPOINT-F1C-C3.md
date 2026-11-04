# F1-C-C3 检查点（已完成）

## 做到哪

**F1-C-C3 DONE。** 剩余 10 项全部终裁。**143 项原始能力至此全部有终裁。**
F1-C 子批次完成，剩 F1-C-D 收口。

## 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1c_c3_decisions.py` | 10 项裁决数据（含逐项分项回答） |
| `tools/fusion/f1c_c3_verify.py` | 19 条独立验收 |
| `tools/fusion/f1c_d_handoff.py` | F1-C-D 待办清单生成器（现算） |
| `docs/fusion/F1C_C3_REMAINING_DECISIONS.md` | 裁决详述 |
| `docs/fusion/F1C_C3_RECONCILIATION.json` | 清算记录 |
| `docs/fusion/F1C_D_HANDOFF_INVENTORY.json` | F1-C-D 全局待收口清单 |

## 数字

MAPPED 139 / ROUTED 0 / UNREVIEWED 4 = 143，canonical 75（**本批无新增**）。

4 项 UNREVIEWED 全部是已裁 REJECT：U04-C27、U05-C27、U05-C28、U06-C21。

## ★ 本批最重要的边界判定

**U04-C21（报告间解释分歧，Research/0038）≠ U05-C21（Claim 间证据矛盾，EC/0028）。**
前者可能两者都对（视角不同），后者必有一方错。两者不得合并，也不得建第二套状态机。

## ★ 三条 REJECT 的区别（不要批量同一句）

- C23 拒「五档机械排序」（不成全序 + 允许任意层级 → 自我消解）
- C24 拒「强制单一图示语法 + 无校验」
- C25 拒「禁止使用确定性设施」这条自我设限（**Facts 要用 AST、Storage 要用索引**）
- C26 拒「无条件逐术语建页」

## ★ 踩的坑

1. **def 语法两处**：`)` 误写成 `],`、多余括号。写完必跑 `ast.parse`。
2. **验证器断言查错关键词**：理由写「绑死 Claude 家族」，断言查「供应商」。
   **教训：断言要查语义存在而非某个预想词。**
3. **函数内引用了函数外的变量**（c15 的 `unrev`）。

## 下一步：F1-C-D

清单：`docs/fusion/F1C_D_HANDOFF_INVENTORY.json`
1. terminal_disposition 迁移（4 项 REJECT，正交字段不改 state）
2. 8 项待议跨模块冲突
3. 7 条零来源 canonical 归档
4. 17 条反例绑定 + 2 条 U06 无许可引用复核
5. 冻结前复跑历史验证

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1c_c3_verify.py | tail -2
```

检索词：F1C-C3 checkpoint。
