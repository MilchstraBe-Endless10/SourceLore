# F2-P6F 真实 ESM 仓库 E2E

## 已固定身份（P6E 取得，本轮从 Storage 复核）

```
owner/repo     sindresorhus/is-plain-obj
repository_id  38923193
commit_sha     666df7c10035f7e26f27ec214fe5ae3173435f34
root_tree_sha  5d176b98189da7878396a2cffe7590ff35461332
license        MIT
tree 条目      13，未截断
```

目标文件（**实际 Git 路径，小写**）：

| 文件 | OID | 字节 |
|---|---|---|
| `license` | fa7ceba3eb4a9657a9db7f3ffca4e4e97a9019de | 1117 |
| `readme.md` | 25212c562cd8f1a6101fc1b85c4627b972d59d00 | 794 |
| `package.json` | 340b4909a6aaa34afe976df2dddaf2017ea5d672 | 758 |
| `index.js` | 92555c3d3916f4868375fa19d7da7ecafe6ee9b3 | 344 |

**不能写成 `LICENSE` / `README.md`** —— 大小写规范化只用于受控选择匹配，
不作为 Blob 或 Evidence 的身份。

## 恢复盘点先于采集

正式执行前必须先输出：

- 已验证元数据（identity / commit / tree / entries）
- 已验证字节资产
- 仅在历史日志出现的对象（**不算缓存**）
- 当前缺失对象
- 需要几个请求
- 授权阻断
- 可离线完成的步骤
- 当前预算

不允许直接从头重采。

## 预算

四个 Blob 都缺、Commit 与 Tree 已在库时，理论必要请求 = 4（一条 `/rate_limit` 除外）。

但实际计划必须按真实已存资产重算，**不硬编码 4**。
`build_repo_acceptance_plan(have_blobs=...)` 就是干这个的。

## 请求日志字段

每次请求记录：`execution_id` / `request_node_id` / method / endpoint 类别 /
object identity / repository_id / commit_sha / HTTP status / 起止时间 /
`X-RateLimit-{Limit,Remaining,Used,Reset,Resource}` / `Retry-After` /
GitHub Request ID / 结果资产 ID / 结果。**不记 Token。**

## 剩余配额突变归因

必须分开：本进程已记录请求 / 进程外共享 IP 变化 / 响应头区域差异 /
主限流 / 次级限流 / 无法判定。

不能凭 `remaining 23 → 0` 说「SourceLore 发了 23 次」；
也不能凭本地计数 8 就说「别人发了 15 次」。

证据不足时明确写 `RATE_LIMIT_CHANGE_CAUSE_UNDETERMINED`。

## ESM 事实

不预设 `index.js` 一定有什么符号。按实际字节：

- 有 `export default function` → default export 事实 + Symbol
- 有 `export const/function` → declaration export 事实
- 有 `export * from` → reexport 事实
- 若是 CommonJS → `UNSUPPORTED_SEMANTIC_FORM`，**不制造导出事实**

`PARSE_COMPLETE` 不能替代事实入库证明。
