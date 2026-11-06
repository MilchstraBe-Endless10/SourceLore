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

## D-60 --resume 是声明式空参数（2026-11-06 18:15）
`--resume` 只有 argparse 定义，**函数体零引用** —— 和 D-46 `license_known` 同一类缺陷。
新增 `src/skill_interface/capture_resume_report.py`：只读、零网络，
按真实 Storage 盘点「已完成 / 缺失 / 需几次请求」，**不信日志**。

实测 is-number：
```
net: 0 | repo: 24313173
已持久化: README.md / package.json / index.js
缺失: LICENSE  → 需 1 请求
```

顺手修了一个查询错误：`index_rows` 只有索引列（asset_id/asset_type/logical_identity/
repository_id/subject_id/commit_sha/asset_version），**payload 在 assets 表**。
自己拼 SQL 会撞 `no such column: payload_json`；改用已有的 `capture_request_plan._load_snapshot`。

## D-61 两个死开关当场被抓（2026-11-06 18:17）
新写的 `test_declared_switches.py` 扫描所有 `add_argument` 定义的开关，
断言每个都必须在函数体里被 `getattr(args, ...)` 或 `args.X` 读过。
**第一次运行就抓出 `--language` 和 `--relation`** —— 全是死开关。

- `--language`：底层 `source_knowledge.query_code` **根本不支持 language 过滤**
- `--relation`：无任何实现

处理：**删掉，不是硬接**。保留会让用户以为能用，实际什么都没做——
这正是 D-46/D-60 那类缺陷的温床。
注释里写明「需要时再连底层能力一起加，而不是只加一个参数」。

1482 项全绿。
