# F2-P5I 执行报告

**基线** `11cbb26`

## 结论

SourceLore 现在能结合**固定 Commit 中已验证的源码与 tsconfig/package.json**，解释 JS/TS 模块引用的静态配置关系，形成可追溯知识资产，并由安装版 Skill 查询与展示。

流程：`验证源码 Blob → Import Fact → 验证配置 Blob → Config Observation → 有界解析 → Module Relation Fact → EC 裁决 → 查询 → 关系卡片`

## 一、配置来源与完整性

配置只能通过 `repository_id + commit_sha + path + blob_oid + content_asset_id` 定位。**不读工作目录**，不借用其他 Commit，不假定「仓库没有 tsconfig」。

未采集 → `CONFIG_CONTENT_NOT_CAPTURED`。

## 二、JSONC 解析

字符状态机，**非正则**。必须这样做，因为 `"https://example.com"` 与 `"text // not a comment"` 都是合法字符串。

覆盖：单行/多行注释、尾随逗号、转义、字符串内注释符号、BOM、CRLF、超限、未闭合、非对象顶层。

## 三、paths 匹配

优先级按 **TypeScript 实际规则**，不是配置文件出现顺序：

```
精确 @config  (rank 0)
  > 通配 @lib/*  (前缀 5)
  > 通配 @/*     (前缀 2)
  > *           (前缀 0，兜底)
```

`baseUrl` 缺失时基准是**配置目录**，绝不默认项目根——这是 monorepo 正确性的关键。

多目标按数组顺序回退，第一个命中即止。

## 四、extends / references

只支持**同仓库同 Commit 的本地配置**。检测循环、限制深度（8 层）。

`extends` 指向 npm 包或绝对路径 → `CONFIG_INHERITANCE_UNRESOLVED`，不假装继承完成。

`references` 仅识别，不构建 Project References 图。

## 五、Monorepo

同一 alias 在 `packages/a` 与 `packages/b` 指向不同文件，实测隔离正确。

归属不确定 → `CONFIG_NOT_CAPTURED`，**不随意选一个 tsconfig**。

## 六、package.json

- `imports`（`#xxx`）同包作用域解析
- `exports` self-reference 根与子路径
- **未列出子路径 → `SUBPATH_NOT_IN_EXPORTS`**（不据文件存在放行）
- `null` → `EXPORT_EXPLICITLY_BLOCKED`
- 通配 `./feat/*` 正确展开

## 七、条件导出

`default` 是**兜底**：仅在无 import/require 可用时生效。

多条件同时可用 → `MULTIPLE_CONDITIONS_AVAILABLE`，**不任选**。未知自定义条件 → `NO_MATCHING_CONDITION`。

## 八、三层状态

| 层 | 状态 |
|---|---|
| 1 | `MODULE_REFERENCE_OBSERVED` |
| 2 | `CONFIG_MAPPING_CANDIDATE` |
| 3 | `LOCAL_MODULE_RESOLVED` |

**不存在 `RUNTIME_IMPORT_VERIFIED`**——本工具不验证运行时加载。

## 九、实测

```
写入：Commit A(3 关系) / Commit B(3 关系)
查询 A：RELATIONS_FOUND rels=3 resolved=3 net=0
  @/utils              @/*  → src/utils.ts
  @/components/Button  @/*  → src/components/Button.tsx
  @/types              @/*  → src/types.ts
查询 B：→ lib/utils.ts / lib/components/Button.tsx / lib/types.ts
卡片：SOURCE_MODULE_RELATION_CARD 5003 字节 ×2
安装版 CLI：rels=3 resolved=3 net=0；--module 过滤生效
```

## 十、五个真缺陷

**D-29 `default` 条件被当普通条件拦截。** `k in available_conditions` 直接跳过它，
导致「只有 default 没有 import/require」时永不解析。default 必须在循环外作兜底。

**D-30 package 通配目标未展开。** `./src/feat/*.js` 里的 `*` 没被替换成捕获值，
命中判断恒失败。补 `_subpath_capture`。

**D-31 关系事实缺 `subject` 键。** `dict(subject, **{...})` 把字段铺平了，
但查询与裁决都读 `np["subject"]` → 恒空。这是**写入端与读取端契约不一致**，
测试只在读取侧暴露。

**D-32 查询结果缺 `rule_id` / `repository_id`。** 裁决端第一道检查就是 `rule_id`。

**D-33 查询模块依赖 `paths` 但未加该路径。** 独立调用直接 `ModuleNotFoundError`。

---

## 十一、验证

```
runtime45 storage53 collector48 facts44 EC36 lifecycle142
views50 renderer59 research122 skill_interface69 content77
blob_capture59 content_persistence63 content_skill49
source_analysis88 js_ts_analysis72 module_resolution147
= 1223 项，失败 0（保留原 1076 + 新增 147）
f1d 26/26
Crosswalk 42841207… 未变
```

## 十二、门禁

| 门禁 | 状态 |
|---|---|
| A_CONFIG_BLOB_INTEGRITY | **DONE** |
| B_TSCONFIG_JSONC | **DONE** |
| C_TSCONFIG_PATHS | **DONE** |
| D_TSCONFIG_INHERITANCE | **DONE** |
| E_PACKAGE_IMPORTS | **DONE** |
| F_PACKAGE_EXPORTS | **DONE** |
| G_RESOLUTION_POLICY | **DONE** |
| H_CONFIG_EVIDENCE | **DONE** |
| I_MODULE_RELATION_FACTS | **DONE** |
| J_MODULE_RELATION_CLAIMS | **DONE** |
| K_MODULE_RELATION_QUERY | **DONE** |
| L_MODULE_RELATION_CARDS | **DONE** |
| M_INSTALLED_SKILL_E2E | **DONE** |
| N_MULTI_COMMIT_CONFIG_ISOLATION | **DONE** |
| O_EXISTING_SOURCE_REGRESSION | **DONE** |
| P_REAL_GITHUB_MODULE_E2E | **NOT_VERIFIED** |
| Q_NATURAL_LANGUAGE_AUTO_TRIGGER | **NOT_VERIFIED** |
| R_DISTRIBUTION_READY | **NOT_READY** |

证据级别分开报：`CONFIG_PARSED` DONE ／ `CONFIG_MAPPING_FOUND` DONE ／
`LOCAL_FILE_CANDIDATE_VERIFIED` DONE ／ `MODULE_RELATION_FACT_PERSISTED` DONE ／
`CLAIM_VERIFIED` DONE ／ `INSTALLED_SKILL_E2E` DONE ／ `REAL_GITHUB_E2E` **NOT_VERIFIED**

## 十三、尚未实现

npm 包内 `extends`；完整 Node.js 条件解析；`tsconfig references` 的构建图；编译输出路径映射；
TypeScript 的 `.js`→`.ts` 扩展名替换规则。

## 十四、下一批建议

先做 `tsconfig references` 的项目归属，再做编译输出映射——两者都依赖更完整的 TypeScript 配置模型。
