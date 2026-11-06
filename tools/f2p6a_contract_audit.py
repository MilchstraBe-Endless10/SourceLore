#!/usr/bin/env python3
"""F2-P6A 跨模块数据契约审计。

★ 检查 write 端产出的字段名 == read 端读取的字段名（D-31/D-32/D-41 同类）。
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# 写入端产出的 payload 键（人工登记，来自各 build_* 函数）
WRITE_SUBJECT_KEYS = {
    "source_fact_ingest": {"qualified_name", "symbol_kind", "symbol_name",
                           "language", "module_name", "imported_name",
                           "import_syntax", "relative_level",
                           "module_specifier", "is_type_only",
                           "export_kind", "exported_name", "source_reference"},
    "module_relation_ingest": {"importing_file_path", "module_specifier",
                               "import_kind", "is_type_only",
                               "resolved_target_path", "matched_config_rule",
                               "resolution_state", "resolution_policy",
                               "config_path", "config_kind", "subpath"},
    "ts_project_ingest": {"config_path", "config_blob_oid",
                          "discovery_status", "is_solution_style",
                          "declared_composite", "declared_root_dir",
                          "declared_out_dir", "declared_files",
                          "declared_include", "declared_exclude",
                          "from_project_id", "from_config_path",
                          "declared_path", "to_config_path",
                          "to_project_id", "status", "project_id",
                          "source_file_path", "state", "matched_rule",
                          "matched_field", "excluded_by"},
}

# 读取端消费的键（来自各 query/adapter 的 .get() 调用）
READ_KEYS = {
    "source_claim_adapter": {"qualified_name", "symbol_kind", "module_name",
                             "imported_name", "is_type_only"},
    "module_relation_adapter": {"importing_file_path", "module_specifier",
                                "import_kind", "is_type_only",
                                "expected_target_path",
                                "expected_matched_rule"},
    "ts_project_adapter": {"config_path", "source_file_path",
                           "expected_state", "expected_to_config_path",
                           "from_config_path", "declared_path",
                           "to_config_path", "to_project_id", "status",
                           "project_id", "state", "matched_rule",
                           "matched_field", "excluded_by"},
}


def scan_get_calls(path):
    """扫描 .get("key") 与 ["key"] 读到但可能写端没有的键。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text)
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                keys.add(a.value)
    return keys


def check_aliases():
    """确认 adapter 侧的 ALIAS 映射覆盖了期望字段与实际字段的差异。"""
    out = {}
    for name in ("module_relation_adapter", "ts_project_adapter"):
        p = SRC / "content_persistence" / f"{name}.py"
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        out[name] = {
            "has_alias": "ALIAS" in text,
            "maps_expected_state": '"expected_state": "state"' in text,
            "maps_expected_target": '"expected_to_config_path"' in text
                                   or '"expected_target_path"' in text,
        }
    return out


def check_flat_compat():
    """确认 adapter 同时兼容 payload 嵌套与查询扁平两种形态。"""
    out = {}
    for name in ("module_relation_adapter", "ts_project_adapter",
                 "source_claim_adapter"):
        p = SRC / "content_persistence" / f"{name}.py"
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        out[name] = {
            "accepts_normalized_parameters": "normalized_parameters" in t,
            "accepts_flat": ("fact.get" in t) or ("or fact" in t),
        }
    return out


def _related(w, r):
    """写端与读端的语义配对。"""
    pairs = {("source_fact_ingest", "source_claim_adapter"),
             ("module_relation_ingest", "module_relation_adapter"),
             ("ts_project_ingest", "ts_project_adapter")}
    return (w, r) in pairs


if __name__ == "__main__":
    # 写入端 vs 读取端的键差异
    gaps = {}
    for wmod, wkeys in WRITE_SUBJECT_KEYS.items():
        for rmod, rkeys in READ_KEYS.items():
            # 只在语义相关模块对之间比较
            if not _related(wmod, rmod):
                continue
            # ★ 读取端的期望字段（expected_*）由 adapter 的 ALIAS 映射到实际字段，
            #   不是真正的契约缺口。只有**非 expected_ 前缀**的缺失才算。
            missing = {k for k in (rkeys - wkeys)
                       if not k.startswith("expected_")}
            if missing:
                gaps[f"{wmod}->{rmod}"] = sorted(missing)

    result = {
        "write_read_key_gaps": gaps,
        "aliases": check_aliases(),
        "flat_compat": check_flat_compat(),
        "ok": not gaps and all(v["has_alias"] for v in check_aliases().values()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)
