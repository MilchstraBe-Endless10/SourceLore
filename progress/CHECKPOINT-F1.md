# F1 检查点（中断）

> 状态：**F1 未完成，停在数据提取之后。**
> 中断原因：模型输出预算熔断（连续 6 轮未产出正文），非项目阻塞。
> 恢复方式：手动压缩上下文后，按本文「恢复步骤」继续。

---

## 一、做到哪了

### 已完成

1. **F0 状态核验**（本轮开头）：
   - HEAD = `bb45ab1`，工作树干净
   - `c0877e0124551352e603d693158f8296ada08607` 与 `bb45ab1` 均存在且为 commit
   - `STATE`：`active_milestone=M1-FUSION-GATE`、`active_task=M1-FUSION-GATE`、
     `status=IN_PROGRESS`、`next_task=M1-FUSION-GATE-F1`、`blockers=[]`

2. **六源能力全量提取已完成**，实测结果：
   - UPSTREAM-01：15（C01–C15）
   - UPSTREAM-02：18（C01–C18）
   - UPSTREAM-03：27（C01–C27）
   - UPSTREAM-04：27（C01–C27）
   - UPSTREAM-05：28（C01–C28）
   - UPSTREAM-06：28（C01–C28）
   - **合计 143，与指令给的对照数一致**

3. **能力记录字段已确认**：`id` / `capability` / `mechanism` / `where` / `disposition` / `why`。
   六源字段结构一致，可直接机读，无需适配器。

### 未完成

- `docs/fusion/CAPABILITY_CROSSWALK.json` 未产出
- `docs/fusion/ABILITY_DECISIONS.md` 未产出
- 十项冲突裁决未撰写
- 自动化验收 13 项未跑
- TASKS/STATE/HANDOFF 未更新（当前仍指向 F1 待启动，实际已启动但未完成）
- 未创建 F1 提交

---

## 二、下一步是什么

严格按指令 §2–§7 执行：

1. 建立 143 → N 的映射，分配 `SL-CAP-0001` 起的稳定 ID
2. 每个原始 `(upstream_id, original_id)` 必须且只能映射一次
3. 每项填 12 个字段：`canonical_id` / `name` / `description` / `owner_module` /
   `upstream_refs` / `disposition` / `license_permission` / `dependencies` /
   `overlaps` / `v1_scope` / `evidence` / `unresolved`
4. 唯一模块归属，限于十个逻辑模块（Collector / Facts / Evidence-Claims / Product /
   Research / Lifecycle / Security / Renderer / Storage / DSH Adapter）
5. 十项冲突逐条裁决（清单见指令 §5）
6. 跑 §7 的 13 项验收
7. 更新账本 + 两次提交（审计 + SHA 回填）

---

## 三、卡在哪

**没有技术阻塞。** 六份 JSON 可读、字段齐、数量对得上。

实际阻塞只有一条：**当前会话上下文已耗尽**，模型输出预算熔断。
续跑必须在压缩后进行，否则会重复熔断。

---

## 四、已定下的关键约束（续跑时必须遵守）

从执行指令与 F0 结论继承，不要重新推导：

1. **143 是上游候选数，不是最终能力数。** 去重后必然减少；验收第 2 项要求动态核算 143，
   验收第 4 项要求 crosswalk 覆盖全部 143 项原始能力——两者不矛盾，指的是「原始全覆盖」。
2. **UPSTREAM-06 的 28 项全部无复制授权。** `license_permission` 必须独立于 `disposition`，
   只能记「仅参考设计」。禁止出现任何形式的文本移植。
3. **UPSTREAM-06 C06 必须记 `ADAPT`**（来源：F0 勘误 E-06）。保留逐跳证据定位要求，
   拒绝「无法验证即 FALSE_POSITIVE」的判否语义。无法验证的 Claim 归 `insufficient`。
4. **UPSTREAM-03 的 CC BY 4.0** 需保留来源、许可链接、署名状态与修改声明要求。
5. **名称相似但语义不同不得强行合并**（指令 §2 明文）。
6. **Manifest V2 的正式 Schema 留待 F2**，本轮只做能力归属与设计裁决。

---

## 五、已完成提取的原始能力清单（供续跑直接使用，无需重读 JSON）

### UPSTREAM-01（15 项，repo-analyzer-skill，MIT）
C01 REUSE fact-first 分层抽取 · C02 ADAPT repo_facts.json 单一事实契约 ·
C03 ADAPT 引用存在性校验 · C04 ADAPT 预算化代码采样 ·
C05 REUSE 入口点启发式 · C06 REUSE LLM provider 解耦（Protocol） ·
C07 ADAPT 单次调用 + 有界重试 · C08 ADAPT 树截断降级 ·
C09 ADAPT monorepo 支持 · C10 REUSE 报告 schema + markdown 渲染 ·
C11 ADAPT 提示词作为 markdown 资产 · C12 ADAPT 评测基线（gold + 确定性评分） ·
C13 REJECT 直接外部 LLM API 客户端 · C14 REJECT 多模型 judge 集成 ·
C15 REJECT 自建 GitHub REST 客户端

### UPSTREAM-02（18 项，deer-flow github-deep-research，MIT）
C01 ADAPT GitHub REST 端点清单与取数语义 · C02 REUSE get_tree 用 HEAD 让服务端解析默认分支 ·
C03 REUSE 原始内容直取（raw accept） · C04 ADAPT requests 可选依赖降级 ·
C05 REUSE 失败必须是异常而非写入数据通道 · C06 ADAPT 分页遍历与短页终止判据 ·
C07 REUSE Issue 列表排除 PR · C08 REJECT 仓库摘要聚合 summarize_repo ·
C09 REJECT 树格式化 format_tree · C10 REIMPLEMENT 四轮研究流程 ·
C11 ADAPT 查询策略 Broad to Narrow · C12 ADAPT 五层来源优先级 ·
C13 ADAPT 报告九节结构 · C14 ADAPT 来源分桶清单 ·
C15 REJECT 置信度三档百分比 · C16 ADAPT 强制内联引用规则 ·
C17 REJECT Mermaid 图表硬要求 · C18 REJECT 自建 GitHub REST 客户端

### UPSTREAM-03（27 项，repository-discovery，CC BY 4.0）
C01 REUSE 边界三分类 · C02 REUSE 集成指示符正则 + 必扫面清单 ·
C03 REUSE 显式未知优于自信猜测 · C04 ADAPT 观察/推理硬隔离 ·
C05 ADAPT Canonical Knowledge Registry · C06 ADAPT 产品模型八要素 ·
C07 ADAPT 十四步依赖序构建 · C08 ADAPT Rerun Protocol 九个触发点 ·
C09 ADAPT 未知项一等公民 · C10 ADAPT 来源冲突必须记录 ·
C11 ADAPT 置信度三档 High/Medium/Low · C12 ADAPT 二十条反模式清单 ·
C13 ADAPT 渐进发现（广度→具体） · C14 ADAPT Knowledge Refinement 十动作 ·
C15 ADAPT 写作风格与受众定义 · C16 REIMPLEMENT 业务实体建模 ·
C17 REIMPLEMENT 终止条件 · C18 REIMPLEMENT 十八条结构一致性检查 ·
C19 REIMPLEMENT Obsidian wiki link 校验 · C20 REIMPLEMENT 五条一致性规则 ·
C21 REIMPLEMENT 五十五问自检清单 · C22 REIMPLEMENT 主张措辞规则 ·
C23 REJECT 五档证据优先级 · C24 REJECT D2 图规范 ·
C25 REJECT 不得依赖 AST/图数据库/索引系统 · C26 REJECT 每术语独立成页 ·
C27 REJECT 百分比置信度豁免

### UPSTREAM-04（27 项，SNIKO swe-research，MIT）
C01 REUSE 可变层/不可变层分离 · C02 REUSE Subject 作为知识身份单位 ·
C03 REUSE 索引是派生视图禁止手改 · C04 REUSE 双通道检索 ·
C05 REUSE 按需加载的模式指引 · C06 REUSE 不存密钥/凭据/个人数据 ·
C07 ADAPT 证据三分法 · C08 ADAPT 外部探测存档清单 ·
C09 ADAPT Superseded 关系与保留历史 · C10 ADAPT Finding 四段结构 ·
C11 ADAPT verified-against 新鲜度字段 · C12 ADAPT 优先扩展而非新建 ·
C13 ADAPT 报告粒度禁令 · C14 ADAPT 产物命名与链接规范 ·
C15 ADAPT 自主权分级 · C16 ADAPT 完成检查 ·
C17 ADAPT 仓库影响面调查流程 · C18 REIMPLEMENT Reuse/Extend/Create 三态判定 ·
C19 REIMPLEMENT 知识失效检测 · C20 REIMPLEMENT Current understanding 演进史 ·
C21 REIMPLEMENT 冲突处理 · C22 REIMPLEMENT 并发写入保护 ·
C23 REIMPLEMENT 结构化查询能力 · C24 REIMPLEMENT 无法复现的外部观察标记 ·
C25 REJECT 一仓一 corpus 住仓库内 · C26 REJECT Research 必须产报告 ·
C27 REJECT HTML/excalidraw 等具体产物格式

### UPSTREAM-05（28 项，lazy-rabbit project-knowledge-base，Apache-2.0）
C01 REUSE 脚本优先/规则先行/零 token 前置 · C02 REUSE 三级更新梯度 L1/L2/L3 ·
C03 REUSE 旁车产物与叙事页分离 · C04 REUSE review_status 人机权限分离 ·
C05 REUSE 必须留 [NEEDS INPUT] 而非编造 · C06 REUSE Auto-generated 头与出处强制 ·
C07 ADAPT 命令族与编号页集 · C08 ADAPT Phase 0 三分路由 ·
C09 ADAPT PKB_ROOT 与项目分离 · C10 ADAPT 契约式 Postconditions ·
C11 ADAPT 回滚与降级路径 · C12 ADAPT 渐进式 AI 投喂 ·
C13 ADAPT C4 强制顺序 · C14 ADAPT 版本页脚七字段 ·
C15 ADAPT 发布节奏绑定 · C16 ADAPT 测试用例维护触发 ·
C17 REIMPLEMENT 过期检测机制 · C18 REIMPLEMENT 索引生成 ·
C19 REIMPLEMENT 人类主导的语义补充 · C20 REIMPLEMENT 保密切分与发布脱敏 ·
C21 REIMPLEMENT 冲突处理 · C22 REIMPLEMENT 并发写入保护 ·
C23 REIMPLEMENT 结构化查询 · C24 REIMPLEMENT 不可复现外部观察标记 ·
C25 REIMPLEMENT 测试覆盖作为质量证据 · C26 REJECT 知识库住在被分析仓库内 ·
C27 REJECT 产出面向人类的整册项目文档 · C28 REJECT 双语 Sphinx 站与 gettext

### UPSTREAM-06（28 项，Consensys repo-security-review，**无许可证**）
C01 ADAPT 两阶段信任边界（finder → judgment） ·
C02 REUSE 阶段间上下文卫生 · C03 REUSE Surface Gate ·
C04 ADAPT Boundary Gate · C05 REUSE 四节点数据流契约 ·
C06 REUSE→**必须改记 ADAPT** 不可验证即判否（E-06） ·
C07 ADAPT 验证状态机与 report_tier 映射 · C08 ADAPT 动态证据升级阶梯 + 每级同意 ·
C09 REUSE 环境失败绝不改判 · C10 REUSE 动态否证只降级到人工复核 ·
C11 REUSE 两份独立控制 + 结构性构造门 · C12 REUSE 失效安全门控 ·
C13 ADAPT Semgrep 三层规则集 + 本地缓存优先 · C14 REUSE 族扫描与诚实否定 ·
C15 ADAPT 依赖可达性三态 + 保守默认 + KEV 下限 · C16 REUSE P3b 有效严重度与优先级 ·
C17 ADAPT 密钥打码与原始输出清理 · C18 ADAPT 成本报告 ·
C19 REIMPLEMENT 多仓库拓扑与跨服务合成 · C20 ADAPT 延迟裁决与跨仓库解析 ·
C21 REJECT 模型分层 · C22 ADAPT Skill/Agent 指令安全（OWASP LLM Top 10） ·
C23 ADAPT 供应商采纳审计模式 · C24 REUSE PR diff 增量审查与移除控制回归 ·
C25 REIMPLEMENT 三态分离的产物契约 · C26 REIMPLEMENT 新鲜度与失效判定 ·
C27 REIMPLEMENT 密钥/数据分级 · C28 REJECT 一键安装外部扫描器

---

## 六、恢复步骤

```bash
cd '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore'
git log --oneline -3          # 应为 bb45ab1 / c0877e0 / b0c8e6d
git status --short            # 应为空
python3 -c "
import json
t=0
for i in range(1,7):
    A=json.load(open('progress/UPSTREAM-0%d-audit.json'%i))
    n=len(A['capability_matrix']); t+=n
    print('UPSTREAM-0%d'%i, n)
print('TOTAL', t)   # 必须打印 143
"
```

然后从本文「二、下一步是什么」第 1 步继续。

**不要重新读六份审计 JSON 的全文**——§5 的清单已经够用，只有需要 `mechanism` 细节时
才按需查单条。
