# F1-B 全部十批次完成 · 检查点

## 做到哪

**F1-B 十个模块批次全部 DONE。** 十验证器全绿，幂等已验证。
**但 143 项原始能力未全部完成归属裁决**——剩余量与分类见 `docs/fusion/F1B_REMAINDER_INVENTORY.json`。

### 十批次一览

| 批次 | canonical | mapped | redirected | 验证器 |
|---|---|---|---|---|
| Facts | 10 (0001–0010) | 11 | 1 | 12/12 |
| Collector | 9 (0011–0019) | 11 | 4 | 30/30 |
| Evidence-Claims | 9 (0020–0028) | 12 | 1 | 50/50 |
| Product | 6 (0029–0034) | 10 | 1 | 43/43 |
| Research | 5 (0035–0039) | 10 | 1 | 46/46 |
| Lifecycle | 6 (0040–0045) | 12 | 4 | 48/48 |
| Security | 9 (0046–0054) | 17 | 3 | 53/53 |
| Renderer | 7 (0055–0061) | 11 | 2 | 48/48 |
| Storage | 6 (0062–0067) | 11 | 2 | 54/54 |
| DSH-Adapter | 6 (0068–0073) | 7 | 1 | 56/56 |

**合计**：73 canonical、MAPPED 112、ROUTED 11、UNREVIEWED 20 = 143。

### 验证（全部 exit 0）

```
f1b_verify.py 12/12 · collector 30/30 · ec 50/50 · product 43/43 · research 46/46
lifecycle 48/48 · security 53/53 · renderer 48/48 · storage 54/54 · dsh_adapter 56/56
```

### 构建链（幂等，正确顺序）

```bash
python3 tools/fusion/f1b_build_collector.py     # Facts 构建器有防误跑闸，不能重跑
python3 tools/fusion/f1b_build_ec.py
python3 tools/fusion/f1b_build_product.py
python3 tools/fusion/f1b_build_research.py
python3 tools/fusion/f1b_build_lifecycle.py
python3 tools/fusion/f1b_build_security.py
python3 tools/fusion/f1b_build_renderer.py
python3 tools/fusion/f1b_build_storage.py
python3 tools/fusion/f1b_build_dsh_adapter.py
python3 tools/fusion/f1b_build_remainder.py    # 生成剩余清单
```

## 剩余待裁决（F1-C 的实质内容）

| 类别 | 数量 | 说明 |
|---|---|---|
| UNREVIEWED | 20 | 分 4 个语义组：分析与评估 / 研究报告与外部资料 / 知识页面与质量门 / 知识库维护流程 |
| ROUTED 未承接 | 11 | 涉 4 个模块，**目标模块已完成但没建卡承接**——要么承接、要么改判 |
| REJECT 待裁 | 8 | 未 MAPPED 的 REJECT 项，需逐条确认是「已裁决」还是「待 F1-C」 |
| 归属争议 | 2 | `U06-C25`（Storage vs EC）、`SL-CAP-0009`（Facts vs Storage） |

**核心立场：不得为了让统计变成 143/0/0 而人为制造 canonical。**

## 十批次踩过的通用坑（规律已成型）

1. **★ 既有验证器每推进一批就会报红。** 三类标准修法：
   - 出向计数：改为「与现算自洽」，不要求等于旧值
   - 分流去向：改为「要么仍在路由表且正确，要么已被预期目标承接（有晋升记录）」
   - 「指向自身」：只查本批 def 自己声明的那批，不全局禁止
2. **★ def 引用已归他模块的身份 = 二次映射。** 起草前先跑占用检查，别凭印象。
3. **★ 不得擅自改前批 canonical 归属。** 保留原判 + 登记 F1-C，不逐批就地覆盖。
4. **★ 被撤出的条目必须从草稿基线快照重来。** 只改 def 重跑，旧记录会残留。
5. **★ 断言措辞必须与 def 字面一致。** 差一个字就误红；写断言前先 grep。
6. **★ 模块名写法要统一。** `BATCH_ORDER` 用空格而 def 用连字符会让批次排序错误。
7. 多行 `return (a,` 元组是语法雷区，先算 `detail` 再 return。
8. Python 字符串里混入字面换行或多余引号会直接语法崩，notes 一律单行拼接。

## 下一步

**F1-C 未启动，需 Owner 明确批准。** 最小可执行起点：

1. 裁 2 处已知归属争议
2. 按 4 个语义组处理 20 项 UNREVIEWED
3. 处理 11 项 ROUTED 的「已完成未承接」
4. 十项冲突裁决（F1 原定任务）
5. 8 项待裁 REJECT

F1-D（全量验收 + `CAPABILITY_CROSSWALK.json` 冻结）在 F1-C 之后。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -3 && git status --short \
  && python3 tools/fusion/f1b_verify_dsh_adapter.py | tail -2 \
  && python3 -c "import json;print(json.load(open('docs/fusion/F1B_REMAINDER_INVENTORY.json'))['state_totals'])"
```

检索词：F1B complete checkpoint。
