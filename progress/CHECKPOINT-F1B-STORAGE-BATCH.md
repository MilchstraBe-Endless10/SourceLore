# F1-B / Storage 批次 · 检查点（已完成）

## 做到哪

**本批已 DONE。** 九个验证器全绿，幂等已验证。下一批（最后一批）是 DSH-Adapter。

### 交付物

| 文件 | 作用 |
|---|---|
| `tools/fusion/f1b_storage_def.py` | 6 条 canonical（0062–0067）+ 11 承接 + 2 分流 |
| `tools/fusion/f1b_build_storage.py` | 增量构建器，幂等 |
| `tools/fusion/f1b_verify_storage.py` | 54 条独立检查 |
| `docs/fusion/F1B_STORAGE_DECISIONS.md` | 四层模型图 + M-A..M-H + X-1..X-7 |
| `docs/fusion/F1B_STORAGE_VERIFICATION.json` | 机读验收证据 |
| `tools/fusion/f1b_stats.py` | 已登记 `Storage` |

### 实测数字

- 承接 11 个身份（含 4 条 ROUTED）、6 条 canonical、外推 2 条（U05-C19→EC、U05-C14→Renderer）
- 累计：MAPPED 105 / ROUTED 11 / UNREVIEWED 27 = 143，canonical 67
- 批次：Facts 11/1、Collector 11/4、EC 12/0、Product 10/1、Research 10/1、
  Lifecycle 12/4、Security 17/4、Renderer 11/2、Storage 11/2

### 验证（实际退出码，全 0）

```
12/12 · 30/30 · 50/50 · 43/43 · 46/46 · 48/48 · 53/53 · 48/48 · 54/54
```

## 核心裁决

1. 四层读写权限分明，同一事实只有单一权威副本
2. 派生索引可整体删除重建，重建后查询等价
3. 六标识分列不可互替（repository_id/subject_id/commit_sha/root_tree_sha/evidence·claim_id/artifact_version）
4. 写入五步契约 + CAS，并发冲突显式返回
5. 多文件重命名不得宣称跨文件原子事务
6. 知识根目录不得位于被分析仓库内

## 本批踩的坑（下批务必注意）

1. **★ 不得擅自更改前一模块已提交的 canonical 归属。** 本批曾把 `U06-C25` 改判给 EC，
   违反第 11 节。正确做法：**保留原判 + 登记 F1-C 待裁决**。归属调整集中裁决，不逐批就地覆盖。
2. **★ 被撤出的条目必须从草稿基线重来。** 只改 def 再重跑构建器，已落盘的旧分流不会消失，
   会残留并污染后续验证。做法：构建前先 `cp` 快照，撤出条目后从快照恢复再重建。
3. **验证器断言措辞必须与 def 字面一致**（本批 c18/c23/c44 三处误红）。写断言前先 grep def。
4. **既有验证器每批也可能因「归属变化」而红**，不只是时间作用域。Security c50 就是例子——
   需区分「合法的职责裁决」与「擅自改归属」。

## 下一步

**F1-B 最后一模块：DSH-Adapter。** 候选：
`U01-C06`（LLM provider 解耦 Protocol）、`U01-C07`（单次调用 + 有界修复）、
`U01-C11`（prompt 资产即 markdown 知识）、`U01-C12`（eval baseline）、
`U01-C13`（直连外部 LLM API，REJECT）、`U01-C14`（多模型 judge，REJECT）、
`U06-C18`（成本报告，Security 改路由指向本模块）、`U04-C15`（自主权分级）。

新 ID 从 `SL-CAP-0068` 起。F1-C、F1-D 未启动。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -3 && git status --short \
  && python3 tools/fusion/f1b_verify_storage.py | tail -2
```

检索词：F1B Storage batch checkpoint。
