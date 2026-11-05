# F2-P4A 检查点（中途落盘）

**基线**：db65ce7 · Crosswalk sha256 `42841207…` 已验证未变

## 已完成（可运行、已验证）

| 文件 | 状态 |
|---|---|
| `src/renderer/safe_html.py` | 完成。esc/clean_text/safe_url/document + CSP |
| `src/renderer/card_models.py` | 完成。五轴投影 + 措辞约束 + card_id |
| `src/renderer/card_renderer.py` | 完成。JSON + HTML + 阻断页 |
| `src/renderer/report_renderer.py` | 完成。A/B 多版本对照 |
| `src/renderer/pre_publish_check.py` | 完成。8 类检查，distribution 恒 False |
| `tools/f2p4a_e2e_preview.py` | 完成。4 场景产物已生成 |
| `tools/f2p4a_stats_audit.py` | 完成。自动汇总 |
| `tests/renderer/{rfx,test_cards(16),test_html_security(13)}.py` | 全过 |

## 已验证的真实验收

**浏览器实测**（Playwright，本地 HTTP，1920×1080）：
- overflowX = false（无横向溢出）
- scripts=0, iframes=0, imgs=0, eventAttr=0
- CSP 生效（default-src 'none'; script-src 'none'）
- 8 个语义 h2 齐全（裁决/新鲜度/审核/来源/证据/限制/分发门禁）

**多版本报告**：H2 显示两个不同 Commit（7fd1a60b… 与 bbbb…），
tables=1，无脚本、无事件属性、无横向溢出。

**产物**：`docs/preview/f2p4a/{s1_refuted,s2_supported,s3_partial,s4_multi}/`
每个含 rendered_card.json / knowledge_card.html / knowledge_report.html，
s1 另有 preview.png（1920×2036 视觉证据）。

## 已修的缺陷

**P3C §13 阶段追踪**：`RS.set_stage` **从未被调用** → 8 阶段全停在 PENDING。
已补：每阶段进入记 RUNNING、离开记 COMMITTED、失败记 FAILED_FATAL。
实测最终 run 八阶段全部 COMMITTED。P3C 142 项回归全绿。

**CSP 实体化**：原用 `esc(BASE_CSP)` 把引号变成 `&#x27;`（仍有效但不利核查），
改为常量内联。

## P3D 统计核实

清单算术和 **202**（24+20+22+18+17+15+22+16+22+26），报告写 **203**，差 1。
十验证器实跑全 exit 0 → **统计错误，非验证遗漏**。权威口径 `F2_P4A_STATS_AUDIT.json`。

## 尚未完成

1. `tests/renderer/test_read_only.py`（T-25..T-31）
2. `tests/renderer/test_multiversion.py`（T-13/T-14）
3. `tests/renderer/test_distribution_gates.py`（T-34/T-35）
4. `tools/f2p4a_verify.py`
5. 三份文档 + 账本 + 提交

## 关键设计（续跑必读）

- **不可信内容只能经 `esc()` 进模板**；结构由可信函数拼装
- `safe_url`：只允许 https + github.com/api.github.com/raw.githubusercontent.com 子域；
  拒绝 userinfo、端口≠443、路径含 `..`
- **预览许可 ≠ 分发许可**：`preview_allowed=True` 恒真，`distribution_allowed=False` 恒假
- `card_id` 只由视图内容 + schema + renderer 版本决定，时间戳不参与
- 阻断页：证据损坏/缺失时输出"无法生成可信知识卡片"，不生成半成品
