# F2-P6E 真实 ESM 仓库验收

## 候选与固定版本

`sindresorhus/is-plain-obj`

本轮**不以网页预览为准**。以下全部来自固定 Commit 的 Tree 与 Blob，
文件大小写也以真实 Tree 为准（该仓库用的是 `readme.md`，不是 `README.md`）。

（实际身份数据见 `F2_P6E_GATE_RESULTS.json` 的 `real_repository` 段；
若本轮被配额阻断则那一节标 `NOT_COLLECTED`，不填任何推测值。）

## 最小采集范围

| 文件 | 用途 |
|---|---|
| LICENSE | 只作**授权核验输入**，不计入业务知识类别 |
| readme.md | README 内容知识 |
| package.json | Manifest 内容知识 |
| index.js | ESM 源码结构与导出 |

不取 tests、工作流配置、整个仓库。不跑 `npm install`，不执行第三方代码。

## 授权

五维独立判定：FETCH / PERSIST / DERIVE_FACTS / PREVIEW / DISTRIBUTE。

公开可读 **不等于** 允许持久化或允许分发。所以：

```
copy_permitted = false
distribution_allowed = false
```

B-1/B-2/B-3 仍是独立问题，不由本轮结论覆盖。

## 字节真实性的两层验证

1. **Git Blob OID**：`SHA1("blob " + len + "\0" + raw)` 与 Tree 里的 OID 比对。
   不等就拒绝落库 —— 不允许「差不多」。
2. **内容 SHA-256**：落库后按内容寻址存储，任何读回都重新校验。

这两层不可互相替代。OID 证明「这与 Git 对象一致」，SHA-256 证明「落盘的字节没变」。

## ESM 事实的预期

对 `index.js`，按**实际字节**决定预期，不按网页示例：

- 若有 `export default function ...` → `ts/js` default export 事实 + 对应 Symbol
- 若有 `export const/function ...` → declaration export 事实
- 若有 `export * from` → reexport 事实

**若实际是 CommonJS**：保留 `UNSUPPORTED_SEMANTIC_FORM`，不制造导出事实。
这正是 P6D 修的那条 —— 能力缺口不能伪装成事实结论。

## 语义覆盖报告

每个源文件都输出：

```
language / parser_version / parse_status
supported_rule_families          # 只列真实具备的
observed_supported_nodes
recognized_but_unsupported_forms # 有样本
facts_persisted / claims_verified
analysis_coverage
limitations
```

`SUPPORTED_RULE_FAMILIES` 目前只有三族：

```
symbol_declaration / es_export_statement / es_import_statement
```

不宣称「完整理解 JavaScript」。这句话写在 `limitations` 里，是机器可读的。

## 卡片

复用 Safe Renderer，不另建 HTML 系统。必须展示：

仓库 / 固定 Commit / 源文件路径 / Blob OID / Parser / Symbol / Export /
Fact / Verification / Evidence 位置 / 语义覆盖范围 / 不支持的形态 /
许可与分发限制。

安全门禁：CSP、HTML 转义、无脚本、不复制超出授权范围的大段原文、
`distribution_allowed=false`。

## 多仓库隔离

两个仓库都有 `README.md` / `package.json` / `index.js`。
隔离靠三键：`repository_id` + `commit_sha` + `file_path`。

**同名文件不构成混淆条件** —— 查询输出的每一条都带前两个键，
这是 P6A 就定下的契约，本轮只是在新仓库上再验一次。
