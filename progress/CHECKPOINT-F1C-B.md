# F1-C-B 检查点（已完成）

## 做到哪

**F1-C-B DONE。** 11 项 ROUTED 全部清算完毕，两处前置勘误已处理。F1-C 总体仍 IN_PROGRESS。

## 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1c_routed_decisions.py` | 11 项裁决数据 + 2 处勘误（纯数据） |
| `tools/fusion/f1c_apply_routed.py` | 确定性应用层：**从冻结基线重建**，可 `--dry-run` |
| `tools/fusion/f1c_b_routed_audit.py` | ROUTED 只读审计 → `F1C_B_ROUTED_AUDIT.json` |
| `tools/fusion/f1c_b_verify.py` | 20 条独立验收 |
| `docs/fusion/F1B_FROZEN_BASELINE.json` | F1-B 收官快照（`git show HEAD:` 导出） |
| `docs/fusion/F1C_B_ROUTED_DECISIONS.md` | 逐项裁决详述 |
| `docs/fusion/F1C_B_ROUTED_RECONCILIATION.json` | 应用记录 + 勘误 |

## 关键数字

MAPPED 120 / ROUTED 3 / UNREVIEWED 20 = 143，canonical 74。

## ★ 本批最重要的一条工程原则

**应用层从基线重建，不在草稿上打补丁。**
`f1c_apply_routed.py` 每次都读 `F1B_FROZEN_BASELINE.json` + 裁决数据 → 全量重算。
因此撤销/修改裁决后重跑**不会残留历史路由**。这直接解决了 F1-B 时代的老问题
（「改 def 重跑，已落盘的旧分流还在」）。

## ★ 踩的坑（必须记住）

1. **元组换行写法，本批又踩 5 次。** `return (expr),` 换行接字符串 = 单元素元组 →
   `ValueError: not enough values to unpack`。**固定写法：先算 `detail = (...)` 再 `return (cond), detail`。**
   已在验证器写完时跑正则自检：`re.findall(r'return \([^\n]+\),\n\s+[f(]', src)` 应为 0。
2. **应用层漏同步 PROGRESS** → 所有验证器「进度同源」全红。写跨文件应用层时必须列全要更新的文件。
3. **历史验证器作用域**：mapped 定格要 `>=` 不是 `==`；canonical_ids 要「本批全在」不是「完全相等」；
   分流去向要三分支（仍在表 / 已被承接 / 已待裁）。

## 下一步：F1-C-C

1. **先裁 3 项 DEFER 的 owner**——不裁就定不了承接形态
2. 20 项 UNREVIEWED（建议从 U05 系 11 项起）
3. 8 项待裁 REJECT 定性
4. 十项冲突裁决
5. （F1-C-D）`terminal_disposition` 正交字段 + 交叉表冻结

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1c_b_verify.py | tail -2
```

检索词：F1C-B checkpoint。
