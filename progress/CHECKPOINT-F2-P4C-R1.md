# F2-P4C-R1 真实模型路由最小验证（检查点）

**基线**：056de10 · CLI 0.2.1-rc.2 · OmniRoute 16.3.8 @127.0.0.1:20128

## 本轮边界

- 允许：只读探测网关 API 面、隔离临时 patch 合成验证
- **禁止**：真实推理请求（除非用户单独授权）、改正式 profile、改凭据、复制 Web 登录态

## 已确认前提（R1 前置轮实测）

- headless `llm-pi-ai` 是**空壳无 config** → 不注册任何 provider
- headless 全文 `omniroute` 0 次
- 网关真实存在：`omniroute (v16.3.8)` pid 3735170，systemd `omniroute.service` active 3 天
- 网关配置根 `$HOME/omniroute-deployment/.config/omniroute/`
- `ds-web/*` 前缀网关**完全不认识**
- 网关实际 ID 格式 `<上游>/<model>`，如 `deepseek/deepseek-v4.1-flash`
- 13 条 provider 连接；`deepseek-web` 的 default_model 为 NULL
- `OMNIROUTE_API_KEY` 只在**网关进程**环境，DSH 侧完全没有

## 验收分类（本轮必须分开报）

- `HEADLESS_PROVIDER_REGISTERED`
- `GATEWAY_CLIENT_AUTH_VERIFIED`
- `REAL_LLM_CALL_VERIFIED`
- `UPSTREAM_MODEL_IDENTITY_VERIFIED`
- `SOURCELORE_REAL_ADAPTER_VERIFIED`
- `SYNTHESIS_GROUNDING_VERIFIED`
- `REAL_HARNESS_AUTHORIZED_E2E`

## 停止条件

未获真实调用授权 → 只交预检 + 临时合成结果，停。

## A 段结论（客户端鉴权准备）

### 两个配置根（必须先分清）

| 根 | 用途 | api_keys 行数 |
|---|---|---|
| `~/.config/omniroute/` | CLI **默认**加载（XDG_CONFIG_HOME=~/.config）；仅 32KB 空库 | 查询失败/空 |
| `~/omniroute-deployment/.config/omniroute/` | **运行中服务实际使用**（systemd 注入）；42MB | 1 |

所以：**CLI 不加 `XDG_CONFIG_HOME` 会连错库** —— 上一轮 `keys list` 报
"No keys configured" 就是连了空库。加 `XDG_CONFIG_HOME=~/omniroute-deployment/.config` 后才看到真实数据。

### 两类 Key 不可混淆

- `omniroute keys add/list/remove` → **provider 上游凭据**（9 个：agnes/auriko/deepseek-web/
  fastrouter/firecrawl(disabled)/kimi-web/ollama-cloud/vertex/zai-web）
- `api_keys` 表 → **客户端 Key**（现有 1 行：name=DeepSeek,
  scopes=`["manage","self:usage"]`, model_access_mode=all, is_active=1）

**现有客户端 Key 带 `manage` 权限** —— 不符合「仅推理、无管理权限」要求。

### 专用 Key 可用的权限字段（表结构实测）

`allowed_models / blocked_models / model_access_mode / allowed_connections /
allowed_endpoints / scopes / max_requests_per_day / max_requests_per_minute /
usage_limit_enabled / daily_usage_limit_usd / throttle_delay_ms`

→ **技术上能做出仅允许指定模型、限额、无 manage 的专用 Key。**

### 创建入口

- `keys regenerate <id>` / `keys rotate <id>` —— 对**已有** key 重生成
- `keys policy set <id>` —— 设限额
- 新建客户端 Key 的具体子命令**未在 keys --help 中明确列出**
  （keys add 是加 provider 凭据）。可能需要 Dashboard（`omniroute dashboard`）或 REST。

**结论：A 段未完成。** 需要用户自行在 Dashboard 创建专用 Key，
并放入 `SOURCELORE_OMNIROUTE_CLIENT_KEY`。我不创建、不读取、不导出。

## B 段（待做）

临时 patch 合成验证。

## B 段结论（临时 patch 合成验证，全部通过）

命令：`dsh --profile headless --patch /tmp/p4c_r1/headless_omniroute.yml --dump-config`
结果：**exit=0，stderr 空**，输出 12851 bytes

| 检查项 | 结果 |
|---|---|
| 1. llm-pi-ai 注册 omniroute | ✅ L85-91 `providers.omniroute` |
| 2. 模型 ID 与默认模型一致 | ✅ 两处均 `deepseek/deepseek-v4.1-flash` |
| 3. endpoint / apiKeyEnv 正确 | ✅ `baseURL: http://127.0.0.1:20128/v1`<br>`apiKeyEnv: SOURCELORE_OMNIROUTE_CLIENT_KEY`<br>`api: openai-completions` |
| 4. 其他插件仍加载 | ✅ 插件条目数 98→98（无丢失） |
| 5. 无 provider ID 冲突 | ✅ `omniroute:` 仅 1 处定义 |
| 6. 未泄漏凭据 | ✅ 疑似密钥字面量 0 |
| 7. 正式 headless 哈希不变 | ✅ md5 `7390256202c2b81f4dcdcd743a9875b3` |

**注意**：patch 里 `apiKeyEnv` 用的是 `SOURCELORE_OMNIROUTE_CLIENT_KEY`，
**不是** `OMNIROUTE_API_KEY` —— 刻意与网关服务自身凭据隔离。

## C 段（未执行）

真实请求**未发出**，等待用户独立授权。
