# F1-D 检查点（已完成）

## 冻结判定

**`FROZEN_INTERNAL_RESTRICTED`** — 内部设计基线已冻结；
公开分发未获许可；产品实现尚未开始；F2 需独立批准。

## 正式产物

- `docs/fusion/CAPABILITY_CROSSWALK.json` — sha256 `42841207b8088c89…`，355,795 字节
- `docs/fusion/F1D_FREEZE_MANIFEST.json` — 20 份输入语义哈希 + 冻结判定
- `docs/fusion/F1D_F2_ENTRY_GATES.json` — 42 条（impl 39 / dist 3 / freeze 0）
- `docs/fusion/F1D_FREEZE_REPORT.md`
- `docs/fusion/F1D_VERIFICATION.json` — 26/26

统计：143 身份（含 4 项未映射拒绝）/ 75 canonical / 21 amendment；
MAPPED 139 · ROUTED 0 · UNREVIEWED 4；终态 122/17/4/0。

## 工具

`f1d_build_freeze.py`（确定性构建，`--out` 支持隔离重建）
`f1d_verify.py`（26 条，不 import 任何批次验证器）
`f1d_entry_gates.py`（F2 准入生成）
`f1d_freeze_state.py`（**共享冻结状态判定**，供历史验证器复用）

## ★★ 两条必记的设计决定

1. **哈希口径分离**：产物用字节哈希；输入用语义哈希（剔除 `generated_at`）。
   混用会导致假失效。
2. **「不得提前冻结」是历史时点断言**：`f1d_freeze_state.freeze_state()` 判定
   「不存在」或「存在且 manifest 合法」均通过；**存在但无合法 manifest = 无记录冻结 = 失败**。

## ★ 三处踩坑（其中两处是重犯）

1. **tuple-newline**（12 处）：写完验证器必须跑正则自检。
2. **正则跨函数误伤**：前批已记录，本批又犯。跨函数修改一律按唯一旧串或行号。
3. **哈希函数改了调用方没改**：20 份全误报。

## 下一步：F2（未执行）

Y6-P1..P6 → X-5 崩溃注入/并发 → 各模块实现门禁。

## 恢复命令

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore' \
  && git log --oneline -2 && git status --short \
  && python3 tools/fusion/f1d_verify.py | tail -2
```

检索词：F1-D checkpoint freeze。
