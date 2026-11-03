# F1-B / Lifecycle 批次 · 检查点（已完成）

## 做到哪

**本批已 DONE。** 六个验证器全绿，幂等已验证。下一个批次是 Security。

### 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1b_lifecycle_def.py` | 6 条 canonical（0040–0045）+ 12 承接 + 5 分流 |
| `tools/fusion/f1b_build_lifecycle.py` | 增量构建器，幂等 |
| `tools/fusion/f1b_verify_lifecycle.py` | 48 条独立检查 |
| `docs/fusion/F1B_LIFECYCLE_DECISIONS.md` | Subject 六问 S-A..S-F + 跨模块 unresolved X-1..X-6 |
| `docs/fusion/F1B_LIFECYCLE_VERIFICATION.json` | 机读验收证据 |
| `tools/fusion/f1b_stats.py` | 已登记 `Lifecycle` |

### 实测数字

- 承接 12 个身份、6 条 canonical、外推 5 条
- 累计：MAPPED 66 / ROUTED 12 / UNREVIEWED 65 = 143，canonical 45
- 批次：Facts 11/1、Collector 11/4、EC 12/0、Product 10/1、Research 10/3、Lifecycle 12/5
- 晋升 21 条、分流 12 条零重复

### 验证（实际退出码，全 0）

```
f1b_verify.py 12/12 · collector 30/30 · ec 50/50 · product 43/43 · research 46/46 · lifecycle 48/48
```

## 核心裁决

1. **三轴正交**：任务执行 / 知识有效性 / Claim 验证，三轴互不替代
2. **旧结论对旧版本成立 ≠ 对新版本成立**（本批要防的核心错误）
3. **路径 A 与路径 B 不得合并**（已知依赖检测 vs 新事实发现）
4. **失效检测用内容哈希不用 mtime**；变化集不完整必须降级

## 本批踩的坑

1. **★ def 里引用已归属他模块的身份 = 同一身份二次映射。** SL-CAP-0045 起初引用了
   U04-C24/U05-C24（Research 已判给 EC）与 U06-C26（已归 SL-CAP-0042）。
   修法：零来源独立设计 + 在 notes 与决策文档里写清「为何不引用」。
   下一批起草 def 前，先 grep 草稿确认候选未被占用。
2. **Python 字符串里混入字面换行或多余双引号会直接语法崩。** 本批踩两次。
   notes 一律单行拼接；写完先 `python3 -c "import ast; ast.parse(...)"`。
3. **Product 验证器三处作用域过时**（c14/c38/c43），因本批承接了 `U03-C08`。
   已按「历史批次判历史事实」修正。这是每批必现的固定模式，下批直接预期。
4. **改验证器时要先看真实代码再写替换串。** 本批有一次正则定位失败导致整个 patch 未写入，
   白跑一轮。定位失败要 `sed -n` 看真身，别猜。

## 下一步

**F1-B 下一批：Security。** 已定向候选：
`U06-C18`（成本报告，Collector 分流指向 Security）、`U06-C24`（PR diff 增量审查，同）、
`U06-C04`（Boundary Gate）、`U06-C22`（OWASP LLM Top 10）、`U05-C20`（保密分级与脱敏，本批分流指向 Security）、
`U04-C17`（影响面调查，可考虑归 Security）。

新 ID 从 `SL-CAP-0046` 起。其余待办：Renderer → Storage → DSH-Adapter。
F1-C、F1-D 仍未启动。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -3 && git status --short \
  && python3 tools/fusion/f1b_verify_lifecycle.py | tail -2
```

检索词：F1B Lifecycle batch checkpoint。
