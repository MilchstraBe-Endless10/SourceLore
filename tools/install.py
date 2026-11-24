#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SourceLore official installer.

Subcommands:
  install   Install/refresh the Skill from a Git checkout or a release ZIP.
  doctor    Report install state; never modifies anything.
  update    Safe staged update (backup + integrity check + rollback).
  uninstall Remove only SourceLore install/Skill files; preserve user data.

Design rules:
  - Never touch the knowledge-base data root (kb.db, captured bytes, docs).
  - Never overwrite a Skill dir we do not own (no install marker => refuse).
  - No hardcoded author paths; no dependence on a Chinese mount or username.
  - Work under any path containing spaces, parentheses or non-ASCII chars.
  - No network calls. No root required. Never executes analyzed repo code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

VERSION_FALLBACK = "0.1.0-beta.2"
MARKER = ".sourcelore-install.json"          # owner marker written at install root
LEGACY_MARKER = ".sourcelore-skill.json"     # legacy marker from f2p5a_install.py
REQUIRED_SKILL_FILES = ["SKILL.md", "scripts/sourcelore.py"]
REQUIRED_PROJECT_FILES = ["src/skill_interface/cli.py", "src/skill_interface/version.py"]


def now() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def emit(obj: dict) -> int:
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    return 0 if obj.get("ok", True) else 1


def default_skill_dest() -> Path:
    """Agent-host discovery root. User-level ~/.agents/skills is the default."""
    override = os.environ.get("SOURCELORE_SKILL_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".agents" / "skills" / "sourcelore"


def _layout(root: Path) -> tuple[Path, Path] | None:
    """Return (skill_dir, project_root_with_src) for either source layout.

    checkout: <root>/skill/sourcelore + <root>/src
    ZIP root: <root> (SKILL.md/scripts)  + <root>/_sourcelore_src
    """
    checkout_skill = root / "skill" / "sourcelore"
    if (checkout_skill / "SKILL.md").is_file() and (root / "src" / "skill_interface" / "cli.py").is_file():
        return checkout_skill, root
    if (root / "SKILL.md").is_file() and (root / "scripts" / "sourcelore.py").is_file():
        proj = root / "_sourcelore_src"
        if (proj / "src" / "skill_interface" / "cli.py").is_file():
            return root, proj
    return None


def read_version_from_checkout(root: Path) -> str | None:
    """Read the single source of truth version without importing project code."""
    layout = _layout(root)
    if layout:
        root = layout[1]
    vp = root / "src" / "skill_interface" / "version.py"
    if not vp.is_file():
        return None
    try:
        for line in vp.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("RELEASE_VERSION") and "=" in s:
                return s.split("=", 1)[1].strip().strip('"\'')
    except Exception:
        pass
    return None


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            h.update(str(f.relative_to(root)).encode("utf-8", "ignore"))
            h.update(f.read_bytes())
        except Exception:
            pass
    return h.hexdigest()[:32]


def verify_source(root: Path) -> tuple[bool, str]:
    """A valid source has both Skill files and the project CLI files."""
    layout = _layout(root)
    if not layout:
        return False, "unrecognized layout (need checkout skill/sourcelore + src, or ZIP skill root + _sourcelore_src)"
    skill_dir, proj_root = layout
    missing = [p for p in REQUIRED_SKILL_FILES if not (skill_dir / p).is_file()]
    missing += [p for p in REQUIRED_PROJECT_FILES if not (proj_root / p).is_file()]
    if missing:
        return False, "missing: " + ", ".join(missing)
    return True, "ok"


def is_owned(dest: Path) -> bool:
    return (dest / MARKER).is_file() or (dest / LEGACY_MARKER).is_file()


def check_launcher(dest: Path) -> tuple[bool, str]:
    launcher = dest / "scripts" / "sourcelore.py"
    if not launcher.is_file():
        return False, "launcher missing"
    import subprocess
    try:
        r = subprocess.run([sys.executable, str(launcher), "--version"],
                           capture_output=True, text=True, timeout=30,
                           env={**os.environ, "SOURCELORE_PROJECT_ROOT": str(
                               _project_root_from_marker(dest) or dest.parent.parent)})
        if r.returncode == 0 and "skill_version" in r.stdout:
            return True, json.loads(r.stdout).get("skill_version", "?")
        return False, (r.stderr or r.stdout).strip()[:200]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _project_root_from_marker(dest: Path) -> Path | None:
    for m in (MARKER, LEGACY_MARKER):
        mp = dest / m
        if mp.is_file():
            try:
                d = json.loads(mp.read_text(encoding="utf-8"))
                v = d.get("project_root") or d.get("install_root")
                if v:
                    return Path(v)
            except Exception:
                pass
    return None


def _data_root_status(path: Path) -> str:
    if not path.exists():
        return "not_created"
    try:
        if any(path.rglob("*.db")):
            return "initialized"
    except Exception:
        pass
    return "empty"


def cmd_doctor(args) -> int:
    """Read-only health check with an explicit, machine-readable status contract.

    status is one of: ok, not_installed, unowned, incomplete, launcher_failed,
    version_mismatch. Only status=ok sets ok/healthy=true and exit code 0.
    An empty/uninitialized data root is reported separately and never fails the
    install check.
    """
    dest = Path(args.skill_dir).expanduser() if args.skill_dir else default_skill_dest()
    data_root = Path(os.environ.get("SOURCELORE_DATA_ROOT", "~/.sourcelore")).expanduser()
    result = {
        "ok": False,
        "status": "unknown",
        "healthy": False,
        "issue": None,
        "skill_dir": str(dest),
        "installed": dest.is_dir(),
        "owned_by_sourcelore": False,
        "marker": None,
        "launcher_ok": False,
        "launcher_version": None,
        "launcher_version_or_error": "not installed",
        "expected_version": getattr(args, "expect_version", None),
        "data_root": str(data_root),
        "data_root_status": _data_root_status(data_root),
        "note": "doctor is read-only; no files were modified",
    }

    if not dest.is_dir():
        result.update(status="not_installed", issue="Skill directory does not exist")
        return emit(result)

    result["owned_by_sourcelore"] = is_owned(dest)
    for m in (MARKER, LEGACY_MARKER):
        if (dest / m).is_file():
            try:
                result["marker"] = json.loads((dest / m).read_text(encoding="utf-8"))
            except Exception:
                pass
            break

    if not result["owned_by_sourcelore"]:
        result.update(status="unowned",
                      issue="directory exists but has no SourceLore install marker")
        return emit(result)

    proj_root = _project_root_from_marker(dest) or dest
    missing = [p for p in REQUIRED_SKILL_FILES if not (dest / p).is_file()]
    missing += [p for p in REQUIRED_PROJECT_FILES if not (proj_root / p).is_file()]
    if missing:
        result.update(status="incomplete", issue="missing files: " + ", ".join(missing))
        return emit(result)

    launcher_ok, launcher_info = check_launcher(dest)
    result["launcher_ok"] = launcher_ok
    result["launcher_version_or_error"] = launcher_info
    if not launcher_ok:
        result.update(status="launcher_failed", issue="launcher failed: " + str(launcher_info))
        return emit(result)

    result["launcher_version"] = launcher_info
    expect = getattr(args, "expect_version", None)
    marker_version = (result["marker"] or {}).get("version")
    if expect and launcher_info != expect:
        result.update(status="version_mismatch",
                      issue=f"launcher version {launcher_info} != expected {expect}")
        return emit(result)
    if marker_version and launcher_info != marker_version:
        result.update(status="version_mismatch",
                      issue=f"launcher version {launcher_info} != marker version {marker_version}")
        return emit(result)

    result.update(ok=True, healthy=True, status="ok", issue=None)
    return emit(result)


def _copy_source_into(source_root: Path, dest: Path) -> None:
    """Install Skill files plus the project source it needs, self-contained."""
    layout = _layout(source_root)
    if not layout:
        raise RuntimeError("unrecognized source layout")
    skill_src, proj_root = layout
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_src, dest)
    # Bundle project's src/ as <dest>/_sourcelore_src/src/ so that the launcher,
    # which checks <project_root>/src/skill_interface/cli.py, resolves correctly
    # when project_root = <dest>/_sourcelore_src.
    bundle_root = dest / "_sourcelore_src"
    bundle_root.mkdir(parents=True, exist_ok=True)
    bundled = bundle_root / "src"
    src_src = proj_root / "src"
    if bundled.exists():
        # ZIP source already contains _sourcelore_src/src; refresh in place.
        shutil.rmtree(bundled)
    shutil.copytree(src_src, bundled)
    # The launcher locates the project root via a legacy marker (or by walking
    # upward for src/). Point project_root at the bundled src so a ZIP install
    # keeps working after the original checkout/temp dir is deleted.
    installed_version = read_version_from_checkout(source_root) or VERSION_FALLBACK
    marker_data = {
        "project": "SourceLore",
        "install_mode": "self_contained",
        "version": installed_version,
        "installed_at": now(),
        "source_hash": tree_hash(source_root),
        "project_root": str(bundle_root),  # contains src/skill_interface/cli.py
    }
    (dest / MARKER).write_text(json.dumps(marker_data, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    (dest / LEGACY_MARKER).write_text(json.dumps(marker_data, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")


def cmd_install(args) -> int:
    source_root = _resolve_source(args)
    if source_root is None:
        return emit({"ok": False, "error": "cannot resolve SourceLore source checkout / ZIP"})
    ok, why = verify_source(source_root)
    if not ok:
        return emit({"ok": False, "error": "invalid source", "detail": why})

    dest = Path(args.skill_dir).expanduser() if args.skill_dir else default_skill_dest()
    if dest.exists() and not is_owned(dest):
        return emit({"ok": False, "error": "target exists and is not a SourceLore install",
                     "detail": str(dest), "hint": "choose --skill-dir or remove it manually"})

    if args.dry_run:
        return emit({"ok": True, "dry_run": True, "source": str(source_root),
                     "dest": str(dest), "would_overwrite": dest.exists()})

    _copy_source_into(source_root, dest)
    launcher_ok, info = check_launcher(dest)
    return emit({"ok": launcher_ok, "installed": str(dest),
                 "version": read_version_from_checkout(source_root),
                 "launcher": info,
                 "data_root_preserved": True})


def _self_source_dir() -> Path:
    """Directory of this installer. Inside a release ZIP this is the ZIP root."""
    return Path(__file__).resolve().parent


def _resolve_source(args) -> Path | None:
    if getattr(args, "zip", None):
        return _unzip_safely(Path(args.zip).expanduser())
    if getattr(args, "source", None):
        root = Path(args.source).expanduser()
        return root if _layout(root) else None
    # No explicit source: prefer the current directory (a repo checkout), then
    # fall back to this installer's own directory (self-contained release ZIP).
    for root in (Path.cwd(), _self_source_dir()):
        if _layout(root):
            return root
    return None


def _unzip_safely(zp: Path) -> Path | None:
    """Extract a release ZIP into a temp dir, blocking path traversal and symlinks."""
    import zipfile
    if not zp.is_file():
        return None
    base = Path(tempfile.mkdtemp(prefix="sourcelore-zip-"))
    try:
        with zipfile.ZipFile(zp) as z:
            for member in z.infolist():
                name = member.filename
                if name.startswith("/") or ".." in Path(name).parts:
                    return None
                target = base / name
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        # ZIP entries are rooted under "sourcelore/". Normalize to that
        # directory regardless of extra top-level files inside it.
        root = base / "sourcelore"
        if not root.is_dir():
            root = base
        if (root / "src" / "skill_interface" / "cli.py").is_file() or \
           (root / "scripts" / "sourcelore.py").is_file():
            return root
        # Fallback: a single directory that itself contains the skill.
        subs = [p for p in root.iterdir() if p.is_dir()]
        for s in subs:
            if (s / "scripts" / "sourcelore.py").is_file():
                return s
        return None
    except Exception:
        return None


def cmd_update(args) -> int:
    source_root = _resolve_source(args)
    if source_root is None:
        return emit({"ok": False, "error": "cannot resolve new version source"})
    ok, why = verify_source(source_root)
    if not ok:
        return emit({"ok": False, "error": "invalid new version source", "detail": why})
    new_ver = read_version_from_checkout(source_root) or VERSION_FALLBACK

    dest = Path(args.skill_dir).expanduser() if args.skill_dir else default_skill_dest()
    if dest.exists() and not is_owned(dest):
        return emit({"ok": False, "error": "refuse to update a Skill dir we do not own",
                     "detail": str(dest)})

    # Stage complete new version in a temp directory next to dest.
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".sourcelore-stage-", dir=str(dest.parent)))
    try:
        _copy_source_into(source_root, staging / "sourcelore")
        stage = staging / "sourcelore"
        launch_ok, info = check_launcher(stage)
        if not launch_ok:
            return emit({"ok": False, "error": "staged version failed launcher check",
                         "detail": info})

        backup = None
        if dest.exists():
            backup = dest.with_name(f"{dest.name}.bak-{now()}")
            shutil.move(str(dest), str(backup))
        try:
            shutil.move(str(stage), str(dest))
        except Exception as e:
            if backup and backup.exists():
                shutil.move(str(backup), str(dest))
            return emit({"ok": False, "error": "switch failed, rolled back", "detail": str(e)})

        return emit({"ok": True, "updated": str(dest), "version": new_ver,
                     "previous_backup": str(backup) if backup else None,
                     "data_root_touched": False})
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def cmd_uninstall(args) -> int:
    dest = Path(args.skill_dir).expanduser() if args.skill_dir else default_skill_dest()
    if not dest.exists():
        return emit({"ok": True, "removed": None, "note": "not installed"})
    if not is_owned(dest):
        return emit({"ok": False, "error": "refuse to remove a Skill dir we do not own",
                     "detail": str(dest)})
    marker = _project_root_from_marker(dest)
    backup = dest.with_name(f"{dest.name}.uninstalled-{now()}")
    shutil.move(str(dest), str(backup))
    return emit({"ok": True, "removed": str(dest), "backup": str(backup),
                 "user_data_preserved": True,
                 "note": "knowledge base, config and generated docs were NOT touched"})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="install.py", description="SourceLore official installer")
    p.add_argument("--version", action="store_true", help="show installer version")
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--skill-dir", default=None,
                        help="target Skill directory (default ~/.agents/skills/sourcelore)")

    si = sub.add_parser("install", help="install SourceLore Skill")
    common(si)
    src = si.add_mutually_exclusive_group()
    src.add_argument("--source", default=None, help="path to a SourceLore Git checkout")
    src.add_argument("--zip", default=None, help="path to a standalone release ZIP")
    si.add_argument("--dry-run", action="store_true")

    sd = sub.add_parser("doctor", help="read-only install diagnostics")
    common(sd)
    sd.add_argument("--json", action="store_true")
    sd.add_argument("--expect-version", default=None,
                    help="fail with version_mismatch if launcher reports a different version")

    su = sub.add_parser("update", help="safe staged update")
    common(su)
    usrc = su.add_mutually_exclusive_group()
    usrc.add_argument("--source", default=None)
    usrc.add_argument("--zip", default=None)

    sn = sub.add_parser("uninstall", help="remove SourceLore install only")
    common(sn)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        detected = read_version_from_checkout(_self_source_dir()) or VERSION_FALLBACK
        return emit({"ok": True, "installer_version": detected})
    if args.cmd == "install":
        return cmd_install(args)
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "update":
        return cmd_update(args)
    if args.cmd == "uninstall":
        return cmd_uninstall(args)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
