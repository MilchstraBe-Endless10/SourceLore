# F2-P6D 执行报告

基线 `625cc71`。

## 结论先说

本轮完成两项修复，**未完成第二仓库真实验收**——GitHub 配额耗尽。

- **--plan 与执行不一致**：查明是时序问题，不是判定分歧。已补统一上下文标识 + 计划失效重校验。
- **CommonJS 语义误报**：真修了。is-number 的 index.js 现在报 `UNSUPPORTED_SEMANTIC_FORM`，不再谎称「该文件没有导出」。

is-plain-obj 的真实采集没做成：`remaining=0/60`，reset 在 43 分钟后。按任务书 §6.3 停止联网，不长时间等待。

## 一、--plan 不一致的根因

P6C 时我贴的两份输出是**不同时刻**的：

```
先跑 --plan   → 那时三个资产都不存在，所以 CONTENT_NOT_CAPTURED
后跑执行      → 此时采集已完成，所以 reused=3
```

**同一存储状态下，两者是一致的。** 本轮实测：

```
--plan  → estimated_requests=0
          README.md     CLAIMS_VERIFIED
          package.json  CLAIMS_VERIFIED
          index.js      CONTENT_CAPTURED_BUT_NOT_PARSED
执行    → net=0, reused=3, 三个 ALREADY_CAPTURED
```

我没有用「换个 data_root」掩盖问题——两次都在 `/tmp/p6b_real`。

但解释不等于机制。所以补了 `capture_plan_consistency.py`：

```
plan_id + inventory_digest（按 path/oid/state/planned 排序后 sha256）
revalidate() → PLAN_FRESH / PLAN_STALE_REVALIDATED / PLAN_CONTEXT_MISMATCH
三种结果都返回 use_inventory = 新鲜盘点，永不按旧计划发请求
```

`database_identity` 用绝对路径哈希做内部比对，输出脱敏成 `…/kb.db`。

## 二、CommonJS 语义覆盖

原逻辑：0 事实 → 一律 `VALID_EMPTY_RESULT`。

这是把「我的规则没覆盖」说成「这个文件没有东西」——最坏的一类错误，因为它听起来像结论。

新逻辑区分七态：

| 状态 | 含义 |
|---|---|
| `SUPPORTED_FACTS_EXTRACTED` | 有事实入库 |
| `VALID_EMPTY_RESULT` | 解析成功、规则跑完、范围内确实没有 |
| `UNSUPPORTED_SEMANTIC_FORM` | **有已识别但未覆盖的形态** |
| `PARSE_FAILED` | 语法失败 |
| `SOURCE_CONTENT_NOT_CAPTURED` | 内容没捕获 |
| `SOURCE_FACTS_NOT_PERSISTED` | 解析完了但没入库 |

判定顺序：先查未支持形态，**再**才考虑空结果。

实测 is-number：

```
index.js → UNSUPPORTED_SEMANTIC_FORM
  recognized_but_unsupported_forms:
    [{form: commonjs_module_exports, sample: "module.exports = ..."}]
  explain: 语法解析成功，但文件中存在已识别且当前规则族未覆盖的语义形态；
           不能据此判定该文件没有导出
```

`SUPPORTED_RULE_FAMILIES` 只列真实具备的三族（symbol_declaration / es_export_statement / es_import_statement），不吹「完整理解 JavaScript」。

## 三、第二仓库：BLOCKED

候选 `sindresorhus/is-plain-obj` 只做了筛选调研，**没有采集**。

配额实况：

```
GET /rate_limit → 200
remaining 0/60, reset 在 2614 秒后
```

按 §6.3：输出计划并停止，不长时间等待，不用未授权身份绕过。

所以 E~M 全部 BLOCKED。**我没有用 is-number 的数据冒充第二个仓库。**

## 四、测试

```
1422 项，失败 0，退出码全 0
（保留 1402 + 新增 product_multirepo 20）
```

## 五、门禁

| 门禁 | 状态 | 依据 |
|---|---|---|
| A CAPTURE_PLAN_STATE_CONSISTENCY | **DONE** | 同状态实测一致 |
| B CAPTURE_PLAN_INVALIDATION | **DONE** | 三态重校验 |
| C REQUEST_BUDGET_REGRESSION | **DONE** | 保留 |
| D COMMONJS_COVERAGE_DIAGNOSIS | **DONE** | UNSUPPORTED_SEMANTIC_FORM |
| E REAL_ESM_REPOSITORY_IDENTITY | **BLOCKED** | 配额 0 |
| F REAL_ESM_LICENSE_AUTHORIZATION | **BLOCKED** | 未采集 |
| G REAL_ESM_BLOB_CAPTURE | **BLOCKED** | 未采集 |
| H REAL_ESM_BLOB_INTEGRITY | **BLOCKED** | 未采集 |
| I REAL_ESM_SOURCE_FACTS | **BLOCKED** | 未采集 |
| J REAL_ESM_CLAIM_VERIFICATION | **BLOCKED** | 未采集 |
| K REAL_ESM_INSTALLED_SKILL_QUERY | **BLOCKED** | 未采集 |
| L REAL_ESM_SOURCE_CARD | **BLOCKED** | 未采集 |
| M MULTI_REPOSITORY_ISOLATION | **PARTIAL** | is-number 单仓库已验证；第二仓库未入库 |
| N OFFLINE_RESTART_REUSE | **DONE** | net=0 |
| O SUCCESS_CONTRACT_REGRESSION | **DONE** | 保留 |
| P EXISTING_SOURCE_REGRESSION | **DONE** | 全量回归 |
| Q NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** | 缺独立会话 |
| R DISTRIBUTION_READY | **NOT_READY** | B-1/B-2/B-3 OPEN |

M 给 PARTIAL：单仓库隔离机制在（repository_id + commit 严格三键），但「两个仓库」只有一个是真实的，不能算多仓库已验证。

## 六、仍未支持的代码语义

- `module.exports = ...`（CommonJS）
- `exports.foo = ...`
- `require(...)`
- 动态 `import(...)`

四类都已能**识别**，但都不能**分析**。本轮只做到识别，不越界做解析器。

## 七、下一批

配额一恢复，最先做的就是把 is-plain-obj 采下来——它只差 4 次请求（commit/ref/tree/3 blob）。

但更值得想的是：**为什么连续三轮都在跟同一个 60/小时配额较劲**。

真正的问题不是配额小，是我没有把「一次验收需要几次请求」当成设计输入。
P6C 建了预算模块，但它只在采集内部生效，不管验收编排。
下一批该做的是：把验收编排本身也纳入预算——先算出这批要几次，够了才动手。
