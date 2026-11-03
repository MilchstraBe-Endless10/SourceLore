# F1-B / Evidence-Claims 批次 · 检查点（已完成并提交）

## 做到哪

**本批已 DONE 并提交 `9e0f5ae`。** 三个验证器全绿。下一个批次是 Product。

### 交付物（全部已入库）

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1b_ec_def.py` | 9 条 canonical 定义 + `CONSUMED_THIS_BATCH`（12 个身份承接声明） |
| `tools/fusion/f1b_build_ec.py` | 增量构建器，幂等，写入延后到校验通过 |
| `tools/fusion/f1b_verify_ec.py` | 50 条独立检查，只写 `F1B_EC_VERIFICATION.json` |
| `docs/fusion/F1B_EVIDENCE_CLAIMS_DECISIONS.md` | 设计裁决，第 E 节六项约束逐条落章 |
| `docs/fusion/F1B_EC_VERIFICATION.json` | 机读验收证据 |
| `tools/fusion/f1b_stats.py` | 已登记 `Evidence-Claims` 到 `_MODULE_DEFS` 与 `BATCH_NAMES` |

### 实测数字（磁盘实算，非声明）

- 本批承接 12 个身份、合成 9 条 canonical（`SL-CAP-0020`…`0028`）、出向分流 0
- 累计：MAPPED 34 / ROUTED 5 / UNREVIEWED 104 = 143，canonical 28
- 批次视图：Facts 11/1、Collector 11/4、EC 12/0（出向按契约现算，下游承接后自然递减）
- 晋升记录 14 条全在盘

### 验证

```
python3 tools/fusion/f1b_verify.py            → 12/12 PASS
python3 tools/fusion/f1b_verify_collector.py  → 30/30 PASS
python3 tools/fusion/f1b_verify_ec.py         → 50/50 PASS
```

重建链（幂等，已实测重复运行结果一致）：`f1b_build_collector.py` → `f1b_build_ec.py` → 三个验证器。
`f1b_build_facts.py` 有防误跑闸，草稿含其它模块条目时 exit 2 不写盘，所以整表重建不能从 Facts 起。

## 本批核心裁决

**显式拒绝「不可验证即判否」。** 上游 U06::C06 原文是 can't prove → FALSE_POSITIVE，
把「说不清」直接归入否定。本批取其「必须给悬置一个确定去向」的取向，把去向改为
`insufficient_evidence`，并写成硬规则：不可验证只产生 insufficient_evidence，禁止落成 refuted；
无法证明不等于已被证伪。U06::C06 判 ADAPT，拒绝语义记入 `merge_note` 与决策文档。

## 本批踩的坑（下一批别再踩）

1. **验证器基线写死会假阳性。** Facts c10 断言「全局无人引用 C03/C10」，EC 一批就红；
   Facts c11 拿当前全局数去卡历史文档，每推进一批必然不等；Collector c27 用 Collector 的引用集
   去卡其它批次的晋升。三处都已收窄作用域。判据收窄不降强度，只是去掉「历史必须等于现在」。
2. **批次出向分流是现算视图，不是定格历史。** 下游承接后数字会减（Facts 9→1、Collector 5→4）。
   校验只能查「与现算自洽」，不能查「等于上一批的旧值」。mapped 才是定格的（11/11/12）。
3. **`from` 字段必须与磁盘事实核对。** U06::C07 起初被我误标 `cross_module_redirections`，
   实际它不在路由表里（是未审命中），构建器的复核断言直接抓出来了。声明来自哪，磁盘得有证据。
4. **多行 `return (a,` + `b)` 一旦括号错位就是语法灾难。** 本批连改三轮才把 6 处补齐。
   写法改成先算 `detail` 变量再 `return cond, detail`，不再跨行元组。
5. **验证器 `check()` 只接受返回 `(ok, detail)` 的函数。** 返回单值会 TypeError——
   本批第一轮 7 条 FAIL 里有 6 条是这个，不是数据问题。

## 下一步

**F1-B 下一批：Product。** 候选已定向：`U03::C01`（边界三分类）、`U03::C06`（产品八要素）。
流程照本批：检索候选 → 归并 → 裁决 → def → 幂等构建器 → 独立验证器 → 决策文档 → 进度记录 → 独立提交。
新 ID 从 `SL-CAP-0029` 起。

其余待办批次：Research → Lifecycle → Security → Renderer → Storage → DSH-Adapter。
F1-C（十项冲突裁决）、F1-D（全量验收与 `CAPABILITY_CROSSWALK.json` 冻结）仍未启动。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -3 && git status --short \
  && python3 tools/fusion/f1b_verify_ec.py | tail -2
```

检索词：F1B EC batch checkpoint（本文件为完成版）。
