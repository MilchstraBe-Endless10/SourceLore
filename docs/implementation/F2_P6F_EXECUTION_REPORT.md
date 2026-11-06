# F2-P6F 执行报告

基线 `acfdbde`。

## 结论

两个 P0 都完成：

A. **逐 Blob 即时持久化** —— 定位后修正：正式路径本来就没有 D-58，
缺陷在我上一轮临时写的工具脚本（自建第二条采集路径）。已让工具走正式路径。

B. **编排器接入正式 CLI** —— `analyze` 现在先预检、再采集，预算贯穿全程。

第二仓库真实字节：**4/4 全部落盘并验签**，源码事实 4 条入库，查询与卡片均通。

## 零、结论速览

| 项 | 实测 |
|---|---|
| is-plain-obj 四文件 | license 1117B / readme.md 794B / package.json 758B / index.js 344B，**oid_match 全 True** |
| 实际请求 | 首轮 8 次（含 1 bootstrap），续跑 6 次；**前三个直接 ALREADY_CAPTURED** |
| 源码事实 | 4 条（2 符号 + 2 导出），`SUPPORTED_FACTS_EXTRACTED` |
| 源码查询 | `FOUND`，net=0，符号/导出口径正确 |
| 卡片 | 5701B，net=0 |
| 两仓库 | 38923193 / 24313173 独立，同名 index.js 不混用 |

## 一、D-58 定位修正

P6E 报告说 D-58 是「采集流程全采完才落盘」。检查后：

`src/skill_interface/content_capture.py` **一直是逐 Blob 即时入库**：

```
for item in eligible:
    got = BF.fetch_blob(...)            # 采
    ing = CIC.ingest_captured_blob(...) # 立刻写
```

问题在 `tools/f2p6e_e2e.py` —— 我自己另建了采集循环，把字节攒在内存 dict 里。

**这正是任务书 §4.1 禁止的「两条会产生不同结果的执行路径」。**

修法不是给工具脚本补落盘（那会让两条路径都"正确"，但仍然是两条），
而是删掉自建循环、让它走正式路径。本轮 `tools/f2p6f_real_e2e.py` 每采一个立刻 `ingest_captured_blob`。

## 二、编排器接入 CLI

`cli.py` 的 include-content 分支新增 `_preflight_budget`：

```
建请求 DAG（本地已有资产标 LOCAL_REUSE）
→ bootstrap 取权威响应头（至多一次）
→ 三条件判定（local_max / remaining>=need+reserve / 非限流）
→ 通过才 CC.capture(budget=...)
```

`content_capture.capture` 新增 `budget` 参数：每个 blob 采集前 `can_spend`，
采完用真实响应头 `consume`。

`blob_fetcher.fetch_blob` 原来**不回传响应头**——预算拿不到真实剩余。
已补 `headers` / `http_status` 透传。

## 三、命中的缺陷

**D-59 预检逻辑错误。** `need==0`（全部本地复用）时仍检查 `remaining`，
导致「无需联网」的运行被误判 `INSUFFICIENT_REMAINING`。

实测：修前 `can_begin=False`，修后 `True`；有缺口无响应头仍正确阻断。

**D-60 `--resume` 是声明式空参数。** 和 D-46 `license_known` 同一类：
argparse 里有定义，**函数体零引用**。带不带 `--resume` 行为完全相同。

新增 `capture_resume_report.py` 接线：只读、零网络、按真实 Storage 盘点。

实测 is-number：
```
net: 0 | repo: 24313173
已持久化: README.md / package.json / index.js
缺失: LICENSE → 需 1 请求
```

## 四、真实 ESM 源码知识（本轮新增）

`index.js` 真实内容：

```js
export default function isPlainObject(value) {
	const prototype = Object.getPrototypeOf(value);
	return ...;
}
```

解析：`PARSE_COMPLETE`，2 symbols / 2 exports。

入库事实 4 条：

| 类型 | subject |
|---|---|
| symbol | `isPlainObject` / `js_function` / line 1–8 / byte 15–343 |
| symbol | `isPlainObject.prototype` / `js_variable` / line 6 / byte 120–167 |
| export | `export_declaration` / `isPlainObject` |
| export | `default_export` / `isPlainObject` |

覆盖度：`SUPPORTED_FACTS_EXTRACTED`。

## 五、命中的两个新缺陷

**D-62 源码事实统计与语义误判（阻断级）。**

`github_knowledge_extract` 只统计 `written`，**不计 `reused`**。重复执行时事实明明在库，
却报 `source_facts=0`；叠加 `semantic_coverage` 的「0 事实 → VALID_EMPTY_RESULT」，
最终把一份**成功解析出 2 个符号 2 个导出**的文件谎报成「合法空结果」。

这正是任务书 §8.2 点名的阻断级情形：受支持的语法没有产生事实，不能标正常空。

修两处：
1. `n = written + reused`，并分别暴露 `source_facts_written` / `source_facts_reused`
2. `observed_nodes > 0` 且 0 事实 → `SOURCE_FACTS_NOT_PERSISTED`（不是 `VALID_EMPTY_RESULT`）

修后实测：`sf` 由 0 → **4**，覆盖度由 `VALID_EMPTY_RESULT` → `SUPPORTED_FACTS_EXTRACTED`。

**D-63 `data_root=None` 让知识抽取整体失败。**

CLI 里 `root = args.data_root` 默认是 None（环境变量在别处读），
`content_capture` 内部有 `DEFAULT_DATA_ROOT` 兜底，但 GKE 调用点没有
→ `TypeError: ... not 'NoneType'`，整个 `knowledge_extraction` 被吞成 `ok:False`。

## 六、测试

```
1489 项，失败 0，退出码全 0
（保留 1449 + 新增 p6f_capture 40）
tools/f2p6f_verify.py：17 项（含真实采集 4 项）
```

## 五、门禁

（见 F2_P6F_GATE_RESULTS.json）

## 六、这轮最值得记的

**D-60 是第三次出现同类缺陷**（D-46 是第一次，D-59 算近亲）。

它们的共同形态：**参数/开关存在，读起来像功能，但函数体里没有任何一处使用它。**
不报错、不崩溃，只是静默地什么都不做。

这类缺陷很难靠测试抓到——因为「不带参数」和「带参数但不生效」的输出完全一样。
唯一可靠的检查是：**每个新增开关都要有一条断言证明它在函数体里被读过。**
