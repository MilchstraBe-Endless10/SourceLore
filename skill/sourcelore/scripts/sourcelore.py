#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore Skill 启动器。

★ 自包含地把工程 src/ 加入 sys.path，然后交给 skill_interface.cli。
不依赖当前工作目录、不依赖安装目录内副本。
"""

import os
import sys
from pathlib import Path

# 优先用环境变量指定的工程根；否则从本文件向上查找 SourceLore 根
_HERE = Path(__file__).resolve()


def _find_project_root() -> Path:
    """★ 三级回退：环境变量 → 安装 marker → 向上查找。

    安装到 ~/.agents/skills 后目录与工程分离，
    因此安装时会写入 marker 记录工程根。
    """
    env = os.environ.get("SOURCELORE_PROJECT_ROOT")
    if env:
        return Path(env).resolve()

    marker = _HERE.parents[1] / ".sourcelore-skill.json"
    if marker.exists():
        try:
            import json
            root = Path(json.loads(marker.read_text(encoding="utf-8"))
                        .get("project_root", ""))
            if root and (root / "src" / "skill_interface" / "cli.py").exists():
                return root
        except Exception:
            pass

    for up in _HERE.parents:
        if (up / "src" / "skill_interface" / "cli.py").exists():
            return up
    raise SystemExit(
        "找不到 SourceLore 工程根；请设置 SOURCELORE_PROJECT_ROOT")


PROJECT_ROOT = _find_project_root()
for name in ("runtime", "storage", "collector", "facts", "evidence_claims",
             "lifecycle", "views", "renderer", "research", "skill_interface"):
    p = PROJECT_ROOT / "src" / name
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
