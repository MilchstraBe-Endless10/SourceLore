# F2-P6H 知识卡片 · 检查点（2026-11-07 14:40）

## 用户真正要的「卡片」（本轮查证后定案）
不是聊天里的表格/清单，而是：
1. **有专用 UI 组件的知识卡片**（一条知识 = 一张卡）
2. 卡片**互相串联**
3. 可**双向链接到 Obsidian 独立笔记**
4. UI 要有设计感、丰富有趣
5. **接入到 DeepSeek Bot 之中**
6. 卡片里写什么内容要设计清楚

## 一手查证结论（勿重复调查）
- **AI 聊天卡片规范**（eucalipse.com）：typed JSON + 真实组件渲染；
  表格/清单/动作提案/确认/错误五类；「把 markdown 解析成 UI 是永久故障源」。
- **Zettelkasten**（sspai.com/post/60802）：核心是**连接**不是分类；
  文献/书目/永久三层；一条笔记只讲一件事，用 `[[双链]]` 挂到已有笔记。
- **Bot 的 `card` 是工具授权卡**（allowed-once/always/denied；decided/answered/
  cancelled/expired），不是知识卡 → 禁止挪用。

## 接入机制（核实过的真机制）
```
package.json  dsh.bundle.patch → cordis.patch.yml（insert row，id 必须等于 index.js 的 name）
              dsh.client { platform:"web", inject:[] }
宿主半        ctx.inject(['webServer'], wc => wc.webServer.register({
                kind:'prefix', path:'/api/dsh-sourcelore-cards', handler }))
客户端半      client.js 由 DSH_BOOT entries 投递到浏览器
★ 必须是磁盘真包 —— 动态 Cordis 插件的 client 半投递不到浏览器
```

## 已交付
| 项 | 状态 |
|---|---|
| `src/skill_interface/obsidian_export.py` | DONE：一条知识一文件，仓库/文件/符号三层互链；实测 15 笔记 / 41 出链 / **0 断链** |
| `card --code --vault <dir>` | DONE：Bot 文本块 + Obsidian 笔记一次产出，零网络 |
| `plugin/dsh-sourcelore-cards` | 已写：宿主路由 3 条 + 客户端卡片墙（状态色带/悬停浮起/点击展开关联链） |
| 安装 | `dsh plugin --profile web add link:<dir>` 成功；已在 `dsh.profile.bundles`（第 64 条） |
| 插件两端加载 | `node --input-type=module` 均验证 apply 是 function |

## 剩余
- **需重启 DSH 才生效**（用户记忆里明确：重启必须先告知并等同意）
- 重启后验证：侧栏出现 ◈ 按钮 → 点开是卡片墙 → 导出到 Obsidian
- 全量回归

## 关键路径
- 插件：`SourceLore/plugin/dsh-sourcelore-cards/{package.json,index.js,client.js,cordis.patch.yml}`
- 导出：`SourceLore/src/skill_interface/obsidian_export.py`
- 数据根：`…/GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data`
- 实测仓库：preactjs/preact `42283287` / commit `dbeba0d59bb59260ea4a90c5adf9f5a29d43cdab` / `src/index.js`
