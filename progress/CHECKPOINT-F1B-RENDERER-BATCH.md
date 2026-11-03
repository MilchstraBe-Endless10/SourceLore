# F1-B / Renderer 批次 · 检查点（已完成）

## 做到哪

**本批已 DONE。** 八个验证器全绿，幂等已验证。下一个批次是 Storage。

### 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1b_renderer_def.py` | 7 条 canonical（0055–0061）+ 11 承接 + 2 分流 |
| `tools/fusion/f1b_build_renderer.py` | 增量构建器，幂等 |
| `tools/fusion/f1b_verify_renderer.py` | 48 条独立检查 |
| `docs/fusion/F1B_RENDERER_DECISIONS.md` | Markdown 八问 D-A..D-H + 跨模块 K-1..K-8 |
| `docs/fusion/F1B_RENDERER_VERIFICATION.json` | 机读验收证据 |
| `tools/fusion/f1b_stats.py` | 已登记 `Renderer` |

### 实测数字

- 承接 11 个身份（含 3 条 ROUTED）、7 条 canonical、外推 2 条（U04-C16、U05-C10 → Lifecycle）
- 累计：MAPPED 94 / ROUTED 13 / UNREVIEWED 36 = 143，canonical 61
- 批次：Facts 11/1、Collector 11/4、EC 12/0、Product 10/1、Research 10/2、
  Lifecycle 12/4、Security 17/5、Renderer 11/2
- 晋升 26 条、分流 13 条零重复、幽灵晋升 0

### 验证（实际退出码，全 0）

```
12/12 · 30/30 · 50/50 · 43/43 · 46/46 · 48/48 · 53/53 · 48/48
```

## 核心裁决

1. 四类视图共享同一事实源，同一事实不得出现不同数值
2. 卡片不是 Claim 的第二份权威副本
3. 九节结构不得成全局模板
4. 拒绝强制出图，保留可选图表；无法提取关系时不生成假图
5. 生成完成 ≠ 脱敏通过 ≠ 发布授权；G-3 只能由人触发
6. 有引用不等于支持；facts_only 不得冒充完整报告；不得提级

## 本批踩的坑

1. **★ def 引用已归他模块的身份 = 二次映射。** 本批 `SL-CAP-0055` 初版踩了一次
   （`U02-C13` 已归 Research 的 0038）。**下一批起草 def 前先跑一遍占用检查**，
   别只靠记忆判断「这条好像没人要」。
2. **验证器断言措辞必须与 def 字面一致。** 差一个字就误红（本批 c28 踩了）。
   写断言前先 `grep` def 里的实际措辞，或先打印 blob 再写。
3. **既有验证器每批必红**，本批是 Research c15/c45 + Lifecycle c47。
   固定修法：出向改为与现算自洽、分流去向改为「要么在路由表、要么已被预期目标承接」、
   「指向自身」只查本批自己声明的那批。
4. **容器表达式的笔误很难看出来。** `("X","Y").__class__ and (...)` 语法合法但不合意图，
   靠自检脚本（refs vs declared 集合对比）才发现。

## 下一步

**F1-B 下一批：Storage。** 已定向候选：
`U04-C03`（索引是派生视图）、`U04-C22`（并发写入保护）、`U04-C23`（结构化查询）、
`U06-C19`（多仓库拓扑，Security 已分流指向 Storage）、
`U06-C25`（三态产物契约，同）、`U05-C09`（PKB_ROOT 与项目分离）。
另可核 `U04-C25`（仓库内 corpus 部署模型，已 REJECT 可否作反例）、`U05-C26`。

新 ID 从 `SL-CAP-0062` 起。余 DSH-Adapter。F1-C、F1-D 未启动。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -3 && git status --short \
  && python3 tools/fusion/f1b_verify_renderer.py | tail -2
```

检索词：F1B Renderer batch checkpoint。
