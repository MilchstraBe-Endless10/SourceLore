#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装 SourceLore Skill 到 ~/.agents/skills/sourcelore（受控复制）。

★ 不覆盖其他项目；已存在且非本项目时拒绝。
"""
import json, shutil, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "skill" / "sourcelore"
DEST = Path.home() / ".agents" / "skills" / "sourcelore"
MARKER = ".sourcelore-skill.json"


def tree_hash(p: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(p)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:32]


def main(dry=False) -> int:
    if not (SRC / "SKILL.md").exists():
        print(json.dumps({"ok": False, "error": "源 SKILL.md 缺失"}))
        return 1

    existing = DEST.exists()
    owned = (DEST / MARKER).exists()
    if existing and not owned:
        print(json.dumps({"ok": False, "error": "目标已存在且非本项目",
                          "detail": str(DEST)}, ensure_ascii=False))
        return 1

    if dry:
        print(json.dumps({"ok": True, "dry_run": True,
                          "src": str(SRC), "dest": str(DEST),
                          "would_overwrite": existing}, ensure_ascii=False))
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    if existing:
        bak = DEST.with_suffix(".bak")
        if bak.exists():
            shutil.rmtree(bak)
        shutil.move(str(DEST), str(bak))
    shutil.copytree(SRC, DEST)
    (DEST / MARKER).write_text(json.dumps({
        "project": "SourceLore",
        "project_root": str(ROOT),          # ★ 安装后定位工程根
        "source": str(SRC),
        "source_tree_hash": tree_hash(SRC)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    print(json.dumps({"ok": True, "installed": str(DEST),
                      "skill_md": str(DEST / "SKILL.md"),
                      "files": sorted(str(p.relative_to(DEST))
                                      for p in DEST.rglob("*") if p.is_file())},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
