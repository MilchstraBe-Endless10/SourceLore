# F2-P6B 检查点 · 基线 1b1426c

## 限流诊断（2026-11-06 13:20:53 UTC+8）
```
GET https://api.github.com/rate_limit  → HTTP 200（该端点不计费）
X-RateLimit-Limit:      60
X-RateLimit-Remaining:  0
X-RateLimit-Used:       60
X-RateLimit-Resource:   core
X-RateLimit-Reset:      1793942591 → 2026-11-06T05:23:11Z（= 13:23:11 +08）
Retry-After:            无
X-GitHub-Request-Id:    5DCE:BFD61:281B1E8:83E8ABB:6AED63B6
authenticated:          false
```
判定：**主限流（primary）**，非次级（secondary）。
依据：`X-RateLimit-Remaining=0` + `X-RateLimit-Used=Limit`。
次级限流的特征是 403/429 配 `Retry-After` 且 remaining 通常非 0 —— 此处不成立。
恢复依据：**响应头给出的 reset 时间**，不是猜测。

## 安装版完整 SHA-256
```
launcher  cfd254245b1dc043a725cc1fcb99f45586fb2c773776bb351fcaf8a374ebe66a
SKILL.md  e710729b4a7665005d49fd4fa4765d7082c17a1e46799d01f5f2c0b9408be7fe
project_root  .../SourceLore
```
P6A 报的 `cfd254245b1dc043` 只是前缀 16 字符，本轮补全。

## 待办
1. reset 后做最小预算真实采集
2. 自然语言触发清单（需用户会话）
3. D-42 成功契约永久防护
4. 产品级 Gold ≥15
5. 门禁与报告

## 真实 GitHub 已走通前半（2026-11-06 13:28）
- repo jonschlinkert/is-number, id 24313173
- commit 98e8ff1da1a89f93d1397a24d7413ed15421c139 (2018-07-04)
- tree 37450e1347ebbad642393376ee3ef67f576d1109, 13 项未截断
- LICENSE 9af4a67d206f24ecdbb5fdff2839041ca0bbd346 (MIT, 1091 字节)
- 4 blob 全部 OID 自校验通过；真实字节已建本地 git 库
  commit 41dee5ac90993da43b1b253cb393ef97d8dddd5a
- 真实字节 → 51 内容事实（README 44 + package.json 7）

## 限流实况（两小时内两次配额耗尽）
13:20 reset 后 remaining 45 → 探测消耗 8 次 → 内容采集再耗 → 13:25 remaining 0
判定：**主限流**，非次级。恢复依据是 reset 时间，非猜测。

## 本轮真缺陷（持续发现中）
- D-42 状态名跨层误用（CONTENT_AVAILABLE vs CONTENT_AVAILABLE_VERIFIED）
- D-43 导入字段 module_name vs module_specifier
- D-44 module_relation_adapter 缺 ALIAS
- D-45 五处 lstrip("./")
- **D-46 license_known 是声明式空参数**（接收但从不使用 → FETCH/PERSIST 全 UNKNOWN）
- **D-47 内容链路只入库不建命题**（P6A 只建了路径命题 → 内容查询恒 INSUFFICIENT）
- **D-48 查询侧缺 normalized_parameters/repository_id**（裁决 _matches 恒 False）

## 当前卡点
_readme_heading_exists 的 _matches 四项前置检查全过，仍返回 False。

## D-46/47/48/49 记录（真实链路暴露）
- D-46 `license_known` 是声明式空参数：CLI 有、签名有、函数体零引用。
  已接线 → authorization_basis=LICENSE_OBSERVED_AND_APPLICABLE。
- D-47 内容链路只入库不建命题：P6A 只建路径命题 → 内容查询恒 INSUFFICIENT。
- D-48 查询侧缺 normalized_parameters/repository_id → 裁决 _matches 恒 False。
- D-49 `ingest_content_facts` 的 written 不含 subject（只有 fact_id/rule_id/asset_id/observation_id），
  原始抽取 facts 的 id 与之不对齐 → 建命题拿不到主体。

## 已验证可用
- manifest 两类命题已 supported（dependency_declared / field_present）
- README heading 仍在收口

## 不变式（本轮确认）
真实 GitHub 字节已落本地对象库，三个 blob OID 与 GitHub 报告逐一相同：
LICENSE 9af4a67d206f / README eb8149e8cf5f / package.json 3715072609d6
