# F2-P5D 执行报告

**基线** `871264c`

## 结论

真实 GitHub Blob 抓取与完整性校验**做通了**；真实字节**持久化被授权门禁正确阻断**。

这是本轮最重要的两个事实，必须分开看：

```
REAL_FETCH_VERIFIED      DONE   ← 真实 HTTP、真实字节、Git OID 校验通过
REAL_BYTES_PERSISTED     BLOCKED ← LICENSE_UNKNOWN，preflight 拒绝写入
```

阻断不是失败，是门禁按设计生效。

## 真实抓取实录

```
GET /repos/octocat/Hello-World/git/blobs/980a0d5f19a64b4b30a87d4206aade58726b60e3

preflight : AUTHORIZATION_UNKNOWN / LICENSE_UNKNOWN   ← 正确阻断写入
size_gate : True (13B ≤ 256KiB)
status    : FETCH_OK    network_requests = 1
bytes     : b'Hello World!\n'   len = 13
git_oid   : 980a0d5f19a64b4b30a87d4206aade58726b60e3   MATCH
sha256    : sha256:03ba204e50d126e4674c005e04d82e84c21366780af1f43bd54a37816b6ab340
```

`git_blob_oid` 算法另用独立已知值验证：`SHA1(b"blob " + len + b"\0" + raw)`。

## 新增模块

```
src/collector/content_acquisition_policy.py   四档授权 + 白名单 + 路径安全
src/collector/blob_fetcher.py                 预算门 + base64 解码 + 八项校验
src/storage/blob_content_store.py             内容寻址字节存储
src/storage/content_ingest_coordinator.py     元数据入 A 层
src/content/captured_blob_loader.py           离线读回（零网络）
src/skill_interface/content_capture.py        CLI 采集入口
```

## 存储设计（为什么字节不进 assets）

`assets` 表只有 `payload_json`（TEXT），没有 BLOB 列。把原始字节塞进 JSON 会：

1. 改变换行 / BOM 语义
2. 无法做二进制级校验
3. 违反"原始内容必须是真实字节"的要求

方案：

```
元数据 → assets.captured_blob_content（权威，含 content_sha256）
字节   → <data_root>/blobs/<sha256>.bin（内容寻址）
绑定   → 两侧 sha256 必须相等，读时逐次校验
```

这不是第二套知识库——它没有独立知识语义，只是 A 层记录的字节后端。

## 三个真缺陷

**D-9 `captured_blob_content` 未注册为合法资产类型**
`AssetDraft.__post_init__` 直接抛 `ModelError`，所有写入失败。

**D-10 `logical_identity` 不允许 `/` 字符**
含路径的身份被拒。第一次用 `%XX` 编码——`%` 也不在允许集内。改用 `_xXX_`（下划线在允许集内）。

**D-11 试图事后 UPDATE 回填 `content_asset_id`**
A 层触发器 `A_LAYER_IMMUTABLE` 拒绝 → 字段恒 NULL。
改为写入前用确定性 ID 预先计算，删掉 UPDATE。

这条最值得记：**A 层不可改，任何自引用必须在写入前算好。**

## 合成链路验收

```
进程 1 写入  → content_asset_id=SL-CBLOB-20cb53...
进程 2 读回  → CONTENT_AVAILABLE_VERIFIED, bytes_equal=True, len=56
进程 3 再读  → 同上，网络请求 0
```

三次重复采集 → 同一资产 ID，`index_rows` 仅 1 行（幂等成立）。

## 验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77 blob_capture59
= 804 项，失败 0
f1d 26/26（已登记 tests/blob_capture/）
Crosswalk 42841207… 未变
```

阻断级指标全部为 0：错误 Blob 接受 / 未授权持久化 / 错误 Commit 绑定 /
不完整标为完整 / 只读触发网络 / 权威资产被改。

## 门禁

| 门禁 | 状态 |
|---|---|
| A_CONTENT_ACQUISITION_POLICY | **DONE** |
| B_GITHUB_BLOB_FETCH | **DONE** |
| C_GIT_BLOB_INTEGRITY | **DONE** |
| D_IMMUTABLE_CONTENT_STORAGE | SYNTHETIC_ONLY |
| E_OFFLINE_BLOB_RELOAD | SYNTHETIC_ONLY |
| F_CAPTURE_IDEMPOTENCY | **DONE** |
| G_CONTENT_ENGINE_REAL_INPUT | BLOCKED |
| H_CONTENT_FACTS_EC_PERSISTENCE | NOT_STARTED |
| I_REAL_GITHUB_BLOB_E2E | PARTIAL（抓取 DONE，持久化 BLOCKED） |
| J_NATURAL_LANGUAGE_AUTO_TRIGGER | NOT_VERIFIED |
| K_DISTRIBUTION_READY | NOT_READY |

## 下一批最小起点

要让真实链路走通 E，只需一个东西：**明确的内容采集授权依据**。

两条路，任选其一：

1. 用你自己拥有的测试仓库（`repo_looks_third_party=False` 路径已实现）
2. 给某个开源仓库提供可审计的许可证依据，`--license-known` 传 true

有一条不能做：把 `copy_permitted=false` 改成 true。那会改变字段原有语义，也解不开 B-1/B-2/B-3。
