# 安全边界

## 输入校验

`analyze` 的 URL 必须满足：

- scheme ∈ {http, https}，且必须是 `github.com` 或 `www.github.com`
- 端口 ∈ {None, 80, 443}
- 路径匹配 `/<owner>/<repo>[/tree/<ref>]`
- 拒绝：内网地址、`evil.com`、`github.com.evil.com`、userinfo、路径穿越

## 只读约束

- 不推送、不创建 Issue/PR、不执行仓库内脚本
- 不使用任何私有仓库凭据通道
- GitHub 请求受 `--max-requests` 限制（默认 40），超限即失败而非静默继续

## 数据位置

- `kb.db` 拒绝写入 Git 仓库（脚本内 guard 抛错）
- 预览产物写入 `<数据根>/preview/`，标 `distribution_allowed: false`

## 呈现约束

- 卡片 HTML 走 F2-P4A Safe Renderer：唯一入口 `html.escape`，CSP 默认 `'none'`
- 不解析 HTML 反推 Claim/Evidence
- 不把模型推理结果写入知识库

## 分发门禁

`FROZEN_INTERNAL_RESTRICTED`，B-1 / B-2 / B-3 全 OPEN。
本 Skill 只用于内部开发与本地预览，不构成公开分发许可。
