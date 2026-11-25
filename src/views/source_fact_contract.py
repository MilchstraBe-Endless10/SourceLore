"""源码事实统一读取契约（P2-C §2 前置门禁 GRAPH_SEMANTIC_CLASSIFICATION_INTEGRITY）。

★ 为什么必须存在：
  P2-B 的 _code_rows() 用 "IMPORT" in rule_id 猜 kind，且只认
  subject.source_reference / subject.module_specifier。Python AST 的导入事实
  实际写的是 module_name + relative_level + imported_name，module_specifier=null。
  结果：153 条 SOURCE_IMPORT_DECLARED 里 from_import 被误当符号声明（有 name+kind、
  无 ref），普通 import 连 name 都没有被丢弃 —— arch-grower 图谱出现
  DECLARES 189 / IMPORTS 0 / RESOLVES_TO 0 的假象。

★ 本模块是唯一分类与 specifier 规范化口径，供 derive/graph/miner/answer 共用：
  - classify(rule_id)   精确按真实 rule_id 分类，不靠模糊包含；
  - normalize_subject() 把 Python / JS / TS 导入字段统一成 module_specifier
                        与 source_reference，不动已落库 Facts（只读派生）。
"""


# 真实 rule_id 常量（与 source_fact_ingest.py 一致，冗余在此以免导入耦合）
RULE_SYMBOL = "SOURCE_SYMBOL_DECLARED"
RULE_IMPORT = "SOURCE_IMPORT_DECLARED"
RULE_EXPORT = "SOURCE_EXPORT_DECLARED"
RULE_LOCAL = "SOURCE_LOCAL_MODULE_RESOLVED"

_SYNC_RULES = {
    RULE_SYMBOL: "symbol",
    RULE_IMPORT: "import",
    RULE_EXPORT: "export",
    RULE_LOCAL: "relation",
}


def classify(rule_id):
    """按真实 rule_id 精确返回 kind；未知类型返回 kind=None 而不冒充符号。"""
    if not rule_id:
        return None
    return _SYNC_RULES.get(str(rule_id).strip())


def normalize_module_specifier(subject, *, language=None, module_name=None,
                               imported_name=None, relative_level=0,
                               import_syntax=None):
    """把不同语言的导入字段规范化成模块说明符字符串。

    - Python 绝对导入：module_name，如 "argparse" / "arch_engine"；
      from_import 带 imported_name 时保留为 "module.name"（仅作说明符展示，
      不做文件系统推断）；
    - Python 相对导入：'.' * relative_level + (module_name or '')；
    - JS/TS：module_specifier 原样（如 "./graph_ops" / "preact/hooks"）。
    返回 None 表示无法形成说明符，调用方应如实记录，不得编造。
    """
    lang = (language or "").lower()
    if lang == "python":
        level = int(relative_level or 0)
        base = (module_name or "").strip()
        if level:
            spec = "." * level + base
        elif base:
            spec = base
        else:
            return None
        return spec or None
    # JS/TS 与其它语言：优先 module_specifier，其次 module_name
    return (module_name or "").strip() or None


def normalize_subject(rule_id, subject, *, file_path=None, commit_sha=None,
                      repository_id=None, fact_id=None):
    """返回规范化后的 subject 副本（不改入参），补齐统一字段。

    统一字段：
      - kind             : symbol / import / export / relation
      - module_specifier : 规范化说明符（仅 import/export）
      - source_reference : 与 module_specifier 同值，兼容既有 reader
      - name             : 符号或导入名的稳定展示名（仅用于 label）
    原字段（module_name/imported_name/relative_level/...）全部保留供证据回查。
    """
    subj = dict(subject or {})
    kind = classify(rule_id)
    subj["kind"] = kind or "unknown"
    lang = subj.get("language")
    name = (subj.get("qualified_name") or subj.get("symbol_name")
            or subj.get("exported_name") or subj.get("imported_name")
            or subj.get("name"))
    subj["name"] = name

    if kind in ("import", "export"):
        spec = subj.get("module_specifier") or subj.get("source_reference")
        if not spec:
            spec = normalize_module_specifier(
                subj,
                language=lang,
                module_name=subj.get("module_name"),
                imported_name=subj.get("imported_name"),
                relative_level=subj.get("relative_level", 0),
                import_syntax=subj.get("import_syntax"))
        if spec:
            subj["module_specifier"] = spec
            # source_reference 统一为说明符；from_import 的成员名不冒充 ref
            subj["source_reference"] = spec
    return subj
