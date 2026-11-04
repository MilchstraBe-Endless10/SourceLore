#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Facts 抽取规则注册表。

契约：SL-CAP-0008（观察 vs 推断分层）。

**规则版本是硬契约：**
逻辑一变就必须升版本，不能静默改旧版本的含义。
旧版本的事实记录必须仍能按其原版本重放。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from models import (OBJ_BLOB, OBJ_COMMIT, OBJ_TREE, OBJ_UNKNOWN,
                    MODE_DIR, MODE_SUBMODULE, MODE_SYMLINK)

EXTRACTOR_VERSION = "sourcelore-facts/1.0.0"

# ── 规则 1：file_path_observation ─────────────────────────────
RULE_FILE_PATH = "file_path_observation"
RULE_FILE_PATH_V1 = "v1"

RULES = {
    (RULE_FILE_PATH, RULE_FILE_PATH_V1): {
        "description": "在固定快照的 Tree 清单中观察某个路径是否存在",
        "parameters": {
            "target_path": "必填；仓库相对路径，按 normalize_path 规则标准化",
        },
        "produces": "单结果",
        "deterministic": True,
        "uses_llm": False,
    },
}

# 混合用途禁止：本批所有规则都必须声明不用 LLM
for _key, _meta in RULES.items():
    assert _meta["uses_llm"] is False, f"规则 {_key} 违反无 LLM 约束"
    assert _meta["deterministic"] is True, f"规则 {_key} 违反确定性约束"


def get_rule(rule_id: str, rule_version: str) -> dict:
    key = (rule_id, rule_version)
    if key not in RULES:
        raise KeyError(f"未注册的规则: {rule_id}@{rule_version}")
    return RULES[key]


def describe_object(obj_type: str, mode: str) -> dict:
    """把 Tree 条目翻译成**不夸大**的描述。

    关键：symlink / submodule / 目录**不得**被描述成普通文件。
    """
    is_reg = (obj_type == OBJ_BLOB and mode not in (MODE_SYMLINK, MODE_SUBMODULE))

    kind = "regular_file"
    if mode == MODE_SYMLINK or mode == "120000":
        kind = "symlink"
    elif mode == MODE_SUBMODULE or obj_type == OBJ_COMMIT:
        kind = "submodule"
    elif mode == MODE_DIR or obj_type == OBJ_TREE:
        kind = "directory"
    elif obj_type == OBJ_UNKNOWN:
        kind = "unknown_object"
    elif obj_type == OBJ_BLOB:
        kind = "regular_file"

    return {
        "object_type": obj_type,
        "mode": mode,
        "object_kind": kind,
        "is_regular_file": bool(is_reg and kind == "regular_file"),
        # 明确写死：不是普通文件时，不得按普通文件理解
        "note": (None if kind == "regular_file"
                 else f"该条目是 {kind}，不是普通文件；不得按普通文件处理"),
    }
