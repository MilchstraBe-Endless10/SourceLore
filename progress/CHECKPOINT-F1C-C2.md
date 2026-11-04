# F1-C-C2 检查点（已完成）

## 做到哪

**F1-C-C2 DONE。** U05 剩余 10 项全部终裁：8 承接、2 REJECT、0 新增 canonical。
F1-C 总体仍 IN_PROGRESS。

## 关键事实

**U05 未审是 10 项不是 11。** 汇报稿的 11 是上一轮抄写错误；
基线文件自 F1-C-A 起记录的就是这 10 项（C07/C08/C12/C13/C15/C16/C21/C25/C27/C28）。

## 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1c_c2_decisions.py` | 10 项裁决数据 |
| `tools/fusion/f1c_c2_verify.py` | 18 条独立验收 |
| `tools/fusion/f1c_history_verify.py` | **新增**：独立全局历史验证入口（F1-D 可直接调用） |
| `docs/fusion/F1C_C2_U05_DECISIONS.md` | 裁决详述 |
| `docs/fusion/F1C_C2_U05_RECONCILIATION.json` | 清算记录 |
| `docs/fusion/F1C_HISTORY_VERIFICATION.json` | 全局历史验证证据 |

## 数字

MAPPED 131 / ROUTED 0 / UNREVIEWED 12 = 143，canonical 75（**本批无新增**）。

## ★ 三个最容易判错的点

1. **C21 四类冲突不合并**：Claim 冲突→EC、历史与当前→Lifecycle、并发写入→Storage、人工与生成→Renderer。
2. **C13 采纳 C4 的粒度降序、拒绝其强制产出机制**（与 SL-CAP-0057 同源）。
3. **C25 覆盖率四条禁令**：覆盖率≠正确性、存在≠通过、通过≠全验证、上游有测试≠已验证。

## ★ 踩的坑

1. **检查器字段混淆**（真缺陷）：`upstream_disposition`（上游原始处置，不得改）
   vs `verdict`（SourceLore 自己的裁定，可不同）。拿一个去要求另一个会误报。
   **教训：语义不同的字段必须先分清再写检查。**
2. **历史文档 vs 当前值**：lifecycle c38 用当前 mapped(15) 去要求历史文档（记的是 12）。
   文档是快照，断言必须按历史值。
3. **断言格式不一致**：文档写 `C07`，断言查 `U05::C07`。

## 下一步：F1-C-C3

剩余 12 项 UNREVIEWED（U05 的 C27/C28 已裁、等迁移），实际待处理 10 项：
- U01/U02：0 项
- **U03 × 4**（C23/C24/C25/C26，全 REJECT 且同源）→ 建议成组以反例约束方式处理
- **U04 × 5**（C05/C06/C13/C21/C27）
- **U06 × 1**（C21 模型分层 REJECT）

★ **最易判错**：U04-C21（报告间判断差异，Research 层）≠ U05-C21（Claim 间证据冲突，EC 层）。
同名不同义，必须分开裁。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1c_c2_verify.py | tail -2 \
  && python3 tools/fusion/f1c_history_verify.py | tail -2
```

检索词：F1C-C2 checkpoint。
