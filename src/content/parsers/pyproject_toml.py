#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pyproject.toml 解析器：优先 tomllib（3.11+），否则明确不可解析。"""

from content_models import P_PYPROJECT
PARSER_VERSION = "1.0.0"

try:
    import tomllib as _toml
except Exception:      # pragma: no cover
    _toml = None


def available() -> bool:
    return _toml is not None


def parse(text):
    if _toml is None:
        return False, None, "PARSER_UNAVAILABLE", "本机无 tomllib，拒绝用正则猜测"
    try:
        data = _toml.loads(text)
    except Exception as e:
        return False, None, "MANIFEST_INVALID_TOML", f"{type(e).__name__}: {e}"
    if not isinstance(data, dict):
        return False, None, "MANIFEST_NOT_OBJECT", "顶层不是表"
    return True, data, None, None


def extract(data, text):
    facts = []
    proj = data.get("project")
    if isinstance(proj, dict):
        for f in ("name", "version", "description"):
            if f in proj:
                facts.append({"field": f"project.{f}", "kind": "field"})
        deps = proj.get("dependencies")
        if isinstance(deps, list):
            for spec in deps:
                if isinstance(spec, str):
                    name = spec.split(">=")[0].split("==")[0].split("<")[0]
                    name = name.split("[")[0].split("~")[0].strip()
                    facts.append({"field": "project.dependencies",
                                  "dependency": name, "constraint": spec,
                                  "kind": "dependency"})
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        for k in tool:
            facts.append({"field": f"tool.{k}", "kind": "table_present"})
    return facts
