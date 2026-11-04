# F1-C-D1 检查点（已完成）

## 做到哪

**F1-C-D1 DONE。** 143 项原始能力全部有可机读终态，与三态进度正交。
三态未变（139/0/4），canonical 未变（75）。

## 三个正交概念

| 概念 | 字段 | 分布 |
|---|---|---|
| 进度 | `mapping_status` | MAPPED 139 / ROUTED 0 / UNREVIEWED 4 |
| 终态 | `terminal_disposition` | ADOPTED 122 / ADOPTED_AS_COUNTEREXAMPLE 17 / REJECTED_WITH_REASON 4 / DEFERRED 0 |
| 来源 | `canonical_origin_type` | UPSTREAM_DERIVED 68 / INTERNAL_DESIGN_ONLY 7 |

## ★ 核心结构决定

**终态推导并入应用链**（`f1c_terminal_model.derive`，由 `f1c_apply_routed.py` 写盘前调用）。
初版作为独立后置步骤，被任何验证器的幂等检查冲掉。这是架构错，不是验证器的错。

## ★ 概念纠正

`INTERNAL_DESIGN_ONLY` 是 **canonical 来源性质**，不是上游身份终态。前轮草案误置，本批已纠正。
上游身份终态只有四值。

## 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1c_terminal_model.py` | 终态推导纯函数（应用链调用） |
| `tools/fusion/f1c_d1_migrate_terminal.py` | 薄封装：跑应用链 + 导出快照 |
| `tools/fusion/f1c_d1_verify.py` | 19 条独立验收 |
| `docs/fusion/F1C_D1_TERMINAL_MODEL.md` | 终态模型说明 |
| `docs/fusion/F1C_D1_TERMINAL_MIGRATION.json` | 迁移快照 |

## ★★ 踩的坑：正则跨函数误伤（严重）

`re.search` 匹配多行块批量改写时，正则吞掉整个后续函数体，
删掉了 `f1c_b` 的 c1 和 `f1c_c2/c3` 的 c10。
**git checkout 回滚 + 改用唯一定位旧串/按行号精确替换。**

教训：跨多行正则改函数体是危险的。能按行号就别用正则；
改完必须检查函数数量与重复定义。

## 下一步：F1-C-D2

1. 8 项待议跨模块冲突
2. `U06-C13` / `U02-C17` 反向个案复审
3. 21 项反例绑定的许可证核验

零来源审查留 D3；交叉表冻结留 F1-D。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1c_d1_verify.py | tail -2
```

检索词：F1C-D1 checkpoint。
