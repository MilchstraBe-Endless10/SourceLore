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

/** 不依赖宿主注入的任何服务 —— 自己 spawn CLI。 */
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
            return send(200, {
              ok: true,
              repository_id: rid,
              commit_sha: picked,
              card: read('card-data.json'),
              graph: read('code-graph.json'),
              files: fs.readdirSync(dir).filter((f) => f.endsWith('.md')),
            })
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
