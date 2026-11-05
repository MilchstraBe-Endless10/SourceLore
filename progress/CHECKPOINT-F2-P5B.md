# F2-P5B（检查点）

基线 `eb781f3`。Crosswalk 42841207… 须复算。

## 七项任务
1. 离线优先缓存复用（--offline / --refresh / 固定 commit）
2. 限流快失败（P5A 已做，需保留）
3. 可选 GITHUB_TOKEN（走 GitHubClient 请求层）
4. 多 Commit 持久化与对照
5. index_rows.commit_sha NULL 根因
6. 自然语言触发（大概率 NOT_VERIFIED，出清单）
7. 单文件/空树/证据不足提示

## 硬约束
- 不改冻结 Crosswalk、不改 Harness 模型配置
- 不建第二套 GitHub Client
- Token 不进 Git/日志/资产/对话
- 640 项回归
