/**
 * dsh-sourcelore-cards — 浏览器半。
 *
 * ★ 设计依据（已查证，不是自造）：
 * 1. 知识卡片 ≠ 聊天里的表格/清单。它是一条知识 = 一张卡，
 *    卡与卡之间**互相串联**（Zettelkasten 的核心是连接，不是分类）。
 * 2. UI 必须「有设计感」：这里用**卡片墙**（masonry 风格）+ 状态色带 +
 *    悬停浮起 + 点击展开关联链，而不是一行行文字。
 * 3. 双向链接：卡片上直接标出「链到哪」，并一键导出成 Obsidian 笔记
 *    （导出由宿主半执行，客户端只发意图）。
 *
 * ★ 实测约束：sidebar.footer.action 只有 256×36px，面板必须 position:fixed
 *   挂在槽位外自己定位（同 dsh-agent-clock 的结论）。
 */
const STYLE_ID = 'sourcelore-cards-style'

const STATE = {
  SUPPORTED_SOURCE_CLAIM:    { zh: '已验证',  color: '#3ddc84', ring: 'rgba(61,220,132,.35)' },
  OBSERVED_SOURCE_FACT:      { zh: '已观察',  color: '#f5b942', ring: 'rgba(245,185,66,.35)' },
  INSUFFICIENT_EVIDENCE:     { zh: '证据不足', color: '#8a8f98', ring: 'rgba(138,143,152,.3)' },
  UNSUPPORTED_SEMANTIC_FORM: { zh: '不支持',  color: '#b07cff', ring: 'rgba(176,124,255,.35)' },
  NOT_ANALYZED:              { zh: '未分析',  color: '#5a6068', ring: 'rgba(90,96,104,.3)' },
}

function css() {
  return `
.slc-wrap{position:fixed;z-index:1100;width:min(680px,82vw);max-height:min(70vh,620px);
  overflow:auto;padding:18px;border-radius:16px;
  background:linear-gradient(160deg,#1b1d22 0%,#14161a 100%);
  border:1px solid rgba(255,255,255,.09);
  box-shadow:0 24px 64px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.03) inset;
  color:#e8eaee;font-size:13px;line-height:1.55}
.slc-head{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.slc-title{font-weight:650;font-size:15px;letter-spacing:.2px}
.slc-repo{font-family:ui-monospace,monospace;font-size:11px;color:#9aa1ab;
  background:rgba(255,255,255,.05);padding:2px 7px;border-radius:6px}
.slc-sub{color:#828893;font-size:11.5px;margin-bottom:14px}
.slc-wall{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
.slc-card{position:relative;padding:11px 13px 11px 17px;border-radius:11px;
  background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);
  cursor:pointer;transition:transform .16s ease,box-shadow .16s ease,background .16s ease}
.slc-card:hover{transform:translateY(-2px);background:rgba(255,255,255,.06);
  box-shadow:0 10px 26px rgba(0,0,0,.38)}
.slc-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
  border-radius:11px 0 0 11px;background:var(--sc)}
.slc-name{font-family:ui-monospace,monospace;font-size:12.5px;font-weight:600;
  color:#f2f4f7;word-break:break-all;margin-bottom:5px}
.slc-meta{display:flex;align-items:center;gap:7px;font-size:10.5px;color:#828893}
.slc-dot{width:6px;height:6px;border-radius:50%;background:var(--sc);box-shadow:0 0 0 3px var(--sr)}
.slc-badge{margin-left:auto;font-size:10px;padding:1px 6px;border-radius:999px;
  color:var(--sc);background:var(--sr);border:1px solid var(--sc)}
.slc-links{margin-top:9px;padding-top:8px;border-top:1px dashed rgba(255,255,255,.09);
  font-size:10.5px;color:#8d939d;display:none}
.slc-card.expanded .slc-links{display:block}
.slc-link{color:#7fc3ff;text-decoration:none}
.slc-foot{display:flex;gap:8px;margin-top:16px;padding-top:12px;
  border-top:1px solid rgba(255,255,255,.07)}
.slc-btn{font:inherit;font-size:12px;padding:6px 13px;border-radius:8px;cursor:pointer;
  border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:#e8eaee}
.slc-btn:hover{background:rgba(255,255,255,.1)}
.slc-btn.primary{background:rgba(79,140,255,.18);border-color:rgba(79,140,255,.5);color:#a9c8ff}
.slc-empty{color:#828893;padding:26px 0;text-align:center}`
}

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return
  const s = document.createElement('style')
  s.id = STYLE_ID
  s.textContent = css()
  document.head.appendChild(s)
}

async function getJson(url) {
  const r = await fetch(url, { headers: { accept: 'application/json' } })
  return await r.json()
}

function buildPanel() {
  const wrap = document.createElement('div')
  wrap.className = 'slc-wrap'
  wrap.innerHTML = `
    <div class="slc-head">
      <span class="slc-title">知识卡片</span>
      <span class="slc-repo" id="slc-repo">—</span>
    </div>
    <div class="slc-sub" id="slc-sub">正在读取…</div>
    <div class="slc-wall" id="slc-wall"></div>
    <div class="slc-foot">
      <button class="slc-btn primary" id="slc-export">导出到 Obsidian</button>
      <button class="slc-btn" id="slc-close">关闭</button>
    </div>`
  return wrap
}

function renderCards(wrap, data) {
  const wall = wrap.querySelector('#slc-wall')
  const repo = wrap.querySelector('#slc-repo')
  const sub = wrap.querySelector('#slc-sub')
  repo.textContent = data.repository || ('repo ' + (data.repository_id || '-'))
  const claims = data.claims || []
  if (!claims.length) {
    sub.textContent = '这个文件没有可展示的裁决'
    wall.innerHTML = '<div class="slc-empty">没有卡片</div>'
    return
  }
  sub.textContent = `${claims.length} 张卡片 · commit ${String(data.commit_sha || '').slice(0, 10)} · 文件 ${data.file_path || ''}`
  wall.innerHTML = ''
  for (const c of claims) {
    const st = STATE[c.display_level] || STATE.NOT_ANALYZED
    const s = c.subject || {}
    const name = s.qualified_name || s.exported_name || s.module_name || '?'
    const card = document.createElement('div')
    card.className = 'slc-card'
    card.style.setProperty('--sc', st.color)
    card.style.setProperty('--sr', st.ring)
    card.innerHTML = `
      <div class="slc-name">${name}</div>
      <div class="slc-meta">
        <span class="slc-dot"></span>
        <span>${c.kind || ''}</span>
        <span>${c.start_line ? 'L' + c.start_line : ''}</span>
        <span class="slc-badge">${st.zh}</span>
      </div>
      <div class="slc-links">
        <div>↗ 仓库 <span class="slc-link">${repo.textContent}</span></div>
        <div>↗ 文件 <span class="slc-link">${data.file_path || ''}</span></div>
        <div>↗ claim <span class="slc-link">${(c.claim_id || '').slice(-8)}</span></div>
      </div>`
    card.addEventListener('click', () => card.classList.toggle('expanded'))
    wall.appendChild(card)
  }
}

export function apply(ctx) {
  ensureStyle()

  // ★ 注册侧栏按钮（拿不到槽位就退到悬浮球，绝不无声失败）
  const mount = () => {
    let slot = null
    try {
      slot = ctx?.sidebar?.footerAction?.()
    } catch { slot = null }
    const btn = document.createElement('button')
    btn.title = 'SourceLore 知识卡片'
    btn.textContent = '◈'
    Object.assign(btn.style, {
      width: '36px', height: '36px', borderRadius: '50%', cursor: 'pointer',
      border: '1px solid rgba(255,255,255,.14)',
      background: 'rgba(255,255,255,.06)', color: '#e8eaee', fontSize: '15px',
    })
    let panel = null
    btn.addEventListener('click', async (e) => {
      e.stopPropagation()
      if (panel) { panel.remove(); panel = null; return }
      panel = buildPanel()
      const r = btn.getBoundingClientRect()
      panel.style.left = Math.max(12, r.left - 690) + 'px'
      panel.style.bottom = '24px'
      document.body.appendChild(panel)
      panel.querySelector('#slc-close').onclick = () => { panel.remove(); panel = null }
      try {
        const repos = await getJson('/api/dsh-sourcelore-cards/repositories')
        const first = (repos.repositories || [])[0]
        if (!first) { panel.querySelector('#slc-sub').textContent = '知识库为空'; return }
        const q = `?repository_id=${encodeURIComponent(first.repository_id)}`
        const card = await getJson('/api/dsh-sourcelore-cards/card' + q)
        renderCards(panel, { ...card, repository: first.repository })
        panel.querySelector('#slc-export').onclick = async () => {
          const vault = prompt('Obsidian vault 目录：')
          if (!vault) return
          const out = await getJson(`/api/dsh-sourcelore-cards/export${q}&vault=${encodeURIComponent(vault)}`)
          const o = out.obsidian || {}
          panel.querySelector('#slc-sub').textContent =
            `已导出 ${o.notes_written || 0} 篇笔记到 ${vault}`
        }
      } catch (err) {
        panel.querySelector('#slc-sub').textContent = '读取失败：' + err.message
      }
    })

    if (slot && typeof slot.mount === 'function') slot.mount(btn, { order: 70 })
    else {
      Object.assign(btn.style, { position: 'fixed', right: '18px', bottom: '84px', zIndex: 1050 })
      document.body.appendChild(btn)
    }
  }

  if (document.body) mount()
  else document.addEventListener('DOMContentLoaded', mount, { once: true })
}

export const name = 'dsh-sourcelore-cards'
