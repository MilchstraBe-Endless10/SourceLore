# F1-C-A 检查点（已完成）

## 做到哪

**F1-C-A DONE。** 两项归属争议已裁（均保持原判），31 项遗留基线已现算，终态模型建议已提出。
**F1-C 总体仍 IN_PROGRESS。**

## 交付物

| 文件 | 作用 |
|---|---|
| `docs/fusion/F1C_DECISION_REGISTER.json` | 裁决登记表，F1-C 全批次共用（不得每轮重建为不兼容格式） |
| `docs/fusion/F1C_A_OWNERSHIP_DECISIONS.md` | 本批裁决详述 + 终态模型预审 |
| `docs/fusion/F1C_REMAINDER_BASELINE.json` | 31 项遗留身份现算基线 |
| `docs/fusion/F1C_A_VERIFICATION.json` | 机读验收证据 |
| `tools/fusion/f1c_a_baseline.py` | 只读基线计算（不重跑 F1-B 构建器） |
| `tools/fusion/f1c_a_verify.py` | 16 条独立验收 |

## 两项裁决

| decision_id | 对象 | 结论 | 是否落地 |
|---|---|---|---|
| F1C-A-001 | `U06::C25` | 唯一 owner = **Storage**（保持） | 无迁移（原判如此） |
| F1C-A-002 | `SL-CAP-0009` | 唯一 owner = **Facts**（保持） | 无迁移（原判如此） |

两项都登记 `decision_state = adjudicated`，`applied_changes_this_batch = []`（机检 `git diff` 确认 Crosswalk 逐字节未改）。

## 实测数字

- 143 原始 / 112 MAPPED / 11 ROUTED / 20 UNREVIEWED / 31 遗留 / 73 canonical
- ROUTED 分布：EC 5、Lifecycle 4、Renderer 4、Storage 1 —— **模块都完成了，身份都没被承接**
- UNREVIEWED 分组：分析与评估 4、研究报告 2、知识页面与质量门 3、知识库维护流程 11
- 待裁 REJECT 8 项，全部在 31 项内；另 13 项 REJECT 已绑 canonical

## 验证（全部 exit 0）

`f1c_a_verify.py` 16/16；十个 F1-B 验证器 12/30/50/43/46/48/53/48/54/56 全绿；基线重跑逐项一致。

## 本批踩的坑（★ 下一批必须注意）

**★ 元组换行写法，同一批摔了四次。**
错误写法：
```python
return (cond),
    f"detail..."     # ← 这是单元素元组，不是二元组
```
正确写法：
```python
detail = (f"...")
return (cond), detail
```
报错表现：`ValueError: not enough values to unpack (expected 2, got 1)`。
上一批已经记录过这条，本批又犯 —— **说明它该写进验证器生成模板，不能只靠记性。**

**断言措辞仍要与文档字面一致**（本批 c15「保持 Storage」vs 文档「唯一建议 owner：Storage」）。

## 下一步：F1-C-B

按依赖顺序：
1. 处理 11 项 ROUTED 的「已完成未承接」——逐条二选一：建卡承接 / 改判去向
2. 先定 `U06-C25` 的承接形态（Storage 已定，但未落 canonical；`SL-CAP-0062` 未覆盖其具体契约）
3. 按语义组处理 20 项 UNREVIEWED（建议从 U05 系 11 项开始，量大且集中）
4. 8 项待裁 REJECT 逐条定性
5. 十项冲突裁决（F1 原定任务）
6. 实施终态模型扩展（正交 `terminal_disposition` 字段）+ 配套验证器

**终态模型建议（本批只提出未实施）**：
```
state（不变）:            MAPPED | ROUTED | UNREVIEWED
terminal_disposition:     ADOPTED | ADOPTED_AS_COUNTEREXAMPLE |
                          REJECTED_WITH_REASON | DEFERRED_WITH_REASON |
                          INTERNAL_DESIGN_ONLY
```
两轴正交，`state` 守恒仍按 143，十个既有验证器读 `state` 的断言不受影响。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1c_a_verify.py | tail -2 \
  && python3 -c "import json;d=json.load(open('docs/fusion/F1C_REMAINDER_BASELINE.json'));print(d['totals'])"
```

检索词：F1C-A checkpoint。
