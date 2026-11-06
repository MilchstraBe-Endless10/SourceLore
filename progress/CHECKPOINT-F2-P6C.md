# F2-P6C 检查点 · 基线 8ef5ebb · Crosswalk 复算匹配

## ★★ 首个关键发现（必须先说清）

真实 Storage 里有两个不同的知识库，**不能混为一谈**：

| 库 | repository_id | commit | tree条目 | 资产 |
|---|---|---|---|---|
| `/tmp/p6b_real` | **24313173**（真实 GitHub） | 98e8ff1da1a8… | **13** | snapshot 1 / fact 1 / claim 1 / verif 1，**无 content blob** |
| `/tmp/p6b_realE` | local:13fc64103be1（本地种子） | 41dee5ac9099… | 3 | snapshot 1 / blob 2 / fact 51 / claim 5 / verif 5 |

`/tmp/p6b_realE` 是用**真实 GitHub 字节**（OID 已逐一比对）建起的本地 git 对象库，
但它自己的 repository_id 是 local，commit 是本地重算的。

**所以 P6B 报告里「51 事实」对应的不是 GitHub 仓库本身**，是本地种子库。
这样写不算造假（字节确实来自 GitHub），但把它当作「真实 GitHub 仓库的知识」是**口径混淆**。
本轮必须把真实 GitHub 库（24313173）自身补齐。

## 真实库缺口（待程序化确认）
- tree 已枚举 13 项
- content blob：0
- index.js / README.md / package.json / LICENSE 全部 CONTENT_NOT_CAPTURED
- 唯一事实是路径命题（repository_path_exists）

## 下一步
1. 建 request_budget.py + capture_request_plan.py（真实缺口盘点 + 预算）
2. --plan 只读模式
3. 预算够就真采 index.js（1 次请求）
4. 源码事实 → Claim → 查询 → 卡片

## ★ 真实 index.js 已采集并验证（2026-11-06 14:33）
```
net=1（只发 1 次 Blob 请求，README/package.json 未动）
asset SL-CBLOB-22f5c42a71bedbe53c231aaeae5cc65feeee2050
sha256 04255e482e181687823a95b207802ddd32e746c65dce4c95a5176fc192735960
git_blob_oid 27f19b757f7c1186b92c405a213bf0dd9b6cbe95 (411 字节)
本地复算 OID = 27f19b757f7c1186b92c405a213bf0dd9b6cbe95 → MATCH
completeness COMPLETE
```

## 源码实际形态（读字节得出，不是猜）
```js
'use strict';
module.exports = function(num) { ... };   // CommonJS 匿名函数表达式
```
无具名函数声明、无 import、无 ES export。

## 解析结果：0 symbols / 0 exports / 0 imports
这是**合法空结果**而非缺陷：
`js_ts_import_export_rules.collect_exports` 只处理 `export_statement`（ES module），
`module.exports =` 不在当前契约内。

→ `VALID_EMPTY_RESULT`（对本次文件而言），
  但必须标为「该仓库源码知识受解析器能力边界限制」，
  **不能据此宣称「源码知识完整」**。

## 真实 GitHub 库现状（2026-11-06 14:36）
```
repository_id 24313173
commit 98e8ff1da1a89f93d1397a24d7413ed15421c139
captured_blob_content 3  (README/package.json/index.js，全部 COMPLETE)
extracted_fact 51        (README 44 + package.json 7)
claim_candidate 18
claim_verification 18
```
查询：README → SUPPORTED net=0；index.js → SOURCE_NOT_ANALYZED（0 事实，诚实）
卡片：16603 字节 README_CONTENT_CARD

## 本轮新缺陷
- **D-51** GitHub 路径原本只捕获字节、不抽取知识（本地路径有链路，GitHub 路径没有）
- **D-52 已保存内容被无意义重新下载** —— 有完整资产仍发请求，撞限流后把已存好的标记成失败。
  修：采集前查 `find_content_asset`，COMPLETE 直接 `ALREADY_CAPTURED` 复用。
  实测 net 从 1 → 0，reused=3。

## 源码知识结论
index.js 是 CommonJS `module.exports = function(num){...}`。
解析器只处理 ES `export_statement` → 0 symbols/exports/imports。
判定 **VALID_EMPTY_RESULT**，并明确标注「受解析器能力边界限制」，
不宣称「源码知识完整」。

## 预算实测
- 单次上限 8，预留 5
- 实际发请求：index.js 1 次 + README/package.json 2 次 = 3 次
- 三次总量远低于上限；reset 后 remaining=60
