# F1-C-D3 · 七条零来源 canonical 质量总审

产物：`tools/fusion/f1c_d3_review.py` → `F1C_D3_ZERO_ORIGIN_REVIEW.json`

---

## 原则

零来源 canonical 是 **SourceLore 自有需求**，不是缺失来源的次品。
**不得为减少数量而补 `upstream_ref`**；若发现职责重复，**只记录合并方案与影响范围，不静默删除**。

---

## 逐条结论

### SL-CAP-0013 · Commit 与根 Tree 的钉定（三字段分列）— Collector

- **A 无 upstream_ref**：✓
- **B origin_type**：`INTERNAL_DESIGN_ONLY`
- **C 内部需求来源**：来自 F0 勘误 E-01/E-02/E-03——GitHub Trees API 以 commit-ish 为 ref 时回显请求标识，
  故 `commit_sha` / `root_tree_sha` / `tree_query_ref` 必须三字段分列。**这是本项目实测发现**，
  六源中没有任何一处给出三字段分离的定义。
- **D 独立职责**：取数层的身份钉定。上游索引表只有四列，既无内容哈希也无版本链。
- **E 与既有重复**：无。与 SL-CAP-0012 是「解析」与「钉定」两段（BASELINE 已记录该关系）。
- **F owner 唯一**：Collector
- **G 依赖**：消费 Facts 的仓库身份（SL-CAP-0040 / 0063）
- **H V1 范围**：三字段契约已定；`snapshot_manifest_v2` 实现留 F2
- **I 虚构来源**：无
- **J F2 验收**：三字段不得互换；`root_tree_sha` 必须取自 `GET /commits/{ref}` 的 `commit.tree.sha`
- **结论：PASS**

### SL-CAP-0019 · 统一只读数据接口 — Collector

- **A** ✓　**B** `INTERNAL_DESIGN_ONLY`
- **C 需求来源**：六源各自的取数方式互不兼容（有的用 tar.gz、有的用 files.tsv、有的用 Trees API），
  必须收束成单一只读接口，否则 Facts 无法统一消费。
- **D 独立职责**：取数通道抽象。没有任何上游提供这一层。
- **E 重复**：无。与 SL-CAP-0013 是「接口」与「字段语义」的分工。
- **F** Collector　**G** 被 Facts / Research / Security 消费
- **H** V1 契约已定；具体端点留 F2
- **I** 无　**J** 所有取数必须经此接口，不得各模块自行直连
- **结论：PASS**

### SL-CAP-0045 · 外部可变来源的新鲜度与不可复现观察保留 — Lifecycle

- **A** ✓　**B** `INTERNAL_DESIGN_ONLY`
- **C 需求来源**：Issue/PR 等外部来源**会变化且不可复现**——同一 URL 两次抓取内容可能不同，
  而 commit 级快照可复现。这一区分六源均未处理。
- **D 独立职责**：可变来源的时效语义与观察留痕。
- **E 重复**：与 SL-CAP-0042（哈希失效）不同——0042 针对**仓库文件**，本条针对**外部可变来源**。
- **F** Lifecycle　**G** 消费 Collector 的采集时刻；被 Research 引用
- **H** V1 语义已定；保留期限留 F2
- **I** 无　**J** 每条外部材料必须带 `retrieved_at`，且不得与 `verified_against_commit` 混同
- **结论：PASS**

### SL-CAP-0047 · 安全发现契约与四项独立检查（证据分级）— Security

- **A** ✓　**B** `INTERNAL_DESIGN_ONLY`
- **C 需求来源**：U06 的机制形状可参考但**不能复制实现**（无许可证），必须自建工具无关的发现契约。
- **D 独立职责**：安全发现的证据分级与四项检查的独立性。
- **E 重复**：与 SL-CAP-0053（分级/脱敏/门禁）不同——0053 管**产物发布**，本条管**安全发现本身**。
- **F** Security　**G** 消费 Collector 的仓库快照；被 Renderer 呈现
- **H** V1 契约已定；四项检查的实现留 F2
- **I** 无　**J** 四项检查必须独立可判；不得因一项通过就推定其余通过
- **结论：PASS**

### SL-CAP-0061 · 呈现安全转义与发布前检查 — Renderer

- **A** ✓　**B** `INTERNAL_DESIGN_ONLY`
- **C 需求来源**：Renderer 生成 HTML/SVG 派生视图时，仓库内容可能含注入载荷。
  上游的文档流水线未把转义当作安全边界。
- **D 独立职责**：呈现层的转义与发布前检查。
- **E 重复**：与 SL-CAP-0053 的关系是「Security 定分级与门禁语义、Renderer 执行转义」，
  K-4 已记录该边界，非重复。
- **F** Renderer　**G** 消费 Security 的分级；产出 D 层产物
- **H** V1 规则已定；转义实现留 F2
- **I** 无　**J** 任何来自仓库内容的字符串进入派生视图前必须转义；未转义即不得发布
- **结论：PASS**

### SL-CAP-0063 · 身份层级与版本标识（三种身份分离）— Storage

- **A** ✓　**B** `INTERNAL_DESIGN_ONLY`
- **C 需求来源**：四层模型（SL-CAP-0062）落地必须有主键契约。六源中没有任何一处给出
  「逻辑身份 / 内容哈希 / 业务版本」三者分离的存储层定义——上游索引表只有四列，
  `summary` 被要求不含结论，既无内容哈希也无版本链。
- **D 独立职责**：存储层的身份分配与永不复用保证。
- **E 重复**：与 SL-CAP-0040 的关系是「语义定义 vs 存储分配」，M-B 已明确该边界，非重复。
- **F** Storage　**G** 消费 Lifecycle 的 Subject 语义；被全部模块引用
- **H** V1 契约已定；主键格式留 F2
- **I** 无　**J** 三种身份不得混用；逻辑身份一旦分配永不复用
- **结论：PASS**

### SL-CAP-0073 · 与九模块的能力编排接口（逻辑契约）— DSH-Adapter

- **A** ✓　**B** `INTERNAL_DESIGN_ONLY`
- **C 需求来源**：九个模块各有 canonical，必须有一个逻辑编排层说明它们如何被一次任务调用串起来。
  六源都是单一 skill，不存在跨模块编排需求。
- **D 独立职责**：跨模块编排的逻辑契约（不复制实现）。
- **E 重复**：与 SL-CAP-0068（Skill 入口）/ 0071（检查点）分工明确——0068 管加载、0071 管恢复、本条管编排。
- **F** DSH-Adapter　**G** 消费全部九模块的能力声明
- **H** V1 只定逻辑契约；实现形态（进程内/子进程/MCP）留 F2（Y-5）
- **I** 无　**J** 编排不得绕过各模块的 owner；不得在编排层复制模块约束
- **结论：PASS**

---

## 汇总

| 项 | 值 |
|---|---|
| 零来源 canonical 总数 | **7** |
| PASS | **7** |
| 按 owner 分布 | Collector 2、Lifecycle 1、Security 1、Renderer 1、Storage 1、DSH-Adapter 1 |

**未发现职责重复。** 每条都解决了现有 canonical 未覆盖的独立职责，
且与相邻 canonical 的边界已在 F1-B 的 M-* / K-* / Y-* 表中登记。

**未虚构任何 upstream_ref。** 七条的 `upstream_refs` 全部为空、`origin_type` 全部 `INTERNAL_DESIGN_ONLY`。
