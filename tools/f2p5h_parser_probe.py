#!/usr/bin/env python3
"""F2P5H tree-sitter 兼容探针。★ 必须真实加载 grammar 并解析四类源码。

用法: python3 tools/f2p5h_parser_probe.py [--json]
"""
import json
import sys

CASES = {
    "javascript": (".js", "tree_sitter_javascript", "language", """
function run() {}
const start = () => {};
class Worker { execute() { return 1; } }
"""),
    "jsx": (".jsx", "tree_sitter_javascript", "language", """
function App() { return <div className="x">hi</div>; }
"""),
    "typescript": (".ts", "tree_sitter_typescript", "language_typescript", """
interface User { id: number }
type Id = string;
enum Color { Red, Green }
function typed(x: number): string { return String(x); }
"""),
    "tsx": (".tsx", "tree_sitter_typescript", "language_tsx", """
interface P { n: number }
function C(p: P) { return <div>{p.n}</div>; }
"""),
}


def probe():
    out = {"core_version": None, "grammars": [], "cases": [], "ok": False,
           "python": sys.version.split()[0]}
    try:
        import tree_sitter
        out["core_version"] = getattr(tree_sitter, "__version__", "unknown")
    except Exception as e:
        out["error"] = f"core import failed: {type(e).__name__}: {e}"
        return out

    from tree_sitter import Language, Parser

    loaded = {}
    for lang_id, (_, mod_name, fn_name, _) in CASES.items():
        try:
            mod = __import__(mod_name)
            fn = getattr(mod, fn_name)
            lang = Language(fn())
            loaded[lang_id] = lang
            out["grammars"].append({
                "package": mod_name, "call": fn_name, "language_id": lang_id,
                "version": getattr(mod, "__version__", "unknown"),
                "abi": getattr(lang, "abi_version", None),
                "node_kind_count": lang.node_kind_count
                if hasattr(lang, "node_kind_count") else None,
                "loaded": True})
        except Exception as e:
            out["grammars"].append({"package": mod_name, "call": fn_name,
                                    "language_id": lang_id, "loaded": False,
                                    "error": f"{type(e).__name__}: {e}"})

    for lang_id, (ext, _, _, src) in CASES.items():
        rec = {"language_id": lang_id, "ext": ext}
        if lang_id not in loaded:
            rec["status"] = "GRAMMAR_UNAVAILABLE"
            out["cases"].append(rec); continue
        try:
            raw = src.encode("utf-8")
            p = Parser(loaded[lang_id])
            tree = p.parse(raw)
            root = tree.root_node
            rec.update({
                "status": "PARSE_COMPLETE" if not root.has_error
                          else "PARSE_WITH_ERRORS",
                "root_type": root.type,
                "root_start_byte": root.start_byte,
                "root_end_byte": root.end_byte,
                "byte_len": len(raw),
                "has_error": root.has_error,
                "child_count": root.child_count,
                "node_types": _top_types(root)[:8],
            })
            # 二次解析一致
            tree2 = p.parse(raw)
            rec["deterministic"] = (
                tree2.root_node.start_byte == root.start_byte
                and tree2.root_node.end_byte == root.end_byte
                and tree2.root_node.child_count == root.child_count)
            # 错误检测
            bad = p.parse(b"function ( {")
            rec["detects_error"] = bad.root_node.has_error
        except Exception as e:
            rec["status"] = "PARSER_ERROR"
            rec["error"] = f"{type(e).__name__}: {e}"
        out["cases"].append(rec)

    out["ok"] = (all(g.get("loaded") for g in out["grammars"])
                 and all(c.get("status") in ("PARSE_COMPLETE", "PARSE_WITH_ERRORS")
                         for c in out["cases"]))
    return out


def _top_types(root):
    seen = []
    for ch in root.children:
        if ch.type not in seen:
            seen.append(ch.type)
    return seen


if __name__ == "__main__":
    r = probe()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"python: {r['python']}  core: {r['core_version']}")
        for g in r["grammars"]:
            print(f"  [{'OK' if g.get('loaded') else 'FAIL'}] {g['package']}"
                  f".{g['call']}()  v={g.get('version')} abi={g.get('abi')}"
                  + ("" if g.get("loaded") else f"  {g.get('error')}"))
        for c in r["cases"]:
            print(f"  {c['language_id']:12s} {c.get('status')}"
                  f"  types={c.get('node_types')}"
                  f"  det={c.get('deterministic')}"
                  f"  errdet={c.get('detects_error')}")
        print("\n结论:", "PASS" if r["ok"] else "FAIL")
    sys.exit(0 if r["ok"] else 1)
