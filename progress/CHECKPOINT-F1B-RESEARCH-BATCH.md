# F1-B / Research 批次 · 检查点（已完成）

## 做到哪

**本批已 DONE。** 五个验证器全绿，幂等已验证。下一个批次是 Lifecycle。

### 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1b_research_def.py` | 5 条 canonical（0035–0039）+ 10 条承接 + 3 条分流 |
| `tools/fusion/f1b_build_research.py` | 增量构建器，幂等，写入延后到校验通过 |
| `tools/fusion/f1b_verify_research.py` | 46 条独立检查 |
| `docs/fusion/F1B_RESEARCH_DECISIONS.md` | 冲突裁决 C-1..C-8 + 工程约束 R-A..R-G 逐条落章 |
| `docs/fusion/F1B_RESEARCH_VERIFICATION.json` | 机读验收证据 |
| `tools/fusion/f1b_stats.py` | 已登记 `Research` |

### 实测数字

- 承接 10 个身份、5 条 canonical（`SL-CAP-0035`…`0039`）、外推 3 条
- 累计：MAPPED 54 / ROUTED 9 / UNREVIEWED 80 = 143，canonical 39
- 批次：Facts 11/1、Collector 11/4、EC 12/0、Product 10/2、Research 10/3
- 晋升 19 条、分流 9 条零重复

### 验证（实际退出码）

```
f1b_verify.py            12/12 PASS (exit 0)
f1b_verify_collector.py  30/30 PASS (exit 0)
f1b_verify_ec.py         50/50 PASS (exit 0)
f1b_verify_product.py    43/43 PASS (exit 0)
f1b_verify_research.py   46/46 PASS (exit 0)
```

## 核心裁决

1. **来源类型不构成真伪排序**（U02-C12 降级为字段，不替代 EC 验证规则）
2. **阶段完成 ≠ 结论正确；资料读完 ≠ 研究完成**（R3 只产候选，R4 必须列剩余问题）
3. **partial/truncated/unavailable/empty 四态分列**，禁止把「没拿到」写成「没有」
4. **retrieved_at 与 verified_against_commit 不可互换**（F0 勘误 E-01 的同构延伸）

## 本批踩的坑

1. **★ 历史验证器的「当前值」判据会在下一批必然报红。** 本批一次触发五处：
   EC c49 数 owner=EC 的分流总数、Product c6 要求全局最大编号恒为 34、
   Product c29 拿当前全局数卡历史文档、Product c37 重跑历史构建器触发其编号保护、
   Product c38「重跑前后一致」对历史批次不适用。
   统一修法：历史批次判历史事实（自身编号连续、自身 mapped 定格、自身文档内快照自洽），
   当前全局状态由当前 Crosswalk 现算。核心不变量一条未放宽。
   下一批务必预期同样的五类，别再当成数据缺陷去查。
2. **正则 `\\n` 写在字符类里会退化成字面反斜杠 + n**（从 heredoc 转义而来）。
   需要跨行匹配时改用逐行扫描，别赌转义。
3. **def 的承接声明与 refs 必须逐键对齐。** U02-C15 在大表里但漏在 refs 里，
   构建器的一致性断言直接抓出——这个断言值得每批保留。
4. **多行 `return (a,` 元组仍是语法雷区。** 本批又踩两次，一律改写成先算 `detail`。

## 下一步

**F1-B 下一批：Lifecycle。** 已定向候选：
`U05-C17`（过期检测，Collector 已分流指向 Lifecycle）、`U04-C19`（知识失效检测）、
`U03-C08`（Rerun Protocol 九个触发点，Product 已分流指向 Lifecycle）、
`U06-C26`（新鲜度与失效判定）、`U02-*` 相关的长期维护语义。

新 ID 从 `SL-CAP-0040` 起。其余待办：Security → Renderer → Storage → DSH-Adapter。
F1-C、F1-D 仍未启动。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -3 && git status --short \
  && python3 tools/fusion/f1b_verify_research.py | tail -2
```

检索词：F1B Research batch checkpoint。
