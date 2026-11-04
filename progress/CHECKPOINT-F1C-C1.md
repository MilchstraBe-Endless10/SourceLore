# F1-C-C1 检查点（已完成）

## 做到哪

**F1-C-C1 DONE。** 3 项 DEFER 全部终裁，ROUTED 归零。F1-C 总体仍 IN_PROGRESS。

## 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1c_c1_decisions.py` | 3 项裁决数据（含逐项证据化分项回答） |
| `tools/fusion/f1c_c1_verify.py` | 15 条独立验收 |
| `tools/fusion/f1c_history_invariants.py` | **新增**：历史不变量集合级三项检查 |
| `docs/fusion/F1C_C1_DEFER_RESOLUTION.md` | 裁决详述 |
| `docs/fusion/F1C_C1_RESOLUTION.json` | 清算记录 |
| `docs/fusion/F1C_C1_VERIFICATION.json` | 机读验收证据 |

## 三项裁决

| 身份 | 旧 → 新 owner | 承接 |
|---|---|---|
| U04-C16 | Lifecycle → **DSH-Adapter** | SL-CAP-0071 + G-1..G-3 |
| U05-C10 | Lifecycle → **Storage** | SL-CAP-0064 + W-2' |
| U01-C12 | EC → **EC（新建）** | SL-CAP-0075 |

## 数字

MAPPED 123 / ROUTED 0 / UNREVIEWED 20 = 143，canonical 75。

## ★ 本批最重要的一条判据区分

**C16 判「任务做完没」→ DSH-Adapter；C10 判「写对了没」→ Storage。**
两者是不同层的退出条件。把这两件事混为一谈是最容易犯的错。

另一条：**拒绝付费 API / 多模型 judge ≠ 拒绝离线基准评测。**
SL-CAP-0075 的 V1 完全离线、零外部依赖。

## ★ 踩的坑

1. **历史不变量检查器初版有设计缺陷**：把「canonical 上已存在 amendment」
   当成本批新增，误判 F1-C-B 留下的。正确做法：只校验该 recon 自己声明的 AMEND 目标。
   **教训：写「谁负责哪部分」的检查时，边界必须先定义清楚。**
2. **批次标记前缀重复**：`f"F1-{BATCH}"` 而 BATCH 已含 `F1-`。拼接前先看常量本身带不带前缀。
3. **元组换行**（老问题，本批未再犯）：先算 detail 再 return。

## 下一步：F1-C-C2（U05 系 11 项 UNREVIEWED）

已覆盖不重复：U05-C18→0062、C22/C23→0064/0065、C04/C14/C19→已处理。
待处理重点：C12、C13、C15、C16、C21、C25。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1c_c1_verify.py | tail -2
```

检索词：F1C-C1 checkpoint。
