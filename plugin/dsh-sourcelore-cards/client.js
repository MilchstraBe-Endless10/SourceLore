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

  // ★ bh:home 是**已退役的 panel id**（源码 RETIRED_RAIL_IDS = [HOME_SLOT, "bh:tob-mode"]），
  //   不是可注册的 slot。注册到它上面不会渲染 —— 这是上一版看不到面板的根因。
  var SECTION_SLOT = "botharness.settings.section";
  var ID = "dsh-sourcelore-cards";

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
    return fetch(url, { headers: { accept: "application/json" } })
      .then(function (r) { return r.json(); });
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
  };

  function StatusCard(props) {
    var h = props.h;
    var item = props.item;
    var st = STATE[item.state] || STATE.NOT_ANALYZED;
    var open = props.open;
    var hover = props.hover;
    var style = Object.assign({}, S.card, hover ? S.cardHover : null);
    var left = {
      position: "absolute", left: 0, top: 0, bottom: 0, width: "3px",
      borderRadius: "11px 0 0 11px", background: st.c,
    };
    return h("div", {
      style: style,
      onClick: props.onToggle,
      onMouseEnter: props.onHover,
      onMouseLeave: props.onLeave,
      title: item.name,
    },
      h("div", { style: left }),
      h("div", { style: S.name }, item.name),
      h("div", { style: S.meta },
        h("span", { style: Object.assign({}, S.dot, { background: st.c }) }),
        h("span", null, item.kind || ""),
        h("span", null, item.line ? "L" + item.line : ""),
        h("span", {
          style: Object.assign({}, S.badge, {
            color: st.c, background: st.ring, border: "1px solid " + st.c,
          }),
        }, st.zh)),
      open ? h("div", { style: Object.assign({}, S.links, { display: "block" }) },
        h("div", null, "↗ 仓库 ", props.repo),
        h("div", null, "↗ 文件 " + (props.file || "-")),
        h("div", null, "↗ claim ..." + String(item.claim_id || "").slice(-8))
      ) : null
    );
  }

  function Panel(props) {
    var h = props.h;
    var st = props.state;
    var set = props.set;

    if (st.status === "loading") {
      return h("div", { style: S.wrap }, h("div", { style: S.sub }, "正在读取 SourceLore 知识库…"));
    }
    if (st.status === "failed") {
      return h("div", { style: S.wrap },
        h("div", { style: S.title }, "知识卡片"),
        h("div", { style: S.sub }, "读取失败：" + st.message));
    }

    var items = st.items || [];
    return h("div", { style: S.wrap },
      h("div", { style: S.head },
        h("span", { style: S.title }, "源码知识卡片"),
        h("span", { style: S.repo }, st.repo || "-"),
        h("span", { style: S.sub }, items.length + " 张")),
      h("div", { style: S.sub },
        st.commit ? "commit " + String(st.commit).slice(0, 10) : "",
        st.file ? " · " + st.file : ""),

      items.length === 0
        ? h("div", { style: S.empty }, "这个文件还没有可展示的裁决")
        : h("div", { style: S.wall }, items.map(function (it, i) {
            return h(StatusCard, {
              key: String(i), h: h, item: it, repo: st.repo, file: st.file,
              open: st.openIdx === i, hover: st.hoverIdx === i,
              onToggle: function () { set({ openIdx: st.openIdx === i ? -1 : i }); },
              onHover: function () { set({ hoverIdx: i }); },
              onLeave: function () { set({ hoverIdx: -1 }); },
            });
          })),

      h("div", { style: S.foot },
        h("button", {
          style: S.btn,
          onClick: function () {
            var vault = window.prompt("Obsidian vault 目录：");
            if (!vault) return;
            getJson(api("/export?repository_id=" + encodeURIComponent(st.rid)
              + (st.commit ? "&commit=" + st.commit : "")
              + (st.file ? "&path=" + encodeURIComponent(st.file) : "")
              + "&vault=" + encodeURIComponent(vault)))
              .then(function (o) {
                var r = o.obsidian || {};
                set({ note: "已导出 " + (r.notes_written || 0) + " 篇笔记到 " + vault });
              });
          },
        }, "导出到 Obsidian"),
        h("button", {
          style: S.btn,
          onClick: function () {
            set({ status: "loading" });
            loadFirst(set);
          },
        }, "刷新"),
        st.note ? h("span", { style: S.sub }, st.note) : null)
    );
  }

  function loadFirst(set) {
    getJson(api("/repositories")).then(function (r) {
      var first = (r.repositories || [])[0];
      if (!first) { set({ status: "ok", items: [], repo: "-" }); return; }
      getJson(api("/card?repository_id=" + encodeURIComponent(first.repository_id)))
        .then(function (c) {
          var items = (c.claims || []).map(function (x) {
            var s = x.subject || {};
            return {
              name: s.qualified_name || s.exported_name || s.module_name || "?",
              kind: x.kind, state: x.display_level,
              line: x.start_line, claim_id: x.claim_id,
            };
          });
          set({
            status: "ok", items: items, openIdx: -1, hoverIdx: -1,
            repo: c.repository || first.repository || String(first.repository_id),
            rid: first.repository_id, commit: c.commit_sha, file: c.file_path,
          });
        })
        .catch(function (e) { set({ status: "failed", message: String(e.message || e) }); });
    }).catch(function (e) { set({ status: "failed", message: String(e.message || e) }); });
  }

  function apply(ctx) {
    ctx.slots.inject(SECTION_SLOT, function () {
      return ctx.slots.register(
        { name: SECTION_SLOT, id: ID, order: 40, label: "源码知识卡片" },
        function (react) {
          var h = react.createElement;
          var useState = react.useState;
          var useEffect = react.useEffect;
          var st = useState({ status: "loading", items: [], openIdx: -1, hoverIdx: -1 });
          var s = st[0], set = st[1];
          useEffect(function () { loadFirst(set); }, []);
          return h(Panel, { h: h, state: s, set: set });
        }
      );
    });
  }

    exports.apply = apply;
    exports.inject = ["slots"];
    return module.exports;
  },
});
