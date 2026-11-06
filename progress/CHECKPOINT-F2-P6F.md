# F2-P6F 检查点 · 基线 acfdbde · Crosswalk 匹配

## ★ 关键发现：D-58 定位修正

`src/skill_interface/content_capture.py` **本来就是逐 Blob 即时落盘**：
```
for item in eligible:
    got = BF.fetch_blob(...)          # 采
    ing = CIC.ingest_captured_blob(...)  # 立刻写（循环内）
```
所以**正式 CLI 路径没有 D-58**。

D-58 出在 `tools/f2p6e_e2e.py` —— 那是我上一轮临时写的工具脚本，
自己另建了一套采集循环、把字节攒在内存 dict 里、最后统一落盘。

这恰好就是任务书 §4.1 说的：
> 不允许「工具脚本使用新编排器，正式 CLI 却绕过编排器直接调用旧 Collector」
> 不允许「同一逻辑存在两套会产生不同结果的执行路径」

**修法不是给工具脚本补落盘，而是删掉它的自建采集，让它走正式路径。**
从根本上消灭第二条路径，而不是让两条路径都"正确"。

## 已完成（2026-06-18 18:10）
**编排器接入正式 CLI**：`analyze` 的 include-content 分支现在先走
`_preflight_budget` → 建 DAG（标 LOCAL_REUSE）→ bootstrap 取真实响应头 → 三条件判定
→ 通过才调 `CC.capture(budget=...)`。预检不过则不采集，但已完成资产仍可查询。

**content_capture 接预算**：新增 `budget=None` 参数；每个 blob 采集前 `can_spend`，
采完用 blob_fetcher 透传的 `headers` 调 `consume` 更新真实剩余。

**blob_fetcher 透传响应头**：原来不回传 headers/http_status → 预算拿不到真实数据。

**D-59 预检逻辑错误**：need==0（全复用）时仍检查 remaining，
导致"无需联网"的运行被误判 `INSUFFICIENT_REMAINING`。
实测：修前 can_begin=False，修后 True；有缺口无头仍正确阻断。

实测 CLI：
```
can_begin: True | planned: 0 | net: 0
index.js → ALREADY_CAPTURED
README.md → ALREADY_CAPTURED
```

## 验收器（离线部分 13/13）
```
PER_BLOB_IN_LOOP        入库点在 fetch 之后、同循环内
NO_BATCH_FINAL_WRITE    无攒批结构
CLI_HAS_PREFLIGHT       _preflight_budget
CLI_PASSES_BUDGET       budget=_budget
CLI_OFFLINE_BLOCK       OFFLINE_NO_REQUESTS
BLOB_FETCHER_HEADERS    got["headers"]
PERSIST_BEFORE_WRITE    持久化判定在写入前
NO_UNLICENSED_WRITE     同上（索引序验证）
REUSE_ZERO_REQUESTS
D59_NO_HEADER_OK_WHEN_ZERO
D59_BLOCK_WHEN_GAP
CJS_UNSUPPORTED
VALID_EMPTY
```
真实采集 4 项待 E2E 完成。

## 测试
1469 项全绿（保留 1449 + 新增 p6f_capture 20）
