/**
 * dsh-sourcelore-cards — 宿主半。
 *
 * ★ 为什么必须有这一半（实测约束，来自 dsh-agent-clock 的判决）：
 *   只有**磁盘上的真包**才会被写进 `window.__DSH_BOOT__.entries`，
 *   客户端半才投递得到浏览器。动态 Cordis 插件的 client 半实测投递不到。
 *   所以本包必须是真包（package.json + cordis.patch.yml + 这一半）。
 *
 * 宿主职责：把 SourceLore 的知识库查询暴露成一条 HTTP 路由给客户端半用，
 * 以及把「导出到 Obsidian」也做成一条路由。
 * ★ 零网络：所有数据来自本地 kb.db。
 */
import { createRequire } from 'node:module'

export const name = 'dsh-sourcelore-cards'

/**
 * ★ inject 必须留空 —— 这是 2026-11-12 实证的结论。
 *
 * 声明 ["dockPanels"] 会让宿主半永久 pending：
 *   `sourcelore-cards (dsh-sourcelore-cards): pending (waiting for service: dockPanels)`
 * 因为 dockPanels 是 **Tobs 客户端**通过 ctx.provide 暴露的服务，
 * 只在浏览器侧的 cordis 上下文里，宿主 Node 侧根本看不到。
 * 宿主 pending → 整个插件（含客户端 bundle 投递）都不挂载。
 *
 * 客户端半要拿 dockPanels，在 client.js 的 apply(ctx) 里用
 * ctx.inject(["dockPanels"], …) 即可，不需要在宿主这里声明。
 */
export const inject = []

const CLI_PATH = process.env.SOURCELORE_CLI
  || '/home/arlune_innersea/.agents/skills/sourcelore/scripts/sourcelore.py'

async function runCli(args) {
  const { spawn } = await import('node:child_process')
  return await new Promise((resolve) => {
    const p = spawn('python3', [CLI_PATH, ...args], { stdio: ['ignore', 'pipe', 'pipe'] })
    let out = '', err = ''
    p.stdout.on('data', (d) => { out += d })
    p.stderr.on('data', (d) => { err += d })
    p.on('close', (code) => {
      try { resolve({ ok: true, code, data: JSON.parse(out) }) }
      catch { resolve({ ok: false, code, error: 'PARSE_FAILED', raw: out.slice(0, 400), stderr: err.slice(0, 400) }) }
    })
    p.on('error', (e) => resolve({ ok: false, error: 'SPAWN_FAILED', detail: String(e) }))
  })
}

export function apply(ctx) {
  // ★ 真实注册机制（核实自 dsh-agent-studio/lib/api.js:575 与 lib/index.js:56）：
  //   不是 `ctx.http`，而是 ctx.inject(['webServer'], cb) → webCtx.webServer.register({kind:'prefix', path, handler})。
  //   用注入回调而不是顶层 inject，是为了「缺服务时插件仍能挂载」（纯 CLI 组合没有 webServer）。
  const logger = ctx?.logger ?? console

  ctx.inject(['webServer'], (webCtx) => {
    const webServer = webCtx?.webServer
    if (!webServer || typeof webServer.register !== 'function') {
      logger.warn?.('[sourcelore-cards] webServer 不可用，路由未挂载')
      return
    }
    const PREFIX = '/api/dsh-sourcelore-cards'
let PANEL_STATUS = null
    webServer.register({
      kind: 'prefix',
      path: PREFIX,
      handler: async (req, res) => {
        const url = new URL(req.url ?? '/', 'http://localhost')
        const path = url.pathname.replace(/\/+$/, '')
        const q = url.searchParams
        const send = (code, obj) => {
          res.statusCode = code
          res.setHeader('content-type', 'application/json; charset=utf-8')
          res.end(JSON.stringify(obj))
        }
        try {
          if (path === `${PREFIX}/repositories`) {
            const r = await runCli(['repositories'])
            return send(200, r.ok ? r.data : { ok: false, error: r.error })
          }
          if (path === `${PREFIX}/card`) {
            const args = ['card', '--repository-id', q.get('repository_id') || '']
            if (q.get('commit')) args.push('--commit', q.get('commit'))
            if (q.get('path')) args.push('--path', q.get('path'))
            args.push('--code')
            const r = await runCli(args)
            return send(200, r.ok ? r.data : { ok: false, error: r.error })
          }
          // ★ 仓库知识卡片：直接读派生视图（与项目文档同一批数据）
          if (path === `${PREFIX}/repocard`) {
            const rid = q.get('repository_id') || ''
            if (!rid) return send(400, { ok: false, error: 'REPOSITORY_ID_REQUIRED' })
            const fs = await import('node:fs')
            const root = process.env.SOURCELORE_DATA_ROOT
              || '/mnt/Server_Data_Center/Team_Flie(团队文件)/GitHub_Knowledge_Base(Gihub知识库)/SourceLore_Data'
            const base = `${root}/派生视图/${rid}`
            if (!fs.existsSync(base)) {
              return send(200, { ok: false, error: 'NO_DERIVED_VIEW', repository_id: rid })
            }
            // 取最新 commit 目录（有 card-data.json 的）
            const commits = fs.readdirSync(base).filter((d) => {
              try { return fs.statSync(`${base}/${d}`).isDirectory() } catch { return false }
            })
            let picked = null
            for (const c of commits.sort().reverse()) {
              if (fs.existsSync(`${base}/${c}/card-data.json`)) { picked = c; break }
            }
            if (!picked) return send(200, { ok: false, error: 'NO_CARD_DATA', repository_id: rid })
            const dir = `${base}/${picked}`
            const read = (n) => {
              try { return JSON.parse(fs.readFileSync(`${dir}/${n}`, 'utf8')) }
              catch { return null }
            }
            const cardData = read('card-data.json')
            // ★ 文档正文由 card-data.documents 携带（derive 时由 repo_miner 生成）。
            //   若旧数据没有 documents，退回读取 .md 文件并按 ## 切章，保证不空手。
            let documents = (cardData && cardData.documents) || []
            if (!documents.length) {
              const mdFiles = fs.readdirSync(dir).filter((f) => f.endsWith('.md'))
              documents = mdFiles.map((f) => {
                let raw = ''
                try { raw = fs.readFileSync(`${dir}/${f}`, 'utf8') } catch { raw = '' }
                const secs = []
                let cur = { section_id: 'head', heading: f, body: [] }
                for (const ln of raw.split('\n')) {
                  const m = ln.match(/^##\s+(.*)$/)
                  if (m) {
                    if (cur.body.length || cur.heading !== f) secs.push({
                      section_id: cur.section_id, heading: cur.heading,
                      body: cur.body.join('\n').trim(), refs: [],
                    })
                    cur = { section_id: 's' + secs.length, heading: m[1], body: [] }
                  } else cur.body.push(ln)
                }
                if (cur.body.length) secs.push({
                  section_id: cur.section_id, heading: cur.heading,
                  body: cur.body.join('\n').trim(), refs: [],
                })
                return { document_id: f.replace(/\.md$/, ''), title: f, sections: secs }
              })
            }
            return send(200, {
              ok: true,
              repository_id: rid,
              commit_sha: picked,
              card: cardData,
              graph: read('code-graph.json'),
              documents,
              files: fs.readdirSync(dir).filter((f) => f.endsWith('.md')),
            })
          }
          if (path === `${PREFIX}/panelstatus`) {
            // 客户端注册成功后 POST 上报，便于命令行验证
            if (method === 'POST') {
              let body = ''
              req.on('data', (c) => { body += c })
              req.on('end', () => {
                PANEL_STATUS = { at: new Date().toISOString(), body }
                return send(200, { ok: true })
              })
              return
            }
            return send(200, { ok: true, status: PANEL_STATUS })
          }
          if (path === `${PREFIX}/export`) {
            const vault = q.get('vault') || ''
            if (!vault) return send(400, { ok: false, error: 'VAULT_REQUIRED' })
            const args = ['card', '--repository-id', q.get('repository_id') || '']
            if (q.get('commit')) args.push('--commit', q.get('commit'))
            if (q.get('path')) args.push('--path', q.get('path'))
            args.push('--code', '--vault', vault)
            const r = await runCli(args)
            return send(200, r.ok ? r.data : { ok: false, error: r.error })
          }
          return send(404, { ok: false, error: 'NOT_FOUND', path })
        } catch (err) {
          logger.error?.('[sourcelore-cards] handler 异常: ' + (err?.message ?? err))
          return send(500, { ok: false, error: 'HANDLER_FAILED', detail: String(err?.message ?? err) })
        }
      },
    })
    logger.info?.(`[sourcelore-cards] 已挂载 ${PREFIX}`)
  })
}
