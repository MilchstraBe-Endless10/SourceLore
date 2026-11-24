#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a self-contained standalone Skill release ZIP + SHA-256 manifest.

The ZIP contains everything needed to run the Skill independently:
  sourcelore/SKILL.md, references/, scripts/, bundled src/, RELEASE_INFO.json
It never includes the knowledge database, captured third-party bytes, tokens,
local config, .venv, or any path/marker from the developer's machine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_version() -> str:
    for line in (ROOT / "src" / "skill_interface" / "version.py").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("RELEASE_VERSION") and "=" in s:
            return s.split("=", 1)[1].strip().strip('"\'')
    raise RuntimeError("RELEASE_VERSION not found")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(out_dir: Path) -> dict:
    version = read_version()
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sl-release-") as td:
        stage = Path(td) / "sourcelore"
        stage.mkdir()
        # Skill instruction set
        skill_src = ROOT / "skill" / "sourcelore"
        for item in skill_src.iterdir():
            if item.name in (".sourcelore-install.json", ".sourcelore-skill.json"):
                continue
            if item.is_dir():
                (stage / item.name).mkdir(parents=True, exist_ok=True)
                for f in item.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(skill_src)
                        dst = stage / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(f.read_bytes())
            elif item.is_file():
                (stage / item.name).write_bytes(item.read_bytes())
        # Self-contained program source (all of src/)
        bundle = stage / "_sourcelore_src" / "src"
        bundle.parent.mkdir(parents=True, exist_ok=True)
        for f in (ROOT / "src").rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                rel = f.relative_to(ROOT / "src")
                dst = bundle / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(f.read_bytes())
        # Release metadata embedded in the ZIP
        info = {
            "project": "SourceLore",
            "version": version,
            "tag": "v" + version,
            "install_mode": "self_contained",
            "project_root": "_sourcelore_src",
            "contains_user_data": False,
        }
        (stage / "RELEASE_INFO.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        import zipfile
        zip_path = out_dir / f"sourcelore-skill-v{version}.zip"
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(stage.rglob("*")):
                if f.is_file():
                    z.write(f, str(Path("sourcelore") / f.relative_to(stage)))
        digest = sha256(zip_path)

    manifest = {
        "version": version,
        "tag": "v" + version,
        "artifact": zip_path.name,
        "sha256": digest,
        "files": [p.name for p in out_dir.iterdir() if p.is_file()],
        "note": "Verify with: sha256sum -c SHA256SUMS.txt",
    }
    (out_dir / "SHA256SUMS.txt").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    (out_dir / "RELEASE_INFO.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "zip": str(zip_path), "sha256": digest,
            "version": version, "out_dir": str(out_dir)}


def main():
    ap = argparse.ArgumentParser(prog="build_release.py")
    ap.add_argument("--out", default="dist", help="output directory")
    args = ap.parse_args()
    print(json.dumps(build(Path(args.out).expanduser()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
