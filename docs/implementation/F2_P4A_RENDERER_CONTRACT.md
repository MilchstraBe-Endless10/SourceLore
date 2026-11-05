# F2-P4A · 安全渲染引擎契约

产物：`F2_P4A_E2E_PREVIEW.json`、`F2_P4A_VERIFICATION.json`、
`F2_P4A_GATE_RESULTS.json`、`F2_P4A_STATS_AUDIT.json`、`F2_P4A_EXECUTION_REPORT.md`
预览：`docs/preview/f2p4a/`（4 个场景，每场景 3 个文件）

**结论：`SAFE_RENDERER_CORE = DONE`；`LOCAL_VISUAL_PREVIEW = DONE`（含浏览器实测）。
`DISTRIBUTION_READY` 保持 `NOT_READY`；`FULL_RENDERER` 未启动。**

---

## 1. 输入与输出

**输入**：只接受校验过的 `KnowledgeView`（P3D 的输出）。
渲染器**不读数据库表**、**不自行拼接裁决**、**不重新验证据**。

**输出**（三种，均为本地内部预览产物）：

```
rendered_card.json      结构化卡片描述（确定性 JSON，键排序）
knowledge_card.html     单卡片，无 JS，可浏览器直接打开
knowledge_report.html   多版本对照报告
```

不写入人工文档、不写入权威知识库、不构成正式发布。

---

## 2. 卡片结构（七个区域）

| 区域 | 内容 |
|---|---|
| A 标题与范围 | 命题描述、repository_id、**完整 Commit**、Claim 类型、范围声明 |
| B 证据裁决 | `supported`/`refuted`/`insufficient_evidence` 原样 + 含义说明 + 规则版本 |
| C 新鲜度 | 状态、含义、当前适用性、观测 Commit/时间 |
| D 人工审核 | 真实 `review_status`；非 approved 时明确提示 |
| E 来源与授权 | 来源等级、判定依据、混合来源标记、授权类别、TEST_ONLY 显式面板 |
| F 证据与历史 | Fact/Snapshot 引用、覆盖范围、`history_refs` 关系 |
| G 限制与分发门禁 | 每条 limitations、B-1/B-2/B-3 表 |

**范围声明固定为**："本卡片只描述 <Commit> 这一个固定 Commit 上的命题，
不代表该仓库的当前最新状态。"

---

## 3. 措辞约束（严格忠实）

```
supported            → "在指定范围内，现有经过验证的证据支持该命题。"
refuted              → "现有有效反证与该命题矛盾。"
insufficient_evidence→ "证据不足，无法作出支持或反驳裁决。"
POSSIBLY_STALE       → "所跟踪版本已经变化，旧结论对该 Ref 的当前适用性有待核查。
                         这不表示旧结论已经失效或错误。"
TEST_ONLY            → "本卡片由隔离测试授权（TEST_ONLY）产生，
                         未通过真实平台授权验收，不代表生产环境结论。"
```

**禁用短语**（`card_models.check_wording` 强制，命中即抛错）：

```
完全正确 / 整个项目存在问题 / 该软件正确 / 肯定不存在 /
已证明错误 / 必然无效 / 当前最新 / 当前有效 / 已发布
```

---

## 4. HTML 安全

**唯一入口**：`safe_html.esc()` → `html.escape(quote=True)`。
结构由可信模板函数拼装，不可信数据只作为转义后的文本进入。

防护清单（逐项有负向测试）：

| 威胁 | 处理 |
|---|---|
| HTML 标签注入 | 全部实体化（`&lt;` `&gt;`） |
| 属性注入 | 引号实体化（`&quot;` `&#x27;`） |
| script / iframe / object / embed / svg / math | 全部实体化，无 `<` 可执行 |
| onerror / onclick 等事件属性 | 无法生成（属性位无 `on*=`） |
| `javascript:` / `data:` / `vbscript:` / `file:` | `safe_url` 返回 `None` |
| 外部资源 | 无 `<link>`、无外链 CSS、无 `<img>`、无 `@import` |
| Markdown 原标签 | 不做 Markdown 转换，一律按纯文本转义 |
| 路径穿越 | `safe_url` 拒绝含 `..` 段 |
| 超长文本 | `clean_text` 截断（text 4000 / path 240）并标注"已截断" |
| 控制字符 / 双向文本符 | 剥离 C0/C1、U+200B–200F、U+202A–202E、U+2066–2069、BOM |
| 外观伪造 | NFC 归一化 |

**CSP**（内联 meta，模块内可信常量，不做实体转义）：

```
default-src 'none'; style-src 'unsafe-inline'; img-src data:;
script-src 'none'; object-src 'none'; frame-src 'none';
form-action 'none'; base-uri 'none'
```

**URL 白名单**：只允许 `https` + `github.com` / `api.github.com` /
`raw.githubusercontent.com`（含子域）；拒绝 userinfo、端口≠443、`..`。
不可验证时输出 `<span class="plain-url">` 纯文本，**不产生 `<a>`**。

---

## 5. 视觉规范

- 最大宽度 1040px，窄屏 `@media(max-width:720px)` 降级为单列
- 全部 `word-break: break-word|break-all`，SHA 与路径可安全换行
- 系统字体栈（`-apple-system`/`Segoe UI`/`Noto Sans CJK SC`/`Microsoft YaHei`），无外部字体
- 语义化 `h1/h2/h3/dl/ul/table`，键盘可读顺序
- **状态不只靠颜色**：每个 badge 同时显示文字（`supported`/`refuted`/`pending_review`）
- 无横向溢出（浏览器实测 `overflowX=false` @1920×1080）

---

## 6. 确定性

```
card_id = SL-CARD- + H(view_id, verification_status, claim_commit_sha,
                       review_status, freshness_state, current_applicability,
                       provenance_level, authorization_class,
                       card_schema_version, renderer_version)[:32]
```

- JSON 键排序固定
- 证据引用排序固定
- 报告内部按 `commit_sha` 排序，**传入顺序无关**
- `assembled_at` 只进页脚诊断，**不参与身份**
- 同输入重复渲染逐字节一致

---

## 7. 阻断策略

证据链损坏 / 来源缺失时**不生成半成品卡片**，改为输出：

```
<h1>无法生成可信知识卡片</h1>
阻断 <错误码>
为什么不显示结论（三条说明）
```

阻断页**不含任何裁决徽章、不含裁决措辞**（有测试断言）。

---

## 8. 分发前检查

`pre_publish_check(rendered_artifact, source_view, restrictions)` 检查 8 类：

```
ARTIFACT_IS_TEST_ONLY          产物由隔离测试授权产生
SYNTHETIC_PROVENANCE           来源为合成夹具
EVIDENCE_CORRUPT               证据冲突
UNDISPLAYED_LIMITATIONS        限制未在产物中展示
DISTRIBUTION_GATE_OPEN         分发门禁仍 OPEN
UNTRUSTED_EXTERNAL_RESOURCE    含外部资源写法
FALSE_CURRENT_CLAIM            错误宣称当前有效
THIRD_PARTY_EXPRESSION         复制受保护第三方表达
```

返回值固定：

```
preview_allowed      = True    （本地内部预览允许）
distribution_allowed = False   （★ 本轮恒为 False）
publish_blocked      = True
```

**`preview_allowed=true` 不等于 `distribution_allowed=true`。**
即使所有 Claim 都 supported、审核都是 approved，分发仍被拒绝（有测试）。

---

## 9. 输出目录约束

固定写入 `docs/preview/f2p4a/<scenario>/`。

**禁止重叠**：`docs/fusion/`、`progress/`、知识数据库、Checkpoint 数据库、原始仓库目录。
渲染器模块本身**不含任何文件写入代码**（写文件只发生在 `tools/f2p4a_e2e_preview.py`）。

---

## 10. 明确不做

- 不实现 Research 推理
- 不调用 LLM 生成知识结论
- 不实现 Web 服务
- 不创建对外 Skill
- 不自动发布
- 不改 A/B/C 层、不改人工文档、不自动批准 Claim
- 不关闭许可证门禁
- 不修改 F1-D 冻结基线
