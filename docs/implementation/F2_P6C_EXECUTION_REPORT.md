# F2-P6C 执行报告

基线 `8ef5ebb`。

## 结论

真实 GitHub 仓库 `jonschlinkert/is-number` 的**内容知识已经闭环**：
3 个 blob 全部入库并验证，51 条内容事实、18 条命题/裁决，
安装版 CLI 查询 `SUPPORTED`，卡片可生成，零网络。

请求预算机制建成并实测：3 次请求完成全部采集，上限 8、预留 5。

但源码知识**没有闭环**，原因是解析器边界——不是缺陷：
`index.js` 是 CommonJS `module.exports = function(num){...}`，
现有解析器只处理 ES `export_statement`。
按任务书要求，这个结果标为 `VALID_EMPTY_RESULT`，并明确声明「受解析器能力边界限制」，
**不宣称源码知识完整**。

## 一、首个必须说清的事

真实 Storage 里有两个库，不能混：

| 库 | repository_id | commit | tree | 资产 |
|---|---|---|---|---|
| `/tmp/p6b_real` | **24313173**（真实 GitHub） | 98e8ff1d… | 13 | 3 blob / 51 fact / 18 claim |
| `/tmp/p6b_realE` | local:13fc64103be1（本地种子） | 41dee5ac… | 3 | 2 blob / 51 fact / 5 claim |

`/tmp/p6b_realE` 是用真实 GitHub 字节建的本地 git 库，字节是真的，但它的
`repository_id` 是 local、commit 是本地重算的。

**P6B 报告里「51 事实」当时属于本地种子库，不是 GitHub 仓库本身。**
现在真实库（24313173）已有自己的 51 事实、18 命题。

## 二、请求预算

```
src/collector/request_budget.py
  GitHubRequestBudget：本地上限 + 预留 + 最近响应头三重闸门
  默认 request_limit=8，reserve=5
  没有权威响应头时 → 拒绝发请求（宁可不发，不猜）
```

关键设计：**绝不使用 `60 - 自己记录的请求数` 推断剩余**。
匿名配额按来源 IP 算，其他进程也在花。

实测：
```
reset 后 remaining=60
采集 README + package.json   → 2 请求
采集 index.js                → 1 请求
合计 3，远低于 8 上限
```

## 三、--plan 只读

```
analyze <url> --commit <sha> --plan
→ read_only=true, network_requests=0, wrote_assets=0
  repo 24313173, snapshot COMPLETE
  estimated_requests=3
  completeness: tree=COMPLETE / content=PARTIAL / knowledge=PARTIAL
  README.md     CONTENT_NOT_CAPTURED  needed=True
  package.json  CONTENT_NOT_CAPTURED  needed=True
  index.js      CONTENT_NOT_CAPTURED  needed=True
```

三种完整性分开报，不因为 tree COMPLETE 就把内容标 COMPLETE。

## 四、限流分类

```
主限流   remaining=0 + used=limit              → PRIMARY
次级限流 Retry-After 存在 + remaining 非 0     → SECONDARY
两者都缺                                      → UNKNOWN（不猜）
```

不能只看 HTTP 403。

## 五、真实 index.js

| 项 | 值 |
|---|---|
| GitHub OID | 27f19b757f7c1186b92c405a213bf0dd9b6cbe95 |
| 字节 | 411 |
| 本地复算 OID | 27f19b757f7c1186b92c405a213bf0dd9b6cbe95 → **MATCH** |
| content_asset_id | SL-CBLOB-22f5c42a71bedbe53c231aaeae5cc65feeee2050 |
| sha256 | 04255e482e181687823a95b207802ddd32e746c65dce4c95a5176fc192735960 |

真实内容：
```js
'use strict';
module.exports = function(num) { ... };
```

解析：`PARSE_COMPLETE`，0 symbols / 0 exports / 0 imports。
**VALID_EMPTY_RESULT** —— 该文件在解析契约内确实没有可登记结构。

## 六、命中缺陷

**D-51 GitHub 路径只捕获不抽取。** 本地路径（`analyze_local`）有完整内容+源码链路，
GitHub 路径走 `content_capture` 只把字节存下来就完了。两条路径能力不对等。

**D-52 已保存内容被无意义重新下载。** 库里明明有完整资产，采集仍无条件发请求；
撞限流后把已经存好的内容标记成 `BLOB_HTTP_ERROR`。

修：采集前查 `find_content_asset`，`COMPLETE` 直接 `ALREADY_CAPTURED` 复用。

实测 `net` 从 1 → **0**，`reused=3`。这是任务书列的阻断指标之一，现在为零。

## 七、真实库最终状态

```
repository_id 24313173
commit 98e8ff1da1a89f93d1397a24d7413ed15421c139
captured_blob_content 3   (README / package.json / index.js，全 COMPLETE)
extracted_fact       51   (README 44 + package.json 7 + index.js 0)
claim_candidate      18
claim_verification   18
```

查询：
```
query --type content --path README.md  → SUPPORTED  net=0
query --type code    --path index.js   → SOURCE_NOT_ANALYZED  net=0
card --path README.md                  → 16603 字节
```

`index.js` 报 `SOURCE_NOT_ANALYZED` 是**诚实的**——0 事实就是没分析出东西，
不假装成功。

## 八、测试

```
1402 项，失败 0，退出码全 0
（保留原 1381 + 新增 capture_maintenance 21）
```

## 九、门禁

| 门禁 | 状态 | 依据 |
|---|---|---|
| A REQUEST_BUDGET_PLANNING | **DONE** | 三重闸门 + 实测 3/8 |
| B REQUEST_PLAN_READ_ONLY | **DONE** | net=0 wrote=0 |
| C RATE_LIMIT_HEADER_HANDLING | **DONE** | 从响应头取值，不猜 |
| D PRIMARY_SECONDARY_LIMIT_CLASSIFICATION | **DONE** | 两路 + UNKNOWN |
| E PARTIAL_CAPTURE_RESUME | **DONE** | ALREADY_CAPTURED 复用 |
| F EXISTING_ASSET_REUSE | **DONE** | net 1→0 reused=3 |
| G CAPTURE_IDEMPOTENCY | **DONE** | 二次跑指纹不变 |
| H REAL_GITHUB_SOURCE_BLOB_PERSISTENCE | **DONE** | index.js 411 字节入库，OID 复算一致 |
| I REAL_GITHUB_SOURCE_FACTS | **PARTIAL** | 解析契约内 0 事实（CommonJS 不在支持范围） |
| J REAL_GITHUB_SOURCE_CLAIMS | **PARTIAL** | 无源码命题可建（事实为 0） |
| K REAL_GITHUB_SOURCE_CLI_QUERY | **DONE** | SOURCE_NOT_ANALYZED，net=0，诚实 |
| L REAL_GITHUB_SOURCE_KNOWLEDGE_CARD | **PARTIAL** | 内容卡可出；源码卡无谓词可渲 |
| M OFFLINE_RESTART_REUSE | **DONE** | net=0，指纹不变 |
| N SUCCESS_CONTRACT_INTEGRITY | **DONE** | 八档保留，VALID_EMPTY 已标 |
| O CROSS_MODULE_SCHEMA_CONTRACT | **DONE** | D-51/D-52 修复 |
| P MULTI_COMMIT_ISOLATION | **DONE** | 回归通过 |
| Q INSTALLED_SKILL_PRODUCT_E2E | **DONE** | product_acceptance 21/21 |
| R NATURAL_LANGUAGE_SKILL_DISCOVERY | **NOT_VERIFIED** | 缺独立会话 |
| S NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** | 缺独立会话 |
| T DISTRIBUTION_READY | **NOT_READY** | B-1/B-2/B-3 OPEN |

I/J/L 给 PARTIAL 而不给 DONE：字节和持久化是真的，但**解析器不支持 CommonJS**，
没有可建的源码事实。用原创夹具凑事实进来充 DONE 是任务书明令禁止的。

## 十、源码知识的真实边界

这不是「本轮没做完」，是「当前解析器不支持这种代码形态」：

- 支持：`export function`、`export const`、`export default`、`export * from`
- 不支持：`module.exports = ...`、`exports.foo = ...`

`is-number` 恰好整份文件是 CommonJS。换个 ES module 仓库就能有事实，
但本轮不添新解析器（任务书明令禁止）。

## 十一、下一批

要让源码知识真正闭环，两条路：
1. 补 CommonJS 导出识别（属解析器扩展，本轮禁止）；
2. 换一个 ES module 的验收仓库。

我倾向第 2 条——先把「能采、能存、能查、能复用」这条产品链在更多真实仓库上跑稳，
再回头补语言覆盖面。语言解析器是最容易越做越深、越深越难验收的部分。
