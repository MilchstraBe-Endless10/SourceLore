# F2-P4C Provider 真实注册与调用链预检（检查点）

**基线**：056de10 · CLI 实际版本 0.2.1-rc.2

## 本轮范围

只预检，不修改、不请求。禁止：真实推理、改全局配置、改凭据、换 Web 默认模型、装插件。

## 已确认基线（上一轮实测）

- DSH_HOME 存在；`profiles/` 只有 `headless` 与 `web`，**无 desktop**
- Web：`trae / deepseek-v4.1-flash`（trae 来自 dsh-our-free-model 账号池插件）
- Headless：`deepseek-official / deepseek-flash`
- Headless 三项显式禁用：`credentials` / `authorization` / `deepseek-account`
- CLI 目录名 rc.3 但包版本 rc.2（命名与实包不一致）
- Home 级 cordis.patch.yml 不存在

## 待核清单（本轮）

1. headless dump-config 提取非敏感字段
2. llm-pi-ai 是否在 headless 启用
3. omniroute 是否在 headless 注册表
4. 模型 ID 是否实际注册（不照抄 web）
5. 127.0.0.1:20128 监听存在性
6. 监听进程真实身份（端口开放≠OmniRoute）
7. OMNIROUTE_API_KEY 配置入口存在性（不输出值）
8. 网关协议与兼容性
9. 模型名是否网关别名 + 上游可核验性
10. `src/research/llm_adapter.py` 与 Harness 调用接口的缺口

## 硬约束（续跑必读）

- `dsh --dump-config` 成功 ≠ 模型调用成功
- 端口开放 ≠ 服务是 OmniRoute
- 配置文件存在 ≠ 凭据有效
- 临时验证只能用 `--patch <临时补丁>`，**不得覆盖** `profiles/headless/cordis.patch.yml`
- 任何真实推理都需独立授权；本轮门禁保持 OPEN

## 本轮实测结果（2026-11-05 14:25）

### 1. headless 的 llm-pi-ai：已加载但**无 config**

```
- id: llm-pi-ai
  name: '@deepseek-ai/dsh-llm-pi-ai'          ← 仅此两行，无 config
```

### 2. headless 全文中 provider 关键字计数

```
providers  : 0
omniroute  : 0
inferx     : 0
trae       : 0
```

**结论：omniroute 在 headless 中完全没有注册。**

### 3. 20128 端口：真实存在且身份确认为 OmniRoute

```
LISTEN 127.0.0.1:20128  users:(("omniroute (v16.",pid=3735170,fd=21))
```

- 进程：`omniroute (v16.3.8)`
- systemd 用户单元：`omniroute.service` — **OmniRoute AI Gateway**
- 状态：`active (running) since 2026-11-01 16:24:32 CST; 3 days ago`
- enabled；有 drop-in `chrome-path.conf`
- 运行在 node 26.8.2（mise 安装）

**这不是「端口开放就猜是 OmniRoute」—— 进程名与 systemd 单元名双重印证。**

### 4. 待补

- OMNIROUTE_API_KEY 配置入口存在性（不输出值）
- 网关协议（openai-completions）与 baseURL 兼容性
- `ds-web/deepseek-v4-flash` 是否网关别名
- llm_adapter.py 与 Harness 调用接口缺口
- 临时 patch 合成验证（不覆盖正式文件）

### 5. OMNIROUTE_API_KEY 入口

- systemd 单元**未**声明该变量（只声明 XDG_CONFIG_HOME / SERVER_HOST / READY_TIMEOUT_MS）
- 但**网关进程自身环境里存在该变量名**（来自 `$HOME/omniroute-deployment/.config/omniroute/.env`）
- 当前 DSH 进程 / systemd 用户环境**都没有**该变量

**推论：网关自己有 key，但 DSH 侧没有。** 若 headless 要连 omniroute，
`llm-pi-ai` 的 `apiKeyEnv: OMNIROUTE_API_KEY` 在 DSH 进程里取不到值。

### 6. 网关服务真实身份（已确认）

- 进程：`omniroute (v16.3.8)`，pid 3735170
- systemd 用户单元 `omniroute.service`「OmniRoute AI Gateway」active 3 天
- ExecStart：`.../0.2.1-rc.3/package-runtime/bin/omniroute serve --no-open`
- 配置根：`$HOME/omniroute-deployment/.config/omniroute/`
  （含 storage.sqlite / .env / oauth / logs / server / call_logs）

### 7. 网关模型注册（只读 sqlite）

`storage.sqlite` 42 MB，`provider_connections` **13 行**，有 token/api_key 列（**未读取值**）。
`model_context_overrides` 431 行、`session_model_history` 2 行。

### 8. 待补

- `ds-web/deepseek-v4-flash` 是否为网关可识别 ID
- llm_adapter.py 与 Harness 接口缺口
- 临时 patch 合成验证

### 9. 模型 ID 核验（关键否定结论）

网关 `model_context_overrides` 里有：`deepseek-v4-flash`、`deepseek-v4.1-flash`、
`deepseek/deepseek-v4-flash`、`deepseek/deepseek-v4.1-flash` 等。

**但 `ds-web/*` 前缀在网关中一条都没有** —— web profile 配置里的
`ds-web/deepseek-v4-flash` **不是网关能识别的模型 ID**。

实际可用格式是 `<上游>/<model>`（如 `fastrouter/google/gemini-3.1-pro-preview`，
见 `session_model_history.model_str`）。

`provider_connections` 13 项：
agnes / auriko / **deepseek-web** / fastrouter / firecrawl(inactive) / kimi-coding /
kimi-web / kiro / ollama-cloud / ollama-local / vertex / workbuddy / zai-web。

（`deepseek-web` 的 `default_model` 为 NULL —— 需显式指定模型名。）

### 10. adapter 缺口

`src/research/llm_adapter.py`：
- 对外只有 `make_stub_client` / `invoke` / `classify`
- **http/requests/urllib 相关行数 = 0** —— 没有任何真实传输实现
- client 契约要求返回键：`adapter_state / text / statement_refs / provider / model`
- `llm_used` 判定：`provider not in (None, "offline-stub")`

**缺口清单**：真实 HTTP 客户端、鉴权头注入、超时/重试、错误映射、
响应→`{text, statement_refs}` 的转换、`real_call_verified` 的真实判定逻辑。

### 与 Harness 的关系

`llm-pi-ai` 在 headless **无 config** → 不注册任何 provider；
omniroute 只在 **web** 的 `llm-pi-ai.config.providers` 里定义。
**headless 与 omniroute 之间没有任何已建立的注册关系。**
