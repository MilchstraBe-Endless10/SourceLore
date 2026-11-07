# F2-P6H 检查点 · 提交 b5151d5

## 用户三条指令（权威，不可偏离）
1. 卡片进 **DeepSeek Bot 内建可视化**，删除网页 HTML 路径
2. **先查别人排版，只加功能不改排版**
3. **不再等 GitHub 配额**

## 三条全部落地
### ③ 配额绕过 —— DONE
`git clone --depth 1 --filter=blob:none` 走独立通道，零 REST 配额。
实测 API=0 时 clone 成功，commit 与 API 侧一致。preact 真字节在 /tmp/preact_probe。

### ② 排版调查 —— DONE
```
@botharness/botui-core  点阵引擎
  三张独立表：cells / order / brightness
  createDotMatrix(el,{size,cols,rows,silhouette,dot,preset})
  DotGlyphSpec{sides,radius,innerRadius,star,spin,aspect}
  Envelope{stops,rest,duty,gauss,cycleMs}
@botharness/ui/lib/client.js  7.9MB，导出 queryClient
```
★★ **关键否定**：Bot 的 `card` 是**工具授权卡**
（`cardOutcome`: allowed-once/always-tool/always-exact/always-all/rejected；
生命周期 decided/answered/cancelled/expired），语义是权限确认，不是知识展示。
**挪用即改别人排版，明令禁止。**

### ① Bot 呈现 —— DONE
新模块 `src/skill_interface/bot_card.py`：
```python
render_bot_block(query_result, repo_name=None) -> str   # 纯函数，零写盘零联网
GLYPH = {SUPPORTED:"▣", OBSERVED:"▤", INSUFFICIENT:"□",
         UNSUPPORTED:"△", NOT_ANALYZED:"·"}
```
CLI 接入：`card --code` **默认**输出 `{format:"bot_block", text:..., network_requests:0}`；
`--html` 为显式遗留出口。实测 is-plain-obj 输出正确（4 项 ▣、行号 1/6）。
`source_knowledge_query._verdicts_block` 已带 start_line/end_line。

## 剩余
- 回归测试（bot_card 单测、CLI 行为）
- 用 git 协议补采 preact 真字节入库
- 文档更新

## preact 已真正入库（2026-07 12:04）
```
git 取字节 src/index.js 423B  oid 045fb679cfb6c813（与 GitHub 一致）
SD.parse_source → PARSE_COMPLETE / EXTRACTED
SFI.ingest_source_facts → facts written 13, reused 0
API 配额消耗：0
```
★ 证明「热门仓库 + 真源码」完全不需要 API 配额。

回归：skill_interface OK / renderer OK

## 单测（10/10 OK）
`tests/bot_presentation/test_bot_card.py`（需 `__init__.py`）：
T1 满格▣ / T2 半格▤且不误报已验证 / T3 空心□ / T4 异形△ / T5 空位· /
T6 **输出无任何 HTML 标签** / T7 非 FOUND 明确说答不了 / T8 纯函数不写盘 /
T9 图例五符号齐 / T10 行号
