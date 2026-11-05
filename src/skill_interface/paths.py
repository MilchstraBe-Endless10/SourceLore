#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径解析：数据根、包根、模块导入。

★ 不依赖当前工作目录；不依赖模型记住项目路径。
"""

import os
import sys
from pathlib import Path

# 本文件名固定，用于反推包根（src/ 的父目录）
_THIS = Path(__file__).resolve()

SRC_ROOT = _THIS.parents[1]          # .../SourceLore/src
PROJECT_ROOT = SRC_ROOT.parent       # .../SourceLore

DEFAULT_DATA_ROOT = Path(
    os.environ.get("SOURCELORE_DATA_ROOT")
    or (Path.home() / ".sourcelore")
)

SKILL_VERSION = "f2p5a/1.0"


def ensure_import_path() -> None:
    """把 src/ 下各模块目录加入 sys.path（现有工程是扁平模块，无统一包）。"""
    for name in ("runtime", "storage", "collector", "facts", "evidence_claims",
                 "lifecycle", "views", "renderer", "research", "skill_interface"):
        p = SRC_ROOT / name
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


def db_path(data_root: Path | str | None = None) -> Path:
    root = Path(data_root) if data_root else DEFAULT_DATA_ROOT
    return root / "kb.db"


def guard_inside_project_db(p: Path) -> None:
    """★ 数据库不得写进 Git 仓库。"""
    try:
        resolved = p.resolve()
    except Exception:
        return
    if str(resolved).startswith(str(PROJECT_ROOT.resolve()) + os.sep):
        raise RuntimeError(
            f"拒绝把知识库写进 Git 仓库：{resolved}；"
            f"请用 SOURCELORE_DATA_ROOT 指向仓库外目录")
