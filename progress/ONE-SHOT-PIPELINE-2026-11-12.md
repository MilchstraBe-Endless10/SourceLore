# 一条命令跑完整个知识库流程（固化，不再摸索）

## 为什么要这个

2026-11-12 之前的每次会话都在重新摸索：CLI 路径、store 构造、ingest 参数、
字段名、限流原因……这些已经全部查清，不该再摸索第二次。

## 标准流程（三条命令）

```bash
cd "/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore"

# 1) 补采文件正文（raw 通道，不受 GitHub API 限流影响）
python3 tools/capture_raw.py --repository-id <RID> --preset preact

# 2) 提取代码符号并入库（tree-sitter，走官方 ingest_source_facts）
python3 tools/extract_symbols.py --repository-id <RID>

# 3) 重新生成派生文档与卡片数据
python3 skill/sourcelore/scripts/sourcelore.py derive <RID>
```

## 验证（四项，全部有确定期望值）

```bash
CLI=skill/sourcelore/scripts/sourcelore.py

# ① 正文采集 + 字节完整性
python3 - <<'PY'
import sqlite3, hashlib, os, json
DR="/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data"
c=sqlite3.connect(os.path.join(DR,"kb.db"))
for (pj,) in c.execute("select payload_json from assets where asset_type='captured_blob_content'"):
    p=json.loads(pj); sha=p["content_sha256"].split(":")[-1]
    f=os.path.join(DR,"blobs",sha+".bin")
    ok = os.path.exists(f) and hashlib.sha256(open(f,'rb').read()).hexdigest()==sha
    print(p["repository_id"], p["file_path"], p["raw_byte_length"], "OK" if ok else "FAIL")
PY

# ② 代码符号
python3 $CLI query <RID> --type code --commit <SHA>
#   期望: symbols 非空, coverage_status=COVERED_BY_EXTRACTED_SOURCE

# ③ 正文查询
python3 $CLI query <RID> --type content --commit <SHA> --path README.md
#   期望: raw_byte_length 与 ① 一致, provenance_level=OBSERVED

# ④ 卡片数据
curl -s "http://127.0.0.1:<PORT>/api/dsh-sourcelore-cards/repocard?repository_id=<RID>"
#   期望: documents 非空, 每个 document 的 id 非空, sections[0].body 有真实正文
```

## 三仓库固定参数（不用再查）

| RID | 仓库 | Commit | preset |
|---|---|---|---|
| 24313173 | jonschlinkert/is-number | 98e8ff1da1a89f93d1397a24d7413ed15421c139 | is-number |
| 38923193 | sindresorhus/is-plain-obj | 666df7c10035f7e26f27ec214fe5ae3173435f34 | is-plain-obj |
| 42283287 | preactjs/preact | dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab | preact |

## 已知陷阱（都踩过，别再踩）

| 现象 | 真因 | 做法 |
|---|---|---|
| `query --type content` 报 MISSING_COMMIT | content 类型强制要求 `--commit` | 必须带 commit |
| `query --type code` 返回 0 行但源码已抓 | 没跑 `tools/extract_symbols.py`，`source_structure_observation` 资产不存在 | 先跑提取 |
| symbols 全 0 且 coverage=NOT_COVERED | 规则不认 CJS `module.exports=` 形态 | 已修（2026-11-12） |
| 树 `ROOT_ONLY` | GitHub API 配额 0/60 | raw 通道可用；递归树需 token 或等配额 |
| `bs.get_bytes` 取字节时 KeyError 'bytes' | 实际键是 `raw` | 用 `r["raw"]` |
| `parse_bytes` 返回 dict | 实际是 `(tree, status, diags)` 三元组 | 解包三元组 |
| `collect_symbols` 返回 list | 实际是 `(symbols, exports, diags)` | 解包三元组 |
| `ingest_source_facts` 报 'extraction_status' | 需逐文件 observation，含 extraction_status/evidence_ranges/parser_id | 见 tools/extract_symbols.py |
| `content_sha256` 直接拼路径找不到文件 | payload 里带 `sha256:` 前缀 | `.split(":",1)[-1]` |
| `document_id` 与 `id` | 数据是 document_id，客户端读 id | 插件已补别名 |
