# F2-P5D（检查点）· 基线 871264c · Crosswalk 已复算匹配

## 目标（只一件）
Existing Snapshot → Authorized Blob Fetch → Integrity Verify → Immutable Store → Offline Read
**不加解析器、不加 Claim 类型、不建第二套 Storage。**

## 已核验
- GitHub 限流**已恢复**（`/repos/octocat/Hello-World` → HTTP 200）
- `GitHubClient.blob(owner, name, blob_sha, repository_id=, commit_sha=)` **已存在**
  → `GET /git/blobs/{sha}`，stage=blob_fetch
- 仓库当前工作区干净

## 关键待决（必须先想清楚）
1. **A 层 assets 表能否存原始字节**：`payload_json` 是 JSON TEXT，
   存 base64 会改变"字节真实存储"的语义。需查 ASSET_TYPES 与是否有 BLOB 列。
2. **授权门禁**：`copy_permitted=false` 不可改；B-1/B-2/B-3 OPEN。
   需新增独立的「内部内容采集授权」判定，不覆盖原字段。
3. **Git Blob OID 校验**：`SHA1(b"blob " + len + b"\0" + raw)`，
   不能用普通文件 sha1 冒充。

## 硬约束
- 白名单：README.md/.markdown/.txt、package.json、pyproject.toml、
  Cargo.toml、go.mod（仅仓库根；子目录须显式指定）
- 预算：单 blob 256KiB、批 2MiB、32 路径
- 不发请求前先看 tree entry 的 size
- 本轮默认**不持久化不完整 Blob**
- 不执行仓库代码、不采 LFS、不追 submodule、不读 symlink 目标

## 已完成模块（2026-11-05 20:03）
- `src/collector/content_acquisition_policy.py` — 四档授权 + 白名单 + 路径安全
- `src/collector/blob_fetcher.py` — git_blob_oid 算法**已用已知值验证**
  （Hello-World README 13B → 980a0d5f... MATCH True）
- `src/storage/blob_content_store.py` — 内容寻址（blobs/<sha256>.bin），幂等、原子替换
- `src/storage/content_ingest_coordinator.py` — 元数据入 A 层 + 字节入 store

## 设计决定（重要）
`assets` 只有 payload_json(TEXT)，**没有 BLOB 列**。
因此：元数据入 assets（权威），字节入 blobs/ 目录，由 content_sha256 强绑定。
这不是第二套知识库——它没有独立知识语义。

## ★ 真实 GitHub Blob 抓取成功（2026-11-05 20:03）
```
preflight: AUTHORIZATION_UNKNOWN / LICENSE_UNKNOWN   ← 正确阻断
size_gate : True (13B ≤ 256KiB)
status    : FETCH_OK  network_requests=1
bytes     : b'Hello World!\n'   len=13
git_oid   : 980a0d5f19a64b4b30a87d4206aade58726b60e3  MATCH=True
sha256    : sha256:03ba204e50d126e4674c005e04d82e84c21366780af1f43bd54a37816b6ab340
```
**结论分离**：
- `REAL_FETCH_VERIFIED` = 可标记（真实 HTTP + 真实字节 + OID 校验）
- `REAL_BYTES_PERSISTED` = **必须保持 BLOCKED**（license unknown，preflight 拒绝写入）
- 这正是授权门禁生效的证据，不是失败
