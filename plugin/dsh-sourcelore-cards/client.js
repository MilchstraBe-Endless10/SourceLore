/**
 * dsh-sourcelore-cards — 浏览器半（Bot 模式面板）。
 *
 * ★ 接入机制的权威依据（核实自 dsh-agent-model-statusbar/client.js:317-327，
 *   它是本机上真实可用的 Bot 插件范例）：
 *     ctx.slots.inject("<slot>", () => ctx.slots.register({name,id,order,label}, render))
 *     exports.inject = ["slots"]     ← ★ 少了这一行整包**静默失效**
 *
 * ★ Bot 模式的槽位（核实自 @botharness/ui/lib/client.js）：
 *     bh:home                    Bot 主页区   ← 本插件用这个
 *     bh:workspace-rail          工作区侧栏
 *     bh:channels                频道列表
 *     bh:channel-body            消息主体
 *     botharness.settings.section  Bot 设置页分区
 *
 * ★ 为什么不是 shell.overlay：那是 DSH 主界面的浮层，不是 Bot 模式。
 *   用户明确要求「显示在 Bot 模式界面之中」。
 */
window.__ModuleLoader__.load({
  id: "dsh-sourcelore-cards",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    var react = require("react");   // ★ 照 dsh-agent-model-statusbar 的写法，factory 内直接 require

  // ★ 目标：Bot 模式内的停靠面板。用官方 dockPanels 服务（见 progress/PLAN-DOCKPANEL.md）
  var ID = "dsh-sourcelore-cards";
  // ★ 每次改渲染逻辑就改这个值，用来强制 React 重建组件实例。
  var BUILD = "2026-11-12-0305";

  var STATE = {
    SUPPORTED_SOURCE_CLAIM:    { zh: "已验证",  c: "#3ddc84", ring: "rgba(61,220,132,.32)" },
    OBSERVED_SOURCE_FACT:      { zh: "已观察",  c: "#f5b942", ring: "rgba(245,185,66,.32)" },
    INSUFFICIENT_EVIDENCE:     { zh: "证据不足", c: "#8a8f98", ring: "rgba(138,143,152,.28)" },
    UNSUPPORTED_SEMANTIC_FORM: { zh: "不支持",  c: "#b07cff", ring: "rgba(176,124,255,.32)" },
    NOT_ANALYZED:              { zh: "未分析",  c: "#5a6068", ring: "rgba(90,96,104,.28)" },
  };

  function api(path) {
    return "/api/dsh-sourcelore-cards" + path;
  }

  function getJson(url) {
    // ★ no-store：实测浏览器会缓存住一次空响应，导致后续刷新永远 0 个仓库。
    return fetch(url, { cache: "no-store", headers: { accept: "application/json" } })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      });
  }

  var S = {
    wrap: {
      display: "flex", flexDirection: "column", gap: "14px",
      padding: "20px 22px", height: "100%", overflowY: "auto",
      boxSizing: "border-box", color: "inherit", fontSize: "13px", lineHeight: "1.55",
    },
    head: { display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" },
    title: { fontSize: "15px", fontWeight: "650", letterSpacing: ".2px" },
    repo: {
      fontFamily: "ui-monospace,monospace", fontSize: "11px", opacity: ".75",
      background: "rgba(127,127,127,.14)", padding: "2px 8px", borderRadius: "6px",
    },
    sub: { fontSize: "11.5px", opacity: ".62" },
    wall: {
      display: "grid", gap: "10px",
      gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
    },
    card: {
      position: "relative", padding: "11px 13px 11px 17px", borderRadius: "11px",
      background: "rgba(127,127,127,.08)", border: "1px solid rgba(127,127,127,.18)",
      cursor: "pointer", transition: "transform .16s ease, box-shadow .16s ease, background .16s ease",
    },
    cardHover: {
      transform: "translateY(-2px)",
      boxShadow: "0 10px 26px rgba(0,0,0,.28)",
      background: "rgba(127,127,127,.14)",
    },
    name: {
      fontFamily: "ui-monospace,monospace", fontSize: "12.5px", fontWeight: "600",
      wordBreak: "break-all", marginBottom: "5px",
    },
    meta: { display: "flex", alignItems: "center", gap: "7px", fontSize: "10.5px", opacity: ".7" },
    dot: { width: "6px", height: "6px", borderRadius: "50%", flex: "none" },
    badge: { marginLeft: "auto", fontSize: "10px", padding: "1px 7px", borderRadius: "999px" },
    links: {
      marginTop: "9px", paddingTop: "8px", borderTop: "1px dashed rgba(127,127,127,.28)",
      fontSize: "10.5px", opacity: ".78", display: "none", lineHeight: "1.75",
    },
    foot: { display: "flex", gap: "8px", marginTop: "auto", paddingTop: "12px" },
    btn: {
      font: "inherit", fontSize: "12px", padding: "6px 14px", borderRadius: "8px",
      cursor: "pointer", border: "1px solid rgba(127,127,127,.3)",
      background: "rgba(127,127,127,.1)", color: "inherit",
    },
    empty: { opacity: ".6", padding: "28px 0", textAlign: "center" },
    // ── 仓库知识卡片 ──
    rcard: {
      border: "1px solid rgba(128,128,128,.22)", borderRadius: "10px",
      padding: "12px 14px", marginBottom: "10px",
    },
    rhead: { display: "flex", alignItems: "baseline", gap: "10px", flexWrap: "wrap" },
    rtitle: { fontSize: "14.5px", fontWeight: "650", wordBreak: "break-all" },
    rcommit: { fontSize: "10.5px", opacity: ".55", marginLeft: "auto" },
    rscope: { fontSize: "10.5px", opacity: ".55", marginTop: "3px" },
    rbadges: { display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "8px" },
    rtabs: { display: "flex", gap: "2px", marginTop: "10px",
             borderBottom: "1px solid rgba(128,128,128,.18)" },
    rtab: { padding: "4px 10px", fontSize: "11.5px", cursor: "pointer",
            opacity: ".6", borderBottom: "2px solid transparent" },
    rtabOn: { opacity: "1", fontWeight: "600", borderBottomColor: "#4b6fd6" },
    rpane: { marginTop: "10px", maxHeight: "260px", overflowY: "auto" },
    tree: { fontSize: "11.5px", fontFamily: "ui-monospace,Menlo,Consolas,monospace" },
    sz: { opacity: ".45", fontSize: "10px" },
    crow: { display: "flex", alignItems: "center", gap: "8px",
            padding: "4px 0", fontSize: "11.5px",
            borderBottom: "1px solid rgba(128,128,128,.1)" },
    srow: { display: "flex", gap: "10px", padding: "3px 0", fontSize: "11.5px" },
    sk: { opacity: ".55", minWidth: "76px", flex: "none" },
    // ── 项目文档 ──
    docbar: { display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" },
    docchip: { padding: "3px 10px", fontSize: "11.5px", cursor: "pointer",
               border: "1px solid rgba(128,128,128,.28)", borderRadius: "999px",
               opacity: ".72" },
    docchipOn: { opacity: "1", fontWeight: "600", borderColor: "#4b6fd6",
                 color: "#4b6fd6" },
    seclist: { display: "flex", gap: "4px", flexWrap: "wrap", marginBottom: "8px",
               paddingBottom: "8px", borderBottom: "1px solid rgba(128,128,128,.14)" },
    secitem: { padding: "2px 8px", fontSize: "11px", cursor: "pointer",
               borderRadius: "5px", opacity: ".62" },
    secitemOn: { opacity: "1", background: "rgba(75,111,214,.14)", fontWeight: "600" },
    docbody: { maxHeight: "420px", overflowY: "auto", paddingRight: "6px" },
    docH: { fontSize: "13px", fontWeight: "650", margin: "10px 0 6px" },
    docP: { fontSize: "12.5px", lineHeight: "1.65", margin: "6px 0",
            wordBreak: "break-word" },
    docCode: { fontSize: "11.5px", lineHeight: "1.5", padding: "8px 10px",
               background: "rgba(128,128,128,.1)", borderRadius: "6px",
               overflowX: "auto", margin: "8px 0",
               fontFamily: "ui-monospace,Menlo,Consolas,monospace" },
    docTable: { width: "100%", borderCollapse: "collapse", fontSize: "11.5px",
                margin: "8px 0" },
    docCell: { padding: "4px 8px", borderBottom: "1px solid rgba(128,128,128,.16)",
               textAlign: "left", wordBreak: "break-all" },
    docList: { fontSize: "12.5px", lineHeight: "1.6", margin: "6px 0",
               paddingLeft: "20px" },
    docQuote: { fontSize: "12px", padding: "6px 10px", margin: "8px 0",
                borderLeft: "3px solid #4b6fd6",
                background: "rgba(75,111,214,.07)", borderRadius: "0 5px 5px 0" },
    lim: { fontSize: "11.5px", padding: "6px 9px", marginBottom: "6px",
           borderLeft: "3px solid #d97706", background: "rgba(217,119,6,.08)",
           borderRadius: "0 5px 5px 0" },
  };

  // ══ 仓库知识卡片 ══════════════════════════════════════════════
  //   数据来自宿主 /repocard → SourceLore_Data/派生视图/<repo>/<commit>/
  //   的 card-data.json + code-graph.json，与项目文档同源。
  var VERDICT = {
    supported: { zh: "支持", c: "#16a34a" },
    refuted: { zh: "反驳", c: "#dc2626" },
    insufficient_evidence: { zh: "证据不足", c: "#d97706" },
    unknown: { zh: "未裁决", c: "#9ca3af" },
  };

  function loadRepos(set) {
    set({ status: "loading" });
    getJson(api("/repositories")).then(function (r) {
      var repos = (r && r.repositories) || [];
      if (!repos.length) {
        set({ status: "ok", cards: [], tabs: {},
              diag: "repos=0 raw=" + JSON.stringify(r).slice(0, 160) });
        return;
      }
      var done = [], remaining = repos.length, errs = [];
      repos.forEach(function (rp) {
        getJson(api("/repocard?repository_id=" + encodeURIComponent(rp.repository_id)))
          .then(function (d) {
            if (d && d.ok && d.card) done.push(d);
            else errs.push(String(rp.repository_id) + ":" + String((d && d.error) || "NO_CARD"));
          })
          .catch(function (e) { errs.push(String(rp.repository_id) + ":" + String(e && e.message || e)); })
          .then(function () {
            remaining -= 1;
            if (remaining === 0) {
              done.sort(function (a, b) {
                return String((a.card || {}).title || "")
                  .localeCompare(String((b.card || {}).title || ""));
              });
              set({ status: "ok", cards: done, tabs: {}, errs: errs });
            }
          });
      });
    }).catch(function (e) {
      set({ status: "failed", message: String(e.message || e) });
    });
  }

  function Badge(h, k, n) {
    var v = VERDICT[k] || VERDICT.unknown;
    return h("span", {
      key: k,
      style: Object.assign({}, S.badge, {
        color: v.c, border: "1px solid " + v.c,
        background: "transparent", marginLeft: 0,
      }),
    }, v.zh + " " + n);
  }

  function TreePane(h, graph) {
    var rows = ((graph && graph.nodes) || []).filter(function (n) {
      return n.node_type === "file" || n.node_type === "directory";
    }).sort(function (a, b) {
      return String("/" + a.path).localeCompare(String("/" + b.path));
    });
    if (!rows.length) return h("div", { style: S.sub }, "无条目");
    return h("div", { style: S.tree }, rows.map(function (n) {
      var isDir = n.node_type === "directory";
      var name = String(n.path || "").split("/").pop();
      var depth = String(n.path || "").split("/").length - 1;
      return h("div", {
        key: n.id,
        style: { paddingLeft: depth * 14 + "px",
                 color: isDir ? "#4b6fd6" : "inherit",
                 fontWeight: isDir ? 600 : 400 },
      }, (isDir ? "▸ " : "· ") + name,
        (!isDir && n.size != null) ? h("span", { style: S.sz }, " " + n.size + " B") : null);
    }));
  }

  function ClaimsPane(h, card) {
    var cs = (card && card.claims) || [];
    if (!cs.length) return h("div", { style: S.sub }, "本仓库暂无已登记命题。");
    return h("div", null, cs.map(function (c) {
      var v = VERDICT[c.verdict] || VERDICT.unknown;
      return h("div", { key: c.claim_id, style: S.crow },
        h("span", { style: Object.assign({}, S.dot, { background: v.c }) }),
        h("span", { style: { flex: "1", wordBreak: "break-all" } },
          String(c.claim_type || "-") + " · " + String(c.path || "-")),
        h("span", { style: { color: "#6b7280", flex: "none" } }, v.zh),
        h("span", { style: { color: "#9ca3af", flex: "none", marginLeft: "8px" } },
          "证据 " + (c.fact_count || 0)));
    }));
  }

  function StatPane(h, card) {
    var g = (card && card.graph) || {};
    var nt = g.node_types || {}, et = g.edge_types || {};
    function row(k, v) {
      return h("div", { key: k, style: S.srow },
        h("span", { style: S.sk }, k),
        h("span", { style: { wordBreak: "break-all" } }, v));
    }
    function fmt(o) {
      var ks = Object.keys(o).sort();
      return ks.length ? ks.map(function (k) { return k + " " + o[k]; }).join(" · ") : "-";
    }
    return h("div", null,
      row("节点", String(g.node_count || 0)),
      row("边", String(g.edge_count || 0)),
      row("节点构成", fmt(nt)),
      row("边构成", fmt(et)),
      row("树完整度", String((card.completeness || {}).tree_status_label || "-")),
      row("图谱摘要", String(g.graph_digest || "").slice(0, 24)));
  }

  // ★ 项目知识文档面板：真正渲染正文，不是文件名清单
  function DocPane(h, docs, st, setSelDoc) {
    if (!docs || !docs.length) {
      return h("div", { style: S.sub }, "本仓库暂无已生成的项目文档。");
    }
    var cur = docs[st.selDocIdx || 0] || docs[0];
    var secs = cur.sections || [];
    return h("div", null,
      // 文档选择条
      h("div", { style: S.docbar },
        docs.map(function (d, i) {
          var on = (st.selDocIdx || 0) === i;
          return h("span", {
            key: d.document_id || String(i),
            style: Object.assign({}, S.docchip, on ? S.docchipOn : null),
            onClick: function () { setSelDoc(i); },
          }, String(d.title || d.document_id || "-"));
        })),
      // 章节导航
      secs.length > 1
        ? h("div", { style: S.seclist },
            secs.map(function (sec, i) {
              var on = (st.selSecIdx || 0) === i;
              return h("div", {
                key: sec.section_id || String(i),
                style: Object.assign({}, S.secitem, on ? S.secitemOn : null),
                onClick: function () { setSelDoc(st.selDocIdx || 0, i); },
              }, String(sec.heading || ""));
            }))
        : null,
      // 正文
      h("div", { style: S.docbody },
        secs.length
          ? renderSections(h, secs, st.selSecIdx || 0)
          : h("div", { style: S.sub }, "该文档暂无章节内容。")));
  }

  // 极简 Markdown 渲染：标题/表格/列表/代码块/引用
  function renderSections(h, secs, only) {
    var picked = (only >= 0 && only < secs.length) ? [secs[only]] : secs;
    var out = [];
    picked.forEach(function (sec, si) {
      out.push(h("div", { key: "h" + si, style: S.docH }, String(sec.heading || "")));
      var lines = String(sec.body || "").split("\n");
      var i = 0, buf = [];
      function flushPara() {
        if (!buf.length) return;
        out.push(h("div", { key: "p" + si + "-" + out.length, style: S.docP },
          buf.join(" ")));
        buf = [];
      }
      while (i < lines.length) {
        var ln = lines[i];
        if (/^```/.test(ln)) {
          flushPara();
          var code = [];
          i++;
          while (i < lines.length && !/^```/.test(lines[i])) { code.push(lines[i]); i++; }
          out.push(h("pre", { key: "c" + si + "-" + out.length, style: S.docCode },
            code.join("\n")));
          i++;
          continue;
        }
        if (/^\|.*\|\s*$/.test(ln)) {
          flushPara();
          var rows = [];
          while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) {
            var cells = lines[i].split("|").slice(1, -1)
              .map(function (x) { return x.trim(); });
            if (!/^[-: ]+$/.test(cells.join(""))) rows.push(cells);
            i++;
          }
          out.push(h("table", { key: "t" + si + "-" + out.length, style: S.docTable },
            h("tbody", null, rows.map(function (r, ri) {
              return h("tr", { key: String(ri) }, r.map(function (c2, ci) {
                return h(ri === 0 ? "th" : "td",
                  { key: String(ci), style: S.docCell }, String(c2));
              }));
            }))));
          continue;
        }
        if (/^\s*[-*]\s+/.test(ln) || /^\s*\d+\.\s+/.test(ln)) {
          flushPara();
          var items = [];
          while (i < lines.length &&
                 (/^\s*[-*]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
            items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
            i++;
          }
          out.push(h("ul", { key: "u" + si + "-" + out.length, style: S.docList },
            items.map(function (it, ii) {
              return h("li", { key: String(ii) }, String(it));
            })));
          continue;
        }
        if (/^>\s?/.test(ln)) {
          flushPara();
          out.push(h("div", { key: "q" + si + "-" + out.length, style: S.docQuote },
            ln.replace(/^>\s?/, "")));
          i++;
          continue;
        }
        if (!ln.trim()) { flushPara(); i++; continue; }
        buf.push(ln.trim());
        i++;
      }
      flushPara();
    });
    return out;
  }

  function RepoCard(props) {
    var h = props.h;
    // ★ Tab 状态放在卡片自己身上：父层 setState 一旦被当作整体替换，
    //   会把 cards 一起清掉（实测：点一次 tab 变 0 个仓库）。卡片自治最稳。
    var docs = d.documents || [];
    var ts = react.useState(docs.length ? "docs" : "tree");
    var tab = ts[0], setTab = ts[1];
    // ★ 文档/Tab 状态放在卡片自身，父层不参与（避免父 setState 覆写 cards）
    var ds = react.useState({ selDocIdx: 0, selSecIdx: 0 });
    var dst = ds[0], dset = ds[1];
    function setSelDoc(di, si) {
      dset({
        selDocIdx: di,
        selSecIdx: (si === undefined) ? 0 : si,
      });
    }
    var d = props.data || {};
    var c = d.card || {};
    var g = d.graph || {};
    var vs = c.verdict_summary || {};
    var tabs = [];
    if (docs.length) tabs.push(["docs", "项目文档"]);
    tabs.push(["tree", "文件结构"], ["claims", "知识主张"],
              ["stat", "图谱统计"], ["limit", "限制"]);
    var lims = c.limitations || [];

    return h("div", { style: S.rcard },
      h("div", { style: S.rhead },
        h("span", { style: S.rtitle }, String(c.title || d.repository_id || "-")),
        h("span", { style: S.rcommit }, String(d.commit_sha || "").slice(0, 10))),
      h("div", { style: S.rscope }, "固定 Commit · 不代表仓库当前最新状态"),
      h("div", { style: S.rbadges },
        Object.keys(vs).map(function (k) { return Badge(h, k, vs[k]); })),
      h("div", { style: S.rtabs }, tabs.map(function (t) {
        return h("span", {
          key: t[0],
          style: Object.assign({}, S.rtab, tab === t[0] ? S.rtabOn : null),
          onClick: function () { setTab(t[0]); },
        }, t[1]);
      })),
      h("div", { style: S.rpane },
        tab === "docs" ? DocPane(h, docs, dst, setSelDoc)
          : tab === "tree" ? TreePane(h, g)
          : tab === "claims" ? ClaimsPane(h, c)
          : tab === "stat" ? StatPane(h, c)
          : (lims.length
              ? h("div", null, lims.map(function (x, i) {
                  return h("div", { key: String(i), style: S.lim }, String(x));
                }))
              : h("div", { style: S.sub }, "无已知限制。"))));
  }

  // ★ 错误边界：本卡片任何异常都不得冒泡到 Bot 主面板（否则整个 Welcome 白屏）
  // ★ 极简安全壳：不依赖 react hooks、不依赖任何 S（样式表）以外的对象，
  //   确保即使内部逻辑全崩，Bot 主面板也不会跟着白屏。
  // ★ 必须用 createElement 渲染 Panel，绝不能直接调用 Panel(props)：
  //   Panel 内用了 useState/useEffect，当普通函数调用会破坏 hooks 上下文 → 整个 Bot 面板白屏。
  function SafePanel(props) {
    return react.createElement(Panel, props);
  }

  function Panel(props) {
    var h = props.h;
    var st = props.state;
    var set = props.set;

    if (st.status === "loading") {
      return h("div", { style: S.wrap },
        h("div", { style: S.sub }, "正在读取 SourceLore 知识库…"));
    }
    if (st.status === "failed") {
      return h("div", { style: S.wrap },
        h("div", { style: S.title }, "仓库知识卡片"),
        h("div", { style: S.sub }, "读取失败：" + st.message));
    }

    var cards = st.cards || [];
    return h("div", { style: S.wrap },
      h("div", { style: S.head },
        h("span", { style: S.title }, "仓库知识卡片"),
        h("span", { style: S.sub }, cards.length + " 个仓库")),
      cards.length === 0
        ? h("div", { style: S.empty },
            "知识库里还没有已生成的仓库卡片",)
        : h("div", null, cards.map(function (d, i) {
            return h(RepoCard, { key: String(i), h: h, data: d });
          })),
      st.diag ? h("div", { style: S.sub }, "DIAG: " + st.diag) : null,
      (st.errs && st.errs.length)
        ? h("div", { style: S.sub }, "诊断：" + st.errs.join(" · "))
        : null,
      h("div", { style: S.foot },
        h("button", { style: S.btn, onClick: function () { loadRepos(set); } }, "刷新"),
        h("span", { style: S.sub }, "与项目文档同源 · 派生视图")));
  }

  function SourcelorePanel() {
    var h = react.createElement;
    var st = react.useState({ status: "loading", cards: [], tabs: {} });
    var s = st[0], set = st[1];
    react.useEffect(function () { loadRepos(set); }, []);
    return h(Panel, { h: h, state: s, set: set });
  }

  // ★ Bot 主页槽位：window.__bhHomeSlots__（由 @botharness/ui 的 BhHomeSlot 渲染）
  //   插件只推 {id, component}，UI 侧无注册时不渲染任何东西，因此不影响 Bot 原生外观。
  var SLOT_KEY = "__bhHomeSlots__";

  function slotList() {
    if (typeof window === "undefined") return null;
    if (!Array.isArray(window[SLOT_KEY])) window[SLOT_KEY] = [];
    return window[SLOT_KEY];
  }

  // ★ 官方扩展点（2026-11-11 从 @botharness/ui 1.6.1 源码实证）：
  //   Tobs 自己用 ctx.provide("dockPanels") 暴露注册表，内置的「活动中心」「插件市场」
  //   都通过 dockPanels.register(panel) 注册。第三方插件走同一个口子即可——
  //   既不用改 @botharness/ui，也不会被 Tobs 升级覆盖。
  //
  //   panel 契约（照 createMarketPanel 抄的）：
  //     { id, title, icon, scope:"global", order, defaultPosition:{zone:"right"},
  //       component: () => ReactNode, headerAction?: () => ReactNode }
  //   id 校验：/^[a-zA-Z0-9:@._-]{1,160}$/，且不得以 "instance:" 开头。
  var PANEL_ID = "sourcelore:repo-cards";
  var _dispose = null;

  function apply(ctx) {
    if (!ctx || typeof ctx.get !== "function") {
      return;
    }
    var done = false;

    function tryRegister(registry, viaLabel) {
      if (done || !registry || typeof registry.register !== "function") return false;
      try {
        if (_dispose) { try { _dispose(); } catch (e) {} }
        _dispose = registry.register({
          id: PANEL_ID,
          title: "仓库知识卡片",
          icon: "folder",
          scope: "global",
          order: 520,
          defaultPosition: { zone: "right" },
          component: function () { return react.createElement(SourcelorePanel); },
        });
        done = true;
        try { window.__sourcelorePanel__ = { id: PANEL_ID, via: viaLabel, build: BUILD }; } catch (e) {}
        try { ctx.logger && ctx.logger.info("[sourcelore] 面板已注册 via " + viaLabel + " BUILD=" + BUILD); } catch (e) {}
        try {
          fetch(api("/panelstatus"), { method: "POST", cache: "no-store",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ ok: true, via: viaLabel, build: BUILD,
              panelId: PANEL_ID }) });
        } catch (e) {}
        return true;
      } catch (e) {
        try { ctx.logger && ctx.logger.warn("[sourcelore] register 失败(" + viaLabel + "): " + (e && e.message)); } catch (e2) {}
        return false;
      }
    }

    // 立即尝试注册（幂等：已注册则忽略）
    (function () {
      var reg = null;
      try { reg = ctx.get("dockPanels"); } catch (e) {
        
        return;
      }
      if (!reg) {  return; }
      if (typeof reg.register !== "function") {
        
        return;
      }
      try {
        reg.register({
          id: PANEL_ID, title: "仓库知识卡片", icon: "folder",
          scope: "global", order: 520,
          defaultPosition: { zone: "right" },
          component: function () { return react.createElement(SourcelorePanel); },
        });
        
      } catch (e) {
        var msg = String(e && e.message || e);
        if (msg.indexOf("duplicate") < 0) {
          try { ctx.logger && ctx.logger.warn("[sourcelore] 注册失败: " + msg); } catch (e2) {}
        }
      }
      // ★ 主动打开：registry.open(id) 内部是 `layout?.open(id)`，
      //   而 layout 只在 Bot 面板挂载时由 attach() 注入（registry.available()）。
      //   Bot 模式未挂载时调用会被静默丢弃 —— 必须轮询到 available() 为真再开。
      openWhenReady();

    })();

    // ★ 等 dock 布局真正挂载后再开面板（最多约 60 秒）
    function openWhenReady() {
      var n = 0;
      function tick() {
        n++;
        var r = null;
        try { r = ctx.get("dockPanels"); } catch (e) {}
        if (r && typeof r.open === "function") {
          var ready = false;
          try { ready = typeof r.available === "function" ? r.available() : true; } catch (e) { ready = false; }
          var isOpen = false;
          try { isOpen = typeof r.isOpen === "function" ? r.isOpen(PANEL_ID) : false; } catch (e) {}
          if (ready && !isOpen) {
            try { r.open(PANEL_ID); } catch (e) {}
            try { ctx.logger && ctx.logger.info("[sourcelore] panel opened after " + n + " ticks"); } catch (e) {}
            // 再确认一次
            setTimeout(function () {
              try { if (typeof r.isOpen === "function" && !r.isOpen(PANEL_ID)) r.open(PANEL_ID); } catch (e) {}
            }, 800);
            return;
          }
        }
        if (n < 240) setTimeout(tick, 250);
      }
      setTimeout(tick, 300);
    }

    // 路径 1：注入回调（服务已就绪时走这条）
    try {
      ctx.inject(["dockPanels"], function (c) {
        tryRegister(c && c.dockPanels, "inject");
      });
    } catch (e) {}

    // 路径 2：轮询 ctx.get（Tobs 可能在 apply 之后才 provide）
    var tries = 0;
    function poll() {
      if (done || tries++ > 40) return;
      var r = null;
      try { r = ctx.get("dockPanels"); } catch (e) {}
      if (tryRegister(r, "poll#" + tries)) return;
      setTimeout(poll, 250);
    }
    setTimeout(poll, 0);
  }

  exports.apply = apply;
    // ★★ 这里必须留空！2026-11-12 实证：
    //   client 的 inject 同样会被宿主看到，声明客户端服务 dockPanels 会让插件永久
    //   pending（waiting for service: dockPanels）→ 整个插件不挂载。
    //   dockPanels 在 apply(ctx) 内部用 ctx.inject / ctx.get 取，不需要在这里声明。
    exports.inject = [];
    return module.exports;
  },
});
