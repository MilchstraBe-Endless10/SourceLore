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

# ★ 数据根解析优先级（单一权威来源，CLI / Skill / 定时任务共用）：
#   1) --data-root 参数（调用方显式传入 db_path(data_root=...)）
#   2) SOURCELORE_DATA_ROOT 环境变量
#   3) ~/.config/sourcelore/config.json 的 data_root
#   4) ~/.sourcelore（旧默认）
# ★ 不把某台机器的绝对路径硬编码进核心模块 —— 配置从文件读。
CONFIG_PATH = Path.home() / ".config" / "sourcelore" / "config.json"


def _configured_data_root():
    try:
        if CONFIG_PATH.exists():
            import json
            d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            v = (d or {}).get("data_root")
            if isinstance(v, str) and v.strip():
                return Path(v).expanduser()
    except Exception:
        pass
    return None


DEFAULT_DATA_ROOT = (
    Path(os.environ["SOURCELORE_DATA_ROOT"]).expanduser()
    if os.environ.get("SOURCELORE_DATA_ROOT")
    else (_configured_data_root() or (Path.home() / ".sourcelore"))
)

SKILL_VERSION = "f2p5a/1.0"


def ensure_import_path() -> None:
    """把 src/ 下各模块目录加入 sys.path（现有工程是扁平模块，无统一包）。"""
    for name in ("runtime", "storage", "collector", "facts", "evidence_claims",
                 "lifecycle", "views", "renderer", "research", "skill_interface", "content", "content_persistence",
                 "source_analysis"):
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
