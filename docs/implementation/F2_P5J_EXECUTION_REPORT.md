# F2-P5J 执行报告

**基线** `9433e43`

## 结论

SourceLore 现在能识别固定 Commit 中的 TypeScript 项目、解释项目间的 `references` 关系、
判断源码文件在受支持配置规则下的项目归属，并保存为可追溯知识资产，由安装版 Skill 查询与展示。

## 一、Node 条件键顺序修复（前置回归）

原实现把「多个条件同时可用」一律判 `MULTIPLE_CONDITIONS_AVAILABLE`，这**违反 Node 规范**。

规范要点：条件是**按配置对象键的原始顺序**匹配；`default` 是**始终匹配**的通用条件。

重写后实测：

```
default 在前 {default,import} + import 可用 → ./fallback.js（default 先命中）
default 在后 {import,default} + import 可用 → ./esm.js
多条件同时可用 {import,node,require}      → 按序取 import
null 值                                   → EXPORT_EXPLICITLY_BLOCKED
types 未列入条件集合                       → 不命中 types
```

## 二、项目发现

只认 **`tsconfig.json` / `jsconfig.json`**（标准命名）。

这一条是修 D-38 时确立的：被 `extends` 引用的 `base.json` **不是独立项目**。
最初我把所有出现在 Tree 里的配置都当项目，结果 `base.json` 带着自己的 `include`
抢走了子项目的文件归属。

## 三、extends 语义（关键区分）

| 字段 | 随 extends 继承 |
|---|---|
| `files` / `include` / `exclude` | **是**（子配置有则覆盖） |
| `references` | **否** |

这是本轮最容易搞反的一点。TS 文档明确 `references` 不继承，但 `include` 会继承。
我第一版把三个字段都当"子配置专属"，导致 T16 失败——那个测试救了这条语义。

## 四、references 解析

支持目录目标（自动找 `tsconfig.json`/`jsconfig.json`）与具体文件目标。
循环检测、深度上限 8、越界拒绝（`PROJECT_REFERENCE_OUTSIDE_REPOSITORY`）。

`PROJECT_REFERENCE_TARGET_VERIFIED` 只表示**目标配置已验证存在**——
不代表 B 已构建、不代表 A 已使用 B 的产物。

## 五、files / include / exclude

| 规则 | 语义 |
|---|---|
| `files` 显式列出 | 优先于 include，**不受 exclude 影响** |
| `exclude` | **只过滤 include 扫描**，不是绝对排除 |
| `files: []` | **不触发默认扫描**（显式空数组 = 无输入文件） |
| 两者都未声明 | 默认递归扫描（`allowJs=false` 时排除 .js/.jsx） |

**`INPUT_EXCLUDED_FROM_INCLUDE` ≠ 「不可能进入 TypeScript Program」。**
这两个状态名本身就是判据——我特意没让任何状态带 `NEVER` 或 `NOT_IN_PROGRAM` 字样。

支持的模式子集：`src/**/*.ts`、`src/*.tsx`、精确路径、`*.d.ts`。
不支持 `{a,b}`、`!` 取反、绝对路径、多重 `**` → `UNSUPPORTED_SELECTION_RULE`。

## 六、归属状态

8 种状态各自独立。**只有前三者构成归属候选**：
`INPUT_EXPLICITLY_LISTED` / `INPUT_MATCHED_INCLUDE` / `INPUT_EXCLUDED_FROM_INCLUDE`。

`INPUT_POSSIBLE_VIA_IMPORT` 只是"可通过 import 进入"，**不是本项目归属**——
D-40 就是把它误当候选，导致一个文件报出 3 个项目。

## 七、项目上下文

唯一可验证 → `PROJECT_CONTEXT_SELECTED`；多候选 → `PROJECT_CONTEXT_AMBIGUOUS`（**不任选**）。

## 八、实测

```
A：3 项目（app/core + solution-style 根），2 条引用均 VERIFIED，3 条归属
   packages/app/src/main.ts → INPUT_MATCHED_INCLUDE（唯一）
B：4 项目（多出 packages/util），关系独立不覆盖
安装版 CLI：projects=3 solution=1 refs=2 net=0
```

## 九、八个真缺陷

**D-34 条件多可用被误判歧义。** 违反 Node 规范。

**D-35 null 值未触发阻断。** null 进入递归后被当普通空值忽略。

**D-36 候选清单被提前 return 截断。** 命中后立即返回，其余键全丢。

**D-37 `lstrip('./')` 吞掉绝对路径与越界。** `"/abs/**"` 变成 `"abs/**"`，
`"../../etc"` 的越界前缀被吃掉——安全检测直接失效。这是**安全相关**缺陷。

**D-38 extends 基础配置被登记为独立项目。**

**D-39 files/include/exclude 未随 extends 继承。** 违反 TS 语义。

**D-40 归属候选包含了"可能通过 import 进入"。**

**D-41 裁决绑定字段名与事实字段名不一致**（`expected_state` vs `state`）。

## 十、验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77
blob_capture59 content_persistence63 content_skill49
source_analysis88 js_ts_analysis72 module_resolution148 ts_projects136
= 1360 项，失败 0（保留原 1223 + 新增 137）
f1d 26/26
Crosswalk 42841207… 未变
```

## 十一、门禁

| 门禁 | 状态 |
|---|---|
| A_NODE_CONDITIONAL_ORDER_REGRESSION | **DONE** |
| B_TS_PROJECT_CONFIG_DISCOVERY | **DONE** |
| C_TS_PROJECT_REFERENCE_RESOLUTION | **DONE** |
| D_TS_PROJECT_REFERENCE_EVIDENCE | **DONE** |
| E_TS_FILES_SELECTION | **DONE** |
| F_TS_INCLUDE_EXCLUDE_SEMANTICS | **DONE** |
| G_TS_CONFIG_INHERITANCE_SEMANTICS | **DONE** |
| H_TS_SOLUTION_STYLE_PROJECTS | **DONE** |
| I_TS_MONOREPO_MEMBERSHIP | **DONE** |
| J_TS_PROJECT_CONTEXT_RESOLUTION | **DONE** |
| K_TS_PROJECT_FACT_PERSISTENCE | **DONE** |
| L_TS_PROJECT_CLAIM_VERIFICATION | **DONE** |
| M_TS_PROJECT_RESEARCH_QUERY | **DONE** |
| N_TS_PROJECT_KNOWLEDGE_CARDS | **DONE** |
| O_INSTALLED_SKILL_TS_PROJECT_E2E | **DONE** |
| P_MULTI_COMMIT_PROJECT_ISOLATION | **DONE** |
| Q_EXISTING_SOURCE_REGRESSION | **DONE** |
| R_REAL_GITHUB_TS_PROJECT_E2E | **NOT_VERIFIED** |
| S_NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** |
| T_DISTRIBUTION_READY | **NOT_READY** |

证据级别：`PROJECT_REFERENCE_DECLARED` / `PROJECT_REFERENCE_TARGET_VERIFIED` /
`FILE_INPUT_SELECTION_OBSERVED` / `PROJECT_MEMBERSHIP_CANDIDATE` / `PROJECT_CONTEXT_SELECTED` 全部 DONE；
**`RUNTIME_MODULE_VERIFIED` 不是本轮可授予的能力。**

## 十二、仍不支持

npm 包内 `extends`；完整 Node 条件解析（自定义条件集合）；`tsconfig references` 的构建图；
编译输出路径映射；`.js`→`.ts` 扩展名替换；`resolveJsonModule` / `allowJs` 的完整模拟。

## 十三、下一批建议

`typescript` 的 `paths` 与项目归属已经有基础，下一步可以做**编译输出映射**
（`rootDir` + `outDir` + `declarationDir` 的静态路径推演），仍不执行编译器。
