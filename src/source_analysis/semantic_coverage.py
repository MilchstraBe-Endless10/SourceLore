#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语义覆盖度：区分「解析成功」与「语义被完整理解」。

★ 核心教训：PARSE_COMPLETE 只证明语法树构造成功，
  不证明这个文件的语义已被规则覆盖。
"""

# 分析覆盖状态
PARSE_COMPLETE = "PARSE_COMPLETE"
SUPPORTED_FACTS_EXTRACTED = "SUPPORTED_FACTS_EXTRACTED"
VALID_EMPTY_RESULT = "VALID_EMPTY_RESULT"
UNSUPPORTED_SEMANTIC_FORM = "UNSUPPORTED_SEMANTIC_FORM"
PARSE_FAILED = "PARSE_FAILED"
SOURCE_CONTENT_NOT_CAPTURED = "SOURCE_CONTENT_NOT_CAPTURED"
SOURCE_FACTS_NOT_PERSISTED = "SOURCE_FACTS_NOT_PERSISTED"

# 已支持的规则族（与 js_ts_import_export_rules 实际能力一致）
SUPPORTED_RULE_FAMILIES = (
    "symbol_declaration",     # function / class / const 声明
    "es_export_statement",    # export function / const / default / *
    "es_import_statement",    # import ... from
)

# 已识别但当前规则族未覆盖的形态
UNSUPPORTED_FORMS = {
    "commonjs_module_exports": "module.exports = ...",
    "commonjs_exports_prop": "exports.foo = ...",
    "commonjs_require": "require(...)",
    "dynamic_import": "import(...)",
    "reexport_star_as": "export * as ns from",
}


def detect_unsupported_forms(text):
    """有界识别：只找形态出现，不做语义分析。★ 不执行任何代码。"""
    found = []
    if "module.exports" in text:
        found.append("commonjs_module_exports")
    if "exports." in text and "module.exports" not in text:
        found.append("commonjs_exports_prop")
    if "require(" in text:
        found.append("commonjs_require")
    if "import(" in text:
        found.append("dynamic_import")
    return found


def classify(*, parse_status, language, facts_persisted, observed_nodes,
             unsupported_forms, content_available=True):
    """给出分析覆盖状态与报告。★ 绝不把「未覆盖」说成「没有」。"""
    if not content_available:
        return {"analysis_coverage": SOURCE_CONTENT_NOT_CAPTURED,
                "explain": "内容未捕获，无法分析"}

    if parse_status == "PARSE_FAILED":
        return {"analysis_coverage": PARSE_FAILED,
                "explain": "语法解析失败"}

    if facts_persisted > 0:
        return {"analysis_coverage": SUPPORTED_FACTS_EXTRACTED,
                "explain": "已提取并持久化受支持规则的事实"}

    if parse_status == PARSE_COMPLETE and facts_persisted == 0:
        # ★ D-62：解析器观察到受支持节点、却 0 事实入库 → 阻断级缺陷，
        #   绝不能用 VALID_EMPTY_RESULT 掩盖（is-plain-obj 的 index.js 就是这样被谎报的）。
        if observed_nodes > 0:
            return {"analysis_coverage": SOURCE_FACTS_NOT_PERSISTED,
                    "explain": ("解析器观察到 %d 个受支持节点，但没有任何事实入库；"
                                "这是语义提取/入库缺陷，不是合法空结果"
                                % observed_nodes),
                    "unsupported_forms": list(unsupported_forms or [])}
        if unsupported_forms:
            # ★ 关键区别：解析成功但存在已识别、未支持的形态
            #   → UNSUPPORTED_SEMANTIC_FORM，不是 VALID_EMPTY_RESULT
            return {"analysis_coverage": UNSUPPORTED_SEMANTIC_FORM,
                    "explain": ("语法解析成功，但文件中存在已识别且当前规则族"
                                "未覆盖的语义形态；不能据此判定该文件没有导出"),
                    "unsupported_forms": list(unsupported_forms)}
        return {"analysis_coverage": VALID_EMPTY_RESULT,
                "explain": "解析成功且受支持规则已实际检查完毕，未发现符合规则的声明",
                "unsupported_forms": []}

    return {"analysis_coverage": SOURCE_FACTS_NOT_PERSISTED,
            "explain": "解析完成但事实未持久化"}


def coverage_report(*, file_path, language, parser_version, parse_status,
                    facts_persisted, claims_verified, observed_nodes,
                    unsupported_forms, content_available=True):
    cls = classify(parse_status=parse_status, language=language,
                   facts_persisted=facts_persisted,
                   observed_nodes=observed_nodes,
                   unsupported_forms=unsupported_forms,
                   content_available=content_available)
    return {
        "file_path": file_path,
        "language": language,
        "parser_version": parser_version,
        "parse_status": parse_status,
        "supported_rule_families": list(SUPPORTED_RULE_FAMILIES),
        "observed_supported_nodes": observed_nodes,
        "recognized_but_unsupported_forms": [
            {"form": f, "sample": UNSUPPORTED_FORMS.get(f, "")}
            for f in (unsupported_forms or [])],
        "facts_persisted": facts_persisted,
        "claims_verified": claims_verified,
        "analysis_coverage": cls["analysis_coverage"],
        "explain": cls["explain"],
        "limitations": [
            "只报告实际具备规则覆盖的语法类别",
            "分析覆盖不等于完整理解 JavaScript",
            "静态分析不等于运行时行为验证",
        ],
    }
