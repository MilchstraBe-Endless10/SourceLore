#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""package.json 解析器：用 json 真解析，不靠正则猜。"""

import json

from content_models import P_PKGJSON
PARSER_VERSION = "1.0.0"

DEP_FIELDS = ("dependencies", "devDependencies", "peerDependencies",
              "optionalDependencies")


def parse(text):
    """返回 (ok, data_or_None, error_code, error_msg)。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return False, None, "MANIFEST_INVALID_JSON", f"{e.msg} @line {e.lineno}"
    if not isinstance(data, dict):
        return False, None, "MANIFEST_NOT_OBJECT", "顶层不是 JSON 对象"
    return True, data, None, None


def extract(data, text):
    """抽取声明字段。★ 全部只读，不执行任何 scripts。"""
    facts = []
    for f in ("name", "version", "private"):
        if f in data:
            facts.append({"field": f, "value": data[f], "kind": "field"})
    for df in DEP_FIELDS:
        block = data.get(df)
        if isinstance(block, dict):
            for name, spec in sorted(block.items()):
                facts.append({"field": df, "dependency": name,
                              "constraint": str(spec), "kind": "dependency"})
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        for name in sorted(scripts):
            facts.append({"field": "scripts", "script_name": name,
                          "kind": "script_declared"})
    return facts
